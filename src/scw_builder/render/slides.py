from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from scw_builder.manifest import BeatManifest, Manifest


SIZE_BY_ASPECT = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}
THEME_COLORS = {
    "bg": "#0b0d10",
    "text": "#f2f2f2",
    "muted": "#a7adb5",
    "panel": (0, 0, 0, 140),
    "burnt_red": "#d14a3a",
    "brassy_gold": "#caa44a",
    "cold_blue": "#3a7bd5",
}


def render_slides(manifest: Manifest, slides_dir: Path) -> list[Path]:
    slides_dir.mkdir(parents=True, exist_ok=True)
    size = SIZE_BY_ASPECT.get(manifest.aspect, SIZE_BY_ASPECT["16:9"])
    templates = _load_templates(Path(manifest.build_dir).parents[1] / "templates")
    fonts = _load_fonts()
    output_paths: list[Path] = []

    for index, beat in enumerate(manifest.beats, start=1):
        image = _render_beat(manifest, beat, size, templates, fonts, index)
        path = slides_dir / f"{index:04d}.png"
        image.save(path)
        output_paths.append(path)

    return output_paths


def _render_beat(manifest, beat, size, templates, fonts, index) -> Image.Image:
    base = _render_background(manifest, beat, size, templates, index)
    graded = _apply_noir_grade(base, beat.noir, beat.beat_type, beat.beat_id)
    canvas = graded.convert("RGBA")
    canvas = _apply_panel_layer(canvas, manifest, beat)
    canvas = _apply_text_layers(canvas, manifest, beat, templates, fonts)
    canvas = _apply_timestamp(canvas, manifest, beat, fonts)
    return canvas.convert("RGB")


def _render_background(manifest, beat, size, templates, index) -> Image.Image:
    if beat.beat_type == "map" or beat.beat_type == "map_move":
        return _render_map_move(manifest, beat, size, templates)
    if beat.beat_type == "quote_card":
        return Image.new("RGB", size, color=THEME_COLORS["bg"])
    if beat.beat_type == "montage":
        return _render_montage(manifest, beat, size, index)
    if beat.beat_type == "doc_scan":
        return _render_doc_scan(manifest, beat, size, index)
    if beat.beat_type == "archival_clip":
        return _render_archival_clip(manifest, beat, size, index)
    return _render_still_background(beat, size, index)


def _render_montage(manifest, beat, size, index) -> Image.Image:
    canvas = Image.new("RGB", size, color=THEME_COLORS["bg"])
    montage = beat.montage or {}
    cuts = int(montage.get("cuts", 5))
    gutter = 18
    columns = min(cuts, max(1, len(beat.assets) or 1))
    panel_width = (size[0] - gutter * (columns + 1)) // columns
    for asset_index in range(columns):
        box = (
            gutter + asset_index * (panel_width + gutter),
            110,
            gutter + asset_index * (panel_width + gutter) + panel_width,
            size[1] - 180,
        )
        frame = _asset_frame(beat, box[2] - box[0], box[3] - box[1], asset_index, index)
        canvas.paste(frame, (box[0], box[1]))
        ImageDraw.Draw(canvas).rectangle(box, outline=THEME_COLORS[manifest.accent_color], width=4)
    return canvas


def _render_still_background(beat, size, index) -> Image.Image:
    frame = _asset_frame(beat, size[0], size[1], 0, index)
    return frame


