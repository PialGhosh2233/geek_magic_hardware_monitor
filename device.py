"""HTTP client for the GeekMagic SmallTV-Ultra stock firmware.

Usage: python device.py <ip> [image.jpg]   -> probes the device and uploads the image.
"""
import sys

import requests

UPLOAD_DIR = "/image/"


def probe(ip, timeout=3.0):
    """Return the device's /v.json (model + firmware) or raise."""
    r = requests.get(f"http://{ip}/v.json", timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text.strip()}


def upload(ip, path, name, timeout=10.0):
    """Upload a JPEG to /image/<name>, overwriting any previous file with that name."""
    with open(path, "rb") as fh:
        # Query strings are built by hand: the stock firmware is known to accept the
        # raw "/image/" form and community scripts send it unencoded.
        r = requests.post(
            f"http://{ip}/doUpload?dir={UPLOAD_DIR}",
            files={"file": (name, fh, "image/jpeg")},
            timeout=timeout,
        )
    r.raise_for_status()
    return r


def select_image(ip, name, timeout=5.0):
    """Make /image/<name> the picture currently displayed."""
    r = requests.get(f"http://{ip}/set?img={UPLOAD_DIR}{name}", timeout=timeout)
    r.raise_for_status()
    return r


def set_theme(ip, theme=3, timeout=5.0):
    """Theme 3 = picture/album display on the Ultra."""
    r = requests.get(f"http://{ip}/set?theme={theme}", timeout=timeout)
    r.raise_for_status()
    return r


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python device.py <device-ip> [image.jpg]")
    ip = sys.argv[1]
    print("device:", probe(ip))
    if len(sys.argv) > 2:
        img = sys.argv[2]
        upload(ip, img, "monitor.jpg")
        set_theme(ip, 3)
        select_image(ip, "monitor.jpg")
        print(f"uploaded {img} as /image/monitor.jpg and selected it")
