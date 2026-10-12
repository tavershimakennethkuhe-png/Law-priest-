from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import csv
import re
import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "cases.db"
CSV_PATH = APP_DIR / "illustrative_cases.csv"

app = FastAPI(title="The Law Priest Legal Analytics", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_name TEXT NOT NULL,
                area_of_law TEXT NOT NULL,
                outcome TEXT NOT NULL,
                sentence TEXT NOT NULL,
                notes TEXT NOT NULL
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        if count == 0 and CSV_PATH.exists():
            with CSV_PATH.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        "INSERT INTO cases (case_name, area_of_law, outcome, sentence, notes) VALUES (?, ?, ?, ?, ?)",
                        (row["case_name"], row["area_of_law"], row["outcome"], row["sentence"], row["notes"])
                    )


@app.on_event("startup")
def startup():
    init_db()


class AnalyzeRequest(BaseModel):
    text: str


@app.get("/", response_class=HTMLResponse)
def home():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/summary")
def summary():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT area_of_law, outcome, sentence FROM cases").fetchall()
    outcomes, areas = {}, {}
    for area, outcome, _sentence in rows:
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        areas[area] = areas.get(area, 0) + 1
    return {
        "total_cases": len(rows), "outcomes": outcomes, "areas": areas,
        "notice": "Illustrative sample data only; not real court statistics."
    }


@app.get("/api/cases")
def cases():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    text = request.text.strip()
    if not text:
        return {"keywords": [], "summary": "Enter legal text to analyze.", "disclaimer": "Educational tool only."}
    terms = [
        "burden of proof", "fair hearing", "negligence", "contract",
        "mens rea", "actus reus", "sentencing", "appeal",
        "fundamental rights", "jurisdiction", "evidence", "damages"
    ]
    lower = text.lower()
    found = [term for term in terms if term in lower]
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    return {
        "keywords": found, "word_count": word_count,
        "summary": f"Found {len(found)} tracked legal keyword(s) in {word_count} words.",
        "disclaimer": "Keyword matching only; this is not legal advice or validated legal analysis."
    }


@app.post("/api/predict")
def predict(request: AnalyzeRequest):
    text = request.text.lower()
    if not text.strip():
        return {"outcome": "Insufficient text", "confidence": "Not calculated", "reason": "Enter a short case summary."}
    claim_terms = ["breach", "agreement", "contract", "damages", "evidence"]
    defence_terms = ["no evidence", "dismiss", "jurisdiction", "limitation", "reasonable doubt"]
    claim_score = sum(term in text for term in claim_terms)
    defence_score = sum(term in text for term in defence_terms)
    if claim_score > defence_score:
        outcome, reason = "Claim-favouring indicators", "The text contains more predefined claim-related keywords."
    elif defence_score > claim_score:
        outcome, reason = "Defence-favouring indicators", "The text contains more predefined defence-related keywords."
    else:
        outcome, reason = "Inconclusive", "The simple keyword rules do not indicate a clear direction."
    return {
        "outcome": outcome, "confidence": "Not calculated", "reason": reason,
        "disclaimer": "Rule-based demonstration only. Not a trained model, legal opinion, or prediction of an actual court decision."
    }
