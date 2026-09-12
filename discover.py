"""Find the GeekMagic device on the local network.

    python discover.py            -> prints every SmallTV found (ip, model, firmware, mac)

Used by monitor.py when the saved IP stops answering (e.g. after a router reboot
hands out a new DHCP address).
"""
import concurrent.futures as cf
import ipaddress
import re
import socket
import subprocess
import sys

import psutil
import requests

MAX_HOSTS = 1024  # cap the scan for very large subnets


def local_networks():
    """IPv4 networks of the PC's active non-loopback interfaces, as ip_network objects."""
    nets = []
    for name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET and a.netmask and not a.address.startswith(("127.", "169.254.")):
                try:
                    net = ipaddress.ip_network(f"{a.address}/{a.netmask}", strict=False)
                except ValueError:
                    continue
                if net.num_addresses > MAX_HOSTS:  # shrink to the /24 around our own address
                    net = ipaddress.ip_network(f"{a.address}/24", strict=False)
                nets.append(net)
    return nets


def _probe(ip, timeout=0.6):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((str(ip), 80))
    except OSError:
        return None
    finally:
        s.close()
    try:
        r = requests.get(f"http://{ip}/v.json", timeout=3)
        j = r.json()
        if isinstance(j, dict) and "m" in j:
            return {"ip": str(ip), "model": j.get("m", ""), "version": j.get("v", "")}
    except Exception:
        pass
    return None


def arp_table():
    """{ip: 'aa-bb-cc-dd-ee-ff'} from `arp -a` (Windows) / `arp -an` (others)."""
    table = {}
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return table
    for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\D+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})", out):
        table[m.group(1)] = m.group(2).lower().replace(":", "-")
    return table


def find_devices(model_prefix="SmallTV"):
    found = []
    with cf.ThreadPoolExecutor(64) as ex:
        for net in local_networks():
            for res in ex.map(_probe, net.hosts()):
                if res and res["model"].lower().startswith(model_prefix.lower()):
                    found.append(res)
    arp = arp_table()
    for d in found:
        d["mac"] = arp.get(d["ip"], "")
    return found


def find_device(preferred_mac=None):
    """Return the device dict, preferring one whose MAC matches; None if nothing found."""
    devices = find_devices()
    if not devices:
        return None
    if preferred_mac:
        want = preferred_mac.lower().replace(":", "-")
        for d in devices:
            if d["mac"] == want:
                return d
    return devices[0]


if __name__ == "__main__":
    devs = find_devices()
    if not devs:
        sys.exit("no GeekMagic device found on the local network")
    for d in devs:
        print(f"{d['ip']}  {d['model']}  {d['version']}  mac={d['mac'] or '?'}")
