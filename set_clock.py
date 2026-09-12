"""Switch the GeekMagic to its clock theme (off_theme in config.json, default 4 = Time Style 1).

    python set_clock.py        # clock
    python set_clock.py 3      # any theme number, e.g. 3 = back to the photo album / dashboard

Used by the "GeekMagic Clock On Shutdown" scheduled task; handy for manual use too.
"""
import json
import os
import sys

import device

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    cfg = json.load(f)
theme = int(sys.argv[1]) if len(sys.argv) > 1 else int(cfg.get("off_theme", 4))
ip = cfg["device_ip"]
device.set_theme(ip, theme, timeout=3.0)
print(f"device {ip}: theme {theme} set")
