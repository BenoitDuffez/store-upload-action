import argparse
import sys
from pathlib import Path
import yaml

from android import publish_android
from apple import publish_ios, publish_macos


def parse_pubspec_version(pubspec_path: str) -> dict:
    with open(pubspec_path, "r") as f:
        data = yaml.safe_load(f)
    return {'name': data["version"].split("+")[0], 'code': data["version"].split("+")[1]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and upload Flutter app to stores")

    # android options
    parser.add_argument("--package_name", help="Android package name")
    parser.add_argument("--service_account_json", help="Google service account JSON")
    parser.add_argument("--track", default="production", help="Google Play track (comma-separated for multiple tracks)")
    parser.add_argument("--internal_testing", action="store_true", help="Also publish to internal testing track")
    parser.add_argument("--phone_dir", default="./metadata/en-US/images/phoneScreenshots",
                        help="Android phone screenshots dir")
    parser.add_argument("--tablet_dir", default="./metadata/en-US/images/macbookScreenshots",
                        help="Android tablet screenshots dir")

    # apple options
    parser.add_argument("--ios_bundle_id", help="iOS bundle ID")
    parser.add_argument("--macos_bundle_id", help="macOS bundle ID")
    parser.add_argument("--key_id", help="Apple API key ID")
    parser.add_argument("--issuer_id", help="Apple issuer ID")
    parser.add_argument("--p8_folder", help="Apple .p8 directory path")
    parser.add_argument("--macos_cert", help="macOS Apple '3rd Party Mac Developer Installer' certificate name")

    parser.add_argument("--iphone_dir", default="./metadata/en-US/images/iphoneScreenshots",
                        help="iOS iPhone screenshots dir (e.g., 6.5 inch)")
    parser.add_argument("--ipad_dir", default="./metadata/en-US/images/ipadScreenshots",
                        help="iOS iPad screenshots dir (e.g., 12.9 inch)")
    parser.add_argument("--macos_dir", default="./metadata/en-US/images/macbookScreenshots",
                        help="MacBook screenshots dir (e.g., 14 inch)")

    # common options
    parser.add_argument("--locale", default="en-US", help="Locale for metadata")

    args = parser.parse_args()

    version = parse_pubspec_version('pubspec.yaml')['name']
    version_code = parse_pubspec_version('pubspec.yaml')['code']

    exceptions = []

    # Android
    if args.package_name is None:
        print(f"Skipping Google Play publishing: no package ({args.package_name})")

    elif not Path(args.service_account_json).is_file():
        print(f"Skipping Google Play publishing: no credentials ({args.service_account_json})")

    else:
        # Handle multiple tracks
        tracks = [t.strip() for t in args.track.split(",")]
        if args.internal_testing and "internal" not in tracks:
            tracks.append("internal")
        
        try:
            publish_android(args.package_name, args.service_account_json, args.phone_dir, args.tablet_dir, tracks,
                            args.locale, version_code)
        except Exception as e:
            print(f"Failed Google Play publishing: {e}")
            if "This edit has already been successfully committed, please create a new Edit." in str(e):
                print("Ignoring this error success.")
            else:
                exceptions.append(e)

    # Apple
    p8 = f"{args.p8_folder}/AuthKey_{args.key_id}.p8"
    if not Path(p8).is_file():
        print(f"Skipping Apple Store publishing: no credentials ({p8})")
    else:
        if args.ios_bundle_id is None:
            print(f"Skipping iOS App Store publishing: no Bundle ID ({args.ios_bundle_id})")

        else:
            try:
                publish_ios(args.ios_bundle_id, args.key_id, args.issuer_id, args.p8_folder, version,
                            [args.iphone_dir, args.ipad_dir], args.locale)
            except Exception as e:
                print(f"Failed iOS App Store publishing: {e}")
                exceptions.append(e)

        if args.macos_bundle_id is None:
            print(f"Skipping macOS App Store publishing: no Bundle ID ({args.macos_bundle_id})")

        else:
            try:
                publish_macos(args.macos_bundle_id, args.key_id, args.issuer_id, args.p8_folder, version, [args.macos_dir],
                              args.macos_cert, args.locale)
            except Exception as e:
                print(f"Failed macOS App Store publishing: {e}")
                exceptions.append(e)

    if len(exceptions) > 0:
        print("Errors happened!")
        for e in exceptions:
            print(e)
        sys.exit(1)
