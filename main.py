import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QRadioButton, QButtonGroup, QFrame, QStackedLayout, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QSize
import requests

from gui.staff_panel import StaffPanel
from gui.admin_panel.login_screen import AdminPanel


class ClickableLabel(QLabel):
    def __init__(self, label_type, click_callback, parent=None):
        super().__init__(parent)
        self.label_type = label_type
        self.click_callback = click_callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_callback(self.label_type)


class LoginUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E-WorkTrack")
        self.resize(1000, 680)
        self.setMinimumSize(600, 480)
        self.setStyleSheet("background-color: #f0f4fb;")

        self.stack = QStackedLayout()
        self.setLayout(self.stack)

        self.init_landing_ui()

        # Initialize login panels
        self.staff_panel = StaffPanel(self.back_to_landing)
        self.admin_panel = AdminPanel(self.back_to_landing)

        self.stack.addWidget(self.landing_widget)
        self.stack.addWidget(self.staff_panel)
        self.stack.addWidget(self.admin_panel)

    def init_landing_ui(self):
        self.landing_widget = QWidget()
        layout = QVBoxLayout(self.landing_widget)

        title = QLabel("Welcome to E-WorkTrack")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #1e293b; padding-top: 30px; padding-bottom: 15px;")
        layout.addWidget(title)

        self.card_layout = QHBoxLayout()
        self.card_layout.setSpacing(30)

        self.staff_card, self.staff_image_label, self.staff_pixmap = self.create_card(
            "Staff",
            "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        )
        self.admin_card, self.admin_image_label, self.admin_pixmap = self.create_card(
            "Admin",
            "https://cdn-icons-png.flaticon.com/512/4034/4034609.png"
        )

        self.card_layout.addWidget(self.staff_card)
        self.card_layout.addWidget(self.admin_card)
        layout.addLayout(self.card_layout)

        lang_label = QLabel("Choose Language")
        lang_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_label.setStyleSheet("color: #475569; font-size: 13px; padding-top: 10px")
        layout.addWidget(lang_label)

        lang_row = QHBoxLayout()
        self.radio_group = QButtonGroup()

        self.eng_radio = QRadioButton("English")
        self.mal_radio = QRadioButton("മലയാളം")
        self.eng_radio.setChecked(True)

        for btn in [self.eng_radio, self.mal_radio]:
            btn.setStyleSheet("""
                font-size: 13px;
                color: #1e293b;
                padding: 6px 12px;
            """)
            self.radio_group.addButton(btn)
            lang_row.addWidget(btn)

        lang_frame = QFrame()
        lang_frame.setLayout(lang_row)
        lang_frame.setStyleSheet("""
            background-color: #e0e7ff;
            padding: 5px;
            border-radius: 12px;
            border: 1px solid #c7d2fe;
        """)
        layout.addWidget(lang_frame)

        powered = QLabel("Powered by E-WorkTrack AI Logging Engine")
        powered.setAlignment(Qt.AlignmentFlag.AlignCenter)
        powered.setStyleSheet("color: #64748b; font-size: 12px; padding-top: 10px")
        layout.addWidget(powered)

    def create_card(self, label, url):
        vbox = QVBoxLayout()
        image_label = ClickableLabel(label, self.handle_card_click)
        image_label.setScaledContents(True)
        image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        try:
            response = requests.get(url)
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            image_label.setPixmap(pixmap)
        except:
            pixmap = QPixmap()
            image_label.setText("Image Load Error")

        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setStyleSheet("color: #1e293b; font-weight: bold; font-size: 14px;")

        wrapper = QFrame()
        wrapper.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 12px;
                padding: 10px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout = QVBoxLayout()
        layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        wrapper.setLayout(layout)

        return wrapper, image_label, pixmap

    def handle_card_click(self, role):
        if role == "Staff":
            self.stack.setCurrentWidget(self.staff_panel)
        elif role == "Admin":
            self.stack.setCurrentWidget(self.admin_panel)

    def back_to_landing(self):
        self.stack.setCurrentWidget(self.landing_widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_size = QSize(self.width() // 4, self.width() // 4)
        for label, pixmap in [(self.staff_image_label, self.staff_pixmap), (self.admin_image_label, self.admin_pixmap)]:
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    new_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                label.setPixmap(scaled)
                label.setFixedSize(new_size)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoginUI()
    win.show()
    sys.exit(app.exec())
