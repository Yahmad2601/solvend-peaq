# Issues found in peaqOS

Found while taking SolVend from a fresh install to an activated,
revenue-reporting machine on peaq mainnet (6–9 Oct 2026). Each issue is
self-contained, with a reproduction and a suggested fix.

**Environment:** `peaq-os-cli 0.0.15 (peaq_os_sdk 0.11.0)`, Python 3.13.5,
Debian 13 (trixie) on a Raspberry Pi 4 (`aarch64`), installed with
`pip install 'peaq-os-cli[ows]'`. Network `peaq-mainnet` (chain 3338) unless
stated.

| # | Title | Kind |
|---|---|---|
| 1 | MCR API returns 403 (Cloudflare 1010) to Python's default User-Agent | Bug |
| 2 | Solana-settled revenue cannot be reported as on-chain verifiable | Feature gap |
| 3 | Python Tokenomics 2.0 surface is missing from the docs | Documentation |
| 4 | `--did-document`: `publicKeyMultibase` required by the CLI, "N/A for EVM" in docs | Docs / CLI mismatch |
| 5 | `peaqos activate --tier` help shows `ENTRY`, but only `entry` is accepted | CLI bug |
| 6 | `peaqos wallet create` silently uses `OWS_PASSPHRASE`; docs say it always prompts | Documentation |

---

## 1. MCR API returns 403 (Cloudflare 1010) to Python's default User-Agent

**What happens.** `GET https://mcr.peaq.xyz/mcr/{did}` succeeds from curl, but
the same URL requested with Python's standard library and its default
`Python-urllib/3.x` User-Agent gets `403` with body `error code: 1010`. That's
a Cloudflare browser-integrity block, not an API response.

**Reproduce** (any machine DID; ours is activated on mainnet):

```bash
D="did:peaq:8600820691859294852796023821329786994502637838982221572620760063908348418155"
curl -s -o /dev/null -w "%{http_code}\n" "https://mcr.peaq.xyz/mcr/$D"     # 200
python3 -c "import urllib.request; urllib.request.urlopen('https://mcr.peaq.xyz/mcr/$D')"
# urllib.error.HTTPError: HTTP Error 403: Forbidden   (body: "error code: 1010")
```

Setting any custom User-Agent (e.g. `SolVend-display/1.0`) returns 200.

**Why it matters.** The get-mcr page says the endpoint needs no API key, which
invites exactly this kind of lightweight client (a dashboard, a cron job, a
device). A 403 with no JSON body reads as an auth failure and sends people
looking in the wrong place. The SDK's `query_mcr` was unaffected in our test.

**Suggested fix.** Exempt `/mcr/*` from the Cloudflare browser-integrity check,
or document that a non-default User-Agent is required.

---

## 2. Solana-settled revenue cannot be reported as on-chain verifiable

**Context.** Our machine is peaq-homed, but its customers pay in USDC on
Solana. Every sale has a real, final Solana transaction.

**What happens.** `submit_event(..., trust_level=1, source_chain_id=…,
source_tx_hash=…)` cannot express that:

- `source_tx_hash` is `Hex32` (0x + 64 hex). A Solana signature is a 64-byte
  base58 string, so it does not fit.
