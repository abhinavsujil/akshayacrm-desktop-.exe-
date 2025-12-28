from __future__ import annotations

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any
import re

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QHeaderView,
    QMessageBox,
)

# safe import for QShortcut (some builds expose it under QtGui)
try:
    from PyQt6.QtWidgets import QShortcut
except Exception:
    from PyQt6.QtGui import QShortcut  # fallback

from supabase_utils import (
    get_pending_services_with_logs,
    update_service_status,
)


def format_pretty_date(raw_ts: Any) -> str:
    """Return a friendly short date like '17th Nov, Tue' or empty string."""
    if not raw_ts:
        return ""
    try:
        dt = raw_ts if isinstance(raw_ts, datetime) else datetime.fromisoformat(str(raw_ts))
    except Exception:
        return str(raw_ts)

    d = dt.day
    if 11 <= d <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")

    day_part = f"{d}{suffix}"
    month_part = dt.strftime("%b")
    weekday_part = dt.strftime("%a")
    return f"{day_part} {month_part}, {weekday_part}"


class FetchPendingThread(QThread):
    fetched = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            # IMPORTANT: include_suggestions=True so staff-suggested services
            # (service_suggestions table) also appear here.
            rows = get_pending_services_with_logs(include_suggestions=True) or []
            # Optional: quick debug so you can see if backend is returning anything
            print(f"[VerifyServices] fetched pending rows: {len(rows)}")
            self.fetched.emit(rows)
        except Exception as e:
            self.failed.emit(str(e))


