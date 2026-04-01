#!/usr/bin/env python3
"""
Brazilian Consulate Cairo — VISIT VISA (VIVIS) Date Checker
Logs in, opens the 'Available dates' page, reads the table,
and alerts you when the VIVIS / Tourism Visa slot is before June 20 2026.

Usage:
    python visa_checker.py              # single check
    python visa_checker.py --loop       # re-check every CHECK_INTERVAL_MINUTES
"""

import asyncio
import random
import sys
from datetime import date, datetime

import requests
from playwright.async_api import Page, async_playwright

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  ← fill in your credentials
# ──────────────────────────────────────────────────────────────────────────────
EMAIL    = "YOUR_EMAIL@example.com"   # the Email field on the login page
PASSWORD = "YOUR_PASSWORD"

TELEGRAM_TOKEN   = "YOUR_BOT_TOKEN"   # from @BotFather
TELEGRAM_CHAT_ID = "971364231"        # your personal chat ID

TARGET_DATE            = date(2026, 6, 20)   # alert if slot is BEFORE this
LOGIN_URL              = "https://ec-cairo.itamaraty.gov.br/login"
CHECK_INTERVAL_MINUTES = 30                  # loop mode only
HEADLESS               = False               # True = no visible browser window
# ──────────────────────────────────────────────────────────────────────────────



# ── Human-like helpers ────────────────────────────────────────────────────────

async def pause(min_ms: float = 400, max_ms: float = 1400):
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


async def human_type(page: Page, selector: str, text: str):
    """Click a field then type each character with a random inter-key delay."""
    el = await page.wait_for_selector(selector, timeout=15_000)
    await el.click()
    await pause(200, 500)
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(random.uniform(0.06, 0.20))
    await pause(200, 600)


async def human_click(page: Page, selector: str, timeout: int = 15_000):
    """Move the mouse to an element and click slightly off-centre."""
    el = await page.wait_for_selector(selector, timeout=timeout)
    box = await el.bounding_box()
    if box:
        x = box["x"] + box["width"]  * random.uniform(0.25, 0.75)
        y = box["y"] + box["height"] * random.uniform(0.25, 0.75)
        await page.mouse.move(x, y, steps=random.randint(12, 30))
        await pause(100, 350)
        await page.mouse.click(x, y)
    else:
        await el.click()
    await pause(300, 900)


# ── Notification ──────────────────────────────────────────────────────────────

def send_telegram(found_date: date):
    text = (
        f"🚨 Visa slot available!\n"
        f"VISIT VISA (VIVIS) - TOURISM VISA\n"
        f"First available: {found_date.strftime('%A, %B %d, %Y')}\n"
        f"Book now at: {LOGIN_URL}"
    )
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        if resp.ok:
            print("[+] Telegram notification sent.")
        else:
            print(f"[!] Telegram error: {resp.text}")
    except Exception as e:
        print(f"[!] Telegram failed: {e}")


def notify(found_date: date):
    border = "═" * 60
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{border}")
    print("  *** VISA SLOT AVAILABLE ***")
    print(f"  VISIT VISA (VIVIS) - TOURISM VISA")
    print(f"  First available date : {found_date.strftime('%A, %B %d, %Y')}")
    print(f"  Your target deadline : {TARGET_DATE.strftime('%B %d, %Y')}")
    print(f"  Checked at           : {ts}")
    print(f"{border}\n")
    print("\a\a\a")   # terminal bell × 3
    send_telegram(found_date)

    # Optional desktop popup — install with: pip install plyer
    try:
        from plyer import notification as desktop
        desktop.notify(
            title="Visa slot available!",
            message=f"VIVIS Tourism Visa: {found_date}",
            timeout=60,
        )
    except Exception:
        pass


# ── Date parsing ──────────────────────────────────────────────────────────────

