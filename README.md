# GeekMagic Ultra 4 — PC monitor

Shows CPU temp / CPU usage / GPU temp / GPU usage / RAM on the GeekMagic Ultra 4
by rendering a 240x240 picture on the PC and uploading it to the device over WiFi
every 5 s. Stock firmware, nothing flashed.

**The USB-C cable only powers the device.** All data goes over your home WiFi.

## One-time setup

### 1. Put the device on your home WiFi
The device joins your *router's* WiFi (the same network the PC is on). Your PC's
internet is not affected.

1. Power the device. On first boot it shows a hotspot name on screen.
2. From your **phone**, join that hotspot, open `http://192.168.4.1` (or the page
   that pops up), choose your home 2.4 GHz WiFi and enter the password.
   (You can do this from the PC too; just switch the PC back to your normal WiFi afterwards.)
3. The device reboots and shows its IP, e.g. `192.168.0.150`.
4. Check from the PC: open `http://<that-ip>/v.json` in a browser; it should show `SmallTV-Ultra`.
5. Put that IP in `config.json` → `"device_ip"` (or leave it blank: the script finds the device by itself, see below).

### Automatic IP discovery (no router access needed)
`monitor.py` does not rely on a fixed IP. At startup it checks the saved `device_ip`;
if it doesn't answer, and whenever three uploads in a row fail (e.g. the router
rebooted and handed out a new address), it scans the local network for a device
answering `/v.json` as `SmallTV-*`, prefers the one whose MAC matches
`device_mac`, saves the new IP into `config.json` and carries on. Rescans run at
most once a minute. `python discover.py` runs the same scan by hand.
Set `"auto_discover": false` in `config.json` to turn this off.

### 2. LibreHardwareMonitor (reads CPU + AMD GPU temperatures)
Installed at `C:\Tools\LibreHardwareMonitor\LibreHardwareMonitor.exe` (v0.9.6),
pre-configured to run its web server on port 8085 and sit minimized in the tray.
It is already running, and a scheduled task **LibreHardwareMonitor Autostart**
(run with highest privileges, so no UAC prompt at login) starts it at logon.

- Verify: `http://localhost:8085/data.json` shows CPU / GPU / Memory nodes.
- If the tray icon is missing, start it again from that folder (accept the UAC prompt).
- Don't also tick "Run On Windows Startup" inside the app; that would make a second
  copy which fails to open port 8085 (harmless, but noisy).

### 3. Clock when the PC is off or asleep
When Windows shuts down, logs off or goes to sleep, the device is switched to a
plain clock (theme 4 = "Time Style 1"; change `off_theme` in `config.json`,
5/6 are the other time styles, 7 is the simple weather clock). When the PC comes
back, the dashboard is re-selected automatically.

Two mechanisms, so it works even if the script was already killed:
- `monitor.py` listens for Windows' shutdown/sleep notifications and switches the theme.
- scheduled task **GeekMagic Clock On Shutdown** fires on the system "shutdown
  initiated" event (System log, User32, event 1074) and runs `set_clock.py`.

`python set_clock.py` switches to the clock by hand; `python set_clock.py 3` goes
back to the dashboard.

**Power:** for this to be useful the device must stay powered after shutdown.
If it is on a PC USB port, the port must keep 5 V in the off state (a BIOS option,
often called "ErP", "USB power in S4/S5" or "USB charging when off"). A wall USB
adapter avoids the question entirely.

### 4. Autostart
`install_task.ps1` registered a scheduled task **GeekMagic Monitor** that starts
`monitor.py` (hidden) 30 s after you log in. Remove with `uninstall_task.ps1`.
All three GeekMagic/LibreHardwareMonitor tasks are visible in Task Scheduler → Task Scheduler Library.

## Run on another PC
1. Install Python 3 from python.org (tick **Add python.exe to PATH**).
2. Copy this whole folder to the new PC (any location).
3. Open PowerShell in that folder and run:
   ```
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```
   It installs the Python packages, downloads LibreHardwareMonitor into
   `C:\Tools\LibreHardwareMonitor` with the web server pre-enabled, registers the
   three scheduled tasks, starts everything and prints the last log lines.
   Expect one UAC prompt (LibreHardwareMonitor needs admin for CPU temps).
4. Nothing to configure: the device is found on the LAN automatically and
   `config.json` is updated with its IP and MAC.

Notes
- The new PC must be on the same WiFi/LAN as the device.
- Run the monitor on only one PC at a time; two PCs would overwrite each other's
  picture. Stop it on the old PC with `uninstall_task.ps1` (or just disable the
  "GeekMagic Monitor" task) before starting it elsewhere.
- Any CPU/GPU works: sensors are picked by LibreHardwareMonitor's ids
  (`/intelcpu/`, `/amdcpu/`, `/gpu-nvidia/`, `/gpu-amd/`, `/gpu-intel/`). If a value
  shows `--`, run `python sensors.py` and adjust the names in `sensors.py`.
- `setup.ps1 -SkipElevated` skips the UAC step; then start LibreHardwareMonitor by hand.

## Files
| File | Purpose |
|---|---|
| `config.json` | device IP + MAC (auto-filled), refresh interval, LHM URL, JPEG quality, auto_discover, off_theme |
| `sensors.py` | reads LHM `data.json` + psutil → metrics dict. `python sensors.py` prints all sensors |
| `render.py` | draws the 240x240 dashboard. `python render.py` writes `preview.jpg` |
| `device.py` | HTTP calls to the device. `python device.py <ip> preview.jpg` tests upload |
| `discover.py` | LAN scan for the device; used automatically when the IP changes |
| `session_hooks.py` | hidden window that receives Windows shutdown/sleep/resume notifications |
| `set_clock.py` | switch the device to the clock theme (or any theme number) |
| `setup.ps1` | one-shot install on a new PC (deps, LibreHardwareMonitor, tasks) |
| `monitor.py` | main loop; logs to `monitor.log` |
| `run_monitor.vbs` | launches `monitor.py` without a console window |

## Run manually
```
python monitor.py
```
Stop with Ctrl+C.

## Troubleshooting
- **Values show `--`**: LibreHardwareMonitor isn't running or its web server is off
  (Options → Remote Web Server → Run). Run `python sensors.py` to see every sensor
  name; if the GPU is listed under a different label, adjust the names in `sensors.py`.
- **"device_ip is empty"** in `monitor.log`: fill in `config.json`.
- **Device unreachable**: confirm `http://<ip>/v.json` works in a browser; the device
  must be on the same 2.4 GHz network as the PC.
- **Picture not showing**: on the device web page (`http://<ip>`) → Pictures, make
  sure image display is enabled. The script sets theme 3 and selects `monitor.jpg`.

## Flash-wear note
Each upload writes the device's flash. At 5 s that is fine for roughly a year of
24/7 use; the script skips uploads when nothing changed. Keep `refresh_seconds`
at 5 or higher (minimum enforced: 3).
