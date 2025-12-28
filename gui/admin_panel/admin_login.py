# gui/admin_panel/admin_login.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QStackedWidget
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from gui.admin_panel.admin_dashboard import AdminDashboard
from language.translator import Translator
from supabase_utils import supabase_get, SUPABASE_URL


class AdminLogin(QWidget):
    """
    Admin login screen:
      - Reads from Supabase `admins` table
      - Looks up by ID only
      - Compares password in Python
    """

    def __init__(self, back_callback, stack: QStackedWidget | None = None):
        super().__init__()
        self.back_callback = back_callback
        self.stack = stack

        self.translator: Translator | None = None
        self.tr = lambda x: x
        self.id_input: QLineEdit | None = None
        self.pass_input: QLineEdit | None = None

        self.init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #f8fafc;")

        # detect language from parent, same style as StaffPanel
        parent = self.parent()
        while parent:
            if hasattr(parent, "eng_radio") and hasattr(parent, "mal_radio"):
                lang = "English" if parent.eng_radio.isChecked() else "Malayalam"
                break
            parent = parent.parent()
        else:
            lang = "English"

        self.translator = Translator(lang)
        self.tr = self.translator.translate

        title = QLabel(self.tr("🛂 ADMIN LOGIN"))
        title.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1e293b; margin-bottom: 20px;")
        layout.addWidget(title)

        # Admin ID
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(self.tr("ENTER ADMIN ID"))
        self.id_input.setStyleSheet(
            """
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
        )
        layout.addWidget(self.id_input)

        # Password
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText(self.tr("ENTER PASSWORD"))
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setStyleSheet(
            """
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
        )
        layout.addWidget(self.pass_input)

        # Login button
        login_btn = QPushButton(self.tr("🔐 LOGIN"))
        login_btn.clicked.connect(self.validate_login)
        login_btn.setStyleSheet(
            """
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
        )
        layout.addWidget(login_btn)

        # Back button
        back_btn = QPushButton(self.tr("← BACK TO HOME"))
        back_btn.clicked.connect(self.back_callback)
        back_btn.setStyleSheet(
            """
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
        )
        layout.addWidget(back_btn)

    # ------------------------------------------------------------------
    # Helper: message box with black text (fixes white text issue)
    # ------------------------------------------------------------------
    def _show_message(self, icon: QMessageBox.Icon, title: str, text: str):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)

        box.setStyleSheet(
            """
            QMessageBox {
                background-color: #ffffff;
            }
            QLabel {
                color: #000000;
                font-size: 13px;
            }
            QPushButton {
                min-width: 80px;
                padding: 4px 10px;
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            """
        )

        box.exec()

    # ------------------------------------------------------------------
    # Login logic
    # ------------------------------------------------------------------
    def validate_login(self):

        raw_id = self.id_input.text() if self.id_input else ""
        raw_pwd = self.pass_input.text() if self.pass_input else ""

        admin_id = (raw_id or "").strip()
        pwd = (raw_pwd or "").strip()

        if not admin_id or not pwd:
            self._show_message(
                QMessageBox.Icon.Warning,
                self.tr("Login Failed"),
                self.tr("Please enter both ID and password."),
            )
            return

        # --- Step 1: look up by ID only ---
        filter_query = f"id=eq.{admin_id}"

        try:
            resp = supabase_get(
                "admins",
                filter_query=filter_query,
                select="id,name,password,is_active",
            )
        except Exception as e:
            self._show_message(
                QMessageBox.Icon.Critical,
                self.tr("Error"),
                self.tr("Failed to connect to Supabase."),
            )
            return

        status = getattr(resp, "status_code", None)

        if status != 200:
            self._show_message(
                QMessageBox.Icon.Critical,
                self.tr("Error"),
                f"{self.tr('Server error while fetching admin.')} (status {status})",
            )
            return

        try:
            rows = resp.json() or []
        except Exception:
            rows = []

        if not rows:
            self._show_message(
                QMessageBox.Icon.Warning,
                self.tr("Login Failed"),
                self.tr("No admin found with this ID."),
            )
            return

        # --- Step 2: compare password in Python ---
        admin_row = rows[0]
        db_id = str(admin_row.get("id") or "").strip()
        db_name = str(admin_row.get("name") or db_id).strip()
        db_pwd = str(admin_row.get("password") or "").strip()
        db_active = admin_row.get("is_active")

        if db_active is False:
            self._show_message(
                QMessageBox.Icon.Warning,
                self.tr("Login Failed"),
                self.tr("This admin account is disabled."),
            )
            return

        if pwd != db_pwd:
            self._show_message(
                QMessageBox.Icon.Warning,
                self.tr("Login Failed"),
                self.tr("Invalid ID or password."),
            )
            return

        # SUCCESS -> open dashboard (prefer embedding in stack)
        self._open_dashboard(admin_id=db_id, admin_name=db_name)

    # ------------------------------------------------------------------
    # Open dashboard
    # ------------------------------------------------------------------
    def _open_dashboard(self, admin_id: str, admin_name: str):
        lang = "English"
        parent = self.parent()
        while parent:
            if hasattr(parent, "eng_radio") and hasattr(parent, "mal_radio"):
                lang = "English" if parent.eng_radio.isChecked() else "Malayalam"
                break
            parent = parent.parent()

        self.dashboard = AdminDashboard(
            admin_id=admin_id,
            admin_name=admin_name,
        )

        stack = self.stack
        if stack is not None:
            stack.addWidget(self.dashboard)
            stack.setCurrentWidget(self.dashboard)

            try:
                def on_logout_and_cleanup(d=self.dashboard, s=stack):
                    try:
                        self.back_callback()
                    except Exception:
                        try:
                            s.setCurrentIndex(0)
                        except Exception:
                            pass
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
            # fallback: top-level window but still try to call back
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

        try:
            if self.isWindow():
                self.close()
        except Exception:
            pass
