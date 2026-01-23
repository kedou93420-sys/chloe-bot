import json
import os
import random
import asyncio
from gtts import gTTS
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)
from openai import OpenAI

# ======================
# CONFIG
# ======================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"
VOICE_FILE = "temp_voice.mp3"

# ======================
# MÉMOIRE LONGUE DURÉE
# ======================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"users": {}}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()

# ======================
# DÉTECTION DES MODES
# ======================

def detect_mode(text: str) -> str:
    t = text.lower()

    if any(x in t for x in ["triste", "fatigué", "marre", "ça va pas", "déprimé"]):
        return "confidence"

    if any(x in t for x in ["argent", "business", "projet", "objectif", "revenu"]):
        return "business"

    if any(x in t for x in ["lol", "mdr", "haha", "😂", "😄"]):
        return "chill"

    return "neutre"

# ======================
# PERSONNALITÉ ÉVOLUTIVE
# ======================

def personality_prompt(user_data, mode):
    level = user_data.get("personality_level", 1)

    prompt = "Tu es Chloé, une sœur proche, humaine et naturelle."

    if level >= 5:
        prompt += " Tu es à l’aise et familière."
    if level >= 10:
        prompt += " Tu peux être directe et taquine."

    if mode == "confidence":
        prompt += " Tu es douce, rassurante et protectrice."
    elif mode == "business":
        prompt += " Tu es motivante, structurée et ambitieuse."
    elif mode == "chill":
        prompt += " Tu es drôle et détendue."

    prompt += " Tu ne dis pas bonjour à chaque message."

    return prompt

# ======================
# EXTRACTION DE SOUVENIRS
# ======================

def extract_fact(text):
    triggers = ["je veux", "mon projet", "je travaille", "mon objectif"]
    for t in triggers:
        if t in text.lower():
            return text
    return None

# ======================
# TEXT TO SPEECH
# ======================

def generate_voice(text, mode):
    slow = True if mode == "confidence" else False
    tts = gTTS(text=text, lang="fr", slow=slow)
    tts.save(VOICE_FILE)

# ======================
# COMMANDES
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey 🙂\nMoi c’est Chloé.\nJe suis là, parle-moi."
    )

# ======================
# HANDLER PRINCIPAL
# ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    text = update.message.text

    # Init utilisateur
    if user_id not in memory["users"]:
        memory["users"][user_id] = {
            "facts": [],
            "summary": "",
            "message_count": 0,
            "personality_level": 1
        }

    user_data = memory["users"][user_id]

    # 🔧 Sécurité rétrocompatibilité
    if "personality_level" not in user_data:
        user_data["personality_level"] = 1
    if "message_count" not in user_data:
        user_data["message_count"] = 0
    if "facts" not in user_data:
        user_data["facts"] = []

    user_data["message_count"] += 1
    user_data["personality_level"] += 1

    # Sauvegarde faits importants
    fact = extract_fact(text)
    if fact:
        user_data["facts"].append(fact)

    save_memory(memory)

    # 🧠 TEMPS DE RÉFLEXION HUMAIN (ICI C’EST CORRECT)
    await asyncio.sleep(random.uniform(1, 3))

    mode = detect_mode(text)
    system_prompt = personality_prompt(user_data, mode)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = "Hmm… attends une seconde, j’ai buggué là 😅"

    # 🎙️ TEXTE OU VOCAL (CHOIX CHLOÉ)
    voice_chance = {
        "confidence": 0.6,
        "chill": 0.5,
        "neutre": 0.3,
        "business": 0.1
    }

    if random.random() < voice_chance.get(mode, 0.3):
        generate_voice(reply, mode)
        with open(VOICE_FILE, "rb") as audio:
            await update.message.reply_voice(audio)
        os.remove(VOICE_FILE)
    else:
        await update.message.reply_text(reply)

# ======================
# HANDLER D’ERREURS
# ======================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("⚠️ Erreur capturée :", context.error)

# ======================
# MAIN
# ======================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("🤍 Chloé est en ligne (stable, étape 5)")
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    main()
