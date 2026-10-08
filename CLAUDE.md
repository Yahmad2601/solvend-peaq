# SolVend × peaq — project context

Loaded automatically at the start of every session in this repo. Read
`SCORING.md` next; it holds the plan and the deadline.

---

## What this is

**SolVend** is a real physical vending machine. A customer messages it in a chat
app, pays from their own wallet, gets a 4-digit code, types it on the keypad, and
a gantry drops a can. It has been built, deployed and run against real payments.

**This repo adds the economic layer.** SolVend activates a machine identity on
**peaq** and streams *genuine* revenue events from every can it sells, so its
Machine Credit Rating is built from real trade rather than simulated telemetry.

**The pitch in one line:** most Machine Economy entries simulate a machine. This
one takes money from strangers and physically dispenses a product.

## Hackathon

- **peaq — "Advance the Machine Economy"**, Crypto World's Fair (Germany track)
- **~6 days.** Confirm exact deadline with @erti_peaq
- Regional gate: a **teammate in Germany submits**
- Judged on: Innovation · Technical Implementation · Impact · Clarity ·
  Machine Economy adherence
- Full plan, scope lock, risks and day plan: **`SCORING.md`**

## Scope — locked, do not expand

**IN:** `activateMachine` → DID · `submitEvent` on every settled invoice ·
machine display showing identity/revenue/credit · evidence of real sales.

**OUT** (write up as direction only): borrowing against credit, fractional
ownership, a new robotic.sh adapter, machine paying its own AI bill.

> The AI-bill loop is a **Day 3 stretch**, allowed only if activate +
> submitEvent + one real on-chain sale are all done by end of Day 2. Otherwise
> it ships as roadmap. peaq explicitly penalises "five partially built features
> instead of one fully functional one."

---

## The machine

| Part | Role |
|---|---|
| Raspberry Pi 4 (4GB, `aarch64`) | Runs everything. Use **prebuilt** binaries — source builds risk OOM |
| ESP32 (CH340 serial) | Motors + keypad only. **No Wi-Fi, no keys, no network** — deliberate |
| 16x2 I2C LCD · 4x3 keypad | `0x27` or `0x3F`. Lit-but-blank = contrast pot, not logic |
| NEMA 17 + **A4988** · 2× MG996R servos | Gantry + release. Servos stall ~2.5A each |
| TEC1-12706 cooler · 12V 100W PSU + buck | Cooler eats 60–70W — brownout shows as `EVENT:BOOT` mid-dispense |

**Serial protocol**, 115200 8N1, newline-terminated:
ESP32→Pi `KEYPAD:<4 digits>` · `EVENT:BOOT` · `EVENT:DISPENSED:drink-N` · `EVENT:PONG`
Pi→ESP32 `DISPENSE:drink-1|2|3` · `DENY:<reason>` · `PING`

Test with no hardware: `socat -d -d pty,raw,echo=0 pty,raw,echo=0`

**Catalogue:** water 1.00 / drink-1 · cola 1.50 / drink-2 · energy 2.50 / drink-3

## Architecture rules — never weaken

1. **Price is not a parameter.** The catalogue is the only source of truth; the
   item is a *tool name*. A test asserts no `amount` argument exists.
2. **Payout destinations are read from the settled transaction**, never a message.
3. **Reference entropy is `os.urandom(32)`**, never model-generated.
4. **A receipt is not a payment.** Verify the balance delta, not a signature.
5. **No model in the money path.** Settlement, code minting, delivery and claim
   are SQL and shell. The model only picks an item.

**peaq events must inherit rule 5** — `submitEvent` fires from the settlement
path, never from the agent. A dead model provider must not stop revenue
reporting.

## Layout

```
solvend/solvend.py        state machine, ledger, atomic OTP burn (55 tests)
solvend/test_solvend.py   run before and after every change
solvend/solvend-serial.py ESP32 bridge
solvend/bin/              env wrappers + poller
peaq/                     machine identity + revenue events  ← the new work
tools/machine_display.py  becomes the identity/credit display
firmware/solvend_esp32/   ESP32 firmware
deploy/                   bootstrap, deploy, systemd units
```

---

## Standing rules for Claude

- **The user controls git.** Never commit, push or branch. Report changed files.
- **Verify, don't infer.** Read the schema, the `--help`, the actual file. If
  asked "did you verify that or infer it?", the answer must be *verified*.

- **When uncertain about anything peaq-specific, ASK — don't guess.**
  There is an AI assistant on **docs.peaq.xyz** that answers from the real docs.
  It has already resolved in minutes things that would otherwise have been
  guessed wrong for days.

  Whenever a contract address, SDK signature, config key, env variable, limit,
  threshold, chain id, endpoint or tier price is not *verified*, do all three:

  1. Mark it `UNVERIFIED` in the code or doc, right where it is used
  2. Emit a copy-pasteable block for the user, like this:

     > **ASK THE DOCS ASSISTANT (docs.peaq.xyz):**
     > 1. <one precise question, naming the exact field or function>
     > 2. <another>

     Questions must be specific enough to be answered without context —
     name the method, the field, the network. "How does activation work?" is
     useless; "What is the `tier` argument range for `activate_machine` on
     agung, and what does each value cost?" is answerable.
  3. Record the answer in **`peaq/DOCS-ANSWERS.md`** once it comes back, and
     remove the `UNVERIFIED` marker.

  Never write a plausible-looking address, hash, signature or magic number into
  the codebase to keep moving. A wrong constant fails silently and costs more
  than the hour spent asking.
- **Capture evidence the day it happens** — see `EVIDENCE.md`. A judge cannot
  score what was not captured. This is the single biggest lesson from the last
  bounty, which was lost on evidence, not engineering.
- **File bugs upstream to peaq as they're found.** Framework hackathons reward
  it heavily; a bug list in a README scores nothing.
- **Run `python3 solvend/test_solvend.py` before and after touching `solvend.py`.**
  Want `55 passed, 0 failed`.
- **Feature freeze end of Day 3.** After that: evidence, README, video, submit.

## Known traps (paid for already)

- Config: an unknown key can silently discard a whole section while the health
  check still reports zero errors. Validate after every hand edit.
- Daemons do not hot-load skills/plugins — restart, then confirm the banner
  **timestamp advanced**.
- Free-tier model providers cap **tokens per day**, not just per minute. Heavy
  testing can exhaust the day right before recording.
- Never retype an address or payment URI — regenerate from the ledger.
- Cache-bust generated QR filenames; a stale image once caused a payment against
  the wrong invoice.
- `~/.cargo/bin` is not on a scheduler's PATH. Resolve absolutely.
- Source env files with `set -a`, or values silently fall back to defaults.