def parse_date(text: str) -> date | None:
    """
    Parse the dates shown in the table, e.g. 'Thursday, July 02, 2026'.
    Falls back through several formats.
    """
    text = text.strip()
    for fmt in (
        "%A, %B %d, %Y",   # Thursday, July 02, 2026
        "%B %d, %Y",        # July 02, 2026
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ── Core logic ────────────────────────────────────────────────────────────────

async def login(page: Page):
    # Go directly to the login URL (ec-cairo.itamaraty.gov.br/login)
    print(f"[*] Opening {LOGIN_URL}")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    await pause(1500, 3000)

    # ── Email field  (id="email-input", name="email") ─────────────────────
    print("[*] Entering email ...")
    await human_type(page, "#email-input", EMAIL)

    await pause(500, 1000)

    # ── Password field  (id="pass-input", name="pass") ────────────────────
    print("[*] Entering password ...")
    await human_type(page, "#pass-input", PASSWORD)

    await pause(700, 1300)

    # ── Green "Enter" button ───────────────────────────────────────────────
    print("[*] Clicking Enter ...")
    await human_click(page, "button:has-text('Enter')")

    await page.wait_for_load_state("networkidle", timeout=25_000)
    await pause(1500, 2500)

    # If we're still on /login the credentials were wrong
    if "/login" in page.url:
        await page.screenshot(path="debug_login_failed.png")
        raise RuntimeError(
            "Still on login page after submit.\n"
            "Check EMAIL / PASSWORD in the script, or see debug_login_failed.png."
        )
    print("[+] Logged in.")


async def go_to_available_dates(page: Page):
    """Click the 'Available dates' link in the top navigation bar."""
    await pause(800, 1600)
    for sel in (
        "a:has-text('Available dates')",
        "a:has-text('Available Dates')",
        "a:has-text('Datas disponíveis')",
        "a:has-text('Datas Disponíveis')",
        "nav a[href*='available']",
        "nav a[href*='datas']",
    ):
        try:
            await human_click(page, sel, timeout=5_000)
            await page.wait_for_load_state("networkidle", timeout=20_000)
            await pause(1000, 2000)
            print("[+] On 'Available dates' page.")
            return
        except Exception:
            continue

    await page.screenshot(path="debug_post_login.png")
    raise RuntimeError(
        "Cannot find 'Available dates' nav link.\n"
        "See debug_post_login.png and check the selector."
    )


async def find_vivis_date(page: Page) -> date | None:
    """
    Read the two-column table on the 'Dates available for scheduling' page.
    Find the row whose Service cell contains VIVIS / TOURISM VISA keywords,
    then parse and return the date in the adjacent 'First available date' cell.
    """
    await pause(500, 1000)

    # Each row: <tr><td>Service name</td><td>First available date</td></tr>
    rows = await page.query_selector_all("table tr")

    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 2:
            continue

        service_text = (await cells[0].inner_text()).strip().upper()
        date_text    = (await cells[1].inner_text()).strip()

        if service_text == "VISIT VISA (VIVIS) - TOURISM VISA":
            print(f"[+] Found row  : {(await cells[0].inner_text()).strip()}")
            print(f"    Date text  : {date_text}")
            parsed = parse_date(date_text)
            if parsed:
                return parsed
            else:
                print(f"[!] Could not parse date: {date_text!r}")
                return None

    # Nothing matched — save a screenshot for inspection
    await page.screenshot(path="debug_table.png")
    print(
        "[!] VIVIS row not found in table.\n"
        "    Screenshot saved as debug_table.png.\n"
        "    Check VIVIS_KEYWORDS at the top of the script."
    )
    return None


# ── Main cycle ────────────────────────────────────────────────────────────────

async def run_once():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-infobars",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Africa/Cairo",
        )
        # Remove the webdriver fingerprint
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)

        page = await context.new_page()
        try:
            await login(page)
            await go_to_available_dates(page)
            vivis_date = await find_vivis_date(page)

            if vivis_date is None:
                print("[i] Could not determine VIVIS date this run.")
            elif vivis_date < TARGET_DATE:
                notify(vivis_date)
            else:
                print(
                    f"[i] No early slot yet.\n"
                    f"    VIVIS first available : {vivis_date}\n"
                    f"    Your target           : before {TARGET_DATE}"
                )
        finally:
            await pause(800, 1500)
            await browser.close()


async def run_loop():
    print(
        f"[*] Loop mode — checking every {CHECK_INTERVAL_MINUTES} min. "
        "Press Ctrl-C to stop."
    )
    while True:
        print(f"\n[*] Check at {datetime.now().strftime('%H:%M:%S')}")
        try:
            await run_once()
        except Exception as exc:
            print(f"[!] Check failed (will retry next cycle): {exc}")
        print(f"[i] Sleeping {CHECK_INTERVAL_MINUTES} min ...")
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    if "--loop" in sys.argv:
        asyncio.run(run_loop())
    else:
        asyncio.run(run_once())
