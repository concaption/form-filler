"""Form Filler Web Application.

Simple local web UI to pull client data from OnePageCRM
and auto-fill provider application forms.
"""

import os
import sys
import webbrowser
import threading
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify, send_file

# Ensure we're running from the project directory
os.chdir(Path(__file__).parent)

from crm_client import search_contacts, list_all_contacts, get_contact
from pdf_filler import fill_form, get_available_forms, OUTPUT_DIR

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Form Filler - Your Finance</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #333; }
  .container { max-width: 900px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 28px; color: #1a1a2e; margin-bottom: 4px; }
  .subtitle { color: #666; margin-bottom: 24px; font-size: 14px; }
  .card { background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { font-size: 16px; color: #444; margin-bottom: 12px;
             border-bottom: 2px solid #e8e8e8; padding-bottom: 8px; }
  .search-row { display: flex; gap: 8px; }
  .search-row input { flex: 1; padding: 10px 14px; border: 1px solid #ddd;
                      border-radius: 6px; font-size: 14px; outline: none; }
  .search-row input:focus { border-color: #4a90d9; box-shadow: 0 0 0 2px rgba(74,144,217,0.2); }
  .btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px;
         cursor: pointer; font-weight: 500; transition: all 0.15s; }
  .btn-primary { background: #4a90d9; color: #fff; }
  .btn-primary:hover { background: #357abd; }
  .btn-secondary { background: #e8e8e8; color: #555; }
  .btn-secondary:hover { background: #ddd; }
  .btn-success { background: #27ae60; color: #fff; font-size: 16px; padding: 12px 32px; }
  .btn-success:hover { background: #219a52; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .contact-list { list-style: none; max-height: 200px; overflow-y: auto;
                  border: 1px solid #eee; border-radius: 6px; margin-top: 10px; }
  .contact-list li { padding: 10px 14px; border-bottom: 1px solid #f0f0f0;
                     cursor: pointer; font-size: 14px; transition: background 0.1s; }
  .contact-list li:hover { background: #f0f6ff; }
  .contact-list li.selected { background: #e3f0ff; font-weight: 500; }
  .contact-list li:last-child { border-bottom: none; }
  .details-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; font-size: 13px; }
  .details-grid .label { color: #888; }
  .details-grid .value { font-weight: 500; }
  .form-checks { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .form-checks label { display: flex; align-items: center; gap: 8px; font-size: 14px;
                        padding: 8px 10px; border-radius: 6px; cursor: pointer; }
  .form-checks label:hover { background: #f5f5f5; }
  .form-checks input[type=checkbox] { width: 18px; height: 18px; accent-color: #4a90d9; }
  .status { margin-top: 12px; padding: 10px 14px; border-radius: 6px;
            font-size: 13px; display: none; }
  .status.info { display: block; background: #e8f4fd; color: #2980b9; }
  .status.success { display: block; background: #eafaf1; color: #27ae60; }
  .status.error { display: block; background: #fdedec; color: #e74c3c; }
  .output-files { margin-top: 10px; }
  .output-files a { display: inline-block; margin: 4px 8px 4px 0; padding: 6px 12px;
                    background: #f0f6ff; color: #4a90d9; border-radius: 4px;
                    text-decoration: none; font-size: 13px; }
  .output-files a:hover { background: #d9eaff; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff;
             border-top-color: transparent; border-radius: 50%;
             animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .empty { color: #999; font-style: italic; padding: 20px; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <h1>Form Filler</h1>
  <p class="subtitle">Pull client data from OnePageCRM and auto-fill application forms</p>

  <!-- 1. Search -->
  <div class="card">
    <h2>1. Select Client</h2>
    <div class="search-row">
      <input type="text" id="searchInput" placeholder="Search client name..."
             onkeydown="if(event.key==='Enter') doSearch()">
      <button class="btn btn-primary" id="searchBtn" onclick="doSearch()">Search</button>
      <button class="btn btn-secondary" id="loadAllBtn" onclick="loadAll()">Load All</button>
    </div>
    <ul class="contact-list" id="contactList">
      <li class="empty">Search for a client to begin</li>
    </ul>
  </div>

  <!-- 2. Details -->
  <div class="card" id="detailsCard" style="display:none">
    <h2>2. Client Details</h2>
    <div class="details-grid" id="detailsGrid"></div>
  </div>

  <!-- 3. Forms -->
  <div class="card" id="formsCard" style="display:none">
    <h2>3. Select Forms to Fill</h2>
    <div class="form-checks" id="formChecks"></div>
  </div>

  <!-- Generate -->
  <div id="generateSection" style="display:none; text-align:center; margin: 20px 0;">
    <button class="btn btn-success" id="generateBtn" onclick="generateForms()">
      Generate Forms
    </button>
  </div>

  <!-- Status -->
  <div class="status" id="statusBar"></div>
  <div class="output-files" id="outputFiles"></div>
</div>

<script>
let contacts = [];
let selectedContact = null;
let forms = [];

// Load available forms on page load
fetch('/api/forms').then(r => r.json()).then(data => {
  forms = data;
  const container = document.getElementById('formChecks');
  forms.forEach(f => {
    const label = document.createElement('label');
    label.innerHTML = '<input type="checkbox" checked value="' + f.mapping_file + '"> ' +
                      '<span><strong>' + f.provider + '</strong> ' + f.product + '</span>';
    container.appendChild(label);
  });
});

function setStatus(msg, type) {
  const bar = document.getElementById('statusBar');
  bar.className = 'status ' + type;
  bar.textContent = msg;
}

function doSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) return;
  setStatus('Searching...', 'info');
  document.getElementById('searchBtn').disabled = true;
  fetch('/api/search?q=' + encodeURIComponent(query))
    .then(r => r.json())
    .then(data => { contacts = data; renderContacts(); })
    .catch(e => setStatus('Search failed: ' + e, 'error'))
    .finally(() => { document.getElementById('searchBtn').disabled = false; });
}

function loadAll() {
  setStatus('Loading all contacts...', 'info');
  document.getElementById('loadAllBtn').disabled = true;
  fetch('/api/contacts')
    .then(r => r.json())
    .then(data => { contacts = data; renderContacts(); })
    .catch(e => setStatus('Load failed: ' + e, 'error'))
    .finally(() => { document.getElementById('loadAllBtn').disabled = false; });
}

function renderContacts() {
  const list = document.getElementById('contactList');
  list.innerHTML = '';
  if (contacts.length === 0) {
    list.innerHTML = '<li class="empty">No contacts found</li>';
    setStatus('No contacts found.', 'info');
    return;
  }
  contacts.forEach((c, i) => {
    const li = document.createElement('li');
    li.textContent = c.full_name + '  |  ' + (c.email || '') + '  |  ' + (c.company_name || '');
    li.onclick = () => selectContact(i);
    list.appendChild(li);
  });
  setStatus('Found ' + contacts.length + ' contact(s). Click one to select.', 'info');
}

function selectContact(idx) {
  selectedContact = contacts[idx];
  // Highlight
  document.querySelectorAll('.contact-list li').forEach((li, i) => {
    li.className = i === idx ? 'selected' : '';
  });
  // Show details
  const grid = document.getElementById('detailsGrid');
  grid.innerHTML = '';
  const fields = [
    ['Name', 'full_name'], ['Title', 'title'], ['DOB', 'date_of_birth'],
    ['PPS Number', 'pps_number'], ['Email', 'email'], ['Mobile', 'phone_mobile'],
    ['Address', 'address_full'], ['Occupation', 'occupation'],
    ['Employer', 'employer_name'], ['Marital Status', 'marital_status'],
    ['Employment', 'employment_type'], ['Annual Income', 'annual_income'],
    ['NRA', 'normal_retirement_age'], ['Nationality', 'nationality'],
    ['IBAN', 'iban'], ['BIC', 'bic']
  ];
  fields.forEach(([label, key]) => {
    const val = selectedContact[key] || '';
    if (val) {
      grid.innerHTML += '<span class="label">' + label + '</span><span class="value">' + val + '</span>';
    }
  });
  document.getElementById('detailsCard').style.display = '';
  document.getElementById('formsCard').style.display = '';
  document.getElementById('generateSection').style.display = '';
  setStatus('Selected: ' + selectedContact.full_name, 'info');
}

function generateForms() {
  if (!selectedContact) return;
  const checked = [];
  document.querySelectorAll('#formChecks input:checked').forEach(cb => {
    checked.push(cb.value);
  });
  if (checked.length === 0) { setStatus('Select at least one form.', 'error'); return; }

  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating...';
  setStatus('Generating forms...', 'info');
  document.getElementById('outputFiles').innerHTML = '';

  fetch('/api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ contact_id: selectedContact.id, forms: checked })
  })
  .then(r => r.json())
  .then(data => {
    if (data.results && data.results.length > 0) {
      setStatus('Generated ' + data.results.length + ' form(s) successfully!', 'success');
      const div = document.getElementById('outputFiles');
      data.results.forEach(r => {
        const a = document.createElement('a');
        a.href = '/download/' + encodeURIComponent(r.filename);
        a.textContent = r.filename;
        a.target = '_blank';
        div.appendChild(a);
      });
    }
    if (data.errors && data.errors.length > 0) {
      setStatus('Errors: ' + data.errors.join(', '), 'error');
    }
  })
  .catch(e => setStatus('Generation failed: ' + e, 'error'))
  .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forms'; });
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/forms")
def api_forms():
    return jsonify(get_available_forms())


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    return jsonify(search_contacts(query))


@app.route("/api/contacts")
def api_contacts():
    return jsonify(list_all_contacts())


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    contact_id = data.get("contact_id", "")
    form_list = data.get("forms", [])

    if not contact_id or not form_list:
        return jsonify({"errors": ["Missing contact_id or forms"]}), 400

    contact = get_contact(contact_id)
    results = []
    errors = []

    for mapping_file in form_list:
        try:
            output_path = fill_form(mapping_file, contact)
            filename = Path(output_path).name
            results.append({"filename": filename, "path": output_path})
        except Exception as e:
            errors.append(f"{mapping_file}: {e}")

    return jsonify({"results": results, "errors": errors})


@app.route("/download/<filename>")
def download(filename):
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        return "File not found", 404
    return send_file(str(filepath), as_attachment=True)


def main():
    port = 8080
    url = f"http://localhost:{port}"
    print(f"\n  Form Filler running at: {url}\n")
    # Auto-open browser after a short delay
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
