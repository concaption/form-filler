"""Application path configuration.

In development: all paths resolve to the project directory.
When frozen (PyInstaller .exe): bundled resources are copied to an
'AutoFill_Data' folder next to the .exe on first run, so users can
browse and edit PDFs, field mappings, and templates directly.
"""

import sys
import shutil
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller .exe — data lives next to the executable
    APP_DIR = Path(sys.executable).parent / "AutoFill_Data"
    _BUNDLE_DIR = Path(sys._MEIPASS)
else:
    # Development
    APP_DIR = Path(__file__).parent
    _BUNDLE_DIR = None

MAPPINGS_DIR = APP_DIR / "field_mappings"
PDFS_DIR = APP_DIR / "pdfs"
TEMPLATES_DIR = APP_DIR / "templates"
OUTPUT_DIR = APP_DIR / "output"
DB_PATH = APP_DIR / "contacts.db"


def init_app_data():
    """Copy bundled resources to the local data folder on first run.

    Only runs when packaged as a .exe. Existing files are never
    overwritten so user edits are preserved.
    """
    if _BUNDLE_DIR is None:
        return

    APP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    for dirname in ("pdfs", "field_mappings", "templates"):
        dest = APP_DIR / dirname
        src = _BUNDLE_DIR / dirname
        if not src.exists():
            continue
        if not dest.exists():
            # First run — copy the whole directory
            shutil.copytree(str(src), str(dest))
        else:
            # Subsequent runs — add any NEW files (don't overwrite edits)
            for src_file in src.rglob("*"):
                if src_file.is_file():
                    rel = src_file.relative_to(src)
                    dest_file = dest / rel
                    if not dest_file.exists():
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(src_file), str(dest_file))
