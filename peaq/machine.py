#!/usr/bin/env python3
"""SolVend's peaq machine identity and revenue reporting.

Gives the vending machine an on-chain identity on peaq and publishes its sales
as revenue events, so its Machine Credit Rating is built from real trade.

Called by the minute poller (solvend/bin/solvend-poll.sh), never by a chat or a
model: a sale is reported because the ledger says it was paid and dispensed.

Reporting rules
---------------
1. `value` is in ISO 4217 minor units (US cents). The ledger stores USDC base
   units (6 decimals), so a 1.50 drink is 1_500_000 there and 150 here.
2. The Machine Credit Rating counts only revenue events of at least 1,000 cents
   ($10) and sums revenue per UTC day. Sales are therefore aggregated into one
   event per UTC day, submitted once that day reaches $10.
3. `source_tx_hash` accepts only a 32-byte hex hash, and Solana is not a
   supported source chain, so events are self-reported (trust level 0) with
   `source_chain_id=0`. The Solana signature of every sale travels in
   `raw_data`, so each event can be checked against Solana.
4. Idempotent: every reported invoice is recorded against its event, keyed by
   invoice ID. A retry, restart or manual run never reports a sale twice.

Usage
-----
    python3 peaq/machine.py --spike             # build a signing client, read chain id
    python3 peaq/machine.py --activate-preview  # bond quote and machine ID, signs nothing
    python3 peaq/machine.py --activate          # one-time: activate the machine identity
    python3 peaq/machine.py --sync              # publish every UTC day that reached $10
    python3 peaq/machine.py --dry-run           # show what --sync would publish
    python3 peaq/machine.py --status            # DID, credit rating, reported, pending

Environment (/etc/solvend/env, or a repo-root .env for manual runs)
-----------
    PEAQOS_RPC_URL            peaq mainnet RPC (chain 3338)
    PEAQOS_OWS_WALLET         the machine's own OWS wallet (never the merchant's)
    OWS_PASSPHRASE            vault passphrase, read by PeaqosClient.from_wallet()
    TOKENOMICS_DEPLOYMENT_ID  peaq-mainnet (the deployment with a credit rating service)
    PEAQOS_MCR_API_URL        https://mcr.peaq.xyz
    IDENTITY_REGISTRY_ADDRESS, IDENTITY_STAKING_ADDRESS, EVENT_REGISTRY_ADDRESS,
    MACHINE_NFT_ADDRESS, DID_REGISTRY_ADDRESS, BATCH_PRECOMPILE_ADDRESS
                              contract addresses required by the client
    PEAQ_MACHINE_ID           base-10 machine ID, from activation
    PEAQ_REPORT_FROM          Unix time from which sales count as revenue
    SOLVEND_DB                ledger path (default /var/lib/solvend/solvend.db)
"""
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict

try:
    # Hand runs pick up the repo-root .env. The poller sources /etc/solvend/env
    # first, and override=False means the env file always wins.
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("SOLVEND_DB", "/var/lib/solvend/solvend.db")
RPC_URL = os.environ.get("PEAQOS_RPC_URL", "https://quicknode1.peaq.xyz")
DEPLOYMENT_ID = os.environ.get("TOKENOMICS_DEPLOYMENT_ID", "peaq-mainnet")
MCR_API_URL = os.environ.get("PEAQOS_MCR_API_URL", "https://mcr.peaq.xyz")
WALLET = os.environ.get("PEAQOS_OWS_WALLET", "solvend")
MACHINE_ID = os.environ.get("PEAQ_MACHINE_ID", "")
# Only sales claimed at or after this Unix time are revenue; earlier ledger rows
# are pre-production test data. 0 = no cutoff (tests, fresh ledgers).
REPORT_FROM = int(os.environ.get("PEAQ_REPORT_FROM", "0") or 0)
# Tokenomics mode DID is "did:peaq:" + the base-10 machine ID (query_mcr docstring).
MACHINE_DID = f"did:peaq:{MACHINE_ID}" if MACHINE_ID else ""

USDC_DECIMALS = 6          # SolVend ledger precision
MIN_REVENUE_CENTS = 1000   # peaq: a day below $10 does not count toward the MCR
CURRENCY = "USD"           # ISO 4217; value is in minor units of this
# Solana is not a supported source chain, so a Solana-settled sale is reported
# as off-chain (0) with no source_tx_hash (rule 3 above).
SOURCE_CHAIN_OFFCHAIN = 0
METADATA = b'{"schema":"solvend.revenue.v1"}'   # metadata is required; max 4096 B

