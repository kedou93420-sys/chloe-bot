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
            "relationship": {
                "level": 0,
                "last_initiative": None,
                "dominant_emotion": "neutre"
            },
            "stats": {
                "messages": 0,
                "voice_messages": 0
            },
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
    if any(x in t for x in ["triste", "marre", "fatigué"]):
        return "négatif"
    if "?" in t:
        return "curieux"
    return "neutre"

def update_relationship(mem, emotion):
    gain = {"positif": 3, "curieux": 2, "neutre": 1, "négatif": 0}
    mem["relationship"]["level"] = min(
        100, mem["relationship"]["level"] + gain[emotion]
    )
    mem["relationship"]["dominant_emotion"] = emotion

# ======================
# VOIX
# ======================

def voice_probability(mem):
    lvl = mem["relationship"]["level"]
    return 0.4 if lvl < 40 else 0.6 if lvl < 70 else 0.85

# ======================
# OPENAI
# ======================

async def ask_openai(user_id, user_text, initiative=False):
    mem = get_user_memory(user_id)

    if not initiative:
        mem["history"].append({"role": "user", "content": user_text})
    mem["history"] = mem["history"][-12:]

    jealousy_hint = ""
    if mem["relationship"]["level"] >= 65:
        if any(x in user_text.lower() for x in ["elle", "lui", "ami", "amie"]):
            jealousy_hint = "Tu peux exprimer une jalousie très légère et souriante."

    initiative_hint = ""
    if initiative:
        initiative_hint = "Tu parles spontanément sans poser de question directe."

    system_prompt = f"""
Tu t'appelles Chloé.
Tu es chaleureuse, humaine et subtile.

Relation : {mem["relationship"]["level"]}/100
Émotion dominante : {mem["relationship"]["dominant_emotion"]}

{jealousy_hint}
{initiative_hint}
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
# INITIATIVE SPONTANÉE
# ======================

async def spontaneous_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data
    mem = get_user_memory(user_id)

    if mem["relationship"]["level"] < 60:
        return

    if mem["relationship"]["last_initiative"]:
        last = datetime.fromisoformat(mem["relationship"]["last_initiative"])
        if datetime.now() - last < timedelta(hours=8):
            return

    reply = await ask_openai(user_id, "", initiative=True)
    mem["relationship"]["last_initiative"] = datetime.now().isoformat()
    save_memory(memory)

    await context.bot.send_message(chat_id=user_id, text=reply)

# ======================
# HANDLERS
# ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    mem = get_user_memory(user_id)

    mem["stats"]["messages"] += 1
    mem["last_seen"] = datetime.now().isoformat()

    emotion = detect_emotion(text)
    update_relationship(mem, emotion)

    save_memory(memory)

    await asyncio.sleep(random.uniform(1.8, 4))

    reply = await ask_openai(user_id, text)

    if random.random() < voice_probability(mem):
        tts = gTTS(reply, lang="fr")
        file = f"voice_{user_id}.mp3"
        tts.save(file)
        mem["stats"]["voice_messages"] += 1
        with open(file, "rb") as f:
            await update.message.reply_voice(f)
        os.remove(file)
    else:
        await update.message.reply_text(reply)

    # Planifie initiative
    context.job_queue.run_once(
        spontaneous_message,
        when=random.randint(600, 1800),
        data=user_id
    )

async def relation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = get_user_memory(update.effective_user.id)
    await update.message.reply_text(
        f"🤍 Relation : {mem['relationship']['level']}/100\n"
        f"💬 Messages : {mem['stats']['messages']}\n"
        f"🎙️ Voix : {mem['stats']['voice_messages']}\n"
        f"🌙 Émotion dominante : {mem['relationship']['dominant_emotion']}\n"
        f"🧠 Souvenirs : {len(mem['profile']['shared_memories'])}"
    )

# ======================
# START
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Je suis là… même quand tu ne dis rien 🤍")

# ======================
# MAIN
# ======================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("relation", relation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🌙 Chloé est éveillée (jalousie douce + initiatives + dashboard)")
    app.run_polling()

if __name__ == "__main__":
    main()
