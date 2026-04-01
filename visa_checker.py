#!/usr/bin/env python3
"""
Brazilian Consulate Cairo — Appointment Date Checker
Monitors available dates for VISIT VISA (VIVIS) / Tourism Visa.
Alerts you when a slot earlier than June 20 2026 appears.

Usage:
    python visa_checker.py              # single check
    python visa_checker.py --loop       # check every CHECK_INTERVAL_MINUTES minutes
"""

import asyncio
import random
import sys
from datetime import date, datetime

from playwright.async_api import Page, async_playwright

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  ← fill in your credentials here
# ──────────────────────────────────────────────────────────────────────────────
USERNAME = "YOUR_USERNAME"
PASSWORD = "YOUR_PASSWORD"

TARGET_DATE = date(2026, 6, 20)          # alert if any date is BEFORE this
BASE_URL    = "https://ec-cairo.itamaraty.gov.br/"
CHECK_INTERVAL_MINUTES = 15              # loop mode: minutes between checks
HEADLESS = False                         # False = visible browser (recommended while tuning)
# ──────────────────────────────────────────────────────────────────────────────


# ── Human-like helpers ────────────────────────────────────────────────────────

async def pause(min_ms: float = 400, max_ms: float = 1400):
    """Random pause mimicking human reaction time."""
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


async def human_type(page: Page, selector: str, text: str):
    """Click a field and type character-by-character at human speed."""
    el = await page.wait_for_selector(selector, timeout=15_000)
    await el.click()
    await pause(200, 500)
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(random.uniform(0.06, 0.20))   # 60-200 ms per key
    await pause(200, 600)


async def human_click(page: Page, selector: str, timeout: int = 15_000):
    """Move mouse to element and click slightly off-centre."""
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

def notify(message: str):
    """Print a prominent alert; optionally fire a desktop notification."""
    border = "═" * 64
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{border}")
    print(f"  🚨  APPOINTMENT ALERT  🚨")
    print(f"  {message}")
    print(f"  {ts}")
    print(f"{border}\n")
    print("\a\a\a")   # terminal bell × 3

    # Optional desktop popup — install with: pip install plyer
    try:
        from plyer import notification as desktop
        desktop.notify(
            title="Consulate Appointment Available!",
            message=message,
            timeout=60,
        )
    except Exception:
        pass


# ── Date parsing ──────────────────────────────────────────────────────────────

def try_parse_date(text: str) -> date | None:
    """Return a date object if text looks like a date, else None."""
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
                "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ── Core logic ────────────────────────────────────────────────────────────────

async def login(page: Page):
    """Navigate to the site and log in."""
    print(f"[*] Opening {BASE_URL}")
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
    await pause(1500, 3000)

    # ── Locate username field ──────────────────────────────────────────────
    # Try several common selector patterns used by consulate portals.
    user_candidates = [
        "input[name='username']",
        "input[name='login']",
        "input[name='user']",
        "input[id='username']",
        "input[id='login']",
        "input[type='text']:first-of-type",
    ]
    user_sel = None
    for sel in user_candidates:
        if await page.query_selector(sel):
            user_sel = sel
            break
    if not user_sel:
        await page.screenshot(path="debug_login_page.png")
        raise RuntimeError("Cannot find username field — see debug_login_page.png")

    print("[*] Typing credentials ...")
    await human_type(page, user_sel, USERNAME)
    await pause(400, 900)
    await human_type(page, "input[type='password']", PASSWORD)
    await pause(600, 1200)

    # ── Click login button ─────────────────────────────────────────────────
    login_btn_candidates = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Entrar')",
        "button:has-text('Acessar')",
        "a:has-text('Login')",
    ]
    for sel in login_btn_candidates:
        if await page.query_selector(sel):
            await human_click(page, sel)
            break

    await page.wait_for_load_state("networkidle", timeout=25_000)
    await pause(1500, 2500)

    # Quick sanity-check: still on login page?
    if any(kw in page.url.lower() for kw in ("login", "senha", "signin")):
        await page.screenshot(path="debug_login_failed.png")
        raise RuntimeError(
            "Still on login page after submit — "
            "wrong credentials or CAPTCHA. See debug_login_failed.png"
        )
    print("[+] Logged in.")


async def navigate_to_available_dates(page: Page):
    """
    Find and click the 'Available Dates' section.
    Adjust selectors below if the page uses different labels.
    """
    await pause(800, 1600)

    candidates = [
        "text=Available Dates",
        "text=Datas Disponíveis",
        "text=Datas disponíveis",
        "text=Agendamento",
        "a[href*='available']",
        "a[href*='dates']",
        "a[href*='datas']",
        "a[href*='agendamento']",
        "a[href*='schedule']",
    ]

    for sel in candidates:
        try:
            await human_click(page, sel, timeout=5_000)
            print(f"[+] Navigated via: {sel}")
            await page.wait_for_load_state("networkidle", timeout=20_000)
            await pause(1000, 2000)
            return
        except Exception:
            continue

    await page.screenshot(path="debug_landing.png")
    raise RuntimeError(
        "Cannot find 'Available Dates' link — see debug_landing.png.\n"
        "Update the `candidates` list in navigate_to_available_dates()."
    )


