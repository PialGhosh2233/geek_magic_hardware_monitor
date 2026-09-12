"""Main loop: read sensors -> render 240x240 JPEG -> upload to the GeekMagic Ultra.

    python monitor.py            # uses config.json next to this file
"""
import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import psutil

import device
import discover
import render
import sensors
import session_hooks

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
LOG = os.path.join(HERE, "monitor.log")


def setup_logging():
    log = logging.getLogger("monitor")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler(LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if sys.stdout is not None:  # pythonw has no console
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    return log


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("refresh_seconds", 5)
    cfg.setdefault("lhm_url", sensors.DEFAULT_LHM_URL)
    cfg.setdefault("jpeg_quality", 80)
    cfg.setdefault("image_name", "monitor.jpg")
    cfg.setdefault("device_mac", "")
    cfg.setdefault("auto_discover", True)
    cfg.setdefault("off_theme", 4)  # 4/5/6 = Time Style 1/2/3, 7 = Simple Weather Clock
    return cfg


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def rediscover(cfg, log):
    """Scan the LAN for the device; update cfg (and config.json) if found. Returns new ip or None."""
    log.info("scanning the local network for the GeekMagic device...")
    d = discover.find_device(cfg.get("device_mac") or None)
    if not d:
        log.warning("no GeekMagic device found on the network")
        return None
    changed = d["ip"] != cfg.get("device_ip") or (d["mac"] and d["mac"] != cfg.get("device_mac"))
    cfg["device_ip"] = d["ip"]
    if d["mac"]:
        cfg["device_mac"] = d["mac"]
    if changed:
        save_config(cfg)
    log.info("found %s %s at %s (mac %s)", d["model"], d["version"], d["ip"], d["mac"] or "?")
    return d["ip"]


def main():
    log = setup_logging()
    cfg = load_config()
    ip = cfg.get("device_ip", "").strip()
    if cfg["auto_discover"]:
        reachable = False
        if ip:
            try:
                device.probe(ip)
                reachable = True
            except Exception as e:
                log.warning("saved device_ip %s not answering (%s)", ip, e)
        if not reachable:
            ip = rediscover(cfg, log) or ip
    if not ip:
        log.error("device_ip is empty in config.json and no device was found on the network")
        return 2
    interval = max(3, float(cfg["refresh_seconds"]))
    name = cfg["image_name"]
    tmp = os.path.join(HERE, name)
    psutil.cpu_percent(interval=None)  # prime

    log.info("starting: device=%s interval=%ss lhm=%s", ip, interval, cfg["lhm_url"])
    state = {"ip": ip, "need_select": True}

    def to_clock():
        device.set_theme(state["ip"], int(cfg["off_theme"]), timeout=3.0)
        log.info("device switched to clock theme %s", cfg["off_theme"])

    def on_resume():
        state["need_select"] = True  # re-select the dashboard on the next loop

    session_hooks.start(on_end_session=to_clock, on_suspend=to_clock, on_resume=on_resume, log=log)

    last_bytes = None
    last_lhm_ok = None
    backoff = 0
    failures = 0
    last_scan = 0.0
    last_tick = time.time()
    last_select = 0.0

    while True:
        t0 = time.time()
        # A big gap since the last tick means the PC was asleep and the device may be on the clock;
        # also re-select the dashboard every 5 min as a safety net.
        if t0 - last_tick > interval * 3 + 10 or t0 - last_select > 300:
            state["need_select"] = True
        last_tick = t0
        try:
            m = sensors.read_metrics(cfg["lhm_url"])
            if m["lhm_ok"] != last_lhm_ok:
                log.warning("LibreHardwareMonitor %s", "reachable" if m["lhm_ok"] else "NOT reachable - temps/GPU will show '--'")
                last_lhm_ok = m["lhm_ok"]
            data = render.render_jpeg_bytes(m, cfg["jpeg_quality"])
            if data != last_bytes:
                with open(tmp, "wb") as f:
                    f.write(data)
                device.upload(ip, tmp, name)
                last_bytes = data
                if state["need_select"]:
                    device.set_theme(ip, 3)
                    device.select_image(ip, name)
                    state["need_select"] = False
                    last_select = time.time()
                    log.info("device online (%s), image selected", device.probe(ip))
            backoff = 0
            failures = 0
        except KeyboardInterrupt:
            log.info("stopped by user")
            try:
                to_clock()
            except Exception as e:
                log.warning("could not switch to clock: %s", e)
            return 0
        except Exception as e:
            state["need_select"] = True
            last_bytes = None
            failures += 1
            backoff = min(30, backoff + 5)
            log.error("%s: %s (retry in %ss)", type(e).__name__, e, backoff)
            # After a few misses (e.g. router reboot changed the DHCP lease), look for the device again,
            # at most once a minute.
            if cfg["auto_discover"] and failures >= 3 and time.time() - last_scan > 60:
                last_scan = time.time()
                new_ip = rediscover(cfg, log)
                if new_ip:
                    ip = new_ip
                    state["ip"] = new_ip
                    backoff = 0
        elapsed = time.time() - t0
        time.sleep(max(0.5, (backoff or interval) - elapsed))


if __name__ == "__main__":
    sys.exit(main())
