import csv, json, os, re, sqlite3, urllib.error, urllib.request
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
DB = ROOT / "cases.db"
CSV_FILE = ROOT / "illustrative_cases.csv"
app = FastAPI(title="The Law Priest Legal Analytics", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(ROOT)), name="static")

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_name TEXT NOT NULL,
        area_of_law TEXT NOT NULL, outcome TEXT NOT NULL,
        sentence TEXT NOT NULL, notes TEXT NOT NULL)""")
        if conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0 and CSV_FILE.exists():
            with CSV_FILE.open(encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    conn.execute("INSERT INTO cases(case_name,area_of_law,outcome,sentence,notes) VALUES(?,?,?,?,?)",
                                 (r["case_name"], r["area_of_law"], r["outcome"], r["sentence"], r["notes"]))

@app.on_event("startup")
def startup(): init_db()

class TextRequest(BaseModel):
    text: str = Field(max_length=12000)

class AIRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    task: str = Field(default="Analyse the legal issues and arguments", max_length=100)

@app.get("/", response_class=HTMLResponse)
def home(): return (ROOT / "index.html").read_text(encoding="utf-8")

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/api/summary")
def summary():
    with sqlite3.connect(DB) as c: rows = c.execute("SELECT area_of_law,outcome FROM cases").fetchall()
    outcomes, areas = {}, {}
    for area, outcome in rows:
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        areas[area] = areas.get(area, 0) + 1
    return {"total_cases":len(rows), "outcomes":outcomes, "areas":areas,
            "notice":"Illustrative sample data, not real court statistics."}

@app.get("/api/cases")
def cases():
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()]

@app.post("/api/analyze")
def analyze(req: TextRequest):
    text = req.text.strip()
    terms = ["burden of proof","fair hearing","negligence","contract","mens rea","actus reus",
             "sentencing","appeal","fundamental rights","jurisdiction","evidence","damages"]
    found = [t for t in terms if t in text.lower()]
    words = len(re.findall(r"\\b[\\w'-]+\\b", text))
    return {"keywords":found, "word_count":words,
            "summary":f"Found {len(found)} tracked legal keyword(s) in {words} words.",
            "disclaimer":"Keyword matching only; not legal advice."}

@app.post("/api/ai-analyze")
def ai_analyze(req: AIRequest):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "OpenRouter is not configured. Add OPENROUTER_API_KEY in Render Environment.")
    model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
    system = ("You are an educational legal research assistant for a Nigerian law student. "
              "Analyse the supplied text clearly. Identify issues, principles, arguments and missing facts where relevant. "
              "Never invent legislation, case names, citations, quotations or legal rules. State uncertainty and advise "
              "verification from authoritative sources. Do not claim to predict a real court decision. This is educational "
              "information, not legal advice.")
    payload = {"model":model, "messages":[{"role":"system","content":system},
               {"role":"user","content":"Task: "+req.task+"\\n\\nLegal text:\\n"+req.text}],
               "temperature":0.2, "max_tokens":1200}
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(), headers={"Authorization":"Bearer "+key,
        "Content-Type":"application/json","X-OpenRouter-Title":"The Law Priest Legal Analytics"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode())
        answer = result["choices"][0]["message"]["content"]
        return {"answer":answer, "model":result.get("model",model),
                "disclaimer":"AI-generated educational analysis. Verify all legal authorities independently."}
    except urllib.error.HTTPError as e:
        if e.code in (401,403): msg = "OpenRouter rejected the API key. Check OPENROUTER_API_KEY in Render."
        elif e.code == 429: msg = "OpenRouter rate limit reached. Wait and try again."
        else: msg = f"OpenRouter returned HTTP {e.code}. Check model ID and account status."
        raise HTTPException(502,msg) from e
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(502,"Could not reach OpenRouter. Please try again.") from None
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        raise HTTPException(502,"OpenRouter returned an unexpected response.") from None

@app.post("/api/predict")
def predict(req: TextRequest):
    t = req.text.lower()
    claim = sum(x in t for x in ["breach","agreement","contract","damages","evidence"])
    defence = sum(x in t for x in ["no evidence","dismiss","jurisdiction","limitation","reasonable doubt"])
    if claim > defence: outcome, reason = "Claim-favouring indicators","More predefined claim-related keywords were found."
    elif defence > claim: outcome, reason = "Defence-favouring indicators","More predefined defence-related keywords were found."
    else: outcome, reason = "Inconclusive","The simple keyword rules show no clear direction."
    return {"outcome":outcome,"confidence":"Not calculated","reason":reason,
            "disclaimer":"Rule-based demo only, not a trained model or actual court prediction."}
        
