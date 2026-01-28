from flask import Flask, render_template
import json
from datetime import datetime

app = Flask(__name__)

MEMORY_FILE = "memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

@app.route("/")
def index():
    data = load_memory()

    if not data:
        return "Aucune donnée mémoire trouvée"

    user_id, user = list(data.items())[0]

    last_seen = user.get("last_seen")
    if last_seen:
        last_seen = datetime.fromisoformat(last_seen).strftime("%d/%m/%Y %H:%M")

    return render_template(
        "index.html",
        user_id=user_id,
        profile=user.get("profile", {}),
        relationship=user.get("relationship", {}),
        stats=user.get("stats", {}),
        last_seen=last_seen
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
