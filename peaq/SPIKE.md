# Day 1 spike — prove the peaq SDK runs on the Pi

Six stages, each with a **pass condition** and a **fallback**. Stop at the first
failure and take the fallback; don't push on hoping it resolves later.

Everything here runs **on the Pi**, over SSH.

**Verified from docs.peaq.xyz (6 Oct 2026):**

| | agung testnet |
|---|---|
| EVM RPC | `https://peaq-agung.api.onfinality.io/public` |
| WSS | `wss://peaq-agung.api.onfinality.io/public-ws` |
| Chain ID | `9990` |
| Explorer | `https://agung-testnet.subscan.io/` |
| Gas Station (faucet) | `https://depinstation.peaq.xyz` — **2FA-gated** |

Python SDK: `peaq-os-sdk`, requires **Python ≥ 3.10**, **synchronous** (uses
`requests.Session` — no async, no event loop).

**Confirmed by the docs.peaq.xyz assistant (6 Oct 2026):**
- *"The docs don't mention Raspberry Pi specifically, but the install steps are
  the same for any Linux-based device."* No Pi-specific restrictions.
- *"Any device with internet access and the required Node.js (≥22) or Python
  (≥3.10) runtime — including a Raspberry Pi — should be able to reach"* agung.
- There is a **CLI** (`peaq-os-cli`) which is a cheaper first proof than the SDK.
- Extras exist: `pip install 'peaq-os-cli[ows,solana]'` — **note the `solana`
  extra.** SolVend settles on Solana, so this may be the supported path for
  referencing Solana payments. Investigate during Stage 1a.

---

## Stage 0 — Prerequisites

```bash
ssh pi@solvend.local
python3 --version          # need >= 3.10
sudo apt update && sudo apt install -y python3-venv python3-dev build-essential
```

**There is no browser faucet.** `https://depinstation.peaq.xyz` is an API root
(a browser gets a JSON 404, which is expected). Funding happens from the CLI:
`peaqos activate` detects an under-funded signing wallet, triggers 2FA
enrollment, and funds it via the Gas Station API. The wallet itself is created
on the Pi with `peaqos wallet create` (Stage 1a). No MetaMask/Phantom needed.
See `DOCS-ANSWERS.md` → Gas Station, Wallet.

*Done 7 Oct 2026:* Pi 4 Model B Rev 1.5, aarch64, Debian 13 trixie,
Python 3.13.5, clock synced.

> `build-essential` and `python3-dev` are not optional. Some Ethereum
> dependencies (`coincurve`, `cytoolz`) build native extensions, and on ARM pip
> may have no prebuilt wheel. Without a compiler the install fails with a wall
> of C errors that looks like a broken package but isn't.

**Pass:** Python ≥ 3.10 and build tools installed. (Funding moves to Stage 6.)

---

## Stage 1 — Install into a venv

Debian marks the system Python externally-managed; installing globally fails
with `error: externally-managed-environment`. Use a venv.

```bash
cd ~/solvend-peaq
python3 -m venv .peaq
source .peaq/bin/activate
pip install -U pip wheel
time pip install -U peaq-os-sdk python-dotenv
```

**Pass:** install completes. Note the time — on a Pi this may take several
minutes if anything compiles.

**Fail → fallback ladder:**
1. Read the error. A missing compiler means Stage 0 was skipped.
2. `pip install --only-binary :all: peaq-os-sdk` — tells you whether wheels
   exist for ARM at all.
