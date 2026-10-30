"""Scheduled job: download exports -> build summary.json -> publish.

Run every 30 minutes by Windows Task Scheduler (see setup_schedule.ps1).
Publishing is a git commit + push of docs/summary.json (served by GitHub Pages).
"""
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_summary import OUT_FILE, build  # noqa: E402
from fetch_exports import SessionExpired, fetch_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "logs" / "run.log"

LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("run")


def notify(title, message):
    """Windows toast notification (best effort)."""
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        f"$t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('{title}')) > $null;"
        f"$t.GetElementsByTagName('text')[1].AppendChild($t.CreateTextNode('{message}')) > $null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Geotag Dashboard').Show("
        "[Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def publish():
    if not (ROOT / ".git").exists() or not git("remote").stdout.strip():
        log.info("No git remote - skipping publish")
        return
    # Only the generated summary is committed automatically
    if not git("status", "--porcelain", "--", str(OUT_FILE)).stdout.strip():
        log.info("No data change - nothing to publish")
        return
    git("commit", "-m", "Update geotag summary", "--", str(OUT_FILE))
    result = git("push")
    if result.returncode != 0:
        raise RuntimeError(f"git push failed: {result.stderr.strip()}")
    log.info("Published to GitHub")


def main():
    log.info("Run started")
    try:
        fetch_all()
        summary = build()
        total = sum(r[3] for r in summary["rows"])
        log.info("Summary built: %s geotags -> %s", f"{total:,}", OUT_FILE)
        publish()
    except SessionExpired:
        log.error("Session expired - run scraper/login.py")
        notify("Geotag Dashboard", "Login expired. Run login.py and enter the captcha.")
        return 2
    except Exception:
        log.exception("Run failed")
        notify("Geotag Dashboard", "Update failed. See logs/run.log")
        return 1
    log.info("Run finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
