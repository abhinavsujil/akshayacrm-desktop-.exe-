from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class AdminDashboard(QWidget):
    def __init__(self, admin_name="Admin"):
        super().__init__()
        self.admin_name = admin_name
        self.setWindowTitle("Admin Dashboard")
        self.setMinimumSize(1200, 700)

        # try to load the qss, but don't crash if missing
        try:
            with open("gui/admin_panel/style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception:
            # fallback style (keeps it visually consistent)
            self.setStyleSheet("""
                QWidget { background-color: #f0f4fb; color: #1e293b; font-family: 'Segoe UI', sans-serif; }
                QFrame#sidebarFrame { background-color: white; border-right: 1px solid #e2e8f0; min-width: 220px; }
                QLabel { font-size: 14px; }
                QPushButton#sidebarButton { background: transparent; text-align: left; padding: 10px; border: none; }
                QFrame#statCard { background: white; border-radius: 8px; padding: 12px; border: 1px solid #e6eefc; }
            """)

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Sidebar
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(12, 12, 12, 12)
        sidebar.setSpacing(6)

        title = QLabel("⚙️ Admin Panel")
        title.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar.addWidget(title)

        btn_dashboard = QPushButton("📊 Dashboard")
        btn_logs = QPushButton("📜 View Logs")
        btn_services = QPushButton("🛠 Verify Services")
        btn_logout = QPushButton("🚪 Logout")

        for btn in [btn_dashboard, btn_logs, btn_services, btn_logout]:
            btn.setObjectName("sidebarButton")
            sidebar.addWidget(btn)

        sidebar.addStretch()

        sidebar_frame = QFrame()
        sidebar_frame.setLayout(sidebar)
        sidebar_frame.setObjectName("sidebarFrame")

        # Main content area
        content_layout = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        header_title = QLabel("Welcome, " + self.admin_name)
        header_title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        header.addWidget(header_title)
        header.addStretch()
        content_layout.addLayout(header)

        # Stats section
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(self.create_stat_card("Total Logs", "152"))
        stats_layout.addWidget(self.create_stat_card("Pending Verifications", "8"))
        stats_layout.addWidget(self.create_stat_card("Total Staff", "25"))
        content_layout.addLayout(stats_layout)

        # Table for logs (placeholder)
        table = QTableWidget(5, 3)
        table.setHorizontalHeaderLabels(["Log ID", "Customer Phone", "Status"])
        for row in range(5):
            table.setItem(row, 0, QTableWidgetItem(f"LOG-{row+1}"))
            table.setItem(row, 1, QTableWidgetItem(f"+91 98765432{row}"))
            table.setItem(row, 2, QTableWidgetItem("Pending" if row % 2 == 0 else "Completed"))
        content_layout.addWidget(table)

        # Combine sidebar and content
        main_layout.addWidget(sidebar_frame)
        main_layout.addLayout(content_layout, stretch=1)

    def create_stat_card(self, title, value):
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 12))

        value_label = QLabel(value)
        value_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #2563eb;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card
