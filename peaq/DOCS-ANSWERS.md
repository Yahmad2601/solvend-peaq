# Verified facts from the docs.peaq.xyz assistant

Everything here was **asked and answered**, not inferred. Add to it as you go;
delete nothing without replacing it with a newer answer and the date.

Format: question → answer → date → where it's used.

---

## Network — agung testnet

| | Value |
|---|---|
| EVM RPC | `https://peaq-agung.api.onfinality.io/public` |
| WSS | `wss://peaq-agung.api.onfinality.io/public-ws` |
| Chain ID | `9990` |
| Explorer | `https://agung-testnet.subscan.io/` |
| Faucet ("Gas Station") | `https://depinstation.peaq.xyz` — 2FA-gated |
| peaq mainnet chain ID | `3338` (for `source_chain_id`) |

*Verified 6 Oct 2026. Used in: `peaq/machine.py`, `peaq/SPIKE.md`, `.env`.*

## Economics 2.0 deployment

**`TOKENOMICS_DEPLOYMENT_ID = agung-2026-08-28`** (chain ID 9990).

> "`TOKENOMICS_DEPLOYMENT_ID` is for the newer Economics 2.0 path, not
> Tokenomics 1.0 — on agung that deployment record is `agung-2026-08-28`. The
> Tokenomics 1.0 contracts are the legacy path for machines already onboarded;
> **new machines on agung activate against Economics 2.0 instead.**"

The four Tokenomics 1.0 contract addresses are still required by the SDK
constructor. **Copy them from the "peaqOS Smart Contracts" docs page** — do not
retype from a screenshot.

*Verified 6 Oct 2026.*

## Activation bond

Entry tier (`0`) is **$0.02 USD per 365-day period**, converted to PEAQ at the
live oracle rate: `bondAmount = tierPriceUsd(0) / latest PEAQ price`.

agung runs an older contract build with different tier prices than mainnet —
always check the live figure with `peaqos activate ... --dry-run` or
`previewMachineActivation`.

Tiers: `0` = Entry, `1` = Basic, `2` = Pro.

*Verified 6 Oct 2026.*

## `submit_event` — the three gotchas

**1. `value` is ISO 4217 minor units (cents)**, not token base units.
A 1.50 USDC drink is `1_500_000` in SolVend's ledger and **`150`** here.

**2. The Machine Credit Rating has a floor and a daily rhythm:**

> "Only revenue events worth at least **1,000 USD cents ($10)** after FX
> conversion are summed into `total_revenue` on `GET /mcr/{did}`. Events below
> that are excluded from the total, though scoring also factors **daily
> aggregation** (events are summed per **UTC day**, and only days meeting a
> minimum economic threshold count)."

→ `machine.py` aggregates **one event per UTC day**, submitted once that day
clears $10. At 1.50 a can that is **7 sales in one UTC day**.

**3. `source_tx_hash` is `bytes32` — a Solana signature does not fit:**

> "The `source_tx_hash` field must be a 0x-prefixed, 32-byte hex string (66
> chars) — it does not accept a base58-encoded Solana signature. The SDK checks
> the length only, so pass a real hash. Since trust level 1 requires
> `source_tx_hash`, if the underlying event is a Solana payment you can't pass
> its base58 signature directly in that field."

→ Events submit at **`TRUST_SELF_REPORTED`** with the Solana settlement
signatures carried in `raw_data`. **File this upstream** — a Solana-settled
machine cannot currently claim on-chain-verifiable trust.

Event types: `0` = Revenue, `1` = Activity. `metadata` max 4096 bytes.
Trust levels: `0` self-reported, `1` on-chain verifiable, `2` hardware-signed.
`source_chain_id` documented examples: peaq `3338`, Base `8453`. **Solana is
not in that table.**

*Verified 6 Oct 2026. Used in: `peaq/machine.py`.*

## Credit rating read

`GET /mcr/{did}`

*Verified 6 Oct 2026.*

## Solana support — paused

> "`[solana]` extra enables `peaqos activate --chain solana`,
> `peaqos stream pay --chain solana`, and Solana reads/previews/management/
> events — pulling in `@solana/web3.js` / `@coral-xyz/anchor` (JS) or the Python
> extra, plus requiring `PEAQOS_SVM_RPC_URL`. **Solana onboarding is currently
> paused for CLI 0.0.14 / SDK 0.10.0.**"

