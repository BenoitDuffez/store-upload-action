import time

import jwt
import requests
from typing import Dict
import os, hashlib
import glob
import subprocess

API_BASE = "https://api.appstoreconnect.apple.com/v1"
POLL_WAIT = 0.5
POLL_RETRIES = 10


########################################################################################################################

def publish_ios(bundle_id: str, key_id: str, issuer_id: str, p8_folder: str, version: str, iphone_dir: str,
                ipad_dir: str, locale: str) -> None:
    print("#########################################################")
    print("# iOS                                                   #")
    print("#########################################################")
    return
    os.environ["API_PRIVATE_KEYS_DIR"] = os.path.relpath(p8_folder)
    ipa_path = build_ipa()
    upload_ipa_to_apple(ipa_path, key_id, issuer_id)

    jwt_token = generate_jwt(key_id, issuer_id, f"{p8_folder}/AuthKey_{key_id}.p8")
    headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
    app_id = get_app_id(bundle_id, headers)
    version_id = get_or_create_version(app_id, version, headers, "IOS")
    upload_screenshots_to_apple(version_id, iphone_dir, ipad_dir, locale, jwt_token)

    print("iOS builds were uploaded, but they will not appear directly in AppStore Connect")
    print("Wait for the confirmation email before you can submit the app for approval from Apple")


########################################################################################################################

def build_ipa():
    print("Building IPA")
    subprocess.run(["flutter", "build", "ipa", "--release"], check=True)
    return glob.glob("build/ios/ipa/*.ipa")[0]


def upload_ipa_to_apple(ipa_path: str, api_key: str, api_issuer: str):
    print(f"Uploading IPA '{ipa_path}' to Apple")
    subprocess.run(
        ["xcrun", "altool",
         "--upload-app", "-f", ipa_path,
         "--platform", "ios",
         "--apiKey", api_key,
         "--apiIssuer", api_issuer],
        check=True)


def generate_jwt(key_id: str, issuer_id: str, p8_path: str) -> str:
    print("Generating JWT for Apple")
    with open(p8_path, "r") as f:
        private_key = f.read()
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {"iss": issuer_id, "exp": int(time.time() + 1200), "aud": "appstoreconnect-v1"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=header)


def get_app_id(bundle_id: str, headers: Dict) -> str:
    print("Getting App ID")
    response = requests.get(f"{API_BASE}/apps?filter[bundleId]={bundle_id}", headers=headers)
    response.raise_for_status()
    return response.json()["data"][0]["id"]


def get_or_create_version(app_id: str, version: str, headers: Dict, platform: str) -> str:
    print(f"Getting/creating Apple Version from App ID '{app_id}' / Version '{version}'")

    # Check existing
    response = requests.get(f"{API_BASE}/apps/{app_id}/appStoreVersions",
                            headers=headers)
    response.raise_for_status()
    json = response.json()
    print(f"get existing? {json}")
    if json["data"]:
        for release in json["data"]:
            if release["attributes"]["platform"] == platform and release["attributes"]["versionString"] == version:
                print(f"Apple Version already exists: {release['id']}")
                return release["id"]

    # Create
    print(f"Creating Apple Version {version} for {app_id}")
    body = {
        "data": {
            "type": "appStoreVersions",
            "attributes": {"platform": platform, "versionString": version},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}}
        }
    }

    url = f"{API_BASE}/appStoreVersions"
    print(f"Create version: POST {url} with body: {body}")
    response = requests.post(url, json=body, headers=headers)
    if response.status_code >= 400:
        print(f"Failed to create version: {response.status_code} = {response.text}")
    response.raise_for_status()
    version_id = response.json()["data"]["id"]
    print(f"Created version: {version_id}")
    return version_id


########################################################################################################################

