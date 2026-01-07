import argparse
from pathlib import Path
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

w, h = 1320, 2868


def build_background(background: str, ellipse: str):
    img = Image.new("RGB", (w, h), background)
    draw = ImageDraw.Draw(img)

    # Big arc from bottom-right
    center = (w + 800, h + 400)  # far bottom-right
    radius = 3200
    draw.ellipse(
        [center[0] - radius, center[1] - radius,
         center[0] + radius, center[1] + radius],
        fill=ellipse
    )

    # Shadow
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        [center[0] - radius + 80, center[1] - radius + 100,
         center[0] + radius + 80, center[1] + radius + 100],
        fill=(0, 0, 0, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(80))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(img)

    return img, draw


def add_screenshot_and_frame(img, app_screenshot, device_frame):
    # Lower position
    y_offset = 600

    # App screenshot (smaller than frame, rounded corners)
    app = Image.open(app_screenshot).convert("RGBA")
    app_width = 1160
    app_resized = app.resize((app_width, int(app.height * app_width / app.width)))

    mask = Image.new("L", app_resized.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), app_resized.size], radius=180, fill=255)
    app_rounded = Image.new("RGBA", app_resized.size)
    app_rounded.paste(app_resized, (0, 0), mask)

    img.paste(app_rounded, (85, 130 + y_offset), app_rounded)

    # iPhone frame (larger)
    frame = Image.open(device_frame).convert("RGBA")
    frame_resized = frame.resize((1260, 2788))
    img.paste(frame_resized, (30, 68 + y_offset), frame_resized)


# Text overlay
def wrapped_text(draw, text, font):
    max_w = 1200
    lines = []
    words = text.split()
    current = ""
    for word in words:
        test = current + (" " if current else "") + word
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def draw_text(draw, text, outline: str, font):
    wrapped = wrapped_text(draw, text, font)

    # Center wrapped text
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    x = (w - text_w) // 2
    y = 50

    # Outline
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx or dy:
                draw.multiline_text((x + dx, y + dy), wrapped, font=font, fill=outline, align="center")

    # Main text
    draw.multiline_text((x, y), wrapped, font=font, fill="#FFFFFF", align="center")


def pipeline(app_screenshot, device_frame, text, font, background: str, ellipse: str, outline: str):
    img, draw = build_background(background, ellipse)
    add_screenshot_and_frame(img, app_screenshot, device_frame)
    draw_text(draw, text, outline, font)
    img.save(app_screenshot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and upload Flutter app to stores")

    parser.add_argument("--screenshot", required=True, help="App screenshot")
    parser.add_argument("--device", required=True, help="Device frame")
    parser.add_argument("--text", required=True, help="Text to insert")
    parser.add_argument("--font", required=True, help="Font to use")
    parser.add_argument("--background", required=True, help="Background color")
    parser.add_argument("--ellipse", required=True, help="Ellipse color")
    parser.add_argument("--outline", required=True, help="Outline color")

    args = parser.parse_args()

    font = ImageFont.truetype(args.font, 140)

    pipeline(args.screenshot, args.device, args.text, font, args.background, args.ellipse, args.outline)
