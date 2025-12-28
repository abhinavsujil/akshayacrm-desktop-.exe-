from __future__ import annotations
from typing import List
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QFrame, QHBoxLayout,
    QPushButton, QMessageBox, QWidget, QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QFont


# -------------------- STYLE --------------------
LIGHT_STYLES = """
QDialog {
    background-color: #E8EEF3;
    font-family: 'Segoe UI', sans-serif;
}

QFrame#mainCard {
    background: #FFFFFF;
    border-radius: 20px;
    border: 1px solid #E2E8F0;
}

QLabel#backButton {
    color: #3B82F6;
    font-size: 13px;
}
QLabel#backButton:hover {
    color: #2563EB;
    text-decoration: underline;
}

QLabel#titleLabel {
    font-size: 22px;
    font-weight: bold;
    color: #1a1a1a;
}

QLabel.metaLabel {
    font-size: 13px;
    color: #64748B;
}

QComboBox {
    background: white;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 36px;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #64748B;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: white;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    selection-background-color: #3B82F6;
    selection-color: white;
    padding: 4px;
}

QFrame#docContainer {
    background: #F1F5F9;
    border-radius: 16px;
    border: 1px solid #E2E8F0;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QPushButton#editButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #06B6D4, stop:1 #0891B2);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 24px;
    min-height: 40px;
    max-width: 280px;
}

QPushButton#editButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0891B2, stop:1 #0E7490);
}

QPushButton#editButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0E7490, stop:1 #155E75);
}
"""

DOC_ITEM_STYLE = """
QFrame#docItem {
    background: white;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
}

QFrame#docItem:hover {
    border-color: #3B82F6;
}

QLabel#docIcon {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    font-size: 22px;
}

QLabel#docText {
    color: #1E293B;
    font-size: 13px;
}

QPushButton#infoButton {
    background: white;
    border: 1.5px solid #CBD5E1;
    border-radius: 18px;
    color: #64748B;
    font-weight: bold;
    font-size: 13px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
}

QPushButton#infoButton:hover {
    border-color: #3B82F6;
    color: #3B82F6;
    background: #F8FAFC;
}
"""


# ------------- Date Formatting -------------
def format_date(raw: str) -> str:
    """Convert ISO timestamp to: 24 - November - 2025, Monday"""
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d - %B - %Y, %A")
    except Exception:
        return raw


# -------------------- DOCUMENT ITEM WIDGET --------------------
class DocumentItemWidget(QWidget):
    """Individual document row with icon, text, and info button"""
    
    def __init__(self, number: int, text: str, parent=None):
        super().__init__(parent)
        
        # Main frame
        self.frame = QFrame()
        self.frame.setObjectName("docItem")
        self.frame.setStyleSheet(DOC_ITEM_STYLE)
        self.frame.setFixedHeight(80)
        
        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(16)
        
        # Icon
        icon_label = QLabel("📄")
        icon_label.setObjectName("docIcon")
        icon_label.setFixedSize(50, 50)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Text
        text_label = QLabel(f"{number}. {text}")
        text_label.setObjectName("docText")
        text_label.setWordWrap(True)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Info button
        info_btn = QPushButton("i")
        info_btn.setObjectName("infoButton")
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.clicked.connect(lambda: self.show_info(text))
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label, 1)
        layout.addWidget(info_btn)
        
        # Wrap in container
        container = QVBoxLayout(self)
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(self.frame)
    
    def show_info(self, text: str):
        QMessageBox.information(self, "Document Info", text)


