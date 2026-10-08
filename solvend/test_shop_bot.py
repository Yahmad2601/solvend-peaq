#!/usr/bin/env python3
"""Host-run tests for the shop bot. Fake Telegram, temp ledger, no network.

Run:  python3 solvend/test_shop_bot.py
"""
import os
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit

TMP = tempfile.mkdtemp()
os.environ["SOLVEND_DB"] = os.path.join(TMP, "test.db")
os.environ["SOLVEND_RECIPIENT"] = "4QBmNWkWCdTXKrHjJnbZVbKCCctdJRk5RZsB49F7P8yP"
os.environ["SOLVEND_PAY_PAGE_URL"] = "https://example.github.io/solvend-peaq/pay/"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import solvend    # noqa: E402
import shop_bot   # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")


with solvend.db() as c:
    c.executescript(solvend.SCHEMA)

SENT = []


def fake_call(method, **params):
    SENT.append((method, params))
    return {}


def tap(chat, data, cb_id="cb1"):
    SENT.clear()
    shop_bot.handle({"callback_query": {"id": cb_id, "data": data,
                                        "message": {"chat": {"id": chat}}}}, fake_call)
    return [p for m, p in SENT if m == "sendMessage"]


def open_rows(chat):
    with solvend.db() as c:
        return c.execute("SELECT * FROM invoices WHERE handle=? AND status='AWAITING_PAYMENT'",
                         (str(chat),)).fetchall()


print("\nmenu — any message gets the catalogue as buttons")
SENT.clear()
shop_bot.handle({"message": {"chat": {"id": 111}, "text": "hi"}}, fake_call)
kb = SENT[0][1]["reply_markup"]["inline_keyboard"] if SENT else []
check("one button per catalogue item", len(kb) == len(solvend.ITEMS))
check("prices come from ITEMS", any("1.50 USDC" in row[0]["text"] for row in kb)
      and all(row[0]["callback_data"].startswith("buy:") for row in kb))

print("\norder — a tap creates exactly one invoice at the catalogue price")
msgs = tap(111, "buy:cola")
rows = open_rows(111)
check("one AWAITING_PAYMENT invoice", len(rows) == 1)
check("priced from ITEMS, not the button", rows and rows[0]["amount_base"] == 1_500_000)
check("addressed to this chat on the shopbot channel",
      rows and rows[0]["channel"] == "shopbot" and rows[0]["handle"] == "111")
check("reference is 32 random bytes, base58", rows and 40 <= len(rows[0]["reference"]) <= 44)
check("callback acknowledged", SENT and SENT[0][0] == "answerCallbackQuery")
buttons = [b[0] for b in msgs[0]["reply_markup"]["inline_keyboard"]] if msgs else []
check("two wallet buttons", [b["text"] for b in buttons] == ["Pay with Phantom", "Pay with Solflare"])

print("\nlinks — wallet universal links wrap the pay page with the order")
ph = buttons[0]["url"] if buttons else ""
sf = buttons[1]["url"] if len(buttons) > 1 else ""
check("Phantom browse link format", ph.startswith("https://phantom.com/ul/browse/https%3A%2F%2F"))
check("Solflare browse link format", sf.startswith("https://solflare.com/ul/v1/browse/https%3A%2F%2F"))
inner = unquote(urlsplit(ph).path[len("/ul/browse/"):])
q = parse_qs(urlsplit(inner).query)
check("pay page carries invoice, item, amount, reference",
      rows and q.get("invoice") == [rows[0]["invoice_id"]] and q.get("item") == ["cola"]
      and q.get("amount") == ["1.5"] and q.get("reference") == [rows[0]["reference"]])
check("pay page link has no merchant or mint (the page hard-codes them)",
      "to" not in q and "recipient" not in q and "mint" not in q
      and solvend.MERCHANT not in inner)
check("ref is the pay page origin", urlsplit(ph).query == "ref=https%3A%2F%2Fexample.github.io")

print("\none open order per chat")
msgs = tap(111, "buy:energy")
check("second tap does not create another invoice", len(open_rows(111)) == 1)
check("it re-sends the open order", msgs and "already have an open order" in msgs[0]["text"]
      and "Cola" in msgs[0]["text"])
check("another chat orders independently", tap(222, "buy:water") and len(open_rows(222)) == 1)

print("\nforged buttons cannot set a price or invent an item")
msgs = tap(333, "buy:caviar")
check("unknown item creates nothing", open_rows(333) == [])
check("customer is shown the menu again", msgs and "inline_keyboard" in msgs[0]["reply_markup"])
tap(333, "sell:cola")
check("non-buy callback ignored", open_rows(333) == [])

print("\nexpiry — an expired order no longer blocks a new one")
with solvend.db() as c:
    c.execute("UPDATE invoices SET created_at=? WHERE handle='111'",
              (solvend.now() - solvend.UNPAID_TTL_SECS - 1,))
solvend.cmd_watch(lambda m, p: {"result": []} if m != "getTokenAccountsByOwner"
                  else {"result": {"value": []}})
tap(111, "buy:energy")
rows = open_rows(111)
check("fresh order after expiry", len(rows) == 1 and rows[0]["item"] == "energy")

print("\npay page check — refuses a page that pays someone else")
good = 'const MERCHANT   = "%s";\nconst USDC_MINT  = "%s";' % (solvend.MERCHANT, solvend.USDC_MINT)
check("matching page passes", shop_bot.check_pay_page(lambda u: good) == "")
bad = good.replace(solvend.MERCHANT[:6], "ATTACK")
check("different merchant refused", "MERCHANT" in shop_bot.check_pay_page(lambda u: bad))
check("different mint refused", "USDC_MINT" in shop_bot.check_pay_page(
    lambda u: good.replace(solvend.USDC_MINT, "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")))
check("unreachable page refused", "unreachable" in shop_bot.check_pay_page(
    lambda u: (_ for _ in ()).throw(OSError("down"))))
real = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "pay",
                         "index.html"), encoding="utf-8").read()
check("the repo's own pay page matches this machine", shop_bot.check_pay_page(lambda u: real) == "")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
