import json
from pathlib import Path

from flask import Flask, jsonify, render_template

app = Flask(__name__)

AREAS_FILE = Path(__file__).parent / "mpa_areas.json"
AREAS = json.loads(AREAS_FILE.read_text(encoding="utf-8"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/areas")
def areas():
    return jsonify(AREAS)