# main.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QRadioButton, QButtonGroup, QFrame, QSizePolicy, QStackedWidget,
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QSize
import requests

# Adjust this import if your admin login class is named differently
from gui.staff_panel import StaffPanel
from gui.admin_panel.admin_login import AdminLogin


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
        self.setWindowTitle("AKSHAYA KODANNUR CRM")

        # sensible default window
        self.resize(1200, 760)
        self.setMinimumSize(900, 620)

        self.setStyleSheet("background-color: #f0f4fb;")

        # central stacked widget for navigation
        self.stack = QStackedWidget()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.stack)

        # keep references so resizeEvent can access card widgets/pixmaps
        self.staff_card = None
        self.admin_card = None
        self.staff_image_label = None
        self.admin_image_label = None
        self.staff_pixmap = None
        self.admin_pixmap = None

        self.init_landing_ui()

        # instantiate other panels (these constructors should match your project)
        try:
            self.staff_panel = StaffPanel(self.back_to_landing)
        except TypeError:
            try:
                self.staff_panel = StaffPanel(self.back_to_landing, self.stack)
            except Exception:
                self.staff_panel = StaffPanel(self.back_to_landing)

        try:
            self.admin_panel = AdminLogin(self.back_to_landing)
        except TypeError:
            try:
                self.admin_panel = AdminLogin(self.back_to_landing, self.stack)
            except Exception:
                self.admin_panel = AdminLogin(self.back_to_landing)

        # add pages to stack
        self.stack.addWidget(self.landing_widget)
        self.stack.addWidget(self.staff_panel)
        self.stack.addWidget(self.admin_panel)

        # show landing initially
        self.stack.setCurrentWidget(self.landing_widget)

    def init_landing_ui(self):
        # root landing widget
        self.landing_widget = QWidget()
        root_layout = QVBoxLayout(self.landing_widget)
        root_layout.setContentsMargins(24, 18, 24, 18)
        root_layout.setSpacing(12)

        # header (constrained width so title never becomes ridiculously long)
        title = QLabel("Welcome to AKSHAYA KODANNUR CRM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Inter", 34, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #0f172a; margin-top: 8px;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root_layout.addWidget(title)

        subtitle = QLabel("Choose a role to continue")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Inter", 12))
        subtitle.setStyleSheet("color: #475569; margin-bottom: 6px;")
        root_layout.addWidget(subtitle)

        # --- Center wrapper (constrain max width so UI looks like a login page) ---
        self.center_wrapper = QFrame()
        center_layout = QVBoxLayout(self.center_wrapper)
        center_layout.setContentsMargins(10, 6, 10, 6)
        center_layout.setSpacing(14)
        self.center_wrapper.setMaximumWidth(980)   # <--- critical to keep readable column on wide monitors
        self.center_wrapper.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # cards row (we'll rely on spacing + center_wrapper max width for layout)
        self.cards_row = QHBoxLayout()
        self.cards_row.setContentsMargins(18, 8, 18, 8)
        self.cards_row.setSpacing(36)

        # create cards (images are loaded lazily)
        self.staff_card, self.staff_image_label, self.staff_pixmap = self.create_card("Staff")
        self.admin_card, self.admin_image_label, self.admin_pixmap = self.create_card("Admin")

        # force same preferred dimensions for both cards (keeps symmetric)
        card_pref_w = 420
        card_pref_h = 360
        for c in (self.staff_card, self.admin_card):
            c.setMinimumWidth(320)
            c.setMaximumWidth(card_pref_w)
            c.setMinimumHeight(card_pref_h)
            c.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # add stretch to center the pair inside the constrained center wrapper
        self.cards_row.addStretch(1)
        self.cards_row.addWidget(self.staff_card, alignment=Qt.AlignmentFlag.AlignCenter)
        self.cards_row.addSpacing(12)
        self.cards_row.addWidget(self.admin_card, alignment=Qt.AlignmentFlag.AlignCenter)
        self.cards_row.addStretch(1)

        center_layout.addLayout(self.cards_row)

        # language selector (compact & centered)
        lang_label = QLabel("Choose Language")
        lang_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_label.setStyleSheet("color: #475569; font-size: 13px; margin-top: 6px;")
        center_layout.addWidget(lang_label)

        lang_row = QHBoxLayout()
        lang_row.setContentsMargins(120, 0, 120, 0)
        lang_row.setSpacing(24)
        self.radio_group = QButtonGroup()
        self.eng_radio = QRadioButton("English")
        self.mal_radio = QRadioButton("മലയാളം")
        self.eng_radio.setChecked(True)
        for btn in (self.eng_radio, self.mal_radio):
            btn.setStyleSheet("QRadioButton { font-size: 13px; color: #0f172a; }")
            self.radio_group.addButton(btn)
            lang_row.addWidget(btn)

        lang_holder = QHBoxLayout()
        lang_holder.addStretch()
        lang_holder.addLayout(lang_row)
        lang_holder.addStretch()
        center_layout.addLayout(lang_holder)

        powered = QLabel("Powered by Akshaya Kodannur CRM AI Logging Engine")
        powered.setAlignment(Qt.AlignmentFlag.AlignCenter)
        powered.setStyleSheet("color: #64748b; font-size: 12px; padding-top: 8px;")
        center_layout.addWidget(powered)

        root_layout.addStretch(1)
        root_layout.addWidget(self.center_wrapper, alignment=Qt.AlignmentFlag.AlignCenter)
        root_layout.addStretch(1)

    def create_card(self, label):
        image_label = ClickableLabel(label, self.handle_card_click)
        image_label.setScaledContents(True)
        image_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        pixmap = QPixmap()
        # try to fetch images (fail gracefully)
        try:
            url_map = {
                "Staff": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                "Admin": "https://cdn-icons-png.flaticon.com/512/4034/4034609.png"
            }
            resp = requests.get(url_map.get(label, ""), timeout=4)
            if resp.status_code == 200:
                pixmap.loadFromData(resp.content)
                image_label.setPixmap(pixmap)
        except Exception:
            # fallback: an emoji/text placeholder
            image_label.setText("👤" if label == "Staff" else "🛂")
            image_label.setFont(QFont("Inter", 48))
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_widget = QLabel(label.upper())
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 14px; padding: 10px 8px;")

        wrapper = QFrame()
        wrapper.setStyleSheet("""
            QFrame { background-color: #ffffff; border-radius: 12px; padding: 18px; border: 1px solid #e6edf7; }
        """)
        v = QVBoxLayout(wrapper)
        v.setSpacing(12)
        v.setContentsMargins(20, 10, 20, 14)

        # fixed-size image frame so both cards align perfectly
        img_frame = QFrame()
        img_frame.setFixedSize(220, 220)
        img_layout = QVBoxLayout(img_frame)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.addStretch()
        img_layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        img_layout.addStretch()

        # ensure image_label uses target size
        image_label.setFixedSize(180, 180)

        v.addWidget(img_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        v.addWidget(label_widget)
        return wrapper, image_label, pixmap

    def handle_card_click(self, role):
        if role == "Staff":
            self.stack.setCurrentWidget(self.staff_panel)
        elif role == "Admin":
            self.stack.setCurrentWidget(self.admin_panel)

    def back_to_landing(self):
        self.stack.setCurrentWidget(self.landing_widget)

    def resizeEvent(self, event):
        # override to implement responsive stacking and proper pixmap scaling
        super().resizeEvent(event)
        try:
            w = self.width()
            # responsive threshold: narrow windows stack vertically
            if w < 820:
                # stack vertically by forcing both cards to the full constrained width
                for c in (self.staff_card, self.admin_card):
                    if c:
                        c.setMaximumWidth(self.center_wrapper.maximumWidth() - 40)
                        c.setMinimumWidth(360)
                # adjust spacing (cards_row stays HBox but cards fill center so appear stacked)
                self.cards_row.setSpacing(12)
            else:
                # wide mode: symmetric side-by-side cards
                for c in (self.staff_card, self.admin_card):
                    if c:
                        c.setMaximumWidth(420)
                self.cards_row.setSpacing(36)
        except Exception:
            pass

        # scale pixmaps into their labels preserving aspect ratio
        for label, pixmap in [
            (getattr(self, "staff_image_label", None), getattr(self, "staff_pixmap", None)),
            (getattr(self, "admin_image_label", None), getattr(self, "admin_pixmap", None))
        ]:
            if label is None:
                continue
            try:
                if pixmap and not pixmap.isNull():
                    target = label.size()
                    scaled = pixmap.scaled(
                        target,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    label.setPixmap(scaled)
            except Exception:
                pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoginUI()
    win.show()
    sys.exit(app.exec())
