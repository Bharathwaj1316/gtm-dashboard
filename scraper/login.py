"""One-time login to greentnmission.com.

Opens a visible browser. You log in (username, password, captcha) yourself.
The session is kept in a persistent browser profile so the scheduled
scraper can reuse it headless.
"""
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / ".browser_profile"
DEBUG_DIR = ROOT / "scraper" / "debug"
EXPORT_URL = "https://www.greentnmission.com/Export"


def main():
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        _goto(page, EXPORT_URL)

        print("Log in in the browser window (choose your login type, enter the captcha).")
        print("Waiting up to 10 minutes...")
        # Logged in once /Export loads without bouncing to a login page
        for _ in range(120):
            page.wait_for_timeout(5000)
            if "login" in page.url.lower():
                continue
            _goto(page, EXPORT_URL)
            if "login" not in page.url.lower():
                page.wait_for_selector('[data-target="#exportModalForest"]', timeout=60_000)
                break
        else:
            raise SystemExit("Timed out waiting for login.")

        (DEBUG_DIR / "export_page.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(DEBUG_DIR / "export_page.png"), full_page=True)
        print("Logged in. Session saved to", PROFILE_DIR)
        ctx.close()


def _goto(page, url):
    # The site redirects to /Web/login mid-navigation, which aborts goto()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    except Error:
        page.wait_for_load_state("domcontentloaded")


if __name__ == "__main__":
    main()
