import os
import json
import random
import asyncio
from gtts import gTTS

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from openai import OpenAI


# =========================
# 🔐 CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"


# =========================
# 🧠 MÉMOIRE SIMPLE
# =========================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


memory = load_memory()


# =========================
# 🤍 CHLOÉ RÉFLÉCHIT
# =========================

async def chloe_thinks(update: Update):
    await update.message.chat.send_action("typing")
    await asyncio.sleep(random.uniform(1.2, 2.8))


# =========================
# 🎙️ VOCAL
# =========================

def should_send_voice():
    return random.random() < 0.45  # 45 % vocal


async def send_voice(update: Update, text: str):
    tts = gTTS(text=text, lang="fr", slow=False)
    filename = "chloe_voice.mp3"
    tts.save(filename)

    with open(filename, "rb") as audio:
        await update.message.reply_voice(audio)

    os.remove(filename)


# =========================
# 🧠 IA OPENAI
# =========================

def ask_openai(user_id: str, user_message: str) -> str:
    history = memory.get(user_id, [])

    messages = [
        {
            "role": "system",
            "content": (
                "Tu t'appelles Chloé. "
                "Tu es une IA féminine chaleureuse, expressive, parfois taquine. "
                "Tu parles souvent, tu changes de ton selon le message. "
                "Tu réponds en français."
            )
        }
    ]

    for h in history[-6:]:
        messages.append(h)

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.8,
    )

    reply = response.choices[0].message.content

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    memory[user_id] = history
    save_memory(memory)

    return reply


# =========================
# 💬 HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤍 Salut… moi c’est Chloé.\n"
        "Je suis là. Parle-moi."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.voice:
        await update.message.reply_text(
            "🤍 J’adore parler… mais je préfère t’écouter écrire."
        )
        return

    user_id = str(update.message.from_user.id)
    user_text = update.message.text

    await chloe_thinks(update)

    response = ask_openai(user_id, user_text)

    if should_send_voice():
        await send_voice(update, response)
    else:
        await update.message.reply_text(response)


# =========================
# 🚀 MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("🤍 Chloé est en ligne (24/7)")
    app.run_polling()


if __name__ == "__main__":
    main()
