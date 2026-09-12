"""Render the 240x240 dashboard image for the GeekMagic display.

Run directly to write preview.jpg with sample values.
"""
import io
import os
import time

from PIL import Image, ImageDraw, ImageFont

SIZE = 240
FONT_DIR = r"C:\Windows\Fonts"
BG = (12, 12, 16)
FG = (235, 235, 235)
DIM = (140, 140, 150)
TRACK = (40, 40, 48)


def _font(names, size):
    for n in names:
        p = os.path.join(FONT_DIR, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_LABEL = _font(["segoeui.ttf", "arial.ttf"], 15)
F_VALUE = _font(["segoeuib.ttf", "arialbd.ttf"], 19)
F_SMALL = _font(["segoeui.ttf", "arial.ttf"], 13)

ROWS = [
    # key, label, unit, (warn, crit)
    ("cpu_temp", "CPU temp", "°C", (60, 80)),
    ("cpu_load", "CPU usage", "%", (60, 85)),
    ("gpu_temp", "GPU temp", "°C", (60, 80)),
    ("gpu_load", "GPU usage", "%", (60, 85)),
    ("ram_pct", "RAM", "%", (70, 90)),
]


def _colour(value, warn, crit):
    if value is None:
        return DIM
    if value >= crit:
        return (235, 70, 70)
    if value >= warn:
        return (240, 190, 50)
    return (70, 200, 110)


def render(metrics, clock=True):
    """Return a PIL Image (RGB, 240x240) for the given metrics dict."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)

    top = 6
    if clock:
        d.text((8, top), "PC MONITOR", font=F_SMALL, fill=DIM)
        t = time.strftime("%I:%M %p").lstrip("0")  # 12-hour, e.g. "3:07 PM"
        w = d.textlength(t, font=F_SMALL)
        d.text((SIZE - 8 - w, top), t, font=F_SMALL, fill=DIM)
        top += 20
    if not metrics.get("lhm_ok", True):
        d.text((8, top), "sensors offline", font=F_SMALL, fill=(235, 70, 70))

    rows = ROWS
    if metrics.get("lhm_ok"):
        # Sensors are being read fine, so a missing GPU value means the hardware has no such
        # sensor (no GPU at all, or an integrated GPU without a temperature sensor): drop the row.
        rows = [r for r in ROWS if not (r[0].startswith("gpu") and metrics.get(r[0]) is None)]
    row_h = (SIZE - top - 4) // len(rows)
    y = top + 2
    for key, label, unit, (warn, crit) in rows:
        v = metrics.get(key)
        colour = _colour(v, warn, crit)
        d.text((8, y), label, font=F_LABEL, fill=FG)
        if key == "ram_pct" and metrics.get("ram_used_gb") is not None:
            txt = f"{v:.0f}%  {metrics['ram_used_gb']:.1f}/{metrics['ram_total_gb']:.0f}G" if v is not None else "--"
        elif key == "gpu_load" and metrics.get("gpu_vram_used_gb") is not None:
            txt = f"{v:.0f}% ({metrics['gpu_vram_used_gb']:.1f}GB)" if v is not None else "--"
        else:
            txt = f"{v:.0f}{unit}" if v is not None else "--"
        w = d.textlength(txt, font=F_VALUE)
        d.text((SIZE - 8 - w, y - 3), txt, font=F_VALUE, fill=colour)
        # bar
        by = y + min(28, row_h - 12)  # bar sits just under the text, whatever the row height
        d.rounded_rectangle((8, by, SIZE - 8, by + 7), radius=3, fill=TRACK)
        if v is not None:
            scale = 100.0 if unit == "%" else 100.0  # temps drawn on a 0-100 °C scale
            fill_w = max(0, min(1.0, v / scale)) * (SIZE - 16)
            if fill_w > 6:
                d.rounded_rectangle((8, by, 8 + fill_w, by + 7), radius=3, fill=colour)
        y += row_h
    return img


def render_jpeg_bytes(metrics, quality=80):
    buf = io.BytesIO()
    render(metrics).save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    sample = {
        "cpu_temp": 47, "cpu_load": 23, "gpu_temp": 66, "gpu_load": 91, "gpu_vram_used_gb": 10.2,
        "ram_pct": 58, "ram_used_gb": 9.3, "ram_total_gb": 16, "lhm_ok": True,
    }
    data = render_jpeg_bytes(sample)
    with open("preview.jpg", "wb") as f:
        f.write(data)
    print(f"wrote preview.jpg ({len(data)} bytes)")
    sample.update(gpu_temp=None, gpu_load=None)
    with open("preview_nogpu.jpg", "wb") as f:
        f.write(render_jpeg_bytes(sample))
    print("wrote preview_nogpu.jpg (layout for a PC without a GPU)")
