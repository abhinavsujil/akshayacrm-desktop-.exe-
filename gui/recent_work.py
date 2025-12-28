# recent_work.py
from __future__ import annotations

from datetime import datetime, date
from typing import List, Dict, Any
import csv

# --- IMPORTS ---
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QFileDialog, QMessageBox, QFrame, QScrollArea, QWidget,
    QSizePolicy
)
from PyQt6.QtGui import QFont, QKeySequence, QColor, QPalette, QCursor
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal


# safe import for QShortcut
try:
    from PyQt6.QtWidgets import QShortcut  # preferred
except Exception:
    from PyQt6.QtGui import QShortcut  # fallback

# server-side fetch helper
try:
    from supabase_utils import supabase_get
except ImportError:
    # Mock for standalone testing if utils not present
    def supabase_get(*args, **kwargs): return None

# ------------------------------------------------------------------ #
# Utilities
# ------------------------------------------------------------------ #
def format_timestamp(raw_ts) -> str:
    """Formats timestamp for the main table row"""
    if not raw_ts:
        return ""
    try:
        # handle timezone-aware strings too
        dt = datetime.fromisoformat(str(raw_ts))
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        try:
            return str(raw_ts)
        except Exception:
            return ""

def parse_timestamp(raw_ts) -> datetime | None:
    if not raw_ts:
        return None
    try:
        return datetime.fromisoformat(str(raw_ts))
    except Exception:
        return None

