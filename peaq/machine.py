#!/usr/bin/env python3
"""SolVend's peaq machine identity and revenue reporting.

The seam between the vending machine and the Machine Economy. SolVend's ledger
already records every invoice it settles; this module gives the machine an
on-chain identity and publishes those settlements as revenue events, so its
Machine Credit Rating is built from real trade.

DESIGN RULE INHERITED FROM solvend.py: no model in the money path. This is
called from the settlement path, never from the agent. A dead model provider
must not stop revenue reporting.

THREE THINGS peaq DICTATES, ALL EASY TO GET WRONG
-------------------------------------------------
1. `value` is in ISO 4217 *minor units* — CENTS, not token base units.
   SolVend's ledger stores USDC base units at 6 decimals, so a 1.50 drink is
   1_500_000 there and **150** here. Passing the raw base amount would report a
   $15,000 sale and make the rating meaningless.

2. The Machine Credit Rating ignores revenue events below **1,000 cents ($10)**,
   and scoring "factors daily aggregation — events are summed per UTC day, and
   only days meeting a minimum economic threshold count." So we aggregate
   **one event per UTC day**, submitted once that day clears $10. At 1.50 a can
   that is 7 sales in a day. Every covered invoice is recorded against the
   transaction, so nothing double-counts and nothing is silently dropped.

3. `source_tx_hash` must be 0x-prefixed 32-byte hex (66 chars). **A Solana
   base58 signature does not fit**, and trust level 1 (on-chain verifiable)
   requires that field. So events are submitted at TRUST_SELF_REPORTED with the
   Solana settlement signature carried in `raw_data` instead — the audit trail
   survives even though peaq cannot verify it natively.
   → This is a real limitation worth reporting upstream: peaq's cross-chain
     audit trail documents peaq (3338) and Base (8453); a Solana-settled machine
     cannot currently claim on-chain-verifiable trust.

IDEMPOTENCY IS THE WHOLE GAME. A retry, a restart mid-batch, or an operator
running this by hand must never double-report. An inflated score built on
duplicates is worse than no score at all.

    python3 peaq/machine.py --spike      # day 1: prove the SDK works at all
    python3 peaq/machine.py --activate   # one-time: mint the machine identity
    python3 peaq/machine.py --sync       # publish any UTC day that cleared $10
    python3 peaq/machine.py --dry-run    # show what WOULD be published
    python3 peaq/machine.py --status     # DID, credit, reported, pending

Env (via /etc/solvend/env with `set -a`, or .env):
    PEAQOS_RPC_URL            https://peaq-agung.api.onfinality.io/public
    PEAQ_WALLET               OWS vault wallet name (`solvend`) — the machine's
                              own wallet, NEVER the merchant wallet
    OWS_PASSPHRASE            unlocks it; read by PeaqosClient.from_wallet()
    TOKENOMICS_DEPLOYMENT_ID  agung-2026-08-28
    PEAQ_MACHINE_ID           written here by --activate
    PEAQ_MACHINE_DID          written here by --activate
    SOLVEND_DB                ledger path (default /var/lib/solvend/solvend.db)
"""
import datetime as dt
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict

DB = os.environ.get("SOLVEND_DB", "/var/lib/solvend/solvend.db")
RPC_URL = os.environ.get("PEAQOS_RPC_URL",
                         "https://peaq-agung.api.onfinality.io/public")
DEPLOYMENT_ID = os.environ.get("TOKENOMICS_DEPLOYMENT_ID", "agung-2026-08-28")
MACHINE_ID = os.environ.get("PEAQ_MACHINE_ID", "")
MACHINE_DID = os.environ.get("PEAQ_MACHINE_DID", "")

USDC_DECIMALS = 6          # SolVend ledger precision
MIN_REVENUE_CENTS = 1000   # peaq: a day below $10 does not count toward the MCR
CURRENCY = "USD"           # ISO 4217; value is in minor units of this
SOURCE_CHAIN_PEAQ = 3338


def to_cents(amount_base):
    """USDC base units -> ISO 4217 minor units. 1_500_000 -> 150."""
    return round(amount_base / 10 ** USDC_DECIMALS * 100)


