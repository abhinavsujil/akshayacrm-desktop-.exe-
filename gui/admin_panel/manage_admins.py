# gui/admin_panel/manage_admins.py

from __future__ import annotations

from typing import Any, List

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QComboBox,
    QMessageBox,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from supabase_utils import supabase_get, supabase_post, supabase_patch


# ------------------------------------------------------------------ #
# Utility: styled message box
# ------------------------------------------------------------------ #
def _show_message(parent, icon: QMessageBox.Icon, title: str, text: str):
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStyleSheet(
        """
        QMessageBox {
            background-color: #ffffff;
        }
        QLabel {
            color: #000000;
            font-size: 13px;
        }
        QPushButton {
            min-width: 80px;
            padding: 4px 14px;
            background-color: #2E1A6B;
            color: #ffffff;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #3d2b8a;
        }
        """
    )
    box.exec()


# ------------------------------------------------------------------ #
# Dialog to add / edit a single admin
# ------------------------------------------------------------------ #
class AdminEditDialog(QDialog):
    """
    Dialog to add / edit an admin record.

    Fields:
      - Admin ID (required, immutable when editing)
      - Name
      - Phone
      - Password (plain text, prefilled when editing)
      - Active (Yes/No)
    """

    def __init__(self, parent=None, existing: dict | None = None):
        super().__init__(parent)
        self._existing = existing or {}

        self.setWindowTitle("Edit Admin" if existing else "Add Admin")
        self.setMinimumWidth(420)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel(self.windowTitle())
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Manage admin credentials and access.")
        subtitle.setFont(QFont("Inter", 10))
        subtitle.setStyleSheet("color: #64748b;")
        layout.addWidget(subtitle)

        # ID
        layout.addWidget(self._field_label("Admin ID"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Unique admin ID (used for login)")
        self.id_input.setText(str(self._existing.get("id") or ""))
        if self._existing:
            self.id_input.setReadOnly(True)
        layout.addWidget(self.id_input)

        # Name
        layout.addWidget(self._field_label("Name"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full name")
        self.name_input.setText(str(self._existing.get("name") or ""))
        layout.addWidget(self.name_input)

        # Phone
        layout.addWidget(self._field_label("Phone"))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone number")
        self.phone_input.setText(str(self._existing.get("phone") or ""))
        layout.addWidget(self.phone_input)

        # Password (plain text)
        layout.addWidget(self._field_label("Password"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(
            "Set a password (leave blank to keep existing)"
            if self._existing
            else "Set password"
        )
        # prefill existing password in plain text
        if self._existing:
            self.password_input.setText(str(self._existing.get("password") or ""))
        layout.addWidget(self.password_input)

        # Active?
        layout.addWidget(self._field_label("Active"))
        self.active_combo = QComboBox()
        self.active_combo.addItems(["Yes", "No"])
        is_active = self._existing.get("is_active")
        self.active_combo.setCurrentText("No" if is_active is False else "Yes")
        layout.addWidget(self.active_combo)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setObjectName("dialogCancelButton")

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_btn.setObjectName("dialogPrimaryButton")

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # Style for fields + dialog buttons
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f8fafc;
            }
            QLineEdit {
                background: #ffffff;
                border-radius: 8px;
                border: 1px solid #cbd5e1;
                padding: 8px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00B8D4;
            }
            QComboBox {
                background: #ffffff;
                border-radius: 8px;
                border: 1px solid #cbd5e1;
                padding: 6px 10px;
                font-size: 13px;
            }
            QPushButton#dialogPrimaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #2E1A6B, stop:1 #00B8D4);
                color: #ffffff;
                border-radius: 999px;
                padding: 6px 22px;
                font-weight: 600;
            }
            QPushButton#dialogPrimaryButton:hover {
                background-color: #3b2a90;
            }
            QPushButton#dialogCancelButton {
                background: transparent;
                color: #475569;
                border-radius: 999px;
                padding: 6px 16px;
                border: 1px solid #cbd5e1;
            }
            QPushButton#dialogCancelButton:hover {
                background: #e2e8f0;
            }
            """
        )

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        lbl.setStyleSheet("color: #0f172a;")
        return lbl

    def get_data(self) -> dict[str, Any] | None:
        admin_id = (self.id_input.text() or "").strip()
        name = (self.name_input.text() or "").strip()
        phone = (self.phone_input.text() or "").strip()
        password = (self.password_input.text() or "").strip()
        is_active = self.active_combo.currentText() == "Yes"

        if not admin_id:
            _show_message(self, QMessageBox.Icon.Warning, "Validation error", "Admin ID is required.")
            return None

        data: dict[str, Any] = {
            "id": admin_id,
            "name": name or None,
            "phone": phone or None,
            "is_active": is_active,
        }

        if password != "":
            data["password"] = password

        return data


# ------------------------------------------------------------------ #
# Main Manage Admins dialog
# ------------------------------------------------------------------ #
class ManageAdminsDialog(QDialog):
    """
    Admin screen to manage admin accounts.

    Uses Supabase table: `admins`
    Columns used:
        id, name, phone, password, is_active, created_at (optional)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Manage Admins")
        self.setMinimumSize(900, 540)

        self.table: QTableWidget | None = None
        self.search_input: QLineEdit | None = None

        self._rows_cache: List[dict] = []

        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #e5edf7;
            }
            QLabel {
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QFrame#card {
                background-color: #f9fafb;
                border-radius: 22px;
            }
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 16)
        card_layout.setSpacing(10)

        # Header
        header = QFrame()
        header.setFixedHeight(90)
        header.setStyleSheet(
            """
            QFrame {
                border-top-left-radius: 22px;
                border-top-right-radius: 22px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #2E1A6B, stop:1 #00B8D4);
            }
            """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 18, 24, 18)

        left_header = QVBoxLayout()
        title_row = QHBoxLayout()
        icon_lbl = QLabel("👤👤")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))
        icon_lbl.setStyleSheet("color: #A5F3FC;")
        title_row.addWidget(icon_lbl)

        title_lbl = QLabel("Manage Admins")
        title_lbl.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: white;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        left_header.addLayout(title_row)

        subtitle_lbl = QLabel("Control who can access the admin dashboard.")
        subtitle_lbl.setStyleSheet("color: rgba(255,255,255,0.85);")
        subtitle_lbl.setFont(QFont("Inter", 10))
        left_header.addWidget(subtitle_lbl)

        header_layout.addLayout(left_header)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)

        header.setLayout(header_layout)

        header.setStyleSheet(
            header.styleSheet()
            + """
            QPushButton#refreshButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #06b6d4, stop:1 #22c55e);
                color: #ffffff;
                border-radius: 999px;
                padding: 8px 26px;
                font-weight: 600;
                font-size: 13px;
                border: none;
            }
            QPushButton#refreshButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #0891b2, stop:1 #16a34a);
            }
            """
        )

        card_layout.addWidget(header)

        # Body
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(24, 14, 24, 8)
        body_layout.setSpacing(12)

        search_row = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setFont(QFont("Inter", 11, QFont.Weight.Medium))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by admin name or ID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_search_filter)
        self.search_input.setMinimumWidth(260)
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background: #ffffff;
                border-radius: 999px;
                border: 1px solid #cbd5e1;
                padding: 6px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00B8D4;
            }
            """
        )

        search_row.addWidget(search_label)
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addStretch()
        body_layout.addLayout(search_row)

        # Table (with password column)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Admin ID", "Name", "Phone", "Password", "Active", "Created"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background: #ffffff;
                border-radius: 12px;
                gridline-color: #e2e8f0;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #28155A;
                color: #ffffff;
                padding: 8px 6px;
                border: none;
                font-weight: 600;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #e0f2fe;
            }
            """
        )
        body_layout.addWidget(self.table)

        card_layout.addLayout(body_layout)

        # Bottom buttons
        bottom_frame = QFrame()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(24, 4, 24, 10)
        bottom_layout.setSpacing(22)

        add_btn = QPushButton("Add Admin")
        add_btn.setObjectName("bottomPrimary")
        add_btn.clicked.connect(self.add_admin)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.setObjectName("bottomSecondary")
        edit_btn.clicked.connect(self.edit_selected_admin)

        toggle_btn = QPushButton("Toggle Active")
        toggle_btn.setObjectName("bottomSecondary")
        toggle_btn.clicked.connect(self.toggle_active_selected)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("bottomPrimary")
        close_btn.clicked.connect(self.close)

        for btn in (add_btn, edit_btn, toggle_btn, close_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(44)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        bottom_layout.addWidget(add_btn)
        bottom_layout.addWidget(edit_btn)
        bottom_layout.addWidget(toggle_btn)
        bottom_layout.addWidget(close_btn)

        bottom_frame.setStyleSheet(
            """
            QPushButton#bottomPrimary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #00B8D4, stop:1 #22c55e);
                color: #ffffff;
                border-radius: 999px;
                border: none;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton#bottomPrimary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #0891b2, stop:1 #16a34a);
            }
            QPushButton#bottomSecondary {
                background: #2E1A6B;
                color: #ffffff;
                border-radius: 999px;
                border: none;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton#bottomSecondary:hover {
                background: #3d2b8a;
            }
            """
        )

        card_layout.addWidget(bottom_frame)
        outer.addWidget(card)

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def refresh_data(self):
        if not self.table:
            return

        print(">>> [ManageAdmins] refresh_data()")
        self.table.setRowCount(0)

        try:
            resp = supabase_get(
                "admins",
                select="id,name,phone,password,is_active,created_at",
            )
        except Exception as e:
            print(">>> [ManageAdmins] HTTP error:", e)
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to load admin data from Supabase.",
            )
            return

        status = getattr(resp, "status_code", None)
        print(">>> [ManageAdmins] status =", status)

        if status != 200:
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while fetching admins. (status {status})",
            )
            return

        try:
            rows = resp.json() or []
        except Exception as e:
            print(">>> [ManageAdmins] JSON parse error:", e)
            rows = []

        self._rows_cache = rows
        self._populate_table(rows)

    def _populate_table(self, rows: List[dict]):
        self.table.setRowCount(0)

        for row in rows:
            admin_id = str(row.get("id") or "")
            name = str(row.get("name") or "")
            phone = str(row.get("phone") or "")
            pwd_display = str(row.get("password") or "")
            active = row.get("is_active")
            created = str(row.get("created_at") or "")

            active_text = "Yes" if active or active is None else "No"

            r = self.table.rowCount()
            self.table.insertRow(r)

            id_item = QTableWidgetItem(admin_id)
            name_item = QTableWidgetItem(name)
            phone_item = QTableWidgetItem(phone)
            pwd_item = QTableWidgetItem(pwd_display)
            active_item = QTableWidgetItem(active_text)
            created_item = QTableWidgetItem(created)

            for item in (id_item, name_item, phone_item, pwd_item, created_item):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )

            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if active_text == "Yes":
                active_item.setBackground(QColor("#bbf7d0"))
                active_item.setForeground(QColor("#166534"))
            else:
                active_item.setBackground(QColor("#fecaca"))
                active_item.setForeground(QColor("#991b1b"))

            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, name_item)
            self.table.setItem(r, 2, phone_item)
            self.table.setItem(r, 3, pwd_item)
            self.table.setItem(r, 4, active_item)
            self.table.setItem(r, 5, created_item)

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def apply_search_filter(self, text: str):
        text = (text or "").strip().lower()
        if not text:
            self._populate_table(self._rows_cache)
            return

        filtered = []
        for row in self._rows_cache:
            id_ = str(row.get("id") or "").lower()
            name = str(row.get("name") or "").lower()
            phone = str(row.get("phone") or "").lower()
            if text in id_ or text in name or text in phone:
                filtered.append(row)

        self._populate_table(filtered)

    # ------------------------------------------------------------------ #
    # Helpers & actions
    # ------------------------------------------------------------------ #
    def _get_selected_admin_id(self) -> str | None:
        if not self.table:
            return None
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.text().strip()

    def add_admin(self):
        dlg = AdminEditDialog(self, existing=None)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data:
            return

        print(">>> [ManageAdmins] Adding admin:", data)
        try:
            resp = supabase_post("admins", data)
        except Exception as e:
            print(">>> [ManageAdmins] POST error:", e)
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to add admin (HTTP error).",
            )
            return

        if getattr(resp, "status_code", None) not in (200, 201):
            print(">>> [ManageAdmins] POST failed:", resp.status_code, getattr(resp, "text", ""))
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while adding admin. (status {resp.status_code})",
            )
            return

        _show_message(
            self,
            QMessageBox.Icon.Information,
            "Success",
            "Admin added successfully.",
        )
        self.refresh_data()

    def edit_selected_admin(self):
        admin_id = self._get_selected_admin_id()
        if not admin_id:
            _show_message(
                self,
                QMessageBox.Icon.Warning,
                "No selection",
                "Please select an admin row to edit.",
            )
            return

        try:
            resp = supabase_get(
                "admins",
                filter_query=f"id=eq.{admin_id}",
                select="id,name,phone,is_active,password",
            )
        except Exception as e:
            print(">>> [ManageAdmins] GET for edit error:", e)
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to load admin details.",
            )
            return

        if getattr(resp, "status_code", None) != 200:
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while fetching admin. (status {resp.status_code})",
            )
            return

        try:
            rows = resp.json() or []
        except Exception as e:
            print(">>> [ManageAdmins] JSON parse error on edit:", e)
            rows = []

        if not rows:
            _show_message(
                self,
                QMessageBox.Icon.Warning,
                "Not found",
                "Could not find this admin record.",
            )
            return

        existing = rows[0]
        dlg = AdminEditDialog(self, existing=existing)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data:
            return

        payload = {
            "name": data.get("name"),
            "phone": data.get("phone"),
            "is_active": data.get("is_active"),
        }
        if "password" in data:
            payload["password"] = data["password"]

        print(">>> [ManageAdmins] Updating admin:", admin_id, payload)
        try:
            resp = supabase_patch("admins", filter_query=f"id=eq.{admin_id}", data=payload)
        except Exception as e:
            print(">>> [ManageAdmins] PATCH error:", e)
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to update admin (HTTP error).",
            )
            return

        if getattr(resp, "status_code", None) not in (200, 204):
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while updating admin. (status {resp.status_code})",
            )
            return

        _show_message(
            self,
            QMessageBox.Icon.Information,
            "Success",
            "Admin updated successfully.",
        )
        self.refresh_data()

    def toggle_active_selected(self):
        admin_id = self._get_selected_admin_id()
        if not admin_id:
            _show_message(
                self,
                QMessageBox.Icon.Warning,
                "No selection",
                "Please select an admin row to toggle.",
            )
            return

        row = self.table.currentRow()
        active_item = self.table.item(row, 4)  # Active column index
        current_text = active_item.text().strip() if active_item else "Yes"
        new_active = not (current_text == "Yes")

        print(f">>> [ManageAdmins] Toggle active for {admin_id} -> {new_active}")

        try:
            resp = supabase_patch(
                "admins",
                filter_query=f"id=eq.{admin_id}",
                data={"is_active": new_active},
            )
        except Exception as e:
            print(">>> [ManageAdmins] PATCH toggle error:", e)
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to update active status.",
            )
            return

        if getattr(resp, "status_code", None) not in (200, 204):
            _show_message(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while toggling active. (status {resp.status_code})",
            )
            return

        self.refresh_data()
