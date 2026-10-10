# Evidence ledger

Fill this the day something works, not at the deadline. The last bounty was lost
on evidence, not engineering — the machine did more than the repo could prove.

**Rule: if it isn't captured here, a judge cannot score it.**

---

## Core claims

| # | Claim | Evidence needed | Captured |
|---|---|---|---|
| 1 | It is real hardware, not a simulation | `cat /proc/device-tree/model` output + photo/video of the machine | ☐ |
| 2 | The machine has a peaq identity | DID string + explorer link to the `activateMachine` tx | ☑ 8 Oct · [`12-activation-subscan.png`](evidence/12-activation-subscan.png) |
| 3 | Revenue events are real sales | ≥3 settlements, each with an explorer link, matched to its ledger row | ☐ |
| 4 | The credit rating moves | Before/after screenshots of the score with timestamps | ☐ |
| 5 | Reporting is autonomous | Log excerpt: settlement → `submitEvent` with no human action between | ☐ |
| 6 | No model in the money path | Show the event firing while the agent is stopped | ☐ |
| 7 | Nothing double-counts | Run `--sync` twice; second run reports 0 submitted | ☐ |
| 8 | Tests pass | `python3 solvend/test_solvend.py` output, pasted with the count | ☑ 10 Oct: solvend 55/0 · shop_bot 25/0 · machine 24/0 · display 21/0 (laptop, Python 3.12). On the Pi (Python 3.13) earlier versions passed (50 / 22 / 20); current versions not yet re-run there |
| 9 | A stranger could run it | Quickstart you have actually followed on a clean machine | ☐ |
| 10 | Bugs found in peaq | Links to filed issues | ☐ |

Claim 6 is the quiet one that sells the architecture: the revenue path survives a
dead model provider. Worth ten seconds of video.

Claim 7 is the one a technical judge will probe. Have the terminal output ready.

---

## Captured artifacts

Paste links, hashes and paths as you get them.

**Hardware** (claim 1, captured 7 Oct 2026 over SSH to `pi@solvend`)
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
Still needed for claim 1: photo/video of the machine.

**peaqOS on the device** (captured 7 Oct 2026, inside `~/solvend-peaq/.peaq` venv)
```
$ peaqos --version
peaq-os-cli 0.0.15 (peaq_os_sdk 0.11.0)
```
All native deps installed as prebuilt `aarch64` wheels; no compilation.
Screenshots: [`03-peaqos-version.png`](evidence/03-peaqos-version.png) (install + version), [`04-sdk-import-ok.png`](evidence/04-sdk-import-ok.png) (SDK import + real signatures), [`05-wallet-created.png`](evidence/05-wallet-created.png) (machine wallet generated on the Pi)

**SolVend's own code drives the SDK on the device** (8 Oct 2026, Pi, SDK 0.11.0)
```
$ python3 peaq/machine.py --spike
  "address": "0x60901F3fC014Eb097411720f55f247a5E6652996",
  "chain_id": 3338,
  "sdk": "client ok"
```
Tests on the Pi (Python 3.13): `peaq/test_machine.py` 22 passed, 0 failed ·
`solvend/test_solvend.py` 50 passed, 0 failed.

