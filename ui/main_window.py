import os
import json
import platform
import subprocess
import sys
from threading import Thread
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFileDialog, QLabel, QListWidget,
    QHBoxLayout, QMessageBox, QLineEdit, QToolButton, QStyle, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction, QIcon

from core.folder_watcher import FolderWatcher
from core.sync_engine import SyncEngine
from core.drive_client import DriveClient

if platform.system() == "Windows":
    APP_DATA_DIR = Path(os.getenv("APPDATA")) / "DriveSync"
else:
    APP_DATA_DIR = Path.home() / ".config" / "DriveSync"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

SYNCED_JSON = str(APP_DATA_DIR / "synced_folders.json")
TOKEN_JSON = str(APP_DATA_DIR / "token.json")
TRACKING_DB = str(APP_DATA_DIR / "sync_tracking.json")

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class MainWindow(QWidget):
    status_updated = pyqtSignal(str)
    folder_added = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DriveSync")
        self.setMinimumSize(600, 420)
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))

        top = QHBoxLayout()

        self.add_btn = QToolButton()
        self.add_btn.setText("Add")
        self.add_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.add_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.add_btn.clicked.connect(self.select_folder)

        add_action = QAction("Add", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self.select_folder)
        self.addAction(add_action)

        self.remove_btn = QToolButton()
        self.remove_btn.setText("Remove")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)

        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("Refresh")
        self.refresh_btn.clicked.connect(self.reload_from_disk)

        self.help_btn = QToolButton()
        self.help_btn.setText("Help")
        self.help_btn.clicked.connect(self.show_help)

        self.reset_btn = QToolButton()
        self.reset_btn.setText("Reset Sync")
        self.reset_btn.clicked.connect(self.reset_sync)

        self.full_reset_btn = QToolButton()
        self.full_reset_btn.setText("Full Reset")
        self.full_reset_btn.clicked.connect(self.full_reset)

        self.logout_btn = QToolButton()
        self.logout_btn.setText("Logout")
        self.logout_btn.clicked.connect(self.logout)

        top.addWidget(self.add_btn)
        top.addWidget(self.remove_btn)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.help_btn)
        top.addWidget(self.reset_btn)
        top.addWidget(self.full_reset_btn)
        top.addWidget(self.logout_btn)
        top.addStretch()

        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter folders...")
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(QLabel("Search:"))
        filter_layout.addWidget(self.filter_input)

        self.list_label = QLabel("Synced Folders:")
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._open_folder_for_item)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)

        self.status_label = QLabel("Not logged in.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray;")

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(filter_layout)
        layout.addWidget(self.list_label)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.creds = None
        self.drive_client = None
        self.sync_engine = None
        self.watchers = {}
        self.tray = None
        self.login_window_ref = None

        self.status_updated.connect(self._set_status)
        self.folder_added.connect(self._append_folder_item)

        self._load_synced_json()

    def set_tray(self, tray_icon):
        self.tray = tray_icon

    def set_credentials(self, creds):
        self.creds = creds
        self.drive_client = DriveClient(creds)
        self.sync_engine = SyncEngine(self.drive_client)
        self.add_btn.setEnabled(True)
        self.status_label.setText("Ready to Sync")

    def enable_sync_ui(self):
        self.add_btn.setEnabled(True)
        self.remove_btn.setEnabled(bool(self.list_widget.selectedItems()))
        self.status_label.setText("Ready to Sync")
        for folder in self._get_persisted_folders():
            if os.path.isdir(folder) and folder not in self.watchers:
                self._start_sync_for(folder)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Sync")
        if folder:
            folder = os.path.abspath(folder)
            if folder in self._get_persisted_folders():
                QMessageBox.information(self, "Already Added", f"{folder} is already being synced.")
                return
            self.folder_added.emit(folder)
            self._save_synced_json()
            self._start_sync_for(folder)
            self.status_updated.emit(f"Watching: {folder}")

    def _start_sync_for(self, folder):
        if not self.sync_engine:
            self.status_updated.emit("ERROR: Sync engine not initialized.")
            return

        self.sync_engine.register_folder(folder)

        def do_full_sync():
            try:
                self.status_updated.emit(f"Full sync started: {folder}")
                self.sync_engine.sync_folder(folder)
                self.status_updated.emit(f"Full sync completed: {folder}")
            except Exception as e:
                self.status_updated.emit(f"Sync error: {e}")

            try:
                watcher = FolderWatcher(
                    folder,
                    self.sync_engine.sync_file,
                    self.sync_engine.delete_file,
                    self.sync_engine.move_file
                )
                watcher.start()
                self.watchers[folder] = watcher
                self.status_updated.emit(f"Watcher started: {folder}")
            except Exception as e:
                self.status_updated.emit(f"Watcher error: {e}")

        Thread(target=do_full_sync, daemon=True).start()

    def remove_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            return

        if QMessageBox.question(
            self, "Confirm Remove", "Remove selected folders?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        for it in items:
            folder = it.text()
            if folder in self.watchers:
                self.watchers[folder].stop()
                del self.watchers[folder]
            self.list_widget.takeItem(self.list_widget.row(it))

        self._save_synced_json()
        self.status_updated.emit("Folder removed.")

    def _on_selection_changed(self):
        self.remove_btn.setEnabled(bool(self.list_widget.selectedItems()))

    def _load_synced_json(self):
        if os.path.exists(SYNCED_JSON):
            try:
                with open(SYNCED_JSON, "r") as f:
                    data = json.load(f)
                for folder in data:
                    self.list_widget.addItem(folder)
            except:
                pass

    def _get_persisted_folders(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def _save_synced_json(self):
        with open(SYNCED_JSON, "w") as f:
            json.dump(self._get_persisted_folders(), f, indent=2)

    def _set_status(self, text):
        self.status_label.setText(text)

    def _append_folder_item(self, folder):
        self.list_widget.addItem(folder)
        self._save_synced_json()

    def _apply_filter(self, text):
        t = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(t not in item.text().lower())

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        folder = item.text()

        menu = QMenu(self)
        open_action = QAction("Open Folder", self)
        open_action.triggered.connect(lambda: self._open_folder(folder))
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_single(folder))

        menu.addAction(open_action)
        menu.addAction(remove_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _open_folder(self, folder):
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except:
            pass

    def _open_folder_for_item(self, item):
        self._open_folder(item.text())

    def _remove_single(self, folder):
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == folder:
                self.list_widget.setCurrentRow(i)
                break
        self.remove_selected()

    def reload_from_disk(self):
        for w in list(self.watchers.values()):
            try: w.stop()
            except: pass

        self.watchers.clear()
        self.list_widget.clear()
        self._load_synced_json()

        for folder in self._get_persisted_folders():
            if os.path.isdir(folder):
                self._start_sync_for(folder)

        self.status_updated.emit("Reloaded.")

    def logout(self):
        if QMessageBox.question(
            self, "Logout", "Logout from Google?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        for w in list(self.watchers.values()):
            try: w.stop()
            except: pass

        self.watchers.clear()

        if os.path.exists(TOKEN_JSON):
            try: os.remove(TOKEN_JSON)
            except: pass

        self.creds = None
        self.drive_client = None
        self.sync_engine = None

        self.list_widget.clear()
        self._save_synced_json()

        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        self.status_updated.emit("Logged out.")

        if self.tray:
            try: self.tray.showMessage("DriveSync", "Logged out.", msecs=2500)
            except: pass

        if self.login_window_ref:
            self.hide()
            self.login_window_ref.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if self.tray:
            try: self.tray.showMessage("DriveSync", "Running in background.", msecs=3000)
            except: pass

    def show_help(self):
        QMessageBox.information(
            self,
            "DriveSync Help",
            "• Add: Select a folder to sync.\n"
            "• Remove: Stop syncing.\n"
            "• Refresh: Restart watchers.\n"
            "• Reset Sync: Clear tracking + folder list.\n"
            "• Full Reset: Deletes everything including login."
        )

    def reset_sync(self):
        resp = QMessageBox.question(
            self,
            "Reset Sync",
            "Reset sync data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        for w in list(self.watchers.values()):
            try: w.stop()
            except: pass
        self.watchers.clear()

        try:
            if os.path.exists(SYNCED_JSON): os.remove(SYNCED_JSON)
            if os.path.exists(TRACKING_DB): os.remove(TRACKING_DB)
        except:
            pass

        self.list_widget.clear()

        self.sync_engine = None
        self.drive_client = None

        self.set_credentials(self.creds)
        self.status_updated.emit("Sync reset.")

        if self.tray:
            try: self.tray.showMessage("DriveSync", "Sync reset.", msecs=2000)
            except: pass

    def full_reset(self):
        resp = QMessageBox.question(
            self,
            "Full Reset",
            "Delete all sync data + login?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        for w in list(self.watchers.values()):
            try: w.stop()
            except: pass
        self.watchers.clear()

        try:
            if os.path.exists(SYNCED_JSON): os.remove(SYNCED_JSON)
            if os.path.exists(TRACKING_DB): os.remove(TRACKING_DB)
            if os.path.exists(TOKEN_JSON): os.remove(TOKEN_JSON)
        except:
            pass

        self.list_widget.clear()
        self.sync_engine = None
        self.drive_client = None
        self.creds = None

        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        if self.tray:
            try: self.tray.showMessage("DriveSync", "Full reset done.", msecs=2500)
            except: pass

        self.hide()
        if self.login_window_ref:
            self.login_window_ref.show()
