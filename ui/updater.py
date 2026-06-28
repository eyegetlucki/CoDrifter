"""
Auto-update checker for CoDrifter.
Checks GitHub Releases for a newer version, downloads the installer, and
runs it silently. All network/file I/O runs in daemon threads — never blocks UI.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal

from version import __version__

GITHUB_API_URL = "https://api.github.com/repos/eyegetlucki/CoDrifter/releases/latest"
CHECK_TIMEOUT = 8  # seconds


def _parse_version(tag: str) -> tuple:
    """Strip leading 'v' and return a comparable tuple, e.g. (1, 0, 1)."""
    return tuple(int(x) for x in tag.lstrip("v").split("."))


class UpdateChecker(QObject):
    update_available  = pyqtSignal(str, str)   # (new_version, download_url)
    up_to_date        = pyqtSignal()
    check_failed      = pyqtSignal()
    download_progress = pyqtSignal(int)         # 0–100
    download_ready    = pyqtSignal(str)         # path to installer on disk
    download_failed   = pyqtSignal(str)         # error message

    def check_async(self):
        threading.Thread(target=self._check, daemon=True).start()

    def download_async(self, url: str):
        threading.Thread(target=self._download, args=(url,), daemon=True).start()

    def install(self, installer_path: str):
        """Run the installer silently and quit the app. Safe during a session —
        closeEvent() stops the telemetry worker before the process exits."""
        try:
            subprocess.Popen(
                [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception:
            pass
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ── Internal ──────────────────────────────────────────────────────

    def _check(self):
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CoDrifter"},
            )
            with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            assets = data.get("assets", [])
            if not tag or not assets:
                self.check_failed.emit()
                return

            remote_ver = _parse_version(tag)
            local_ver  = _parse_version(__version__)

            if remote_ver <= local_ver:
                self.up_to_date.emit()
                return

            download_url = assets[0]["browser_download_url"]
            self.update_available.emit(tag.lstrip("v"), download_url)

        except Exception:
            self.check_failed.emit()

    def _download(self, url: str):
        try:
            dest_dir = os.path.join(tempfile.gettempdir(), "CoDrifter_update")
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, "CoDrifter_Setup.exe")

            def _progress(block_num, block_size, total_size):
                if total_size > 0:
                    pct = min(100, int(block_num * block_size * 100 / total_size))
                    self.download_progress.emit(pct)

            urllib.request.urlretrieve(url, dest, reporthook=_progress)
            self.download_progress.emit(100)
            self.download_ready.emit(dest)

        except Exception as e:
            self.download_failed.emit(str(e))
