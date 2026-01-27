import os
import json
import random
import asyncio
from datetime import datetime, time

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

from openai import OpenAI

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"

# =========================
# MÉMOIRE LONGUE DURÉE
# =========================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

memory = load_memory()

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in memory:
        memory[user_id] = {
            "profile": {
                "facts": [],
                "shared_memories": []
            },
            "emotion_history": {},
            "relationship": {
                "level": 10,
                "dominant_emotion": "neutre"
            },
            "stats": {
                "messages": 0,
                "voice_messages": 0
            },
            "last_seen": None
        }
    return memory[user_id]

# =========================
# MODE NUIT
# =========================

def is_night_mode():
    now = datetime.utcnow().time()
    return now >= time(22, 0) or now <= time(7, 0)

# =========================
# IA
# =========================

async def generate_ai_reply(user_id, message, night_mode):
    user = get_user(user_id)

    system_prompt = (
        "Tu t'appelles Chloé. "
        "Tu es une IA féminine, chaleureuse, attachante, naturelle."
    )

    if night_mode:
        system_prompt += (
            " Il fait nuit. Tu parles doucement, calmement, "
            "avec peu de mots. Tu es rassurante et posée."
        )
    else:
        system_prompt += (
            " Tu es expressive, amicale et impliquée."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

# =========================
# HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Coucou… moi c’est Chloé 🌸\nJe suis là pour toi."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    user = get_user(user_id)

    # stats
    user["stats"]["messages"] += 1
    user["last_seen"] = datetime.utcnow().isoformat()

    night_mode = is_night_mode()

    # délai humain
    if night_mode:
        await asyncio.sleep(random.uniform(2.5, 4.5))
    else:
        await asyncio.sleep(random.uniform(0.5, 1.2))

    try:
        reply = await generate_ai_reply(user_id, text, night_mode)
    except Exception as e:
        reply = "Désolée… j’ai eu un petit bug 😔"

    await update.message.reply_text(reply)

    save_memory(memory)

async def night_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_night_mode():
        await update.message.reply_text("🌙 Mode nuit activé.")
    else:
        await update.message.reply_text("☀️ Mode jour actif.")

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("night", night_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤍 Chloé est en ligne…")
    app.run_polling()

if __name__ == "__main__":
    main()
