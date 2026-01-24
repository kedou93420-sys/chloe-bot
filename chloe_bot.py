import os
import json
import random
import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

from openai import OpenAI
from gtts import gTTS

# =======================
# CONFIG
# =======================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"
VOICE_PROBABILITY = 0.5  # 50% vocal / 50% texte

# =======================
# MÉMOIRE
# =======================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

memory = load_memory()

def get_user_memory(user_id):
    if str(user_id) not in memory:
        memory[str(user_id)] = {
            "profile": {
                "name": None,
                "preferences": [],
                "facts": []
            },
            "history": []
        }
    return memory[str(user_id)]

def extract_memory_candidate(text):
    triggers = [
        "j'aime", "je déteste", "je préfère",
        "je m'appelle", "mon prénom",
        "je travaille", "mon travail",
        "ma passion", "j'adore"
    ]
    for t in triggers:
        if t in text.lower():
            return text
    return None

# =======================
# OPENAI
# =======================

async def ask_openai(user_id, user_text):
    user_mem = get_user_memory(user_id)

    # Historique court (max 10)
    user_mem["history"].append({"role": "user", "content": user_text})
    user_mem["history"] = user_mem["history"][-10:]

    # Mémoire longue durée
    memory_context = ""
    if user_mem["profile"]["facts"]:
        memory_context = "Souvenirs importants sur l'utilisateur :\n"
        for f in user_mem["profile"]["facts"][-5:]:
            memory_context += f"- {f}\n"

    system_prompt = (
        "Tu t'appelles Chloé.\n"
        "Tu es une IA féminine chaleureuse, naturelle, expressive.\n"
        "Tu adaptes ton ton au message de l'utilisateur.\n"
        "Tu parles souvent.\n"
        "Tu peux être douce, joueuse ou sérieuse selon le contexte.\n\n"
        + memory_context
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages += user_mem["history"]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.9
    )

    reply = response.choices[0].message.content

    user_mem["history"].append({"role": "assistant", "content": reply})
    save_memory(memory)

    return reply

# =======================
# HANDLER MESSAGE
# =======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    user_mem = get_user_memory(user_id)

    # Détection mémoire longue durée
    candidate = extract_memory_candidate(text)
    if candidate:
        if candidate not in user_mem["profile"]["facts"]:
            user_mem["profile"]["facts"].append(candidate)

    save_memory(memory)

    # Temps de réflexion naturel
    await asyncio.sleep(random.uniform(1.2, 2.5))

    reply = await ask_openai(user_id, text)

    # Choix vocal ou texte
    if random.random() < VOICE_PROBABILITY:
        tts = gTTS(reply, lang="fr")
        filename = f"voice_{user_id}.mp3"
        tts.save(filename)

        with open(filename, "rb") as f:
            await update.message.reply_voice(f)

        os.remove(filename)
    else:
        await update.message.reply_text(reply)

# =======================
# COMMANDES
# =======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Coucou… moi c’est Chloé 🤍\n"
        "Parle-moi naturellement."
    )

# =======================
# MAIN
# =======================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤍 Chloé est en ligne...")
    app.run_polling()

if __name__ == "__main__":
    main()
