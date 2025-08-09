from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from gui.staff_dashboard import StaffDashboard
from language.translator import Translator
from supabase_utils import supabase_get  # ✅ Supabase functions

class StaffPanel(QWidget):
    def __init__(self, back_callback):
        super().__init__()
        self.back_callback = back_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #f8fafc;")

        parent = self.parent()
        while parent:
            if hasattr(parent, 'eng_radio') and hasattr(parent, 'mal_radio'):
                lang = "English" if parent.eng_radio.isChecked() else "Malayalam"
                break
            parent = parent.parent()
        else:
            lang = "English"

        self.translator = Translator(lang)
        self.tr = self.translator.translate

        title = QLabel(self.tr("🧑‍💼 STAFF LOGIN"))
        title.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1e293b; margin-bottom: 20px;")
        layout.addWidget(title)

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(self.tr("ENTER STAFF ID"))
        self.id_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border-radius: 10px;
                border: 2px solid #cbd5e1;
                background-color: white;
                color: #1e293b;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
        """)
        layout.addWidget(self.id_input)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText(self.tr("ENTER PASSWORD"))
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border-radius: 10px;
                border: 2px solid #cbd5e1;
                background-color: white;
                color: #1e293b;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
        """)
        layout.addWidget(self.pass_input)

        login_btn = QPushButton(self.tr("🔐 LOGIN"))
        login_btn.clicked.connect(self.validate_login)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                padding: 12px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        layout.addWidget(login_btn)

        back_btn = QPushButton(self.tr("← BACK TO HOME"))
        back_btn.clicked.connect(self.back_callback)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #2563eb;
                font-size: 13px;
                padding: 6px;
                border: none;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        layout.addWidget(back_btn)

    def validate_login(self):
        user = self.id_input.text().strip()
        pwd = self.pass_input.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, self.tr("Login Failed"), self.tr("Please enter both ID and password."))
            return

        filter_query = f"id=eq.{user}&password=eq.{pwd}"
        response = supabase_get("staff", filter_query)

        if response.status_code == 200:
            data = response.json()
            if data:
                staff = data[0]
                staff_name = staff.get("name", user)

                lang = "English"
                parent = self.parent()
                while parent:
                    if hasattr(parent, 'eng_radio') and hasattr(parent, 'mal_radio'):
                        lang = "English" if parent.eng_radio.isChecked() else "Malayalam"
                        break
                    parent = parent.parent()

                # ✅ Pass both staff_id and staff_name
                self.dashboard = StaffDashboard(staff_id=user, staff_name=staff_name, lang=lang)
                self.dashboard.show()
                self.close()
            else:
                QMessageBox.warning(self, self.tr("Login Failed"), self.tr("Invalid ID or password."))
        else:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to connect to Supabase."))
