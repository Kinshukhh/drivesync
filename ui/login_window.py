from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QMovie, QKeySequence
from PyQt6.QtGui import QIcon
import os,sys
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class LoginWindow(QWidget):
    loginRequested = pyqtSignal()
    cancelRequested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sign in — DriveSync")
        self.setFixedSize(420, 260)
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self._create_widgets()
        self._layout_widgets()
        self._connect_signals()
        self._apply_styles()

        self._spinner_movie = None
        self._spinner_label = None
        self._load_spinner()

    def _create_widgets(self):
        self.header = QLabel("Sign in to Google Drive")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        self.header.setFont(header_font)
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle = QLabel("Authorize DriveSync to access your Google Drive so it can sync files automatically.")
        self.subtitle.setWordWrap(True)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo = QLabel()
        self.logo.setFixedSize(72, 72)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setText("🔒")
        self.logo.setAccessibleName("login-logo")

        self.status_label = QLabel("") 
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("login-status")

        self.login_btn = QPushButton("Login with Google")
        self.login_btn.setDefault(True)
        self.login_btn.setAutoDefault(True)
        self.login_btn.setToolTip("Start Google sign-in (Enter)")
        self.login_btn.setAccessibleName("login-button")

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel and close (Esc)")
        self.cancel_btn.setAccessibleName("cancel-button")
        self.cancel_btn.clicked.connect(self.close)


    def _layout_widgets(self):
        main = QVBoxLayout()
        main.setContentsMargins(18, 18, 18, 18)
        main.setSpacing(12)

        main.addWidget(self.header)
        main.addWidget(self.subtitle)

        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(self.logo)
        logo_row.addStretch()
        main.addLayout(logo_row)

        main.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addItem(QSpacerItem(8, 8, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addItem(QSpacerItem(8, 8, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        main.addLayout(btn_row)

        self.setLayout(main)

    def _connect_signals(self):
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QLabel#login-status { color: #333; }
            QPushButton { padding: 8px 14px; }
            QPushButton:disabled { color: #777; }
            """
        )

    def _load_spinner(self):
        try:
            movie = QMovie("spinner.gif")
            if movie.isValid():
                self._spinner_movie = movie
                spinner = QLabel()
                spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spinner.setFixedSize(24, 24)
                spinner.setMovie(movie)
                self._spinner_label = spinner
            else:
                self._spinner_movie = None
                self._spinner_label = None
        except Exception:
            self._spinner_movie = None
            self._spinner_label = None

    def _on_login_clicked(self):
        self.start_login()
        self.loginRequested.emit()

    def _on_cancel_clicked(self):
        self.cancelRequested.emit()

    def start_login(self, message: str = "Opening browser to sign in..."):
        """Call this before starting the async sign-in flow."""
        self.login_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText(message)
        if self._spinner_label and self._spinner_movie:
            if self._spinner_movie.state() != QMovie.MovieState.Running:
                self._spinner_movie.start()
            self.layout().insertWidget(3, self._spinner_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def stop_login(self):
        """Stop any spinner and re-enable the login button (use after flow completes)."""
        self.login_btn.setEnabled(True)
        if self._spinner_label and self._spinner_movie:
            try:
                self._spinner_movie.stop()
            except Exception:
                pass
            try:
                self.layout().removeWidget(self._spinner_label)
                self._spinner_label.setParent(None)
            except Exception:
                pass

    def set_success(self, message: str = "Login successful!"):
        """Show success state and disable login button."""
        self.stop_login()
        self.status_label.setText(message)
        self.login_btn.setEnabled(False)
        self.login_btn.setToolTip("Already logged in")
        self.status_label.setStyleSheet("color: green;")
        self.cancel_btn.setText("Close")
        self.cancel_btn.clicked.connect(self.close)


    def set_failure(self, message: str = "Login failed. Try again."):
        """Show failure state and allow retry."""
        self.stop_login()
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;")
        self.login_btn.setEnabled(True)


    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.InsertParagraphSeparator) or event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.login_btn.isEnabled():
                self._on_login_clicked()
                return
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel_clicked()
            return
        super().keyPressEvent(event)
