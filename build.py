"""Build script to create a Windows .exe using PyInstaller.

Run this on a Windows machine:
    pip install pyinstaller
    python build.py
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
    # Bundle the PDF templates and field mappings
    f"--add-data={ROOT / 'pdfs'}{os.pathsep}pdfs",
    f"--add-data={ROOT / 'field_mappings'}{os.pathsep}field_mappings",
    f"--add-data={ROOT / 'templates'}{os.pathsep}templates",
    # Hidden imports
    "--hidden-import=flask",
    "--hidden-import=PyPDF2",
    "--hidden-import=requests",
    "--hidden-import=dotenv",
    "--clean",
    "--noconfirm",
])

print("\nBuild complete! Find AutoFill.exe in the 'dist' folder.")
