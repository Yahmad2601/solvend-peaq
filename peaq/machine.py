#!/usr/bin/env python3
"""SolVend's peaq machine identity and revenue reporting.

The seam between the vending machine and the Machine Economy. SolVend's ledger
already records every invoice it settles; this module gives the machine an
on-chain identity and publishes those settlements as revenue events, so its
Machine Credit Rating is built from real trade.

DESIGN RULE INHERITED FROM solvend.py: no model in the money path. This is
called from the settlement path, never from the agent. A dead model provider
must not stop revenue reporting.

IDEMPOTENCY IS THE WHOLE GAME HERE. A poller that retries, a daemon that
restarts mid-batch, or an operator running the script by hand must never
double-report revenue — an inflated credit score built on duplicates is worse
than no score at all. Every submission is recorded against its invoice_id in
peaq_events, and the UNIQUE index is the backstop.

    python3 peaq/machine.py --spike      # day 1: prove the SDK works at all
    python3 peaq/machine.py --activate   # one-time: mint the machine identity
    python3 peaq/machine.py --sync       # publish any unreported settlements
    python3 peaq/machine.py --status     # DID, credit score, unreported count

Env (via /etc/solvend/env, sourced with `set -a`):
    PEAQ_RPC_URL          agung testnet endpoint
    PEAQ_MACHINE_SEED     machine's own key — NEVER the merchant wallet
    PEAQ_OWNER_ADDRESS    owner that signs activation
    PEAQ_MACHINE_ID       written here by --activate
    SOLVEND_DB            path to the ledger (default /var/lib/solvend/solvend.db)
"""
import json
import os
import sqlite3
import sys
import time

DB = os.environ.get("SOLVEND_DB", "/var/lib/solvend/solvend.db")
RPC_URL = os.environ.get("PEAQ_RPC_URL", "https://wss-async.agung.peaq.network")
MACHINE_ID = os.environ.get("PEAQ_MACHINE_ID", "")
OWNER = os.environ.get("PEAQ_OWNER_ADDRESS", "")

USDC_DECIMALS = 6


# ---------------------------------------------------------------------------
# UNVERIFIED — fill in after the Day 1 spike.
#
# docs.peaq.xyz states the shape but not the exact signatures:
#   * activateMachine  -> machine id, DID, ownership token, locked deposit
#   * submitEvent / batchSubmitEvents -> revenue entries feeding the credit score
#   * SDKs: @peaqos/peaq-os-sdk (JS, recommended) and a Python SDK
#   * testnet: agung, faucet is 2FA-gated
#
# DO NOT guess these signatures into the rest of the codebase. Everything below
# this block is written against *this module's* interface, so when the real SDK
# lands only the three functions here change.
#
# If the Python SDK will not install on ARM, fall back in this order:
#   1. Node + @peaqos/peaq-os-sdk, called as a subprocess from here
#   2. web3.py straight at the EVM contract (peaq chain is EVM-compatible)
#   3. run the client off-Pi reading this ledger — weakest story, declare it
# ---------------------------------------------------------------------------

def _sdk():
    """Import the peaq SDK. Isolated so the fallback path is one edit."""
    raise NotImplementedError(
        "Day 1 spike: install the peaq SDK on the Pi and wire this up.\n"
        "  pip install <peaq python sdk>   OR   npm i @peaqos/peaq-os-sdk\n"
        "Then implement _sdk(), peaq_activate() and peaq_submit_event()."
    )


def peaq_activate(owner_address):
    """One activateMachine call signed by the owner.
    Returns {machine_id, did, tx_hash}."""
    raise NotImplementedError("wire to SDK activateMachine")


def peaq_submit_event(machine_id, event):
    """Publish one revenue event. Returns a tx hash."""
    raise NotImplementedError("wire to SDK submitEvent")


def peaq_credit_score(machine_id):
    """Current Machine Credit Rating. Returns a dict; shape TBD."""
    raise NotImplementedError("wire to SDK credit score read")


