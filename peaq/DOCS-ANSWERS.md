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

## Solana support — paused *(SUPERSEDED for CLI 0.0.15 / SDK 0.11.0 — see below)*

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

## ⚠ Installed version is newer than the docs answers

`pip install 'peaq-os-cli[ows]'` on the Pi (7 Oct 2026) installed
**`peaq-os-cli 0.0.15 (peaq_os_sdk 0.11.0)`**. Every answer above that names a
version was given for **CLI 0.0.14 / SDK 0.10.0**. Re-check signatures against
the installed package (`help(...)`), and re-ask the Solana-pause question for
0.0.15 / 0.11.0 before relying on it either way.

Install facts (verified on the Pi): all native deps arrived as prebuilt
`cp313 manylinux aarch64` wheels — nothing compiled. `time`: real 5m0s,
user 0m40s (the time was download, not build). The CLI pulls in
`peaq_os_sdk`, `web3 8.0.0`, `eth-account 0.14.0`, `open-wallet-standard
1.4.2` and `python-dotenv` as dependencies.

## Client construction — `from_env` vs `from_wallet`

> "`PeaqosClient.from_env()` only reads the raw `PEAQOS_PRIVATE_KEY` env var —
> it does **not** read from the OWS vault (`~/.ows/wallets/`). For vault-backed
> wallets, use **`PeaqosClient.from_wallet()`** instead (Python equivalent of
> JS's `fromWallet`), which loads a wallet by name/passphrase and signs through
> OWS directly — no raw key export needed."
>
> "If you specifically need the raw key exported, the command is
> `peaqos wallet export <name-or-id>`. This reveals the recovery phrase/private
> key after interactive confirmation (prints to stdout)."

*Verified 7 Oct 2026 (asked about SDK 0.10.0). Used in: `peaq/machine.py` `_client()`.*

## Gas Station 2FA — TOTP, works over SSH

> "It's **TOTP** (authenticator app), not email: enrollment calls
> `setupFaucet2FA` to get an `otpauthUri`/QR code, which you scan or manually
> enter into any TOTP-compatible app (Google Authenticator, Authy, 1Password),
> then confirm with the generated 6-digit code via `confirmFaucet2FA`."
>
> "This works fine over SSH on a headless device — since `otpauthUri` is just a
> text URI (not a QR-only flow), you can manually enter it into an
> authenticator app running on another device, then paste the resulting TOTP
> code back into your SSH session."

→ Have an authenticator app on your phone ready before Stage 6.

*Verified 7 Oct 2026.*

## `--dry-run` does not fund

> "Funding only happens on a real activation, not during `--dry-run`. The
> dry-run path uses `previewMachineActivation` to show the bond cost and gas
> estimate without triggering `fundFromGasStation` or any 2FA enrollment —
> those only fire when the actual signing/activation transaction detects an
> under-funded wallet."

→ Running `--dry-run` first is safe and free.

*Verified 7 Oct 2026.*

## `from_wallet()` passphrase — `OWS_PASSPHRASE`, never prompts

> "`PeaqosClient.from_wallet()` can take the passphrase as an explicit
> `passphrase` argument, or it falls back to the **`OWS_PASSPHRASE`**
> environment variable if omitted."
>
> Docs (Wallets (OWS)): "Passphrase handling. Sourced from the explicit
> argument or the `OWS_PASSPHRASE` env var; if neither is set, the SDK raises
> `PeaqosError` rather than prompting. Never stored on disk."

→ Under systemd: put `OWS_PASSPHRASE` in the service's `EnvironmentFile=`
(`/etc/solvend/env`, chmod 600), omit the `passphrase` kwarg. A missing
passphrase fails loudly with `PeaqosError` — it cannot hang a daemon.

*Verified 7 Oct 2026, asked about SDK 0.11.0. Used in: `peaq/machine.py` `_client()`.*

## Solana onboarding — no longer paused, but mainnet only

> "No — Solana onboarding is **not** paused as of CLI 0.0.15 / SDK 0.11.0 (SDK
> 0.10.0's pause was tied to an earlier build). Requires
> `pip install -U 'peaq-os-cli[solana,ows]'` (CLI ≥0.0.15) and Python SDK
> ≥0.11.0. Note it's **mainnet only** — there's no Solana testnet, so a
> dry-run preview is the only rehearsal before a real bond settlement."

→ **Supersedes the "Solana support — paused" section above.** Decision stands
anyway for the hackathon: home the machine on **agung**. Solana homing means a
real mainnet bond with no rehearsal, and expands locked scope. Write it up as
direction (it is the natural home for a Solana-settled machine).

*Verified 7 Oct 2026.*

## CLI wallet surface (verified from `--help` on the Pi, CLI 0.0.15)

`peaqos wallet` subcommands: `create`, `delete`, `export`, `import`, `list`,
`show`, `use`.
`peaqos wallet create [OPTIONS] NAME` — options are only `--words [12|24]`,
`--json`. **There is no passphrase flag.** "The mnemonic is not displayed; use
`peaqos wallet export` to retrieve it."

## Installed SDK surface (verified by `inspect` on the Pi, SDK 0.11.0)

Not a docs answer: read straight off the installed package, 7 Oct 2026.

- `peaq_os_sdk.__version__` does not exist. Use `peaqos --version`.
- `EVENT_TYPE_REVENUE = 0`, `TRUST_SELF_REPORTED = 0`.
- `SUPPORTED_CHAINS = {'peaq': 3338, 'ethereum': 1, 'base': 8453,
  'polygon': 137, 'arbitrum': 42161, 'optimism': 10}`. **No Solana, no agung.**
- `from_wallet(name_or_id, passphrase=None, ows_signing=True,
  vault_path=None, **config_kwargs)`. Docstring: "Passphrase is **not**
  verified at construction." With `ows_signing=True` the SDK never holds the
  raw key.
- `from_env()` requires `PEAQOS_RPC_URL`, `PEAQOS_PRIVATE_KEY`, and the six
  contract addresses. Optional: **`PEAQOS_MCR_API_URL` (defaults to
  `http://127.0.0.1:8000`)**, `PEAQOS_ORCHESTRATION_URL`, `PEAQOS_API_KEY`,
  `MACHINE_ACCOUNT_FACTORY_ADDRESS`, `MACHINE_NFT_ADAPTER_ADDRESS`,
  `TOKENOMICS_DEPLOYMENT_ID` ("omitted or empty leaves the client in legacy
  mode").
- `activate_machine(params: ActivateMachineParams | ActivateSolanaMachineParams
  | ActivateSolanaTerminalParams)`. Raises `TokenomicsConfigError` with no
  `tokenomics20`, `ValidationError` before any RPC, `TokenomicsActivationError`
  on preflight/approval/revert.
- `submit_event(*, machine_id: int, event_type: int, value: int, timestamp:
  int, raw_data: bytes|None, trust_level: int, source_chain_id: int,
  source_tx_hash: Hex32|None, metadata: bytes, currency: str|None)` →
  `tuple[str, bytes]`. "BREAKING (PRO-334): `value` is an ISO 4217 subunit
  integer… `float` / `Decimal` / `bool` / `str` / `None` raise `TypeError`."
- Relevant public methods: `setup_faucet_2fa`, `confirm_faucet_2fa`,
  `fund_from_gas_station`, `preview_machine_activation`, `activate_machine`,
  `compute_machine_id`, `get_machine_activation_state`, `submit_event`,
  `batch_submit_events`, `query_mcr`, `query_machine`, `list_wallets`,
  `get_wallet`.

## Machine wallet (created on the Pi, 7 Oct 2026)

`peaqos wallet create solvend --words 24` →
ID `f84d08c7-15a4-4567-9b44-40c0924ee495`, vault `~/.ows/wallets/f84d08c7.json`.
EVM address (peaq 3338 and every EVM chain):
`0x60901F3fC014Eb097411720f55f247a5E6652996`.

## ⚠ Docs vs. observed: `wallet create` did NOT prompt

> Docs assistant: "`peaqos wallet create` prompts **interactively** for the
> vault passphrase at creation time — it does not read `OWS_PASSPHRASE` for
> creation… and it does not create an unprotected/no-passphrase wallet."

**Observed on the Pi:** with `OWS_PASSPHRASE` exported, `peaqos wallet create
solvend --words 24` printed "Wallet created." with **no prompt**. So either the
CLI read `OWS_PASSPHRASE` (docs wrong) or it created the wallet without a
passphrase. Being tested; if it's the env var, it's a docs bug to file upstream.

## Still to ask

- [ ] What is `PEAQOS_MCR_API_URL` for agung? (SDK default is
      `http://127.0.0.1:8000`, so `query_mcr` fails without it.)
- [ ] What `source_chain_id` should a self-reported revenue event carry when
      the payment settled on Solana? (`SUPPORTED_CHAINS` has no Solana.)
- [ ] How is `Tokenomics20Config(deployment_id=...)` passed to
      `PeaqosClient.from_wallet(**config_kwargs)`, and which `config_kwargs`
      are required (rpc_url, contract addresses)?

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
