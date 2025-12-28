# gui/add_required_documents.py
from __future__ import annotations
from typing import List, Callable, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QWidget, QMessageBox, QScrollArea, QFrame, QSizePolicy, QSpacerItem,
    QCompleter,               # 👈 add this
)


from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QWidget, QMessageBox, QScrollArea, QFrame,
    QSizePolicy, QSpacerItem, QCompleter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# Optional: try to get existing documents from Supabase for suggestions
try:
    from supabase_utils import get_service_documents, supabase_get  # type: ignore
except Exception:  # if not available, fall back gracefully
    get_service_documents = None  # type: ignore

    def supabase_get(*args, **kwargs):  # type: ignore
        return None


LIGHT_STYLES = """
/* enforce light dialog style so parent's sidebar styles don't leak in */
QDialog { background-color: #F8FAFC; color: #0F172A; }
QFrame#container { background-color: #FFFFFF; border-radius: 10px; border: 1px solid #e6edf3; padding: 16px; }
QLabel { color: #0f172a; }
QLineEdit { background: #FFFFFF; border: 1px solid #d1dbe4; border-radius: 8px; padding: 10px; }
QComboBox { background: #FFFFFF; border: 1px solid #d1dbe4; border-radius: 8px; padding: 8px; }
QPushButton#primary { background: #06B6D4; color: white; border-radius: 10px; padding: 10px 14px; }
QPushButton#secondary { background: #E6F6D8; color: #055A63; border-radius: 8px; padding: 8px 12px; }
QPushButton.removeBtn { background: transparent; border: 1px solid #e6edf3; border-radius: 18px; min-width: 36px; min-height: 36px; }
"""


