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

**Machine identity**
- DID: `...`
- Activation tx: `...`
- Owner address: `...`

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
