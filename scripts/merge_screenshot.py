import argparse

from PIL import Image, ImageDraw


def merge_screenshot(app_screenshot_path: str, device_frame_path: str, output_path: str) -> None:
    app = Image.open(app_screenshot_path).convert("RGBA")
    frame = Image.open(device_frame_path).convert("RGBA")

    app_width = int(frame.width * 0.92)
    app_height = int(app.height * app_width / app.width)
    app_resized = app.resize((app_width, app_height))

    app_x = (frame.width - app_resized.width) // 2
    app_y = (frame.height - app_resized.height) // 2

    corner_radius = int(app_resized.width * 0.14)

    mask = Image.new("L", app_resized.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [(0, 0), app_resized.size],
        radius=corner_radius,
        fill=255,
    )

    app_rounded = Image.new("RGBA", app_resized.size, (0, 0, 0, 0))
    app_rounded.paste(app_resized, (0, 0), mask)

    output = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    output.paste(app_rounded, (app_x, app_y), app_rounded)
    output.paste(frame, (0, 0), frame)

    output.save(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Put an app screenshot into a device mockup."
    )

    parser.add_argument("app_screenshot", help="Path to the app screenshot PNG")
    parser.add_argument("device_frame", help="Path to the device mockup PNG")
    parser.add_argument("output_path", help="Path where the merged PNG will be saved")

    args = parser.parse_args()

    merge_screenshot(
        args.app_screenshot,
        args.device_frame,
        args.output_path,
    )