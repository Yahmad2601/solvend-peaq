# Evidence ledger

Fill this the day something works, not at the deadline. The last bounty was lost
on evidence, not engineering — the machine did more than the repo could prove.

**Rule: if it isn't captured here, a judge cannot score it.**

---

## Core claims

| # | Claim | Evidence needed | Captured |
|---|---|---|---|
| 1 | It is real hardware, not a simulation | `cat /proc/device-tree/model` output + photo/video of the machine | ☐ |
| 2 | The machine has a peaq identity | DID string + explorer link to the `activateMachine` tx | ☐ |
| 3 | Revenue events are real sales | ≥3 settlements, each with an explorer link, matched to its ledger row | ☐ |
| 4 | The credit rating moves | Before/after screenshots of the score with timestamps | ☐ |
| 5 | Reporting is autonomous | Log excerpt: settlement → `submitEvent` with no human action between | ☐ |
| 6 | No model in the money path | Show the event firing while the agent is stopped | ☐ |
| 7 | Nothing double-counts | Run `--sync` twice; second run reports 0 submitted | ☐ |
| 8 | Tests pass | `python3 solvend/test_solvend.py` output, pasted with the count | ☐ |
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
Screenshot: `...` *(save the terminal screenshot into the repo and link it here)*
Still needed for claim 1: photo/video of the machine.

**peaqOS on the device** (captured 7 Oct 2026, inside `~/solvend-peaq/.peaq` venv)
```
$ peaqos --version
peaq-os-cli 0.0.15 (peaq_os_sdk 0.11.0)
```
All native deps installed as prebuilt `aarch64` wheels; no compilation.
Screenshot: `...` *(save into the repo and link here)*

**Machine identity: preview (dry run, 8 Oct 2026, peaq mainnet)**
- machine_type `VendingMachine`, credential subject `peaq/credential-subject.json`
  (canonical JSON, includes sha256 of the Pi's hardware serial)
- Predicted machine ID: see `peaq/activation-preview.json` (`machine_id`)
- Bond quote: 0.4921 PEAQ (Entry tier, $0.02/yr)

**Machine identity**
- DID: `...`
- Activation tx: `...`
- Owner address: `0x60901F3fC014Eb097411720f55f247a5E6652996` (OWS wallet
  `solvend`, generated on the Pi 7 Oct 2026, key never left the device)

**Revenue events**

| Invoice | Item | Amount | Settled | peaq tx | Explorer |
|---|---|---|---|---|---|
| | | | | | |

**Credit rating**
- Before first sale: `...`
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
