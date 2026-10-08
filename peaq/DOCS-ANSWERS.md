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

**Resolved 8 Oct 2026:** in a fresh SSH session with no `OWS_PASSPHRASE`,
`peaqos wallet create scratch-test` **prompted** `Vault passphrase:` (then
deleted). So the CLI prompts when the variable is unset and **silently uses
`OWS_PASSPHRASE` when it is set**. `solvend` is protected with the passphrase
entered via `read -rsp`. The docs saying `create` ignores `OWS_PASSPHRASE` is a
**docs bug, file upstream**.

## MCR API URL — only `https://mcr.peaq.xyz` is documented

> "The docs only document `https://mcr.peaq.xyz` as the MCR API host — used
> both as the general example/default fallback and specifically as the mainnet
> (`peaq-mainnet`) deployment-record host. There's no separate agung-specific
> MCR URL documented… The docs don't state a distinct agung testnet MCR
> endpoint."

*Verified 8 Oct 2026.*

## `source_chain_id` for a Solana-settled event → `0`

> "Per Events, `sourceChainId` must be one of the supported values: `0`,
> `3338`, or `8453` — there's no Solana chain-ID entry. For a self-reported
> revenue event (`trustLevel = 0`) where payment settled on Solana, you'd use
> **`sourceChainId = 0`** (off-chain, since Solana isn't in the supported set),
> with **`sourceTxHash` left null** — self-reported events don't require
> `sourceTxHash` anyway (only mandatory at `trustLevel = 1`, and
> `trustLevel = 1` would require a chain ID actually present in the supported
> set, which Solana currently isn't)."

Note: the Events docs list `0 / 3338 / 8453`, but the installed SDK's
`SUPPORTED_CHAINS` also has 1, 137, 42161, 10, and no `0`. Small docs/SDK drift.

*Verified 8 Oct 2026. Used in: `peaq/machine.py` `peaq_submit_revenue`.*

## 🚨 agung deployment has no paired MCR

> "Per Monetize: Opt-in, `deployment_id` for the monetization/MCR config only
> accepts `"peaq-mainnet"` — **`"agung-2026-08-28"` raises
> `TokenomicsConfigError` `DEPLOYMENT_UNAVAILABLE` (no paired MCR there).**"

Not yet clear whether this blocks only the monetization opt-in, or activation
and credit scoring on agung too. If agung has no MCR, **a machine on agung
has no Machine Credit Rating**, and the credit display in scope needs mainnet.
Being checked against the installed SDK source and asked of @erti_peaq.

## `from_wallet` config kwargs (docs example, Python)

```python
client = PeaqosClient.from_wallet(
    "my-machine", passphrase="s3cret",
    rpc_url="https://peaq-rpc.example.com",
    identity_registry="0x...", identity_staking="0x...",
    event_registry="0x...", machine_nft="0x...",
    did_registry="0x0000000000000000000000000000000000000800",
    batch_precompile="0x0000000000000000000000000000000000000805",
)
```

> "The docs don't show a Python example passing
> `tokenomics20=Tokenomics20Config(deployment_id=...)` as a kwarg the way the JS
> client does (`tokenomics20: { deploymentId: "peaq-mainnet" }`)."

→ The Python kwarg name is **UNVERIFIED**. Read it from the installed
`PeaqosClient.__init__` / config class.

*Verified 8 Oct 2026.*

## Installed SDK source: deployments and MCR (read on the Pi, 8 Oct 2026)

From `inspect` and `grep` over `.peaq/lib/python3.13/site-packages/peaq_os_sdk`:

- `tokenomics/deployments.py:28`: `Tokenomics20DeploymentId =
  Literal["agung-2026-08-28", "peaq-mainnet", "peaq-mainnet-michael"]`.
  `peaq-mainnet-michael` is an `audience="internal"` record; don't use it.
- `agung-2026-08-28` → `chain_id=9990`, record source
  `agung-2026-08-28T15-20-37-404Z.md`. **It exists and activation is
  supported.**
- `peaq-mainnet` → `api_base="https://mcr.peaq.xyz"` (line 137). The grep for
  `mcr.peaq` matched **only** under `peaq-mainnet`.
- `query_mcr` docstring: raises `TokenomicsConfigError` "**If Tokenomics mode is
  selected but the deployment has no approved MCR endpoint.**"
  `query/_internal/mcr_base_url.py:44` raises `DEPLOYMENT_UNAVAILABLE`.
- ✅ **VERIFIED 8 Oct 2026: agung has no MCR.** Printed
  `TOKENOMICS_2_0_DEPLOYMENTS` (`deployments.py` lines 80–140). The
  `peaq-mainnet` record carries `monetization=Tokenomics20MonetizationDeployment(
  api_base="https://mcr.peaq.xyz", api_version="tokenomics-2.0-monetization-v1")`.
  The `agung-2026-08-28` record has **no `monetization` field at all**. Both
  are `status="available"`. Mainnet `event_start_block=11_446_416`. Contract
  addresses for both live in the SDK snapshot, so we never type them.
  → **A credit rating requires `peaq-mainnet`.** Decision: activate on mainnet.
- `PeaqosClient.__init__(*, rpc_url, private_key=None, identity_registry,
  identity_staking, event_registry, machine_nft, did_registry,
  batch_precompile, machine_account_factory=None, machine_nft_adapter=None,
  api_url='http://127.0.0.1:8000', operational_limits=None,
  orchestration_url=None, api_key=None, verbose=False,
  tokenomics20: Tokenomics20Config | None = None, _ows_account=None)`.
  **The Python kwarg is `tokenomics20=`.** The six legacy addresses have no
  default, so they are still required.
- `Tokenomics20Config(deployment_id: str, creation_home: Literal['peaq',
  'solana'] = 'peaq', solana_rpc_url=None)`. "Contract addresses are
  deliberately not accepted here. They come from the SDK's approved deployment
  snapshot." "Supplying this puts the client in **Tokenomics mode**, which
  enables activation and disables the integrations that cannot carry a
  Tokenomics 2.0 machine ID."
- `ActivateMachineParams(controller, verification_methods:
  tuple[VerificationMethodInput, ...], authentication: tuple[int, ...],
  service_endpoints: tuple[ServiceEndpointInput, ...], machine_type: str,
  credential_subject: bytes, manufacturer: Address, tier: SubscriptionTier,
  expected_machine_id=None, max_net_peaq_amount=None, confirmations=1,
  timeout_seconds=120.0, cancel=None, on_transaction_submitted=None)`.
  "The signer becomes the machine's owner and pays the bond."
  **"`machine_type` and the exact `credential_subject` bytes alone determine
  the permanent machine ID, so neither can change after activation."**
- `preview_machine_activation(params)` → `ActivationPreview`, "without signing
  or writing". `max_net_peaq_amount` caps what activation may spend.
- `fund_from_gas_station(owner_address, target_wallet_address, chain_id,
  two_factor_code, faucet_base_url, request_id=None)` → `FundedResponse`
  (`tx_hash`, `funded_amount`) or `SkippedResponse` (`current_balance`,
  `min_gas_balance`). `chain_id` defaults to `"peaq"`. Docstring example
  `owner_address="5GrwvaEF..."` is a Substrate SS58 address.
- `query_mcr(did)` → `MCRResponse` (`mcr_score`, `mcr`). In Tokenomics mode
  the DID is `did:peaq:` + the **base-10 machine ID**.
- There is also a read-only `PeaqosQueryClient(deployment_id="peaq-mainnet")`.

## Docs assistant answers, 8 Oct 2026

- **activate_machine on agung:** the assistant called `activate_machine`,
  `Tokenomics20Config`, `deployment_id` and `DEPLOYMENT_UNAVAILABLE`
  "fabricated identifiers" not in the docs. **All four exist in the installed
  SDK 0.11.0** (see above). So the docs don't cover the Python Tokenomics 2.0
  surface. That's a **docs gap, file upstream**. Treat the installed source as
  the authority for this.
- **`GET /mcr/{did}`:** the docs don't mention a mainnet/testnet restriction.
  The SDK source does gate it per deployment, as above.
- **Gas Station networks:** "funds peaq wallets only". `chain_id` is simply
  `"peaq"`, with no mainnet/agung distinction documented. Whether it funds
  mainnet is still unknown.
- **Mainnet:** EVM RPC `https://quicknode1.peaq.xyz` (fallbacks
  `quicknode2/3.peaq.xyz`, `https://peaq.api.onfinality.io/public`,
  `https://peaq-rpc.publicnode.com`), chain ID **3338**. Entry bond **$0.02
  per 365-day period**, paid in PEAQ at the oracle rate at activation time.

## Getting PEAQ on mainnet (8 Oct 2026)

> "Gas Station: Yes, it funds machine wallets on peaq chain generally — 'Gas
> Station funds peaq wallets only,' with `chainId: "peaq"`… No explicit
> mainnet-only restriction is called out."
> "Standard wallet transfer: since peaq is EVM-compatible, any 0x address can
> simply receive PEAQ sent from another EVM wallet/exchange." Also Substrate →
> EVM via the Address Converter (EVM Token Transfer page).
> "For machine wallets specifically, Gas Station is the supported bootstrap
> mechanism."

→ Plan: try the Gas Station on mainnet first (it fires inside a real
activation). Buying PEAQ is the fallback.

## USDT activation: not usable on mainnet

> "`activate_machine_with_usdt` and `preview_machine_activation_with_usdt`
> settle the activation bond in USDT through the
> `SubscriptionTokenProvisionPool`… However, per SDK: Python: **this is not
> usable on peaq mainnet** — the pool has no USDT token configured there, so
> both the USDT quote and the write call revert… on mainnet, you still need
> PEAQ."

→ The 4 USDC on Solana doesn't help directly.

## Tokenomics 1.0 addresses, peaq mainnet

The docs assistant returned all four (IdentityRegistry, IdentityStaking,
EventRegistry, MachineNFT) with their env var names, from the **peaqOS Smart
Contracts** page. **Deliberately not transcribed here from a screenshot.** Copy
them from that page straight into the Pi's env file, then check each one with
`eth_getCode` (it must be non-empty) before use.

## @erti_peaq: can't DM

Telegram blocks DMs to @erti_peaq without Premium (8 Oct 2026). Reach them
another way (see SCORING.md questions).

## Gas Station owner = the machine wallet itself

> "The real docs example uses `owner_address="0xOwner..."`, an EVM-style
> address, not an SS58 Substrate address… the examples use `client.address`…
> There's no documented requirement that `owner_address` be a separate
> Substrate account; it can be the same address used elsewhere by the client,
> including a machine wallet's own EVM address, as long as it's 2FA-enrolled
> via `setup_faucet_2fa` / `confirm_faucet_2fa`."

→ The `solvend` wallet enrolls itself. (The SS58 in the SDK docstring is just
an old example. Minor docs inconsistency.)

*Verified 8 Oct 2026.*

## CLI surface, `peaqos --help` / `activate --help` (CLI 0.0.15, on the Pi)

Commands: `activate`, `init` ("Write a .env configuration file"), `machine`,
`monetize` ("machine monetisation through the MCR"), `qualify` ("Qualify
machine data for credit rating and verification"), `scale`, `show`, `stream`,
`verify`, `wallet`, `whoami` ("Show the active wallet identity and loaded
configuration").

**No global network/RPC flag.** The network comes from config/env.
`PEAQOS_OWS_WALLET` selects the default OWS wallet.

`peaqos activate` (EVM/peaq path):
- `--machine-type TEXT`: "Identity domain for the machine."
- `--credential-subject-hex TEXT`: "0x-prefixed identity-anchor bytes. Together
  with `--machine-type` these fix the permanent machine ID and cannot be
  changed afterwards."
- `--manufacturer TEXT`: "EVM hex or Solana public key (recorded, never verified)."
- `--tier [ENTRY|BASIC|PRO|0-7]`
- `--did-document TEXT`: path to UTF-8 JSON with `verificationMethods`,
  `authentication`, `serviceEndpoints`.
- `--for` / `--machine-key`: machine-key mode (the machine EOA signs from a raw
  key file). **Not used**: our signer is already the machine's own OWS wallet.
- `--skip-funding`: skip balance check, 2FA enrollment and Gas Station.
- `--payment [peaq|usdt]` (default `peaq`). `--slippage-bps` is rejected for PEAQ.
- `--dry-run` ("Preview only; submit nothing"), `--json`, `-y/--yes`.
- Everything else (`--chain solana`, `--phase`, `--solana-owner`,
  `--operator-wallet`, `--pay-in`, lamport ceilings…) is Solana-home only.
  Interesting detail: Solana operator registration costs "about 0.01 PEAQ".

*Verified from `--help` on the Pi, 8 Oct 2026.*

`peaqos init`: interactive by default ("prompts for network and private key
source (paste, generate, or create an OWS wallet), then connection URLs,
orchestration settings, and the EventRegistry contract address. Writes a
`.env` file in the current directory and runs `whoami` to verify"). Choosing
`wallet` writes `PEAQOS_OWS_WALLET` instead of `PEAQOS_PRIVATE_KEY`.
`--non-interactive` reads env vars, "falling back to network defaults where
available". `--force` overwrites. **There's no "use existing wallet" option**,
so we write `.env` by hand rather than risk a second wallet.

`peaqos whoami` with `PEAQOS_OWS_WALLET=solvend` and no `.env`: prompted
"Vault passphrase for wallet 'solvend':", then `Error: Missing required env
var: PEAQOS_RPC_URL`. So the CLI reads `PEAQOS_OWS_WALLET` and needs
`PEAQOS_RPC_URL` from env or `./.env`.

*Verified on the Pi, 8 Oct 2026.*

## Mainnet config: verified on the Pi (8 Oct 2026)

The `.env` was written by heredoc, and the four Tokenomics 1.0 addresses were
pasted from the peaqOS Smart Contracts page. Checked with `eth_getCode` against
`https://quicknode1.peaq.xyz`: `eth_chainId` = **3338**. IdentityRegistry,
IdentityStaking, EventRegistry and MachineNFT each have **170 code bytes**
(the same size for all four, consistent with proxies). The DID (`0x…0800`) and
batch (`0x…0805`) precompiles return 0 bytes, as expected for precompiles.

`peaqos whoami` loads it: address `0x6090…2996`, chain 3338, MCR API
`https://mcr.peaq.xyz`, Tokenomics 2.0 deployment `peaq-mainnet` (InfoDesk
`0x6C74…6A82`, …), "resolved from the SDK's deployment record, not from your
.env… **verified against InfoDesk on-chain before any write**."
`Network : unknown`: probably cosmetic, watch it in the dry run.

**The CLI sends telemetry.** whoami printed `[PostHog] analytics lane flush ran
out of budget`. UNVERIFIED: what it sends and how to opt out.

## First mainnet dry run (8 Oct 2026)

```
peaqos activate --machine-type VendingMachine --credential-subject-hex "$CS" \
  --tier entry --manufacturer "$MFR" --did-document peaq/did-document.json \
  --dry-run --json
```

- `--tier` must be **lowercase**. `--help` shows `[ENTRY|BASIC|PRO|0-7]`, but
  `ENTRY` is rejected: "'ENTRY' is not one of 'entry', 'basic', 'pro'".
  **CLI help/validator mismatch, file upstream.**
- `--manufacturer` and `--did-document` are **required** for EVM activation.
- A DID document of `{"verificationMethods": [], "authentication": [],
  "serviceEndpoints": []}` passes validation.
- Steps shown: `[1/4] Compute machine identity`, `[2/4] Reconcile previous
  submissions`, `[3/4] Quote the activation`. Result: `status: error`,
  `error_code: INSUFFICIENT_PEAQ`, `mode: self-owned`, owner = controller =
  manufacturer = `0x6090…2996`, `peaq_token` = the `0x…0809` precompile,
  `voucher_credit: 0`, `approval_required: true`.
- **Bond 0.4891 PEAQ + 0.0500 PEAQ gas headroom = 0.5391 PEAQ needed.** That's
  Entry tier at $0.02/yr, so PEAQ ≈ $0.04 at quote time.
- `machine_id` is a 76-digit decimal. **Not transcribed here.** The authoritative
  copy is `peaq/activation-preview.json`, saved straight from the CLI.

## DID document schema (installed SDK + docs, 8 Oct 2026)

- `VerificationMethodInput(id, method_type, controller, public_key_multibase)`,
  e.g. `id="#key-1"`. "`controller`: Entity controlling this key. May differ
  from the DID document's own controller."
- `ServiceEndpointInput(id: str, service_type: str, service_endpoint: str)`,
  e.g. `id="#telemetry"`, `service_type="TelemetryService"`.
- CLI parser: `peaq_os_cli/commands/activation/did_input.py`.
- Docs assistant, JSON file keys: verificationMethods entries `id`,
  `methodType`, `controller`, `publicKeyMultibase`. serviceEndpoints entries
  `id`, `serviceType`, `serviceEndpoint`. "`authentication`: a list of integer
  indexes into the `verificationMethods` array".
- Docs assistant, EVM signer: "`EcdsaSecp256k1RecoveryMethod2020` is the
  required type for EVM wallets… for EVM, the verification method uses the
  account address itself… `publicKeyMultibase` is 'N/A' for EVM." The SDK
  dataclass still has a `public_key_multibase` field, so whether the CLI
  accepts it missing is UNVERIFIED until `did_input.py` is read.
- Verification methods and service endpoints are **editable after
  activation** (`set_machine_verification_methods`,
  `set_machine_service_endpoints`). Only `machine_type` + `credential_subject`
  are permanent.

## Gas Station covers gas only, not the bond

> "Only gas, not the bond. Per Onboarding Quickstart: 'Copy the `0x…` address
> and send PEAQ to it: **the bond plus at least 0.5 PEAQ**. Below 0.5 PEAQ a
> real `peaqos activate` run stops to fund the wallet for you through the Gas
> Station… Staying above 0.5 PEAQ avoids it.'" "The bond itself must be sent
> to the wallet separately before activation; if it's missing, activation
> fails with `INSUFFICIENT_PEAQ`."

→ **We have to acquire PEAQ.** Target: bond (~0.49) + 0.5 buffer + headroom
for daily `submit_event` gas ≈ **1.5–2 PEAQ** (about $0.06–0.08 at quote).

*Verified 8 Oct 2026.*

## CLI DID parser (`peaq_os_cli/commands/activation/did_input.py`, read on the Pi)

- Root: exactly `verificationMethods`, `authentication`, `serviceEndpoints`.
  "All three required, nothing else permitted." `id` and `controller` at the
  root are **explicitly rejected**. The CLI sets the controller from the
  activation mode (self-owned → the signer).
- Each verification method needs exactly `id`, `methodType`, `controller` (must
  match a 0x 40-hex EVM address), and **`publicKeyMultibase` (required
  string)**. So the docs' "publicKeyMultibase is N/A for EVM" does not match
  the CLI. **Docs/CLI mismatch, file upstream.**
- Each service endpoint needs exactly `id`, `serviceType`, `serviceEndpoint`,
  non-empty on the EVM path.
- `authentication` entries must be JSON integers in range. If
  `verificationMethods` is empty, `authentication` must be empty too.
- Duplicate JSON keys are rejected, so a repeat can't silently pick what goes
  on-chain.

→ Decision: activate with **no verification method** and one service
endpoint (`#source` → the GitHub repo). Add a proper secp256k1 key later with
`set_machine_verification_methods` once its `publicKeyMultibase` encoding is
verified. That's editable, so it doesn't block activation.

## EVM verification method: `publicKeyMultibase` = the 0x address

> "methodType: `EcdsaSecp256k1RecoveryMethod2020` — correct.
> publicKeyMultibase: for EVM, the docs explicitly say this field '**always uses
> the account address**' — not a multicodec-encoded compressed public key. The
> example shows `"publicKeyMultibase": "0x9Eeab1…"` (the raw 0x address)… The
> `z…` format only appears in Substrate examples." Source: DID Operations (JS),
> DID Operations (Python).

→ **Supersedes the "activate with no verification method" decision above.**
The DID document now carries `#key-1` (`EcdsaSecp256k1RecoveryMethod2020`,
controller and publicKeyMultibase = the machine address) with
`authentication: [0]`. It's generated on the Pi from `wallet show`, never
typed. Caveat: the source pages describe the legacy DID precompile; this is
editable after activation if Tokenomics 2.0 expects otherwise.

*Verified 8 Oct 2026.*

## Getting PEAQ: what the docs say

Two documented paths: a standard EVM transfer from a wallet holding PEAQ on
peaq (paste the `0x` address, send), or Substrate → EVM via the Address
Converter. A PEAQ OFT exists on Solana, but "the docs don't detail a
Solana→peaq-EVM bridge path." **The docs list no exchanges** that withdraw on
the peaq EVM network. PEAQ itself is the native token, exposed at the `0x…0809`
precompile.

*Verified 8 Oct 2026.*

## Second dry run (8 Oct 2026)

Output saved to `peaq/activation-preview.json`. `machine_id`
`8600820691859294852796023821329786994502637838982221572620760063908348418155`
(copied from CLI text output, matches the file). `net_peaq_amount`
`492112543185951367` wei = **0.4921 PEAQ**. The bond moves with the PEAQ price
(was 0.4891 an hour earlier).

## Still to ask

- [ ] For an EVM (secp256k1) verification method in a peaqOS DID document, what
      exact `methodType` and `publicKeyMultibase` encoding does the CLI expect,
      given `did_input.py` requires `publicKeyMultibase` as a string?
- [ ] Supported route to move PEAQ from Solana (the PEAQ OFT) or an exchange to
      a peaq mainnet EVM `0x` address.
- [ ] What does the peaqOS CLI/SDK send to PostHog, and which env var disables
      it? (Seen in `peaqos whoami`, CLI 0.0.15.)
- [ ] `peaqos whoami` shows `Network : unknown` with `PEAQOS_RPC_URL` set to
      mainnet. Which env var sets it, and does activation or the Gas Station
      depend on it?
- [ ] Is `--did-document` required for an EVM activation, or does the CLI
      default to empty `verificationMethods` / `authentication` /
      `serviceEndpoints`? (The dry run will show this.)

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
