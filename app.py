"""Form Filler Application.

Desktop app to pull client data from OnePageCRM
and auto-fill provider application forms.

Opens in a native desktop window using pywebview.
"""

import os
import sys
import threading
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify, send_file

from config import TEMPLATES_DIR, OUTPUT_DIR, init_app_data

# Extract bundled resources next to the .exe on first run
init_app_data()

from crm_client import list_all_contacts, get_contact
from pdf_filler import fill_form, get_available_forms
from db import (
    save_contacts,
    search_contacts_local,
    list_contacts_local,
    get_contact_local,
    get_contact_count,
    get_last_sync,
)

app = Flask(__name__)

TEMPLATE_PATH = TEMPLATES_DIR / "index.html"


@app.route("/")
def index():
    return render_template_string(TEMPLATE_PATH.read_text())


@app.route("/api/forms")
def api_forms():
    return jsonify(get_available_forms())


@app.route("/api/sync-info")
def api_sync_info():
    return jsonify({"count": get_contact_count(), "last_sync": get_last_sync()})


@app.route("/api/sync", methods=["POST"])
def api_sync():
    """Sync all contacts from OnePageCRM to local SQLite."""
    try:
        contacts = list_all_contacts()
        save_contacts(contacts)
        return jsonify({"count": len(contacts)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/contacts/search")
def api_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    return jsonify(search_contacts_local(query))


@app.route("/api/contacts/local")
def api_contacts_local():
    return jsonify(list_contacts_local())


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    contact_id = data.get("contact_id", "")
    mapping_file = data.get("form", "")

    if not contact_id or not mapping_file:
        return jsonify({"error": "Missing contact or form selection"}), 400

    # Try local first, fall back to API
    contact = get_contact_local(contact_id)
    if not contact:
        contact = get_contact(contact_id)

    try:
        output_path = fill_form(mapping_file, contact)
        filename = Path(output_path).name
        return jsonify({"filename": filename, "path": output_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download(filename):
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        return "File not found", 404
    return send_file(str(filepath), as_attachment=True)


def main():
    import webview

    port = 8080

    # Start Flask in a background thread
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False),
        daemon=True,
    )
    server.start()

    # Open a native desktop window
    webview.create_window(
        "AutoFill - YourFinance.ie",
        f"http://127.0.0.1:{port}",
        width=1100,
        height=750,
        min_size=(800, 500),
    )
    webview.start()


if __name__ == "__main__":
    main()
