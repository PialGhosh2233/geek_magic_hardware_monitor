"""Read CPU/GPU/RAM metrics from LibreHardwareMonitor's web server + psutil.

Run directly to print the metrics and every sensor LHM exposes (useful when a
label doesn't match and a value shows as None).
"""
import json
import os
import re
import sys
import time

import psutil
import requests

DEFAULT_LHM_URL = "http://localhost:8085/data.json"
_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def _to_float(value):
    if value is None:
        return None
    m = _NUM.search(str(value))
    return float(m.group(0).replace(",", ".")) if m else None


def _flatten(node, path=(), out=None):
    """Walk LHM's tree into flat rows: (hw_name, hw_kind, category, sensor, value, sensor_id).

    hw_kind comes from the SensorId path, e.g. /intelcpu/0/temperature/8 -> "intelcpu",
    /gpu-amd/0/load/0 -> "gpu-amd". Falls back to ancestor text if SensorId is missing.
    """
    if out is None:
        out = []
    children = node.get("Children") or []
    text = node.get("Text", "")
    if children:
        for child in children:
            _flatten(child, path + (text,), out)
        return out
    sid = node.get("SensorId", "") or ""
    parts = [p for p in sid.split("/") if p]
    hw_kind = parts[0] if parts else ""
    # path = (root, computer, hardware, category) in the stock tree
    hw_name = path[-2] if len(path) >= 2 else ""
    category = path[-1] if path else ""
    out.append((hw_name, hw_kind, category, text, node.get("Value"), sid))
    return out


def fetch_lhm(url=DEFAULT_LHM_URL, timeout=2.0):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return _flatten(r.json())


def _is_cpu(hw, kind):
    return kind in ("intelcpu", "amdcpu") or (not kind and re.search(r"intel|ryzen|core|xeon", hw, re.I) and "radeon" not in hw.lower())


def _is_gpu(hw, kind):
    return kind.startswith("gpu") or (not kind and re.search(r"radeon|geforce|rtx|gtx|arc", hw, re.I) is not None)


def _pick(rows, hw_pred, category, names):
    """First sensor whose category matches and whose name is in `names` (priority order)."""
    for wanted in names:
        for hw, kind, cat, name, value, _ in rows:
            if hw_pred(hw, kind) and cat and cat.lower().startswith(category) and name.lower() == wanted.lower():
                v = _to_float(value)
                if v is not None:
                    return v
    return None


_net_last = {"t": None, "rx": 0, "tx": 0}


def net_speed_mbps():
    """(download, upload) in Mbit/s since the previous call, all NICs except loopback. First call -> (0, 0)."""
    rx = tx = 0
    for name, c in psutil.net_io_counters(pernic=True).items():
        if "loopback" in name.lower():
            continue
        rx += c.bytes_recv
        tx += c.bytes_sent
    now = time.time()
    last = _net_last
    if last["t"] is None or now - last["t"] <= 0:
        down = up = 0.0
    else:
        dt = now - last["t"]
        down = max(0.0, (rx - last["rx"]) * 8 / dt / 1e6)
        up = max(0.0, (tx - last["tx"]) * 8 / dt / 1e6)
    last.update(t=now, rx=rx, tx=tx)
    return down, up


def disk_usage(drive=None):
    """(percent, used_gb, total_gb) for the system drive (or the given one, e.g. 'D:')."""
    drive = drive or os.environ.get("SystemDrive", "C:")
    try:
        u = psutil.disk_usage(drive + "\\")
    except Exception:
        return None, None, None
    return u.percent, u.used / 2**30, u.total / 2**30


def read_metrics(lhm_url=DEFAULT_LHM_URL, disk_drive=None):
    """Return dict with cpu_temp, cpu_load, gpu_temp, gpu_load, ram_pct, ram_used_gb, ram_total_gb.

    Missing values are None. LHM errors don't raise; psutil values are always filled.
    """
    vm = psutil.virtual_memory()
    metrics = {
        "cpu_temp": None,
        "cpu_load": psutil.cpu_percent(interval=None),
        "gpu_temp": None,
        "gpu_load": None,
        "gpu_vram_used_gb": None,
        "gpu_vram_total_gb": None,
        "ram_pct": vm.percent,
        "ram_used_gb": vm.used / 2**30,
        "ram_total_gb": vm.total / 2**30,
        "lhm_ok": False,
        "gpu_present": True,  # assume yes until LHM tells us otherwise
    }
    metrics["net_down_mbps"], metrics["net_up_mbps"] = net_speed_mbps()
    metrics["disk_pct"], metrics["disk_used_gb"], metrics["disk_total_gb"] = disk_usage(disk_drive)
    try:
        rows = fetch_lhm(lhm_url)
    except Exception:
        return metrics
    metrics["lhm_ok"] = True
    metrics["gpu_present"] = any(_is_gpu(hw, kind) for hw, kind, *_ in rows)
    metrics["cpu_temp"] = _pick(rows, _is_cpu, "temperature", ["CPU Package", "Core Average", "Core Max", "CPU Core #1", "Core (Tctl/Tdie)"])
    metrics["gpu_temp"] = _pick(rows, _is_gpu, "temperature", ["GPU Core", "GPU Hot Spot", "GPU Temperature"])
    metrics["gpu_load"] = _pick(rows, _is_gpu, "load", ["GPU Core", "D3D 3D", "GPU Total", "GPU"])
    used_mb = _pick(rows, _is_gpu, "data", ["GPU Memory Used", "D3D Dedicated Memory Used"])
    total_mb = _pick(rows, _is_gpu, "data", ["GPU Memory Total", "D3D Dedicated Memory Total"])
    if used_mb is not None:
        metrics["gpu_vram_used_gb"] = used_mb / 1024
    if total_mb is not None:
        metrics["gpu_vram_total_gb"] = total_mb / 1024
    lhm_cpu_load = _pick(rows, _is_cpu, "load", ["CPU Total"])
    if metrics["cpu_load"] is None and lhm_cpu_load is not None:
        metrics["cpu_load"] = lhm_cpu_load
    return metrics


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LHM_URL
    psutil.cpu_percent(interval=None)
    import time
    time.sleep(0.5)
    print(json.dumps(read_metrics(url), indent=2))
    print("\n--- all LHM sensors ---")
    try:
        for hw, kind, cat, name, value, sid in fetch_lhm(url):
            print(f"{hw} | {cat} | {name} = {value}   [{sid or kind}]")
    except Exception as e:
        print(f"LHM not reachable at {url}: {e}")