class VerifyServicesDialog(QDialog):
    """
    Admin dialog to verify *service names* that staff have typed.

    Approve/Reject works at **service-name level**:
      - If you select one row of "TC Card" and click Approve,
        ALL pending rows with service="TC Card" in this list
        will be approved in one shot.
    """
    services_updated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Verify Services")
        self.setMinimumSize(920, 540)

        self.date_filter: QComboBox | None = None
        self.staff_filter: QComboBox | None = None
        self.table: QTableWidget | None = None

        # raw pending rows from Supabase: each {"service": {...}, "log": {...}}
        self._pending_rows: List[Dict[str, Any]] = []

        self._fetch_thread: FetchPendingThread | None = None
        self._refresh_timer: QTimer | None = None
        self._refresh_dot_index = 0

        self._load_styles()
        self._init_ui()
        self.refresh_data()

    def _load_styles(self):
        # load style.qss if present, otherwise apply fallback QSS
        try:
            base_dir = Path(__file__).resolve().parent
            qss_path = base_dir / "style.qss"
            if qss_path.exists():
                with qss_path.open("r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                return
        except Exception:
            pass

        # fallback style with clear gridlines and outlined/chip buttons
        self.setStyleSheet(
            """
            QDialog { background-color: #f8fafc; color: #0f172a; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
            QLabel { font-size: 13px; }

            /* Table / grid styles - make lines visible */
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e6eef8;
                border: 1px solid #e6eef8;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #eef2f7;
            }
            QTableWidget::item:selected {
                background-color: #e6f0ff;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 8px 6px;
                border: 1px solid #e6eef8;
                font-weight: 700;
                color: #0f172a;
            }

            /* Refresh button (keeps a compact pill style) */
            QPushButton#refreshButton {
                background-color: #ffffff;
                color: #6b46ff;
                border-radius: 12px;
                padding: 8px 12px;
                border: 1px solid #e9d8ff;
                font-weight: 600;
            }
            QPushButton#refreshButton:hover { background-color: #fbf8ff; }

            /* Approve - chip style (solid green pill) */
            QPushButton#approveButton {
                background-color: #10b981;
                color: #ffffff;
                border-radius: 999px; /* pill */
                padding: 6px 14px;
                border: 2px solid #0f9a64; /* darker outline */
                font-weight: 700;
                font-size: 13px;
                min-height: 36px;
            }
            QPushButton#approveButton:disabled {
                background-color: #93c6a5;
                border: 2px solid #7fb68f;
                opacity: 0.9;
            }
            QPushButton#approveButton:hover:!disabled { background-color: #0ea46f; }

            /* Reject - chip style (white with red border + red text) */
            QPushButton#rejectButton {
                background-color: #ffffff;
                color: #dc2626;
                border-radius: 999px; /* pill */
                padding: 6px 14px;
                border: 2px solid #dc2626; /* red outline */
                font-weight: 700;
                font-size: 13px;
                min-height: 36px;
            }
            QPushButton#rejectButton:disabled {
                background-color: #ffffff;
                color: #f5a3a3;
                border: 2px solid #e09797;
                opacity: 0.85;
            }
            QPushButton#rejectButton:hover:!disabled { background-color: #fff5f5; }

            QPushButton#closeButton {
                background: transparent;
                color: #6b7280;
                border-radius: 6px;
                padding: 6px 12px;
                border: 1px solid #e5e7eb;
            }
            QPushButton#closeButton:hover { background-color: #e5e7eb; }

            QComboBox {
                background-color: #ffffff;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
                padding: 6px 8px;
            }

            /* Small chip labels used inside table for statuses */
            QLabel.statusChip {
                padding: 4px 10px;
                border-radius: 999px;
                font-weight: 700;
                font-size: 12px;
            }
            """
        )

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(12)

        title_label = QLabel("Pending services requiring admin verification")
        title_label.setFont(QFont("Inter", 15, QFont.Weight.Bold))

        title_layout = QHBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("⟳ Refresh")
        self.btn_refresh.setObjectName("refreshButton")
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.clicked.connect(self.refresh_data)
        title_layout.addWidget(self.btn_refresh)

        # keyboard shortcut for refresh (R)
        try:
            QShortcut(QKeySequence("R"), self, activated=self.refresh_data)
        except Exception:
            pass

        main_layout.addLayout(title_layout)

        # Filters
        filters_layout = QHBoxLayout()

        date_title = QLabel("Date:")
        date_title.setFont(QFont("Inter", 12))
        self.date_filter = QComboBox()
        self.date_filter.addItems(["All", "Today", "This Week", "This Month"])
        self.date_filter.currentIndexChanged.connect(self.apply_filters)

        staff_title = QLabel("Staff:")
        staff_title.setFont(QFont("Inter", 12))
        self.staff_filter = QComboBox()
        self.staff_filter.addItem("All Staff")
        self.staff_filter.currentIndexChanged.connect(self.apply_filters)

        filters_layout.addWidget(date_title)
        filters_layout.addWidget(self.date_filter)
        filters_layout.addSpacing(20)
        filters_layout.addWidget(staff_title)
        filters_layout.addWidget(self.staff_filter)
        filters_layout.addStretch()

        main_layout.addLayout(filters_layout)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ensure gridlines are shown and table has a visible area
        self.table.setShowGrid(True)
        self.table.setMinimumHeight(300)

        headers = [
            "Timestamp",
            "Staff ID",
            "Customer Name",
            "Phone",
            "Service",
            "Amount (₹)",
            "Status",
        ]
        self.table.setHorizontalHeaderLabels(headers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(36)
        header.setMinimumSectionSize(80)

        self.table.itemSelectionChanged.connect(self._update_action_buttons_state)

        main_layout.addWidget(self.table)

        # Bottom buttons (chips)
        bottom_layout = QHBoxLayout()

        self.btn_approve = QPushButton("✅  Approve Selected")
        self.btn_approve.setObjectName("approveButton")
        self.btn_approve.setMinimumHeight(44)
        self.btn_approve.setMinimumWidth(140)
        self.btn_approve.clicked.connect(self.approve_selected)
        self.btn_approve.setEnabled(False)
        self.btn_approve.setStyleSheet(
            """
            background-color: #10b981;
            color: #ffffff;
            border-radius: 18px;
            padding: 6px 14px;
            border: 2px solid #0f9a64;
            font-weight: 700;
            font-size: 13px;
        """
        )

        self.btn_reject = QPushButton("❌  Reject Selected")
        self.btn_reject.setObjectName("rejectButton")
        self.btn_reject.setMinimumHeight(44)
        self.btn_reject.setMinimumWidth(140)
        self.btn_reject.clicked.connect(self.reject_selected)
        self.btn_reject.setEnabled(False)
        self.btn_reject.setStyleSheet(
            """
            background-color: #ffffff;
            color: #dc2626;
            border-radius: 18px;
            padding: 6px 14px;
            border: 2px solid #dc2626;
            font-weight: 700;
            font-size: 13px;
        """
        )

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("closeButton")
        self.btn_close.setMinimumHeight(36)
        self.btn_close.clicked.connect(self.close)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_approve)
        bottom_layout.addSpacing(12)
        bottom_layout.addWidget(self.btn_reject)
        bottom_layout.addSpacing(22)
        bottom_layout.addWidget(self.btn_close)

        main_layout.addLayout(bottom_layout)

        # shortcuts for actions
        try:
            QShortcut(QKeySequence("Ctrl+A"), self, activated=self.approve_selected)
            QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.reject_selected)
        except Exception:
            pass

    def refresh_data(self):
        """Fetch pending services (background) and update UI."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            return

        # animate refresh button
        self.btn_refresh.setEnabled(False)
        self._refresh_dot_index = 0
        if self._refresh_timer is None:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setInterval(300)

            def _tick():
                self._refresh_dot_index = (self._refresh_dot_index + 1) % 4
                self.btn_refresh.setText(f"⟳ Refreshing{'.' * self._refresh_dot_index}")

            self._refresh_timer.timeout.connect(_tick)
        self._refresh_timer.start()
        self.btn_refresh.setText("⟳ Refreshing")

        self._fetch_thread = FetchPendingThread()

        def on_fetched(rows):
            if self._refresh_timer:
                self._refresh_timer.stop()
            self.btn_refresh.setText("⟳ Refresh")
            self.btn_refresh.setEnabled(True)

            self._pending_rows = rows or []
            staff_ids = sorted({row["log"].get("staff_id") for row in self._pending_rows if row.get("log")})
            current_staff = (
                self.staff_filter.currentText() if self.staff_filter is not None else "All Staff"
            )

            self.staff_filter.blockSignals(True)
            self.staff_filter.clear()
            self.staff_filter.addItem("All Staff")
            for sid in staff_ids:
                if sid:
                    self.staff_filter.addItem(str(sid))
            self.staff_filter.blockSignals(False)

            idx = self.staff_filter.findText(current_staff)
            if idx != -1:
                self.staff_filter.setCurrentIndex(idx)

            self.apply_filters()
            try:
                self._fetch_thread.quit()
                self._fetch_thread.wait(50)
            except Exception:
                pass
            self._fetch_thread = None

        def on_failed(msg):
            if self._refresh_timer:
                self._refresh_timer.stop()
            self.btn_refresh.setText("⟳ Refresh")
            self.btn_refresh.setEnabled(True)
            QMessageBox.critical(self, "Refresh error", f"Failed to fetch pending services:\n{msg}")
            self._fetch_thread = None

        self._fetch_thread.fetched.connect(on_fetched)
        self._fetch_thread.failed.connect(on_failed)
        self._fetch_thread.start()

    def _pass_date_filter(self, dt: date, mode: str) -> bool:
        today = date.today()
        if mode == "All":
            return True
        if mode == "Today":
            return dt == today
        if mode == "This Week":
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week <= dt <= end_of_week
        if mode == "This Month":
            return dt.year == today.year and dt.month == today.month
        return True

    def apply_filters(self):
        """Apply date + staff filters and populate the table with chip-status cells."""
        if not self.table:
            return

        date_mode = self.date_filter.currentText() if self.date_filter else "All"
        staff_mode = self.staff_filter.currentText() if self.staff_filter else "All Staff"

        self.table.setRowCount(0)

        # regex for hex colours (#abc or #aabbcc)
        hex_re = re.compile(r"^#([A-Fa-f0-9]{3}|[A-Fa-f0-9]{6})$")

        for row in self._pending_rows:
            log = row.get("log") or {}
            service = row.get("service") or {}

            # --- SKIP synthetic suggestion-only rows ---
            # These are the rows that show up as:
            #   Customer Name: "Suggested by: <staff>"
            #   Phone: "sugg:<id>"
            customer_name = str(log.get("name") or "")
            phone = str(log.get("phone") or "")
            if customer_name.lower().startswith("suggested by:") or phone.startswith("sugg:"):
                # ignore pure suggestion rows in this Verify Services screen
                continue
            # --- end skip block ---

            raw_ts = log.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(raw_ts))
                d = dt.date()
            except Exception:
                d = date.today()


            if not self._pass_date_filter(d, date_mode):
                continue

            staff_id = str(log.get("staff_id") or "")
            if staff_mode != "All Staff" and staff_id != staff_mode:
                continue

                        # customer_name and phone already computed above
            service_name = str(service.get("service") or "")


            # amount is now in payments table; service.amount is usually None.
            # For verify-screen (just whitelisting names), blank looks better than 0.
            amount_val = service.get("amount")
            if amount_val in (None, "", 0, 0.0):
                display_amount = ""
            else:
                try:
                    display_amount = str(int(float(amount_val)))
                except Exception:
                    display_amount = str(amount_val)

            status_raw = service.get("status") or ""
            status = str(status_raw).strip()

            # SANITISE: if status looks like a hex color (or contains '#'), treat as invalid
            if status and hex_re.match(status):
                sid = str(service.get("id") or "")
                print(f"[verify_services] WARNING: service.id={sid} has color value in 'status': '{status}'")
                status = "unknown (color saved)"

            s_lower = status.lower()
            if s_lower in ("approved", "approve", "ok", "done"):
                s_normal = "approved"
            elif s_lower in ("rejected", "reject", "declined"):
                s_normal = "rejected"
            elif s_lower in ("pending", "wait", "waiting"):
                s_normal = "pending"
            elif status.startswith("#"):
                s_normal = "unknown (color saved)"
                sid = str(service.get("id") or "")
                print(f"[verify_services] WARNING: service.id={sid} status contains #: '{status}'")
            else:
                s_normal = status or "pending"  # default to pending for safety

            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            service_id = str(service.get("id") or "")
            ts_item = QTableWidgetItem(format_pretty_date(raw_ts))
            ts_item.setData(Qt.ItemDataRole.UserRole, service_id)
            ts_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 0, ts_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(staff_id))
            self.table.setItem(row_idx, 2, QTableWidgetItem(customer_name))
            self.table.setItem(row_idx, 3, QTableWidgetItem(phone))
            self.table.setItem(row_idx, 4, QTableWidgetItem(service_name))

            amt_item = QTableWidgetItem(display_amount)
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 5, amt_item)

            # Status - use a styled QLabel "chip" in the cell for better visuals
            status_label = self._make_status_chip(s_normal)
            self.table.setCellWidget(row_idx, 6, status_label)

        self.table.resizeColumnsToContents()
        if self.table.columnCount() > 4:
            self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self._update_action_buttons_state()

    def _make_status_chip(self, status_text: str) -> QLabel:
        """Return QLabel styled as a small chip representing status_text."""
        t = (status_text or "").strip().lower()
        display_text = status_text if not status_text.startswith("unknown") else "Unknown"

        label = QLabel(display_text.capitalize())
        label.setProperty("class", "statusChip")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        label.setFixedHeight(28)
        label.setContentsMargins(6, 2, 6, 2)

        if t == "approved":
            label.setStyleSheet(
                "QLabel.statusChip { background-color: #dcfce7; color: #065f46; "
                "border-radius: 999px; padding: 4px 10px; border: 1px solid #86efac; font-weight:700; }"
            )
        elif t == "rejected":
            label.setStyleSheet(
                "QLabel.statusChip { background-color: #ffffff; color: #9b1c1c; "
                "border-radius: 999px; padding: 4px 10px; border: 1px solid #dc2626; font-weight:700; }"
            )
        elif t == "pending":
            label.setStyleSheet(
                "QLabel.statusChip { background-color: #fff7ed; color: #92400e; "
                "border-radius: 999px; padding: 4px 10px; border: 1px solid #facc15; font-weight:700; }"
            )
        else:
            label.setStyleSheet(
                "QLabel.statusChip { background-color: #eef2ff; color: #3730a3; "
                "border-radius: 999px; padding: 4px 10px; border: 1px solid #c7d2fe; font-weight:700; }"
            )
        return label

    # --------- selection helpers ---------

    def _get_selected_rows(self) -> List[int]:
        if not self.table:
            return []
        return sorted({idx.row() for idx in self.table.selectedIndexes()})

    def _get_selected_service_ids(self) -> List[str]:
        """Return *only* the IDs of the explicitly selected rows (per-row)."""
        ids: List[str] = []
        if not self.table:
            return ids

        for row in self._get_selected_rows():
            item = self.table.item(row, 0)
            if not item:
                continue
            service_id = item.data(Qt.ItemDataRole.UserRole)
            if service_id:
                ids.append(str(service_id))
        return ids

    def _get_all_ids_for_selected_service_names(self) -> List[str]:
        """
        NEW BEHAVIOUR:
          - Look at the selected rows.
          - Collect their service *names*.
          - Return IDs of **ALL pending rows** in _pending_rows that share those names.

        Example:
          If 'TC Card' appears 5 times and you select just 1 of them,
          this returns all 5 IDs, so 1 approve click approves all 5.
        """
        if not self._pending_rows or not self.table:
            return []

        # 1) From selected rows → get their service IDs
        selected_ids = self._get_selected_service_ids()
        if not selected_ids:
            return []

        # 2) Map those IDs to service names (lowercased)
        selected_names_lower = set()
        for rec in self._pending_rows:
            svc = rec.get("service") or {}
            sid = str(svc.get("id") or "")
            if sid in selected_ids:
                name = (svc.get("service") or "").strip().lower()
                if name:
                    selected_names_lower.add(name)

        if not selected_names_lower:
            # fallback to old behaviour if something weird happens
            return selected_ids

        # 3) Now collect ALL IDs whose service name is in that name set
        all_ids: set[str] = set()
        for rec in self._pending_rows:
            svc = rec.get("service") or {}
            name = (svc.get("service") or "").strip().lower()
            if name and name in selected_names_lower:
                sid = svc.get("id")
                if sid:
                    all_ids.add(str(sid))

        return list(all_ids)

    def _update_action_buttons_state(self):
        ids = self._get_selected_service_ids()
        enabled = len(ids) > 0
        self.btn_approve.setEnabled(enabled)
        self.btn_reject.setEnabled(enabled)

    # --------- Approve / Reject actions ---------

    def approve_selected(self):
        # NEW: operate at service-name level
        ids = self._get_all_ids_for_selected_service_names()
        if not ids:
            QMessageBox.information(self, "No selection", "Please select one or more services to approve.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm approve",
            f"Approve {len(ids)} pending service record(s) for the selected service name(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.btn_approve.setEnabled(False)
        try:
            ok = update_service_status(ids, "approved")
            if ok:
                QMessageBox.information(
                    self,
                    "Approved",
                    f"Approved {len(ids)} service record(s) (all matching service names)."
                )
                self.services_updated.emit()
            else:
                QMessageBox.warning(self, "Partial failure", "Could not approve all services (check logs).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to approve services:\n{e}")
            print("Error approving services:", e)
        finally:
            self.refresh_data()

    def reject_selected(self):
        # NEW: operate at service-name level
        ids = self._get_all_ids_for_selected_service_names()
        if not ids:
            QMessageBox.information(self, "No selection", "Please select one or more services to reject.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm reject",
            f"Reject {len(ids)} pending service record(s) for the selected service name(s)?\n\n"
            f"This can be undone later by re-approving.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.btn_reject.setEnabled(False)
        try:
            ok = update_service_status(ids, "rejected")
            if ok:
                QMessageBox.information(
                    self,
                    "Rejected",
                    f"Rejected {len(ids)} service record(s) (all matching service names)."
                )
                self.services_updated.emit()
            else:
                QMessageBox.warning(self, "Partial failure", "Could not reject all services (check logs).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reject services:\n{e}")
            print("Error rejecting services:", e)
        finally:
            self.refresh_data()