3. Node route: `sudo apt install -y nodejs npm` then
   `npm install @peaqos/peaq-os-sdk viem dotenv` (needs **Node 22+**; check
   `node --version`, Debian's default is older — use NodeSource if so).
4. `web3.py` straight at the EVM contracts (chain is EVM-compatible).
5. Last resort: run the client off-Pi against the Pi's ledger. Weakest story —
   you must say so in the write-up.

---

## Stage 1a — Prove it with the CLI first (cheapest possible win)

Before the SDK, install the CLI. It is a smaller surface, so if it works you
know pip, the runtime and the ARM wheels are all fine — and if it fails you
learn that in one minute instead of ten.

```bash
pip install 'peaq-os-cli[ows,solana]'
peaqos --version
peaqos --help
```

**Pass:** a version prints. **Screenshot it** — "peaqOS CLI running on a
Raspberry Pi" is already an evidence artifact.

The `solana` extra is worth exploring here: `peaqos --help` may expose Solana
flows that matter, since SolVend's payments settle on Solana and peaq supports
Solana as a home chain for Economics 2.0 machines.

If the extras fail to build on ARM, retry plain `pip install peaq-os-cli` — the
extras are the likely culprit, not the package.

---

## Stage 2 — Prove the import

```bash
python3 -c "
import peaq_os_sdk, sys
from peaq_os_sdk import PeaqosClient, EVENT_TYPE_REVENUE, TRUST_SELF_REPORTED, SUPPORTED_CHAINS
print('sdk       :', getattr(peaq_os_sdk, '__version__', 'unknown'))
print('python    :', sys.version.split()[0])
print('chains    :', SUPPORTED_CHAINS)
print('IMPORT OK')"
```

**Pass:** `IMPORT OK`. **Screenshot this** — it is evidence claim #1 that the SDK
runs on the machine itself.

---

## Stage 3 — Prove network reachability

Before involving the SDK, confirm the Pi can reach agung at all:

```bash
curl -s -X POST https://peaq-agung.api.onfinality.io/public \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
```

**Pass:** a result of `"0x2706"` — that is 9990, the agung chain ID.

**Fail:** DNS or egress problem on the Pi, not an SDK problem. Check
`ping 1.1.1.1` and your resolver before touching anything else.

---

## Stage 4 — Construct the client

Create `~/solvend-peaq/.env` (chmod 600 — it holds a private key):

```bash
PEAQOS_NETWORK=agung
PEAQOS_RPC_URL=https://peaq-agung.api.onfinality.io/public
PEAQOS_PRIVATE_KEY=0x...
PEAQOS_GAS_STATION_URL=https://depinstation.peaq.xyz

# Economics 2.0 deployment record for agung (chain ID 9990)
TOKENOMICS_DEPLOYMENT_ID=agung-2026-08-28

# Tokenomics 1.0 contracts — still required by the SDK constructor.
# COPY-PASTE THESE FROM THE "peaqOS Smart Contracts" DOCS PAGE.
# Do NOT retype them from a screenshot: hex has no letter O, and one wrong
# character fails silently or reverts with an unhelpful error.
IDENTITY_REGISTRY_ADDRESS=0x...
IDENTITY_STAKING_ADDRESS=0x...
EVENT_REGISTRY_ADDRESS=0x...
MACHINE_NFT_ADDRESS=0x...
DID_REGISTRY_ADDRESS=0x0000000000000000000000000000000000000800
BATCH_PRECOMPILE_ADDRESS=0x0000000000000000000000000000000000000805
```

> **Activate against Economics 2.0, not 1.0.** Per the docs assistant: the
> Tokenomics 1.0 contracts are "the legacy path for machines already onboarded;
> new machines on agung activate against Economics 2.0 instead." So pass
> `tokenomics20=Tokenomics20Config(deployment_id="agung-2026-08-28")`.

> **Home the machine on peaq, not Solana.** The `[solana]` extra enables
> `peaqos activate --chain solana`, but **"Solana onboarding is currently paused
> for CLI 0.0.14 / SDK 0.10.0."** Don't build on a paused path with six days.

```bash
chmod 600 .env
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from peaq_os_sdk import PeaqosClient
c = PeaqosClient.from_env()
print('address :', c.address)
print('CLIENT OK')"
```

**Pass:** it prints your address. That proves key loading and signing setup work.

---

## Stage 5 — A read call before a write

Cheapest proof that the client talks to the chain. Try a balance read first:

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from peaq_os_sdk import PeaqosClient
c = PeaqosClient.from_env()
print('address:', c.address)
print([m for m in dir(c) if not m.startswith('_')])"
```

That second line prints the real method surface — **use it to correct anything
in this guide that the docs got wrong.** Look for `activate_machine`,
`submit_event`, `batch_submit_events`.

**Pass:** methods listed, no exception.

---

## Stage 6 — Activate the machine (the real proof)

```bash
python3 peaq/machine.py --activate
```

**Pass:** a machine id, a `did:peaq:` string, and a transaction hash. Open the
hash on `https://agung-testnet.subscan.io/` and **screenshot it** — that is
evidence claim #2, and the single most important artifact of Day 1.

Record the machine id into `/etc/solvend/env` as `PEAQ_MACHINE_ID`.

**The bond is trivial — do not over-plan for it.** Entry tier (0) is priced at
**$0.02 USD per 365-day period**, converted to PEAQ at the live oracle rate.
Check the exact amount before committing:

```bash
peaqos activate --machine-type VendingMachine --tier entry --dry-run
```

`--dry-run` previews without submitting and prints the live PEAQ figure. Run it
before the real activation — agung runs an older contract build
(`agung-2026-08-28`) whose tier prices differ from mainnet.

---

## What to report back

Paste the output of Stages 2, 3 and 6. If anything failed, paste the **exact**
error — not a summary. The fallback chosen at the failure point determines the
rest of the build.

## Capture as you go

Stage 2 and Stage 6 outputs belong in `EVIDENCE.md` today, not on Day 5.