def _render_doc_scan(manifest, beat, size, index) -> Image.Image:
    frame = _asset_frame(beat, int(size[0] * 0.74), int(size[1] * 0.74), 0, index)
    frame = frame.rotate(-3, expand=True, fillcolor=THEME_COLORS["bg"])
    canvas = Image.new("RGB", size, color=THEME_COLORS["bg"])
    offset = ((size[0] - frame.width) // 2, (size[1] - frame.height) // 2)
    canvas.paste(frame, offset)
    return canvas


def _render_archival_clip(manifest, beat, size, index) -> Image.Image:
    canvas = Image.new("RGB", size, color="#090909")
    draw = ImageDraw.Draw(canvas)
    frame_box = [150, 110, size[0] - 150, size[1] - 190]
    draw.rectangle(frame_box, outline=THEME_COLORS[manifest.accent_color], width=5)
    draw.rectangle(
        [frame_box[0] + 24, frame_box[1] + 24, frame_box[2] - 24, frame_box[3] - 24],
        fill="#15181d",
    )
    for x in range(frame_box[0] + 26, frame_box[2] - 20, 70):
        draw.rectangle([x, frame_box[1] - 18, x + 36, frame_box[1] + 2], fill=THEME_COLORS["text"])
        draw.rectangle([x, frame_box[3] - 2, x + 36, frame_box[3] + 18], fill=THEME_COLORS["text"])
    return canvas


def _render_map_move(manifest, beat, size, templates) -> Image.Image:
    canvas = Image.new("RGB", size, color="#11161d")
    draw = ImageDraw.Draw(canvas, "RGBA")
    template = templates.get("map_frame", {})
    outline_points = _normalize_polygon(template.get("outline", []))
    regions = template.get("regions", {})
    cities = template.get("cities", {})

    draw.rectangle([180, 120, size[0] - 180, size[1] - 180], outline="#293240", width=2)
    if outline_points:
        draw.polygon(outline_points, fill=(28, 32, 38, 255), outline="#39414d")
    for name, points in regions.items():
        normalized_points = _normalize_polygon(points)
        if not normalized_points:
            continue
        fill = (54, 58, 64) if name not in beat.highlights else _hex_rgba(THEME_COLORS[manifest.accent_color], 150)
        outline = "#515763" if name not in beat.highlights else THEME_COLORS[manifest.accent_color]
        draw.polygon(normalized_points, fill=fill, outline=outline)

    for arrow in beat.arrows:
        start = _normalize_point(cities.get(arrow.get("from")))
        end = _normalize_point(cities.get(arrow.get("to")))
        if not start or not end:
            continue
        _draw_arrow(draw, start, end, THEME_COLORS[manifest.accent_color])
        label = arrow.get("label")
        if label:
            draw.text(((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 - 30), label.upper(), fill=THEME_COLORS["text"])

    for label in beat.labels:
        at = _normalize_point(cities.get(label.get("at")))
        if not at:
            continue
        draw.ellipse([at[0] - 6, at[1] - 6, at[0] + 6, at[1] + 6], fill=THEME_COLORS[manifest.accent_color])
        draw.text((at[0] + 16, at[1] - 16), str(label.get("text", "")).upper(), fill=THEME_COLORS["text"])
    return canvas


def _asset_frame(beat: BeatManifest, width: int, height: int, asset_index: int, seed_offset: int) -> Image.Image:
    image_assets = [asset for asset in beat.assets if asset.media_type == "image" and Path(asset.local_filepath).exists()]
    asset = image_assets[asset_index % len(image_assets)] if image_assets else None
    if asset and asset.mime_type in {"image/jpeg", "image/png"}:
        with Image.open(asset.local_filepath) as source:
            return ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    fallback = Image.new("RGB", (width, height), color=_background(seed_offset))
    draw = ImageDraw.Draw(fallback)
    draw.line((0, height, width, 0), fill="#1f2530", width=4)
    draw.line((0, 0, width, height), fill="#1f2530", width=4)
    return fallback


def _apply_noir_grade(image: Image.Image, noir: dict, beat_type: str, seed_value: str) -> Image.Image:
    grayscale = ImageOps.grayscale(image).convert("RGB")
    if beat_type == "map_move":
        grayscale = ImageEnhance.Contrast(grayscale).enhance(1.25)
    else:
        grayscale = ImageEnhance.Contrast(grayscale).enhance(1.7)
        grayscale = ImageEnhance.Sharpness(grayscale).enhance(1.2)
    grain = float(noir.get("grain", 0.05))
    vignette = float(noir.get("vignette", 0.08))
    graded = _overlay_grain(grayscale, seed_value, grain)
    return _overlay_vignette(graded, vignette)


def _apply_panel_layer(canvas: Image.Image, manifest: Manifest, beat: BeatManifest) -> Image.Image:
    panel = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel, "RGBA")
    margin = manifest.safe_margin_px
    if beat.beat_type == "quote_card":
        box = [margin, canvas.size[1] * 0.18, canvas.size[0] * 0.68, canvas.size[1] * 0.78]
    else:
        box = [margin, canvas.size[1] - 280, canvas.size[0] * 0.62, canvas.size[1] - margin]
    draw.rectangle(box, fill=THEME_COLORS["panel"])
    return Image.alpha_composite(canvas, panel)


def _apply_text_layers(canvas, manifest, beat, templates, fonts):
    draw = ImageDraw.Draw(canvas)
    accent = THEME_COLORS[manifest.accent_color]
    margin = manifest.safe_margin_px
    max_width = int(canvas.size[0] * 0.60)
    x = margin + 24
    if beat.beat_type == "quote_card":
        _draw_quote_card(draw, beat, fonts, x, int(canvas.size[1] * 0.22), max_width, accent)
    else:
        _draw_headline(draw, beat, fonts, x, canvas.size[1] - 240, max_width, accent)
        if beat.lower_third:
            _draw_lower_third(draw, beat.lower_third, templates.get("lower_thirds", {}), fonts, x, canvas.size[1] - 172, accent)
    return canvas


def _apply_timestamp(canvas, manifest, beat, fonts):
    draw = ImageDraw.Draw(canvas)
    if beat.caption:
        draw.text(
            (manifest.safe_margin_px + 24, canvas.size[1] - 60),
            beat.caption.upper(),
            fill=THEME_COLORS["muted"],
            font=fonts["body"],
        )
    return canvas


def _draw_headline(draw, beat, fonts, x, y, max_width, accent):
    lines = beat.overlays or [beat.beat_id.replace("_", " ")]
    body = " ".join(lines[:2]).upper()
    wrapped = _wrap_text(body, 24)
    offset_y = y
    for line in wrapped:
        draw.text((x, offset_y), line, fill=THEME_COLORS["text"], font=fonts["headline"])
        offset_y += 42
    if beat.source:
        draw.text((x, offset_y + 12), beat.source.upper(), fill=THEME_COLORS["muted"], font=fonts["body"])
    draw.rectangle([x, y - 24, x + 120, y - 12], fill=accent)


def _draw_lower_third(draw, lower_third, template, fonts, x, y, accent):
    name = str(lower_third.get("name", "")).upper()
    subtitle = str(lower_third.get("subtitle", ""))
    draw.text((x, y), name, fill=THEME_COLORS["text"], font=fonts["headline"])
    draw.text((x, y + 44), subtitle, fill=THEME_COLORS["muted"], font=fonts["body"])
    draw.rectangle([x - 18, y, x - 6, y + 72], fill=accent)


def _draw_quote_card(draw, beat, fonts, x, y, max_width, accent):
    quote = (beat.quote or "NO QUOTE PROVIDED").strip()
    source = (beat.source or "").upper()
    accent_word = (beat.accent_word or "").strip().lower()
    wrapped = _wrap_text(quote, 32)
    offset_y = y
    for line in wrapped:
        words = line.split(" ")
        cursor_x = x
        for word in words:
            fill = accent if accent_word and accent_word in word.lower().strip(".,") else THEME_COLORS["text"]
            draw.text((cursor_x, offset_y), f"{word} ", fill=fill, font=fonts["quote"])
            cursor_x += int(draw.textlength(f"{word} ", font=fonts["quote"]))
        offset_y += 56
    if source:
        draw.text((x, offset_y + 24), source, fill=THEME_COLORS["muted"], font=fonts["body"])


def _load_fonts():
    return {
        "headline": ImageFont.load_default(),
        "body": ImageFont.load_default(),
        "quote": ImageFont.load_default(),
    }


def _load_templates(template_dir: Path) -> dict:
    templates = {}
    for path in template_dir.glob("*.json"):
        templates[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return templates


def _background(index: int) -> tuple[int, int, int]:
    palette = [
        (11, 13, 16),
        (17, 20, 26),
        (21, 15, 15),
        (18, 20, 14),
    ]
    return palette[(index - 1) % len(palette)]


def _overlay_grain(image: Image.Image, seed_value: str, opacity: float) -> Image.Image:
    if opacity <= 0:
        return image
    rng = random.Random(seed_value)
    noise = Image.new("L", image.size)
    pixels = noise.load()
    for y in range(0, image.size[1], 2):
        for x in range(0, image.size[0], 2):
            value = rng.randint(96, 160)
            pixels[x, y] = value
            if x + 1 < image.size[0]:
                pixels[x + 1, y] = value
            if y + 1 < image.size[1]:
                pixels[x, y + 1] = value
    noise = noise.filter(ImageFilter.GaussianBlur(radius=0.4))
    grain_rgb = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(image, grain_rgb, min(max(opacity, 0.0), 0.12))


def _overlay_vignette(image: Image.Image, opacity: float) -> Image.Image:
    if opacity <= 0:
        return image
    vignette = Image.new("L", image.size, 255)
    draw = ImageDraw.Draw(vignette)
    for inset in range(0, min(image.size) // 2, 24):
        alpha = max(0, 255 - inset // 2)
        draw.rectangle(
            [inset, inset, image.size[0] - inset, image.size[1] - inset],
            outline=alpha,
            width=24,
        )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=64))
    black = Image.new("RGB", image.size, "black")
    return Image.composite(Image.blend(image, black, opacity), image, ImageOps.invert(vignette))


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        proposal = " ".join(current + [word])
        if len(proposal) > width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines[:5]


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    draw.line([start, end], fill=color, width=5)
    arrow_size = 18
    direction = (end[0] - start[0], end[1] - start[1])
    norm = max((direction[0] ** 2 + direction[1] ** 2) ** 0.5, 1)
    ux, uy = direction[0] / norm, direction[1] / norm
    left = (end[0] - ux * arrow_size - uy * arrow_size / 2, end[1] - uy * arrow_size + ux * arrow_size / 2)
    right = (end[0] - ux * arrow_size + uy * arrow_size / 2, end[1] - uy * arrow_size - ux * arrow_size / 2)
    draw.polygon([end, left, right], fill=color)


def _hex_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _normalize_polygon(points) -> list[tuple[int, int]]:
    normalized: list[tuple[int, int]] = []
    if not isinstance(points, list):
        return normalized
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        try:
            normalized.append((int(point[0]), int(point[1])))
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_point(point) -> tuple[int, int] | None:
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        return None
    try:
        return (int(point[0]), int(point[1]))
    except (TypeError, ValueError):
        return None
