import mimetypes
import os
from utils import execute

from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


def publish_android(package_name: str, service_account_json: str, phone_dir: str, tablet_dir: str, track: str,
                    locale: str, version_code: str) -> None:
    print("#########################################################")
    print("# Android                                               #")
    print("#########################################################")

    service, edit_id = start_edit(service_account_json, package_name)

    aab_path = build_aab()
    upload_aab(package_name, aab_path, service, edit_id)

    delete_all_screenshots(package_name, locale, service, edit_id)
    upload_screenshots(package_name, phone_dir, tablet_dir, locale, service, edit_id)
    commit(edit_id, package_name, service, track, version_code)

    print("Android publication complete, check the Play Console if you need to submit the changes for review.")


def build_aab():
    print("Building AAB")
    execute(["flutter", "build", "appbundle", "--release"])
    return "build/app/outputs/bundle/release/app-release.aab"


def start_edit(service_account_json: str, package_name: str) -> tuple[Resource, str]:
    print("Logging in to Google Play")
    credentials = service_account.Credentials.from_service_account_file(service_account_json, scopes=[
        "https://www.googleapis.com/auth/androidpublisher"])
    service = build("androidpublisher", "v3", credentials=credentials)

    print(f"Creating an edit for {package_name}")
    edit_request = service.edits().insert(body={}, packageName=package_name)
    edit_response = edit_request.execute()
    edit_id = edit_response["id"]

    return service, edit_id


def upload_aab(package_name: str, aab_path: str, service: Resource, edit_id):
    # Upload AAB
    print(f"Uploading to Google Play: {package_name} from {aab_path} ({edit_id})")
    media = MediaFileUpload(aab_path, mimetype="application/octet-stream", resumable=True)
    try:
        result = service.edits().bundles().upload(editId=edit_id, packageName=package_name, media_body=media).execute()
        print(f"Uploaded to Google Play: {result}")
    except HttpError as error:
        print(f"An error occurred: {error}")
        return


def delete_all_screenshots(package_name: str, locale: str, service: Resource, edit_id: str) -> None:
    print(f"Deleting all existing screenshots for {package_name} ({locale})")
    image_types = [
        "phoneScreenshots",
        "sevenInchScreenshots",
        "tenInchScreenshots",
        "tvScreenshots",
        "wearScreenshots"
    ]
    for img_type in image_types:
        try:
            images = service.edits().images().list(
                editId=edit_id,
                packageName=package_name,
                language=locale,
                imageType=img_type
            ).execute().get("images", [])

            for img in images:
                image_id = img["id"]
                service.edits().images().delete(
                    editId=edit_id,
                    packageName=package_name,
                    language=locale,
                    imageType=img_type,
                    imageId=image_id
                ).execute()
                print(f"Deleted {img_type}: {image_id}")
        except HttpError as e:
            if e.resp.status == 404:
                continue  # no screenshots of this type
            raise


def upload_screenshots(package_name: str, phone_dir: str, tablet_dir: str, locale: str, service, edit_id):
    # Upload phone screenshots
    print("Upload phone screenshots to Google Play")
    if os.path.exists(phone_dir):
        for file in os.listdir(phone_dir):
            if file.endswith((".png", ".jpg")):
                print(f"Uploading {file}")
                path = os.path.join(phone_dir, file)
                mimetype, _ = mimetypes.guess_type(path)
                media = MediaFileUpload(path, mimetype=mimetype, resumable=True)
                service.edits().images().upload(editId=edit_id, packageName=package_name, language=locale,
                                                imageType="phoneScreenshots", media_body=media).execute()

    # Upload tablet screenshots
    print("Upload tablet screenshots to Google Play")
    if os.path.exists(tablet_dir):
        for file in os.listdir(tablet_dir):
            if file.endswith((".png", ".jpg")):
                print(f"Uploading {file}")
                path = os.path.join(tablet_dir, file)
                mimetype, _ = mimetypes.guess_type(path)
                media = MediaFileUpload(path, mimetype=mimetype, resumable=True)
                service.edits().images().upload(editId=edit_id, packageName=package_name, language=locale,
                                                imageType="tenInchScreenshots", media_body=media).execute()


def commit(edit_id: str, package_name: str, service: Resource, track: str, version_code: str):
    print(f"Commit track '{track}' to Google Play ({version_code})")
    track_body = {
        "track": track,
        "releases": [{"versionCodes": [version_code], "status": "completed"}]
    }
    service.edits().tracks().update(editId=edit_id, track=track, packageName=package_name, body=track_body).execute()

    try:
        service.edits().commit(editId=edit_id, packageName=package_name, changesNotSentForReview=True).execute()
    except Exception as e:
        print("Failed to commit edits with changesNotSentForReview=True")
        print(f"Error: {e}")
        print("Try again without changesNotSentForReview")
        service.edits().commit(editId=edit_id, packageName=package_name).execute()
        print("It worked without changesNotSentForReview!")