# Permanent identity inputs: machine_type + credential_subject determine the
# machine ID, which cannot change after activation. Never edit.
MACHINE_TYPE = "VendingMachine"
TIER = "entry"
CREDENTIAL_SUBJECT_FILE = os.path.join(HERE, "credential-subject.json")
DID_DOCUMENT_FILE = os.path.join(HERE, "did-document.json")

_CLIENT_ENV = ("PEAQOS_RPC_URL", "IDENTITY_REGISTRY_ADDRESS",
               "IDENTITY_STAKING_ADDRESS", "EVENT_REGISTRY_ADDRESS",
               "MACHINE_NFT_ADDRESS", "DID_REGISTRY_ADDRESS",
               "BATCH_PRECOMPILE_ADDRESS")


def to_cents(amount_base):
    """USDC base units -> ISO 4217 minor units. 1_500_000 -> 150."""
    return round(amount_base / 10 ** USDC_DECIMALS * 100)


def utc_day(epoch_secs):
    """UTC date key — peaq sums events per UTC day."""
    return dt.datetime.fromtimestamp(epoch_secs, dt.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# SDK boundary (peaq-os-cli 0.0.15 / peaq_os_sdk 0.11.0)
#
#   PeaqosClient.from_wallet(name_or_id, passphrase=None, ows_signing=True,
#                            vault_path=None, **config_kwargs)
#       Signs through the OWS vault; the raw key never enters this process.
#       The passphrase falls back to OWS_PASSPHRASE and is only checked on
#       the first signature.
#   config_kwargs: rpc_url, identity_registry, identity_staking,
#       event_registry, machine_nft, did_registry, batch_precompile, api_url,
#       tokenomics20=Tokenomics20Config(deployment_id=...)
#   client.submit_event(*, machine_id: int, event_type: int, value: int,
#                       timestamp: int, raw_data: bytes|None, trust_level: int,
#                       source_chain_id: int, source_tx_hash: Hex32|None,
#                       metadata: bytes, currency: str|None) -> (tx_hash, data_hash)
#       value must be an int (float/Decimal/str raise TypeError).
#   client.query_mcr(did) -> MCRResponse
#       did is "did:peaq:" + the base-10 machine ID.
#   EVENT_TYPE_REVENUE == 0, TRUST_SELF_REPORTED == 0
#   Only the peaq-mainnet deployment has a credit rating service
#   (api_base https://mcr.peaq.xyz); the agung testnet deployment has none.
# ---------------------------------------------------------------------------

_client_cache = None


def _client():
    """The peaqOS client, signing through the OWS vault. One edit point.

    The key never leaves ~/.ows: from_wallet() signs through OWS and reads the
    passphrase from OWS_PASSPHRASE. A wrong passphrase is NOT caught here — it
    surfaces on the first signature.
    """
    global _client_cache
    if _client_cache is None:
        missing = [k for k in _CLIENT_ENV if not os.environ.get(k)]
        if missing:
            raise RuntimeError("missing env: " + ", ".join(missing))
        from peaq_os_sdk import Address, PeaqosClient, Tokenomics20Config
        env = os.environ
        # A person at a terminal gets a prompt, like the CLI. The poller has
        # no TTY, so there the SDK raises PeaqosError instead of hanging —
        # verified on the Pi, 8 Oct 2026. Kept in this process's environment
        # only (never on disk), so a child `peaqos` reads it without asking twice.
        if not env.get("OWS_PASSPHRASE") and sys.stdin.isatty():
            import getpass
            env["OWS_PASSPHRASE"] = getpass.getpass(
                f"Vault passphrase for wallet '{WALLET}': ")
        _client_cache = PeaqosClient.from_wallet(
            WALLET,
            rpc_url=env["PEAQOS_RPC_URL"],
            identity_registry=Address(env["IDENTITY_REGISTRY_ADDRESS"]),
            identity_staking=Address(env["IDENTITY_STAKING_ADDRESS"]),
            event_registry=Address(env["EVENT_REGISTRY_ADDRESS"]),
            machine_nft=Address(env["MACHINE_NFT_ADDRESS"]),
            did_registry=Address(env["DID_REGISTRY_ADDRESS"]),
            batch_precompile=Address(env["BATCH_PRECOMPILE_ADDRESS"]),
            api_url=MCR_API_URL,
            tokenomics20=Tokenomics20Config(deployment_id=DEPLOYMENT_ID),
        )
    return _client_cache


def _credential_subject_hex():
    """The exact bytes the dry run validated. Read, never regenerated."""
    with open(CREDENTIAL_SUBJECT_FILE, "rb") as f:
        return "0x" + f.read().hex()


def peaq_activate(dry_run=True):
    """activateMachine via the CLI, with the inputs the dry run validated.

    Uses the CLI rather than activate_machine() because the CLI path is what
    was verified end to end, and it shows the activation terms and asks before
    signing. That is the right shape for a one-time, irreversible mainnet write.
    Record the printed machine ID as PEAQ_MACHINE_ID.
    """
    # Resolve peaqos next to this interpreter: a scheduler's PATH does not
    # include the venv.
    peaqos = os.path.join(os.path.dirname(sys.executable), "peaqos")
    manufacturer = str(_client().address)
    cmd = [peaqos, "activate",
           "--machine-type", MACHINE_TYPE,
           "--credential-subject-hex", _credential_subject_hex(),
           "--tier", TIER,
           "--manufacturer", manufacturer,
           "--did-document", DID_DOCUMENT_FILE]
    if dry_run:
        cmd += ["--dry-run", "--json"]
    rc = subprocess.call(cmd)
    return {"activate": "dry-run" if dry_run else "submitted", "exit_code": rc}


def peaq_submit_revenue(machine_id, cents, timestamp, raw_data):
    """One aggregated revenue event for a UTC day. Returns a tx hash.

    trust_level stays self-reported: see finding 3 in the module docstring.
    """
    from peaq_os_sdk import EVENT_TYPE_REVENUE, TRUST_SELF_REPORTED
    tx_hash, _data_hash = _client().submit_event(
        machine_id=int(machine_id),        # SDK wants an int; env gives a str
        event_type=EVENT_TYPE_REVENUE,
        value=int(cents),                  # ISO 4217 minor units; float -> TypeError
        timestamp=int(timestamp),
        raw_data=raw_data,
        trust_level=TRUST_SELF_REPORTED,
        source_chain_id=SOURCE_CHAIN_OFFCHAIN,
        source_tx_hash=None,
        metadata=METADATA,
        currency=CURRENCY,
    )
    return tx_hash


def peaq_credit_score(did):
    """Machine Credit Rating — GET /mcr/{did} on the deployment's MCR."""
    return dict(_client().query_mcr(did))


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
        "   AND i.claimed_at >= ?"
        " ORDER BY i.rowid ASC LIMIT ?", (REPORT_FROM, limit)).fetchall()


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
        "report_from": REPORT_FROM or None,
    }
    try:
        out["credit"] = peaq_credit_score(MACHINE_DID) if MACHINE_DID else None
    except Exception as e:                          # noqa: BLE001
        # Status is read-only and must never fail on the credit read.
        out["credit"] = f"unavailable: {type(e).__name__}: {e}"[:200]
    return out


