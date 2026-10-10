#!/usr/bin/env python3
"""Host-run tests for peaq revenue reporting. Fake SDK — no network, no PEAQ.

Run:  python3 peaq/test_machine.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import types

TMP = tempfile.mkdtemp()
os.environ["SOLVEND_DB"] = os.path.join(TMP, "test.db")
os.environ["PEAQ_MACHINE_ID"] = "8600820691859294852796023821329786994502637838982221572620760063908348418155"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "solvend"))

# Stand-in for peaq_os_sdk: records every submit_event call. Constant values
# match the installed SDK 0.11.0 (EVENT_TYPE_REVENUE == TRUST_SELF_REPORTED == 0).
SUBMITTED = []
FAIL_NEXT = []


class FakeClient:
    address = "0x" + "11" * 20

    def submit_event(self, **kw):
        if FAIL_NEXT:
            FAIL_NEXT.pop()
            raise RuntimeError("rpc down")
        SUBMITTED.append(kw)
        return ("0x" + f"{len(SUBMITTED):064x}", b"datahash")


sdk = types.ModuleType("peaq_os_sdk")
sdk.EVENT_TYPE_REVENUE = 0
sdk.TRUST_SELF_REPORTED = 0
sys.modules["peaq_os_sdk"] = sdk

import solvend   # noqa: E402  — for the real invoices schema
import machine   # noqa: E402

machine._client_cache = FakeClient()

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")


def reset():
    # Clear rows rather than delete the file: Windows refuses to remove a
    # SQLite file another connection still holds open.
    with solvend.db() as c:
        c.executescript(solvend.SCHEMA)
        c.executescript(machine.SCHEMA)
        c.execute("DELETE FROM invoices")
        c.execute("DELETE FROM peaq_events")
    SUBMITTED.clear()


DAY1 = 1_791_000_000              # a fixed UTC instant
DAY2 = DAY1 + 86_400


def sale(n, item, claimed_at, status="CLAIMED", sig=True):
    price = solvend.ITEMS[item]["price_base"]
    with sqlite3.connect(machine.DB) as c:
        c.execute(
            "INSERT INTO invoices (invoice_id, reference, item, amount_base, channel,"
            " handle, status, signature, created_at, claimed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"INV-{n}", f"ref{n}", item, price, "tg", "h", status,
             f"SIG{n}" if sig else None, claimed_at - 60, claimed_at))


print("\nunits — the $15,000-cola bug")
check("1.50 USDC is 150 cents", machine.to_cents(1_500_000) == 150)
check("2.50 USDC is 250 cents", machine.to_cents(2_500_000) == 250)
check("to_cents returns an int (SDK rejects float)",
      isinstance(machine.to_cents(1_000_000), int))

print("\nthreshold — a day below $10 is held, not dropped")
reset()
for i in range(6):
    sale(i, "cola", DAY1 + i)                       # 6 x 1.50 = 9.00
out = machine.sync()
check("nothing submitted at $9.00", out["submitted"] == 0 and not SUBMITTED)
check("the $9.00 day is reported as holding",
      list(out["holding"].values()) == [900])

print("\nsubmission — one event per UTC day, correct fields")
sale(6, "cola", DAY1 + 6)                           # 7th can -> 10.50
out = machine.sync()
check("one event once the day clears $10", out["submitted"] == 1 and len(SUBMITTED) == 1)
kw = SUBMITTED[0]
check("value is 1050 cents", kw["value"] == 1050 and isinstance(kw["value"], int))
check("machine_id is an int", isinstance(kw["machine_id"], int)
      and kw["machine_id"] == int(os.environ["PEAQ_MACHINE_ID"]))
check("event type is revenue (0)", kw["event_type"] == 0)
check("trust is self-reported (0)", kw["trust_level"] == 0)
check("source chain is off-chain (0), no source hash",
      kw["source_chain_id"] == 0 and kw["source_tx_hash"] is None)
check("currency is USD", kw["currency"] == "USD")
check("timestamp is the day's last sale", kw["timestamp"] == DAY1 + 6)
raw = json.loads(kw["raw_data"])
check("raw_data carries all 7 Solana settlements",
      raw["sales"] == 7 and len(raw["settlements"]) == 7 and raw["chain"] == "solana")
check("metadata is bytes under 4096", isinstance(kw["metadata"], bytes)
      and len(kw["metadata"]) <= 4096)

print("\nidempotency — the claim a judge will probe")
out = machine.sync()
check("second sync submits nothing", out["submitted"] == 0 and len(SUBMITTED) == 1)
with sqlite3.connect(machine.DB) as c:
    n = c.execute("SELECT COUNT(*) FROM peaq_events").fetchone()[0]
check("all 7 invoices recorded against the event", n == 7)

print("\nonly real revenue — CLAIMED means paid AND dispensed")
reset()
for i in range(7):
    sale(100 + i, "cola", DAY2 + i, status="PAID_UNCLAIMED")
for i in range(7):
    sale(200 + i, "cola", DAY2 + i, status="PAID_EXPIRED")
out = machine.sync()
check("unclaimed and expired invoices are never reported",
      out["submitted"] == 0 and not SUBMITTED)

print("\nfailure — a failed submit records nothing and retries next run")
reset()
for i in range(4):
    sale(300 + i, "energy", DAY2 + i)               # 4 x 2.50 = 10.00
FAIL_NEXT.append(True)
out = machine.sync()
check("error surfaced, nothing submitted", out["submitted"] == 0 and len(out["errors"]) == 1)
with sqlite3.connect(machine.DB) as c:
    n = c.execute("SELECT COUNT(*) FROM peaq_events").fetchone()[0]
check("no ledger rows written on failure", n == 0)
out = machine.sync()
check("next run submits the day exactly once", out["submitted"] == 1 and len(SUBMITTED) == 1)

print("\ncutoff — sales before PEAQ_REPORT_FROM are never revenue")
reset()
for i in range(7):
    sale(500 + i, "cola", DAY1 + i)                 # before the mainnet switch
for i in range(4):
    sale(600 + i, "energy", DAY2 + i)               # after it: 10.00
machine.REPORT_FROM = DAY2
try:
    out = machine.sync()
    check("only post-cutoff sales are reported",
          out["submitted"] == 1 and SUBMITTED[0]["value"] == 1000)
    check("pre-cutoff day is neither reported nor held",
          out["holding"] == {} and json.loads(SUBMITTED[0]["raw_data"])["sales"] == 4)
finally:
    machine.REPORT_FROM = 0

print("\ndry run — shows what would publish, publishes nothing")
reset()
for i in range(7):
    sale(400 + i, "cola", DAY1 + i)
out = machine.sync(dry_run=True)
check("dry run submits nothing", not SUBMITTED and "would_submit" in out)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
