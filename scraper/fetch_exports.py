"""Download the 5 Planting Report CSVs from greentnmission.com/Export.

Reuses the logged-in browser profile created by login.py (headless).
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / ".browser_profile"
RAW_DIR = ROOT / "data" / "raw"
EXPORT_URL = "https://www.greentnmission.com/Export"

# department key -> (modal id, form id) on the Export page
DEPARTMENTS = {
    "forest": ("exportModalForest", "exportFormForest"),
    "coastal_habitat": ("exportModalCh", "exportFormCh"),
    "other_dept": ("exportModalOther", "exportFormOther"),
    "plant_a_tree": ("exportModalPat", "exportFormPat"),
    "agriculture": ("exportModalAgri", "exportFormAgri"),
}


class SessionExpired(Exception):
    pass


def fetch_all(headless=True):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, accept_downloads=True
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            _open_export(page)

            for key, (modal_id, form_id) in DEPARTMENTS.items():
                if key == "agriculture":
                    # Agri CSV has no year column, so export one file per year
                    years = page.eval_on_selector_all(
                        f"#{form_id} select[name=year_id] option",
                        "os => os.map(o => [o.value, o.textContent.trim()]).filter(o => o[0] !== 'all')",
                    )
                    for value, label in years:
                        files[f"{key}|{label}"] = _download(
                            page, modal_id, form_id, f"{key}_{label}", {"year_id": value}
                        )
                else:
                    files[key] = _download(page, modal_id, form_id, key)
        finally:
            ctx.close()
    return files


def _open_export(page):
    page.goto(EXPORT_URL, wait_until="domcontentloaded", timeout=90_000)
    if "login" in page.url.lower():
        raise SessionExpired("Not logged in - run scraper/login.py")
    page.wait_for_selector('[data-target="#exportModalForest"]', timeout=60_000)


def _download(page, modal_id, form_id, name, selects=None):
    page.click(f'[data-target="#{modal_id}"]')
    page.wait_for_selector(f"#{modal_id}", state="visible")
    for field, value in (selects or {}).items():
        page.select_option(f"#{form_id} select[name={field}]", value)
    with page.expect_download(timeout=300_000) as dl:
        page.click(f"#{form_id} button[type=submit]")
    target = RAW_DIR / f"{name}.csv"
    dl.value.save_as(target)
    print(f"  {name}: {target.stat().st_size:,} bytes")
    _open_export(page)
    return target


if __name__ == "__main__":
    fetch_all()