# -------------------- MAIN DIALOG --------------------
class ViewRequiredDocumentsDialog(QDialog):
    # 🔹 now sends the selected record dict
    edit_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()
    
    def __init__(self, parent=None, docs=None):
        super().__init__(parent)
        
        self.docs_data = docs or []
        self.records: List[dict] = []
        
        self.setWindowTitle("Required Documents")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)
        
        # Window flags - resizable with minimize/close (no maximize as per requirements)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self.setStyleSheet(LIGHT_STYLES)
        self.setup_ui()
        self.load_services(docs or [])
    
    def setup_ui(self):
        # Main layout with outer padding
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # White card
        card = QFrame()
        card.setObjectName("mainCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 35, 40, 35)
        card_layout.setSpacing(20)
        
        # Back button
        back_label = QLabel("← Back to List")
        back_label.setObjectName("backButton")
        back_label.setCursor(Qt.CursorShape.PointingHandCursor)
        back_label.mousePressEvent = lambda e: self.back_clicked.emit()
        card_layout.addWidget(back_label)
        
        # Title with folder icon
        title_container = QHBoxLayout()
        title_icon = QLabel("📁")
        title_icon.setFont(QFont("Segoe UI", 22))
        
        self.title_label = QLabel("Required Documents: 10th Markscard")
        self.title_label.setObjectName("titleLabel")
        
        title_container.addWidget(title_icon)
        title_container.addWidget(self.title_label)
        title_container.addStretch()
        card_layout.addLayout(title_container)
        
        # Metadata grid (2 columns)
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(60)
        
        # Left column
        left_meta = QVBoxLayout()
        left_meta.setSpacing(8)
        self.lbl_service_name = QLabel("Service Name: 10th Markscard")
        self.lbl_service_name.setProperty("class", "metaLabel")
        self.lbl_type = QLabel("Document Type:")
        self.lbl_type.setProperty("class", "metaLabel")
        left_meta.addWidget(self.lbl_service_name)
        left_meta.addWidget(self.lbl_type)
        
        # Right column
        right_meta = QVBoxLayout()
        right_meta.setSpacing(8)
        self.lbl_date = QLabel("Upload Date: 24 - November - 2025, Monday")
        self.lbl_date.setProperty("class", "metaLabel")
        self.lbl_uploaded_by = QLabel("Uploaded By: abhi")
        self.lbl_uploaded_by.setProperty("class", "metaLabel")
        right_meta.addWidget(self.lbl_date)
        right_meta.addWidget(self.lbl_uploaded_by)
        
        meta_layout.addLayout(left_meta)
        meta_layout.addLayout(right_meta)
        meta_layout.addStretch()
        
        card_layout.addLayout(meta_layout)
        
        # Service dropdown
        dropdown_container = QHBoxLayout()
        self.service_combo = QComboBox()
        self.service_combo.setMinimumWidth(300)
        self.service_combo.currentIndexChanged.connect(self.on_service_changed)
        dropdown_container.addWidget(self.service_combo)
        dropdown_container.addStretch()
        card_layout.addLayout(dropdown_container)
        
        # Large grey document container
        doc_container = QFrame()
        doc_container.setObjectName("docContainer")
        doc_container_layout = QVBoxLayout(doc_container)
        doc_container_layout.setContentsMargins(25, 25, 25, 25)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 8, 0)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.scroll_content)
        doc_container_layout.addWidget(scroll)
        
        card_layout.addWidget(doc_container, 1)  # Stretch factor makes it fill space
        
        # Edit button (compact, centered)
        edit_btn_container = QHBoxLayout()
        edit_btn_container.setContentsMargins(0, 8, 0, 0)
        
        edit_btn = QPushButton("✏️ Edit Required Documents")
        edit_btn.setObjectName("editButton")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self.on_edit_clicked)
        
        edit_btn_container.addStretch()
        edit_btn_container.addWidget(edit_btn)
        edit_btn_container.addStretch()
        
        card_layout.addLayout(edit_btn_container)
        
        main_layout.addWidget(card)
    
    def load_services(self, recs: List[dict]):
        """Load and normalize document records"""
        try:
            cleaned = []
            for r in recs:
                if not isinstance(r, dict):
                    continue
                
                svc = r.get("service") or r.get("service_name") or "Unnamed Service"
                docs = r.get("documents") or []
                if isinstance(docs, str):
                    docs = [d.strip() for d in docs.split(",") if d.strip()]
                
                created_by = r.get("created_by") or r.get("uploaded_by") or "—"
                created_at = r.get("created_at") or r.get("upload_date") or ""
                doc_type = r.get("type") or r.get("document_type") or ""
                
                cleaned.append({
                    "service": svc,
                    "documents": docs,
                    "created_by": created_by,
                    "created_at": created_at,
                    "type": doc_type,
                    "raw": r,          # 🔹 keep original row for editing
                })
            
            self.records = cleaned
        except Exception as e:
            print(f"Error loading services: {e}")
            self.records = []
        
        # Populate combo box
        self.service_combo.blockSignals(True)
        self.service_combo.clear()
        for rec in self.records:
            self.service_combo.addItem(rec["service"])
        self.service_combo.blockSignals(False)
        
        if self.records:
            self.service_combo.setCurrentIndex(0)
            self.populate_documents(0)
    
    def on_service_changed(self, index: int):
        self.populate_documents(index)
    
    def populate_documents(self, index: int):
        """Populate UI with selected service data"""
        # Clear existing documents
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if index < 0 or index >= len(self.records):
            return
        
        rec = self.records[index]
        
        # Update title and metadata
        svc_name = rec["service"]
        self.title_label.setText(f"Required Documents: {svc_name}")
        self.lbl_service_name.setText(f"Service Name: {svc_name}")
        self.lbl_type.setText(f"Document Type: {rec['type']}")
        self.lbl_date.setText(f"Upload Date: {format_date(rec['created_at'])}")
        self.lbl_uploaded_by.setText(f"Uploaded By: {rec['created_by']}")
        
        # Add document items
        docs = rec.get("documents", [])
        for i, doc in enumerate(docs, 1):
            item_widget = DocumentItemWidget(i, doc)
            self.scroll_layout.addWidget(item_widget)
        
        # Add stretch at the end
        self.scroll_layout.addStretch()
    
    def on_edit_clicked(self):
        """Emit the current record so parent can open edit dialog."""
        idx = self.service_combo.currentIndex()
        if idx < 0 or idx >= len(self.records):
            QMessageBox.information(self, "No Service", "Please select a service first.")
            return

        rec = self.records[idx]
        # parent will receive rec (with rec["raw"] = original DB row)
        self.edit_clicked.emit(rec)


# -------------------- TEST CODE --------------------
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Sample data matching your format
    sample_docs = [
        {
            "id": 1,
            "service": "10th Markscard",
            "documents": ["service", "sslc proof"],
            "created_by": "abhi",
            "created_at": "2025-11-24T16:56:13.774922+00:00",
            "document_type": ""
        },
        {
            "id": 2,
            "service": "Birth Certificate Application",
            "documents": [
                "Proof of Identity (e.g., Voter ID, Passport)",
                "Proof of Address (e.g., Utility Bill, Rent Agreement)",
                "Passport Size Photograph"
            ],
            "created_by": "John Doe",
            "created_at": "2023-10-25T14:30:00+00:00",
            "document_type": "Identity Proof"
        }
    ]
    
    dialog = ViewRequiredDocumentsDialog(docs=sample_docs)
    dialog.back_clicked.connect(lambda: print("Back clicked"))
    dialog.edit_clicked.connect(lambda rec: print("Edit clicked for:", rec["service"], "id:", rec["raw"].get("id")))
    dialog.show()
    
    sys.exit(app.exec())
