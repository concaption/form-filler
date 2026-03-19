"""AutoFill Application — YourFinance.ie

Native desktop app built with CustomTkinter.
Syncs contacts from OnePageCRM and fills PDF application forms.
"""

import os
import sys
import json
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

        mapping_btn = ctk.CTkButton(
            right_frame, text="Mapping Tool", width=110, height=32,
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color="#1e5278",
            text_color=GRAY_400, border_width=1, border_color=GRAY_500,
            command=self._open_mapping_tool,
        )
        mapping_btn.pack(side="left", padx=(8, 0))

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
    # Mapping Tool (native)
    # ──────────────────────────────────────────
    def _open_mapping_tool(self):
        from PyPDF2 import PdfReader
        from PyPDF2.generic import ArrayObject

        CRM_OPTIONS = [
            "-- Not mapped --",
            "title", "first_name", "last_name", "full_name",
            "birthday", "pps_1", "email",
            "phone_mobile", "phone_home", "phone_work",
            "address_line1", "address_city", "address_state", "address_postcode",
            "address_work_line1", "address_work_city", "address_work_state",
            "address_work_postcode", "address_work_full",
            "company_name", "job_title", "salary",
            "gender", "status", "nationality", "country_of_residence",
            "employer_tax_number", "start_date_for_current_employment", "smoker",
        ]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Mapping Tool")
        dialog.geometry("900x650")
        dialog.minsize(750, 500)
        dialog.transient(self)

        # State
        dialog.pdf_fields = []
        dialog.pdf_filename = ""
        dialog.field_dropdowns = []

        # --- Top bar ---
        top = ctk.CTkFrame(dialog, fg_color=WHITE, corner_radius=0, height=50)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="Mapping Tool", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=GRAY_800).pack(side="left", padx=16)

        save_btn = ctk.CTkButton(top, text="Save Mapping", width=120, height=34,
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 fg_color=GREEN, hover_color=GREEN_DARK,
                                 command=lambda: save_mapping())
        save_btn.pack(side="right", padx=16)

        fieldmap_btn = ctk.CTkButton(top, text="Open Field Map PDF", width=150, height=34,
                                     font=ctk.CTkFont(size=13),
                                     fg_color=BLUE, hover_color="#1d4ed8",
                                     command=lambda: open_fieldmap())
        fieldmap_btn.pack(side="right", padx=(0, 8))

        # --- Form details ---
        details = ctk.CTkFrame(dialog, fg_color=WHITE, corner_radius=0)
        details.pack(fill="x", padx=16, pady=(12, 0))

        row1 = ctk.CTkFrame(details, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(12, 0))

        ctk.CTkLabel(row1, text="PDF File:", font=ctk.CTkFont(size=12),
                     text_color=GRAY_500).pack(side="left")
        pdf_label = ctk.CTkLabel(row1, text="No file selected", font=ctk.CTkFont(size=12, weight="bold"),
                                 text_color=GRAY_800)
        pdf_label.pack(side="left", padx=(8, 16))

        ctk.CTkButton(row1, text="Browse...", width=90, height=30,
                      font=ctk.CTkFont(size=12), fg_color=GRAY_200,
                      hover_color=GRAY_400, text_color=GRAY_700,
                      command=lambda: pick_pdf()).pack(side="left")

        row2 = ctk.CTkFrame(details, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(8, 0))

        ctk.CTkLabel(row2, text="Provider:", font=ctk.CTkFont(size=12),
                     text_color=GRAY_500, width=60).pack(side="left")
        provider_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=provider_var, width=150, height=30,
                     font=ctk.CTkFont(size=12), placeholder_text="e.g. Aviva").pack(side="left", padx=(4, 16))

        ctk.CTkLabel(row2, text="Product:", font=ctk.CTkFont(size=12),
                     text_color=GRAY_500, width=55).pack(side="left")
        product_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=product_var, width=150, height=30,
                     font=ctk.CTkFont(size=12), placeholder_text="e.g. PRSA").pack(side="left", padx=(4, 16))

        ctk.CTkLabel(row2, text="Form Name:", font=ctk.CTkFont(size=12),
                     text_color=GRAY_500, width=80).pack(side="left")
        formname_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=formname_var, width=200, height=30,
                     font=ctk.CTkFont(size=12), placeholder_text="e.g. Aviva PRSA Application").pack(side="left", padx=4)

        info_label = ctk.CTkLabel(details, text="", font=ctk.CTkFont(size=11),
                                  text_color=GRAY_400)
        info_label.pack(anchor="w", padx=12, pady=(4, 8))

        # --- Header row ---
        header_row = ctk.CTkFrame(dialog, fg_color=GRAY_200, corner_radius=0, height=32)
        header_row.pack(fill="x", padx=16, pady=(12, 0))
        header_row.pack_propagate(False)

        ctk.CTkLabel(header_row, text="PAGE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=GRAY_500, width=45).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(header_row, text="PDF FIELD NAME", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=GRAY_500, width=280).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(header_row, text="TYPE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=GRAY_500, width=50).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(header_row, text="CRM FIELD", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=GRAY_500).pack(side="left", padx=(8, 0))

        # --- Scrollable field list ---
        field_scroll = ctk.CTkScrollableFrame(dialog, fg_color=WHITE, corner_radius=0)
        field_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # --- Status ---
        status_label = ctk.CTkLabel(dialog, text="Select a PDF to begin", font=ctk.CTkFont(size=12),
                                    text_color=GRAY_500, fg_color=WHITE, height=28,
                                    corner_radius=0, anchor="w", padx=16)
        status_label.pack(fill="x", side="bottom")

        # --- Auto-match logic ---
        def auto_match(name):
            n = name.lower()
            if 'first name' in n or 'forename' in n: return 'first_name'
            if 'surname' in n or n == 'last name': return 'last_name'
            if 'title' in n: return 'title'
            if 'date of birth' in n or 'dob' in n: return 'birthday'
            if 'pps' in n or 'public service' in n: return 'pps_1'
            if 'email' in n: return 'email'
            if 'mobile' in n: return 'phone_mobile'
            if 'home' in n and 'phone' in n or n == 'home number': return 'phone_home'
            if 'occupation' in n: return 'job_title'
            if 'salary' in n or 'income' in n or 'earning' in n: return 'salary'
            if 'eircode' in n: return 'address_postcode'
            if 'address' in n and '1' in n: return 'address_line1'
            if 'address' in n and '2' in n: return 'address_city'
            if 'address' in n and '3' in n: return 'address_state'
            if 'employer' in n and 'name' in n: return 'company_name'
            if 'employer' in n and 'tax' in n: return 'employer_tax_number'
            return '-- Not mapped --'

        # --- Pick PDF ---
        def pick_pdf():
            from config import PDFS_DIR
            path = filedialog.askopenfilename(
                parent=dialog, title="Select PDF Form",
                initialdir=str(PDFS_DIR),
                filetypes=[("PDF Files", "*.pdf")],
            )
            if not path:
                return

            # Copy to pdfs/ if not already there
            from config import PDFS_DIR
            src = Path(path)
            dest = PDFS_DIR / src.name
            if not dest.exists():
                import shutil
                shutil.copy2(path, dest)

            dialog.pdf_filename = src.name
            pdf_label.configure(text=src.name)

            # Auto-fill provider
            fn = src.name.lower()
            if 'aviva' in fn: provider_var.set('Aviva')
            elif 'zurich' in fn: provider_var.set('Zurich')
            elif 'irish' in fn or ' il ' in fn or 'il-' in fn: provider_var.set('Irish Life')
            elif 'standard' in fn or 'synergy' in fn: provider_var.set('Standard Life')

            # Extract fields
            reader = PdfReader(str(dest))
            dialog.pdf_fields = []
            for page_idx, page in enumerate(reader.pages):
                annots = page.get("/Annots")
                if not annots:
                    continue
                annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
                for ref in annot_list:
                    annot = ref.get_object()
                    name = str(annot.get("/T", ""))
                    ftype = str(annot.get("/FT", "")).replace("/", "")
                    parent = annot.get("/Parent")
                    parent_name = str(parent.get_object().get("/T", "")) if parent else ""
                    if name:
                        dialog.pdf_fields.append({
                            "name": name, "type": ftype,
                            "page": page_idx + 1, "parent": parent_name,
                        })
                    elif parent_name and parent_name not in [f["name"] for f in dialog.pdf_fields]:
                        dialog.pdf_fields.append({
                            "name": parent_name, "type": "RadioGroup",
                            "page": page_idx + 1, "parent": "",
                        })

            dialog.pdf_fields.sort(key=lambda f: (f["page"], f["name"]))
            info_label.configure(text=f"{len(reader.pages)} pages, {len(dialog.pdf_fields)} fields")
            status_label.configure(text=f"Loaded {len(dialog.pdf_fields)} fields from {src.name}")

            # Render field rows
            for w in field_scroll.winfo_children():
                w.destroy()
            dialog.field_dropdowns = []

            for f in dialog.pdf_fields:
                row = ctk.CTkFrame(field_scroll, fg_color="transparent", height=32)
                row.pack(fill="x", pady=1)
                row.pack_propagate(False)

                ctk.CTkLabel(row, text=str(f["page"]), font=ctk.CTkFont(size=11),
                             text_color=BLUE, width=45).pack(side="left", padx=(4, 0))
                ctk.CTkLabel(row, text=f["name"], font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=GRAY_800, width=280, anchor="w").pack(side="left", padx=(8, 0))
                ctk.CTkLabel(row, text=f["type"], font=ctk.CTkFont(size=10),
                             text_color=GRAY_500, width=50).pack(side="left", padx=(8, 0))

                var = ctk.StringVar(value=auto_match(f["name"]))
                dropdown = ctk.CTkOptionMenu(row, variable=var, values=CRM_OPTIONS,
                                             width=200, height=26, font=ctk.CTkFont(size=11),
                                             fg_color=GRAY_50, button_color=GRAY_400,
                                             text_color=GRAY_700)
                dropdown.pack(side="left", padx=(8, 4))
                dialog.field_dropdowns.append((f["name"], var))

        # --- Open field map PDF ---
        def open_fieldmap():
            if not dialog.pdf_filename:
                status_label.configure(text="Select a PDF first")
                return
            from config import PDFS_DIR
            from generate_field_maps import generate_field_map

            pdf_path = PDFS_DIR / dialog.pdf_filename
            output_dir = PDFS_DIR / "fieldmaps"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"FIELDMAP-{dialog.pdf_filename}"
            generate_field_map(pdf_path, output_path)

            if sys.platform == "win32":
                os.startfile(str(output_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_path)])
            else:
                subprocess.Popen(["xdg-open", str(output_path)])
            status_label.configure(text=f"Opened field map: {output_path.name}")

        # --- Save mapping ---
        def save_mapping():
            if not dialog.pdf_filename:
                status_label.configure(text="Select a PDF first")
                return
            provider = provider_var.get().strip()
            product = product_var.get().strip()
            form_name = formname_var.get().strip()
            if not provider or not product or not form_name:
                status_label.configure(text="Please fill in Provider, Product, and Form Name")
                return

            import re
            from config import MAPPINGS_DIR
            field_map = {}
            for fname, var in dialog.field_dropdowns:
                crm = var.get()
                field_map[fname] = {
                    "label": fname,
                    "crm_field": crm if crm != "-- Not mapped --" else None,
                }

            safe = re.sub(r'[^a-z0-9]+', '_', (provider + "_" + product).lower()).strip('_')
            mapping_path = MAPPINGS_DIR / f"{safe}.json"
            data = {
                "form_name": form_name,
                "pdf_file": dialog.pdf_filename,
                "provider": provider,
                "product": product,
                "field_map": field_map,
            }
            with open(mapping_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

            self._load_forms()
            status_label.configure(text=f"Saved mapping: {mapping_path.name}")
            self._set_status(f"New form added: {provider} - {product}", GREEN)

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
