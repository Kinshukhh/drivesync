import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FolderHandler(FileSystemEventHandler):
    def __init__(self, modify_cb, delete_cb, move_cb):
        self.modify_cb = modify_cb
        self.delete_cb = delete_cb
        self.move_cb = move_cb
        self.last_event = {}
        self.lock = threading.Lock()
        self.DEBOUNCE_MS = 0.25

    def _should_process(self, path):
        now = time.time()
        with self.lock:
            last = self.last_event.get(path, 0)
            if now - last < self.DEBOUNCE_MS:
                return False
            self.last_event[path] = now
            return True

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self.modify_cb(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self.modify_cb(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.delete_cb(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self.move_cb(event.src_path, event.dest_path)


class FolderWatcher:
    def __init__(self, folder, modify_cb, delete_cb, move_cb):
        self.folder = folder
        self.modify_cb = modify_cb
        self.delete_cb = delete_cb
        self.move_cb = move_cb
        self.observer = Observer()
        self.running = False

    def start(self):
        if self.running:
            return
        handler = FolderHandler(self.modify_cb, self.delete_cb, self.move_cb)
        self.observer.schedule(handler, self.folder, recursive=True)
        self.observer.start()
        self.running = True

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.observer.stop()
        self.observer.join()
