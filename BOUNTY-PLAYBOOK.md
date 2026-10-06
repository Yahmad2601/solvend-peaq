# SolVend — Bounty Playbook

**Copy this file into the root of any new bounty project.** Point your assistant
at it first: *"Read BOUNTY-PLAYBOOK.md, then read the bounty brief."*

It carries three things a fresh session cannot know: what the machine is, what
is reusable, and how a bounty is lost.

---

# PART 1 — THE MACHINE

A physical vending machine that sells a can for crypto. A customer talks to it
in a chat app, pays from their own wallet, receives a 4-digit code, types it on
the keypad, and a gantry drops the can.

**The one-line thesis:** the machine never holds a key, and the language model
never decides anything that touches money.

## Hardware inventory (owned, working)

| Part | Notes |
|---|---|
| Raspberry Pi 4, 4GB | Runs the agent runtime + all logic. `aarch64`. Use prebuilt binaries — source builds risk OOM |
| ESP32 (CH340 USB-serial) | Motion + keypad only. **No Wi-Fi, no keys, no network** |
| 16x2 I2C LCD | Address `0x27` or `0x3F`. Lit-but-blank = contrast pot or wrong address, not logic |
| 4x3 matrix keypad | Emits `KEYPAD:<4 digits>` |
| NEMA 17 + **A4988** driver | X-axis gantry. (Often typo'd as A4998) |
| 2x MG996R servos | Can release + final presentation. Stall ~2.5A **each** |
| TEC1-12706 cooler | ~5–6A at 12V — 60–70W of budget |
| 12V 100W PSU + buck converter | Buck steps to 5V for servos/logic |

## Power rules — learned the hard way

- **Bench:** ESP32 on **USB only**. Remove the buck to ESP32 `5V`/`VIN` wire.
  Two sources on one rail can push current into the laptop's USB port.
- **Final:** the Pi's USB powers the ESP32. Leave the buck wire off.
- **All grounds tied at one point.** Motor return current must never travel
  through the USB cable.
- **Budget is tight.** TEC + stepper + 2 servos can exceed 100W. The symptom is
  not electrical-looking: `EVENT:BOOT` appears mid-dispense (brownout), or the
  stepper loses steps and misaligns. Bench with the TEC disconnected first.
- 1000µF across the buck's 5V near the servos; 100µF+ across A4988 `VMOT`.

## Serial protocol — 115200 8N1, newline-terminated

| Direction | Messages |
|---|---|
| ESP32 to Pi | `KEYPAD:<4 digits>` · `EVENT:BOOT` · `EVENT:DISPENSED:drink-N` · `EVENT:PONG` · `EVENT:ERROR:*` |
| Pi to ESP32 | `DISPENSE:drink-1`, `-2`, `-3` · `DENY:<reason>` · `PING` |

The daemon matches `^KEYPAD:(\d{4})$` strictly. Deny reasons shown to customers
are deliberately vague (prevents keypad probing); the operator log has detail.

**Bench testing:** Arduino Serial Monitor, 115200, line ending **Newline** —
with "No line ending" the firmware never sees a terminator and ignores input.
You *type* `PING`, `DISPENSE:drink-1`, `DENY:x`. You *read* `EVENT:*`, `KEYPAD:*`.

**No hardware needed** — virtual serial pair:

    socat -d -d pty,raw,echo=0 pty,raw,echo=0
    SOLVEND_SERIAL_PORT=/dev/pts/3 python3 solvend-serial.py &
    printf 'KEYPAD:1234\n' > /dev/pts/4

## Catalogue

| Item | Price | Base units | Slot |
|---|---|---|---|
| water | 1.00 | 1,000,000 | drink-1 |
| cola | 1.50 | 1,500,000 | drink-2 |
| energy | 2.50 | 2,500,000 | drink-3 |

Serial port: always `/dev/serial/by-id/...`, never `/dev/ttyUSB0` (renumbers
across reboots). In systemd use `DeviceAllow=char-ttyUSB rw`, not a device path —
a path resolves to one major:minor at load time and blocks a renumbered port.

---

# PART 2 — WHAT PORTS TO ANY PLATFORM

## Reusable as-is

- **The state machine.** `AWAITING_PAYMENT → PAID_UNCLAIMED → CLAIMED`, plus
  expiry and refund states. Rail-agnostic.
- **The atomic single-use burn.** The `UPDATE ... RETURNING` *is* the
  authorization decision — status, expiry and attempt budget all live in the
  `WHERE` clause, so there is no check-then-act window. A losing racer changes
  zero rows.
- **The serial daemon and firmware.** Any platform that can say "dispense slot N".
- **The five structural controls** below.

## Must be rewritten per platform

Only the **payment rail**: how a payment request is expressed, and how
settlement is proven. Everything else stays.

## The five structural controls — never weaken these

1. **Price is not a parameter.** The catalogue is the only source of truth, and
   the item is a *tool name*, so an unknown item cannot be expressed at the tool
   boundary either. A test asserts the absence of an `amount` argument.
2. **The payout/refund destination is read from the settled transaction**, never
   from a message. Ambiguous resolves to `None` and fails closed. No address
   parameter exists anywhere.
3. **Reference/nonce entropy is `os.urandom(32)`**, never model-generated.
   Correlated output would cross-credit one customer's payment to another.
4. **A receipt is not a payment.** Verify the *effect* — the balance delta on the
   merchant account — not the existence of a signature or a webhook body.
5. **No model in the money path.** Settlement, code minting, code delivery and
   the claim are SQL and shell. The model only picks an item.

**Write a test for each one.** "A test asserts the absence of this parameter, so
a refactor that adds one fails CI" is a sentence judges reward.

---

# PART 3 — BOUNTY OPERATING PROCEDURE

## Day 1 — before writing any code

1. **Extract the rubric into a weighted checklist** (`SCORING.md`): every
   criterion, its weight, and what evidence would satisfy it.
2. **Separate what the brief *recommends* from what the rubric *rewards*.**
   They diverge. The rubric wins.
   > Learned the hard way: a brief said "a tier 1 solution beats unnecessary
   > WASM" and "T0/T1 is where most of the prize money will land." All seven
   > winners shipped a compiled plugin. Craft was 20% and read "where you built
   > code: pure core, real tests, idiomatic Rust." Pure composition gave the
   > judges nothing to score.
3. **Pick the implementation language the ecosystem is written in**, not the one
   fastest for you. A Rust-native framework expects Rust.
4. **Mark every "required" in the brief as a hard gate**, not a nice-to-have.
5. **List the free-tier limits you will depend on** — model tokens per day, RPC
   calls, faucets — and confirm the ceilings now, not at the deadline.

## Week 1

- **Read three competing or prior-winning submissions.** Architecture
  intelligence on day 3 is worth more than polish on day 30.
- **Get one real transaction on the production network working**, however ugly.
- **Start `EVIDENCE.md`** and add to it the same day anything works.

## Continuously

- **File every framework bug upstream the day you find it.** Ten minutes each.
  > The single most under-priced scoring axis. 1st place had six merged PRs to
  > core; 2nd won partly on "nine upstream issues filed, most already fixed";
  > the sponsor bonus went to "four merged PRs and 22 issues." A bug list in
  > your README scores nothing. The same list in the issue tracker is a category.
- **Capture evidence the moment it happens.** Screenshot the working chat, save
  the transaction signature, paste the terminal output into the repo. Evidence
  gathered at the deadline is evidence that does not exist.

## T-72 hours — feature freeze

No new features. What remains is evidence, write-up, reproduction test and
rehearsal. Anything not working by now is cut and stated as an honest limit.

## T-48 hours

- **Do the production-network transaction and record the signature.**
- **Capture the security/injection transcript** — real messages, real replies,
  pasted into the repo.
- Push everything. Verify the repo is public in a private window.

## T-24 hours

- **Run your own quickstart on a clean machine.** Time it. Fix what breaks.
- Record the demo. Film silently and narrate afterwards — a fumbled line then
  costs nothing, and dead waiting time can be compressed in the edit.

## T-12 hours

- **Submit early with whatever exists.** Most forms allow edits until the
  deadline; none allow a late entry.
- Post in the community channel if the brief says the post *is* the submission.

---

# PART 4 — THE EVIDENCE LEDGER

Keep `EVIDENCE.md` in the repo from week one. A judge cannot score what you did
not capture.

| Claim | Evidence | Where | Done |
|---|---|---|---|
| Runs on real hardware | `cat /proc/device-tree/model`, photo of the box | README | ☐ |
| Production-network transaction | explorer link + signature | README | ☐ |
| Autonomous, no model in path | screenshot of delivered code + scheduler log | README | ☐ |
| Single-use enforcement | terminal: same code twice, second refused | README | ☐ |
| Injection resistance | **full transcript**, attacks and replies | docs/ | ☐ |
| Tests pass | pasted output with a count | README | ☐ |
| Reproducible | timed clean-machine run | README | ☐ |
| Framework bugs found | **links to filed issues** | README | ☐ |

**Rule: production network, not testnet.** Testnet reads as unfinished. The
transaction costs a couple of dollars; the perception costs a placement.

---

# PART 5 — PLATFORM LESSONS

## Framework-agnostic

- **An unknown config key can silently discard a whole section** and fall back to
  defaults while the health check still reports zero errors. Validate the file
  after every hand edit. Prefer a validating `config set` CLI over an editor.
- **Look for a schema dump** (`config schema`, `--print-schema`) before guessing
  any key. Guessing cost a full day once; the schema command existed all along.
- **Daemons rarely hot-load plugins or skills.** Restart, then confirm the banner
  timestamp advanced — status commands replay the last banner and look identical.
- **Security scrubbers can corrupt payment payloads.** An outbound leak detector
  destroyed a Solana Pay URI: base58 keys tripped an entropy heuristic and the
  spec's own `spl-token=` parameter matched a generic `token=` credential regex.
  Always send a payment string to yourself and read it end to end.
- **systemd: no trailing comments on a directive line.** The comment is parsed as
  part of the value and the directive is silently ignored while the unit starts.
- **Never retype an address or payment URI.** Regenerate it from the ledger.
- **Cache-bust generated QR filenames** (`qr-<id>-<timestamp>.png`). A stale
  cached image caused a real payment against the wrong invoice.
- **Check whether "usage limit" is the provider's or your own runtime profile's**
  rate cap before switching providers in a panic.
- **Free tiers cap tokens per day, not just per minute.** Heavy testing can
  exhaust the day right before you record.

## Deployment

- `sudo cp` leaves files `root:root`; a later `chmod 750` then locks out the
  service user. Set ownership explicitly.
- Binaries in `~/.cargo/bin` are **not** on a scheduler's PATH. Resolve
  absolutely, and refuse to act if the binary is missing.
- Source env files with `set -a` — plain `. file` creates *shell* variables that
  `exec` does not pass on, so every value silently falls back to its default.

---

# PART 6 — PRE-SUBMISSION GATE

Do not submit until every line is yes.

- [ ] Repo public — verified in a private window
- [ ] No secret in the repo or anywhere in git history
- [ ] README opens with what it is, who it is for, and the custody/trust posture
- [ ] A quickstart a stranger can follow in under 30 minutes, **which you have run**
- [ ] A table of which framework features were used, and what you built vs composed
- [ ] Production-network transaction linked
- [ ] Security/injection transcript captured, not just a protocol table
- [ ] Test output pasted with a count
- [ ] Honest limits section naming real weaknesses
- [ ] Upstream issues filed and linked
- [ ] Demo video within the stated limit, unlisted but viewable
- [ ] Posted in the channel the brief names as the submission format
- [ ] Form submitted early, edited later

---

# PART 7 — WORKING WITH YOUR ASSISTANT

- **Bring it in on day 1.** Hand it the brief and ask for `SCORING.md` first.
- **Ask it to re-score you weekly** against that file. A standing "transcript:
  missing" line for three weeks gets fixed; realising it on the last night does not.
- **Ask it to draft upstream issues** the moment a framework bug appears.
- **Give it your constraints up front** — token caps, one board, no card for
  billing. It plans around limits it knows about and walks into ones it does not.
- **Ask for the pessimistic pass** a week out: *"What will a judge disbelieve?
  What can a stranger not reproduce? What is missing?"*
- **Make it verify rather than infer** — schema dumps, `--help`, actual file
  contents. Ask directly: "did you verify that, or infer it?"
- **The last 24 hours are for recording and submitting.** If you are debugging a
  provider outage with a camera set up, the plan failed three weeks earlier.
