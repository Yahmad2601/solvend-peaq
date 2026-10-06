# peaq Machine Economy — 6-day scoring plan

**Deadline:** ~12 Oct 2026 (confirm exact time with @erti_peaq)
**Submitter:** teammate in Germany (regional gate) — **verify he can submit TODAY**
**Winner announcement:** 27 Oct 2026

---

## The pitch, in one sentence

A real vending machine, running on a Raspberry Pi, that activates a machine
identity on peaq and streams **genuine revenue events** from every can it sells —
so its Machine Credit Rating is built from actual trade, not simulated telemetry.

Their own starter idea is *"Credit in motion."* Nearly everyone will simulate it.
**You have the machine.**

---

## Scope — locked

### IN (must ship)
1. `activateMachine` → SolVend has a peaq DID + ownership token
2. `submitEvent` fires on **every settled invoice**, from the Pi, automatically
3. Machine display page: DID, trailing revenue, credit rating, last events
4. Evidence: real sales, explorer links, hardware on video

### OUT (write up as direction, do not build)
- Borrowing against the credit rating / self-financed restock
- Fractional ownership + revenue split
- A new robotic.sh adapter
- Machine paying its own inference bill *(only if IN is done by Day 3)*

> "Five partially built features instead of one fully functional one" is on their
> explicit list of what won't score.

---

## Judging criteria → what satisfies it

| Criterion | What we show | Status |
|---|---|---|
| **Innovation & Creativity** | Physical machine with real revenue, not a simulation. Hardware is the moat | ☐ |
| **Technical Implementation** | peaq SDK running on-device (ARM), events fired from the settlement path, not a cron fake | ☐ |
| **Impact & Potential** | A vending machine is the canonical earning machine. Credit from real cashflow → machines become investable | ☐ |
| **Clarity & Presentation** | README a stranger understands cold; ≤3 min video; the loop visible in one diagram | ☐ |
| **Machine Economy adherence** | peaq is the economic layer, not a logging sink. Identity + revenue + credit are the product | ☐ |

## Their anti-criteria — check against these before submitting

- [ ] peaq is **not** tacked on — the economic mechanism is the point
- [ ] Not a generic fleet dashboard — there is a real economic mechanism
- [ ] Working demo, not a deck
- [ ] README assumes **no** prior knowledge of SolVend
- [ ] One finished feature, not five partial ones

---

## Evidence ledger — capture the day it happens

| Claim | Evidence | Done |
|---|---|---|
| Real hardware | `cat /proc/device-tree/model` + photo/video of the machine | ☐ |
| Machine has a peaq identity | DID string + explorer link to `activateMachine` tx | ☐ |
| Revenue events are real | ≥3 sales, each with an explorer link, matched to ledger rows | ☐ |
| Credit rating moves | before/after screenshots of the score | ☐ |
| Autonomous | event fired with no human action — log excerpt with timestamps | ☐ |
| Reproducible | quickstart someone else could follow | ☐ |
| Bugs found | issues filed with peaq | ☐ |

---

## Day plan

| Day | Goal | Freeze rule |
|---|---|---|
| **1 (today)** | **SPIKE: peaq SDK on the Pi.** Faucet tokens on `agung`. One successful `activateMachine` from the Pi | Nothing else matters today |
| **2** | `submitEvent` wired into the settlement path. One real purchase → one on-chain event | |
| **3** | Display page (reuse `tools/machine_display.py`). **FEATURE FREEZE at end of day** | No new code after this |
| **4** | Evidence capture + README written for a stranger | |
| **5** | Video. Film silent, narrate after | |
| **6** | Teammate submits early. Buffer for breakage | |

---

## Risks, highest first

1. **peaq Python SDK may not install on ARM/Pi.** Spike it in the first two hours.
   Fallbacks, in order: JS SDK via Node on the Pi → direct EVM JSON-RPC with
   `web3.py` → run the peaq client on a laptop reading the Pi's ledger (weaker
   story, say so honestly).
2. **Faucet is 2FA-gated.** Get `agung` tokens today or day 1 ends blocked.
3. **Groq free tier daily cap** bit us before. Budget model calls; the demo needs
   two or three, not twenty.
4. **Teammate submission path unverified.** He should open the listing and reach
   the submit form today.
5. **Testnet vs mainnet** — ask @erti_peaq which they expect. Devnet cost us a
   placement last time.

---

## Questions for @erti_peaq (send today)

1. Exact submission deadline, with timezone?
2. `agung` testnet acceptable, or mainnet expected?
3. Is a teammate-submitted entry fine if the builder is outside Germany?
4. Any required tags/mentions on the submission form?