class AddRequiredDocumentsDialog(QDialog):
    """
    Dialog to add required documents for a service.
    Expected usage:
        dlg = AddRequiredDocumentsDialog(
            parent=self,
            services=list_of_services_from_docs_table,
            doc_suggestions=list_of_all_doc_names,
            save_callback=callable
        )
    save_callback signature: save_callback(service_name: str, docs_list: List[str]) -> bool
    """

    def __init__(
        self,
        parent=None,
        services: Optional[List[str]] = None,
        doc_suggestions: Optional[List[str]] = None,
        save_callback: Optional[Callable] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Document Requirements Manager")
        self.setMinimumSize(780, 520)
        self.setStyleSheet(LIGHT_STYLES)

        # 👇 data sources for suggestions
        self.services = services or []
        self.doc_suggestions = sorted(set(doc_suggestions or []))
        self.save_callback = save_callback

        # completers (created once, reused)
        self.service_completer: Optional[QCompleter] = None
        self.doc_completer: Optional[QCompleter] = None

        root = QVBoxLayout(self)

        container = QFrame()
        container.setObjectName("container")
        root.addWidget(container)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)

        title = QLabel("📂 Document Requirements Manager")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Service select
        lbl_service = QLabel("Select Service Name")
        lbl_service.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        layout.addWidget(lbl_service)

        self.service_combo = QComboBox()
        self.service_combo.setEditable(True)
        self.service_combo.addItems(self.services)
        self.service_combo.setPlaceholderText("Select Service Name...")
        self.service_combo.setMinimumHeight(36)
        layout.addWidget(self.service_combo)

        # 👇 create completer for services (FROM docs table only)
        if self.services:
            self.service_completer = QCompleter(sorted(set(self.services)), self)
            self.service_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.service_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.service_combo.setCompleter(self.service_completer)

        # 👇 create completer for individual document fields
        if self.doc_suggestions:
            self.doc_completer = QCompleter(self.doc_suggestions, self)
            self.doc_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.doc_completer.setFilterMode(Qt.MatchFlag.MatchContains)

        # Required documents area (scrollable)
        lbl_docs = QLabel("Required Documents")
        lbl_docs.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        layout.addWidget(lbl_docs)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, stretch=1)

        inner = QWidget()
        self.scroll.setWidget(inner)
        self.docs_layout = QVBoxLayout(inner)
        self.docs_layout.setSpacing(12)

        # store rows as tuples (label_widget, edit_widget, remove_button, row_frame)
        self.doc_rows = []

        # initial 3 rows like your design (Document 1..3)
        self._add_doc_row("Document 1", "")
        self._add_doc_row("Document 2", "")
        self._add_doc_row("Document 3", "")

        # add more button + save button row
        row = QHBoxLayout()
        add_btn = QPushButton("+ Add More Documents")
        add_btn.setObjectName("secondary")
        add_btn.clicked.connect(lambda: self._add_doc_row(f"Document {len(self.doc_rows)+1}", ""))
        row.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        row.addStretch()
        save_btn = QPushButton("Save Documents")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._on_save)
        row.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)


    # ---------- suggestion builders ----------

    def _build_service_completer(self):
        """Completer for the service combo (Aad -> Aadhaar, etc.)."""
        if not self.services:
            self.service_completer = None
            return

        unique_services = sorted(set(self.services))
        comp = QCompleter(unique_services, self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)  # contains, not just prefix
        self.service_completer = comp

    def _build_doc_completer(self):
        """
        Build a completer for document name fields from all
        documents in the service_documents table (if available).
        """
        suggestions: set[str] = set()
        records = None

        try:
            if get_service_documents is not None:
                # helper that already exists in your project
                records = get_service_documents()
            else:
                # generic Supabase GET as a fallback
                resp = supabase_get(
                    "service_documents",
                    filter_query=None,
                    select="documents",
                )
                if resp is not None and getattr(resp, "status_code", None) == 200:
                    records = resp.json() or []
        except Exception as e:
            print("[AddRequiredDocumentsDialog] doc suggestions load failed:", e)
            records = None

        if records:
            for rec in records:
                docs_field = rec.get("documents") or []
                if isinstance(docs_field, list):
                    docs_iter = docs_field
                elif isinstance(docs_field, str):
                    docs_iter = [
                        d.strip() for d in docs_field.split(",") if d.strip()
                    ]
                else:
                    continue
                for d in docs_iter:
                    suggestions.add(d)

        if suggestions:
            docs_list = sorted(suggestions)
            comp = QCompleter(docs_list, self)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.doc_completer = comp
        else:
            self.doc_completer = None

    # ---------- row helpers ----------

    def _add_doc_row(self, label_text: str, text: Optional[str]):
        """
        Adds one document row. text can be None or a string; always convert to str for setText.
        """
        text_value = "" if text is None else str(text)

        row_frame = QFrame()
        row_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(6, 6, 6, 6)

        label = QLabel(label_text)
        label.setFixedWidth(120)
        row_layout.addWidget(label)

        edit = QLineEdit()
        edit.setPlaceholderText("Enter document name")
        edit.setText(text_value)

        # 👇 attach document-name completer (from required-docs table)
        if self.doc_completer is not None:
            edit.setCompleter(self.doc_completer)

        row_layout.addWidget(edit, stretch=1)

        remove = QPushButton("✕")
        remove.setProperty("class", "removeBtn")
        remove.clicked.connect(lambda _, f=row_frame: self._remove_row(f))
        row_layout.addWidget(remove)

        self.docs_layout.addWidget(row_frame)
        self.doc_rows.append((label, edit, remove, row_frame))


    def _remove_row(self, frame):
        # remove the row, renumber labels
        new_rows = []
        for i, (label, edit, rm, fr) in enumerate(self.doc_rows, start=1):
            if fr is frame:
                fr.setParent(None)
                fr.deleteLater()
                continue
            new_rows.append((label, edit, rm, fr))
        self.doc_rows = new_rows
        # re-label the remaining
        for idx, (label, _, _, _) in enumerate(self.doc_rows, start=1):
            label.setText(f"Document {idx}")

    # ---------- save ----------

    def _on_save(self):
        service = self.service_combo.currentText().strip()
        if not service:
            QMessageBox.warning(
                self, "Missing Service", "Please select or enter a service name."
            )
            return

        docs = []
        for _, edit, _, _ in self.doc_rows:
            txt = (edit.text() or "").strip()
            if txt:
                docs.append(txt)

        if not docs:
            QMessageBox.warning(
                self, "No Documents", "Please add at least one document."
            )
            return

        # Call save callback if provided
        if callable(self.save_callback):
            ok = False
            try:
                ok = bool(self.save_callback(service, docs))
            except Exception as e:
                print("[AddRequiredDocumentsDialog] save_callback exception:", e)
                ok = False

            if ok:
                QMessageBox.information(
                    self, "Saved", "Required documents saved successfully."
                )
                self.accept()
                return
            else:
                QMessageBox.critical(
                    self,
                    "Save failed",
                    "Failed to save documents. Check logs or supabase connectivity.",
                )
                return
        else:
            # no save callback: show what would be saved
            QMessageBox.information(
                self, "Preview", f"Service: {service}\nDocuments: {docs}"
            )
            self.accept()
