import os
import hashlib
import json
import threading
import time
import subprocess
from pathlib import Path
import platform
import tempfile

if platform.system() == "Windows":
    APP_DATA_DIR = Path(os.getenv("APPDATA")) / "DriveSync"
else:
    APP_DATA_DIR = Path.home() / ".config" / "DriveSync"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
TRACKING_DB = str(APP_DATA_DIR / "sync_tracking.json")


class SyncEngine:
    def __init__(self, drive_client):
        self.drive = drive_client
        self._lock = threading.RLock()
        if os.path.exists(TRACKING_DB):
            try:
                with open(TRACKING_DB, "r", encoding="utf-8") as f:
                    self.db = json.load(f)
            except:
                self.db = {"folders": {}, "files": {}}
        else:
            self.db = {"folders": {}, "files": {}}

    def save_db(self):
        with self._lock:
            try:
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TRACKING_DB))
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.db, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, TRACKING_DB)
            except:
                pass

    def hydrate(self, path):
        if platform.system() != "Windows":
            return
        try:
            attr = subprocess.check_output(["attrib", path], shell=True).decode(errors="ignore").strip()
            if "O" in attr or "P" in attr:
                try:
                    subprocess.call(["attrib", "-P", path], shell=True)
                    time.sleep(0.2)
                except:
                    pass
        except:
            pass

    def file_hash(self, path):
        try:
            h = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except:
            return None

    def register_folder(self, local_folder, parent_id=None):
        local_folder = os.path.abspath(local_folder)
        with self._lock:
            if local_folder in self.db["folders"]:
                return self.db["folders"][local_folder]
            name = os.path.basename(local_folder.rstrip(os.sep)) or local_folder
            try:
                folder_id = self.drive.create_or_get_folder(name, parent_id)
                if not folder_id:
                    return None
                self.db["folders"][local_folder] = folder_id
                self.save_db()
                return folder_id
            except:
                return None

    def _find_root_folder(self, path):
        path = os.path.abspath(path)
        with self._lock:
            matches = []
            for f in self.db["folders"]:
                try:
                    if os.path.commonpath([os.path.abspath(f), path]) == os.path.abspath(f):
                        matches.append(os.path.abspath(f))
                except:
                    if path.startswith(os.path.abspath(f)):
                        matches.append(os.path.abspath(f))
            if not matches:
                return None
            return max(matches, key=len)

    def sync_file(self, path, retry=1):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            return
        if not os.path.exists(path):
            return
        self.hydrate(path)
        h = self.file_hash(path)
        if h is None:
            if retry > 0:
                time.sleep(0.2)
                return self.sync_file(path, retry - 1)
            return
        with self._lock:
            existing = self.db["files"].get(path)
            if existing and existing.get("hash") == h:
                return
            root = self._find_root_folder(path)
            if not root:
                return
            parent_id = self.db["folders"].get(root)
            if not parent_id:
                return
        try:
            file_id = self.drive.upload_or_update(path, parent_id)
            if not file_id:
                raise Exception()
        except:
            if retry > 0:
                time.sleep(0.5)
                return self.sync_file(path, retry - 1)
            return
        with self._lock:
            self.db["files"][path] = {"id": file_id, "hash": h}
            self.save_db()

    def sync_folder(self, local_folder):
        local_folder = os.path.abspath(local_folder)
        root_id = self.register_folder(local_folder)
        if not root_id:
            return
        for root, dirs, files in os.walk(local_folder):
            root = os.path.abspath(root)
            try:
                parent_local = self._find_root_folder(root)
                parent_id = self.db["folders"].get(parent_local, root_id)
            except:
                parent_id = root_id
            if root not in self.db["folders"]:
                self.register_folder(root, parent_id)
            for d in dirs:
                sub = os.path.abspath(os.path.join(root, d))
                if sub not in self.db["folders"]:
                    self.register_folder(sub, self.db["folders"].get(root, parent_id))
            for f in files:
                fp = os.path.join(root, f)
                try:
                    self.sync_file(fp)
                except:
                    pass
        self.save_db()

    def delete_file(self, path):
        path = os.path.abspath(path)
        with self._lock:
            entry = self.db["files"].get(path)
            if not entry:
                return
            file_id = entry.get("id")
        try:
            if file_id:
                self.drive.delete_file(file_id)
        except:
            pass
        with self._lock:
            if path in self.db["files"]:
                del self.db["files"][path]
                self.save_db()

    def move_file(self, old_path, new_path):
        old_path = os.path.abspath(old_path)
        new_path = os.path.abspath(new_path)
        with self._lock:
            entry = self.db["files"].get(old_path)
            if not entry:
                return
            file_id = entry.get("id")
        try:
            self.drive.rename_file(file_id, os.path.basename(new_path))
        except:
            pass
        with self._lock:
            self.db["files"][new_path] = self.db["files"][old_path]
            del self.db["files"][old_path]
            self.save_db()