# ------------------------------------------------------------------ #
# LogDetailsDialog (High Precision Redesign - White Card Theme)
# ------------------------------------------------------------------ #
class LogDetailsDialog(QDialog):
    def __init__(self, record: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("Log Details")

        # ----------------------------
        # Make the dialog resizable and show minimize/maximize buttons
        # ----------------------------
        # Add Window type and show standard titlebar buttons
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setWindowFlags(self.windowFlags() | flags)

        # Add the size grip so user can resize from corner
        try:
            self.setSizeGripEnabled(True)
        except Exception:
            # ignore if not available
            pass

        # Provide sensible minimum size but keep resizable
        self.setMinimumSize(700, 650)  # Slightly taller for spacing

        # Also add a shortcut to toggle maximize/restore for convenience
        try:
            shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
            shortcut.activated.connect(self._toggle_max_restore)
        except Exception:
            pass

        # --- Main Stylesheet ---
        # Note: made sure QScrollArea and internal widgets don't pick an unintended dark bg
        self.setStyleSheet("""
            QDialog {
                background-color: #F0F4F8; /* Light grey-blue background */
                font-family: 'Segoe UI', sans-serif;
            }

            /* The main white card */
            QFrame#detailCard {
                background-color: #FFFFFF;
                border-radius: 16px;
                border: 1px solid #E2E8F0;
            }

            /* Title */
            QLabel#dialogTitle { font-size: 24px; font-weight: 700; color: #0F172A; }

            /* Section headers */
            QLabel.sectionHeader { font-size: 18px; font-weight: 700; color: #334155; margin-bottom: 12px; margin-top: 6px; }
            QLabel.fieldLabel { color: #64748b; font-weight: 600; font-size: 14px; }
            QLabel.fieldValue { color: #1E293B; font-size: 14px; font-weight: 700; }

            /* Service row styling - we use explicit container styling below too */
            QWidget.service-row-container { background: transparent; }

            /* Close Button */
            QPushButton#closeBtn {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                color: #334155;
                padding: 10px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton#closeBtn:hover { background-color: #E2E8F0; color: #1E293B; border-color: #94A3B8; }

            /* Make any QListWidget or QTableWidget used elsewhere have sane defaults (won't override local row look) */
            QTableWidget { background-color: #FFFFFF; }
            QScrollArea { background: transparent; }
        """)

        # Main layout for the dialog (padding around the card)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # --- The Card Container ---
        card_frame = QFrame()
        card_frame.setObjectName("detailCard")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(20)

        # --- Header: Title & Close Icon ---
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Log Details")
        title_lbl.setObjectName("dialogTitle")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        # 'X' close icon button (top-right)
        close_icon_btn = QPushButton("✕")
        close_icon_btn.setFixedSize(30, 30)
        close_icon_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_icon_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; color: #94A3B8; font-size: 20px; }
            QPushButton:hover { color: #475569; }
        """)
        close_icon_btn.clicked.connect(self.accept)
        header_layout.addWidget(close_icon_btn)
        card_layout.addLayout(header_layout)

        # --- Section 1: Customer Information ---
        header_cust = QLabel("👤 Customer Information")
        header_cust.setProperty("class", "sectionHeader")
        card_layout.addWidget(header_cust)

        cust_grid = QGridLayout()
        cust_grid.setHorizontalSpacing(40)  # generous spacing between columns
        cust_grid.setVerticalSpacing(12)

        # Row 1 - Timestamp & Staff ID
        cust_grid.addWidget(self._create_label("Timestamp:", "fieldLabel"), 0, 0)
        cust_grid.addWidget(self._create_label(self._format_ts_detailed(record.get("timestamp")), "fieldValue"), 1, 0)

        cust_grid.addWidget(self._create_label("Staff ID:", "fieldLabel"), 0, 1)
        cust_grid.addWidget(self._create_label(str(record.get("staff_id") or "—"), "fieldValue"), 1, 1)

        # Row 2 - Customer Name & Phone
        cust_grid.addWidget(self._create_label("Customer Name:", "fieldLabel"), 2, 0)
        cust_grid.addWidget(self._create_label(str(record.get("name") or "—"), "fieldValue"), 3, 0)

        cust_grid.addWidget(self._create_label("Phone Number:", "fieldLabel"), 2, 1)
        cust_grid.addWidget(self._create_label(str(record.get("phone") or "—"), "fieldValue"), 3, 1)

        card_layout.addLayout(cust_grid)
        card_layout.addSpacing(8)

        # --- Section 2: Services & Billing ---
        header_svc = QLabel("📄 Services & Billing")
        header_svc.setProperty("class", "sectionHeader")
        card_layout.addWidget(header_svc)

        services = record.get("services") or []
        payments = record.get("payments") or []
        payments_by_service = {str(p.get("service_id")): p for p in payments if p.get("service_id")}

        if not services:
             card_layout.addWidget(self._create_label("No specific services linked.", "fieldValue"))
        else:
            # Scroll area for services list (prevents large dialog overflow)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(140)
            scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # ensure no dark viewport background
            scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea QWidget { background: transparent; }")

            scroll_content = QWidget()
            # ensure explicit white background behind rows so it matches the card
            scroll_content.setStyleSheet("background: transparent;")
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setContentsMargins(0, 0, 0, 0)
            scroll_layout.setSpacing(8)

            # Header row for service columns
            hdr_row = QHBoxLayout()
            hdr_row.setContentsMargins(8, 6, 8, 6)
            hdr_row.addWidget(self._create_label("Service", "fieldLabel"), stretch=4)

            lbl_base = self._create_label("Base", "fieldLabel")
            lbl_base.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hdr_row.addWidget(lbl_base, stretch=1)

            lbl_charge = self._create_label("Charge", "fieldLabel")
            lbl_charge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hdr_row.addWidget(lbl_charge, stretch=1)

            lbl_total = self._create_label("Total", "fieldLabel")
            lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hdr_row.addWidget(lbl_total, stretch=1)

            # Add a subtle separator before rows (mimics card design)
            hdr_container = QWidget()
            hdr_container.setLayout(hdr_row)
            hdr_container.setStyleSheet("padding: 6px 8px;")
            scroll_layout.addWidget(hdr_container)

            total_billed = 0.0
            # Build each row as a small rounded container to match design
            for s in services:
                sid_key = str(s.get("id")) if s.get("id") is not None else None
                payment_data = payments_by_service.get(sid_key)

                svc_name = s.get("service") or "Unknown"

                if payment_data:
                    base = float(payment_data.get("base_amount") or 0)
                    charge = float(payment_data.get("service_charge") or 0)
                    total = float(payment_data.get("amount") or (base + charge))
                else:
                    total = float(s.get("amount") or 0)
                    base = total
                    charge = 0.0

                total_billed += total

                # Row container - white background with subtle border and rounded corners
                row_container = QWidget()
                row_container.setProperty("class", "service-row-container")
                row_layout = QHBoxLayout(row_container)
                row_layout.setContentsMargins(12, 12, 12, 12)
                row_layout.setSpacing(8)

                # Style row background and border to mimic card row look
                row_container.setStyleSheet("""
                    background-color: #FFFFFF;
                    border: 1px solid #EEF2F6;
                    border-radius: 10px;
                """)

                # Service name (left)
                svc_lbl = self._create_label(svc_name, "fieldValue")
                svc_lbl.setStyleSheet("font-size:14px; color:#0F172A;")
                row_layout.addWidget(svc_lbl, stretch=4)

                # Amounts (right aligned)
                base_lbl = self._create_label(f"₹{int(base)}", "fieldValue")
                base_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(base_lbl, stretch=1)

                charge_lbl = self._create_label(f"₹{int(charge)}", "fieldValue")
                charge_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(charge_lbl, stretch=1)

                total_lbl = self._create_label(f"₹{int(total)}", "fieldValue")
                total_lbl.setStyleSheet("color: #06B6D4; font-weight: 800; font-size: 15px;")
                total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(total_lbl, stretch=1)

                scroll_layout.addWidget(row_container)

            # Add total billed summary as separate row (right aligned)
            total_summary = QWidget()
            ts_layout = QHBoxLayout(total_summary)
            ts_layout.setContentsMargins(0, 8, 0, 0)
            ts_layout.addStretch()
            ts_layout.addWidget(self._create_label("Total Billed:", "fieldLabel"))
            total_billed_lbl = self._create_label(f"₹{int(total_billed)}", "fieldValue")
            total_billed_lbl.setStyleSheet("color: #06B6D4; font-weight: 900; font-size: 16px; margin-left: 12px;")
            ts_layout.addWidget(total_billed_lbl)
            scroll_layout.addWidget(total_summary)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            card_layout.addWidget(scroll, stretch=1)

        # --- Section 3: Payment ---
        card_layout.addSpacing(10)
        header_pay = QLabel("💳 Payment")
        header_pay.setProperty("class", "sectionHeader")
        card_layout.addWidget(header_pay)

        pay_grid = QGridLayout()
        pay_grid.setHorizontalSpacing(50)
        pay_grid.setVerticalSpacing(14)

        # Payment Methods Summary
        methods = sorted(list(set(p.get("payment_method") for p in payments if p.get("payment_method"))))
        method_str = ", ".join(m.upper() for m in methods) if methods else "—"

        pay_grid.addWidget(self._create_label("Payment Method:", "fieldLabel"), 0, 0)
        pay_grid.addWidget(self._create_label(method_str, "fieldValue"), 1, 0)

        # Overall Status with Icon
        overall_status = str(record.get("status") or "Unknown").capitalize()

        pay_grid.addWidget(self._create_label("Status:", "fieldLabel"), 0, 1)

        status_container = QHBoxLayout()
        status_container.setContentsMargins(0,0,0,0)
        status_container.setSpacing(8)
        status_container.setAlignment(Qt.AlignmentFlag.AlignLeft)

        status_value_lbl = self._create_label(overall_status, "fieldValue")

        # Add a checkmark for approved/completed
        if overall_status in ["Approved", "Completed"]:
            icon_lbl = QLabel("✅")
            icon_lbl.setStyleSheet("font-size: 16px; margin-top: 2px;")
            status_container.addWidget(icon_lbl)
            status_value_lbl.setStyleSheet("color: #166534; font-weight: 700;")

        status_container.addWidget(status_value_lbl)
        pay_grid.addLayout(status_container, 1, 1)

        card_layout.addLayout(pay_grid)

        # --- Section 4: Remarks ---
        card_layout.addSpacing(10)
        header_rem = QLabel("📝 Remarks")
        header_rem.setProperty("class", "sectionHeader")
        card_layout.addWidget(header_rem)

        rem_val = self._create_label(str(record.get("remarks") or "—"), "fieldValue")
        rem_val.setWordWrap(True)
        rem_val.setStyleSheet("background-color: #F8FAFC; padding: 12px; border-radius: 8px; border: 1px solid #F1F5F9;")
        card_layout.addWidget(rem_val)

        # --- Add card to main layout ---
        main_layout.addWidget(card_frame)

        # --- Footer Close Button ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setObjectName("closeBtn")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_close)
        main_layout.addLayout(btn_row)

    def _toggle_max_restore(self):
        """Toggle maximize/restore window state (used by Ctrl+M shortcut)."""
        try:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        except Exception:
            pass

    def _create_label(self, text, css_class):
        """Helper to create styled labels quickly"""
        lbl = QLabel(text)
        lbl.setProperty("class", css_class)
        return lbl

    def _format_ts_detailed(self, raw):
        """Formats timestamp specifically for the details dialog view (YYYY-MM-DD HH:MM AM/PM)"""
        if not raw:
            return "—"
        try:
            dt = datetime.fromisoformat(str(raw)) if not isinstance(raw, datetime) else raw
            return dt.strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            return str(raw)

# ------------------------------------------------------------------ #
# Thread: server-side fetch for single staff
# ------------------------------------------------------------------ #
class FetchThread(QThread):
    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, staff_id: str, limit: int = 200):
        super().__init__()
        self.staff_id = str(staff_id)
        self.limit = int(limit)

    def run(self):
        try:
            select = "*,services(*),payments(*)"
            filter_query = f"staff_id=eq.{self.staff_id}&limit={self.limit}&order=timestamp.desc"
            resp = supabase_get("logs", filter_query=filter_query, select=select)
            if resp is None or getattr(resp, "status_code", None) != 200:
                raise Exception(f"HTTP {getattr(resp, 'status_code', 'N/A')}: {getattr(resp, 'text', str(resp))}")
            data = resp.json() or []
            result = []
            for log in data:
                services = log.get("services") or []
                payments = log.get("payments") or []
                result.append({"log": log, "services": services, "payments": payments})
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

# ------------------------------------------------------------------ #
# RecentWorkDialog (Main Table View)
# ------------------------------------------------------------------ #
class RecentWorkDialog(QDialog):
    def __init__(self, staff_id: str, parent=None, fetch_limit: int = 200):
        super().__init__(parent)
        self.staff_id = str(staff_id)
        self.fetch_limit = int(fetch_limit)

        self.setWindowTitle("Recent Work")
        self.setMinimumSize(1000, 600)

        # caches
        self.all_logs: List[Dict[str, Any]] = []
        self.filtered_logs: List[Dict[str, Any]] = []

        # background helpers
        self._thread: FetchThread | None = None
        self._timer: QTimer | None = None
        self._dot_index = 0

        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        # Main Dialog Stylesheet matching the dashboard vibe
        self.setStyleSheet("""
            QDialog { background-color: #F0F4F8; font-family: 'Segoe UI', sans-serif; color: #1E293B; }
            QLabel { font-size: 14px; color: #1E293B; }
            QLabel#headerTitle { font-size: 22px; font-weight: 700; color: #1E293B; }

            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 600;
                color: #334155;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; color: #1E293B; }
            QPushButton:pressed { background-color: #F1F5F9; }

            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                padding: 8px 12px;
                min-width: 130px;
                font-size: 14px;
            }
            QComboBox:focus { border: 2px solid #06B6D4; padding: 7px 11px; }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                selection-background-color: #06B6D4;
                selection-color: white;
                outline: 0;
            }

            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                gridline-color: #F1F5F9;
                outline: 0;
            }

            QHeaderView::section {
                background-color: #F8FAFC;
                padding: 12px 12px;
                border: none;
                border-bottom: 2px solid #E2E8F0;
                font-weight: 600;
                color: #64748B;
                font-size: 14px;
            }

            QScrollBar:vertical {
                border: none; background: #F1F5F9; width: 10px; margin: 0px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1; min-height: 20px; border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(25)

        # --- Header ---
        top = QHBoxLayout()
        t = QLabel(f"Recent Work — Staff: {self.staff_id}")
        t.setObjectName("headerTitle")
        top.addWidget(t)
        top.addStretch()

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_refresh.clicked.connect(self.refresh_data)
        top.addWidget(self.btn_refresh)

        exp = QPushButton("⬇ Export CSV")
        exp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        exp.clicked.connect(self.export_csv)
        top.addWidget(exp)

        main.addLayout(top)

        # --- Filters ---
        frow = QHBoxLayout()
        frow.setSpacing(15)
        label_date = QLabel("Date Range:")
        label_date.setStyleSheet("font-weight: 600; color: #64748B;")
        frow.addWidget(label_date)
        self.date_filter = QComboBox()
        self.date_filter.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.date_filter.addItems(["All Time", "Today", "This Week", "This Month"])
        self.date_filter.currentIndexChanged.connect(self.apply_filters)
        frow.addWidget(self.date_filter)

        frow.addSpacing(20)
        label_service = QLabel("Filter by Service:")
        label_service.setStyleSheet("font-weight: 600; color: #64748B;")
        frow.addWidget(label_service)
        self.service_filter = QComboBox()
        self.service_filter.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.service_filter.addItem("All Services")
        self.service_filter.currentIndexChanged.connect(self.apply_filters)
        frow.addWidget(self.service_filter)

        frow.addStretch()
        main.addLayout(frow)

        # --- Table ---
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Staff ID", "Customer Name", "Phone",
            "Services Summary", "Total (₹)", "Status", "Remarks"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setFrameShape(QFrame.Shape.NoFrame)

        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # initial widths
        hdr.resizeSection(0, 180)
        hdr.resizeSection(1, 100)
        hdr.resizeSection(2, 150)
        hdr.resizeSection(3, 120)
        hdr.resizeSection(4, 250)
        hdr.resizeSection(5, 120)
        hdr.resizeSection(6, 140)

        self.table.setShowGrid(False)
        self.table.cellDoubleClicked.connect(self.open_details)

        main.addWidget(self.table, stretch=1)

        # --- Bottom Action ---
        brow = QHBoxLayout()
        brow.addStretch()
        close = QPushButton("Close")
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close.clicked.connect(self.accept)
        brow.addWidget(close)
        main.addLayout(brow)

    # --------------------------
    # Data loading & Animation
    # --------------------------
    def refresh_data(self):
        if self._thread and self._thread.isRunning():
            return
        self._start_anim()
        self._thread = FetchThread(self.staff_id, limit=self.fetch_limit)

        def on_done(rows):
            self._stop_anim()
            self.all_logs = rows or []
            # Update service filter options
            services = sorted({ s.get("service") for item in self.all_logs for s in (item.get("services") or []) if s.get("service") })
            self.service_filter.blockSignals(True)
            self.service_filter.clear()
            self.service_filter.addItem("All Services")
            for s in services:
                self.service_filter.addItem(str(s))
            self.service_filter.blockSignals(False)
            self.apply_filters()
            self._thread = None

        def on_fail(msg):
            self._stop_anim()
            QMessageBox.critical(self, "Error", f"Failed to fetch recent work:\n{msg}")
            self._thread = None

        self._thread.done.connect(on_done)
        self._thread.failed.connect(on_fail)
        self._thread.start()

    def _start_anim(self):
        self.btn_refresh.setEnabled(False)
        self._dot_index = 0
        if not self._timer:
            self._timer = QTimer(self)
            self._timer.setInterval(300)
            def tick():
                self._dot_index = (self._dot_index + 1) % 4
                self.btn_refresh.setText("🔄 Refreshing" + "." * self._dot_index)
            self._timer.timeout.connect(tick)
        self._timer.start()
        self.btn_refresh.setText("🔄 Refreshing...")

    def _stop_anim(self):
        if self._timer:
            self._timer.stop()
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄 Refresh")

    # --------------------------
    # Filtering & Population
    # --------------------------
    def apply_filters(self):
        self.table.setRowCount(0)
        date_mode = self.date_filter.currentText() if self.date_filter else "All Time"
        service_mode = self.service_filter.currentText() if self.service_filter else "All Services"

        today = date.today()
        now = datetime.now()
        current_iso = now.isocalendar()
        current_year, current_week = current_iso[0], current_iso[1]
        current_month = now.month

        self.filtered_logs = []

        for item in self.all_logs:
            log = item.get("log") or {}
            services = item.get("services") or []
            payments = item.get("payments") or []

            dt = parse_timestamp(log.get("timestamp"))
            if not dt: continue

            # Date Filter
            ok_date = True
            if date_mode == "Today": ok_date = (dt.date() == today)
            elif date_mode == "This Week": ok_date = (dt.isocalendar()[0] == current_year and dt.isocalendar()[1] == current_week)
            elif date_mode == "This Month": ok_date = (dt.year == current_year and dt.month == current_month)
            if not ok_date: continue

            # Service Filter
            if service_mode != "All Services":
                if not any(str(s.get("service") or "") == service_mode for s in services):
                    continue

            # Calculate Totals & Status
            total = sum(float(p.get("amount") or 0) for p in payments) if payments else sum(float(s.get("amount") or 0) for s in services)

            services_parts = [str(s.get("service") or "Unknown") for s in services]
            statuses = [str(s.get("status") or "").lower() for s in services]

            overall = "Unknown"
            if any(s == "pending" for s in statuses): overall = "Pending"
            elif any(s == "rejected" for s in statuses): overall = "Rejected"
            elif all(s == "approved" for s in statuses) and statuses: overall = "Approved"

            rec = {
                "timestamp": log.get("timestamp"),
                "staff_id": log.get("staff_id"),
                "name": log.get("name"),
                "phone": log.get("phone"),
                "services_str": ", ".join(services_parts) if services_parts else "—",
                "total_amount": int(total),
                "remarks": log.get("remarks"),
                "status": overall,
                "services": services,
                "payments": payments,
            }
            self.filtered_logs.append(rec)

        # Populate Table
        for rec in self.filtered_logs:
            r = self.table.rowCount()
            self.table.insertRow(r)

            # 0: Timestamp
            item = QTableWidgetItem(format_timestamp(rec["timestamp"]))
            self.table.setItem(r, 0, item)

            # 1-3: Basic Info
            self.table.setItem(r, 1, QTableWidgetItem(str(rec["staff_id"] or "—")))
            self.table.setItem(r, 2, QTableWidgetItem(str(rec["name"] or "—")))
            self.table.setItem(r, 3, QTableWidgetItem(str(rec["phone"] or "—")))

            # 4: Services (tooltip)
            svc_item = QTableWidgetItem(rec["services_str"])
            svc_item.setToolTip(rec["services_str"])
            self.table.setItem(r, 4, svc_item)

            # 5: Total Amount (Right Aligned)
            amt_item = QTableWidgetItem(f"₹{rec['total_amount']}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amt_item.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            self.table.setItem(r, 5, amt_item)

            # 6: Status Chip
            st = (rec.get("status") or "").lower()
            status_label = QLabel(st.capitalize())
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if st == "approved":
                bg, text_c, border = "#DCFCE7", "#166534", "#86EFAC"  # Green
            elif st == "pending":
                bg, text_c, border = "#FEF9C3", "#854D0E", "#FDE047"  # Yellow/Amber
            elif st == "rejected":
                bg, text_c, border = "#FEE2E2", "#991B1B", "#FCA5A5"  # Red
            else:
                bg, text_c, border = "#F1F5F9", "#475569", "#CBD5E1"  # Grey/Blue

            status_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg}; color: {text_c}; border: 1px solid {border};
                    border-radius: 12px; padding: 6px 12px; font-weight: 700; font-size: 12px;
                }}
            """)
            status_container = QWidget()
            sl = QHBoxLayout(status_container)
            sl.setContentsMargins(0, 5, 0, 5)
            sl.addWidget(status_label)
            sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(r, 6, status_container)

            # 7: Remarks (Greyed out)
            remarks_item = QTableWidgetItem(str(rec.get("remarks") or "—"))
            remarks_item.setForeground(QColor("#94A3B8"))
            remarks_item.setToolTip(str(rec.get("remarks") or ""))
            self.table.setItem(r, 7, remarks_item)

    # --------------------------
    # CSV export
    # --------------------------
    def export_csv(self):
        if not getattr(self, "filtered_logs", None):
            QMessageBox.information(self, "No data", "No rows to export.")
            return
        default = f"recent_work_{self.staff_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", default, "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Timestamp", "Staff ID", "Customer Name", "Phone", "Services", "Total Amount (₹)", "Status", "Remarks"])
                for rec in self.filtered_logs:
                    ts = format_timestamp(rec.get("timestamp"))
                    w.writerow([ts, rec.get("staff_id",""), rec.get("name",""), rec.get("phone",""), rec.get("services_str",""), rec.get("total_amount",""), rec.get("status",""), rec.get("remarks","")])
            QMessageBox.information(self, "Exported", f"CSV exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", f"Could not export CSV:\n{e}")

    # --------------------------
    # Interaction
    # --------------------------
    def open_details(self, row:int, col:int):
        if row < 0 or row >= len(self.filtered_logs):
            return
        rec = self.filtered_logs[row]
        dlg = LogDetailsDialog(rec, self)
        dlg.exec()

if __name__ == '__main__':
    # Simple test harness
    from PyQt6.QtWidgets import QApplication
    import sys

    # Example test record to preview the design
    test_record = {
        "timestamp": datetime.now().isoformat(),
        "staff_id": "S12345",
        "name": "Rahul Kumar",
        "phone": "9876543210",
        "services": [
            {"id": 1, "service": "10th Markscard", "amount": 70, "status": "approved"},
            {"id": 2, "service": "Driving License Renewal", "amount": 130, "status": "approved"}
        ],
        "payments": [
            {"service_id": 1, "amount": 70, "base_amount": 50, "service_charge": 20, "payment_method": "UPI"},
            {"service_id": 2, "amount": 130, "base_amount": 100, "service_charge": 30, "payment_method": "UPI"}
        ],
        "remarks": "Customer requested urgent processing for loan application.",
        "status": "Approved"
    }

    app = QApplication(sys.argv)
    # To quickly preview the LogDetailsDialog without supabase integration:
    dlg = LogDetailsDialog(test_record)
    dlg.exec()

    sys.exit(0)
