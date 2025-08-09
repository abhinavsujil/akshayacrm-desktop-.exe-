from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from gui.admin_panel.admin_dashboard import AdminDashboard  # import your dashboard


class AdminPanel(QWidget):
    def __init__(self, back_callback, stacked_widget):
        super().__init__()
        self.back_callback = back_callback
        self.stacked_widget = stacked_widget  # QStackedWidget instance
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #f8fafc;")

        title = QLabel("👨‍💼 Admin Login")
        title.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1e293b; margin-bottom: 20px;")
        layout.addWidget(title)

        self.admin_id_input = QLineEdit()
        self.admin_id_input.setPlaceholderText("Enter Admin ID")
        self.admin_id_input.setStyleSheet(self.input_style())
        layout.addWidget(self.admin_id_input)

        self.admin_pass_input = QLineEdit()
        self.admin_pass_input.setPlaceholderText("Enter Password")
        self.admin_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_pass_input.setStyleSheet(self.input_style())
        layout.addWidget(self.admin_pass_input)

        login_btn = QPushButton("🔐 Login")
        login_btn.clicked.connect(self.validate_login)
        login_btn.setStyleSheet(self.primary_button_style())
        layout.addWidget(login_btn)

        back_btn = QPushButton("← Back to Home")
        back_btn.clicked.connect(self.back_callback)
        back_btn.setStyleSheet(self.link_button_style())
        layout.addWidget(back_btn)

    def input_style(self):
        return """
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
        """

    def primary_button_style(self):
        return """
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
        """

    def link_button_style(self):
        return """
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
        """

    def validate_login(self):
        user = self.admin_id_input.text().strip()
        pwd = self.admin_pass_input.text().strip()

        # Replace this check with supabase lookup for production
        if user == "admin" and pwd == "admin123":
            # Show visible welcome message
            msg = QMessageBox(self)
            msg.setWindowTitle("Login Successful")
            msg.setText(f"<b>Welcome {user}!</b>")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()

            # Move to dashboard (add to stacked widget)
            dashboard = AdminDashboard(admin_name=user)
            # Avoid adding duplicate dashboards
            # check if widget already in stack
            for i in range(self.stacked_widget.count()):
                if self.stacked_widget.widget(i).__class__ is AdminDashboard:
                    self.stacked_widget.setCurrentIndex(i)
                    return

            self.stacked_widget.addWidget(dashboard)
            self.stacked_widget.setCurrentWidget(dashboard)
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("Login Failed")
            msg.setText("<b>Invalid credentials</b>")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
