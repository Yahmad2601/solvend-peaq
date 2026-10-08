#!/usr/bin/env python3
"""The machine's screen: a QR while an invoice awaits payment, and the machine's
economic identity the rest of the time.

Solana Pay is a point-of-sale spec and QR is its primary transport. A `solana:`
URI pasted into a chat is a deep link, not a URL — Telegram will not linkify it,
and neither Solflare nor Phantom offers a reliable "paste a payment URI" flow.
So the customer scans the machine, exactly as they would at any card terminal.
The chat channel carries the conversation and the dispense code; it is not the
payment rail.

Between sales the screen shows who the machine is on peaq: its DID, the revenue
it has reported from real sales, and the Machine Credit Rating that revenue has
earned. The same card, with recent events, is always at /machine, and the raw
numbers at /machine.json.

Run it on the Pi with a monitor attached and put a browser on it fullscreen:

    set -a; . /etc/solvend/env; set +a
    python3 tools/machine_display.py                 # then open localhost:8080

Read-only and keyless. It opens the ledger in SQLite read-only mode, mints
nothing, settles nothing, signs nothing. The credit rating comes from peaq's
public MCR API (GET /mcr/{did}, no API key), not from the machine's wallet. The
URI is rebuilt from the ledger row plus the same environment the invoice tool
used, so the amount and mint cannot drift from what was actually charged.

    pip install qrcode
"""
import base64
import html
import io
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote

DB = os.environ.get("SOLVEND_DB", "/var/lib/solvend/solvend.db")
RECIPIENT = os.environ.get("SOLVEND_RECIPIENT", "MERCHANT_WALLET_PUBKEY_HERE")
MINT = os.environ.get("SOLVEND_USDC_MINT",
                      "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
PORT = int(os.environ.get("SOLVEND_DISPLAY_PORT", "8080"))
USDC_DECIMALS = 6

MACHINE_ID = os.environ.get("PEAQ_MACHINE_ID", "")
MACHINE_DID = f"did:peaq:{MACHINE_ID}" if MACHINE_ID else ""
# GET /mcr/{did}, no API key. Verified from docs.peaq.xyz get-mcr, 8 Oct 2026.
MCR_API_URL = os.environ.get("PEAQOS_MCR_API_URL", "https://mcr.peaq.xyz")
MCR_CACHE_SECS = 60         # the screen refreshes every 5 s; the MCR does not need to
# peaq mainnet explorer is peaq.subscan.io (docs: Block Explorers). The
# /tx/<0x hash> path was verified on the activation tx, 8 Oct 2026.
EXPLORER = os.environ.get("PEAQ_EXPLORER_URL", "https://peaq.subscan.io")
MIN_REVENUE_CENTS = 1000    # mirrors peaq/machine.py: a day below $10 is held
# Mirrors peaq/machine.py: sales before the mainnet switch were devnet
# rehearsals in faucet USDC and are not revenue. 0 = count everything.
REPORT_FROM = int(os.environ.get("PEAQ_REPORT_FROM", "0") or 0)


# --------------------------------------------------------------------------
# Ledger reads
# --------------------------------------------------------------------------
def _ro():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)


def current_invoice():
    """Newest AWAITING_PAYMENT row, or None. Read-only; never writes."""
    try:
        conn = _ro()
        try:
            row = conn.execute(
                "SELECT invoice_id, item, amount_base, reference FROM invoices"
                " WHERE status='AWAITING_PAYMENT' ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row:
        return None
    invoice_id, item, amount_base, reference = row
    amount = f"{amount_base / 10 ** USDC_DECIMALS:.6f}".rstrip("0").rstrip(".")
    uri = (f"solana:{RECIPIENT}?amount={amount}&spl-token={MINT}"
           f"&reference={reference}&label={quote('SolVend')}"
           f"&message={quote(f'Invoice {invoice_id} - {item}')}")
    return {"invoice_id": invoice_id, "item": item, "amount": amount, "uri": uri}


def ledger_snapshot(now=None):
    """Sales from the ledger and what has been reported to peaq. Read-only.

    peaq_events may not exist yet (machine.py creates it on first sync), so its
    absence reads as "nothing reported", not as an error.
    """
    now = int(now or time.time())
    snap = {"sales": 0, "revenue_cents": 0, "sales_7d": 0, "revenue_7d_cents": 0,
            "reported_sales": 0, "reported_cents": 0, "events": []}
    try:
        conn = _ro()
    except sqlite3.Error as e:
        snap["error"] = f"ledger unavailable: {e}"
        return snap
    try:
        # amount_base is micro-USDC; cents = base // 10_000, matching to_cents
        # for every catalogue price.
        week = max(now - 7 * 86400, REPORT_FROM)
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_base),0),"
            " COALESCE(SUM(claimed_at >= ?),0),"
            " COALESCE(SUM(CASE WHEN claimed_at >= ? THEN amount_base END),0)"
            " FROM invoices WHERE status='CLAIMED' AND claimed_at >= ?",
            (week, week, REPORT_FROM)).fetchone()
        snap["sales"], snap["sales_7d"] = row[0], row[2]
        snap["revenue_cents"] = row[1] // 10_000
        snap["revenue_7d_cents"] = row[3] // 10_000
        has_events = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='peaq_events'"
        ).fetchone()
        if has_events:
            r = conn.execute("SELECT COUNT(*), COALESCE(SUM(cents),0)"
                             " FROM peaq_events").fetchone()
            snap["reported_sales"], snap["reported_cents"] = r
            snap["events"] = [
                {"tx_hash": tx, "day": day, "cents": cents, "sales": n, "at": at}
                for tx, day, cents, n, at in conn.execute(
                    "SELECT tx_hash, utc_day, SUM(cents), COUNT(*), MAX(submitted_at)"
                    " FROM peaq_events GROUP BY tx_hash"
                    " ORDER BY MAX(submitted_at) DESC LIMIT 5")]
    except sqlite3.Error as e:
        snap["error"] = f"ledger read failed: {e}"
    finally:
        conn.close()
    snap["pending_cents"] = snap["revenue_cents"] - snap["reported_cents"]
    return snap