def get_localization(version_id: str, locale: str, headers: Dict) -> str:
    response = requests.get(
        f"{API_BASE}/appStoreVersions/{version_id}/appStoreVersionLocalizations?filter[locale]={locale}",
        headers=headers)
    response.raise_for_status()
    data = response.json()["data"]
    if data:
        return data[0]["id"]
    # Create if not
    body = {
        "data": {
            "type": "appStoreVersionLocalizations",
            "attributes": {"locale": locale},
            "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}}
        }
    }
    response = requests.post(f"{API_BASE}/appStoreVersionLocalizations", json=body, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["id"]


def get_screenshot_set(loc_id: str, display_type: str, headers: Dict) -> str | None:
    url = f"{API_BASE}/appStoreVersionLocalizations/{loc_id}/appScreenshotSets"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        # helpful debug: return raw payload when empty so caller can log it if needed
        # (caller may choose to print it)
        return None
    for item in data:
        attrs = item.get("attributes", {})
        if attrs.get("screenshotDisplayType") == display_type:
            return item["id"]
    return None


def create_screenshot_set(loc_id: str, display_type: str, headers: Dict) -> str:
    body = {
        "data": {
            "type": "appScreenshotSets",
            "attributes": {"screenshotDisplayType": display_type},
            "relationships": {
                "appStoreVersionLocalization": {
                    "data": {"type": "appStoreVersionLocalizations", "id": loc_id}
                }
            }
        }
    }
    response = requests.post(f"{API_BASE}/appScreenshotSets", json=body, headers=headers)
    # If conflict, raise here and let caller handle (caller will re-fetch)
    response.raise_for_status()
    return response.json()["data"]["id"]


def get_or_create_screenshot_set(loc_id: str, display_type: str, headers: Dict) -> str:
    existing = get_screenshot_set(loc_id, display_type, headers)
    if existing:
        return existing

    # Try to create; if we get 409, re-fetch (race or existing)
    try:
        return create_screenshot_set(loc_id, display_type, headers)
    except requests.exceptions.HTTPError as e:
        resp = getattr(e, "response", None)
        if resp is not None and resp.status_code == 409:
            # another source created it — re-fetch and return id
            existing = get_screenshot_set(loc_id, display_type, headers)
            if existing:
                return existing
            # if still None, raise original error for debugging
        raise


def list_screenshots_in_set(set_id: str, headers: Dict) -> list:
    url = f"{API_BASE}/appScreenshotSets/{set_id}/appScreenshots"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", [])


def clear_screenshot_set(set_id: str, headers: Dict, poll_retries: int = POLL_RETRIES, poll_wait: float = POLL_WAIT):
    # delete each screenshot found, then poll until empty (or timeout)
    snaps = list_screenshots_in_set(set_id, headers)
    for shot in snaps:
        shot_id = shot["id"]
        del_url = f"{API_BASE}/appScreenshots/{shot_id}"
        print(f"Deleting screenshot {shot_id} in set {set_id}")
        d = requests.delete(del_url, headers=headers)
        d.raise_for_status()

    # poll until empty
    for i in range(poll_retries):
        snaps = list_screenshots_in_set(set_id, headers)
        if not snaps:
            return
        time.sleep(poll_wait)
    # final check, if still not empty raise
    snaps = list_screenshots_in_set(set_id, headers)
    if snaps:
        raise RuntimeError(f"Timed out waiting for screenshot set {set_id} to be cleared (remaining: {len(snaps)})")


def upload_screenshot_to_apple(set_id: str, file_path: str, headers: Dict):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    md5 = hashlib.md5(data).hexdigest()

    # Reserve
    body = {
        "data": {
            "type": "appScreenshots",
            "attributes": {"fileSize": file_size, "fileName": file_name},
            "relationships": {
                "appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": set_id}}
            }
        }
    }
    response = requests.post(f"{API_BASE}/appScreenshots", json=body, headers=headers)
    response.raise_for_status()
    res_data = response.json()["data"]
    screenshot_id = res_data["id"]
    upload_ops = res_data["attributes"]["uploadOperations"]

    # Upload parts
    for op in upload_ops:
        url = op["url"]
        method = op["method"]
        offset = op.get("offset", 0)
        length = op.get("length", len(data) - offset)
        chunk = data[offset:offset + length]
        req_headers = {h["name"]: h["value"] for h in op.get("requestHeaders", [])}
        requests.request(method, url, data=chunk, headers=req_headers).raise_for_status()

    # Commit
    body = {
        "data": {
            "type": "appScreenshots",
            "id": screenshot_id,
            "attributes": {"uploaded": True, "sourceFileChecksum": md5}
        }
    }
    requests.patch(f"{API_BASE}/appScreenshots/{screenshot_id}", json=body, headers=headers).raise_for_status()


def upload_screenshots_to_apple(version_id: str, iphone_dir: str, ipad_dir: str, locale: str, jwt_token: str):
    headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
    loc_id = get_localization(version_id, locale, headers)

    print("Working on iPhone screenshots for version", version_id)
    if os.path.exists(iphone_dir):
        display_type = "APP_IPHONE_67"
        # find or create (handles 409)
        set_id = get_or_create_screenshot_set(loc_id, display_type, headers)

        # clear set (delete all existing screenshots then wait until empty)
        clear_screenshot_set(set_id, headers)

        # upload files in deterministic order if you care about ordering
        files = [f for f in os.listdir(iphone_dir) if f.lower().endswith((".png", ".jpg"))]
        files.sort()
        for file in files:
            print(f"Uploading screenshot: {file}")
            upload_screenshot_to_apple(set_id, os.path.join(iphone_dir, file), headers)
    else:
        print(f"No iPhone screenshots found at {iphone_dir}")

    print("Working on iPad screenshots for version", version_id)
    if os.path.exists(ipad_dir):
        display_type = "APP_IPAD_PRO_3GEN_129"
        set_id = get_or_create_screenshot_set(loc_id, display_type, headers)
        clear_screenshot_set(set_id, headers)
        files = [f for f in os.listdir(ipad_dir) if f.lower().endswith((".png", ".jpg"))]
        files.sort()
        for file in files:
            print(f"Uploading screenshot: {file}")
            upload_screenshot_to_apple(set_id, os.path.join(ipad_dir, file), headers)
    else:
        print(f"No iPad screenshots found at {ipad_dir}")
