import os
import tempfile
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from pathlib import Path
import platform

if platform.system() == "Windows":
    APP_DATA_DIR = Path(os.getenv("APPDATA")) / "DriveSync"
else:
    APP_DATA_DIR = Path.home() / ".config" / "DriveSync"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

TOKEN_JSON = str(APP_DATA_DIR / "token.json")


class GoogleAuth:
    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def load_existing(self):
        if os.path.exists(TOKEN_JSON):
            creds = Credentials.from_authorized_user_file(TOKEN_JSON, self.SCOPES)
            if creds and creds.valid:
                return creds
        return None

    def login(self):
        creds = self.load_existing()
        if creds:
            return creds

        DROPBOX_LINK = "https://www.dropbox.com/scl/fi/sr0na0y0gjs582m19rsao/DriveSync_credentials.json?rlkey=zlu35sho0824udodi3o1r3y6n&st=pm0qc0m6&dl=0"

        if "dl=0" in DROPBOX_LINK:
            DROPBOX_LINK = DROPBOX_LINK.replace("dl=0", "dl=1")
        elif "dl=1" not in DROPBOX_LINK:
            DROPBOX_LINK += "?dl=1"

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temp_file_path = temp_file.name
        temp_file.close()

        try:
            r = requests.get(DROPBOX_LINK, timeout=10)
            r.raise_for_status()

            with open(temp_file_path, "wb") as f:
                f.write(r.content)

            flow = InstalledAppFlow.from_client_secrets_file(temp_file_path, self.SCOPES)
            creds = flow.run_local_server(port=0)

            with open(TOKEN_JSON, "w") as token:
                token.write(creds.to_json())

            return creds

        finally:
            try:
                os.remove(temp_file_path)
            except:
                pass
