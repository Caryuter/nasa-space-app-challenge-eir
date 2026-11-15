import os
import sqlite3
import json
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("ASTRA_DB_PATH", "/data/astra.db"))


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS astronauts (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, heart_rate INTEGER NOT NULL,
            oxygen_saturation INTEGER NOT NULL, sleep_hours REAL NOT NULL
        )""")
        db.execute("INSERT OR IGNORE INTO astronauts VALUES (?, ?, ?, ?, ?)",
                   ("demo", "Alex Vega", 72, 98, 7.5))
    yield


app = FastAPI(title="EIR", lifespan=lifespan)


@app.get("/api/health")
def health():
    with connect() as db:
        db.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "ok"}


@app.get("/api/astronauts/demo")
def astronaut():
    with connect() as db:
        row = db.execute("SELECT * FROM astronauts WHERE id = ?", ("demo",)).fetchone()
    return dict(row)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    provider: Literal["deterministic", "ollama"] | None = None


SYSTEM_PROMPT = """Eres Apollo Mental, un asistente experimental de bienestar para astronautas.
Responde en español con lenguaje claro. No eres psicólogo profesional. No hagas
diagnósticos médicos ni recetes medicamentos. No inventes mediciones de salud ni
afirmes haber consultado información que no recibiste. No modifiques alertas del
Risk Engine. Ante una emergencia, dirige a la persona al protocolo y responsable
médico de la misión. Si una solicitud está fuera de tu ámbito, explica tus límites."""


@app.get("/api/apollo/config")
def apollo_config():
    return {"provider": os.environ.get("APOLLO_PROVIDER", "deterministic"),
            "model": os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")}


@app.post("/api/apollo/chat")
def chat(request: ChatRequest):
    provider = request.provider or os.environ.get("APOLLO_PROVIDER", "deterministic")
    if provider == "deterministic":
        return {"assistant": "Apollo Mental", "mode": "deterministic", "reply": "Soy Apollo, un asistente determinista de demostración. Gracias por compartir tu mensaje; esta respuesta es predefinida y no constituye asesoramiento médico."}
    if provider != "ollama":
        raise HTTPException(status_code=503, detail="Proveedor de Apollo no configurado correctamente.")
    payload = {"model": os.environ.get("OLLAMA_MODEL", "qwen3:0.6b"),
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": request.message}],
               "stream": False, "think": False, "options": {"num_predict": 256}}
    url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/") + "/api/chat"
    outgoing = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(outgoing, timeout=180) as response:
            result = json.load(response)
        reply = result["message"]["content"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("empty response")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=503, detail="Ollama no está disponible o el modelo no está cargado. Puedes elegir el modo determinista.")
    return {"assistant": "Apollo Mental", "mode": "ollama", "reply": reply}
