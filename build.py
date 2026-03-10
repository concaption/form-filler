"""Build script to create a Windows .exe using PyInstaller.

Run this on a Windows machine:
    pip install pyinstaller
    python build.py

On first launch, AutoFill.exe creates an 'AutoFill_Data' folder
next to itself containing:
    pdfs/             - Source PDF form templates
    field_mappings/   - JSON field mapping configs (editable)
    templates/        - HTML UI template
    output/           - Generated filled PDFs
    contacts.db       - Local contact cache

Users can edit field_mappings/*.json or replace PDFs directly.
Existing user edits are never overwritten on subsequent launches.
"""

import PyInstaller.__main__
import os
from pathlib import Path

ROOT = Path(__file__).parent

PyInstaller.__main__.run([
    str(ROOT / "app.py"),
    "--name=AutoFill",
    "--onefile",
    "--windowed",
    "--icon=NONE",
    # Bundle resources (extracted to AutoFill_Data/ on first run)
    f"--add-data={ROOT / 'pdfs'}{os.pathsep}pdfs",
    f"--add-data={ROOT / 'field_mappings'}{os.pathsep}field_mappings",
    f"--add-data={ROOT / 'templates'}{os.pathsep}templates",
    # Hidden imports
    "--hidden-import=flask",
    "--hidden-import=PyPDF2",
    "--hidden-import=requests",
    "--hidden-import=dotenv",
    "--hidden-import=webview",
    "--hidden-import=config",
    "--clean",
    "--noconfirm",
])

print("\nBuild complete! Find AutoFill.exe in the 'dist' folder.")
print("On first launch it creates 'AutoFill_Data' with editable PDFs and mappings.")
