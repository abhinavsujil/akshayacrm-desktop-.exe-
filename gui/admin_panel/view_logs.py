# view_logs.py  (UPDATED)
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import csv
import os

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QHeaderView,
    QFrame,
    QTextEdit,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QWidget,
)
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal

# safe import for QShortcut (some PyQt6 builds expose it in QtGui)
try:
    from PyQt6.QtWidgets import QShortcut  # preferred
except Exception:
    from PyQt6.QtGui import QShortcut  # fallback

from supabase_utils import get_all_logs_with_services, update_log, delete_log

# ------------------------------------------------------------------ #
# Utility: format timestamp coming from Supabase
# ------------------------------------------------------------------ #
def format_timestamp(raw_ts) -> str:
    """Convert DB timestamp to 'DD Mon, HH:MM AM/PM'."""
    if not raw_ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(raw_ts))
        return dt.strftime("%d %b, %I:%M %p")
    except Exception:
        return str(raw_ts)


def parse_timestamp(raw_ts) -> datetime | None:
    """Parse ISO timestamp to datetime, or None."""
    if not raw_ts:
        return None
    try:
        return datetime.fromisoformat(str(raw_ts))
    except Exception:
        return None


def extract_service_components(service: Dict[str, Any]) -> tuple[float, float, float]:
    """
    Return (base_amount, service_charge, total) for a service row.

    Reads from:
      - service['base_amount'], service['service_charge'], service['amount']
      - and, if present, joined payments rows:
            service['payments'] or service['payment'] (list of dicts)
        using fields: amount, base_amount, service_charge.
    """
    if not isinstance(service, dict):
        return 0.0, 0.0, 0.0

    base = 0.0
    charge = 0.0
    total = 0.0

    # direct fields on service row
    if service.get("base_amount") not in (None, ""):
        try:
            base = float(service["base_amount"])
        except Exception:
            base = 0.0

    if service.get("service_charge") not in (None, ""):
        try:
            charge = float(service["service_charge"])
        except Exception:
            charge = 0.0

    if service.get("amount") not in (None, ""):
        try:
            total = float(service["amount"])
        except Exception:
            total = 0.0

    # payments join (services(*,payments(*)))
    payments = service.get("payments") or service.get("payment") or []
    if isinstance(payments, list):
        for p in payments:
            if not isinstance(p, dict):
                continue

            v_amt = p.get("amount")
            if v_amt not in (None, ""):
                try:
                    total += float(v_amt)
                except Exception:
                    pass

            v_base = p.get("base_amount")
            if v_base not in (None, ""):
                try:
                    base += float(v_base)
                except Exception:
                    pass

            v_charge = p.get("service_charge")
            if v_charge not in (None, ""):
                try:
                    charge += float(v_charge)
                except Exception:
                    pass

    # if total is still 0, derive from base + charge
    if total == 0.0:
        total = base + charge

    return base, charge, total


def extract_service_amount(service: Dict[str, Any]) -> float:
    """Backwards-compat helper: just return the total amount."""
    _, _, total = extract_service_components(service)
    return total



