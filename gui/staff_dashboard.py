from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QTextEdit, QMenu, QToolButton, QMessageBox,
    QSizePolicy, QScrollArea, QApplication
)
from PyQt6.QtGui import QFont, QIntValidator
from PyQt6.QtCore import Qt
from language.translator import Translator
from supabase_utils import supabase_post
from datetime import datetime
import uuid
import sys


class StaffDashboard(QWidget):
    def __init__(self, staff_id, staff_name="Staff", lang="English"):
        super().__init__()
        self.staff_id = staff_id
        self.staff_name = staff_name
        self.lang = lang
        self.setWindowTitle("Staff Dashboard")
        self.setMinimumSize(800, 600)
        self.services_db = ["Income Certificate", "Aadhaar Update", "Ration Card", "Birth Certificate"]
        self.service_fields = []

        self.translator = Translator(lang)
        self.tr = self.translator.translate

        self.setStyleSheet("""
            QWidget {
                background-color: #f0f4fb;
                font-family: 'Segoe UI', sans-serif;
                color: #1e293b;
            }
            QLabel {
                font-size: 15px;
                font-weight: 500;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                color: #1e293b;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 2px solid #2563eb;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.init_ui()

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        layout.addLayout(self.build_header())
        self.form_layout = QVBoxLayout()
        layout.addLayout(self.form_layout)

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        self.build_form_section()

    def build_header(self):
        layout = QHBoxLayout()
        layout.setSpacing(15)

        self.menu_btn = QToolButton()
        self.menu_btn.setText("☰")
        self.menu_btn.setStyleSheet("font-size: 24px; padding: 4px;")
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu()
        menu.addAction(self.tr("📂 Recent Work"), self.show_recent_work)
        menu.addAction(self.tr("🔎 Search Records"), self.show_search_dialog)
        menu.addAction(self.tr("🖨️ Print"), self.handle_print)
        menu.addSeparator()
        menu.addAction(self.tr("🚪 Logout"), self.handle_logout)
        self.menu_btn.setMenu(menu)

        layout.addWidget(self.menu_btn)
        layout.addStretch()

        welcome = QLabel(f"👋 {self.tr('Hello')} {self.staff_name}")
        welcome.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(welcome)

        lang_label = QLabel(self.tr("🌐 Language:"))
        lang_dropdown = QComboBox()
        lang_dropdown.addItems(["English", "മലയാളം"])
        lang_dropdown.setCurrentText(self.lang)
        lang_dropdown.setFixedWidth(130)

        layout.addSpacing(10)
        layout.addWidget(lang_label)
        layout.addWidget(lang_dropdown)

        return layout

    def build_form_section(self):
        layout = self.form_layout

        def add_label_input(label_text, widget):
            label = QLabel(label_text)
            layout.addWidget(label)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(widget)

        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText(self.tr("Enter Name"))
        add_label_input(self.tr("👤 Customer Name:"), self.customer_name_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(self.tr("Enter Phone Number"))
        self.phone_input.setInputMask("0000000000")
        add_label_input(self.tr("📞 Phone Number:"), self.phone_input)

        self.services_container = QVBoxLayout()
        layout.addWidget(QLabel(self.tr("📄 Services & Billing:")))
        layout.addLayout(self.services_container)

        self.add_service_entry()

        add_service_btn = QPushButton(self.tr("➕ Add More Service"))
        add_service_btn.clicked.connect(self.add_service_entry)
        layout.addWidget(add_service_btn)

        self.remarks_input = QTextEdit()
        self.remarks_input.setPlaceholderText(self.tr("Eg: Customer brought old documents / Requested urgent service"))
        self.remarks_input.setMinimumHeight(100)
        add_label_input(self.tr("🗒️ Staff Remarks:"), self.remarks_input)

        submit_btn = QPushButton(self.tr("Submit"))
        submit_btn.clicked.connect(self.handle_submit)
        layout.addSpacing(15)
        layout.addWidget(submit_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def add_service_entry(self):
        hbox = QHBoxLayout()

        service_input = QComboBox()
        service_input.setEditable(True)
        service_input.addItems(sorted(set(self.services_db)))
        service_input.lineEdit().editingFinished.connect(lambda: self.check_service_validity(service_input))
        service_input.setFixedWidth(300)

        amount_input = QLineEdit()
        amount_input.setPlaceholderText("₹")
        amount_input.setValidator(QIntValidator())
        amount_input.setFixedWidth(100)

        hbox.addWidget(service_input)
        hbox.addWidget(amount_input)

        self.services_container.addLayout(hbox)
        self.service_fields.append((service_input, amount_input))

    def check_service_validity(self, combo):
        service = combo.currentText().strip()
        if service and service not in self.services_db:
            QMessageBox.information(self, self.tr("New Service"), self.tr(f"'{service}' will be flagged for admin verification."))
            self.services_db.append(service)
            for s, _ in self.service_fields:
                s.clear()
                s.addItems(sorted(set(self.services_db)))
                s.setCurrentText(service)

    def handle_submit(self):
        name = self.customer_name_input.text().strip()
        phone = self.phone_input.text().strip()
        remarks = self.remarks_input.toPlainText().strip()

        if not name or not phone:
            QMessageBox.warning(self, self.tr("Missing Info"), self.tr("Please fill in all required fields."))
            return

        services_to_log = []
        for service_input, amount_input in self.service_fields:
            service = service_input.currentText().strip()
            amount = amount_input.text().strip()
            if service and amount:
                services_to_log.append((service, amount))
            else:
                QMessageBox.warning(self, self.tr("Missing Info"), self.tr("Please fill in all service fields."))
                return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_id = str(uuid.uuid4())

        log_data = {
            "id": log_id,
            "staff_id": self.staff_id,
            "name": name,
            "phone": phone,
            "remarks": remarks,
            "timestamp": timestamp
        }

        log_response = supabase_post("logs", log_data)

        if log_response.status_code == 201:
            for service, amount in services_to_log:
                service_data = {
                    "log_id": log_id,
                    "service": service,  # ✅ FIXED column name
                    "amount": amount
                }
                supabase_post("services", service_data)

            QMessageBox.information(self, self.tr("Success"), self.tr("✅ Data submitted successfully!"))
            self.clear_form()
        else:
            QMessageBox.critical(self, self.tr("Error"), self.tr("❌ Failed to save to Supabase:\n") + log_response.text)

    def clear_form(self):
        self.customer_name_input.clear()
        self.phone_input.clear()
        self.remarks_input.clear()
        for s_input, a_input in self.service_fields:
            s_input.setCurrentIndex(0)
            a_input.clear()

    def handle_logout(self):
        QMessageBox.information(self, self.tr("Logout"), self.tr("👋 You have been logged out."))
        self.close()

    def show_recent_work(self):
        QMessageBox.information(self, self.tr("Recent Work"), self.tr("📂 This feature is under development."))

    def handle_print(self):
        QMessageBox.information(self, self.tr("Print"), self.tr("🖨️ This will trigger the print dialog."))

    def show_search_dialog(self):
        from gui.search_dialog import SearchDialog
        self.search_dialog = SearchDialog(self.staff_id, self)
        self.search_dialog.exec()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = StaffDashboard(staff_id="s001", staff_name="Abhinav", lang="English")
    win.show()
    sys.exit(app.exec())