# --------------------------------------------------------------------------
# Credit rating — public MCR API, cached
# --------------------------------------------------------------------------
_mcr_cache = {"at": 0.0, "data": None}


def mcr(fetch=None):
    """GET {MCR_API_URL}/mcr/{did}, cached. Failures are cached too, so a dead
    MCR costs one request a minute, not one per screen refresh."""
    if not MACHINE_DID:
        return {"unavailable": "machine not activated yet (PEAQ_MACHINE_ID unset)"}
    if _mcr_cache["data"] is not None and time.time() - _mcr_cache["at"] < MCR_CACHE_SECS:
        return _mcr_cache["data"]
    try:
        if fetch:
            data = fetch(MACHINE_DID)
        else:
            url = f"{MCR_API_URL.rstrip('/')}/mcr/{MACHINE_DID}"
            # Python's default "Python-urllib" User-Agent gets 403 from
            # mcr.peaq.xyz while curl gets through (observed 8 Oct 2026).
            req = urllib.request.Request(url, headers={
                "User-Agent": "SolVend-display/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.load(resp)
    except urllib.error.HTTPError as e:
        # Before activation the API answers 404 {"detail":"Machine not
        # registered"} (observed 8 Oct 2026). Show its words, not the status.
        try:
            detail = json.load(e).get("detail") or e.reason
        except Exception:                           # noqa: BLE001
            detail = e.reason
        data = {"unavailable": f"{str(detail)[:120]} (HTTP {e.code})"}
    except Exception as e:                          # noqa: BLE001
        data = {"unavailable": f"{type(e).__name__}: {e}"[:160]}
    _mcr_cache.update(at=time.time(), data=data)
    return data


def snapshot():
    return {"machine_id": MACHINE_ID or None, "did": MACHINE_DID or None,
            "ledger": ledger_snapshot(), "mcr": mcr(),
            "threshold_cents": MIN_REVENUE_CENTS}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def qr_data_uri(uri: str) -> str:
    import qrcode
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(uri)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image().save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def usd(cents):
    return f"${cents / 100:,.2f}"


def short(s, head=10, tail=6):
    s = str(s)
    return s if len(s) <= head + tail + 1 else f"{s[:head]}…{s[-tail:]}"


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>SolVend</title><style>
 body{{background:#111;color:#eee;font-family:system-ui,sans-serif;margin:0;
      min-height:100vh;display:flex;flex-direction:column;align-items:center;
      justify-content:center;text-align:center;padding:0 16px;box-sizing:border-box}}
 img{{width:min(60vh,80vw);image-rendering:pixelated;background:#fff;padding:16px;
      border-radius:12px}}
 a{{color:#8ab4f8}}
 .item{{font-size:6vh;font-weight:600;margin:3vh 0 0}}
 .amt{{font-size:4vh;color:#7fd67f;margin:.5vh 0 3vh}}
 .inv{{font-size:2vh;color:#666;margin-top:2vh;letter-spacing:.1em}}
 .name{{font-size:5vh;font-weight:700;margin:0}}
 .did{{font-family:ui-monospace,monospace;font-size:1.8vh;color:#888;
      margin:.5vh 0 3vh;word-break:break-all}}
 .grade{{font-size:12vh;font-weight:800;line-height:1;margin:0;color:#7fd67f}}
 .grade.pending{{color:#aaa;font-size:7vh}}
 .score{{font-size:2.4vh;color:#aaa;margin:.5vh 0 3vh}}
 .stats{{display:flex;gap:4vw;justify-content:center;flex-wrap:wrap}}
 .stat b{{display:block;font-size:4.5vh}}
 .stat span{{font-size:1.9vh;color:#888;text-transform:uppercase;letter-spacing:.08em}}
 table{{margin:4vh auto 0;border-collapse:collapse;font-size:1.8vh;max-width:100%}}
 td,th{{padding:.6vh 1.2vw;border-bottom:1px solid #333;text-align:left}}
 th{{color:#888;font-weight:500}}
 .note{{font-size:1.8vh;color:#666;margin-top:3vh;max-width:70ch}}
</style></head><body>{body}</body></html>"""


def identity_card(snap, detail=False):
    led, m = snap["ledger"], snap["mcr"]
    if "mcr" in m:
        grade_cls = "grade pending" if m["mcr"] in ("Provisioned", "NR") else "grade"
        grade = (f'<p class="{grade_cls}">{html.escape(str(m["mcr"]))}</p>'
                 f'<p class="score">Machine Credit Rating · score '
                 f'{html.escape(str(m.get("mcr_score", 0)))}/100'
                 + (f' · trend {html.escape(str(m["revenue_trend"]))}'
                    if m.get("revenue_trend") else "") + '</p>')
    else:
        grade = (f'<p class="grade pending">—</p><p class="score">credit rating '
                 f'{html.escape(str(m.get("unavailable", "unavailable")))}</p>')
    did = (html.escape(snap["did"]) if detail else html.escape(short(snap["did"], 18, 8))) \
        if snap["did"] else "not activated yet"
    body = (f'<p class="name">SolVend</p><p class="did">{did}</p>{grade}'
            f'<div class="stats">'
            f'<div class="stat"><b>{led["sales"]}</b><span>cans sold</span></div>'
            f'<div class="stat"><b>{usd(led["revenue_cents"])}</b><span>revenue</span></div>'
            f'<div class="stat"><b>{usd(led["reported_cents"])}</b><span>reported to peaq</span></div>'
            f'<div class="stat"><b>{usd(led["revenue_7d_cents"])}</b><span>last 7 days</span></div>'
            f'</div>')
    if not detail:
        return body + '<div class="inv">message the shop bot to order</div>'
    if led["events"]:
        rows = "".join(
            f'<tr><td>{html.escape(e["day"])}</td><td>{e["sales"]}</td>'
            f'<td>{usd(e["cents"])}</td><td><a href="{EXPLORER}/tx/{html.escape(e["tx_hash"])}">'
            f'{html.escape(short(e["tx_hash"]))}</a></td></tr>' for e in led["events"])
        body += ('<table><tr><th>UTC day</th><th>sales</th><th>revenue</th>'
                 f'<th>peaq event</th></tr>{rows}</table>')
    since = (time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(REPORT_FROM))
             if REPORT_FROM else None)
    body += (f'<p class="note">Every can counted here was paid in mainnet USDC on '
             f'Solana{f", counted from {since}" if since else ""}. Sales are '
             f'reported to peaq as one revenue event per UTC day once the day clears '
             f'{usd(snap["threshold_cents"])}, the minimum the credit rating counts. '
             f'{usd(max(led["pending_cents"], 0))} is waiting to be reported.</p>')
    if led.get("error"):
        body += f'<p class="note">{html.escape(led["error"])}</p>'
    return body


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/machine.json":
            self._send(json.dumps(snapshot(), indent=2).encode(),
                       "application/json")
            return
        if path == "/machine":
            body, refresh = identity_card(snapshot(), detail=True), 30
        else:
            inv = current_invoice()
            if inv:
                body = (f'<img src="{qr_data_uri(inv["uri"])}" alt="Solana Pay QR">'
                        f'<div class="item">{html.escape(inv["item"])}</div>'
                        f'<div class="amt">{inv["amount"]} USDC</div>'
                        f'<div class="inv">{html.escape(inv["invoice_id"])} &middot; scan to pay</div>')
            else:
                body = identity_card(snapshot())
            refresh = 5
        self._send(PAGE.format(body=body, refresh=refresh).encode(),
                   "text/html; charset=utf-8")

    def log_message(self, *args):        # keep the machine's console quiet
        pass


if __name__ == "__main__":
    try:
        import qrcode  # noqa: F401
    except ImportError:
        sys.exit("pip install qrcode")
    print(f"SolVend display on http://0.0.0.0:{PORT}  (ledger: {DB})")
    print(f"  /          QR while an invoice awaits payment, identity card otherwise")
    print(f"  /machine   identity, revenue, credit rating, recent peaq events")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