# ------------------------------------------------------------------ #
# Detail dialog for a single log row
# (kept mostly intact; used by double-click)
# ------------------------------------------------------------------ #
class LogDetailsDialog(QDialog):
    """
    Premium-looking detail dialog for a single log.

    Expected keys in `record`:
        - timestamp      (ISO str or datetime)
        - staff_id       (str)
        - name           (customer name)
        - phone          (str)
        - services_str   (e.g. 'Aadhaar (₹50, approved); Pan (₹100, pending)')
        - total_amount   (number or str)
        - remarks        (str)
    """

    def __init__(self, record: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.record = record

        self.setWindowTitle("Log Details")
        self.setMinimumSize(650, 480)
        self.setModal(True)

        # ---------- Global style ----------
        self.setStyleSheet("""
        QWidget {
            background: #ffffff;
            font-family: 'Segoe UI', sans-serif;
            color: #0f172a;
        }
        QLabel#TitleLabel {
            font-size: 18px;
            font-weight: 600;
        }
        QLabel.fieldLabel {
            font-size: 13px;
            font-weight: 600;
            color: #64748b;
        }
        QLabel.valueLabel {
            font-size: 14px;
            color: #0f172a;
        }
        QFrame.Divider {
            background: #e2e8f0;
        }
        QPushButton#CloseButton {
            background: #eff6ff;
            border-radius: 6px;
            border: 1px solid #bfdbfe;
            padding: 6px 18px;
            color: #1d4ed8;
            font-weight: 600;
        }
        QPushButton#CloseButton:hover {
            background: #dbeafe;
        }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 16, 20, 16)

        # ---------- Header row: title + status badge ----------
        header_row = QHBoxLayout()
        title_label = QLabel("Log Details")
        title_label.setObjectName("TitleLabel")
        title_label.setFont(QFont("Inter", 18, QFont.Weight.Bold))

        header_row.addWidget(title_label)
        header_row.addStretch()

        status_badge = self._create_status_badge()
        if status_badge:
            header_row.addWidget(status_badge)

        main_layout.addLayout(header_row)
        main_layout.addWidget(self._divider())

        # ---------- Top info grid ----------
        info_form = QFormLayout()
        info_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        info_form.setHorizontalSpacing(30)
        info_form.setVerticalSpacing(10)

        def add_row(label: str, value: str):
            lbl = QLabel(label)
            lbl.setProperty("class", "fieldLabel")
            lbl.setObjectName("FieldLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet("QLabel { font-size: 13px; font-weight: 600; color: #64748b; }")

            val = QLabel(value or "—")
            val.setWordWrap(True)
            val.setObjectName("ValueLabel")
            val.setStyleSheet("QLabel { font-size: 14px; color: #0f172a; }")

            info_form.addRow(lbl, val)

        add_row("Timestamp:", self._format_timestamp(record.get("timestamp")))
        add_row("Staff ID:", str(record.get("staff_id") or ""))
        add_row("Customer Name:", str(record.get("name") or ""))
        add_row("Phone:", str(record.get("phone") or ""))
        add_row("Total Amount (₹):", str(record.get("total_amount") or "0"))

        main_layout.addLayout(info_form)
        main_layout.addWidget(self._divider())

        # ---------- Services section ----------
        services_title = QLabel("Services")
        services_title.setStyleSheet(
            "QLabel { font-size: 13px; font-weight: 600; color: #64748b; }"
        )
        main_layout.addWidget(services_title)

        services_container = QFrame()
        services_layout = QVBoxLayout(services_container)
        services_layout.setSpacing(6)
        services_layout.setContentsMargins(0, 0, 0, 0)

        services_str = str(record.get("services_str") or "")
        services = [s.strip() for s in services_str.split(";") if s.strip()]

        if not services:
            empty_lbl = QLabel("No services recorded.")
            empty_lbl.setStyleSheet("QLabel { color: #94a3b8; font-size: 13px; }")
            services_layout.addWidget(empty_lbl)
        else:
            for s in services:
                services_layout.addWidget(self._create_service_chip(s))

        main_layout.addWidget(services_container)
        main_layout.addWidget(self._divider())

        # ---------- Remarks ----------
        remarks_title = QLabel("Remarks")
        remarks_title.setStyleSheet(
            "QLabel { font-size: 13px; font-weight: 600; color: #64748b; }"
        )
        main_layout.addWidget(remarks_title)

        remarks_val = QLabel(str(record.get("remarks") or "—"))
        remarks_val.setObjectName("ValueLabel")
        remarks_val.setWordWrap(True)
        remarks_val.setStyleSheet(
            "QLabel { font-size: 14px; color: #0f172a; padding-right: 4px; }"
        )
        main_layout.addWidget(remarks_val)

        main_layout.addStretch()

        # ---------- Footer with Close button ----------
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("CloseButton")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)

        main_layout.addLayout(footer)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedHeight(1)
        line.setStyleSheet("QFrame#Divider { background: #e2e8f0; }")
        return line

    def _format_timestamp(self, raw) -> str:
        if not raw:
            return "—"
        try:
            if isinstance(raw, datetime):
                dt = raw
            else:
                dt = datetime.fromisoformat(str(raw))
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(raw)

    def _compute_overall_status(self) -> str:
        """
        If any service string contains 'pending' -> Pending, else Completed.
        """
        services_str = str(self.record.get("services_str") or "").lower()
        if "pending" in services_str:
            return "Pending"
        return "Completed"

    def _create_status_badge(self) -> QLabel:
        status = self._compute_overall_status()
        badge = QLabel(status)

        # pill style
        if status.lower() == "completed":
            badge.setStyleSheet("""
                QLabel {
                    background: #dcfce7;
                    color: #166534;
                    border-radius: 999px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    border: 1px solid #86efac;
                }
            """)
        else:
            badge.setStyleSheet("""
                QLabel {
                    background: #fef9c3;
                    color: #92400e;
                    border-radius: 999px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    border: 1px solid #facc15;
                }
            """)
        return badge

    def _create_service_chip(self, text: str) -> QLabel:
        lower = text.lower()
        if "pending" in lower:
            bg = "#fef2f2"
            border = "#fecaca"
            fg = "#b91c1c"
        elif "approved" in lower:
            bg = "#ecfdf5"
            border = "#bbf7d0"
            fg = "#15803d"
        else:
            bg = "#e5f0ff"
            border = "#bfdbfe"
            fg = "#1d4ed8"

        chip = QLabel(text)
        chip.setWordWrap(True)
        chip.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                border-radius: 8px;
                border: 1px solid {border};
                padding: 6px 10px;
                font-size: 13px;
                color: {fg};
            }}
        """)
        return chip


# ------------------------------------------------------------------ #
# Background fetch thread for logs
# ------------------------------------------------------------------ #
class FetchLogsThread(QThread):
    fetched = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            rows = get_all_logs_with_services() or []
            self.fetched.emit(rows)
        except Exception as e:
            self.failed.emit(str(e))


# ------------------------------------------------------------------ #
# EditLogDialog - NEW
# ------------------------------------------------------------------ #
class EditLogDialog(QDialog):
    """
    Simple edit dialog for a log row. Edits only the top-level log fields:
    - name
    - phone
    - remarks

    On Save, calls supabase_utils.update_log(log_id, payload) and shows feedback.
    """
    def __init__(self, log_record: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.log_record = log_record
        self.log_id = str(log_record.get("id") or log_record.get("log_id") or "")
        self.setWindowTitle("Edit Log")
        self.setMinimumSize(520, 260)
        self.setModal(True)

        self.setStyleSheet("""
            QWidget { background: #ffffff; font-family: 'Segoe UI', sans-serif; color: #0f172a; }
            QLabel.title { font-size: 15px; font-weight: 700; }
            QPushButton.save { background: #06b6d4; color: white; padding: 6px 12px; border-radius: 6px; }
            QPushButton.cancel { background: #f1f5f9; padding: 6px 12px; border-radius: 6px; }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(16, 12, 16, 12)
        main.setSpacing(10)

        title = QLabel("Edit Log")
        title.setProperty("class", "title")
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        main.addWidget(title)

        form = QFormLayout()
        self.name_input = QLineEdit(str(log_record.get("name") or ""))
        self.phone_input = QLineEdit(str(log_record.get("phone") or ""))
        self.remarks_input = QTextEdit(str(log_record.get("remarks") or ""))
        self.remarks_input.setFixedHeight(100)

        form.addRow("Customer Name:", self.name_input)
        form.addRow("Phone:", self.phone_input)
        form.addRow("Remarks:", self.remarks_input)
        main.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("save")
        self.save_btn.clicked.connect(self._on_save_clicked)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        main.addLayout(btn_row)

    def _on_save_clicked(self):
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        remarks = self.remarks_input.toPlainText().strip()

        payload = {}
        if name != (self.log_record.get("name") or ""):
            payload["name"] = name
        if phone != (self.log_record.get("phone") or ""):
            payload["phone"] = phone
        if remarks != (self.log_record.get("remarks") or ""):
            payload["remarks"] = remarks

        if not payload:
            QMessageBox.information(self, "Nothing changed", "No changes to save.")
            self.accept()
            return

        # call backend update
        try:
            ok = update_log(self.log_id, payload)
        except Exception as e:
            ok = False
            print("EditLogDialog update_log exception:", e)

        if ok:
            QMessageBox.information(self, "Saved", "Log updated successfully.")
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Update failed",
                "Remote update failed or did not persist.\n"
                "Check application console for HTTP response details."
            )
            # keep open so user can retry


# ------------------------------------------------------------------ #
# Main View Logs dialog
# ------------------------------------------------------------------ #
class ViewLogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("All Logs")
        self.setMinimumSize(950, 500)

        # Local cache
        self.all_logs: List[Dict[str, Any]] = []      # raw from Supabase
        self.filtered_logs: List[Dict[str, Any]] = []  # after filters

        # UI elements
        self.date_filter: QComboBox | None = None
        self.staff_filter: QComboBox | None = None
        self.table: QTableWidget | None = None

        # background fetch helpers
        self._fetch_thread: FetchLogsThread | None = None
        self._refresh_timer: QTimer | None = None
        self._refresh_dot_index = 0

        self.init_ui()
        self.load_logs()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Title row
        title_row = QHBoxLayout()
        title_label = QLabel("All customer logs with services")
        title_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        title_row.addWidget(title_label)
        title_row.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(26)
        self.refresh_btn.clicked.connect(self.load_logs)
        title_row.addWidget(self.refresh_btn)

        export_btn = QPushButton("⬇ Export CSV")
        export_btn.setFixedHeight(26)
        export_btn.clicked.connect(self.export_filtered_to_csv)
        title_row.addWidget(export_btn)

        main_layout.addLayout(title_row)

        # keyboard shortcuts
        try:
            QShortcut(QKeySequence("R"), self, activated=self.load_logs)
            QShortcut(QKeySequence("E"), self, activated=self.export_filtered_to_csv)
        except Exception:
            # If QShortcut import failed earlier, fallback to no shortcuts
            pass

        # Filter row
        filter_row = QHBoxLayout()

        date_label = QLabel("Date:")
        self.date_filter = QComboBox()
        self.date_filter.addItems(["All Time", "Today", "This Week", "This Month"])
        self.date_filter.currentIndexChanged.connect(self.apply_filters)

        staff_label = QLabel("Staff:")
        self.staff_filter = QComboBox()
        self.staff_filter.addItem("All Staff")
        self.staff_filter.currentIndexChanged.connect(self.apply_filters)

        filter_row.addWidget(date_label)
        filter_row.addWidget(self.date_filter)
        filter_row.addSpacing(20)
        filter_row.addWidget(staff_label)
        filter_row.addWidget(self.staff_filter)
        filter_row.addStretch()

        main_layout.addLayout(filter_row)

        # Table
        # Add Actions column at the end
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Timestamp",
                "Staff ID",
                "Customer Name",
                "Phone",
                "Services",
                "Total Amount (₹)",
                "Remarks",
                "Actions",
            ]
        )

        # Table behaviour
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Style for better readability & show gridlines
        self.table.setShowGrid(True)
        self.table.setStyleSheet("""
        QTableView {
            background: #ffffff;
            alternate-background-color: #f9fafb;
            gridline-color: #cbd5e1;
            selection-background-color: #dbeafe;
            selection-color: #111827;
            border: 1px solid #cbd5e1;
        }
        QTableView::item {
            padding: 4px 6px;
            border-bottom: 1.5px solid #e5e7eb;
        }
        QHeaderView::section {
            background: #f1f5f9;
            padding: 6px 4px;
            border: 0.5px solid #e5e7eb;
            font-weight: 600;
        }
        QPushButton.action {
            background: #eef2ff;
            border: 1px solid #c7d2fe;
            padding: 4px 8px;
            border-radius: 6px;
            min-width: 40px;
        }
        """)
        # Double-click row → details dialog
        self.table.cellDoubleClicked.connect(self.open_row_details)

        # Enter key opens selected row details
        try:
            QShortcut(QKeySequence("Return"), self, activated=self._open_selected_details)
        except Exception:
            pass

        main_layout.addWidget(self.table)

        # Bottom close button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        close_btn = QPushButton("✖ Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        main_layout.addLayout(bottom_row)

    # ------------------------------------------------------------------ #
    # Data loading & filtering
    # ------------------------------------------------------------------ #
    def load_logs(self):
        """Fetch all logs + services from Supabase and populate filters + table."""
        # Use background thread + small animation so UI appears responsive
        if self._fetch_thread and self._fetch_thread.isRunning():
            return

        # start animation
        self._start_refresh_animation()

        self._fetch_thread = FetchLogsThread()
        def on_fetched(rows):
            self._stop_refresh_animation()
            self.all_logs = rows or []

            # Build staff filter options
            staff_ids = sorted(
                {item["log"].get("staff_id") for item in self.all_logs if item["log"].get("staff_id")}
            )
            current_staff = self.staff_filter.currentText() if self.staff_filter else "All Staff"

            self.staff_filter.blockSignals(True)
            self.staff_filter.clear()
            self.staff_filter.addItem("All Staff")
            for sid in staff_ids:
                self.staff_filter.addItem(str(sid))
            # restore selection if possible
            index = self.staff_filter.findText(current_staff)
            if index >= 0:
                self.staff_filter.setCurrentIndex(index)
            self.staff_filter.blockSignals(False)

            self.apply_filters()
            self._fetch_thread = None

        def on_failed(msg):
            self._stop_refresh_animation()
            QMessageBox.critical(self, "Error", f"Failed to fetch logs:\n{msg}")
            self._fetch_thread = None

        self._fetch_thread.fetched.connect(on_fetched)
        self._fetch_thread.failed.connect(on_failed)
        self._fetch_thread.start()

    def _start_refresh_animation(self):
        self.refresh_btn.setEnabled(False)
        self._refresh_dot_index = 0
        if not self._refresh_timer:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setInterval(300)
            def tick():
                self._refresh_dot_index = (self._refresh_dot_index + 1) % 4
                self.refresh_btn.setText("🔄 Refreshing" + "." * self._refresh_dot_index)
            self._refresh_timer.timeout.connect(tick)
        self._refresh_timer.start()
        self.refresh_btn.setText("🔄 Refreshing")

    def _stop_refresh_animation(self):
        if self._refresh_timer:
            self._refresh_timer.stop()
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh")

    def apply_filters(self):
        """Apply date + staff filters, then fill the table."""
        if not self.table:
            return

        date_mode = self.date_filter.currentText() if self.date_filter else "All Time"
        staff_mode = self.staff_filter.currentText() if self.staff_filter else "All Staff"

        self.filtered_logs = []

        today = date.today()
        now = datetime.now()
        current_iso = now.isocalendar()
        current_year = current_iso[0]
        current_week = current_iso[1]
        current_month = now.month

        for item in self.all_logs:
            log = item["log"]
            services = item["services"]

            dt = parse_timestamp(log.get("timestamp"))
            if not dt:
                continue

            d = dt.date()

            # Date filter
            include_date = True
            if date_mode == "Today":
                include_date = (d == today)
            elif date_mode == "This Week":
                iso = dt.isocalendar()
                include_date = (iso[0] == current_year and iso[1] == current_week)
            elif date_mode == "This Month":
                include_date = (dt.year == current_year and dt.month == current_month)

            if not include_date:
                continue

            # Staff filter
            if staff_mode != "All Staff":
                if str(log.get("staff_id") or "") != staff_mode:
                    continue

            # Build a flat record for the table
                        # Build a flat record for the table
            services_parts = []
            total_amount = 0.0
            for s in services:
                name = str(s.get("service") or "Unknown")
                status = (s.get("status") or "").lower()
                base_amt, charge_amt, total_for_service = extract_service_components(s)
                total_amount += total_for_service

                status_text = status if status else "—"

                base_disp = int(base_amt) if base_amt else 0
                charge_disp = int(charge_amt) if charge_amt else 0
                total_disp = int(total_for_service)

                # This string is shown in:
                #  - the Services column in View Logs
                #  - the Log Details dialog under "Services"
                services_parts.append(
                    f"{name} (Base ₹{base_disp}, Charge ₹{charge_disp}, "
                    f"Total ₹{total_disp}, {status_text})"
                )

            services_str = "; ".join(services_parts)


            record = {
                "timestamp": log.get("timestamp"),
                "id": log.get("id"),
                "staff_id": log.get("staff_id"),
                "name": log.get("name"),
                "phone": log.get("phone"),
                "remarks": log.get("remarks"),
                "services_str": services_str,
                "total_amount": int(total_amount),
            }
            self.filtered_logs.append(record)

        # Fill table
        self.table.setRowCount(0)

        for rec in self.filtered_logs:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(format_timestamp(rec["timestamp"])))
            self.table.setItem(row, 1, QTableWidgetItem(str(rec["staff_id"] or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(rec["name"] or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(rec["phone"] or "")))
            self.table.setItem(row, 4, QTableWidgetItem(rec["services_str"]))
            amount_item = QTableWidgetItem(str(rec["total_amount"]))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, amount_item)
            self.table.setItem(row, 6, QTableWidgetItem(str(rec["remarks"] or "—")))

            # Actions cell (Edit / Delete)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(6)

            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("action")
            edit_btn.setProperty("class", "action")
            edit_btn.setFixedHeight(22)
            edit_btn.clicked.connect(lambda _, r=rec: self.open_edit_dialog(r))

            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("action")
            delete_btn.setProperty("class", "action")
            delete_btn.setFixedHeight(22)
            delete_btn.clicked.connect(lambda _, r=rec: self.confirm_and_delete(r))

            action_layout.addWidget(edit_btn)
            action_layout.addWidget(delete_btn)
            action_layout.addStretch()

            self.table.setCellWidget(row, 7, action_widget)

        self.table.resizeColumnsToContents()
        # give a little extra space to Services column
        if self.table.columnCount() > 4:
            self.table.horizontalHeader().setSectionResizeMode(
                4, QHeaderView.ResizeMode.Stretch
            )

    # ------------------------------------------------------------------ #
    # CSV export
    # ------------------------------------------------------------------ #
    def export_filtered_to_csv(self):
        """Export currently visible (filtered) logs to a CSV file."""
        if not getattr(self, "filtered_logs", None):
            QMessageBox.information(self, "No data", "No rows to export.")
            return

        default_name = f"akshaya_logs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", default_name, "CSV files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # header
                writer.writerow(["Timestamp", "Staff ID", "Customer Name", "Phone", "Services", "Total Amount (₹)", "Remarks"])
                # rows
                for rec in self.filtered_logs:
                    ts = format_timestamp(rec.get("timestamp"))
                    staff = rec.get("staff_id", "")
                    name = rec.get("name", "")
                    phone = rec.get("phone", "")
                    services = rec.get("services_str", "")
                    total = rec.get("total_amount", "")
                    remarks = rec.get("remarks", "")
                    writer.writerow([ts, staff, name, phone, services, total, remarks])
            QMessageBox.information(self, "Exported", f"CSV exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", f"Could not export CSV:\n{e}")

    # ------------------------------------------------------------------ #
    # Row actions: edit / delete
    # ------------------------------------------------------------------ #
    def open_edit_dialog(self, rec: Dict[str, Any]):
        # rec is the flat record created by apply_filters
        log_id = rec.get("id")
        if not log_id:
            QMessageBox.warning(self, "Edit", "Log id not available for this row.")
            return

        dlg = EditLogDialog(rec, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # refresh data after success
            QTimer.singleShot(250, self.load_logs)

    def confirm_and_delete(self, rec: Dict[str, Any]):
        log_id = rec.get("id")
        if not log_id:
            QMessageBox.warning(self, "Delete", "Log id not available for this row.")
            return

        ok = QMessageBox.question(self, "Delete", "Are you sure you want to delete this log? This action cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ok != QMessageBox.StandardButton.Yes:
            return

        # call delete helper
        try:
            success = delete_log(log_id)
        except Exception as e:
            success = False
            print("confirm_and_delete exception:", e)

        if success:
            QMessageBox.information(self, "Delete", "Log deleted successfully.")
            QTimer.singleShot(200, self.load_logs)
        else:
            QMessageBox.critical(self, "Delete failed", "Could not delete the log. Check console for details and Supabase permissions.")

    # ------------------------------------------------------------------ #
    # Row details
    # ------------------------------------------------------------------ #
    def open_row_details(self, row: int, column: int):
        """Open a detail dialog for the double-clicked row."""
        if row < 0 or row >= len(self.filtered_logs):
            return
        rec = self.filtered_logs[row]
        dlg = LogDetailsDialog(rec, self)
        dlg.exec()

    def _open_selected_details(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return
        row = sel[0].row()
        self.open_row_details(row, 0)
