"""AutoFill Application — YourFinance.ie

Native desktop app built with CustomTkinter.
Syncs contacts from OnePageCRM and fills PDF application forms.
"""

import os
import sys
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from config import OUTPUT_DIR, init_app_data

# Extract bundled resources next to the .exe on first run
init_app_data()

from crm_client import list_all_contacts, iter_all_contacts, get_contact
from pdf_filler import fill_form, get_available_forms
from db import (
    save_contacts,
    search_contacts_local,
    list_contacts_local,
    get_contact_local,
    get_contact_count,
    get_last_sync,
)

# ─── Theme ───
NAVY = "#0f2b46"
NAVY_LIGHT = "#163d5e"
GREEN = "#059669"
GREEN_DARK = "#047857"
BLUE = "#2563eb"
WHITE = "#ffffff"
GRAY_50 = "#f8fafc"
GRAY_100 = "#f1f5f9"
GRAY_200 = "#e2e8f0"
GRAY_400 = "#94a3b8"
GRAY_500 = "#64748b"
GRAY_700 = "#334155"
GRAY_800 = "#1e293b"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class AutoFillApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AutoFill - YourFinance.ie")
        self.geometry("1060x720")
        self.minsize(860, 580)
        self.configure(fg_color=GRAY_100)

        self.contacts = []
        self.selected_contact = None
        self.forms = []
        self.search_after_id = None

        self._build_header()
        self._build_body()
        self._build_status_bar()

        self._load_forms()
        self._refresh_sync_info()

    # ──────────────────────────────────────────
    # Header
    # ──────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=NAVY, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Brand
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=20)

        badge = ctk.CTkLabel(
            brand, text="YF", font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=GREEN, text_color=WHITE,
            width=34, height=34, corner_radius=8,
        )
        badge.pack(side="left", padx=(0, 10))

        title_frame = ctk.CTkFrame(brand, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(
            title_frame, text="YourFinance.ie",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text="AutoFill Application",
            font=ctk.CTkFont(size=11), text_color=GRAY_400,
        ).pack(anchor="w")

        # Right side: sync + settings
        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.pack(side="right", padx=20)

        self.sync_label = ctk.CTkLabel(
            right_frame, text="", font=ctk.CTkFont(size=12),
            text_color=GRAY_400,
        )
        self.sync_label.pack(side="left", padx=(0, 12))

        self.sync_btn = ctk.CTkButton(
            right_frame, text="Sync Contacts", width=130, height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=NAVY_LIGHT, hover_color="#1e5278",
            command=self._sync_contacts,
        )
        self.sync_btn.pack(side="left")

        settings_btn = ctk.CTkButton(
            right_frame, text="Settings", width=90, height=32,
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color="#1e5278",
            text_color=GRAY_400, border_width=1, border_color=GRAY_500,
            command=self._open_settings,
        )
        settings_btn.pack(side="left", padx=(8, 0))

    # ──────────────────────────────────────────
    # Body — two-column layout
    # ──────────────────────────────────────────
    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 0))

        # Left column: search + contact list
        left = ctk.CTkFrame(body, fg_color=WHITE, corner_radius=12, border_width=1, border_color=GRAY_200)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        left_inner = ctk.CTkFrame(left, fg_color="transparent")
        left_inner.pack(fill="both", expand=True, padx=16, pady=16)

        # Section title
        ctk.CTkLabel(
            left_inner, text="Find Client",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=GRAY_800,
        ).pack(anchor="w")

        # Search row
        search_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        search_row.pack(fill="x", pady=(10, 0))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.search_entry = ctk.CTkEntry(
            search_row, textvariable=self.search_var,
            placeholder_text="Search by name, email or company...",
            height=38, font=ctk.CTkFont(size=13),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            search_row, text="Show All", width=80, height=38,
            font=ctk.CTkFont(size=12), fg_color=GRAY_200,
            hover_color=GRAY_400, text_color=GRAY_700,
            command=self._load_all_contacts,
        ).pack(side="right")

        # Contact list
        self.contact_list_frame = ctk.CTkScrollableFrame(
            left_inner, fg_color=GRAY_50, corner_radius=8,
            border_width=1, border_color=GRAY_200,
        )
        self.contact_list_frame.pack(fill="both", expand=True, pady=(12, 0))

        self.empty_label = ctk.CTkLabel(
            self.contact_list_frame,
            text="Sync contacts to get started\nClick 'Sync Contacts' in the top right",
            font=ctk.CTkFont(size=13), text_color=GRAY_400,
            justify="center",
        )
        self.empty_label.pack(pady=40)

        # Right column: details + form + generate
        right = ctk.CTkFrame(body, fg_color="transparent", width=380)
        right.pack(side="right", fill="both", padx=(10, 0))
        right.pack_propagate(False)

        # Details card
        self.details_card = ctk.CTkFrame(right, fg_color=WHITE, corner_radius=12, border_width=1, border_color=GRAY_200)
        self.details_card.pack(fill="x")

        details_inner = ctk.CTkFrame(self.details_card, fg_color="transparent")
        details_inner.pack(fill="x", padx=16, pady=16)

        self.details_title = ctk.CTkLabel(
            details_inner, text="Client Details",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=GRAY_800,
        )
        self.details_title.pack(anchor="w")

        self.details_content = ctk.CTkFrame(details_inner, fg_color="transparent")
        self.details_content.pack(fill="x", pady=(10, 0))

        self.no_selection_label = ctk.CTkLabel(
            self.details_content,
            text="Select a client from the list",
            font=ctk.CTkFont(size=13), text_color=GRAY_400,
        )
        self.no_selection_label.pack(pady=20)

        # Form select card
        form_card = ctk.CTkFrame(right, fg_color=WHITE, corner_radius=12, border_width=1, border_color=GRAY_200)
        form_card.pack(fill="x", pady=(12, 0))

        form_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        form_inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            form_inner, text="Application Form",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=GRAY_800,
        ).pack(anchor="w")

        self.form_var = ctk.StringVar(value="Choose a form template...")
        self.form_dropdown = ctk.CTkOptionMenu(
            form_inner, variable=self.form_var, values=["Loading..."],
            width=340, height=38, font=ctk.CTkFont(size=13),
            fg_color=GRAY_50, button_color=BLUE, button_hover_color="#1d4ed8",
            text_color=GRAY_700, dropdown_font=ctk.CTkFont(size=12),
        )
        self.form_dropdown.pack(fill="x", pady=(10, 0))

        # Generate button
        self.generate_btn = ctk.CTkButton(
            right, text="Fill & Download", height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=GREEN, hover_color=GREEN_DARK,
            command=self._fill_and_save,
        )
        self.generate_btn.pack(fill="x", pady=(16, 0))

        # Output card (hidden initially)
        self.output_card = ctk.CTkFrame(right, fg_color="#d1fae5", corner_radius=12, border_width=1, border_color="#a7f3d0")
        # Will be packed when there's output

        self.output_label = ctk.CTkLabel(
            self.output_card, text="", font=ctk.CTkFont(size=13),
            text_color=GREEN_DARK, wraplength=320, justify="left",
        )
        self.output_label.pack(padx=16, pady=(12, 4), anchor="w")

        self.open_folder_btn = ctk.CTkButton(
            self.output_card, text="Open Output Folder", height=32,
            font=ctk.CTkFont(size=12), fg_color=GREEN, hover_color=GREEN_DARK,
            command=self._open_output_folder,
        )
        self.open_folder_btn.pack(padx=16, pady=(4, 12), anchor="w")

    # ──────────────────────────────────────────
    # Status bar
    # ──────────────────────────────────────────
    def _build_status_bar(self):
        self.status_bar = ctk.CTkLabel(
            self, text="Ready", font=ctk.CTkFont(size=12),
            text_color=GRAY_500, fg_color=WHITE, height=30,
            corner_radius=0, anchor="w", padx=20,
        )
        self.status_bar.pack(fill="x", side="bottom")

    def _set_status(self, text, color=GRAY_500):
        self.status_bar.configure(text=text, text_color=color)

    # ──────────────────────────────────────────
    # Sync
    # ──────────────────────────────────────────
    def _refresh_sync_info(self):
        count = get_contact_count()
        last = get_last_sync()
        if count > 0 and last:
            try:
                dt = datetime.fromisoformat(last)
                formatted = dt.strftime("%d %b %Y, %H:%M")
            except Exception:
                formatted = last
            self.sync_label.configure(text=f"{count} contacts  |  {formatted}")
        else:
            self.sync_label.configure(text="No contacts synced")

    def _sync_contacts(self):
        self.sync_btn.configure(state="disabled", text="Syncing...")
        self._set_status("Syncing contacts from OnePageCRM...", BLUE)

        def do_sync():
            try:
                all_contacts = []
                for page, max_page, batch in iter_all_contacts():
                    all_contacts.extend(batch)
                    self.after(0, lambda p=page, m=max_page, n=len(all_contacts):
                        self._on_sync_progress(p, m, n))
                save_contacts(all_contacts)
                self.after(0, lambda: self._on_sync_done(len(all_contacts)))
            except Exception as e:
                self.after(0, lambda: self._on_sync_error(str(e)))

        threading.Thread(target=do_sync, daemon=True).start()

    def _on_sync_progress(self, page, max_page, fetched):
        self.sync_btn.configure(text=f"Page {page}/{max_page}")
        self._set_status(f"Syncing... Page {page}/{max_page} ({fetched} contacts)", BLUE)

    def _on_sync_done(self, count):
        self.sync_btn.configure(state="normal", text="Sync Contacts")
        self._refresh_sync_info()
        self._set_status(f"Synced {count} contacts successfully!", GREEN)

    def _on_sync_error(self, error):
        self.sync_btn.configure(state="normal", text="Sync Contacts")
        self._set_status(f"Sync failed: {error}", "#dc2626")

    # ──────────────────────────────────────────
    # Search & contact list
    # ──────────────────────────────────────────
    def _on_search_change(self, *_):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
        self.search_after_id = self.after(300, self._do_search)

    def _do_search(self):
        query = self.search_var.get().strip()
        if len(query) < 2:
            return
        self.contacts = search_contacts_local(query)
        self._render_contacts()

    def _load_all_contacts(self):
        self._set_status("Loading all contacts...", BLUE)
        self.contacts = list_contacts_local()
        self._render_contacts()
        if not self.contacts:
            self._set_status("No contacts found. Please sync first.", "#d97706")
        else:
            self._set_status(f"{len(self.contacts)} contacts loaded", GREEN)

    def _render_contacts(self):
        for widget in self.contact_list_frame.winfo_children():
            widget.destroy()

        if not self.contacts:
            ctk.CTkLabel(
                self.contact_list_frame, text="No contacts found",
                font=ctk.CTkFont(size=13), text_color=GRAY_400,
            ).pack(pady=40)
            return

        for i, c in enumerate(self.contacts):
            self._create_contact_row(c, i)

    def _create_contact_row(self, contact, index):
        row = ctk.CTkFrame(self.contact_list_frame, fg_color="transparent", height=50, cursor="hand2")
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8, pady=4)

        # Avatar
        name = contact.get("full_name", "?")
        parts = name.split()
        initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[0].upper()

        avatar = ctk.CTkLabel(
            inner, text=initials, width=36, height=36,
            corner_radius=18, fg_color=GRAY_200,
            font=ctk.CTkFont(size=12, weight="bold"), text_color=GRAY_500,
        )
        avatar.pack(side="left", padx=(4, 10))

        # Text
        text_frame = ctk.CTkFrame(inner, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame, text=name,
            font=ctk.CTkFont(size=13, weight="bold"), text_color=GRAY_800,
            anchor="w",
        ).pack(anchor="w")

        meta = contact.get("email", "")
        if contact.get("company_name"):
            meta += f"  |  {contact['company_name']}" if meta else contact["company_name"]
        if meta:
            ctk.CTkLabel(
                text_frame, text=meta,
                font=ctk.CTkFont(size=11), text_color=GRAY_400,
                anchor="w",
            ).pack(anchor="w")

        # Bind click to the whole row and all children
        for widget in [row, inner, avatar, text_frame] + text_frame.winfo_children():
            widget.bind("<Button-1>", lambda e, idx=index: self._select_contact(idx))

    def _select_contact(self, index):
        self.selected_contact = self.contacts[index]

        # Highlight selected row
        for i, child in enumerate(self.contact_list_frame.winfo_children()):
            if i == index:
                child.configure(fg_color=BLUE)
                for w in child.winfo_children():
                    for ww in w.winfo_children():
                        if isinstance(ww, ctk.CTkLabel):
                            ww.configure(text_color=WHITE)
                        if isinstance(ww, ctk.CTkFrame):
                            for www in ww.winfo_children():
                                if isinstance(www, ctk.CTkLabel):
                                    www.configure(text_color=WHITE)
            else:
                child.configure(fg_color="transparent")
                for w in child.winfo_children():
                    for ww in w.winfo_children():
                        if isinstance(ww, ctk.CTkLabel) and ww.cget("corner_radius") == 18:
                            ww.configure(text_color=GRAY_500)
                        elif isinstance(ww, ctk.CTkLabel):
                            ww.configure(text_color=GRAY_800)
                        if isinstance(ww, ctk.CTkFrame):
                            for www in ww.winfo_children():
                                if isinstance(www, ctk.CTkLabel):
                                    if www.cget("font").cget("weight") == "bold":
                                        www.configure(text_color=GRAY_800)
                                    else:
                                        www.configure(text_color=GRAY_400)

        self._show_details(self.selected_contact)
        self._set_status(f"Selected: {self.selected_contact['full_name']}", BLUE)

    # ──────────────────────────────────────────
    # Details panel
    # ──────────────────────────────────────────
    def _show_details(self, contact):
        for widget in self.details_content.winfo_children():
            widget.destroy()

        self.details_title.configure(text=contact.get("full_name", "Client Details"))

        fields = [
            ("Date of Birth", "date_of_birth"), ("PPS Number", "pps_number"),
            ("Email", "email"), ("Phone", "phone"),
            ("Address", "address_full"), ("Occupation", "occupation"),
            ("Employer", "employer_name"), ("Marital Status", "marital_status"),
            ("Employment", "employment_type"), ("Nationality", "nationality"),
            ("Annual Income", "annual_income"), ("Retirement Age", "normal_retirement_age"),
            ("IBAN", "iban"), ("BIC", "bic"),
        ]

        for label, key in fields:
            val = contact.get(key, "")
            if not val:
                continue

            row = ctk.CTkFrame(self.details_content, fg_color=GRAY_50, corner_radius=6, height=38)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ctk.CTkLabel(
                row, text=label.upper(), font=ctk.CTkFont(size=10),
                text_color=GRAY_400, width=100, anchor="w",
            ).pack(side="left", padx=(10, 4), pady=4)

            ctk.CTkLabel(
                row, text=str(val), font=ctk.CTkFont(size=12, weight="bold"),
                text_color=GRAY_800, anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(0, 10))

    # ──────────────────────────────────────────
    # Forms
    # ──────────────────────────────────────────
    def _load_forms(self):
        self.forms = get_available_forms()
        display_names = []
        for f in self.forms:
            provider = f.get("provider", "")
            product = f.get("product", f.get("form_name", ""))
            display_names.append(f"{provider} - {product}" if provider else product)

        if display_names:
            self.form_dropdown.configure(values=display_names)
            self.form_var.set("Choose a form template...")
        else:
            self.form_dropdown.configure(values=["No forms available"])

    # ──────────────────────────────────────────
    # Generate
    # ──────────────────────────────────────────
    def _fill_and_save(self):
        if not self.selected_contact:
            self._set_status("Please select a client first.", "#dc2626")
            return

        form_display = self.form_var.get()
        if form_display.startswith("Choose") or form_display.startswith("No forms"):
            self._set_status("Please select a form template.", "#dc2626")
            return

        # Find the matching mapping file
        mapping_file = None
        for f in self.forms:
            provider = f.get("provider", "")
            product = f.get("product", f.get("form_name", ""))
            display = f"{provider} - {product}" if provider else product
            if display == form_display:
                mapping_file = f["mapping_file"]
                break

        if not mapping_file:
            self._set_status("Form template not found.", "#dc2626")
            return

        self.generate_btn.configure(state="disabled", text="Generating...")
        self._set_status("Filling form...", BLUE)

        def do_fill():
            try:
                contact = get_contact_local(self.selected_contact["id"])
                if not contact:
                    contact = self.selected_contact
                output_path = fill_form(mapping_file, contact)
                self.after(0, lambda: self._on_fill_done(output_path))
            except Exception as e:
                self.after(0, lambda: self._on_fill_error(str(e)))

        threading.Thread(target=do_fill, daemon=True).start()

    def _on_fill_done(self, output_path):
        self.generate_btn.configure(state="normal", text="Fill & Download")
        filename = Path(output_path).name

        # Prompt user to save the file somewhere
        save_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Filled Form",
            initialfile=filename,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )

        if save_path:
            shutil.copy2(output_path, save_path)
            self._set_status(f"Saved: {save_path}", GREEN)
            self.output_label.configure(text=f"Saved: {Path(save_path).name}")
        else:
            self._set_status(f"Generated: {filename} (in output folder)", GREEN)
            self.output_label.configure(text=f"Saved: {filename}")

        self.output_card.pack(fill="x", pady=(12, 0))

    def _on_fill_error(self, error):
        self.generate_btn.configure(state="normal", text="Fill & Download")
        self._set_status(f"Error: {error}", "#dc2626")

    # ──────────────────────────────────────────
    # Settings dialog
    # ──────────────────────────────────────────
    def _open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("420x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            frame, text="OnePageCRM Credentials",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=GRAY_800,
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame, text="USER ID",
            font=ctk.CTkFont(size=11), text_color=GRAY_500,
        ).pack(anchor="w", pady=(16, 4))

        user_id_var = ctk.StringVar(value=os.getenv("USER_ID", ""))
        user_id_entry = ctk.CTkEntry(frame, textvariable=user_id_var, height=36, font=ctk.CTkFont(size=13))
        user_id_entry.pack(fill="x")

        ctk.CTkLabel(
            frame, text="API KEY",
            font=ctk.CTkFont(size=11), text_color=GRAY_500,
        ).pack(anchor="w", pady=(12, 4))

        api_key_var = ctk.StringVar(value=os.getenv("API_KEY", ""))
        api_key_entry = ctk.CTkEntry(frame, textvariable=api_key_var, show="*", height=36, font=ctk.CTkFont(size=13))
        api_key_entry.pack(fill="x")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))

        def save():
            uid = user_id_var.get().strip()
            key = api_key_var.get().strip()
            if not uid or not key:
                self._set_status("Both fields are required", "#dc2626")
                return
            env_path = Path(__file__).parent / ".env"
            env_path.write_text(f"API_KEY={key}\nUSER_ID={uid}\n")
            import crm_client
            crm_client.USER_ID = uid
            crm_client.API_KEY = key
            os.environ["USER_ID"] = uid
            os.environ["API_KEY"] = key
            self._set_status("Settings saved", GREEN)
            dialog.destroy()

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80, height=34,
            font=ctk.CTkFont(size=13), fg_color=GRAY_200,
            hover_color=GRAY_400, text_color=GRAY_700,
            command=dialog.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="Save", width=80, height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=BLUE, hover_color="#1d4ed8",
            command=save,
        ).pack(side="right")

    def _open_output_folder(self):
        OUTPUT_DIR.mkdir(exist_ok=True)
        path = str(OUTPUT_DIR)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


def main():
    app = AutoFillApp()
    app.mainloop()


if __name__ == "__main__":
    main()
