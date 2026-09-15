import os, sqlite3, json
from datetime import datetime, timezone
from urllib.request import Request as URLRequest, urlopen
from urllib.error import HTTPError, URLError
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DB_PATH", "signals.db")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

# WhatsApp Cloud API / Meta Graph API
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_TO = os.getenv("WHATSAPP_TO", "")
WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "nkral1_signal_alert")
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "tr")

app = FastAPI(title="NKRAL1 WhatsApp Signal Notifier")


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT, symbol TEXT, action TEXT, price TEXT,
        timeframe TEXT, signal_time TEXT, received_at TEXT,
        whatsapp_sent INTEGER DEFAULT 0,
        whatsapp_error TEXT DEFAULT ''
    )""")
    # Upgrade older DBs created by the mail version.
    cols = {r[1] for r in c.execute("PRAGMA table_info(signals)").fetchall()}
    if "whatsapp_sent" not in cols:
        c.execute("ALTER TABLE signals ADD COLUMN whatsapp_sent INTEGER DEFAULT 0")
    if "whatsapp_error" not in cols:
        c.execute("ALTER TABLE signals ADD COLUMN whatsapp_error TEXT DEFAULT ''")

    c.execute("""CREATE TABLE IF NOT EXISTS states(
        strategy TEXT, symbol TEXT, timeframe TEXT,
        last_action TEXT, PRIMARY KEY(strategy,symbol,timeframe))""")
    c.commit(); c.close()


def whatsapp_configured():
    return bool(
        WHATSAPP_ENABLED
        and WHATSAPP_PHONE_NUMBER_ID
        and WHATSAPP_ACCESS_TOKEN
        and WHATSAPP_TO
        and WHATSAPP_TEMPLATE_NAME
    )


def send_whatsapp(s):
    """Send a WhatsApp Business template message via Meta Cloud API.

    Template body variables are expected in this order:
    {{1}} = action, {{2}} = symbol, {{3}} = timeframe,
    {{4}} = price, {{5}} = signal time.
    """
    if not whatsapp_configured():
        return False, "WhatsApp yapılandırılmamış"

    url = (
        f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_TO,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE_NAME,
            "language": {"code": WHATSAPP_TEMPLATE_LANGUAGE},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": s["action"]},
                    {"type": "text", "text": s["symbol"]},
                    {"type": "text", "text": s["timeframe"]},
                    {"type": "text", "text": s["price"]},
                    {"type": "text", "text": s["signal_time"]},
                ],
            }],
        },
    }
    req = URLRequest(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            if 200 <= response.status < 300:
                return True, ""
            return False, body[:1000]
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code}: {body[:1000]}"
    except URLError as e:
        return False, f"Bağlantı hatası: {e}"
    except Exception as e:
        return False, f"Hata: {e}"


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    c = db()
    rows = c.execute("""SELECT strategy,symbol,action,price,timeframe,signal_time,
                        received_at,whatsapp_sent,whatsapp_error
                        FROM signals ORDER BY id DESC LIMIT 200""").fetchall()
    c.close()
    trs = "".join(
        f"<tr><td>{r['symbol']}</td><td><b>{r['action']}</b></td><td>{r['price']}</td>"
        f"<td>{r['timeframe']}</td><td>{r['signal_time']}</td>"
        f"<td>{'Gönderildi' if r['whatsapp_sent'] else ('Hata' if r['whatsapp_error'] else 'Gönderilmedi')}</td></tr>"
        for r in rows)
    status = "Aktif" if whatsapp_configured() else "Yapılandırılmadı"
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <meta http-equiv="refresh" content="30">
    <title>NKRAL1 Dashboard</title>
    <style>body{{font-family:Arial;margin:30px;background:#f5f5f5}}table{{width:100%;background:white;border-collapse:collapse}}
    th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#222;color:white}}
    .box{{background:white;padding:15px;margin-bottom:20px;border-radius:8px}}</style></head>
    <body><h1>NKRAL1 Sinyal Dashboard</h1>
    <div class="box">Takip: <b>4 Saatlik + Günlük</b> | WhatsApp: <b>{status}</b> | Son 200 sinyal</div>
    <table><tr><th>Sembol</th><th>Sinyal</th><th>Fiyat</th><th>Periyot</th><th>Sinyal zamanı</th><th>WhatsApp</th></tr>{trs}</table>
    </body></html>"""
@app.get("/test")
async def test_webhook(request: Request):
    token = request.query_params.get("secret", "")
    if token != WEBHOOK_SECRET:
        raise HTTPException(401, "Invalid secret")

    return {
        "ok": True,
        "message": "NKRAL1 webhook bağlantısı çalışıyor"
    }

@app.post("/webhook")
async def webhook(request: Request):
    token = request.query_params.get("secret", "")
    if token != WEBHOOK_SECRET:
        raise HTTPException(401, "Invalid secret")
   try:
    body = await request.body()
    print("TRADINGVIEW_RAW:", body.decode("utf-8", errors="replace"))
    data = json.loads(body.decode("utf-8"))
except Exception as e:
    print("JSON_ERROR:", str(e))
    raise HTTPException(400, "Geçersiz JSON")
    except Exception:
        raise HTTPException(400, "JSON bekleniyor")

    required = ["strategy", "action", "symbol", "price", "timeframe"]
    if any(k not in data for k in required):
        raise HTTPException(400, f"Eksik alan: {required}")

    action = str(data["action"]).upper()
    if action not in ("AL", "SAT"):
        raise HTTPException(400, "action AL veya SAT olmalı")

    s = {
        "strategy": str(data["strategy"]),
        "action": action,
        "symbol": str(data["symbol"]),
        "price": str(data["price"]),
        "timeframe": str(data["timeframe"]),
        "signal_time": str(data.get("time", datetime.now(timezone.utc).isoformat()))
    }
    now = datetime.now(timezone.utc).isoformat()

    c = db()
    old = c.execute("""SELECT last_action FROM states
                      WHERE strategy=? AND symbol=? AND timeframe=?""",
                    (s["strategy"], s["symbol"], s["timeframe"])) .fetchone()
    duplicate = old and old["last_action"] == action

    c.execute("""INSERT INTO signals(strategy,symbol,action,price,timeframe,signal_time,received_at,whatsapp_sent,whatsapp_error)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (s["strategy"], s["symbol"], s["action"], s["price"], s["timeframe"], s["signal_time"], now, 0, ""))

    whatsapp_sent = False
    whatsapp_error = ""
    if not duplicate:
        whatsapp_sent, whatsapp_error = send_whatsapp(s)
        c.execute("""UPDATE signals SET whatsapp_sent=?, whatsapp_error=? WHERE id=last_insert_rowid()""",
                  (1 if whatsapp_sent else 0, whatsapp_error))
        c.execute("""INSERT INTO states(strategy,symbol,timeframe,last_action)
                     VALUES(?,?,?,?) ON CONFLICT(strategy,symbol,timeframe)
                     DO UPDATE SET last_action=excluded.last_action""",
                  (s["strategy"], s["symbol"], s["timeframe"], action))
    c.commit(); c.close()
    return {
        "ok": True,
        "whatsapp_sent": whatsapp_sent,
        "duplicate_suppressed": bool(duplicate),
        "whatsapp_error": whatsapp_error,
    }