async def select_visa_type(page: Page):
    """
    Find the visa-type dropdown and pick VIVIS / Tourism Visa.
    """
    # Look for a <select> that has a VIVIS or Tourism option
    selects = await page.query_selector_all("select")
    for sel_el in selects:
        options = await sel_el.eval_on_selector_all(
            "option",
            "els => els.map(e => ({value: e.value, text: e.textContent.trim()}))"
        )
        vivis = next(
            (o for o in options
             if any(kw in o["text"].upper()
                    for kw in ("VIVIS", "TOURISM", "TURISMO", "VISIT VISA"))),
            None
        )
        if vivis:
            handle = await sel_el.element_handle()
            box = await handle.bounding_box()
            if box:
                x = box["x"] + box["width"]  * 0.5
                y = box["y"] + box["height"] * 0.5
                await page.mouse.move(x, y, steps=15)
                await pause(150, 400)
            await sel_el.select_option(value=vivis["value"])
            print(f"[+] Selected visa type: {vivis['text']}")
            await pause(600, 1200)

            # Hit search / filter button if present
            for btn_sel in [
                "button[type='submit']",
                "button:has-text('Search')",
                "button:has-text('Buscar')",
                "button:has-text('Consultar')",
                "button:has-text('Filter')",
                "input[type='submit']",
            ]:
                if await page.query_selector(btn_sel):
                    await human_click(page, btn_sel)
                    await page.wait_for_load_state("networkidle", timeout=20_000)
                    await pause(800, 1600)
                    break
            return

    # If no dropdown found, maybe the page already shows only one visa type,
    # or the selection is done differently (radio buttons, links, etc.)
    print("[i] No visa-type dropdown found — continuing without filtering.")


async def extract_dates(page: Page) -> list[date]:
    """
    Pull date values from whatever elements the results page uses.
    Returns a list of parsed date objects.
    """
    await pause(800, 1500)

    # Grab text from cells, list items, and elements whose class hints at dates
    raw_texts: list[str] = await page.eval_on_selector_all(
        "td, li, "
        "[class*='date'], [class*='data'], [class*='slot'], "
        "[class*='available'], [class*='calendar'], "
        "[data-date], [data-day]",
        """els => els.flatMap(el => {
            const d = el.getAttribute('data-date') || el.getAttribute('data-day');
            return d ? [d, el.textContent.trim()] : [el.textContent.trim()];
        })"""
    )

    found: list[date] = []
    for t in raw_texts:
        d = try_parse_date(t)
        if d:
            found.append(d)

    # De-duplicate while preserving order
    seen: set[date] = set()
    unique: list[date] = []
    for d in found:
        if d not in seen:
            seen.add(d)
            unique.append(d)

    if not unique:
        await page.screenshot(path="debug_dates_page.png")
        print(
            "[!] No dates extracted. Screenshot saved as debug_dates_page.png.\n"
            "    Inspect it and update the selectors in extract_dates()."
        )
    else:
        print(f"[+] Dates found: {', '.join(str(d) for d in sorted(unique))}")

    return unique


# ── Main cycle ────────────────────────────────────────────────────────────────

async def run_once():
    """One complete check: login → navigate → select visa → extract → alert."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized",
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

        # Remove the webdriver flag so the site can't tell it's Playwright
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
        """)

        page = await context.new_page()

        try:
            await login(page)
            await navigate_to_available_dates(page)
            await select_visa_type(page)
            dates = await extract_dates(page)

            if not dates:
                print("[i] No available dates found for VIVIS / Tourism Visa.")
                return

            early = sorted(d for d in dates if d < TARGET_DATE)
            if early:
                notify(
                    f"Slot available before {TARGET_DATE}!\n"
                    f"  Earliest: {early[0]}\n"
                    f"  All early dates: {', '.join(str(d) for d in early)}"
                )
            else:
                soonest = min(dates)
                print(
                    f"[i] No dates before {TARGET_DATE}. "
                    f"Soonest available: {soonest}"
                )

        except Exception as exc:
            print(f"[!] Error during check: {exc}")
            raise

        finally:
            await pause(800, 1500)
            await browser.close()


async def run_loop():
    """Repeat run_once() on a schedule."""
    print(
        f"[*] Loop mode — checking every {CHECK_INTERVAL_MINUTES} min. "
        f"Press Ctrl-C to stop."
    )
    while True:
        print(f"\n[*] Check at {datetime.now().strftime('%H:%M:%S')}")
        try:
            await run_once()
        except Exception as exc:
            print(f"[!] Check failed (will retry): {exc}")
        print(f"[i] Sleeping {CHECK_INTERVAL_MINUTES} min ...")
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--loop" in sys.argv:
        asyncio.run(run_loop())
    else:
        asyncio.run(run_once())
