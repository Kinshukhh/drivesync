import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon

from ui.login_window import LoginWindow
from ui.main_window import MainWindow, TOKEN_JSON
from core.google_auth import GoogleAuth

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)

        icon = QIcon(resource_path("assets/icon.ico"))
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("DriveSync")

        menu = QMenu()
        open_action = menu.addAction("Open DriveSync")
        quit_action = menu.addAction("Quit")
        open_action.triggered.connect(self.open_app)
        quit_action.triggered.connect(self.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()

        self.login_window = LoginWindow()
        self.main_window = MainWindow()
        self.main_window.login_window_ref = self.login_window
        self.main_window.set_tray(self.tray)
        self.main_window.hide()

        self.auth = GoogleAuth()
        self.login_window.loginRequested.connect(self.do_login)

        if os.path.exists(TOKEN_JSON):
            creds = self.auth.load_existing()
            if creds:
                self.main_window.set_credentials(creds)
                self.main_window.enable_sync_ui()
                self.main_window.show()
            else:
                self.login_window.show()
        else:
            self.login_window.show()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_app()

    def open_app(self):
        if self.login_window.isVisible():
            self.login_window.show()
            self.login_window.raise_()
        else:
            self.main_window.show()
            self.main_window.raise_()

    def do_login(self):
        creds = self.auth.login()
        if creds:
            QMessageBox.information(None, "Login", "Login successful!")
            self.login_window.set_success()
            self.login_window.hide()
            self.main_window.set_credentials(creds)
            self.main_window.enable_sync_ui()
            self.main_window.show()

    def quit(self):
        try:
            for w in list(self.main_window.watchers.values()):
                w.stop()
        except:
            pass

        self.main_window.watchers.clear()
        self.tray.hide()
        sys.exit()

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    TrayApp().run()
