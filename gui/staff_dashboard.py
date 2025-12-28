# gui/staff_dashboard.py
from __future__ import annotations

import difflib
import time
from datetime import datetime
import uuid
import sys
from typing import List, Tuple, Optional, Callable

# ADDED: QGraphicsDropShadowEffect for the card shadow, QColor for shadow color
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QTextEdit, QMessageBox, QSizePolicy, QScrollArea, QApplication,
    QFrame, QDialog, QListWidget, QListWidgetItem, QSpacerItem, QSizePolicy as QSP, QCompleter,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QFont, QIntValidator, QColor
from PyQt6.QtCore import Qt, pyqtSignal

# --- MOCKS & supabase helpers (Keep existing structure) ---
try:
    from language.translator import Translator
except ImportError:
    class Translator:
        def __init__(self, lang): pass
        def translate(self, text): return text

try:
    # core helpers
    from supabase_utils import supabase_post, supabase_get, get_approved_service_names
    # optional helpers specifically added for documents
    try:
        from supabase_utils import get_service_documents, save_service_documents, save_service_documents_upsert
    except Exception:
        get_service_documents = None
        save_service_documents = None
        save_service_documents_upsert = None
    try:
        from supabase_utils import get_service_suggestions  # type: ignore
    except Exception:
        get_service_suggestions = None  # type: ignore
except ImportError:
    def supabase_post(*args, **kwargs): raise Exception("Supabase not connected")
    def supabase_get(*args, **kwargs): return None
    def get_approved_service_names(): return ["Income Certificate", "Birth Certificate", "Ration Card"]
    get_service_suggestions = None
    get_service_documents = None
    save_service_documents = None
    save_service_documents_upsert = None
# ---------------------------------------------------------