→ **Home the machine on peaq/agung, not Solana.** Revisit after the hackathon.

*Verified 6 Oct 2026.*

## Gas Station (faucet) — API only, no browser UI

> "The documentation only describes the Gas Station as a **CLI/SDK faucet
> service** (`PEAQOS_GAS_STATION_URL=https://depinstation.peaq.xyz`), not a
> browser UI you connect a wallet to or paste an address into. The flow is:
> `peaqos activate` detects a signing wallet with insufficient gas, **triggers
> 2FA enrollment**, and funds that wallet programmatically through the Gas
> Station API — there's no mention of a WalletConnect/MetaMask connection or a
> manual address-paste form."

Confirmed in practice: opening the URL in a browser returns
`{"name":"NotFound","message":"Page not found","code":404,...}`. That is
expected — it is an API root, not a broken faucet.

> "The cap values, rate-limit windows, and minimum gas balance are configured
> server-side, so branch on the error codes and the `skipped` status rather
> than hard-coding numbers."

→ **No published PEAQ amount per request**, and no guarantee one funding covers
Entry bond + gas. Call `fundFromGasStation`, then compare `fundedAmount` /
`currentBalance` against the live `previewMachineActivation` bond.

*Verified 7 Oct 2026. Used in: `peaq/SPIKE.md` Stage 0.*

## Wallet / key generation — built into the CLI

> "`peaqos wallet create <name>` (requires the `[ows]` extra) generates a new
> BIP-39 mnemonic-backed wallet and derives EVM/Solana accounts for it, stored
> in the encrypted local vault at `~/.ows/wallets/`. You can also import an
> existing raw EVM private key via `peaqos wallet import <name>
> --private-key-file <path>`. So key generation is built into the CLI — no need
> to create it externally."

→ **No MetaMask/Phantom/Solflare needed.** Generate the machine's wallet on the
Pi itself, so the key never exists on a laptop.

*Verified 7 Oct 2026. Used in: `peaq/SPIKE.md` Stage 1a.*

## Raspberry Pi

Confirmed on the actual machine (7 Oct 2026): `Raspberry Pi 4 Model B Rev 1.5`,
`aarch64`, Debian 13 (trixie), **Python 3.13.5**, clock NTP-synchronised,
24G disk free, 3.7Gi RAM. No Node installed.

> "The docs don't mention Raspberry Pi specifically, but the install steps are
> the same for any Linux-based device (Python/pip, Node/npm)."
> "Any device with internet access and the required Node.js (≥22) or Python
> (≥3.10) runtime — including a Raspberry Pi — should be able to reach" agung.

Install: `pip install peaq-os-cli` then `peaqos --version`.
Extras: `pip install 'peaq-os-cli[ows,solana]'`.
Python SDK: `pip install -U peaq-os-sdk python-dotenv` — **synchronous**, uses
`requests.Session`, no async.

*Verified 6 Oct 2026.*

---

## Still to ask

- [ ] Does `PeaqosClient.from_env()` (Python SDK 0.10.0) read a wallet from the
      OWS vault created by `peaqos wallet create`, or does it only accept a raw
      `PEAQOS_PRIVATE_KEY`? If only the raw key, how is it exported from
      `~/.ows/wallets/`?
- [ ] What 2FA method does Gas Station enrollment during `peaqos activate` use
      (TOTP authenticator app, email, other), and can it complete over an SSH
      session with no browser on the device?
- [ ] Does `peaqos activate --dry-run` call the Gas Station, or is funding
      triggered only on a real (non-dry-run) activation?

- [ ] What are the exact agung Tokenomics 1.0 contract addresses? *(copy from
      the "peaqOS Smart Contracts" page rather than transcribing)*
- [ ] What `machine_type` values are valid for `activate_machine`? Is
      `"VendingMachine"` acceptable, or is it a fixed enum?
- [ ] What `verification_methods` / `public_key_multibase` does a machine need
      if it has no Ed25519 key of its own yet — can one be generated by the CLI?
- [ ] Does `GET /mcr/{did}` work on agung, and what does the response look like
      before any revenue has been reported?
- [ ] Is there a rate limit on `submit_event` beyond the SDK's optional
      `rateLimitMaxEvents` / `rateLimitWindowSeconds`?
