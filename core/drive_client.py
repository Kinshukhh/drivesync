from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import os
import traceback


class DriveClient:
    def __init__(self, creds):
        self.service = build("drive", "v3", credentials=creds)
    def create_or_get_folder(self, name, parent_id=None):
        try:
            if parent_id:
                query = (
                    f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
                    f"and '{parent_id}' in parents and trashed=false"
                )
            else:
                query = (
                    f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
                    "and trashed=false"
                )

            res = self.service.files().list(q=query, spaces="drive").execute()

            if res["files"]:
                return res["files"][0]["id"]

            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder"
            }

            if parent_id:
                metadata["parents"] = [parent_id]

            folder = self.service.files().create(body=metadata, fields="id").execute()
            return folder["id"]

        except HttpError as e:
            print("[DRIVE FOLDER ERROR]", e)
            traceback.print_exc()
            return None

    def upload_or_update(self, path, parent_id):
        try:
            name = os.path.basename(path)

            query = (
                f"name='{name}' and '{parent_id}' in parents and trashed=false"
            )
            existing = self.service.files().list(q=query, spaces="drive").execute().get("files", [])

            media = MediaFileUpload(path, resumable=True)

        
            if existing:
                file_id = existing[0]["id"]
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                return file_id

        
            metadata = {
                "name": name,
                "parents": [parent_id]
            }

            upload = self.service.files().create(
                body=metadata,
                media_body=media,
                fields="id"
            ).execute()

            return upload["id"]

        except HttpError as e:
            print("[UPLOAD ERROR]", e)
            traceback.print_exc()
            return None


    def delete_file(self, file_id):
        try:
            self.service.files().delete(fileId=file_id).execute()
        except HttpError as e:
            print("[DELETE ERROR]", e)
            traceback.print_exc()

    def rename_file(self, file_id, new_name):
        try:
            self.service.files().update(
                fileId=file_id,
                body={"name": new_name}
            ).execute()
        except HttpError as e:
            print("[RENAME ERROR]", e)
            traceback.print_exc()