# ------------------- Helper: robust poster with retries -------------------
def post_with_retries(table: str, payload: dict, retries: int = 3, backoff: float = 0.45):
    """Attempt to POST using supabase_post with retries for transient failures."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = supabase_post(table, payload)
            status = getattr(resp, "status_code", None)
            if status is None:
                try:
                    _ = resp.json()
                    return resp
                except Exception:
                    pass
            elif status in (200, 201):
                return resp
            else:
                last_exc = Exception(f"HTTP {status}: {getattr(resp, 'text', str(resp))}")
        except Exception as e:
            last_exc = e
        time.sleep(backoff * attempt)
    raise last_exc


# --------- helper to remove duplicate services case/space-insensitively ----------
def _canonicalize_services(names: List[str]) -> List[str]:
    """
    Take a list of service names and return a list with duplicates removed,
    ignoring case and extra spaces. First seen spelling is kept.
    """
    seen = {}
    for s in names:
        if not isinstance(s, str):
            continue
        cleaned = " ".join(s.split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen[key] = cleaned
    return list(seen.values())


# ---------------- Document store dialog (simple list fallback) ----------------
class DocumentStoreDialog(QDialog):
    """Simple dialog to list required documents and allow staff to open/view them."""
    def __init__(self, parent=None, docs: Optional[List[dict]] = None):
        super().__init__(parent)
        self.setWindowTitle("Required Documents")
        self.setMinimumSize(700, 480)

        layout = QVBoxLayout(self)
        title = QLabel("📂 Required Documents")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        if docs is None:
            docs = []

        self.list_widget = QListWidget()
        for d in docs:
            service = d.get('service') or d.get('name') or 'Untitled'
            docs_list = d.get('documents') or []
            item = QListWidgetItem(f"{service} — {', '.join(docs_list)}")
            item.setData(Qt.ItemDataRole.UserRole, d)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, stretch=1)

        hint = QLabel("Select an item and click 'Open' to view details.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addSpacerItem(QSpacerItem(8, 8, QSP.Policy.Expanding, QSP.Policy.Minimum))
        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.open_selected)
        row.addWidget(self.open_btn)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

    def open_selected(self):
        sel = self.list_widget.currentItem()
        if not sel:
            QMessageBox.information(self, "No selection", "Please select a document to open.")
            return
        data = sel.data(Qt.ItemDataRole.UserRole) or {}
        # show readable summary (no demo path)
        service = data.get("service") or data.get("name") or "Untitled"
        docs = data.get("documents") or []
        created_by = data.get("created_by", "unknown")
        created_at = data.get("created_at", "")
        msg = f"Service: {service}\nDocuments:\n - " + "\n - ".join(docs)
        if created_by:
            msg += f"\n\nCreated by: {created_by}"
        if created_at:
            msg += f"\nCreated at: {created_at}"
        QMessageBox.information(self, "Document details", msg)


# -------------------- StaffDashboard --------------------
class StaffDashboard(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self, staff_id, staff_name="Staff", lang="English"):
        super().__init__()
        self.staff_id = staff_id
        self.staff_name = staff_name
        self.lang = lang
        self.setWindowTitle("Staff Dashboard")
        self.setMinimumSize(1100, 700)  # Adjusted minimum size slightly

        # (DATA INIT)
        self.base_services = [
            "Income Certificate",
            "Aadhaar Update",
            "Ration Card",
            "Birth Certificate",
        ]

        try:
            approved_dynamic = get_approved_service_names() or []
        except Exception:
            approved_dynamic = []

        approved_dynamic = _canonicalize_services(approved_dynamic)
        self.base_services = _canonicalize_services(self.base_services)

        suggested = []
        if get_service_suggestions is not None:
            try:
                suggested = get_service_suggestions() or []
            except Exception:
                suggested = []

        suggested = _canonicalize_services(suggested)

        all_services = _canonicalize_services(self.base_services + approved_dynamic + suggested)
        self.services_db = sorted(all_services)

        approved_list = _canonicalize_services(self.base_services + approved_dynamic)
        self.approved_services = set(approved_list)

        # translator (may be stub)
        try:
            self.translator = Translator(lang)
            self.tr = self.translator.translate
        except Exception:
            self.tr = lambda x: x

        # completer
        self._build_completer()

        # styling
        self.load_stylesheet()

        # ui
        self.init_ui()

    def load_stylesheet(self):
        # Keep your QSS design (kept same content as before)
        self.setStyleSheet("""
            /* Global Resets and Fonts */
            * {
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                font-size: 14px;
                color: #1E293B;
            }
            QWidget#mainContainerWidget { background-color: #F0F4F8; }

            QFrame#sidebar { background-color: #1B0F4A; border: none; }

            QLabel#brandTitle { color: #FFFFFF; font-size: 18px; font-weight: 900; }
            QLabel#brandSubtitle { color: #E2E8F0; font-size: 13px; font-weight: 600; }
            QLabel#brandLocal { color: #CBD5E1; font-size: 12px; font-weight: 600; }
            QLabel.sidebarBrandSmall { color: #94A3B8; font-size: 12px; margin-top: 10px; margin-bottom: 5px; padding-left: 10px;}
            QFrame#sideDivider { background-color: rgba(255,255,255,0.1); max-height: 1px; }

            QPushButton.sidebarBtn {
                text-align: left;
                color: #FFFFFF;
                background-color: transparent;
                border: none;
                padding: 12px 15px;
                border-radius: 8px;
                font-weight: 500;
                margin-bottom: 4px;
            }
            QPushButton.sidebarBtn:hover { background-color: rgba(255,255,255,0.1); }
            QPushButton.sidebarBtn:checked {
                background-color: rgba(6, 182, 212, 0.15);
                color: #FFFFFF;
                font-weight: 700;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-left: 5px solid #06B6D4;
            }

            QScrollArea { border: none; background: transparent; }
            QFrame#cardFrame { background-color: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; }

            QLabel#welcomeLabel { font-size: 20px; font-weight: 700; color: #1E293B; }
            QLabel.sectionLabel { font-size: 14px; font-weight: 600; color: #334155; margin-bottom: 4px; }

            QLineEdit, QTextEdit, QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 10px 12px;
                background-color: #FFFFFF;
                selection-background-color: #06B6D4;
                font-size: 14px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 2px solid #06B6D4;
                padding: 9px 11px;
            }
            QLineEdit[readOnly="true"] {
                background-color: #F1F5F9;
                color: #64748B;
                border-color: #E2E8F0;
            }

            QComboBox::drop-down { border: none; background: transparent; width: 30px; }
            QComboBox QAbstractItemView {
                background-color: #ffffff; color: #333333; border: 1px solid #cfd8dc;
                selection-background-color: #06B6D4; selection-color: #ffffff; outline: 0;
            }
            QComboBox QAbstractItemView::item { min-height: 35px; padding: 4px 8px; }
            QComboBox QAbstractItemView::item:hover { background-color: #e0f7fa; color: #000000; }
            QComboBox QAbstractItemView::item:selected { background-color: #06B6D4; color: #ffffff; }

            QPushButton.primaryBtn {
                background-color: #06B6D4; color: #FFFFFF; border: none; border-radius: 10px;
                padding: 12px 24px; font-size: 15px; font-weight: 700;
            }
            QPushButton.primaryBtn:hover { background-color: #0891B2; }
            QPushButton#addServiceBtn { background-color: #06B6D4; color: #FFFFFF; border: none; border-radius: 10px; padding: 12px; font-size: 15px; font-weight: 600; }
            QPushButton.removeServiceBtn {
                background: #F1F5F9; color: #94A3B8; border: none; min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
                border-radius: 18px; font-size: 16px;
            }
            QLabel#statusLabel { font-weight: 600; color: #0891B2; }
        """)

    # ---------- completer helpers ----------
    def _build_completer(self):
        items = sorted(set(self.services_db))
        try:
            self._completer = QCompleter(items, self)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        except Exception:
            self._completer = None

    def _refresh_completer_and_combos(self):
        self._build_completer()
        for _, s_combo, _, _, _ in getattr(self, "service_fields", []):
            old = s_combo.currentText()
            s_combo.blockSignals(True)
            s_combo.clear()
            s_combo.addItems(sorted(set(self.services_db)))
            s_combo.setCurrentText(old)
            try:
                if self._completer:
                    s_combo.lineEdit().setCompleter(self._completer)
            except Exception:
                pass
            s_combo.blockSignals(False)

    def _prioritise_matches(self, typed: str) -> List[str]:
        typed_l = typed.strip().lower()
        base = sorted(set(self.services_db))
        if not typed_l:
            return base
        starts = [s for s in base if s.lower().startswith(typed_l)]
        lower_base = [s.lower() for s in base]
        fuzzy_lower = difflib.get_close_matches(typed_l, lower_base, n=10, cutoff=0.6)
        fuzzy = [s for s in base if s.lower() in fuzzy_lower and s not in starts]
        approved_first = sorted([s for s in starts + fuzzy if s in self.approved_services], key=lambda x: x)
        others = [s for s in starts + fuzzy if s not in self.approved_services]
        result = approved_first + others
        return result or base

    # ---------- UI init ----------
    def init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ========== Sidebar ==========
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(15, 25, 15, 20)
        side_layout.setSpacing(10)

        # Brand row
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        b_title = QLabel("Akshaya"); b_title.setObjectName("brandTitle")
        b_sub = QLabel("E-WorkTrack"); b_sub.setObjectName("brandSubtitle")
        b_loc = QLabel("അക്ഷയ"); b_loc.setObjectName("brandLocal")
        brand_box.addWidget(b_title); brand_box.addWidget(b_sub); brand_box.addWidget(b_loc)
        side_layout.addLayout(brand_box)

        small = QLabel("Admin · Staff panel"); small.setProperty("class", "sidebarBrandSmall")
        side_layout.addWidget(small)

        divider = QFrame(); divider.setObjectName("sideDivider"); divider.setFrameShape(QFrame.Shape.HLine); divider.setFixedHeight(1)
        side_layout.addSpacing(5); side_layout.addWidget(divider); side_layout.addSpacing(10)

        # Sidebar menu buttons
        self.btn_recent = QPushButton("  ⏱   " + self.tr("Recent Work"))
        self.btn_recent.setCheckable(True); self.btn_recent.setProperty("class", "sidebarBtn"); self.btn_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_recent.clicked.connect(self.show_recent_work); side_layout.addWidget(self.btn_recent)

        self.btn_search = QPushButton("  🔍   " + self.tr("Search Records"))
        self.btn_search.setCheckable(True); self.btn_search.setProperty("class", "sidebarBtn"); self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(self.show_search_dialog); side_layout.addWidget(self.btn_search)

        # NEW: Add Required Documents
        self.btn_add_required = QPushButton("  ➕   " + self.tr("Add Required Documents"))
        self.btn_add_required.setCheckable(True); self.btn_add_required.setProperty("class", "sidebarBtn")
        self.btn_add_required.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_required.clicked.connect(self.show_add_required_documents)
        side_layout.addWidget(self.btn_add_required)

        # NEW: View Required Documents
        self.btn_view_required = QPushButton("  📁   " + self.tr("View Required Documents"))
        self.btn_view_required.setCheckable(True); self.btn_view_required.setProperty("class", "sidebarBtn")
        self.btn_view_required.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_required.clicked.connect(self.show_view_required_documents)
        side_layout.addWidget(self.btn_view_required)

        self.btn_print = QPushButton("  🖨️   " + self.tr("Print"))
        self.btn_print.setCheckable(True); self.btn_print.setProperty("class", "sidebarBtn"); self.btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print.clicked.connect(self.handle_print); side_layout.addWidget(self.btn_print)

        side_layout.addStretch()

        self.btn_logout = QPushButton("  🚪   " + self.tr("Logout"))
        self.btn_logout.setProperty("class", "sidebarBtn"); self.btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_logout.clicked.connect(self.handle_logout); side_layout.addWidget(self.btn_logout)

        root.addWidget(sidebar)

        # ========== Main content area ==========
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.main_container = QWidget(); self.main_container.setObjectName("mainContainerWidget")
        main_content_layout = QVBoxLayout(self.main_container)
        main_content_layout.setContentsMargins(40, 30, 40, 40); main_content_layout.setSpacing(25)

        # Header row
        header_row = QHBoxLayout()
        welcome = QLabel(f"👋 {self.tr('Hello')} {self.staff_name}"); welcome.setObjectName("welcomeLabel")
        header_row.addWidget(welcome); header_row.addStretch()
        lang_label = QLabel("🌐 " + self.tr("Language:")); lang_label.setStyleSheet("font-weight: 600; color: #64748B; font-size: 14px;")
        lang_dropdown = QComboBox(); lang_dropdown.addItems(["English", "മലയാളം"]); lang_dropdown.setCurrentText(self.lang); lang_dropdown.setFixedWidth(130)
        header_row.addWidget(lang_label); header_row.addSpacing(10); header_row.addWidget(lang_dropdown)
        main_content_layout.addLayout(header_row)

        # Card frame
        self.card_frame = QFrame(); self.card_frame.setObjectName("cardFrame")
        shadow = QGraphicsDropShadowEffect(self); shadow.setBlurRadius(25); shadow.setXOffset(0); shadow.setYOffset(4); shadow.setColor(QColor(0,0,0,20))
        self.card_frame.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(self.card_frame); card_layout.setContentsMargins(30,35,30,35); card_layout.setSpacing(25)
        self.form_layout = QVBoxLayout(); self.form_layout.setSpacing(20)
        card_layout.addLayout(self.form_layout)
        main_content_layout.addWidget(self.card_frame); main_content_layout.addStretch()

        scroll.setWidget(self.main_container); root.addWidget(scroll, stretch=1)

        # build the form
        self.build_form_section()

        # store sidebar buttons (include new doc buttons)
        self.sidebar_buttons = [self.btn_recent, self.btn_search, self.btn_add_required, self.btn_view_required, self.btn_print]

    # ---------------- form ----------------
    def build_form_section(self):
        layout = self.form_layout

        def add_label_input(label_text, widget, icon_char=""):
            label = QLabel(f"{icon_char} {label_text}")
            label.setProperty("class", "sectionLabel")
            layout.addWidget(label)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(widget)

        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText(self.tr("Enter Name"))
        add_label_input(self.tr("Customer Name:"), self.customer_name_input, "👤")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(self.tr("Enter Phone Number"))
        self.phone_input.setInputMask("0000000000")
        add_label_input(self.tr("Phone Number:"), self.phone_input, "📞")

        services_heading = QLabel("📄 " + self.tr("Services & Billing:"))
        services_heading.setProperty("class", "sectionLabel")
        layout.addSpacing(10)
        layout.addWidget(services_heading)

        self.services_container = QVBoxLayout()
        self.services_container.setSpacing(12)
        layout.addLayout(self.services_container)

        self.service_fields: List[Tuple[QWidget, QComboBox, QLineEdit, QLineEdit, QLineEdit]] = []
        self.add_service_entry()

        add_service_btn = QPushButton("➕ " + self.tr("Add More Service"))
        add_service_btn.setObjectName("addServiceBtn")
        add_service_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_service_btn.clicked.connect(self.add_service_entry)
        layout.addWidget(add_service_btn)

        layout.addSpacing(10)

        payment_row = QHBoxLayout()
        payment_row.setContentsMargins(0, 0, 0, 0)
        payment_label = QLabel(self.tr("Payment:"))
        payment_label.setProperty("class", "sectionLabel")
        payment_label.setStyleSheet("margin-bottom: 0px;")

        self.payment_method = QComboBox()
        self.payment_method.addItems(["Cash", "UPI", "Bank"])
        self.payment_method.setFixedWidth(180)
        self.payment_method.setCursor(Qt.CursorShape.PointingHandCursor)

        payment_row.addWidget(payment_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        payment_row.addSpacing(15)
        payment_row.addWidget(self.payment_method, alignment=Qt.AlignmentFlag.AlignVCenter)
        payment_row.addStretch()
        layout.addLayout(payment_row)

        self.remarks_input = QTextEdit()
        self.remarks_input.setPlaceholderText(self.tr("Eg: Customer brought old documents / Requested urgent service"))
        self.remarks_input.setMinimumHeight(100)
        self.remarks_input.setMaximumHeight(150)
        add_label_input(self.tr("Staff Remarks:"), self.remarks_input, "🗒️")

        layout.addSpacing(15)

        action_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        action_row.addWidget(self.status_label, stretch=1)

        self.submit_btn = QPushButton(self.tr("Submit Application"))
        self.submit_btn.setProperty("class", "primaryBtn")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self.handle_submit)
        self.submit_btn.setMinimumWidth(200)
        action_row.addWidget(self.submit_btn)
        layout.addLayout(action_row)

    def add_service_entry(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        service_input = QComboBox()
        service_input.setEditable(True)
        service_input.addItems(sorted(set(self.services_db)))
        service_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        service_input.setFixedHeight(42)
        try:
            if self._completer:
                service_input.lineEdit().setCompleter(self._completer)
        except Exception:
            pass

        line = service_input.lineEdit()
        line.setPlaceholderText(self.tr("Select or type service name..."))
        line.textEdited.connect(lambda txt, si=service_input: self._on_service_text_edited(si, txt))
        line.editingFinished.connect(lambda si=service_input: self.check_service_validity(si))

        def config_amount_input(placeholder, read_only=False):
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setValidator(QIntValidator())
            inp.setFixedWidth(110)
            inp.setFixedHeight(42)
            inp.setAlignment(Qt.AlignmentFlag.AlignRight)
            if read_only:
                inp.setReadOnly(True)
            return inp

        base_input = config_amount_input("Base ₹")
        charge_input = config_amount_input("Charge ₹")
        total_input = config_amount_input("Total ₹", read_only=True)

        def recompute_total():
            try:
                b = int(base_input.text()) if base_input.text() else 0
                c = int(charge_input.text()) if charge_input.text() else 0
                total_input.setText(str(b + c))
            except Exception:
                total_input.setText("0")

        base_input.textChanged.connect(lambda _: recompute_total())
        charge_input.textChanged.connect(lambda _: recompute_total())

        remove_btn = QPushButton("✕")
        remove_btn.setToolTip(self.tr("Remove this service"))
        remove_btn.setProperty("class", "removeServiceBtn")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda _, w=row_widget, s=service_input: self._remove_service_entry(w, s))

        row_layout.addWidget(service_input, stretch=5)
        row_layout.addWidget(base_input, stretch=2)
        row_layout.addWidget(charge_input, stretch=2)
        row_layout.addWidget(total_input, stretch=2)
        row_layout.addWidget(remove_btn)

        self.services_container.addWidget(row_widget)
        self.service_fields.append((row_widget, service_input, base_input, charge_input, total_input))

    def _remove_service_entry(self, row_widget: QWidget, combo: QComboBox):
        self.service_fields = [t for t in self.service_fields if t[0] is not row_widget]
        row_widget.setParent(None)
        row_widget.deleteLater()
        if not self.service_fields:
            self.add_service_entry()

    # (NO CHANGES TO LOGIC METHODS BELOW)
    def _on_service_text_edited(self, combo: QComboBox, text: str):
        try:
            matches = self._prioritise_matches(text)
            if self._completer:
                self._completer.model().setStringList(matches)
        except Exception:
            pass

    # ---------- LIGHT THEME QUESTION BOX ----------
    def ask_question(self, title: str, text: str) -> QMessageBox.StandardButton:
        """Show a light-themed Yes/No question dialog."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #0f172a;
                font-size: 14px;
            }
            QMessageBox QPushButton {
                background-color: #e5e7eb;
                color: #111827;
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #dbeafe;
            }
        """)
        return box.exec()

    # ---------- NEW: unified light-themed info/warn/error box ----------
    def show_message(
        self,
        title: str,
        text: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information
    ) -> int:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(icon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #0f172a;
                font-size: 14px;
            }
            QMessageBox QPushButton {
                background-color: #06B6D4;
                color: #ffffff;
                border-radius: 8px;
                padding: 6px 18px;
                min-width: 80px;
                font-weight: 600;
            }
            QMessageBox QPushButton:hover {
                background-color: #0891B2;
            }
        """)
        return box.exec()

    def check_service_validity(self, combo: QComboBox):
        raw = combo.currentText().strip()
        if not raw:
            return

        candidate = " ".join(raw.split())
        # exact match
        for s in self.services_db:
            if s.lower() == candidate.lower():
                combo.setCurrentText(s)
                return

        # startswith family
        starts = [s for s in self.services_db if s.lower().startswith(candidate.lower())]
        if starts:
            pref = next((s for s in starts if s in self.approved_services), starts[0])
            combo.setCurrentText(pref)
            return

        # fuzzy against approved only
        approved_lower = [s.lower() for s in self.approved_services]
        fuzzy = difflib.get_close_matches(candidate.lower(), approved_lower, n=1, cutoff=0.75)
        if fuzzy:
            suggested = next((s for s in self.approved_services if s.lower() == fuzzy[0]), None)
            if suggested:
                resp = self.ask_question(
                    self.tr("Use suggested"),
                    self.tr(
                        f"Did you mean '{suggested}' ?\n"
                        f"Yes = use it, No = keep '{candidate}' as new suggestion"
                    ),
                )
                if resp == QMessageBox.StandardButton.Yes:
                    combo.setCurrentText(suggested)
                    return

        # new suggestion flow
        resp = self.ask_question(
            self.tr("New service"),
            self.tr(
                f"'{candidate}' not found in approved list. "
                f"Add as suggestion for admin verification?"
            ),
        )
        if resp == QMessageBox.StandardButton.Yes:
            # Keep candidate in services_db for UX (so user sees it)
            self.services_db.append(candidate)
            self.services_db = sorted(set(self.services_db))
            self._refresh_completer_and_combos()
            combo.setCurrentText(candidate)
            try:
                supabase_post(
                    "service_suggestions",
                    {
                        "service": candidate,
                        "suggested_by": self.staff_id,
                        "status": "pending",
                    },
                )
            except Exception:
                # ignore posting failure silently (or implement logging)
                pass
        else:
            if combo.count() > 0:
                combo.setCurrentIndex(0)
            else:
                combo.setCurrentText("")

    # ------------- submit ---------------
        # ------------- submit ---------------
    def handle_submit(self):
        # immediate UI guard
        if not hasattr(self, 'submit_btn'):
            return
        self.submit_btn.setEnabled(False)
        self.status_label.setText("Saving... please wait")

        try:
            name = self.customer_name_input.text().strip()
            phone = self.phone_input.text().strip()
            remarks = self.remarks_input.toPlainText().strip()
            payment_method_raw = self.payment_method.currentText()

            if not name or not phone:
                self.show_message(
                    self.tr("Missing Info"),
                    self.tr("Please fill in all required fields."),
                    QMessageBox.Icon.Warning,
                )
                return

            seen = {}
            total_collected = 0
            services_to_log: List[Tuple[str, int, int, int]] = []

            # ---- collect & deduplicate services from UI ----
            for _, service_input, base_input, charge_input, total_input in self.service_fields:
                raw = service_input.currentText().strip()
                try:
                    base_amt = int(base_input.text()) if base_input.text() else 0
                    charge_amt = int(charge_input.text()) if charge_input.text() else 0
                    total_amt = int(total_input.text()) if total_input.text() else base_amt + charge_amt
                except Exception:
                    self.show_message(
                        self.tr("Invalid Amount"),
                        self.tr("Please enter valid numeric amounts."),
                        QMessageBox.Icon.Warning,
                    )
                    return

                if not raw:
                    self.show_message(
                        self.tr("Missing Info"),
                        self.tr("Please fill in all service fields."),
                        QMessageBox.Icon.Warning,
                    )
                    return

                # try to map to an approved canonical name
                canonical = None
                for s in self.services_db:
                    if s.lower() == raw.lower() and s in self.approved_services:
                        canonical = s
                        break

                if canonical is None:
                    approved_lower = [s.lower() for s in self.approved_services]
                    fuzzy = difflib.get_close_matches(raw.lower(), approved_lower, n=1, cutoff=0.8)
                    if fuzzy:
                        canonical = next((s for s in self.approved_services if s.lower() == fuzzy[0]), None)

                final_name = canonical or raw
                key = final_name.lower()
                if key not in seen:
                    seen[key] = (final_name, base_amt, charge_amt, total_amt)
                    total_collected += total_amt
                    services_to_log.append((final_name, base_amt, charge_amt, total_amt))

            services_to_log = list(seen.values())
            if not services_to_log:
                self.show_message(
                    self.tr("Missing Info"),
                    self.tr("Please add at least one service."),
                    QMessageBox.Icon.Warning,
                )
                return

            # ---- create log row ----
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_id = str(uuid.uuid4())

            log_data = {
                "id": log_id,
                "staff_id": self.staff_id,
                "name": name,
                "phone": phone,
                "remarks": remarks,
                "timestamp": timestamp
            }

            try:
                post_with_retries("logs", log_data)
            except Exception as e:
                raise Exception(f"Failed to create log: {e}")

            # ---- create services + payments (AND suggestions for new names) ----
            for svc_name, base_amt, charge_amt, total_amt in services_to_log:
                is_approved = svc_name in self.approved_services
                status_val = "approved" if is_approved else "pending"
                svc_id: Optional[str] = None

                # always create a row in services table
                service_data = {
                    "log_id": log_id,
                    "service": svc_name,
                    "amount": None,
                    "status": status_val,
                }
                try:
                    print("DEBUG: inserting service payload:", service_data)
                except Exception:
                    pass

                try:
                    svc_resp = post_with_retries("services", service_data)
                    try:
                        j = svc_resp.json()
                        if isinstance(j, list) and j:
                            svc_id = j[0].get("id")
                        elif isinstance(j, dict):
                            svc_id = j.get("id")
                    except Exception:
                        svc_id = None
                except Exception:
                    svc_id = None  # keep going; payments will just have service_id=None

                # if NOT approved yet, also add to service_suggestions (for admin UI)
                if not is_approved:
                    suggestion_payload = {
                        "service": svc_name,
                        "suggested_by": self.staff_id,
                        "status": "pending",
                    }
                    try:
                        print("DEBUG: inserting suggestion payload:", suggestion_payload)
                    except Exception:
                        pass
                    try:
                        post_with_retries("service_suggestions", suggestion_payload)
                    except Exception:
                        # suggestion failure should not break main save
                        pass

                # payment row linked to service_id (if we got one)
                payment_method = payment_method_raw.lower().strip()
                payment_record = {
                    "log_id": log_id,
                    "service_id": svc_id,
                    "amount": total_amt,
                    "base_amount": base_amt,
                    "service_charge": charge_amt,
                    "payment_method": payment_method,
                    "payment_ref": None,
                    "received_at": timestamp,
                    "created_by": self.staff_id,
                    "notes": remarks if remarks else ""
                }

                try:
                    print("DEBUG: inserting payment payload:", payment_record)
                except Exception:
                    pass

                try:
                    post_with_retries("payments", payment_record)
                except Exception:
                    pass

            self.show_message(
                self.tr("Success"),
                self.tr("✅ Data submitted successfully!"),
                QMessageBox.Icon.Information,
            )
            self.clear_form()

        except Exception as e:
            self.show_message(
                self.tr("Error"),
                self.tr("❌ Failed to save to Supabase:\n") + str(e),
                QMessageBox.Icon.Critical,
            )
        finally:
            try:
                self.submit_btn.setEnabled(True)
            except Exception:
                pass
            try:
                self.status_label.setText("")
            except Exception:
                pass


    def clear_form(self):
        self.customer_name_input.clear()
        self.phone_input.clear()
        self.remarks_input.clear()
        try:
            self.payment_method.setCurrentText("Cash")
        except Exception:
            pass
        for row_widget, _, _, _, _ in list(self.service_fields):
            row_widget.setParent(None)
            row_widget.deleteLater()
        self.service_fields.clear()
        self.add_service_entry()

    # ---------- shared save helper for required documents ----------
    def _save_service_docs(self, service_name: str, docs_list: List[str]) -> bool:
        """Shared save callback for Add/Edit required documents."""
        if not service_name:
            return False
        try:
            if save_service_documents_upsert is not None:
                return save_service_documents_upsert(service_name, docs_list, created_by=self.staff_id)
            if save_service_documents is not None:
                return save_service_documents(service_name, docs_list, created_by=self.staff_id)

            payload = {
                "service": service_name,
                "documents": docs_list,
                "created_by": self.staff_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            post_with_retries("service_documents", payload)
            return True
        except Exception:
            return False

    # ---------- fetch helper for required documents ----------
    def _fetch_service_docs(self) -> List[dict]:
        """Fetch required documents from helper or supabase_get."""
        try:
            if get_service_documents is not None:
                return get_service_documents() or []
        except Exception:
            pass
        try:
            resp = supabase_get("service_documents", filter_query=None, select="*")
            if resp and getattr(resp, "status_code", None) == 200:
                return resp.json() or []
        except Exception:
            pass
        return []

    # ------------- sidebar actions (updated to use external modules) --------------
    def show_recent_work(self):
        self._mark_sidebar(self.btn_recent)
        try:
            try:
                from .recent_work import RecentWorkDialog  # type: ignore
            except Exception:
                from gui.recent_work import RecentWorkDialog  # type: ignore
            dlg = RecentWorkDialog(self.staff_id, self)
            dlg.exec()
        except Exception:
            QMessageBox.information(self, "Recent Work", "(recent work dialog unavailable)")

    def show_search_dialog(self):
        self._mark_sidebar(self.btn_search)
        try:
            try:
                from .search_dialog import SearchDialog  # type: ignore
            except Exception:
                from gui.search_dialog import SearchDialog  # type: ignore
            self.search_dialog = SearchDialog(self.staff_id, self)
            self.search_dialog.exec()
        except Exception:
            QMessageBox.information(self, "Search", "(search dialog unavailable)")

    def show_add_required_documents(self):
        self._mark_sidebar(self.btn_add_required)

        def fetch_docs():
            try:
                if get_service_documents is not None:
                    return get_service_documents()
            except Exception:
                pass
            try:
                resp = supabase_get("service_documents", filter_query=None, select="*")
                if resp and getattr(resp, "status_code", None) == 200:
                    return resp.json() or []
            except Exception:
                pass
            return []

        docs_rows = fetch_docs()

        services_from_docs = sorted({
            r.get("service") or r.get("service_name") or ""
            for r in docs_rows
            if isinstance(r, dict) and (r.get("service") or r.get("service_name"))
        })

        doc_suggestions_set = set()
        for r in docs_rows:
            if not isinstance(r, dict):
                continue
            docs_list = r.get("documents") or []
            if isinstance(docs_list, str):
                docs_list = [p.strip() for p in docs_list.split(",") if p.strip()]
            for d in docs_list:
                if isinstance(d, str) and d.strip():
                    doc_suggestions_set.add(d.strip())

        doc_suggestions = sorted(doc_suggestions_set)

        def save_docs(service_name: str, docs_list: List[str]) -> bool:
            if not service_name:
                return False
            try:
                if save_service_documents_upsert is not None:
                    return save_service_documents_upsert(service_name, docs_list, created_by=self.staff_id)
                if save_service_documents is not None:
                    return save_service_documents(service_name, docs_list, created_by=self.staff_id)
                payload = {
                    "service": service_name,
                    "documents": docs_list,
                    "created_by": self.staff_id,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                try:
                    post_with_retries("service_documents", payload)
                    return True
                except Exception:
                    return False
            except Exception:
                return False

        try:
            try:
                from gui.add_required_documents import AddRequiredDocumentsDialog  # type: ignore
            except Exception:
                from add_required_documents import AddRequiredDocumentsDialog

            dlg = AddRequiredDocumentsDialog(
                parent=self,
                services=services_from_docs,         # 👈 from required-docs table only
                doc_suggestions=doc_suggestions,    # 👈 all previously-used doc names
                save_callback=save_docs
            )
            try:
                dlg.setStyleSheet(
                    dlg.styleSheet()
                    + "\nQWidget { background: #ffffff; color: #111827; }\n"
                      "QLineEdit, QTextEdit { background: #ffffff; color: #111827; }\n"
                )
            except Exception:
                pass
            dlg.exec()
        except Exception:
            QMessageBox.information(
                self, "Missing module",
                "Could not open Add Required Documents dialog."
            )

    def _open_edit_required_documents_from_view(self, view_dlg, rec: dict):
        service_name = rec.get("service") or rec.get("service_name") or ""
        docs_list = rec.get("documents") or []

        try:
            try:
                from gui.add_required_documents import AddRequiredDocumentsDialog  # type: ignore
            except Exception:
                from add_required_documents import AddRequiredDocumentsDialog  # type: ignore
        except Exception:
            QMessageBox.critical(
                self,
                "Error",
                "Could not import AddRequiredDocumentsDialog"
            )
            return

        def save_docs(svc: str, docs: List[str]) -> bool:
            ok = self._save_service_docs(svc, docs)
            if ok:
                self.services_db.append(svc)
                self.services_db = sorted(set(self.services_db))
                self._refresh_completer_and_combos()
            return ok

        try:
            dlg = AddRequiredDocumentsDialog(
                parent=self,
                services=list(self.services_db),
                save_callback=save_docs,
                initial_service=service_name,
                initial_documents=docs_list,
                edit_mode=True,
            )
        except TypeError:
            dlg = AddRequiredDocumentsDialog(
                parent=self,
                services=list(self.services_db),
                save_callback=save_docs,
            )

        try:
            dlg.setStyleSheet(
                dlg.styleSheet()
                + "\nQWidget { background: #ffffff; color: #111827; }\n"
            )
        except Exception:
            pass

        dlg.exec()

        try:
            updated_docs = self._fetch_service_docs()
            if hasattr(view_dlg, "load_services"):
                view_dlg.load_services(updated_docs)
        except Exception:
            pass

    def show_view_required_documents(self):
        self._mark_sidebar(self.btn_view_required)

        try:
            try:
                from gui.view_required_documents import ViewRequiredDocumentsDialog  # type: ignore
            except ModuleNotFoundError:
                from view_required_documents import ViewRequiredDocumentsDialog  # type: ignore
        except ModuleNotFoundError:
            QMessageBox.information(
                self,
                "Missing module",
                "Could not open View Required Documents dialog."
            )
            return
        except Exception:
            QMessageBox.critical(
                self,
                "Import error",
                "Failed to import 'view_required_documents.py'"
            )
            return

        try:
            docs = self._fetch_service_docs()
            dlg = ViewRequiredDocumentsDialog(parent=self, docs=docs)

            try:
                dlg.edit_clicked.connect(lambda rec, d=dlg: self._open_edit_required_documents_from_view(d, rec))
            except Exception:
                pass
            try:
                dlg.back_clicked.connect(dlg.close)
            except Exception:
                pass

            try:
                dlg.setStyleSheet(
                    dlg.styleSheet()
                    + "\nQWidget { background: #ffffff; color: #111827; }\n"
                )
            except Exception:
                pass
            dlg.exec()
        except Exception:
            QMessageBox.critical(
                self,
                "Error",
                "Could not open View Required Documents dialog."
            )

    def handle_print(self):
        self._mark_sidebar(self.btn_print)
        QMessageBox.information(self, self.tr("Print"), self.tr("🖨️ This will trigger the print dialog."))

    def handle_logout(self):
        # show a small info then emit logout signal for parent to handle stack switch
        box = QMessageBox(self)
        box.setWindowTitle("Logout")
        box.setText("👋 You have been logged out.")
        box.setIcon(QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet("""
            QMessageBox { background-color: #ffffff; }
            QMessageBox QLabel { color: #0f172a; font-size: 14px; }
            QMessageBox QPushButton { background-color: #06B6D4; color: #ffffff; border-radius: 6px; padding: 6px 12px; }
            QMessageBox QPushButton:hover { background-color: #0891B2; }
        """)
        box.exec()
        self.logout_requested.emit()

    def _mark_sidebar(self, active_btn: QPushButton):
        for btn in getattr(self, "sidebar_buttons", []):
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        active_btn.blockSignals(True)
        active_btn.setChecked(True)
        active_btn.blockSignals(False)


if __name__ == '__main__':
    # Enable High DPI scaling for crisp rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = StaffDashboard(staff_id="s001", staff_name="Abhinav", lang="English")
    win.show()
    sys.exit(app.exec())
