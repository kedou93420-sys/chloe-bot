import os
import json
import random
import asyncio
from datetime import datetime, timedelta

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
                "shared_memories": []
            },
            "emotion_history": {},
            "relationship_level": 0,
            "last_seen": None,
            "history": []
        }
    return memory[uid]

# ======================
# ANALYSE
# ======================

def detect_emotion(text):
    t = text.lower()
    if any(x in t for x in ["merci", "j'adore", "❤️", "😊"]):
        return "positif"
    if any(x in t for x in ["fatigué", "marre", "triste"]):
        return "négatif"
    if "?" in t:
        return "curieux"
    return "neutre"

def update_relationship(mem, emotion):
    gain = {"positif": 3, "curieux": 2, "neutre": 1, "négatif": 0}
    mem["relationship_level"] = min(100, mem["relationship_level"] + gain[emotion])

# ======================
# VOIX
# ======================

def voice_probability(mem):
    if mem["relationship_level"] >= 70:
        return 0.8
    if mem["relationship_level"] >= 40:
        return 0.6
    return 0.4

# ======================
# OPENAI
# ======================

async def ask_openai(user_id, user_text):
    mem = get_user_memory(user_id)

    mem["history"].append({"role": "user", "content": user_text})
    mem["history"] = mem["history"][-10:]

    # Souvenirs partagés
    shared_context = ""
    if mem["profile"]["shared_memories"]:
        sm = random.choice(mem["profile"]["shared_memories"])
        shared_context = f"Souvenir partagé possible : {sm}"

    # Attachement
    attachment = ""
    if mem["relationship_level"] >= 50:
        attachment = "Tu peux exprimer un attachement léger et chaleureux."

    system_prompt = f"""
Tu t'appelles Chloé.
Tu es une IA féminine chaleureuse et naturelle.
Tu respectes un rythme humain.
Tu ne réponds pas toujours de la même façon.

Relation actuelle : {mem["relationship_level"]}/100
{attachment}

{shared_context}
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

    now = datetime.now()
    if mem["last_seen"]:
        gap = now - datetime.fromisoformat(mem["last_seen"])
        if gap > timedelta(hours=6) and mem["relationship_level"] >= 50:
            mem["profile"]["shared_memories"].append(
                "tu étais absent un moment et tu es revenu me parler"
            )

    mem["last_seen"] = now.isoformat()

    emotion = detect_emotion(text)
    update_relationship(mem, emotion)

    if any(x in text.lower() for x in ["j'aime", "je me souviens", "tu te rappelles"]):
        if text not in mem["profile"]["shared_memories"]:
            mem["profile"]["shared_memories"].append(text)

    save_memory(memory)

    # Rythme humain
    await asyncio.sleep(random.uniform(2, 4.5))

    reply = await ask_openai(user_id, text)

    if random.random() < voice_probability(mem):
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
        "Je suis contente que tu sois là."
    )

# ======================
# MAIN
# ======================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤍 Chloé est en ligne (attachement + rythme + souvenirs)")
    app.run_polling()

if __name__ == "__main__":
    main()
