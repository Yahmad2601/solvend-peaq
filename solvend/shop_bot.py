#!/usr/bin/env python3
"""SolVend shop bot: tap a drink, get a pay button. No model in the purchase.

Replaces the chat agent on the customer channel (2026-10-08). The agent was
asked to call an invoice tool and paste the URI it returned; after Groq retired
its model, the replacement skipped the tool and replied "[LINK:{uri}]" with no
invoice behind it. A purchase must not depend on a model choosing to cooperate.

Flow:
  any message      -> menu: one button per catalogue item
  tap "Cola"       -> solvend.cmd_invoice (price from ITEMS, reference from
                      os.urandom) -> two URL buttons, Phantom and Solflare
  tap a wallet     -> the wallet's "browse" universal link opens the static pay
                      page (docs/pay/) inside the wallet, which builds the USDC
                      transfer with the invoice reference attached
  paid             -> the minute poller settles it and calls `shop_bot.py
                      notify <chat> <text>` with the 4-digit code

The bot never sees money and decides nothing about payment: it creates an
invoice exactly as the skill did and sends a link. Settlement is unchanged.

    shop_bot.py run                    # long-poll Telegram (systemd service)
    shop_bot.py check                  # verify the published pay page
    shop_bot.py notify <chat> <text>   # used by solvend-poll.sh

Env: SOLVEND_SHOP_BOT_TOKEN (BotFather token of the customer bot),
     SOLVEND_PAY_PAGE_URL, plus solvend.py's SOLVEND_* settings.
Stdlib only.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solvend  # noqa: E402

TOKEN = os.environ.get("SOLVEND_SHOP_BOT_TOKEN", "")
PAY_PAGE = os.environ.get("SOLVEND_PAY_PAGE_URL",
                          "https://yahmad2601.github.io/solvend-peaq/pay/")
CHANNEL = "shopbot"          # invoices.channel; the poller routes codes by it
POLL_TIMEOUT = 50

MENU_TEXT = ("SolVend. Pick a drink.\n\nYou pay in USDC from Phantom or "
             "Solflare. Your 4-digit code arrives here; type it on the "
             "machine's keypad.")


def api(method: str, **params):
    """One Telegram Bot API call. Raises on transport or API error."""
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=json.dumps(params).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
        body = json.load(resp)
    if not body.get("ok"):
        raise RuntimeError(f"telegram {method}: {body.get('description')}")
    return body.get("result")


def price(item: str) -> str:
    return f"{solvend.ITEMS[item]['price_base'] / 10 ** solvend.USDC_DECIMALS:.2f}"


def menu_markup() -> dict:
    return {"inline_keyboard": [
        [{"text": f"{item.title()} · {price(item)} USDC", "callback_data": f"buy:{item}"}]
        for item in solvend.ITEMS]}


def pay_links(invoice_id: str, item: str, amount: str, reference: str) -> dict:
    """Wallet 'browse' universal links that open the pay page inside the app.
    Formats: docs.phantom.com and docs.solflare.com, browse deeplink."""
    page = f"{PAY_PAGE}?" + urlencode({"invoice": invoice_id, "item": item,
                                       "amount": amount, "reference": reference})
    parts = urlsplit(PAY_PAGE)
    ref = quote(f"{parts.scheme}://{parts.netloc}", safe="")
    target = quote(page, safe="")
    return {
        "page": page,
        "phantom": f"https://phantom.com/ul/browse/{target}?ref={ref}",
        "solflare": f"https://solflare.com/ul/v1/browse/{target}?ref={ref}",
    }


def open_order(chat_id: str):
    """This chat's live unpaid invoice, if any. One open order per chat keeps a
    tap-happy customer from stacking invoices the fallback has to tell apart."""
    with solvend.db() as conn:
        return conn.execute(
            "SELECT invoice_id, item, amount_base, reference FROM invoices"
            " WHERE channel=? AND handle=? AND status='AWAITING_PAYMENT'"
            "   AND created_at > ? ORDER BY created_at DESC LIMIT 1",
            (CHANNEL, chat_id, solvend.now() - solvend.UNPAID_TTL_SECS)).fetchone()


def order(chat_id: str, item: str) -> dict:
    """-> {invoice_id, item, amount, reference, reused} or {error}."""
    existing = open_order(chat_id)
    if existing:
        amt = f"{existing['amount_base'] / 10 ** solvend.USDC_DECIMALS:.6f}".rstrip("0").rstrip(".")
        return {"invoice_id": existing["invoice_id"], "item": existing["item"],
                "amount": amt, "reference": existing["reference"], "reused": True}
    reference = solvend.b58encode(os.urandom(32))
    rec = solvend.cmd_invoice(item, CHANNEL, chat_id, reference)
    if "error" in rec:
        return rec
    return {"invoice_id": rec["invoice_id"], "item": item.strip().lower(),
            "amount": rec["amount"], "reference": reference, "reused": False}


def handle(update: dict, call=api) -> None:
    """React to one Telegram update. `call` is injected by tests."""
    cb = update.get("callback_query")
    if cb:
        chat_id = str(cb["message"]["chat"]["id"])
        call("answerCallbackQuery", callback_query_id=cb["id"])
        data = cb.get("data") or ""
        if not data.startswith("buy:"):
            return
        rec = order(chat_id, data[4:])
        if "error" in rec:
            call("sendMessage", chat_id=chat_id,
                 text="Sorry, that item isn't available. Pick again.",
                 reply_markup=menu_markup())
            return
        links = pay_links(rec["invoice_id"], rec["item"], rec["amount"], rec["reference"])
        lead = ("You already have an open order:\n\n" if rec["reused"] else "")
        call("sendMessage", chat_id=chat_id,
             text=(f"{lead}{rec['item'].title()}: {rec['amount']} USDC "
                   f"({rec['invoice_id']}).\n\nTap your wallet to pay. Your "
                   f"4-digit code arrives here about a minute after payment. "
                   f"Pay within 30 minutes."),
             reply_markup={"inline_keyboard": [
                 [{"text": "Pay with Phantom", "url": links["phantom"]}],
                 [{"text": "Pay with Solflare", "url": links["solflare"]}]]})
        return
    msg = update.get("message")
    if msg and "chat" in msg:
        call("sendMessage", chat_id=str(msg["chat"]["id"]), text=MENU_TEXT,
             reply_markup=menu_markup())


def check_pay_page(fetch=None) -> str:
    """'' if the published pay page pays THIS machine's merchant in THIS mint,
    else the reason. The page hard-codes both; a typo there would send every
    customer's money somewhere else, so the bot refuses to start on mismatch."""
    try:
        if fetch:
            html = fetch(PAY_PAGE)
        else:
            req = urllib.request.Request(PAY_PAGE, headers={"User-Agent": "SolVend-shop-bot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode()
    except Exception as e:                          # noqa: BLE001
        return f"pay page unreachable: {type(e).__name__}: {e}"[:200]
    found = {k: (re.search(rf'const {k}\s*=\s*"([^"]+)"', html) or [None, None])[1]
             for k in ("MERCHANT", "USDC_MINT")}
    if found["MERCHANT"] != solvend.MERCHANT:
        return f"pay page MERCHANT {found['MERCHANT']!r} != SOLVEND_RECIPIENT {solvend.MERCHANT!r}"
    if found["USDC_MINT"] != solvend.USDC_MINT:
        return f"pay page USDC_MINT {found['USDC_MINT']!r} != SOLVEND_USDC_MINT {solvend.USDC_MINT!r}"
    return ""


def run() -> int:
    if not TOKEN:
        print("SOLVEND_SHOP_BOT_TOKEN is not set", file=sys.stderr)
        return 2
    problem = check_pay_page()
    if problem:
        print(f"refusing to start: {problem}", file=sys.stderr)
        return 2
    print(f"shop bot up; pay page {PAY_PAGE} verified", flush=True)
    offset = 0
    while True:
        try:
            updates = api("getUpdates", offset=offset, timeout=POLL_TIMEOUT,
                          allowed_updates=["message", "callback_query"])
        except Exception as e:                      # noqa: BLE001
            # 409 here means another process (ZeroClaw) still polls this bot.
            print(f"getUpdates failed: {e}", file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                handle(u)
            except Exception as e:                  # noqa: BLE001
                print(f"update {u.get('update_id')} failed: {e}", file=sys.stderr, flush=True)


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "run"
    if cmd == "run":
        return run()
    if cmd == "check":
        problem = check_pay_page()
        print(json.dumps({"pay_page": PAY_PAGE, "ok": not problem, "problem": problem or None}))
        return 0 if not problem else 2
    if cmd == "notify" and len(args) == 3:
        api("sendMessage", chat_id=args[1], text=args[2])
        return 0
    print("usage: shop_bot.py run | check | notify <chat_id> <text>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
