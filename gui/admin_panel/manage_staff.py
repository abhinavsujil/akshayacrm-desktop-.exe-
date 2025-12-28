# gui/admin_panel/manage_staff.py

from __future__ import annotations

from typing import Any

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
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from supabase_utils import supabase_get, supabase_post, supabase_patch


PRIMARY_PURPLE = "#2E1A6B"
SECONDARY_CYAN = "#00B8D4"
BG_LIGHT = "#edf1f7"


# ------------------------------------------------------------------ #
# Staff add / edit dialog
# ------------------------------------------------------------------ #
class StaffEditDialog(QDialog):
    """
    Simple dialog to add / edit a staff member.
    Fields:
      - Staff ID (string, required)
      - Name
      - Phone
      - Password
      - Active (Yes/No)
    """

    def __init__(self, parent=None, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Staff" if existing else "Add Staff")
        self.setMinimumWidth(380)

        self._existing = existing or {}

        self._build_styles()
        self._init_ui()

    def _build_styles(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {BG_LIGHT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QLabel {{
                color: #0f172a;
            }}
            QLineEdit, QComboBox {{
                border-radius: 10px;
                border: 1px solid #cbd5e1;
                padding: 6px 10px;
                background: #ffffff;
                font-size: 13px;
            }}
            QPushButton#primaryBtn {{
                background-color: {PRIMARY_PURPLE};
                color: #ffffff;
                border-radius: 999px;
                padding: 6px 18px;
                font-weight: 600;
                border: none;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: #412395;
            }}
            QPushButton#ghostBtn {{
                background: transparent;
                border-radius: 999px;
                padding: 6px 18px;
                color: #6b7280;
                border: 1px solid #e5e7eb;
                font-weight: 500;
            }}
            QPushButton#ghostBtn:hover {{
                background-color: #f3f4f6;
            }}
            """
        )

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel(self.windowTitle())
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        # Staff ID
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Staff ID (unique)")
        self.id_input.setText(str(self._existing.get("id") or ""))
        if self._existing:
            # Don't allow changing ID when editing.
            self.id_input.setReadOnly(True)

        # Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full Name")
        self.name_input.setText(str(self._existing.get("name") or ""))

        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone number")
        self.phone_input.setText(str(self._existing.get("phone") or ""))

        # Password (plain text, as requested)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(
            "Password (leave blank to keep existing)"
            if self._existing
            else "Password"
        )
        # Pre-fill existing password in plain text if editing
        if self._existing:
            existing_pwd = str(self._existing.get("password") or "")
            self.password_input.setText(existing_pwd)

        # Active?
        self.active_combo = QComboBox()
        self.active_combo.addItems(["Yes", "No"])
        is_active = self._existing.get("is_active")
        if is_active is False:
            self.active_combo.setCurrentText("No")
        else:
            self.active_combo.setCurrentText("Yes")

        def field(label_text: str, widget):
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Inter", 11))
            layout.addWidget(lbl)
            layout.addWidget(widget)

        field("Staff ID", self.id_input)
        field("Name", self.name_input)
        field("Phone", self.phone_input)
        field("Password", self.password_input)
        field("Active", self.active_combo)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryBtn")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ghostBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def get_data(self) -> dict[str, Any] | None:
        """Return dict to send to Supabase (or None if invalid)."""
        staff_id = (self.id_input.text() or "").strip()
        name = (self.name_input.text() or "").strip()
        phone = (self.phone_input.text() or "").strip()
        pwd = (self.password_input.text() or "").strip()
        is_active = self.active_combo.currentText() == "Yes"

        if not staff_id:
            QMessageBox.warning(self, "Validation error", "Staff ID is required.")
            return None

        data: dict[str, Any] = {
            "id": staff_id,
            "name": name or None,
            "phone": phone or None,
            "password": pwd or None,
            "is_active": is_active,
        }
        return data


# ------------------------------------------------------------------ #
# Manage Staff main dialog
# ------------------------------------------------------------------ #
class ManageStaffDialog(QDialog):
    """
    Admin screen to manage staff records.

    Uses Supabase table: `staff`
    Expected columns (minimum):
        id (text, primary key)
        name (text)
        phone (text)
        password (text)
        is_active (bool)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Staff")
        self.setMinimumSize(780, 520)

        self.table: QTableWidget | None = None

        self._build_styles()
        self.init_ui()
        self.refresh_data()

    # ------------------------------------------------------------------ #
    # Global Style
    # ------------------------------------------------------------------ #
    def _build_styles(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {BG_LIGHT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}

            QFrame#cardFrame {{
                background: rgba(255, 255, 255, 0.96);
                border-radius: 24px;
            }}

            QFrame#headerFrame {{
                border-top-left-radius: 24px;
                border-top-right-radius: 24px;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {PRIMARY_PURPLE},
                    stop:1 {SECONDARY_CYAN}
                );
            }}

            QLabel#headerTitle {{
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
                background: transparent;
            }}

            QLabel#headerIcon {{
                color: #a5f3fc;
                font-size: 26px;
                background: transparent;
            }}

            QPushButton#refreshBtn {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {SECONDARY_CYAN},
                    stop:1 #4adeff
                );
                color: #ffffff;
                border-radius: 18px;
                padding: 6px 22px;
                font-size: 13px;
                font-weight: 600;
                border: none;
            }}
            QPushButton#refreshBtn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #04a8c7,
                    stop:1 #22d3ee
                );
            }}

            QLineEdit#searchInput {{
                background: #ffffff;
                border-radius: 999px;
                border: 1px solid #d1d5db;
                padding: 6px 14px;
                font-size: 13px;
            }}
            QLineEdit#searchInput:focus {{
                border: 1px solid {SECONDARY_CYAN};
            }}

            QTableWidget#staffTable {{
                background: transparent;
                border: none;
                gridline-color: #e5e7eb;
                selection-background-color: rgba(46, 26, 107, 0.08);
                selection-color: #111827;
                alternate-background-color: #f5f7fb;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_PURPLE};
                color: white;
                border: none;
                padding: 10px 8px;
                font-size: 13px;
                font-weight: 600;
            }}

            QPushButton#btnPrimaryCyan {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {SECONDARY_CYAN},
                    stop:1 #4adeff
                );
                color: #ffffff;
                border-radius: 999px;
                padding: 8px 28px;
                font-weight: 600;
                font-size: 14px;
                border: none;
                min-width: 130px;
            }}
            QPushButton#btnPrimaryCyan:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #04a8c7,
                    stop:1 #22d3ee
                );
            }}

            QPushButton#btnPurple {{
                background-color: {PRIMARY_PURPLE};
                color: #ffffff;
                border-radius: 999px;
                padding: 8px 28px;
                font-weight: 600;
                font-size: 14px;
                border: none;
                min-width: 130px;
            }}
            QPushButton#btnPurple:hover {{
                background-color: #412395;
            }}

            QPushButton#btnGhost {{
                background-color: #ffffff;
                color: #111827;
                border-radius: 999px;
                padding: 8px 28px;
                font-weight: 500;
                font-size: 14px;
                border: 1px solid #e5e7eb;
                min-width: 130px;
            }}
            QPushButton#btnGhost:hover {{
                background-color: #f3f4f6;
            }}
            """
        )

    # ------------------------------------------------------------------ #
    # UI helpers
    # ------------------------------------------------------------------ #
    def _show_message(self, icon: QMessageBox.Icon, title: str, text: str):
        box = QMessageBox(self)
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
                padding: 4px 10px;
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            """
        )
        box.exec()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 16, 16)
        card_layout.setSpacing(0)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(15, 23, 42, 90))
        card.setGraphicsEffect(shadow)

        # Header
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(12)

        icon_label = QLabel("👥")
        icon_label.setObjectName("headerIcon")

        title = QLabel("Manage Staff")
        title.setObjectName("headerTitle")

        header_layout.addWidget(icon_label)
        header_layout.addSpacing(4)
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.refresh_btn)

        card_layout.addWidget(header_frame)

        # Content
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(16)

        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Search:")
        search_label.setFont(QFont("Inter", 11))

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search by staff name or ID...")
        self.search_input.textChanged.connect(self._apply_search_filter)

        search_row.addWidget(search_label)
        search_row.addWidget(self.search_input)
        search_row.addStretch()
        content_layout.addLayout(search_row)

        # Table - includes plain text password column
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("staffTable")
        self.table.setHorizontalHeaderLabels(
            ["Staff ID", "Name", "Phone", "Password", "Active"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setStretchLastSection(True)
        content_layout.addWidget(self.table)

        # Buttons row
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.addStretch()

        add_btn = QPushButton("Add Staff")
        add_btn.setObjectName("btnPrimaryCyan")

        edit_btn = QPushButton("Edit Selected")
        edit_btn.setObjectName("btnPurple")

        toggle_btn = QPushButton("Toggle Active")
        toggle_btn.setObjectName("btnPurple")

        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnPrimaryCyan")

        add_btn.clicked.connect(self.add_staff)
        edit_btn.clicked.connect(self.edit_selected_staff)
        toggle_btn.clicked.connect(self.toggle_active_selected)
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(add_btn)
        btn_layout.addSpacing(12)
        btn_layout.addWidget(edit_btn)
        btn_layout.addSpacing(12)
        btn_layout.addWidget(toggle_btn)
        btn_layout.addSpacing(12)
        btn_layout.addWidget(close_btn)

        content_layout.addWidget(btn_frame)

        card_layout.addWidget(content_frame)
        outer.addWidget(card)

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def refresh_data(self):
        if not self.table:
            return

        print(">>> [ManageStaff] refresh_data()")
        self.table.setRowCount(0)

        try:
            # include password here so we can show plain text
            resp = supabase_get("staff", select="id,name,phone,password,is_active")
        except Exception as e:
            print(">>> [ManageStaff] HTTP error:", e)
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to load staff data from Supabase.",
            )
            return

        status = getattr(resp, "status_code", None)
        print(">>> [ManageStaff] status =", status)

        if status != 200:
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while fetching staff. (status {status})",
            )
            return

        try:
            rows = resp.json() or []
        except Exception as e:
            print(">>> [ManageStaff] JSON parse error:", e)
            rows = []

        for row in rows:
            staff_id = str(row.get("id") or "")
            name = str(row.get("name") or "")
            phone = str(row.get("phone") or "")
            pwd_display = str(row.get("password") or "")  # PLAIN TEXT PASSWORD
            active = row.get("is_active")
            active_text = "Yes" if active or active is None else "No"

            r = self.table.rowCount()
            self.table.insertRow(r)

            id_item = QTableWidgetItem(staff_id)
            name_item = QTableWidgetItem(name)
            phone_item = QTableWidgetItem(phone)
            pwd_item = QTableWidgetItem(pwd_display)
            active_item = QTableWidgetItem(active_text)

            id_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            phone_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            pwd_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, name_item)
            self.table.setItem(r, 2, phone_item)
            self.table.setItem(r, 3, pwd_item)
            self.table.setItem(r, 4, active_item)

            # Gradient pill badge for Active column
            badge = QLabel(active_text)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if active_text == "Yes":
                badge.setStyleSheet(
                    f"""
                    QLabel {{
                        background: qlineargradient(
                            x1:0, y1:0, x2:1, y2:1,
                            stop:0 {SECONDARY_CYAN},
                            stop:1 #4ade80
                        );
                        color: #ffffff;
                        padding: 4px 16px;
                        border-radius: 999px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    """
                )
            else:
                badge.setStyleSheet(
                    """
                    QLabel {
                        background-color: #fee2e2;
                        color: #b91c1c;
                        padding: 4px 16px;
                        border-radius: 999px;
                        font-weight: 600;
                        font-size: 12px;
                    }
                    """
                )

            self.table.setCellWidget(r, 4, badge)

        self.table.resizeColumnsToContents()
        self._apply_search_filter(self.search_input.text())

    # ------------------------------------------------------------------ #
    # Simple search filter (client-side)
    # ------------------------------------------------------------------ #
    def _apply_search_filter(self, text: str):
        if not self.table:
            return
        query = (text or "").strip().lower()
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if not id_item or not name_item:
                continue
            id_val = id_item.text().lower()
            name_val = name_item.text().lower()
            match = (query in id_val) or (query in name_val) or not query
            self.table.setRowHidden(row, not match)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _get_selected_staff_id(self) -> str | None:
        if not self.table:
            return None
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.text().strip()

    def add_staff(self):
        dlg = StaffEditDialog(self, existing=None)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data:
            return

        print(">>> [ManageStaff] Adding staff:", data)
        try:
            resp = supabase_post("staff", data)
        except Exception as e:
            # supabase_post raised an Exception (e.g. network error)
            print(">>> [ManageStaff] POST error:", e)
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                str(e),
            )
            return

        # Handle both Response object and dict (e.g. {"error": "..."}).
        if isinstance(resp, dict):
            err = resp.get("error")
            if err:
                print(">>> [ManageStaff] POST dict error:", err)
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Supabase error",
                    f"Failed to add staff: {err}",
                )
                return
        else:
            status = getattr(resp, "status_code", None)
            if status not in (200, 201):
                print(">>> [ManageStaff] POST failed:", status, getattr(resp, "text", ""))
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Error",
                    f"Supabase error while adding staff. (status {status})",
                )
                return

        self._show_message(
            QMessageBox.Icon.Information,
            "Success",
            "Staff added successfully.",
        )
        self.refresh_data()

    def edit_selected_staff(self):
        staff_id = self._get_selected_staff_id()
        if not staff_id:
            self._show_message(
                QMessageBox.Icon.Warning,
                "No selection",
                "Please select a staff row to edit.",
            )
            return

        # fetch one staff row, including password
        try:
            resp = supabase_get(
                "staff",
                filter_query=f"id=eq.{staff_id}",
                select="id,name,phone,is_active,password",
            )
        except Exception as e:
            print(">>> [ManageStaff] GET for edit error:", e)
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                "Failed to load staff details.",
            )
            return

        if getattr(resp, "status_code", None) != 200:
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                f"Supabase error while fetching staff. (status {resp.status_code})",
            )
            return

        try:
            rows = resp.json() or []
        except Exception as e:
            print(">>> [ManageStaff] JSON parse error on edit:", e)
            rows = []

        if not rows:
            self._show_message(
                QMessageBox.Icon.Warning,
                "Not found",
                "Could not find this staff record.",
            )
            return

        existing = rows[0]
        dlg = StaffEditDialog(self, existing=existing)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data:
            return

        # For patch, don't send id key – we filter on it.
        payload: dict[str, Any] = {
            "name": data.get("name"),
            "phone": data.get("phone"),
            "is_active": data.get("is_active"),
        }
        # Always update password to whatever is in the field
        if data.get("password") is not None:
            payload["password"] = data["password"]

        print(">>> [ManageStaff] Updating staff:", staff_id, payload)
        try:
            resp = supabase_patch("staff", filter_query=f"id=eq.{staff_id}", data=payload)
        except Exception as e:
            print(">>> [ManageStaff] PATCH error:", e)
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                str(e),
            )
            return

        if isinstance(resp, dict):
            err = resp.get("error")
            if err:
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Supabase error",
                    f"Failed to update staff: {err}",
                )
                return
        else:
            if getattr(resp, "status_code", None) not in (200, 204):
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Error",
                    f"Supabase error while updating staff. (status {resp.status_code})",
                )
                return

        self._show_message(
            QMessageBox.Icon.Information,
            "Success",
            "Staff updated successfully.",
        )
        self.refresh_data()

    def toggle_active_selected(self):
        staff_id = self._get_selected_staff_id()
        if not staff_id:
            self._show_message(
                QMessageBox.Icon.Warning,
                "No selection",
                "Please select a staff row to toggle.",
            )
            return

        # Find current active value from table (Active is column 4)
        row = self.table.currentRow()
        active_item = self.table.item(row, 4)
        current_text = active_item.text().strip() if active_item else "Yes"
        new_active = not (current_text == "Yes")

        print(f">>> [ManageStaff] Toggle active for {staff_id} -> {new_active}")

        try:
            resp = supabase_patch(
                "staff",
                filter_query=f"id=eq.{staff_id}",
                data={"is_active": new_active},
            )
        except Exception as e:
            print(">>> [ManageStaff] PATCH toggle error:", e)
            self._show_message(
                QMessageBox.Icon.Critical,
                "Error",
                str(e),
            )
            return

        if isinstance(resp, dict):
            err = resp.get("error")
            if err:
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Supabase error",
                    f"Failed to update active status: {err}",
                )
                return
        else:
            if getattr(resp, "status_code", None) not in (200, 204):
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "Error",
                    f"Supabase error while toggling active. (status {resp.status_code})",
                )
                return

        self.refresh_data()