**Machine identity: preview (dry run, 8 Oct 2026, peaq mainnet)**
- machine_type `VendingMachine`, credential subject `peaq/credential-subject.json`
  (canonical JSON, includes sha256 of the Pi's hardware serial)
- Predicted machine ID: see `peaq/activation-preview.json` (`machine_id`)
- Bond quote: 0.4921 PEAQ (Entry tier, $0.02/yr)

**Machine identity: activated on peaq mainnet, 8 Oct 2026** (claim 2 ✅)
- DID: `did:peaq:8600820691859294852796023821329786994502637838982221572620760063908348418155`
- Activation tx: [`0xdeab1fed124579378f9558e55861772729ec37ac4b99841cd65e53865ed50b77`](https://peaq.subscan.io/tx/0xdeab1fed124579378f9558e55861772729ec37ac4b99841cd65e53865ed50b77)
  (Subscan: Confirmed / Success. 0.495 PEAQ bond to MachineSubscription
  `0x9e37…c43895`. MREG identity NFT `860082…418155` minted to the owner. Fee
  0.1024566 PEAQ.)
- Full CLI session: `peaq/activation-log.txt` (recorded with `script`, from
  `machine.py --activate`). Machine type `VendingMachine`, tier `entry`,
  self-owned, homed on peaq. Subscription period 1791474378 → 1823010378
  (365 days).
- Funding: ~20 PEAQ bridged Solana → peaq via Stargate (official route per the
  peaq DeFi guide). Wallet balance before activation: 19.996 PEAQ.
- Screenshots: [`12-activation-subscan.png`](evidence/12-activation-subscan.png) (Subscan: Confirmed, bond, NFT), [`11-activation-cli.png`](evidence/11-activation-cli.png) (CLI: activated), [`06-mainnet-contracts-verified.png`](evidence/06-mainnet-contracts-verified.png) (contracts checked on chain 3338), [`07-whoami-mainnet.png`](evidence/07-whoami-mainnet.png) (CLI on peaq-mainnet), [`08-dry-run-insufficient-peaq.png`](evidence/08-dry-run-insufficient-peaq.png) (first dry run, bond quote), [`09-stargate-bridge.png`](evidence/09-stargate-bridge.png) (20 PEAQ bridged Solana → peaq), [`10-balance-19996-peaq.png`](evidence/10-balance-19996-peaq.png) (preview with 19.996 PEAQ), [`13-spike-client-ok.png`](evidence/13-spike-client-ok.png) (unattended `env -i` run: client ok, no keyboard)
- Owner address: `0x60901F3fC014Eb097411720f55f247a5E6652996` (OWS wallet
  `solvend`, generated on the Pi 7 Oct 2026, key never left the device)

**First mainnet sale, end to end (9 Oct 2026, ~22:10 UTC), INV-0027, water, 1.00 USDC**
- Ordered with the shop bot's **Water** button. Paid with **Pay with Phantom**
  (wallet browse link → `docs/pay/` → Phantom "Confirm transaction", −1 USDC
  from a buyer account that is not the merchant). Code `7436` delivered to the
  chat by the minute poller about a minute later. No model anywhere in the path.
- Keypad **simulated** over a `socat` virtual serial port (hardware not
  assembled): the real `solvend-serial.py` read `KEYPAD:7436` and answered
  `DISPENSE:drink-1 invoice=INV-0027 item=water`, then logged `gantry completed
  drink-1`. **No can physically dropped for this sale.**
- After: `machine.py --status` → `pending_by_day: {"2026-10-09": "1.00"}`,
  `report_from: 1791491666`. `/machine` → 1 can, $1.00, $0.00 reported,
  Provisioned. Below the $10/day threshold, so not reported, by design.
- Solana payment: [`ZF3QEkkN…oGNyi` on Solscan](https://solscan.io/tx/ZF3QEkkNcRV6tVU1c1pV3pTdr4CGmdj5td4x7xeTiS4XuNEYWendSKAo7FTry5tQygMw6FAc6Phwke9eUfoGNyi)
  (signature read from the ledger row, not transcribed). Checked on mainnet via
  `getTransaction`: success, block time 2026-10-09T22:09:16Z, **merchant
  `4QBm…P8yP` +1.00 USDC (mainnet mint `EPjF…Dt1v`)**, paid by `2MML…uBwr`.
- Screenshots: [`20-telegram-buttons.jpg`](evidence/20-telegram-buttons.jpg) (buttons), [`21-paypage-in-phantom.jpg`](evidence/21-paypage-in-phantom.jpg) (checkout page inside Phantom; shows a later order, INV-0029), [`22-phantom-confirm.jpg`](evidence/22-phantom-confirm.jpg) (Phantom: −1 USDC), [`23-paypage-sent.jpg`](evidence/23-paypage-sent.jpg) (sent, INV-0027), [`24-telegram-code.jpg`](evidence/24-telegram-code.jpg) (code 7436 delivered), [`26-display-provisioned-1-can.png`](evidence/26-display-provisioned-1-can.png) (`/machine` after the sale)

**Revenue events**

| Invoice | Item | Amount | Settled | peaq tx | Explorer |
|---|---|---|---|---|---|
| | | | | | |

**Credit rating**
- Before first sale (8 Oct 2026, right after activation, via `machine.py --status`
  and the public `GET https://mcr.peaq.xyz/mcr/{did}`): `mcr: Provisioned`,
  `mcr_score: 0`, `bond_status: bonded`, `event_count: 0`, `revenue_trend:
  insufficient`. Screenshot of `/machine` showing Provisioned: [`26-display-provisioned-1-can.png`](evidence/26-display-provisioned-1-can.png)
- The ledger's 9 sales from 6–7 Aug 2026 were a **devnet rehearsal** (faucet
  USDC, mint `4zMMC9…JDncDU`). Found 8 Oct 2026 when a test invoice still
  carried the devnet mint. They're excluded from reporting and from the display
  by `PEAQ_REPORT_FROM` (the mainnet switch time). Never report them.
- After N sales: `...`

**Media**
- Machine photo: `...`
- Demo video: `...`
- Screenshots: `...`

**Upstream**
- peaq issues filed: `...`

---

## Pre-submission gate

- [ ] Repo public — checked in a private window
- [ ] No secret in the repo or in git history (`PEAQ_MACHINE_SEED` especially)
- [ ] README opens with what it is, assuming no prior knowledge of SolVend
- [ ] The economic mechanism is the point, not peaq tacked on
- [ ] One finished feature, not five partial ones
- [ ] Working demo, not a deck
- [ ] Video ≤ stated limit, unlisted but viewable
- [ ] Teammate in Germany can actually reach the submit form
- [ ] Submitted early, edited after
