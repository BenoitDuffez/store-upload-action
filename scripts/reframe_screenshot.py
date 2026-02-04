import argparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Portrait dimensions (phone)
pw, ph = 1320, 2868
# Landscape dimensions (macbook)
lw, lh = 2880, 1800


def build_background(background: str, ellipse: str, is_landscape: bool):
    if is_landscape:
        w, h = lw, lh
    else:
        w, h = pw, ph
    
    img = Image.new("RGB", (w, h), background)
    draw = ImageDraw.Draw(img)

    if is_landscape:
        # Landscape arc positioning
        center = (w + 200, h + 300)
        radius = 2400
        # Shadow offset for landscape
        shadow_offset_x = 60
        shadow_offset_y = 80
        shadow_blur = 60
    else:
        # Portrait arc positioning
        center = (w + 800, h + 400)  # far bottom-right
        radius = 3200
        shadow_offset_x = 80
        shadow_offset_y = 100
        shadow_blur = 80

    # Big arc
    draw.ellipse(
        [center[0] - radius, center[1] - radius,
         center[0] + radius, center[1] + radius],
        fill=ellipse
    )

    # Shadow
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        [center[0] - radius + shadow_offset_x, center[1] - radius + shadow_offset_y,
         center[0] + radius + shadow_offset_x, center[1] + radius + shadow_offset_y],
        fill=(0, 0, 0, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(img)

    return img, draw


def add_screenshot_and_frame(img, app_screenshot, device_frame, is_landscape: bool):
    if is_landscape:
        w, h = lw, lh
        # Landscape positioning
        y_offset = 00
        app_width = 1737
        app_x = 510
        app_y = 318 + y_offset
        frame_width = 2500
        frame_height = 1800
        frame_x = 140
        frame_y = 00 + y_offset
        corner_radius = 5
    else:
        w, h = pw, ph
        # Portrait positioning (original)
        y_offset = 600
        app_width = 1160
        app_x = 85
        app_y = 130 + y_offset
        frame_width = 1260
        frame_height = 2788
        frame_x = 30
        frame_y = 68 + y_offset
        corner_radius = 180

    # App screenshot (smaller than frame, rounded corners)
    app = Image.open(app_screenshot).convert("RGBA")
    app_resized = app.resize((app_width, int(app.height * app_width / app.width)))

    mask = Image.new("L", app_resized.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), app_resized.size], radius=corner_radius, fill=255)
    app_rounded = Image.new("RGBA", app_resized.size)
    app_rounded.paste(app_resized, (0, 0), mask)

    img.paste(app_rounded, (app_x, app_y), app_rounded)

    # Device frame (larger)
    frame = Image.open(device_frame).convert("RGBA")
    frame_resized = frame.resize((frame_width, frame_height))
    img.paste(frame_resized, (frame_x, frame_y), frame_resized)


# Text overlay
def wrapped_text(draw, text, font, is_landscape: bool):
    if is_landscape:
        max_w = 2000
    else:
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


def draw_text(draw, text, outline: str, font, is_landscape: bool):
    wrapped = wrapped_text(draw, text, font, is_landscape)

    if is_landscape:
        w, h = lw, lh
        max_w = 2400  # wider for landscape
        font_size = 100  # smaller font for landscape
        y = 30
    else:
        w, h = pw, ph
        max_w = 1200
        font_size = 140  # original font size
        y = 50

    # Center wrapped text
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    x = (w - text_w) // 2

    # Outline
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx or dy:
                draw.multiline_text((x + dx, y + dy), wrapped, font=font, fill=outline, align="center")

    # Main text
    draw.multiline_text((x, y), wrapped, font=font, fill="#FFFFFF", align="center")


def pipeline(app_screenshot, device_frame, text, font, background: str, ellipse: str, outline: str):
    # Detect orientation from the input screenshot
    with Image.open(app_screenshot) as img:
        width, height = img.size
        is_landscape = width > height
    
    # Adjust font size based on orientation
    if is_landscape:
        font = ImageFont.truetype(font.path, 100) if hasattr(font, 'path') else font
    else:
        font = ImageFont.truetype(font.path, 140) if hasattr(font, 'path') else font
    
    img, draw = build_background(background, ellipse, is_landscape)
    add_screenshot_and_frame(img, app_screenshot, device_frame, is_landscape)
    draw_text(draw, text, outline, font, is_landscape)
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

    ttf = ImageFont.truetype(args.font, 140)

    pipeline(args.screenshot, args.device, args.text, ttf, args.background, args.ellipse, args.outline)