def spike():
    """Can this Pi build a signing client and reach the chain? Writes nothing."""
    report = {"rpc": RPC_URL, "deployment": DEPLOYMENT_ID, "wallet": WALLET,
              "db": DB, "db_exists": os.path.exists(DB)}
    try:
        c = _client()
        report["address"] = str(c.address)
        report["chain_id"] = c.web3.eth.chain_id
        report["sdk"] = "client ok"
    except Exception as e:                          # noqa: BLE001
        report["sdk"] = f"FAILED: {type(e).__name__}: {e}"[:200]
        report["next"] = "check PEAQOS_* settings and the OWS wallet"
    return report


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "--status"
    if cmd == "--spike":
        out = spike()
    elif cmd == "--activate-preview":
        out = peaq_activate(dry_run=True)
    elif cmd == "--activate":
        out = peaq_activate(dry_run=False)
    elif cmd == "--sync":
        out = sync()
    elif cmd == "--dry-run":
        out = sync(dry_run=True)
    elif cmd == "--status":
        out = status()
    else:
        out = {"error": "usage: machine.py --spike|--activate-preview|--activate"
                        "|--sync|--dry-run|--status"}
    print(json.dumps(out, indent=2))
    return 0 if "error" not in out else 2


if __name__ == "__main__":
    sys.exit(main())
