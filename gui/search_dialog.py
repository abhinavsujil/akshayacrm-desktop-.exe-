from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt
from supabase_utils import supabase_get
from urllib.parse import quote


class SearchDialog(QDialog):
    def __init__(self, staff_id, parent=None):
        super().__init__(parent)
        self.staff_id = staff_id
        self.setWindowTitle("🔍 Search Records")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
                color: #1e293b;
            }
            QLabel, QLineEdit {
                font-size: 14px;
                color: #1e293b;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1e40af;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 🔍 Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter customer name or phone number")
        self.input_field.setStyleSheet(
            "padding: 8px; border-radius: 8px; border: 1px solid #cbd5e1;")
        layout.addWidget(self.input_field)

        # 🔍 Search button
        search_btn = QPushButton("🔎 Search")
        search_btn.clicked.connect(self.perform_search)
        layout.addWidget(search_btn)

        # 🧾 Results area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.scroll.setWidget(self.results_widget)
        layout.addWidget(self.scroll)

        # ❌ Close
        close_btn = QPushButton("❌ Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def perform_search(self):
        search_term = self.input_field.text().strip()
        self.clear_results()

        if not search_term:
            self.results_layout.addWidget(QLabel("❗ Please enter a name or phone number."))
            return

        # 🔐 Filter query
        if search_term.isdigit():
            query = f"phone=eq.{search_term}&staff_id=eq.{self.staff_id}"
        else:
            query = f"name=ilike.*{search_term}*&staff_id=eq.{self.staff_id}"

        encoded_query = quote(query, safe="=&.*")
        response = supabase_get("logs", encoded_query)

        if response.status_code == 200:
            logs = response.json()
            if not logs:
                self.results_layout.addWidget(QLabel("❌ No records found."))
                return

            for log in logs:
                log_id = log['id']
                service_query = quote(f"log_id=eq.{log_id}", safe="=&.")
                services_resp = supabase_get("services", service_query)
                services = services_resp.json() if services_resp.status_code == 200 else []
                self.display_result(log, services)
        else:
            self.results_layout.addWidget(QLabel("❌ Failed to fetch records. Check RLS policy."))

    def clear_results(self):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def display_result(self, log, services):
        result_box = QTextEdit()
        result_box.setReadOnly(True)
        result_box.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            color: #1e293b;
            font-size: 14px;
            padding: 10px;
            border-radius: 8px;
        """)

        result_text = f"""
📌 Name: {log.get('name')}
📱 Phone: {log.get('phone')}
🕓 Date: {log.get('timestamp')}
📝 Remarks: {log.get('remarks')}\n
"""

        if not services:
            result_text += "• No services found.\n"
        else:
            for s in services:
                service_name = s.get('service', 'Unknown')
                billing = s.get('amount', '0')
                result_text += f"• {service_name} - ₹{billing}\n"

        result_box.setText(result_text.strip())
        self.results_layout.addWidget(result_box)
