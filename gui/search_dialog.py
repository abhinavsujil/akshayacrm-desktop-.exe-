# search_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QScrollArea, QWidget,
    QLabel, QTextEdit, QMessageBox, QHBoxLayout, QFileDialog, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QCursor
from supabase_utils import supabase_get
from urllib.parse import quote
import csv
from datetime import datetime

# Try to reuse LogDetailsDialog from recent_work for consistent UI.
# If it's not importable (module path / packaging differences), fall back to a compact local implementation.
try:
    from recent_work import LogDetailsDialog  # type: ignore
except Exception:
    LogDetailsDialog = None  # will be set to fallback below


# Fallback compact details dialog when recent_work.LogDetailsDialog is not available
class LocalLogDetailsDialog(QDialog):
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = record or {}
        self.setWindowTitle("Log Details")
        self.setMinimumSize(640, 420)
        self.setStyleSheet("""
            QDialog { background: #ffffff; font-family: 'Segoe UI', sans-serif; color: #0f172a; }
            QLabel#Title { font-size:18px; font-weight:700; color: #0f172a; }
            QLabel.field { color: #64748b; font-weight:600; min-width:130px; font-size: 14px; }
            QLabel.value { color: #0f172a; font-size: 14px; font-weight: 500; }
            QTextEdit { background: #fbfcff; border: 1px solid #e6eefc; border-radius:6px; padding:8px; }
            QLabel.chip { background:#eef2ff; border:1px solid #bfdbfe; border-radius:6px; padding:6px; font-size:13px; }
            QPushButton#closeBtn { background:#eff6ff; color:#1d4ed8; padding:6px 12px; border-radius:6px; border:1px solid #bfdbfe; font-weight: 600; }
            QPushButton#closeBtn:hover { background: #dbeafe; }
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QFrame#cont { background: transparent; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        title = QLabel("Log Details")
        title.setObjectName("Title")
        layout.addWidget(title)

        # Basic rows
        def add_row(label_text, value_text):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setProperty("class", "field")
            val = QLabel(value_text)
            val.setProperty("class", "value")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        ts = self._format_ts(self.record.get("timestamp"))
        add_row("Timestamp:", ts)
        add_row("Staff ID:", str(self.record.get("staff_id") or "—"))
        add_row("Customer Name:", str(self.record.get("name") or "—"))
        add_row("Phone:", str(self.record.get("phone") or "—"))
        add_row("Status:", str(self.record.get("status") or "Unknown").capitalize())

        layout.addSpacing(5)

        # Payments (if any)
        payments = self.record.get("payments") or []
        if payments:
            p_title = QLabel("Payments:")
            p_title.setProperty("class", "field")
            layout.addWidget(p_title)
            for p in payments:
                p_row = QHBoxLayout()
                p_row.setContentsMargins(130, 0, 0, 0) # Indent to align with values
                amt = p.get("amount") or 0
                base = p.get("base_amount") or 0
                ch = p.get("service_charge") or 0
                pm = p.get("payment_method") or "Unknown"
                p_label = QLabel(f"₹{int(float(amt or 0))} (base: ₹{int(float(base or 0))}, charge: ₹{int(float(ch or 0))}) — {pm.capitalize()}")
                p_label.setProperty("class", "value")
                p_row.addWidget(p_label)
                layout.addLayout(p_row)
        else:
            # show aggregated total_amount if provided
            if self.record.get("total_amount") is not None:
                add_row("Total Amount (₹):", str(self.record.get("total_amount")))

        layout.addSpacing(5)

        # Services list
        s_title = QLabel("Services:")
        s_title.setProperty("class", "field")
        layout.addWidget(s_title)
        services = self.record.get("services") or []
        payments = self.record.get("payments") or []

        payments_by_service = {}
        for p in payments:
            sid = p.get("service_id")
            if sid:
                payments_by_service[str(sid)] = p

        if not services:
             p_row = QHBoxLayout()
             p_row.setContentsMargins(130, 0, 0, 0)
             lbl = QLabel("—")
             lbl.setProperty("class", "value")
             p_row.addWidget(lbl)
             layout.addLayout(p_row)
        else:
            scr = QScrollArea()
            scr.setWidgetResizable(True)
            scr.setMaximumHeight(120) # Limit height for many services
            cont = QFrame()
            cont.setObjectName("cont")
            v = QVBoxLayout(cont)
            v.setContentsMargins(130, 0, 0, 0)
            v.setSpacing(5)
            for s in services:
                name = s.get("service") or "Unknown"
                sid = s.get("id")
                sid_key = str(sid) if sid is not None else None
                payment_for_service = payments_by_service.get(sid_key) if sid_key else None

                if payment_for_service:
                    amt = payment_for_service.get("amount") or 0
                    # base = payment_for_service.get("base_amount") or 0
                    # ch = payment_for_service.get("service_charge") or 0
                    amt_display = f"₹{int(float(amt or 0))}"
                else:
                    svc_amt = s.get("amount")
                    if svc_amt is None or svc_amt == 0:
                        amt_display = "No payment info"
                    else:
                        try:
                            amt_display = f"₹{int(float(svc_amt))}"
                        except Exception:
                            amt_display = str(svc_amt)

                st = s.get("status") or "Unknown"
                chip_text = f"{name} — {amt_display} ({st.capitalize()})"
                chip = QLabel(chip_text)
                # chip.setProperty("class", "chip") # Removed chip style for a cleaner list look in fallback
                chip.setProperty("class", "value")
                v.addWidget(chip)
            
            v.addStretch()
            scr.setWidget(cont)
            layout.addWidget(scr)

        layout.addSpacing(5)
        r_label = QLabel("Remarks:")
        r_label.setProperty("class", "field")
        layout.addWidget(r_label)
        remarks_val = str(self.record.get("remarks") or "—")
        remarks = QLabel(remarks_val)
        remarks.setWordWrap(True)
        remarks.setProperty("class", "value")
        if remarks_val != "—":
             remarks.setStyleSheet("background: #f1f5f9; padding: 8px; border-radius: 6px;")
        layout.addWidget(remarks)

        layout.addStretch()
        close = QPushButton("Close")
        close.setObjectName("closeBtn")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

    def _format_ts(self, raw):
        if not raw:
            return "—"
        try:
            dt = datetime.fromisoformat(str(raw)) if not isinstance(raw, datetime) else raw
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(raw)


# If import failed earlier use the local fallback
if LogDetailsDialog is None:
    LogDetailsDialog = LocalLogDetailsDialog  # type: ignore


class SearchDialog(QDialog):
    def __init__(self, staff_id, parent=None):
        super().__init__(parent)
        self.staff_id = staff_id
        self.setWindowTitle("Search Records")
        self.setMinimumSize(900, 600) # Increased size for table view
        # Updated global stylesheet for the dialog and its widgets
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f4f8; /* Light grey-blue background */
                font-family: 'Segoe UI', sans-serif;
                color: #1e293b;
            }
            QLabel {
                font-size: 14px;
                color: #1e293b;
                font-weight: 500;
            }
            QLabel#headerTitle {
                font-size: 20px;
                font-weight: 700;
                color: #1e293b;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                color: #1e293b;
            }
            QLineEdit:focus {
                border: 2px solid #06b6d4; /* Teal focus border */
                padding: 7px 11px;
            }
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                padding: 8px 16px;
                font-weight: 600;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                color: #1e293b;
                border-color: #94a3b8;
            }
            QPushButton#searchBtn {
                background-color: #06b6d4; /* Teal search button */
                color: white;
                border: none;
            }
            QPushButton#searchBtn:hover {
                background-color: #0891b2;
            }
             /* Table Styles */
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                gridline-color: #f1f5f9;
                outline: 0;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f1f5f9;
                color: #1e293b;
            }
            QTableWidget::item:selected {
                background-color: #f0f9ff; /* Light blue selection */
                color: #1e293b;
            }
             QHeaderView::section {
                background-color: #f8fafc;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 600;
                color: #64748b;
                font-size: 14px;
            }
            /* Scrollbar for table */
            QScrollBar:vertical { border: none; background: #f1f5f9; width: 10px; margin: 0; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #cbd5e1; min-height: 20px; border-radius: 5px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self.perform_search)

        self.results_cache = []  # store (log, services, payments) for export / details
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header Title and Close Button
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Search Records")
        title_lbl.setObjectName("headerTitle")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        
        # 'X' close icon button
        close_icon_btn = QPushButton("✕")
        close_icon_btn.setFixedSize(30, 30)
        close_icon_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Inline style to override general QPushButton styles for a clean icon look
        close_icon_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; color: #94a3b8; font-size: 20px; padding: 0; }
            QPushButton:hover { color: #475569; background: transparent; }
        """)
        close_icon_btn.clicked.connect(self.close)
        header_layout.addWidget(close_icon_btn)
        layout.addLayout(header_layout)

        # Search Bar Row
        search_row = QHBoxLayout()
        search_row.setSpacing(15)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Search by customer name, phone, or staff ID...")
        self.input_field.setFixedHeight(40) # Slightly taller for better look
        # Add a search icon to the leading position
        self.input_field.addAction(QIcon(":/icons/search.png"), QLineEdit.ActionPosition.LeadingPosition) # Placeholder for icon
        search_row.addWidget(self.input_field, stretch=1)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("searchBtn")
        search_btn.setFixedHeight(40)
        search_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Add a search icon to the button
        search_btn.setIcon(QIcon(":/icons/search_white.png")) # Placeholder for white icon
        search_btn.clicked.connect(lambda: self._debounce_timer.start())
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # --- Removed Filters Row (Date Range & Service Type) ---

        # Results Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Customer Name", "Phone", "Service", "Status", "Action"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setShowGrid(False)
        self.table.cellDoubleClicked.connect(self._on_table_double_click)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Timestamp
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed) # Action column fixed width
        hdr.resizeSection(5, 100)

        layout.addWidget(self.table, stretch=1)
        
        # Placeholder message for empty state
        self.empty_state_lbl = QLabel("Enter a search term to find records.")
        self.empty_state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_lbl.setStyleSheet("color: #94a3b8; font-size: 16px; margin-top: 50px;")
        # Initial state is empty, so show the label and hide the table
        self.table.setVisible(False)
        layout.addWidget(self.empty_state_lbl)


        # wire enter key to search (with debounce)
        self.input_field.returnPressed.connect(lambda: self._debounce_timer.start())
        
        # Focus the input field on open
        self.input_field.setFocus()


    def perform_search(self):
        search_term = self.input_field.text().strip()
        self.clear_results()

        if not search_term:
            self.empty_state_lbl.setText("❗ Please enter a search term.")
            self.table.setVisible(False)
            self.empty_state_lbl.setVisible(True)
            return

        self.empty_state_lbl.setText("Searching...")
        self.table.setVisible(False)
        self.empty_state_lbl.setVisible(True)
        QApplication.processEvents() # Force UI update

        # Build supabase filter: restrict by staff_id
        try:
            # Simple logic to guess if it's a phone number or name.
            # Can be improved with regex for more robust validation.
            if search_term.isdigit() and len(search_term) >= 4:
                query = f"phone=ilike.*{search_term}*&staff_id=eq.{self.staff_id}&order=timestamp.desc"
            else:
                # Search by name (case-insensitive partial match)
                query = f"name=ilike.*{search_term}*&staff_id=eq.{self.staff_id}&order=timestamp.desc"

            encoded_query = quote(query, safe="=&.*")
            select = "*,services(*),payments(*)"
            resp = supabase_get("logs", filter_query=encoded_query, select=select)
        except Exception as e:
            resp = None
            print("Search request failed:", e)

        if not resp or getattr(resp, "status_code", None) != 200:
            self.empty_state_lbl.setText("❌ Failed to fetch records. Please check your connection.")
            return

        logs = resp.json() or []
        if not logs:
            self.empty_state_lbl.setText("❌ No matching records found.")
            return

        # Clear cache and populate results table
        self.results_cache = []
        self.table.setVisible(True)
        self.empty_state_lbl.setVisible(False)
        
        for log in logs:
            services = log.get("services") or []
            payments = log.get("payments") or []
            self.results_cache.append((log, services, payments))
            self._add_result_row(log, services)

    def clear_results(self):
        self.table.setRowCount(0)
        self.results_cache = []

    def _add_result_row(self, log, services):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        # 0: Timestamp
        ts_raw = log.get('timestamp')
        ts_str = "—"
        if ts_raw:
            try:
                ts_str = datetime.fromisoformat(str(ts_raw)).strftime("%Y-%m-%d %I:%M %p")
            except:
                ts_str = str(ts_raw)
        self.table.setItem(row_idx, 0, QTableWidgetItem(ts_str))

        # 1: Customer Name
        self.table.setItem(row_idx, 1, QTableWidgetItem(str(log.get('name') or "—")))

        # 2: Phone
        self.table.setItem(row_idx, 2, QTableWidgetItem(str(log.get('phone') or "—")))

        # 3: Service (Summary)
        service_names = [s.get('service') or "Unknown" for s in services]
        service_summary = ", ".join(service_names) if service_names else "—"
        svc_item = QTableWidgetItem(service_summary)
        svc_item.setToolTip(service_summary) # Full list in tooltip
        self.table.setItem(row_idx, 3, svc_item)

        # 4: Status
        # Determine an overall status. For simplicity, let's take the status of the first service, 
        # or the log's own status if available.
        status = "Unknown"
        if services:
             status = str(services[0].get('status') or "Unknown").capitalize()
        elif log.get('status'):
             status = str(log.get('status')).capitalize()
        
        status_lbl = QLabel(status)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Basic status coloring based on text
        if status == "Completed" or status == "Approved":
            bg, text_c = "#dcfce7", "#166534" # Green
        elif status == "Pending":
            bg, text_c = "#fef9c3", "#854d0e" # Yellow
        elif status == "Rejected":
            bg, text_c = "#fee2e2", "#991b1b" # Red
        else:
            bg, text_c = "#f1f5f9", "#475569" # Grey
            
        status_lbl.setStyleSheet(f"background-color: {bg}; color: {text_c}; border-radius: 12px; padding: 4px 8px; font-weight: 600; font-size: 12px;")
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 8, 0, 8) # Center vertically
        status_layout.addWidget(status_lbl)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row_idx, 4, status_container)


        # 5: Action Button
        view_btn = QPushButton("View")
        view_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Use lambda to capture current row index for the button click handler
        view_btn.clicked.connect(lambda checked, r=row_idx: self._on_view_clicked(r))
        
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 6, 0, 6)
        btn_layout.addWidget(view_btn)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row_idx, 5, btn_container)
        

    def _on_view_clicked(self, row_idx):
        self._open_details_for_row(row_idx)

    def _on_table_double_click(self, row_idx, col_idx):
        # Avoid double-opening if the 'View' button column was clicked
        if col_idx != 5:
            self._open_details_for_row(row_idx)

    def _open_details_for_row(self, row_idx):
        if 0 <= row_idx < len(self.results_cache):
            log, services, payments = self.results_cache[row_idx]
            self._open_details(log, services, payments)

    def _open_details(self, log, services, payments):
        rec = {
            "timestamp": log.get("timestamp"),
            "staff_id": log.get("staff_id"),
            "name": log.get("name"),
            "phone": log.get("phone"),
            "remarks": log.get("remarks"),
            "services": services,
            "payments": payments,
            "status": log.get("status") or ""
        }
        # Use the imported or fallback LogDetailsDialog
        dlg = LogDetailsDialog(rec, self)
        dlg.exec()

    def export_csv(self):
        # This function is not present in the UI design but is kept from the original code.
        # You might want to add an "Export" button back to the UI if needed.
        if not self.results_cache:
            QMessageBox.information(self, "No data", "No rows to export.")
            return
        default = f"search_results_{self.staff_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", default, "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Timestamp", "Staff ID", "Customer Name", "Phone", "Services/Payments", "Total Amount (₹)", "Remarks"])
                for log, services, payments in self.results_cache:
                    ts = log.get("timestamp") or ""
                    display = ""
                    total = 0
                    if payments:
                        parts = []
                        for p in payments:
                            amt = p.get("amount") or 0
                            base = p.get("base_amount") or 0
                            charge = p.get("service_charge") or 0
                            pm = p.get("payment_method") or ""
                            parts.append(f"Payment: ₹{int(float(amt or 0))} (b:{int(float(base or 0))}, c:{int(float(charge or 0))}) {pm}")
                            total += float(amt or 0)
                        display = " | ".join(parts)
                    else:
                        parts = []
                        for s in services:
                            name = s.get("service") or ""
                            amt = s.get("amount") or 0
                            st = s.get("status") or ""
                            parts.append(f"{name}:₹{int(float(amt or 0))}({st})")
                            total += float(amt or 0)
                        display = "; ".join(parts)
                    w.writerow([ts, log.get("staff_id",""), log.get("name",""), log.get("phone",""), display, int(total), log.get("remarks","")])
            QMessageBox.information(self, "Exported", f"CSV exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", f"Could not export CSV:\n{e}")

# Need to import QApplication and QCursor for the new UI elements
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor