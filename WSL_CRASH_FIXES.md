# WSL Crash Troubleshooting — Case File & Fixes

**Machine**: CHONDEEPA — Windows 11, 32GB RAM, RTX 4060 Laptop, WSL 2.7.10.0 (kernel 6.18.33.2-2), Ubuntu + docker-desktop distros, VSCode WSL extension 0.104.3.
**Prepared by**: Claude Code (running inside the affected WSL Ubuntu). Hand this file to Claude Desktop and work through it top-to-bottom **on the Windows side**.

---

## 1. Symptoms observed (2026-07-18)

- The WSL VM terminates/restarts repeatedly — observed boot times 14:15, 14:22, 14:31, 15:18 (roughly every 5–15 minutes during active use).
- `wsl` from PowerShell intermittently returns: **`Catastrophic failure — Error code: Wsl/Service/E_UNEXPECTED`** — sometimes recovering on retry, sometimes needing `wsl --shutdown` first.
- VSCode: **"Failed to connect to the remote extension host server (WebSocket close 1006)"** and **"Could not fetch remote environment"** after each drop.
- VSCode WSL extension log at 14:30:59 shows the extension starting fresh and getting `Error` when first exec-ing into Ubuntu — i.e. the VM was already dead before VSCode reconnected.

## 2. Already diagnosed & fixed (Linux side — do not redo)

| Item | Status |
|---|---|
| In-VM out-of-memory kills (a 39.5M-row pandas merge hit the 15.5GB VM cap; dmesg-confirmed OOM kill of python3 at 15.3GB) | **Fixed** — job rebuilt to run chunked; peak now well under cap |
| `/etc/wsl.conf` "Duplicated config key 'automount.options'" warning | **Fixed** — duplicate `[automount]` sections merged |
| Long jobs dying with the VM | **Mitigated** — all pipeline stages checkpoint to disk and auto-resume |

**Remaining problem = Windows side**: the WSL service itself is crashing (`E_UNEXPECTED`), and/or the VM is being torn down by power management / idle policy.

## 3. Fixes to apply (in this order)

### 3.1 Update WSL + reset (5 min, do first)
Open **PowerShell as Administrator**:
```powershell
wsl --update
wsl --shutdown
wsl --version    # expect a version bump
wsl              # confirm it opens cleanly several times in a row
```
`E_UNEXPECTED` service crashes are frequently fixed by a WSL platform update alone.

### 3.2 Read the crash reason from Event Viewer (10 min — this tells you which fix matters)
In PowerShell (Admin), pull recent WSL/Hyper-V/VM events around the crash times (14:00–15:30 on 2026-07-18):
```powershell
Get-WinEvent -LogName "Application","System" -MaxEvents 400 |
  Where-Object { $_.Message -match "WSL|vmcompute|Hyper-V|vmmem|WslService" } |
  Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, Message |
  Format-List | Out-String -Width 300
```
Also check: Event Viewer → Applications and Services Logs → Microsoft → Windows → **Hyper-V-Compute** (vmcompute crashes appear here) and **WSL**.
- If **vmcompute.exe crashes**: proceed to 3.3 and 3.6.
- If events show the VM being **shut down gracefully** at those times: it's power/idle policy — 3.4 is your fix.
- If **no events at all**: likely idle-teardown after the last console closed — 3.4 + 3.5.

### 3.3 Restart/verify the underlying services
```powershell
Get-Service WslService, vmcompute | Format-Table Name, Status, StartType
Restart-Service vmcompute -Force
Restart-Service WslService -Force   # name may be 'WSL Service' on some builds
```
Both should be Running with StartType Manual/Automatic. If either repeatedly dies, note the Event Viewer error for it.

### 3.4 Power settings (likely a major contributor on this laptop)
- Settings → System → Power & battery → Screen and sleep: set **sleep to Never** for *both* "on battery" and "plugged in" (at least while long model fits run).
- Control Panel → Power Options → "Choose what the power buttons do" → Change settings currently unavailable → **uncheck "Turn on fast startup"** → Save. (Fast Startup is a known cause of broken/corrupted WSL & Hyper-V state across shutdown/boot cycles.)
- If the laptop is docked/on Wi-Fi: Device Manager → network adapter → Power Management → uncheck "Allow the computer to turn off this device to save power" (helps the VSCode remote connection drops).

### 3.5 Create `C:\Users\<you>\.wslconfig` (none exists today)
This caps the VM so Windows never gets starved when heavy model fits run, and stops idle teardown:
```ini
[wsl2]
memory=12GB
processors=8
swap=16GB
vmIdleTimeout=-1

[experimental]
autoMemoryReclaim=gradual
```
Then `wsl --shutdown` and reopen. Notes:
- `memory=12GB` leaves Windows 20GB — vmmem can no longer pressure the host (the Linux-side job now fits comfortably in 12GB).
- `vmIdleTimeout=-1` stops Windows terminating the VM shortly after the last console/VSCode window disconnects — this directly addresses the "dies when my internet drops" chain. If the WSL version rejects `-1`, use a large value like `vmIdleTimeout=86400000`.
- If `autoMemoryReclaim` causes issues on this WSL build, delete that section — it's an optimization, not a fix.

### 3.6 Docker Desktop (present on this machine — known WSL destabilizer)
The `docker-desktop` distro exists (currently Stopped). Docker Desktop hooks the WSL service and is a well-documented source of `E_UNEXPECTED`/service crashes.
- Quit Docker Desktop from the system tray when not in use.
- Docker Desktop → Settings → General → **uncheck "Start Docker Desktop when you log in"**.
- Test: with Docker fully quit, does WSL still crash? If crashes stop, update Docker Desktop to latest (its WSL integration fixes land frequently).

### 3.7 If crashes persist after all the above
- `wsl --update --web-download` (bypasses Store caching).
- Settings → Apps → Installed apps → **Windows Subsystem for Linux** → Advanced options → **Repair**.
- Check for pending Windows Updates (WSL service crashes cluster on half-updated systems); reboot after updating.
- Third-party antivirus/VPN: if any is installed, add exclusions for `vmmem`/WSL or temporarily disable to test — several VPN/AV products break Hyper-V networking and crash the WSL service.
- Last resort — reinstall the WSL *platform only* (safe for data): `wsl --install --no-distribution`.

## 4. ⚠️ Do NOT do these

- **Never run `wsl --unregister Ubuntu`** — it permanently deletes the entire Linux filesystem (project caches, credentials, everything Linux-side). No fix in this file requires it.
- Don't delete the `docker-desktop` distro by hand; manage it via Docker Desktop settings.
- `wsl --shutdown` is safe (running model fits checkpoint their work and auto-resume on relaunch), but prefer doing it between fit stages rather than reflexively.

## 5. Verification checklist (after fixes)

1. `wsl` opens cleanly 5× in a row from PowerShell (no `E_UNEXPECTED`).
2. Open a WSL terminal, close ALL windows including VSCode, wait 10 minutes, reopen: `uptime -s` inside Ubuntu should show the VM did **not** reboot (thanks to `vmIdleTimeout`).
3. Run a heavy job inside WSL (any of the project's fit scripts); vmmem in Task Manager should plateau ≤ ~12GB and Windows should stay responsive.
4. Let the laptop sit idle 30 min (screen off): VM still up afterward.

## 6. Context for Claude Desktop

The Ubuntu distro hosts an active ML project at `/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI` with long-running model fits (`freddie.fit_hazard`, `freddie.fit_lgd`) that keep getting killed by these VM teardowns. The fits are checkpointed and self-resuming — the goal of the fixes above is simply a VM that stays alive: (a) `wsl` never returns `E_UNEXPECTED`, (b) the VM survives VSCode/connection drops, (c) the VM survives sleep/idle. Do not modify anything inside the Ubuntu filesystem; all Linux-side fixes are already applied.

---

## 7. RESOLUTION — 2026-07-18 21:16 IST (applied from the Windows side via `wsl_fix\Fix-WSL.ps1`)

**Root cause found: the VM was never crashing — it was being torn down cleanly.** Event Viewer
(48h window) showed **zero** service/app crash events. The Hyper-V VmSwitch log showed the WSL VM
being created and "successfully deleted" over and over — lifetimes of 6, 9, 20 and 14 minutes on
the evening of 18-07 — i.e. the default **~60s idle teardown** firing each time the last
console/VSCode connection dropped. The intermittent `E_UNEXPECTED` was `wsl.exe` racing a teardown
in progress, plus Fast Startup (which was ON) corrupting WSL/Hyper-V state across reboots.
The host itself also shut down cleanly at 19:43 and 20:46 on 18-07 (and twice on 16-07) — if those
were not manual reboots, check Windows Update history.

**Applied (full log: `wsl_fix\wsl_fix_report_2026-07-18_211629.txt`):**
- WSL platform already latest (2.7.10.0) — no update needed.
- `vmcompute` + `WslService` restarted cleanly.
- Sleep + hibernate timeouts → **Never** (AC and battery); **Fast Startup OFF** (HiberbootEnabled=0).
- `C:\Users\Pritam\.wslconfig` created: `memory=12GB`, `processors=8`, `swap=16GB`,
  `vmIdleTimeout=86400000` (24h), `autoMemoryReclaim=gradual`.
- Verified live in-VM after restart: MemTotal 12,248,692 kB, nproc 8.
- **Stability test: 5/5 clean `wsl` launches, no `E_UNEXPECTED`.**

**⚠️ Note for Linux-side jobs:** the VM is now capped at **12GB RAM / 8 CPUs** (plus 16GB swap) —
size fits/chunks accordingly (previous effective cap was ~15.5GB).

**Still manual / watch-items:**
- Docker Desktop: autostart-at-login was ON → turn off in Docker Desktop → Settings → General; quit from tray when unused.
- Realtek Ethernet adapter power management could not be changed by script → Device Manager →
  Realtek PCIe GbE Family Controller → Power Management → uncheck "Allow the computer to turn off this device".
- OpenVPN adapters exist (disconnected during the incidents — not implicated, but a known WSL
  destabilizer if problems return while a VPN is up).
- `wsl_fix\Fix-WSL.ps1` is reusable: Phase A alone is a safe read-only crash-evidence collector.
