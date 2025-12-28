# gui/admin_panel/admin_dashboard.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, date
import csv
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QDate

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QToolTip,
    QDateEdit,
    QFormLayout,
)
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QPainterPath

from gui.admin_panel.view_logs import ViewLogsDialog
from gui.admin_panel.verify_services import VerifyServicesDialog
from gui.admin_panel.manage_staff import ManageStaffDialog
from gui.admin_panel.manage_admins import ManageAdminsDialog
from supabase_utils import get_dashboard_stats, get_all_logs_with_services


# ------------------------------------------------------------------ #
# Activity line chart
# ------------------------------------------------------------------ #
class ActivityLineChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: list[tuple[str, float]] = []
        self.points: list[tuple[float, float, str, float]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(180)

    def set_data(self, data: list[tuple[str, float]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        self.points.clear()

        if not self.data:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Inter", 10))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "No activity for the selected range",
            )
            return

        margin_left = 40
        margin_right = 10
        margin_top = 10
        margin_bottom = 30

        chart_rect = QRectF(
            rect.left() + margin_left,
            rect.top() + margin_top,
            rect.width() - margin_left - margin_right,
            rect.height() - margin_top - margin_bottom,
        )

        axis_pen = QPen(QColor("#e2e8f0"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(
            int(chart_rect.left()),
            int(chart_rect.bottom()),
            int(chart_rect.right()),
            int(chart_rect.bottom()),
        )
        painter.drawLine(
            int(chart_rect.left()),
            int(chart_rect.top()),
            int(chart_rect.left()),
            int(chart_rect.bottom()),
        )

        values = [v for _, v in self.data]
        max_val = max(values) or 1.0
        count = len(self.data)
        step_x = chart_rect.width() if count == 1 else chart_rect.width() / max(count - 1, 1)

        for i, (label, val) in enumerate(self.data):
            x = float(chart_rect.left() + i * step_x)
            y = float(chart_rect.bottom() - (val / max_val) * chart_rect.height())
            self.points.append((x, y, label, val))

        if len(self.points) == 1:
            x, y, _, _ = self.points[0]
            painter.setBrush(QColor("#2563eb"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
        else:
            path = QPainterPath()
            first_x, _, _, _ = self.points[0]
            last_x, _, _, _ = self.points[-1]
            path.moveTo(first_x, chart_rect.bottom())
            for x, y, _, _ in self.points:
                path.lineTo(x, y)
            path.lineTo(last_x, chart_rect.bottom())
            path.closeSubpath()

            painter.setBrush(QColor("#bfdbfe"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

            painter.setPen(QPen(QColor("#2563eb"), 2))
            for i in range(len(self.points) - 1):
                x1, y1, _, _ = self.points[i]
                x2, y2, _, _ = self.points[i + 1]
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            painter.setBrush(QColor("#2563eb"))
            painter.setPen(Qt.PenStyle.NoPen)
            for x, y, _, _ in self.points:
                painter.drawEllipse(QRectF(x - 3, y - 3, 6, 6))

        painter.setFont(QFont("Inter", 9))
        painter.setPen(QColor("#475569"))
        fm = painter.fontMetrics()
        for i, (label, _) in enumerate(self.data):
            x = chart_rect.left() + (step_x * i)
            text_width = fm.horizontalAdvance(label)
            tx = int(x - text_width / 2)
            ty = int(chart_rect.bottom() + fm.height())
            painter.drawText(tx, ty, label)

    def mouseMoveEvent(self, event):
        if not self.points:
            return

        pos = event.position()
        px = pos.x()
        py = pos.y()
        closest = None
        min_dist_sq = 60

        for x, y, label, value in self.points:
            dx = px - x
            dy = py - y
            dist_sq = dx * dx + dy * dy
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest = (label, value)

        if closest:
            label, value = closest
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{label}: {int(value)} logs",
                self,
            )
        else:
            QToolTip.hideText()


# ------------------------------------------------------------------ #
# Service mix donut chart
# ------------------------------------------------------------------ #
class ServiceMixPieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: list[tuple[str, float]] = []
        self.slices: list[dict] = []
        self.inner_radius = 0.0
        self.setMouseTracking(True)
        self.setMinimumHeight(220)

    def set_data(self, data: list[tuple[str, float]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        self.slices.clear()

        if not self.data:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Inter", 10))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "No services for this range",
            )
            return

        total = sum(v for _, v in self.data) or 1.0

        colors = [
            "#2563eb",
            "#10b981",
            "#f59e0b",
            "#8b5cf6",
            "#ec4899",
            "#0ea5e9",
            "#a3e635",
        ]

        margin = 16
        chart_size = min(rect.width() * 0.5, rect.height()) - 2 * margin
        if chart_size < 80:
            chart_size = 80

        center_x = rect.left() + margin + chart_size / 2
        center_y = rect.center().y()
        outer_rect = QRectF(
            center_x - chart_size / 2,
            center_y - chart_size / 2,
            chart_size,
            chart_size,
        )

        start_angle = 0.0
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (label, value) in enumerate(self.data):
            ratio = value / total
            span_angle = ratio * 360.0
            color = QColor(colors[i % len(colors)])
            painter.setBrush(color)
            painter.drawPie(
                outer_rect,
                int(start_angle * 16),
                int(span_angle * 16),
            )

            self.slices.append(
                {
                    "start": start_angle,
                    "span": span_angle,
                    "label": label,
                    "value": value,
                    "color": color,
                    "center_x": center_x,
                    "center_y": center_y,
                    "outer_r": chart_size / 2,
                }
            )

            start_angle += span_angle

        inner_radius = chart_size * 0.55
        self.inner_radius = inner_radius
        inner_rect = QRectF(
            center_x - inner_radius / 2,
            center_y - inner_radius / 2,
            inner_radius,
            inner_radius,
        )
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(inner_rect)

        legend_x = int(outer_rect.right() + 24)
        legend_y = int(rect.top() + margin)
        painter.setFont(QFont("Inter", 10))
        fm = painter.fontMetrics()

        for i, (label, value) in enumerate(self.data):
            color = QColor(colors[i % len(colors)])

            box_size = 10
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(legend_x, legend_y + 3, box_size, box_size)

            painter.setPen(QColor("#0f172a"))
            text = f"{label} – {int(value)}"
            painter.drawText(
                legend_x + box_size + 8,
                legend_y + fm.ascent() + 2,
                text,
            )
            legend_y += fm.height() + 6

    def mouseMoveEvent(self, event):
        if not self.slices:
            return

        import math

        pos = event.position()
        px = pos.x()
        py = pos.y()

        hovered = None
        for sl in self.slices:
            cx = sl["center_x"]
            cy = sl["center_y"]
            dx = px - cx
            dy = py - cy
            r = (dx * dx + dy * dy) ** 0.5

            if r > sl["outer_r"] or r < self.inner_radius / 2:
                continue

            angle = math.degrees(math.atan2(-dy, dx))
            if angle < 0:
                angle += 360.0

            start = sl["start"]
            end = start + sl["span"]
            if start <= angle <= end:
                hovered = sl
                break

        if hovered:
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{hovered['label']}: {int(hovered['value'])}",
                self,
            )
        else:
            QToolTip.hideText()


# ------------------------------------------------------------------ #
# Simple detail dialog for a single log
# ------------------------------------------------------------------ #
class LogDetailDialog(QDialog):
    def __init__(self, log: dict, services: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Details")
        self.setMinimumSize(500, 320)

        layout = QVBoxLayout(self)

        name = str(log.get("name") or "")
        phone = str(log.get("phone") or "")
        staff_id = str(log.get("staff_id") or "")
        remarks = str(log.get("remarks") or "")
        ts_raw = log.get("timestamp")
        try:
            dt = datetime.fromisoformat(str(ts_raw))
            ts = dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            ts = str(ts_raw)

        info = QLabel(
            f"<b>Customer:</b> {name}<br>"
            f"<b>Phone:</b> {phone}<br>"
            f"<b>Staff ID:</b> {staff_id}<br>"
            f"<b>Timestamp:</b> {ts}<br>"
            f"<b>Remarks:</b> {remarks or '-'}"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        table = QTableWidget(len(services), 3)
        table.setHorizontalHeaderLabels(["Service", "Amount (₹)", "Status"])


        for row, s in enumerate(services):
            svc = str(s.get("service") or "")
            amount = 0.0
            payments = s.get("payments") or []
            if isinstance(payments, dict):
                payments = [payments]
            if payments:
                for p in payments:
                    try:
                        a = float(p.get("amount") or 0)
                    except Exception:
                        a = 0.0
                    if a == 0:
                        try:
                            ba = float(p.get("base_amount") or 0)
                        except Exception:
                            ba = 0.0
                        try:
                            ch = float(p.get("service_charge") or 0)
                        except Exception:
                            ch = 0.0
                        a = ba + ch
                    amount += a
            else:
                try:
                    amount = float(s.get("amount") or 0)
                except Exception:
                    amount = 0.0

            status = str(s.get("status") or "")

            table.setItem(row, 0, QTableWidgetItem(svc))
            table.setItem(row, 1, QTableWidgetItem(str(int(amount))))
            table.setItem(row, 2, QTableWidgetItem(status))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# ------------------------------------------------------------------ #
# Admin Dashboard
# ------------------------------------------------------------------ #
class AdminDashboard(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self, admin_id: str, admin_name: str):
        """
        admin_id / admin_name MUST come from Supabase `admins` table.
        """
        super().__init__()
        self.admin_id = admin_id
        self.admin_name = admin_name

        self.setWindowTitle("Admin Dashboard")
        self.setMinimumSize(1200, 700)

        # main stat labels
        self.total_logs_value: QLabel | None = None
        self.pending_value: QLabel | None = None
        self.total_revenue_value: QLabel | None = None
        self.total_staff_value: QLabel | None = None
        self.total_revenue_breakdown: QLabel | None = None  # Base vs Charge line

        # revenue summary labels
        self.today_revenue_value: QLabel | None = None
        self.week_revenue_value: QLabel | None = None
        self.month_revenue_value: QLabel | None = None

        # top staff summary labels
        self.top_staff_name_label: QLabel | None = None
        self.top_staff_revenue_label: QLabel | None = None

        # table + filters
        self.table: QTableWidget | None = None
        self.search_input: QLineEdit | None = None
        self.status_filter: QComboBox | None = None
        self.staff_filter: QComboBox | None = None

        # export button
        self.export_button: QPushButton | None = None

        # charts
        self.activity_chart: ActivityLineChart | None = None
        self.activity_range_combo: QComboBox | None = None
        self.mix_chart: ServiceMixPieChart | None = None
        self.mix_range_combo: QComboBox | None = None
        self.mix_mode_combo: QComboBox | None = None

        # revenue filter combo (placed inside revenue card)
        self.revenue_range_combo: QComboBox | None = None

        # custom range stored as (start_date, end_date) (date objects) or None
        self.custom_range: tuple[date, date] | None = None

        # cached data from Supabase (all logs)
        self.logs_cache: list[dict] = []

        self._load_styles()
        self.init_ui()

        self.refresh_dashboard()

    # ------------------------------------------------------------------ #
    # Styles
    # ------------------------------------------------------------------ #
    def _load_styles(self):
        try:
            base_dir = Path(__file__).resolve().parent
            qss_path = base_dir / "style.qss"
            if qss_path.exists():
                with qss_path.open("r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                return
        except Exception:
            pass

        self.setStyleSheet(
            """
            QWidget {
                background-color: #f0f4fb;
                color: #1e293b;
                font-family: 'Segoe UI', sans-serif;
            }
            QFrame#sidebarFrame {
                background-color: #111827;
                border-right: 1px solid #1f2937;
                min-width: 220px;
            }
            QLabel {
                font-size: 14px;
            }
            QPushButton#sidebarButton {
                background: transparent;
                text-align: left;
                padding: 10px;
                border: none;
                color: #e5e7eb;
            }
            QPushButton#sidebarButton:hover {
                background-color: #1f2937;
            }
            QFrame#statCard {
                background: white;
                border-radius: 8px;
                padding: 16px;
                border: 1px solid #e5e7eb;
            }
            QFrame#revCard {
                background: white;
                border-radius: 8px;
                padding: 12px;
                border: 1px solid #e5e7eb;
            }
            QLineEdit#searchInput {
                background: white;
                border-radius: 8px;
                border: 1px solid #cbd5e1;
                padding: 6px 10px;
                font-size: 13px;
            }
            QComboBox#statusFilter, QComboBox#staffFilter {
                background: white;
                border-radius: 8px;
                border: 1px solid #cbd5e1;
                padding: 4px 8px;
                font-size: 13px;
            }
            QTableWidget {
                background: white;
                alternate-background-color: #f8fafc;
                gridline-color: #e2e8f0;
            }
            """
        )

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # ===== Sidebar =====
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        title = QLabel("⚙️ Admin Panel")
        title.setFont(QFont("Inter", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title)

        self.btn_dashboard = QPushButton("📊 Dashboard")
        self.btn_logs = QPushButton("📜 View Logs")
        self.btn_services = QPushButton("🛠 Verify Services")
        self.btn_staff = QPushButton("👥 Manage Staff")
        self.btn_admins = QPushButton("🛂 Manage Admins")
        self.btn_logout = QPushButton("🚪 Logout")

        for btn in [
            self.btn_dashboard,
            self.btn_logs,
            self.btn_services,
            self.btn_staff,
            self.btn_admins,
            self.btn_logout,
        ]:
            btn.setObjectName("sidebarButton")
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebarFrame")
        sidebar_frame.setLayout(sidebar_layout)

        self.btn_dashboard.clicked.connect(self.refresh_dashboard)
        self.btn_logs.clicked.connect(self.open_logs_dialog)
        self.btn_services.clicked.connect(self.open_verify_dialog)
        self.btn_staff.clicked.connect(self.open_manage_staff_dialog)
        self.btn_admins.clicked.connect(self.open_manage_admins_dialog)
        # IMPORTANT: emit a signal rather than close() when inside a QStackedWidget
        self.btn_logout.clicked.connect(self._on_logout_clicked)

        # ===== Main content =====
        content_layout = QVBoxLayout()

        header = QHBoxLayout()
        header_title = QLabel(f"Welcome, {self.admin_name}")
        header_title.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        header.addWidget(header_title)
        header.addStretch()
        content_layout.addLayout(header)

        # ---- Main stats ----
        stats_layout = QHBoxLayout()

        card_total, self.total_logs_value = self.create_stat_card("Total Logs", "0")
        card_pending, self.pending_value = self.create_stat_card("Pending Verifications", "0")

        # ---- Modified revenue card: includes an internal revenue_range_combo ----
        card_revenue, self.total_revenue_value = self.create_stat_card("Total Revenue (₹)", "0")

        # add a top row inside the revenue card to host the range combo (top-right)
        try:
            rev_layout: QVBoxLayout = card_revenue.layout()  # type: ignore
            rev_top_row = QHBoxLayout()
            rev_top_row.addStretch()

            self.revenue_range_combo = QComboBox()
            # add custom option
            self.revenue_range_combo.addItems(["This Month", "Today", "This Week", "All Time", "Custom Range..."])
            self.revenue_range_combo.setCurrentText("This Month")
            self.revenue_range_combo.setFixedWidth(140)
            # when changed, recalc revenue totals; handle custom selection
            self.revenue_range_combo.currentIndexChanged.connect(self._on_revenue_range_changed)

            rev_top_row.addWidget(QLabel("Range:"))
            rev_top_row.addSpacing(6)
            rev_top_row.addWidget(self.revenue_range_combo)

            rev_layout.insertLayout(0, rev_top_row)
        except Exception:
            # fallback in case layout insertion fails
            self.revenue_range_combo = None

        # add base/charge breakdown line inside revenue card
        try:
            rev_layout: QVBoxLayout = card_revenue.layout()  # type: ignore
            self.total_revenue_breakdown = QLabel("Base: ₹ 0 | Charge: ₹ 0")
            self.total_revenue_breakdown.setFont(QFont("Inter", 10))
            self.total_revenue_breakdown.setStyleSheet("color: #64748b;")
            rev_layout.addWidget(self.total_revenue_breakdown)
        except Exception:
            self.total_revenue_breakdown = None

        card_staff, self.total_staff_value = self.create_stat_card("Total Staff", "0")

        stats_layout.addWidget(card_total)
        stats_layout.addWidget(card_pending)
        stats_layout.addWidget(card_revenue)
        stats_layout.addWidget(card_staff)

        content_layout.addLayout(stats_layout)

        # ---- Revenue summary row ----
        rev_layout = QHBoxLayout()

        card_today, self.today_revenue_value = self.create_revenue_card("Today's Revenue", "0")
        card_week, self.week_revenue_value = self.create_revenue_card("This Week", "0")
        card_month, self.month_revenue_value = self.create_revenue_card("This Month", "0")
        card_top_staff, self.top_staff_name_label, self.top_staff_revenue_label = self.create_top_staff_card(
            "Top Staff (This Month)"
        )

        rev_layout.addWidget(card_today)
        rev_layout.addWidget(card_week)
        rev_layout.addWidget(card_month)
        rev_layout.addWidget(card_top_staff)

        content_layout.addLayout(rev_layout)

        # ---- Charts row ----
        charts_layout = QHBoxLayout()

        activity_card = QFrame()
        activity_card.setObjectName("statCard")
        activity_layout = QVBoxLayout(activity_card)
        activity_header = QHBoxLayout()
        activity_title = QLabel("Activity")
        activity_title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.activity_range_combo = QComboBox()
        # add custom option
        self.activity_range_combo.addItems(["Today", "Last 7 days", "This Month", "All Time", "Custom Range..."])
        self.activity_range_combo.currentIndexChanged.connect(self._on_activity_range_changed)
        activity_header.addWidget(activity_title)
        activity_header.addStretch()
        activity_header.addWidget(self.activity_range_combo)
        activity_layout.addLayout(activity_header)

        self.activity_chart = ActivityLineChart()
        activity_layout.addWidget(self.activity_chart)
        charts_layout.addWidget(activity_card, stretch=3)

        mix_card = QFrame()
        mix_card.setObjectName("statCard")
        mix_layout = QVBoxLayout(mix_card)
        mix_header = QHBoxLayout()
        mix_title = QLabel("Service Mix")
        mix_title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.mix_range_combo = QComboBox()
        self.mix_range_combo.addItems(["Today", "This Week", "This Month", "All Time", "Custom Range..."])
        self.mix_mode_combo = QComboBox()
        self.mix_mode_combo.addItems(["Total Amount (₹)", "Base Only (₹)", "Service Charge (₹)", "Count"])
        self.mix_range_combo.currentIndexChanged.connect(self._on_mix_range_changed)
        self.mix_mode_combo.currentIndexChanged.connect(self.update_service_mix_chart)

        mix_header.addWidget(mix_title)
        mix_header.addStretch()
        mix_header.addWidget(self.mix_range_combo)
        mix_header.addWidget(self.mix_mode_combo)
        mix_layout.addLayout(mix_header)

        self.mix_chart = ServiceMixPieChart()
        mix_layout.addWidget(self.mix_chart)
        charts_layout.addWidget(mix_card, stretch=2)

        content_layout.addLayout(charts_layout)

        # ---- Filters bar ----
        filters_layout = QHBoxLayout()

        search_label = QLabel("Filter:")
        search_label.setFont(QFont("Inter", 11))

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search by customer name or phone...")
        self.search_input.textChanged.connect(self.apply_filters)

        self.status_filter = QComboBox()
        self.status_filter.setObjectName("statusFilter")
        self.status_filter.addItems(["All Status", "Completed", "Pending"])
        self.status_filter.currentIndexChanged.connect(self.apply_filters)

        self.staff_filter = QComboBox()
        self.staff_filter.setObjectName("staffFilter")
        self.staff_filter.addItem("All Staff")
        self.staff_filter.currentIndexChanged.connect(self.staff_filter_changed)

        self.export_button = QPushButton("Export Visible (CSV)")
        self.export_button.clicked.connect(self.export_visible_to_csv)

        filters_layout.addWidget(search_label)
        filters_layout.addWidget(self.search_input, stretch=1)
        filters_layout.addSpacing(12)
        filters_layout.addWidget(self.status_filter)
        filters_layout.addSpacing(12)
        filters_layout.addWidget(self.staff_filter)
        filters_layout.addStretch()
        filters_layout.addWidget(self.export_button)

        content_layout.addLayout(filters_layout)

        # ---- Overview table ----
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "Customer Name", "Phone", "Status", "Staff ID"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.open_log_detail_from_row)
        content_layout.addWidget(self.table)

        main_layout.addWidget(sidebar_frame)
        main_layout.addLayout(content_layout, stretch=1)

    def create_stat_card(self, title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 12))

        value_label = QLabel(value)
        value_label.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #2563eb;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def create_revenue_card(self, title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("revCard")
        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 11))

        value_label = QLabel(value)
        value_label.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #16a34a;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def create_top_staff_card(self, title: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName("revCard")
        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 11))

        name_label = QLabel("—")
        name_label.setFont(QFont("Inter", 15, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #0f172a;")

        revenue_label = QLabel("No revenue yet.")
        revenue_label.setFont(QFont("Inter", 11))
        revenue_label.setStyleSheet("color: #64748b;")
        revenue_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(name_label)
        layout.addWidget(revenue_label)

        return card, name_label, revenue_label

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def format_timestamp(self, raw_ts) -> str:
        if not raw_ts:
            return ""
        try:
            dt = datetime.fromisoformat(str(raw_ts))
            return dt.strftime("%d %b, %I:%M %p")
        except Exception:
            return str(raw_ts)

    def current_staff_filter(self) -> str | None:
        if self.staff_filter:
            text = self.staff_filter.currentText()
            if text and text != "All Staff":
                return text
        return None

    def filtered_logs_for_analytics(self) -> list[dict]:
        staff = self.current_staff_filter()
        if not staff:
            return self.logs_cache
        result = []
        for item in self.logs_cache:
            log = item["log"]
            if str(log.get("staff_id") or "") == staff:
                result.append(item)
        return result

    def _sum_service_payments(self, service: dict) -> tuple[float, float, float]:
        total = 0.0
        base = 0.0
        charge = 0.0

        payments = service.get("payments") or []
        if isinstance(payments, dict):
            payments = [payments]

        if payments:
            for p in payments:
                try:
                    ba = float(p.get("base_amount") or 0)
                except Exception:
                    ba = 0.0
                try:
                    ch = float(p.get("service_charge") or 0)
                except Exception:
                    ch = 0.0
                try:
                    am = float(p.get("amount") or 0)
                except Exception:
                    am = 0.0
                if am == 0 and (ba or ch):
                    am = ba + ch

                base += ba
                charge += ch
                total += am
        else:
            try:
                am = float(service.get("amount") or 0)
            except Exception:
                am = 0.0
            total = am

        return total, base, charge

    # date-range utility
    def _range_for_name(self, name: str) -> tuple[date | None, date | None]:
        """Return (start_date, end_date) for the named range.
           None, None => All time.
        """
        today = date.today()
        if name == "Today":
            return today, today
        if name == "Last 7 days":
            start = today - timedelta(days=6)
            return start, today
        if name == "This Week":
            # Monday as start
            start = today - timedelta(days=today.weekday())
            return start, today
        if name == "This Month":
            start = today.replace(day=1)
            return start, today
        if name == "All Time":
            return None, None
        # Custom will be handled elsewhere
        return None, None

    def _ask_custom_date_range(self, parent=None) -> tuple[date, date] | None:
        """Show a small dialog with two QDateEdits and return (start, end) date objects or None if cancelled."""
        dlg = QDialog(parent or self)
        dlg.setWindowTitle("Select custom date range")
        form = QFormLayout(dlg)

        start_edit = QDateEdit()
        end_edit = QDateEdit()
        start_edit.setCalendarPopup(True)
        end_edit.setCalendarPopup(True)
        start_edit.setDate(QDate.currentDate())
        end_edit.setDate(QDate.currentDate())

        form.addRow("Start date:", start_edit)
        form.addRow("End date:", end_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        sd = start_edit.date().toPyDate()
        ed = end_edit.date().toPyDate()
        if sd > ed:
            # swap to keep start <= end
            sd, ed = ed, sd
        return sd, ed

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def refresh_dashboard(self):
        try:
            stats = get_dashboard_stats()
        except Exception:
            stats = {
                "total_logs": 0,
                "pending_verifications": 0,
                "total_revenue": 0,
                "total_staff": 0,
                "total_base": 0,
                "total_charge": 0,
            }

        if self.total_logs_value:
            self.total_logs_value.setText(str(stats.get("total_logs", 0)))
        if self.pending_value:
            self.pending_value.setText(str(stats.get("pending_verifications", 0)))
        if self.total_revenue_value:
            self.total_revenue_value.setText(str(stats.get("total_revenue", 0)))
        if self.total_staff_value:
            self.total_staff_value.setText(str(stats.get("total_staff", 0)))
        if self.total_revenue_breakdown:
            base = stats.get("total_base", 0)
            charge = stats.get("total_charge", 0)
            self.total_revenue_breakdown.setText(f"Base: ₹ {int(base)} | Charge: ₹ {int(charge)}")

        try:
            self.logs_cache = get_all_logs_with_services()
        except Exception:
            self.logs_cache = []

        self.refresh_staff_filter_options()
        # ensure revenue summary uses current revenue_range_combo
        self.update_revenue_summary()
        self.update_activity_chart()
        self.update_service_mix_chart()
        self.update_top_staff_summary()
        self.apply_filters()

    def refresh_staff_filter_options(self):
        if not self.staff_filter:
            return
        current = self.current_staff_filter()
        self.staff_filter.blockSignals(True)
        self.staff_filter.clear()
        self.staff_filter.addItem("All Staff")

        staff_ids = sorted(
            {str(item["log"].get("staff_id") or "") for item in self.logs_cache if item["log"].get("staff_id")}
        )
        for sid in staff_ids:
            self.staff_filter.addItem(sid)

        if current and current in staff_ids:
            index = self.staff_filter.findText(current)
            if index >= 0:
                self.staff_filter.setCurrentIndex(index)
        self.staff_filter.blockSignals(False)

    def staff_filter_changed(self):
        self.update_revenue_summary()
        self.update_activity_chart()
        self.update_service_mix_chart()
        self.apply_filters()

    # ---- range-change handlers that support custom selection ----
    def _on_activity_range_changed(self, idx=None):
        sel = self.activity_range_combo.currentText()
        if sel == "Custom Range...":
            picked = self._ask_custom_date_range()
            if picked:
                self.custom_range = picked
            else:
                # revert to previous safe value (Today)
                self.activity_range_combo.blockSignals(True)
                self.activity_range_combo.setCurrentText("Today")
                self.activity_range_combo.blockSignals(False)
                return
        # if selection changed and not custom, keep existing custom_range if user wants; otherwise leave as is
        self.update_activity_chart()

    def _on_mix_range_changed(self, idx=None):
        sel = self.mix_range_combo.currentText()
        if sel == "Custom Range...":
            picked = self._ask_custom_date_range()
            if picked:
                self.custom_range = picked
            else:
                self.mix_range_combo.blockSignals(True)
                self.mix_range_combo.setCurrentText("Today")
                self.mix_range_combo.blockSignals(False)
                return
        self.update_service_mix_chart()

    def _on_revenue_range_changed(self, idx=None):
        sel = self.revenue_range_combo.currentText() if self.revenue_range_combo else "This Month"
        if sel == "Custom Range...":
            picked = self._ask_custom_date_range()
            if picked:
                self.custom_range = picked
            else:
                # revert
                if self.revenue_range_combo:
                    self.revenue_range_combo.blockSignals(True)
                    self.revenue_range_combo.setCurrentText("This Month")
                    self.revenue_range_combo.blockSignals(False)
                return
        self.update_revenue_summary()

    # ------------------------------------------------------------------ #
    # Data computations and charts (updated to use start/end date range)
    # ------------------------------------------------------------------ #
    def update_revenue_summary(self):
        """
        Compute totals for Today / This Week / This Month (these three cards),
        and also compute the Total Revenue card based on the selected revenue_range_combo
        (This Month, Today, This Week, All Time, Custom Range...).
        """
        today_total = 0.0
        week_total = 0.0
        month_total = 0.0

        # totals for selected revenue card range
        range_total = 0.0
        range_base = 0.0
        range_charge = 0.0

        logs = self.filtered_logs_for_analytics()
        if not logs:
            for lbl in (self.today_revenue_value, self.week_revenue_value, self.month_revenue_value):
                if lbl:
                    lbl.setText("0")
            if self.total_revenue_value:
                self.total_revenue_value.setText("0")
            if self.total_revenue_breakdown:
                self.total_revenue_breakdown.setText("Base: ₹ 0 | Charge: ₹ 0")
            return

        now = datetime.now()
        today_date = now.date()
        iso = now.isocalendar()
        current_year = iso[0]
        current_week = iso[1]
        current_month = now.month

        # determine selected revenue range mode
        selected_range = "This Month"
        if self.revenue_range_combo:
            try:
                selected_range = self.revenue_range_combo.currentText() or "This Month"
            except Exception:
                selected_range = "This Month"

        # get date boundaries
        start_date: date | None
        end_date: date | None
        if selected_range == "Custom Range...":
            if self.custom_range:
                start_date, end_date = self.custom_range
            else:
                # fallback to this month
                start_date, end_date = self._range_for_name("This Month")
        else:
            start_date, end_date = self._range_for_name(selected_range)

        for item in logs:
            log = item["log"]
            services = item["services"]

            raw_ts = log.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(raw_ts))
            except Exception:
                continue

            log_date = dt.date()
            log_iso = dt.isocalendar()
            log_year = log_iso[0]
            log_week = log_iso[1]
            log_month = dt.month

            # per-service accumulation for the three summary cards
            for s in services:
                total, base, charge = self._sum_service_payments(s)
                if total <= 0:
                    continue

                if log_date == today_date:
                    today_total += total
                if log_year == current_year and log_week == current_week:
                    week_total += total
                if log_year == current_year and log_month == current_month:
                    month_total += total

                # include in selected range totals
                include_in_range = False
                if start_date is None and end_date is None:
                    include_in_range = True
                else:
                    if start_date <= log_date <= end_date:
                        include_in_range = True

                if include_in_range:
                    range_total += total
                    range_base += base
                    range_charge += charge

        # update small summary cards
        if self.today_revenue_value:
            self.today_revenue_value.setText(f"{int(today_total)}")
        if self.week_revenue_value:
            self.week_revenue_value.setText(f"{int(week_total)}")
        if self.month_revenue_value:
            self.month_revenue_value.setText(f"{int(month_total)}")

        # update the Total Revenue card according to the selected range
        if self.total_revenue_value:
            self.total_revenue_value.setText(f"{int(range_total)}")
        if self.total_revenue_breakdown:
            self.total_revenue_breakdown.setText(f"Base: ₹ {int(range_base)} | Charge: ₹ {int(range_charge)}")

    def update_activity_chart(self):
        if not self.activity_chart:
            return

        logs = self.filtered_logs_for_analytics()
        if not logs:
            self.activity_chart.set_data([])
            return

        mode = "Today"
        if self.activity_range_combo:
            mode = self.activity_range_combo.currentText() or "Today"

        # determine start/end
        if mode == "Custom Range...":
            if self.custom_range:
                start_date, end_date = self.custom_range
            else:
                start_date, end_date = self._range_for_name("Today")
        else:
            start_date, end_date = self._range_for_name(mode)

        # all-time
        if start_date is None and end_date is None:
            # choose a reasonable grouping: per day for last 30 days, else per month aggregated.
            # For simplicity, aggregate per day across all logs and sort by date.
            counts: dict[date, int] = {}
            for item in logs:
                log = item["log"]
                raw_ts = log.get("timestamp")
                try:
                    dt = datetime.fromisoformat(str(raw_ts))
                except Exception:
                    continue
                d = dt.date()
                counts[d] = counts.get(d, 0) + 1
            sorted_dates = sorted(counts.items())
            data = [(d.strftime("%d %b %Y"), v) for d, v in sorted_dates]
            self.activity_chart.set_data(data)
            return

        # if single day -> hourly
        days_span = (end_date - start_date).days
        if days_span == 0:
            counts: dict[int, int] = {}
            for item in logs:
                log = item["log"]
                raw_ts = log.get("timestamp")
                try:
                    dt = datetime.fromisoformat(str(raw_ts))
                except Exception:
                    continue
                if dt.date() != start_date:
                    continue
                h = dt.hour
                counts[h] = counts.get(h, 0) + 1
            sorted_hours = sorted(counts.items())
            data = [(f"{h:02d}", v) for h, v in sorted_hours]
            self.activity_chart.set_data(data)
            return

        # multi-day -> per-day counts
        counts: dict[date, int] = {}
        for item in logs:
            log = item["log"]
            raw_ts = log.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(raw_ts))
            except Exception:
                continue
            d = dt.date()
            if d < start_date or d > end_date:
                continue
            counts[d] = counts.get(d, 0) + 1
        sorted_dates = sorted(counts.items())
        data = [(d.strftime("%d %b"), v) for d, v in sorted_dates]
        self.activity_chart.set_data(data)

    def update_service_mix_chart(self):
        if not self.mix_chart:
            return

        logs = self.filtered_logs_for_analytics()
        if not logs:
            self.mix_chart.set_data([])
            return

        range_mode = "Today"
        mode = "Total Amount (₹)"
        if self.mix_range_combo:
            range_mode = self.mix_range_combo.currentText() or "Today"
        if self.mix_mode_combo:
            mode = self.mix_mode_combo.currentText() or "Total Amount (₹)"

        # determine start/end
        if range_mode == "Custom Range...":
            if self.custom_range:
                start_date, end_date = self.custom_range
            else:
                start_date, end_date = self._range_for_name("Today")
        else:
            start_date, end_date = self._range_for_name(range_mode)

        now = datetime.now()
        today = now.date()
        current_iso = now.isocalendar()
        current_year = current_iso[0]
        current_week = current_iso[1]
        current_month = now.month

        summary: dict[str, float] = {}

        for item in logs:
            log = item["log"]
            services = item["services"]

            raw_ts = log.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(raw_ts))
            except Exception:
                continue

            d = dt.date()

            include = False
            if start_date is None and end_date is None:
                include = True
            else:
                if start_date <= d <= end_date:
                    include = True

            if not include:
                continue

            for s in services:
                name = str(s.get("service") or "Unknown")

                total, base, charge = self._sum_service_payments(s)

                if mode == "Total Amount (₹)":
                    value = total
                elif mode == "Base Only (₹)":
                    value = base
                elif mode == "Service Charge (₹)":
                    value = charge
                else:  # Count
                    value = 1.0

                if value <= 0 and mode != "Count":
                    continue

                summary[name] = summary.get(name, 0.0) + value

        if not summary:
            self.mix_chart.set_data([])
            return

        items = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        max_services = 8
        items = items[:max_services]

        self.mix_chart.set_data(items)

    def update_top_staff_summary(self):
        if not (self.top_staff_name_label and self.top_staff_revenue_label):
            return

        if not self.logs_cache:
            self.top_staff_name_label.setText("—")
            self.top_staff_revenue_label.setText("No revenue yet.")
            return

        now = datetime.now()
        current_year = now.year
        current_month = now.month

        staff_totals: dict[str, float] = {}

        for item in self.logs_cache:
            log = item["log"]
            services = item["services"]

            staff_id = str(log.get("staff_id") or "")
            if not staff_id:
                continue

            raw_ts = log.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(raw_ts))
            except Exception:
                continue

            if dt.year != current_year or dt.month != current_month:
                continue

            for s in services:
                total, _, _ = self._sum_service_payments(s)
                if total <= 0:
                    continue
                staff_totals[staff_id] = staff_totals.get(staff_id, 0.0) + total

        if not staff_totals:
            self.top_staff_name_label.setText("—")
            self.top_staff_revenue_label.setText("No revenue this month yet.")
            return

        top_staff_id, top_revenue = max(staff_totals.items(), key=lambda kv: kv[1])
        self.top_staff_name_label.setText(str(top_staff_id))
        self.top_staff_revenue_label.setText(f"Revenue: ₹ {int(top_revenue)}")

    def apply_filters(self):
        if not self.table:
            return

        search_text = ""
        status_filter = "All Status"
        staff_filter = self.current_staff_filter()

        if self.search_input:
            search_text = self.search_input.text().strip().lower()
        if self.status_filter:
            status_filter = self.status_filter.currentText()

        self.table.setRowCount(0)

        for item in self.logs_cache:
            log = item["log"]
            services = item["services"]

            if staff_filter:
                if str(log.get("staff_id") or "") != staff_filter:
                    continue

            raw_ts = log.get("timestamp")
            ts = self.format_timestamp(raw_ts)
            name = str(log.get("name") or "")
            phone = str(log.get("phone") or "")
            staff_id = str(log.get("staff_id") or "")
            log_id = str(log.get("id") or "")

            status = "Completed"
            for s in services:
                if (s.get("status") or "").lower() == "pending":
                    status = "Pending"
                    break

            if search_text:
                if search_text not in name.lower() and search_text not in phone.lower():
                    continue

            if status_filter == "Completed" and status != "Completed":
                continue
            if status_filter == "Pending" and status != "Pending":
                continue

            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            ts_item = QTableWidgetItem(ts)
            name_item = QTableWidgetItem(name)
            phone_item = QTableWidgetItem(phone)

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if status == "Completed":
                status_item.setBackground(QColor("#bbf7d0"))
                status_item.setForeground(QColor("#166534"))
            else:
                status_item.setBackground(QColor("#fed7aa"))
                status_item.setForeground(QColor("#92400e"))

            staff_item = QTableWidgetItem(staff_id)

            ts_item.setData(Qt.ItemDataRole.UserRole, log_id)

            self.table.setItem(row_idx, 0, ts_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, phone_item)
            self.table.setItem(row_idx, 3, status_item)
            self.table.setItem(row_idx, 4, staff_item)

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export_visible_to_csv(self):
        if not self.table or self.table.rowCount() == 0:
            QMessageBox.information(self, "Export", "No rows to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            "e-worktrack-logs.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [
                    self.table.horizontalHeaderItem(c).text()
                    for c in range(self.table.columnCount())
                ]
                writer.writerow(headers)

                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

            QMessageBox.information(self, "Export", "CSV exported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))

    # ------------------------------------------------------------------ #
    # Row detail shortcut
    # ------------------------------------------------------------------ #
    def open_log_detail_from_row(self, item: QTableWidgetItem):
        row = item.row()
        ts_item = self.table.item(row, 0)
        if not ts_item:
            return

        log_id = ts_item.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        target = None
        for entry in self.logs_cache:
            log = entry["log"]
            if str(log.get("id") or "") == str(log_id):
                target = entry
                break

        if not target:
            return

        dlg = LogDetailDialog(target["log"], target["services"], self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Sidebar actions
    # ------------------------------------------------------------------ #
    def open_logs_dialog(self):
        dlg = ViewLogsDialog(self)
        dlg.exec()
        self.refresh_dashboard()

    def open_verify_dialog(self):
        dlg = VerifyServicesDialog(self)
        dlg.services_updated.connect(self.refresh_dashboard)
        dlg.exec()

    def open_manage_staff_dialog(self):
        dlg = ManageStaffDialog(self)
        dlg.exec()
        # staff count on top card may change
        self.refresh_dashboard()

    def open_manage_admins_dialog(self):
        dlg = ManageAdminsDialog(self)
        dlg.exec()
        # dashboard itself doesn’t depend on admin count, but refresh anyway
        self.refresh_dashboard()

    # ------------------------------------------------------------------ #
    # Logout: show light box then emit logout signal
    # ------------------------------------------------------------------ #
    def _on_logout_clicked(self):
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

    # ------------------------------------------------------------------ #
    # (Other methods remain identical: refresh_dashboard, apply_filters, charts, etc.)
    # ------------------------------------------------------------------ #