# ---------------------------------------------------------------------------
# Ledger side — real, works now, independent of the SDK.
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS peaq_events (
    invoice_id   TEXT PRIMARY KEY,
    machine_id   TEXT NOT NULL,
    amount_base  INTEGER NOT NULL,
    tx_hash      TEXT NOT NULL,
    submitted_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_peaq_tx ON peaq_events(tx_hash);
"""


def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def unreported(conn, limit=50):
    """Settled invoices with no peaq event yet, oldest first.

    CLAIMED means the customer actually took the drink — that is the revenue
    event. AWAITING_PAYMENT and expired invoices are not revenue and must never
    be reported, or the credit score stops meaning anything.
    """
    return conn.execute(
        "SELECT i.invoice_id, i.item, i.amount_base, i.claimed_at, i.signature"
        "  FROM invoices i"
        "  LEFT JOIN peaq_events p ON p.invoice_id = i.invoice_id"
        " WHERE i.status = 'CLAIMED' AND p.invoice_id IS NULL"
        " ORDER BY i.rowid ASC LIMIT ?", (limit,)).fetchall()


def build_event(row):
    """Shape a ledger row into a revenue event.

    Keep this small. The last bounty's trap #3 was flooding a model's context
    with raw RPC payloads; the same discipline applies to what we put on-chain.
    """
    return {
        "invoice_id": row["invoice_id"],
        "item": row["item"],
        "amount": f"{row['amount_base'] / 10 ** USDC_DECIMALS:.2f}",
        "amount_base": row["amount_base"],
        "currency": "USDC",
        "settled_at": row["claimed_at"],
        "payment_ref": row["signature"],
    }


def sync(dry_run=False):
    """Publish every unreported settlement. Safe to run repeatedly."""
    if not MACHINE_ID:
        return {"error": "PEAQ_MACHINE_ID unset — run --activate first"}

    conn = db()
    rows = unreported(conn)
    if not rows:
        return {"submitted": 0, "note": "nothing unreported"}

    sent, failed = [], []
    for row in rows:
        event = build_event(row)
        if dry_run:
            sent.append({"invoice_id": event["invoice_id"], "event": event})
            continue
        try:
            tx_hash = peaq_submit_event(MACHINE_ID, event)
        except Exception as e:                      # noqa: BLE001 — report, continue
            failed.append({"invoice_id": event["invoice_id"], "error": str(e)[:120]})
            continue
        # Record only after the chain accepted it. Crashing here re-sends once,
        # which the UNIQUE index on tx_hash catches.
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO peaq_events"
                " (invoice_id, machine_id, amount_base, tx_hash, submitted_at)"
                " VALUES (?,?,?,?,?)",
                (event["invoice_id"], MACHINE_ID, event["amount_base"],
                 tx_hash, int(time.time())))
        sent.append({"invoice_id": event["invoice_id"], "tx_hash": tx_hash})

    return {"submitted": len(sent), "failed": len(failed),
            "events": sent, "errors": failed}


def status():
    conn = db()
    pending = len(unreported(conn, limit=1000))
    reported = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(amount_base),0) s"
                            " FROM peaq_events").fetchone()
    out = {
        "machine_id": MACHINE_ID or None,
        "rpc": RPC_URL,
        "events_reported": reported["c"],
        "revenue_reported": f"{reported['s'] / 10 ** USDC_DECIMALS:.2f}",
        "unreported": pending,
    }
    try:
        out["credit"] = peaq_credit_score(MACHINE_ID) if MACHINE_ID else None
    except NotImplementedError:
        out["credit"] = "sdk not wired yet"
    return out


def spike():
    """Day 1: can this Pi reach peaq and sign at all? Nothing else."""
    report = {"rpc": RPC_URL, "owner_set": bool(OWNER),
              "seed_set": bool(os.environ.get("PEAQ_MACHINE_SEED"))}
    try:
        _sdk()
        report["sdk"] = "import ok"
    except NotImplementedError as e:
        report["sdk"] = "NOT WIRED"
        report["next"] = str(e).splitlines()[0]
    except Exception as e:                          # noqa: BLE001
        report["sdk"] = f"import FAILED: {type(e).__name__}: {e}"
        report["next"] = "try the Node SDK or web3.py fallback (see header)"
    return report


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "--status"
    if cmd == "--spike":
        out = spike()
    elif cmd == "--activate":
        if not OWNER:
            out = {"error": "PEAQ_OWNER_ADDRESS unset"}
        else:
            out = peaq_activate(OWNER)
    elif cmd == "--sync":
        out = sync()
    elif cmd == "--dry-run":
        out = sync(dry_run=True)
    elif cmd == "--status":
        out = status()
    else:
        out = {"error": "usage: machine.py --spike|--activate|--sync|--dry-run|--status"}
    print(json.dumps(out, indent=2))
    return 0 if "error" not in out else 2


if __name__ == "__main__":
    sys.exit(main())