- `source_chain_id` has no Solana value. The Events docs list `0`, `3338` and
  `8453`. The SDK's `SUPPORTED_CHAINS` is `{peaq: 3338, ethereum: 1, base:
  8453, polygon: 137, arbitrum: 42161, optimism: 10}`.

So the only honest option is `trust_level=0` (self-reported) with
`source_chain_id=0`, `source_tx_hash=None`, and the Solana signatures carried
in `raw_data`. The docs assistant confirmed that as the correct pattern.

**Why it matters.** peaqOS now supports Solana-*homed* machines, but a
peaq-homed machine that *earns* on Solana can't get the stronger trust level,
even though its revenue is fully verifiable on a public chain.

**Suggested fix.** A Solana source-chain identifier, plus a `source_tx_ref`
(or a variable-length field) that accepts a base58 signature at trust level 1.

---

## 3. Python Tokenomics 2.0 surface is missing from the docs

**What happens.** Activation in SDK 0.11.0 requires Tokenomics mode
(`PeaqosClient(..., tokenomics20=Tokenomics20Config(deployment_id=...))`,
`activate_machine(ActivateMachineParams(...))`, which raises
`TokenomicsConfigError` without it). When we asked the docs.peaq.xyz assistant
about `Tokenomics20Config`, `activate_machine`, `deployment_id` and
`DEPLOYMENT_UNAVAILABLE`, it answered that these "look like fabricated internal
identifiers" and "don't appear in any peaqOS docs". They are all real, public
names in `peaq_os_sdk` 0.11.0.

Two related facts that are only discoverable by reading the SDK source:

- `Tokenomics20DeploymentId = Literal["agung-2026-08-28", "peaq-mainnet",
  "peaq-mainnet-michael"]` (`tokenomics/deployments.py`).
- **Only `peaq-mainnet` has a `monetization` record** (`api_base=
  "https://mcr.peaq.xyz"`). `agung-2026-08-28` has none, so `query_mcr` on
  agung raises `TokenomicsConfigError` / `DEPLOYMENT_UNAVAILABLE`. In practice,
  **a testnet machine cannot get a Machine Credit Rating.** Builders who
  prototype on agung find this out late.

Also: the 17 Sep 2026 "peaqOS is live on Solana" video shows `peaqos init`
defaulting to deployment ID `solana-mainnet`, which is not a valid ID in SDK
0.11.0. The docs assistant says Solana-homed machines use `peaq-mainnet` with
`creation_home="solana"`.

**Suggested fix.** A Python reference page for `Tokenomics20Config`,
`ActivateMachineParams`, `activate_machine` and the deployment IDs, plus one
sentence on the agung/MCR limitation on the testnet and MCR pages.

---

## 4. `--did-document`: `publicKeyMultibase` required by the CLI, "N/A for EVM" in docs

**What happens.** `peaq_os_cli/commands/activation/did_input.py` requires
exactly `id`, `methodType`, `controller`, `publicKeyMultibase` on every
verification method (`_require_string(obj, "publicKeyMultibase", ...)`). For an
EVM (secp256k1) signer, the docs assistant first said `publicKeyMultibase` is
"N/A" for EVM wallets. It later cited the DID Operations pages, where the
field "always uses the account address" (e.g. `"0x9Eeab1…"`).

**Why it matters.** The value is written on-chain at activation. Three
plausible readings (omit it, a multicodec `z…` key, the 0x address) for a field
named *multibase* invite wrong permanent data.

**Suggested fix.** Add an EVM example of the `--did-document` file to the
activate page:

```json
{"verificationMethods": [{"id": "#key-1",
  "methodType": "EcdsaSecp256k1RecoveryMethod2020",
  "controller": "0x…", "publicKeyMultibase": "0x…"}],
 "authentication": [0], "serviceEndpoints": []}
```

and say explicitly that for EVM the field holds the account address.

---

## 5. `peaqos activate --tier` help shows `ENTRY`, but only `entry` is accepted

**Reproduce:**

```text
$ peaqos activate --help
  --tier [ENTRY|BASIC|PRO|0-7]   Subscription tier to activate: entry, basic or pro. ...
$ peaqos activate --machine-type VendingMachine --credential-subject-hex 0x… --tier ENTRY --dry-run --json
Error: Invalid value for '--tier': 'ENTRY' is not one of 'entry', 'basic', 'pro', or 0-7 with --chain solana.
```

**Suggested fix.** Make the choice case-insensitive (`click.Choice(...,
case_sensitive=False)`), or show lowercase in the help.

---

## 6. `peaqos wallet create` silently uses `OWS_PASSPHRASE`; docs say it always prompts

**Docs** (as summarised by the docs.peaq.xyz assistant from the CLI and Wallets
(OWS) pages): `wallet create` "prompts interactively for the vault passphrase
at creation time — it does not read `OWS_PASSPHRASE` for creation".

**Observed:**

```bash
export OWS_PASSPHRASE=…            # set for later SDK use
peaqos wallet create solvend --words 24
# "Wallet created." No prompt; the env var was used.

env -u OWS_PASSPHRASE peaqos wallet create scratch-test
# "Vault passphrase:" prompt, as documented
```

**Why it matters.** Mostly harmless, but someone who exported the variable for
an unrelated wallet will create a new wallet under that passphrase without
being asked. The behaviour is reasonable; the docs should match it.

**Suggested fix.** Document that `wallet create` uses `OWS_PASSPHRASE` when set
and prompts otherwise.

---

## Minor observations

- `peaq_os_sdk.__version__` is not defined. Only `peaqos --version` reports
  the SDK version.
- `peaqos whoami` prints `Network : unknown` for a correct mainnet config
  (`PEAQOS_RPC_URL` = quicknode1, chain 3338, `TOKENOMICS_DEPLOYMENT_ID=peaq-mainnet`).
- The `fund_from_gas_station` docstring example uses an SS58 `owner_address`
  (`5GrwvaEF…`). The guides use an EVM `0x` address.
- The CLI sends PostHog telemetry (`[PostHog] analytics lane flush ran out of
  budget…` on stderr). There's no documented opt-out.
- The Events docs list `sourceChainId` ∈ {0, 3338, 8453}, while
  `SUPPORTED_CHAINS` in the SDK has a different set (no `0`).
