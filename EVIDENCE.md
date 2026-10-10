# Evidence

Every claim made in the [README](README.md), mapped to an artifact that can be
checked independently: an on-chain transaction, a public API response, a log,
or a screenshot in [`evidence/`](evidence/).

## Summary

| # | Claim | Evidence | Status |
|---|---|---|---|
| 1 | SolVend runs on real hardware | Device model and OS from the Pi ([`01`](evidence/01-pi-hardware.png)) | ✅ |
| 2 | The machine has a peaq identity on mainnet | [Activation transaction](https://peaq.subscan.io/tx/0xdeab1fed124579378f9558e55861772729ec37ac4b99841cd65e53865ed50b77), DID, identity NFT ([`12`](evidence/12-activation-subscan.png)) | ✅ |
| 3 | Customers pay real USDC on Solana mainnet | [First sale on Solscan](https://solscan.io/tx/ZF3QEkkNcRV6tVU1c1pV3pTdr4CGmdj5td4x7xeTiS4XuNEYWendSKAo7FTry5tQygMw6FAc6Phwke9eUfoGNyi), merchant +1.00 USDC | ✅ |
| 4 | No model in the purchase path | Button ordering, deterministic invoice and pay link ([`20`](evidence/20-telegram-buttons.jpg)–[`24`](evidence/24-telegram-code.jpg)) | ✅ |
| 5 | The peaq SDK runs on the device, unattended | `client ok` from a stripped scheduler-like environment ([`13`](evidence/13-spike-client-ok.png)) | ✅ |
| 6 | Revenue events are reported automatically | First daily revenue event on peaq | Pending (sales day) |
| 7 | The Machine Credit Rating responds to revenue | Rating before and after the first event | Before ✅ · After pending |
| 8 | Reporting never double-counts | `--sync` run twice, second reports 0; covered by tests | ✅ tests · live run pending |
| 9 | The test suites pass | 125 tests across four suites | ✅ |
| 10 | Issues found in peaqOS are documented | [`peaq/UPSTREAM-ISSUES.md`](peaq/UPSTREAM-ISSUES.md) | ✅ documented |

---

## 1. Hardware

Captured on the machine's Raspberry Pi, 7 Oct 2026.

```
$ cat /proc/device-tree/model
Raspberry Pi 4 Model B Rev 1.5
$ uname -m
aarch64
$ grep PRETTY_NAME /etc/os-release
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
$ python3 --version
Python 3.13.5
```

Screenshot: [`01-pi-hardware.png`](evidence/01-pi-hardware.png)

## 2. peaqOS on the device

The peaqOS CLI and Python SDK run directly on the Pi. All native dependencies
install as prebuilt `aarch64` wheels; nothing compiles.

```
$ peaqos --version
peaq-os-cli 0.0.15 (peaq_os_sdk 0.11.0)
```

The machine's wallet was generated on the Pi into an encrypted OWS vault
(`peaqos wallet create`). Its key has never existed anywhere else.

- Owner address: `0x60901F3fC014Eb097411720f55f247a5E6652996`
- Screenshots: [`03-peaqos-version.png`](evidence/03-peaqos-version.png),
  [`04-sdk-import-ok.png`](evidence/04-sdk-import-ok.png),
  [`05-wallet-created.png`](evidence/05-wallet-created.png)

SolVend's own reporting code builds a signing client against peaq mainnet, both
interactively and from a stripped environment that mirrors the scheduler (no
TTY, minimal `PATH`):

```
$ env -i HOME=/home/pi PATH=/usr/bin:/bin sh -c '… machine.py --spike </dev/null'
  "address": "0x60901F3fC014Eb097411720f55f247a5E6652996",
  "chain_id": 3338,
  "sdk": "client ok"
```

Screenshot: [`13-spike-client-ok.png`](evidence/13-spike-client-ok.png)

## 3. Machine identity on peaq mainnet

Activated 8 Oct 2026 on the `peaq-mainnet` Economics 2.0 deployment.

| | |
|---|---|
| DID | `did:peaq:8600820691859294852796023821329786994502637838982221572620760063908348418155` |
| Activation tx | [`0xdeab1fed…ed50b77`](https://peaq.subscan.io/tx/0xdeab1fed124579378f9558e55861772729ec37ac4b99841cd65e53865ed50b77) (Confirmed, Success) |
| Bond | 0.495 PEAQ to MachineSubscription `0x9e37…c43895` (Entry tier, $0.02/yr) |
| Identity NFT | MREG `860082…418155`, minted to the machine's own wallet |
| Subscription period | 1791474378 → 1823010378 (365 days) |
| Machine type | `VendingMachine`, self-owned, homed on peaq |

The machine ID is derived from the machine type and a credential subject that
includes a SHA-256 hash of the Pi's hardware serial
([`peaq/credential-subject.json`](peaq/credential-subject.json)). The DID
document ([`peaq/did-document.json`](peaq/did-document.json)) carries the
machine's `EcdsaSecp256k1RecoveryMethod2020` key and a link to this repository.

- Full activation session, recorded with `script`:
  [`peaq/activation-log.txt`](peaq/activation-log.txt)
- Pre-activation preview: [`peaq/activation-preview.json`](peaq/activation-preview.json)
- Contracts checked on chain 3338 before use:
  [`06-mainnet-contracts-verified.png`](evidence/06-mainnet-contracts-verified.png)
- CLI configured for `peaq-mainnet`: [`07-whoami-mainnet.png`](evidence/07-whoami-mainnet.png)
- Bond quote (dry run): [`08-dry-run-insufficient-peaq.png`](evidence/08-dry-run-insufficient-peaq.png)
- Funding: 20 PEAQ bridged Solana → peaq with Stargate, the route named in
  peaq's DeFi guide ([`09-stargate-bridge.png`](evidence/09-stargate-bridge.png),
  [`10-balance-19996-peaq.png`](evidence/10-balance-19996-peaq.png))
- Activation: [`11-activation-cli.png`](evidence/11-activation-cli.png),
  [`12-activation-subscan.png`](evidence/12-activation-subscan.png)

## 4. First mainnet sale

INV-0027, water, 1.00 USDC, 9 Oct 2026 22:09 UTC.

1. The customer taps **Water** in the shop bot
   ([`20-telegram-buttons.jpg`](evidence/20-telegram-buttons.jpg)).
2. The bot creates the invoice and replies with **Pay with Phantom / Pay with
   Solflare**. The checkout page opens inside the wallet
   ([`21-paypage-in-phantom.jpg`](evidence/21-paypage-in-phantom.jpg)).
3. The customer approves −1 USDC in Phantom
   ([`22-phantom-confirm.jpg`](evidence/22-phantom-confirm.jpg),
   [`23-paypage-sent.jpg`](evidence/23-paypage-sent.jpg)).
4. Within a minute the poller verifies the payment on-chain and delivers code
   `7436` to the chat ([`24-telegram-code.jpg`](evidence/24-telegram-code.jpg)).
5. The serial bridge accepts the code and commands the dispense:

   ```
   INFO DISPENSE drink-1 invoice=INV-0027 item=water
   INFO gantry completed drink-1
   ```

   This dispense was executed against a virtual serial port standing in for the
   ESP32; on the assembled machine the same `DISPENSE:drink-1` command drives
   the gantry.

**On-chain verification** of the payment
([Solscan](https://solscan.io/tx/ZF3QEkkNcRV6tVU1c1pV3pTdr4CGmdj5td4x7xeTiS4XuNEYWendSKAo7FTry5tQygMw6FAc6Phwke9eUfoGNyi)),
via `getTransaction`:

| | |
|---|---|
| Status | Success, block time 2026-10-09T22:09:16Z |
| Merchant `4QBm…P8yP` | +1.00 USDC, mainnet mint `EPjF…Dt1v` |
| Payer | `2MML…uBwr` (not the merchant) |

After the sale, the machine display shows 1 can and $1.00 revenue, awaiting the
daily threshold ([`26-display-provisioned-1-can.png`](evidence/26-display-provisioned-1-can.png)).
Sales are counted from 2026-10-08 20:34 UTC (`PEAQ_REPORT_FROM`); earlier ledger
entries are pre-production test data and are excluded from reporting and display.

## 5. Machine Credit Rating

Read from the public endpoint `GET https://mcr.peaq.xyz/mcr/{did}`.

| | Rating | Score | Bond | Revenue events | Trend |
|---|---|---|---|---|---|
| After activation (8 Oct) | Provisioned | 0 | bonded | 0 | insufficient |
| After first revenue event | *pending* | | | | |

## 6. Revenue events

One event per UTC day once that day's sales reach $10, the minimum the credit
rating counts.

| UTC day | Sales | Revenue | peaq transaction |
|---|---|---|---|
| *pending* | | | |

## 7. Tests

Run 10 Oct 2026 (Python 3.12):

| Suite | Covers | Result |
|---|---|---|
| `solvend/test_solvend.py` | Payment verification, anti-spoofing, single-use codes, expiry, refunds | 55 passed |
| `solvend/test_shop_bot.py` | Button ordering, catalogue pricing, pay links, pay-page integrity | 25 passed |
| `peaq/test_machine.py` | Cents conversion, daily threshold, idempotency, event fields | 24 passed |
| `tools/test_machine_display.py` | Ledger reads, credit rating, rendering, HTTP | 21 passed |

The checkout page's transaction builder is additionally verified against the
pinned `@solana/web3.js` build: it derives the merchant's real on-chain USDC
account and attaches the invoice reference as a read-only key.

## 8. Issues found in peaqOS

Six issues found during integration, written up for the peaq team in
[`peaq/UPSTREAM-ISSUES.md`](peaq/UPSTREAM-ISSUES.md).
