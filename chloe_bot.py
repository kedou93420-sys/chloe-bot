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

# ======================
# CONFIG
# ======================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"

# ======================
# MÉMOIRE
# ======================

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
    uid = str(user_id)
    if uid not in memory:
        memory[uid] = {
            "profile": {
                "facts": [],
            },
            "emotion": "neutre",
            "mode": "cool",
            "history": []
        }
    return memory[uid]

# ======================
# ANALYSE ÉMOTION
# ======================

def detect_emotion(text):
    t = text.lower()
    if any(x in t for x in ["merci", "cool", "génial", "j'adore"]):
        return "positif"
    if any(x in t for x in ["ras le bol", "marre", "nul", "fatigué"]):
        return "négatif"
    if any(x in t for x in ["?", "pourquoi", "comment"]):
        return "curieux"
    return "neutre"

# ======================
# MODE AUTO
# ======================

def choose_mode(emotion):
    if emotion == "positif":
        return "taquin"
    if emotion == "négatif":
        return "doux"
    if emotion == "curieux":
        return "sérieux"
    return "cool"

# ======================
# VOIX
# ======================

def voice_probability(emotion):
    if emotion == "positif":
        return 0.7
    if emotion == "négatif":
        return 0.3
    return 0.5

# ======================
# OPENAI
# ======================

async def ask_openai(user_id, user_text):
    mem = get_user_memory(user_id)

    mem["history"].append({"role": "user", "content": user_text})
    mem["history"] = mem["history"][-12:]

    memory_context = ""
    if mem["profile"]["facts"]:
        memory_context = "Souvenirs importants :\n"
        for f in mem["profile"]["facts"][-5:]:
            memory_context += f"- {f}\n"

    mode_prompt = {
        "cool": "Tu es naturelle et détendue.",
        "taquin": "Tu es joueuse, légèrement provocante mais bienveillante.",
        "sérieux": "Tu es claire, posée et pédagogique.",
        "doux": "Tu es rassurante, calme et empathique."
    }

    system_prompt = f"""
Tu t'appelles Chloé.
Tu es une IA féminine expressive.
Tu adaptes ton ton automatiquement.
Mode actuel : {mem["mode"]}.
{mode_prompt[mem["mode"]]}

{memory_context}
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages += mem["history"]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.9
    )

    reply = response.choices[0].message.content
    mem["history"].append({"role": "assistant", "content": reply})
    save_memory(memory)

    return reply

# ======================
# HANDLER
# ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    mem = get_user_memory(user_id)

    # Emotion + mode
    emotion = detect_emotion(text)
    mem["emotion"] = emotion
    mem["mode"] = choose_mode(emotion)

    # Sauvegarde faits importants
    if any(x in text.lower() for x in ["j'aime", "je déteste", "je travaille", "ma passion"]):
        if text not in mem["profile"]["facts"]:
            mem["profile"]["facts"].append(text)

    save_memory(memory)

    # Temps de réflexion
    await asyncio.sleep(random.uniform(1.3, 2.8))

    reply = await ask_openai(user_id, text)

    # Vocal ou texte
    if random.random() < voice_probability(emotion):
        tts = gTTS(reply, lang="fr")
        file = f"voice_{user_id}.mp3"
        tts.save(file)

        with open(file, "rb") as f:
            await update.message.reply_voice(f)

        os.remove(file)
    else:
        await update.message.reply_text(reply)

# ======================
# START
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Coucou… moi c’est Chloé 🤍\n"
        "Je m’adapte à toi naturellement."
    )

# ======================
# MAIN
# ======================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤍 Chloé est en ligne (modes + émotions + voix)")
    app.run_polling()

if __name__ == "__main__":
    main()
