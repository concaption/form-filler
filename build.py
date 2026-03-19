"""Build script to create a Windows .exe using PyInstaller.

Run this on a Windows machine:
    pip install pyinstaller
    python build.py

On first launch, AutoFill.exe creates an 'AutoFill_Data' folder
next to itself containing:
    src/pdfs/             - Source PDF form templates
    src/fieldmaps/        - JSON field mapping configs (editable)
    src/fieldmaps_pdfs/   - Field-map reference PDFs
    templates/            - HTML UI template
    output/               - Generated filled PDFs
    contacts.db           - Local contact cache

Users can edit src/fieldmaps/*.json or replace PDFs directly.
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
    f"--add-data={ROOT / 'src' / 'pdfs'}{os.pathsep}src/pdfs",
    f"--add-data={ROOT / 'src' / 'fieldmaps'}{os.pathsep}src/fieldmaps",
    f"--add-data={ROOT / 'src' / 'fieldmaps_pdfs'}{os.pathsep}src/fieldmaps_pdfs",
    f"--add-data={ROOT / 'templates'}{os.pathsep}templates",
    # Hidden imports
    "--hidden-import=customtkinter",
    "--hidden-import=PyPDF2",
    "--hidden-import=requests",
    "--hidden-import=dotenv",
    "--hidden-import=config",
    "--hidden-import=web_app",
    "--hidden-import=generate_field_maps",
    "--hidden-import=uvicorn",
    "--hidden-import=fastapi",
    "--hidden-import=sse_starlette",
    "--hidden-import=reportlab",
    "--hidden-import=python_multipart",
    "--hidden-import=multipart",
    "--clean",
    "--noconfirm",
])

print("\nBuild complete! Find AutoFill.exe in the 'dist' folder.")
print("On first launch it creates 'AutoFill_Data' with editable PDFs and mappings.")
