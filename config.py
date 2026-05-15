"""Application path configuration.

In development: all paths resolve to the project directory.
When frozen (PyInstaller .exe): bundled resources are copied to an
'AutoFill_Data' folder next to the .exe on first run, so users can
browse and edit PDFs, field mappings, and templates directly.
"""

import sys
import shutil
from pathlib import Path

APP_VERSION = "2.2.3"

if getattr(sys, "frozen", False):
    # PyInstaller .exe — data lives next to the executable
    APP_DIR = Path(sys.executable).parent / "AutoFill_Data"
    _BUNDLE_DIR = Path(sys._MEIPASS)
else:
    # Development
    APP_DIR = Path(__file__).parent
    _BUNDLE_DIR = None

SRC_DIR = APP_DIR / "src"
MAPPINGS_DIR = SRC_DIR / "fieldmaps"
PDFS_DIR = SRC_DIR / "pdfs"
FIELDMAPS_PDFS_DIR = SRC_DIR / "fieldmaps_pdfs"
TEMPLATES_DIR = APP_DIR / "templates"
OUTPUT_DIR = APP_DIR / "output"
DB_PATH = APP_DIR / "contacts.db"


def init_app_data():
    """Copy bundled resources to the local data folder on every .exe launch.

    Bundled files (PDFs, fieldmaps, templates, advisers.json) are always
    refreshed from the .exe bundle so app upgrades actually reach users.
    Files the user added manually (e.g. a custom fieldmap they authored via
    the Mapping Tool) are NOT touched — only paths that exist in the bundle
    get overwritten.
    """
    if _BUNDLE_DIR is None:
        return

    APP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    for dirname in ("src/pdfs", "src/fieldmaps", "src/fieldmaps_pdfs", "templates"):
        dest = APP_DIR / dirname
        src = _BUNDLE_DIR / dirname
        if not src.exists():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        # Always overwrite every bundled file. User-added files (not in the
        # bundle) are preserved automatically since we only iterate bundle files.
        for src_file in src.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(src)
                dest_file = dest / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dest_file))

    # Individual files at src/ root (e.g. advisers.json) — always refresh.
    for filename in ("advisers.json",):
        src_file = _BUNDLE_DIR / "src" / filename
        dest_file = SRC_DIR / filename
        if src_file.exists():
            SRC_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dest_file))
