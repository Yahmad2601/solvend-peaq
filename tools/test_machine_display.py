#!/usr/bin/env python3
"""Host-run tests for the machine display. No network: the MCR fetch is faked.

Run:  python3 tools/test_machine_display.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import urllib.request

TMP = tempfile.mkdtemp()
os.environ["SOLVEND_DB"] = os.path.join(TMP, "test.db")
os.environ["PEAQ_MACHINE_ID"] = "8600820691859294852796023821329786994502637838982221572620760063908348418155"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "solvend"))
sys.path.insert(0, os.path.join(HERE, "..", "peaq"))

import solvend          # noqa: E402  — real invoices schema
import machine          # noqa: E402  — real peaq_events schema
import machine_display as md   # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")


NOW = 1_791_000_000
with solvend.db() as c:
    c.executescript(solvend.SCHEMA)


def sale(n, item, claimed_at, status="CLAIMED"):
    price = solvend.ITEMS[item]["price_base"]
    with sqlite3.connect(md.DB) as c:
        c.execute(
            "INSERT INTO invoices (invoice_id, reference, item, amount_base, channel,"
            " handle, status, signature, created_at, claimed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"INV-{n}", f"ref{n}", item, price, "tg", "h", status, f"SIG{n}",
             claimed_at - 60, claimed_at))


print("\nledger — before peaq_events exists")
sale(1, "cola", NOW - 3600)
sale(2, "energy", NOW - 10 * 86400)                 # outside the 7-day window
sale(3, "water", NOW - 60, status="PAID_UNCLAIMED")  # not revenue
snap = md.ledger_snapshot(now=NOW)
check("missing peaq_events reads as nothing reported",
      "error" not in snap and snap["reported_cents"] == 0 and snap["events"] == [])
check("only CLAIMED sales count", snap["sales"] == 2)
check("revenue in cents", snap["revenue_cents"] == 400)
check("7-day window", snap["sales_7d"] == 1 and snap["revenue_7d_cents"] == 150)
check("pending = sold - reported", snap["pending_cents"] == 400)

print("\nledger — after a reported event")
with sqlite3.connect(md.DB) as c:
    c.executescript(machine.SCHEMA)
    c.executemany(
        "INSERT INTO peaq_events VALUES (?,?,?,?,?,?)",
        [("INV-1", "m", "2026-10-08", 150, "0x" + "ab" * 32, NOW),
         ("INV-2", "m", "2026-10-08", 250, "0x" + "ab" * 32, NOW)])
snap = md.ledger_snapshot(now=NOW)
check("reported totals", snap["reported_sales"] == 2 and snap["reported_cents"] == 400)
check("one event row per tx, sales grouped",
      len(snap["events"]) == 1 and snap["events"][0]["sales"] == 2
      and snap["events"][0]["cents"] == 400)
check("nothing pending", snap["pending_cents"] == 0)

print("\ncredit rating — public MCR, cached")
calls = []


def fake_fetch(did):
    calls.append(did)
    return {"did": did, "mcr": "Provisioned", "mcr_score": 0,
            "revenue_trend": "insufficient", "total_revenue": 0}


md._mcr_cache.update(at=0.0, data=None)
m = md.mcr(fetch=fake_fetch)
check("asks for did:peaq:<decimal id>", calls == ["did:peaq:" + os.environ["PEAQ_MACHINE_ID"]])
md.mcr(fetch=fake_fetch)
check("second read within a minute is cached", len(calls) == 1)
md._mcr_cache.update(at=0.0, data=None)
m = md.mcr(fetch=lambda did: (_ for _ in ()).throw(TimeoutError("slow")))
check("MCR failure degrades, never raises", "unavailable" in m)

print("\nrendering")
md._mcr_cache.update(at=0.0, data=None)
md.mcr(fetch=fake_fetch)
page = md.identity_card(md.snapshot(), detail=True)
check("grade shown", "Provisioned" in page and "score 0/100" in page)
check("full DID on /machine", os.environ["PEAQ_MACHINE_ID"] in page)
check("event links to the explorer", f'{md.EXPLORER}/tx/0x{"ab" * 32}' in page)
idle = md.identity_card(md.snapshot())
check("idle card shortens the DID", os.environ["PEAQ_MACHINE_ID"] not in idle and "…" in idle)
check("idle card has no events table", "<table" not in idle)

print("\nserver — real HTTP round trip")
srv = md.HTTPServer(("127.0.0.1", 0), md.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
root = urllib.request.urlopen(base + "/").read().decode()
check("/ shows the identity card when nothing awaits payment", "Machine Credit Rating" in root)
detail = urllib.request.urlopen(base + "/machine").read().decode()
check("/machine renders", "reported to peaq" in detail and "<table" in detail)
data = json.loads(urllib.request.urlopen(base + "/machine.json").read())
check("/machine.json carries ledger and mcr", data["ledger"]["sales"] == 2
      and data["mcr"]["mcr"] == "Provisioned")
with sqlite3.connect(md.DB) as c:
    c.execute("INSERT INTO invoices (invoice_id, reference, item, amount_base, channel,"
              " handle, status, created_at) VALUES ('INV-9','ref9','cola',1500000,"
              "'tg','h','AWAITING_PAYMENT',?)", (NOW,))
root = urllib.request.urlopen(base + "/").read().decode()
check("/ switches to the payment QR while an invoice awaits",
      "scan to pay" in root and "1.5 USDC" in root)
srv.shutdown()

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
