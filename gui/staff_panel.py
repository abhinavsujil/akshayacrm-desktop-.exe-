# staff_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QStackedWidget
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from gui.staff_dashboard import StaffDashboard
from language.translator import Translator
from supabase_utils import supabase_get  # ✅ Supabase functions


class StaffPanel(QWidget):
    def __init__(self, back_callback, stack: QStackedWidget | None = None):
        """
        back_callback: callable to ask main window to go back to landing page
        stack: optional QStackedWidget instance (preferred). If provided, dashboards will be
               added to it instead of shown as top-level windows.
        """
        super().__init__()
        self.back_callback = back_callback
        self.stack = stack
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
        try:
            response = supabase_get("staff", filter_query)
        except Exception:
            response = None

        if response and getattr(response, "status_code", None) == 200:
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

                # open StaffDashboard — prefer embedding in provided QStackedWidget
                self.dashboard = StaffDashboard(staff_id=user, staff_name=staff_name, lang=lang)

                stack = self.stack
                if stack is not None:
                    # Add dashboard to the stack and show it
                    stack.addWidget(self.dashboard)
                    stack.setCurrentWidget(self.dashboard)

                    # When dashboard emits logout_requested, remove it and return to landing
                    try:
                        def on_logout_and_cleanup(d=self.dashboard, s=stack):
                            # switch to landing via back_callback (main)
                            try:
                                self.back_callback()
                            except Exception:
                                try:
                                    s.setCurrentIndex(0)
                                except Exception:
                                    pass
                            # remove and delete dashboard widget from stack
                            try:
                                s.removeWidget(d)
                                d.deleteLater()
                            except Exception:
                                try:
                                    d.close()
                                except Exception:
                                    pass

                        self.dashboard.logout_requested.connect(on_logout_and_cleanup)
                    except Exception:
                        pass
                else:
                    # fallback: show standalone window (rare). Still connect logout to close+call-back.
                    try:
                        def fallback_logout():
                            try:
                                self.back_callback()
                            except Exception:
                                pass
                            try:
                                self.dashboard.close()
                            except Exception:
                                pass
                        self.dashboard.logout_requested.connect(fallback_logout)
                    except Exception:
                        pass
                    self.dashboard.show()

                # If login panel is a top-level window, close it (if not inside stack).
                try:
                    if self.isWindow():
                        self.close()
                except Exception:
                    pass

            else:
                QMessageBox.warning(self, self.tr("Login Failed"), self.tr("Invalid ID or password."))
        else:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to connect to Supabase."))