def utc_day(epoch_secs):
    """UTC date key — peaq sums events per UTC day."""
    return dt.datetime.fromtimestamp(epoch_secs, dt.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# SDK boundary — the only part the Day 1 spike changes. See peaq/SPIKE.md.
#
# Verified by inspect.signature() on the Pi, peaq-os-cli 0.0.15 / SDK 0.11.0
# (7 Oct 2026). peaq_os_sdk has no __version__; use `peaqos --version`.
#
#   PeaqosClient.from_wallet(name_or_id, passphrase=None, ows_signing=True,
#                            vault_path=None, **config_kwargs)
#       passphrase falls back to OWS_PASSPHRASE. NOT verified at construction:
#       a wrong passphrase only surfaces on the first signature.
#   client.activate_machine(params: ActivateMachineParams) -> ActivateMachineResult
#       raises TokenomicsConfigError if the client has no tokenomics20.
#   client.submit_event(*, machine_id: int, event_type: int, value: int,
#                       timestamp: int, raw_data: bytes|None, trust_level: int,
#                       source_chain_id: int, source_tx_hash: Hex32|None,
#                       metadata: bytes, currency: str|None) -> (str, bytes)
#       value is an ISO 4217 subunit int; float/Decimal/str/None -> TypeError.
#       machine_id is an INT. MACHINE_ID above is a str from env: cast it.
#   client.query_mcr(...) reads the credit rating. PEAQOS_MCR_API_URL defaults
#       to http://127.0.0.1:8000. Only https://mcr.peaq.xyz is documented, and
#       it is the peaq-mainnet host. UNVERIFIED: whether agung has an MCR at
#       all (docs: agung-2026-08-28 -> DEPLOYMENT_UNAVAILABLE, "no paired MCR").
#   EVENT_TYPE_REVENUE == 0, TRUST_SELF_REPORTED == 0
#   SUPPORTED_CHAINS == {peaq:3338, ethereum:1, base:8453, polygon:137,
#                        arbitrum:42161, optimism:10}   (no Solana, no agung)
#   Solana-settled revenue: source_chain_id=0 (off-chain), source_tx_hash=None,
#       trust_level=TRUST_SELF_REPORTED. Verified, DOCS-ANSWERS.md.
#
# from_wallet config_kwargs (docs example): rpc_url, identity_registry,
#   identity_staking, event_registry, machine_nft, did_registry,
#   batch_precompile.
# Activate against Economics 2.0 (kwarg verified from PeaqosClient.__init__):
#   tokenomics20=Tokenomics20Config(deployment_id=DEPLOYMENT_ID)
#   deployment_id is one of "agung-2026-08-28" | "peaq-mainnet". Only
#   peaq-mainnet carries an MCR api_base (https://mcr.peaq.xyz) in the SDK.
#   ActivateMachineParams: machine_type + credential_subject bytes fix the
#   PERMANENT machine ID. Choose them once, deliberately.
#   Tokenomics-mode DID for query_mcr: "did:peaq:" + base-10 machine ID.
# ---------------------------------------------------------------------------

def _client():
    """Construct the peaqOS client. One edit point for the Node/web3 fallback."""
    raise NotImplementedError(
        "Day 1 spike not done. See peaq/SPIKE.md.\n"
        "  pip install -U peaq-os-sdk python-dotenv   (Python >= 3.10)\n"
        "Then: from peaq_os_sdk import PeaqosClient; return PeaqosClient.from_env()"
    )


def peaq_activate():
    """activateMachine (Economics 2.0) -> {machine_id, did, tx_hash}."""
    raise NotImplementedError("wire to client.activate_machine()")


def peaq_submit_revenue(machine_id, cents, timestamp, raw_data):
    """One aggregated revenue event for a UTC day. Returns a tx hash.

    trust_level stays self-reported: see finding 3 in the module docstring.
    """
    raise NotImplementedError("wire to client.submit_event()")


def peaq_credit_score(did):
    """Machine Credit Rating — GET /mcr/{did}."""
    raise NotImplementedError("wire to the MCR endpoint")


# ---------------------------------------------------------------------------
# Ledger side — real, works now, independent of the SDK.
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS peaq_events (
    invoice_id   TEXT PRIMARY KEY,
    machine_id   TEXT NOT NULL,
    utc_day      TEXT NOT NULL,
    cents        INTEGER NOT NULL,
    tx_hash      TEXT NOT NULL,
    submitted_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_peaq_tx  ON peaq_events(tx_hash);
CREATE INDEX IF NOT EXISTS idx_peaq_day ON peaq_events(utc_day);
"""
# tx_hash is indexed but NOT unique — one aggregated event legitimately covers
# several invoices. invoice_id being the primary key is what prevents
# double-reporting.


def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def unreported(conn, limit=1000):
    """Settled invoices with no peaq event yet, oldest first.

    CLAIMED means paid AND the drink physically collected — that is the revenue
    event. AWAITING_PAYMENT and expired invoices are never revenue; reporting
    them would make the credit score meaningless.
    """
    return conn.execute(
        "SELECT i.invoice_id, i.item, i.amount_base, i.claimed_at, i.signature"
        "  FROM invoices i"
        "  LEFT JOIN peaq_events p ON p.invoice_id = i.invoice_id"
        " WHERE i.status = 'CLAIMED' AND p.invoice_id IS NULL"
        " ORDER BY i.rowid ASC LIMIT ?", (limit,)).fetchall()


def group_by_day(rows):
    """{utc_day: {cents, rows}} — peaq scores revenue per UTC day."""
    days = defaultdict(lambda: {"cents": 0, "rows": []})
    for r in rows:
        key = utc_day(r["claimed_at"])
        days[key]["cents"] += to_cents(r["amount_base"])
        days[key]["rows"].append(r)
    return dict(days)


def build_raw(day, bucket):
    """Payload for one day's revenue. Deliberately small.

    Carries the Solana settlement signatures so the audit trail survives, since
    source_tx_hash cannot take a base58 signature (finding 3).
    """
    rows = bucket["rows"]
    return {
        "day": day,
        "sales": len(rows),
        "items": sorted({r["item"] for r in rows}),
        "invoices": [r["invoice_id"] for r in rows],
        "settlements": [r["signature"] for r in rows if r["signature"]],
        "chain": "solana",
    }


def sync(dry_run=False):
    """Publish each UTC day that has cleared the MCR threshold."""
    if not MACHINE_ID:
        return {"error": "PEAQ_MACHINE_ID unset — run --activate first"}

    conn = db()
    rows = unreported(conn)
    if not rows:
        return {"submitted": 0, "note": "nothing unreported"}

    days = group_by_day(rows)
    ready = {d: b for d, b in days.items() if b["cents"] >= MIN_REVENUE_CENTS}
    holding = {d: b["cents"] for d, b in days.items()
               if b["cents"] < MIN_REVENUE_CENTS}

    if not ready:
        return {
            "submitted": 0,
            "holding": holding,
            "threshold_cents": MIN_REVENUE_CENTS,
            "note": ("no UTC day has cleared $10 yet. peaq sums events per UTC "
                     "day and ignores days below the economic threshold."),
        }

    if dry_run:
        return {"would_submit": {d: {"cents": b["cents"],
                                     "raw": build_raw(d, b)}
                                 for d, b in ready.items()},
                "holding": holding}

    submitted, errors = [], []
    for day in sorted(ready):
        bucket = ready[day]
        raw = build_raw(day, bucket)
        # Timestamp the event at the day's last sale, not "now" — the event
        # describes that day's trade.
        ts = max(r["claimed_at"] for r in bucket["rows"])
        try:
            tx_hash = peaq_submit_revenue(
                MACHINE_ID, bucket["cents"], ts,
                json.dumps(raw, separators=(",", ":")).encode())
        except Exception as e:                      # noqa: BLE001
            errors.append({"day": day, "error": f"{type(e).__name__}: {e}"[:160]})
            continue

        # Written only after the chain accepts. A crash here re-sends once; the
        # invoice_id primary key means the retry cannot double-count.
        now = int(time.time())
        with conn:
            conn.executemany(
                "INSERT OR IGNORE INTO peaq_events"
                " (invoice_id, machine_id, utc_day, cents, tx_hash, submitted_at)"
                " VALUES (?,?,?,?,?,?)",
                [(r["invoice_id"], MACHINE_ID, day,
                  to_cents(r["amount_base"]), tx_hash, now)
                 for r in bucket["rows"]])
        submitted.append({"day": day, "sales": len(bucket["rows"]),
                          "cents": bucket["cents"], "tx_hash": tx_hash})

    return {"submitted": len(submitted), "events": submitted,
            "holding": holding, "errors": errors}


def status():
    conn = db()
    pending = group_by_day(unreported(conn))
    rep = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(cents),0) s,"
                       " COUNT(DISTINCT tx_hash) t,"
                       " COUNT(DISTINCT utc_day) d FROM peaq_events").fetchone()
    out = {
        "machine_id": MACHINE_ID or None,
        "did": MACHINE_DID or None,
        "deployment": DEPLOYMENT_ID,
        "rpc": RPC_URL,
        "sales_reported": rep["c"],
        "days_reported": rep["d"],
        "events_on_chain": rep["t"],
        "revenue_reported_usd": f"{rep['s'] / 100:.2f}",
        "pending_by_day": {d: f"{b['cents'] / 100:.2f}" for d, b in pending.items()},
        "threshold_usd": f"{MIN_REVENUE_CENTS / 100:.2f}",
    }
    try:
        out["credit"] = peaq_credit_score(MACHINE_DID) if MACHINE_DID else None
    except NotImplementedError:
        out["credit"] = "sdk not wired yet"
    return out


def spike():
    """Day 1: can this Pi import the SDK and construct a client? Nothing else."""
    report = {"rpc": RPC_URL, "deployment": DEPLOYMENT_ID,
              "db": DB, "db_exists": os.path.exists(DB)}
    try:
        _client()
        report["sdk"] = "client ok"
    except NotImplementedError as e:
        report["sdk"] = "NOT WIRED"
        report["next"] = str(e).splitlines()[0]
    except Exception as e:                          # noqa: BLE001
        report["sdk"] = f"FAILED: {type(e).__name__}: {e}"[:200]
        report["next"] = "see peaq/SPIKE.md fallback ladder"
    return report


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "--status"
    if cmd == "--spike":
        out = spike()
    elif cmd == "--activate":
        out = peaq_activate()
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
