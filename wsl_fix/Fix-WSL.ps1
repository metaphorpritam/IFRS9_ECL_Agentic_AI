# ============================================================================
#  Fix-WSL.ps1 - WSL crash diagnostics + fixes
#  Companion to WSL_CRASH_FIXES.md (machine CHONDEEPA, 2026-07-18)
#
#  HOW TO RUN (from an elevated PowerShell / Windows Terminal "Run as administrator"):
#    powershell -ExecutionPolicy Bypass -File "D:\Python-UV\IFRS9_ECL_Agentic_AI\wsl_fix\Fix-WSL.ps1"
#
#  PHASE A (read-only, always safe):
#    A1. Pull WSL / Hyper-V / power crash evidence from Event Viewer (last 48h)
#    A2. Snapshot system, WSL, services, antivirus/VPN and Docker state
#  PHASE B (asks for confirmation first; applies case-file fixes 3.1-3.5):
#    B1. wsl --update
#    B2. Restart WslService + vmcompute
#    B3. Sleep timeouts -> Never (AC + battery), Fast Startup -> off
#    B4. Write %UserProfile%\.wslconfig (12GB cap, 24h idle timeout; backs up any existing)
#    B5. Disable network-adapter power saving (best effort)
#    B6. wsl --shutdown, then 5x relaunch stability test + config verification
#
#  Everything is logged to wsl_fix_report_<timestamp>.txt next to this script.
#  Docker Desktop autostart must be toggled manually (reminder at the end).
#
#  REVERT NOTES (if ever needed):
#    powercfg /change standby-timeout-ac 30
#    powercfg /change standby-timeout-dc 15
#    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' HiberbootEnabled 1
#    Edit or remove "$env:USERPROFILE\.wslconfig" (a backup is saved beside it), then: wsl --shutdown
# ============================================================================

$ErrorActionPreference = 'Continue'
$env:WSL_UTF8 = '1'   # make wsl.exe output plain UTF-8 instead of UTF-16

# --- elevation check --------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host ''
    Write-Host 'This script needs an elevated (Administrator) PowerShell.' -ForegroundColor Yellow
    $ans = Read-Host 'Relaunch elevated now? [Y/n]'
    if ($ans -eq '' -or $ans -match '^[Yy]') {
        Start-Process powershell.exe -Verb RunAs -ArgumentList '-ExecutionPolicy','Bypass','-NoExit','-File',"`"$PSCommandPath`""
    }
    exit 1
}

if ($PSScriptRoot) { $scriptDir = $PSScriptRoot } else { $scriptDir = (Get-Location).Path }
$stamp      = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$reportPath = Join-Path $scriptDir "wsl_fix_report_$stamp.txt"
Start-Transcript -Path $reportPath | Out-Null

function Section([string]$t) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Cyan
    Write-Host ("  " + $t) -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor Cyan
}
function Note([string]$t) { Write-Host $t -ForegroundColor Yellow }
function Ok([string]$t)   { Write-Host $t -ForegroundColor Green }

function Show-Events($events, [int]$max = 40) {
    if (-not $events) { Write-Host '  (none found)'; return }
    $events | Sort-Object TimeCreated | Select-Object -Last $max | ForEach-Object {
        $msg = ($_.Message -replace '\s+', ' ')
        if ($msg.Length -gt 260) { $msg = $msg.Substring(0, 260) + ' ...' }
        Write-Host ("  [{0}] {1} #{2} ({3}): {4}" -f $_.TimeCreated, $_.ProviderName, $_.Id, $_.LevelDisplayName, $msg)
    }
}

try {

# ===========================================================================
Section 'PHASE A1 - Event Viewer evidence (last 48h, read-only)'
$since = (Get-Date).AddHours(-48)

Write-Host ''
Write-Host '--- Service failures (Service Control Manager: WSL / vmcompute / Hyper-V) ---'
$svcEvents = Get-WinEvent -FilterHashtable @{ LogName='System'; ProviderName='Service Control Manager'; StartTime=$since } -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -in 7000,7001,7023,7024,7031,7034,7043 -and $_.Message -match 'WSL|vmcompute|Hyper-V|Host Compute' }
Show-Events $svcEvents

Write-Host ''
Write-Host '--- Application crashes (wslservice / vmcompute / vmwp / docker) ---'
$appEvents = Get-WinEvent -FilterHashtable @{ LogName='Application'; ProviderName='Application Error','Windows Error Reporting','.NET Runtime'; StartTime=$since } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match 'wsl|vmcompute|vmwp|vmmem|docker' }
Show-Events $appEvents

Write-Host ''
Write-Host '--- Sleep / resume / unexpected reboot (Kernel-Power, Power-Troubleshooter) ---'
$powerEvents = Get-WinEvent -FilterHashtable @{ LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power','Microsoft-Windows-Power-Troubleshooter'; StartTime=$since } -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -in 1,41,42,107 }
Show-Events $powerEvents

Write-Host ''
Write-Host '--- Dedicated WSL / Hyper-V logs (Critical, Error, Warning) ---'
$extraLogs = Get-WinEvent -ListLog '*WSL*','*Hyper-V-Compute*','*Hyper-V-Worker*','*Hyper-V-VMMS*' -ErrorAction SilentlyContinue |
    Where-Object { $_.RecordCount -gt 0 }
$hvEvents = @()
foreach ($l in $extraLogs) {
    $hvEvents += @(Get-WinEvent -FilterHashtable @{ LogName=$l.LogName; StartTime=$since } -MaxEvents 300 -ErrorAction SilentlyContinue |
        Where-Object { $_.LevelDisplayName -in 'Critical','Error','Warning' })
}
Show-Events $hvEvents 60

Write-Host ''
Write-Host '--- Generic sweep (query from case file 3.2) ---'
$genericEvents = Get-WinEvent -LogName 'Application','System' -MaxEvents 800 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -ge $since -and $_.Message -match 'WSL|vmcompute|Hyper-V|vmmem|WslService' }
Show-Events $genericEvents 60

Write-Host ''
Write-Host '--- Quick read of the evidence ---'
$svcCount   = @($svcEvents).Count + @($appEvents).Count
$sleepCount = @($powerEvents | Where-Object { $_.Id -in 1,42,107 }).Count
if ($svcCount -gt 0)   { Note ("  * {0} service/app crash event(s) -> service-crash pattern: WSL update + service restarts + Docker/AV checks matter most (case file 3.1/3.3/3.6/3.7)." -f $svcCount) }
if ($sleepCount -gt 0) { Note ("  * {0} sleep/resume event(s) in the window -> power policy is implicated (case file 3.4 + .wslconfig)." -f $sleepCount) }
if ($svcCount -eq 0 -and $sleepCount -eq 0) { Note '  * No crash or sleep events found -> idle teardown is the likely cause; the .wslconfig vmIdleTimeout fix (case file 3.5) matters most.' }
Write-Host '  (Full interpretation: share this report file back with Claude.)'

# ===========================================================================
Section 'PHASE A2 - System snapshot (read-only)'

Write-Host ''
Write-Host '--- Windows version ---'
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' |
    Select-Object ProductName, DisplayVersion, CurrentBuild, UBR | Format-List | Out-String | Write-Host

Write-Host '--- WSL version ---'
wsl.exe --version 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
Write-Host ''
Write-Host '--- Distros ---'
wsl.exe -l -v 2>&1 | ForEach-Object { Write-Host ("  " + $_) }

Write-Host ''
Write-Host '--- Existing .wslconfig ---'
$cfgPath = Join-Path $env:USERPROFILE '.wslconfig'
if (Test-Path $cfgPath) { Get-Content $cfgPath | ForEach-Object { Write-Host ("  " + $_) } }
else { Write-Host ("  (none at {0})" -f $cfgPath) }

Write-Host ''
Write-Host '--- WSL-related services ---'
Get-Service -Name 'WslService','vmcompute','LxssManager','hns' -ErrorAction SilentlyContinue |
    Format-Table Name, Status, StartType -AutoSize | Out-String | Write-Host

Write-Host '--- Antivirus products registered (AV/VPN can crash the WSL service) ---'
Get-CimInstance -Namespace 'root/SecurityCenter2' -ClassName AntiVirusProduct -ErrorAction SilentlyContinue |
    Select-Object displayName, productState | Format-Table -AutoSize | Out-String | Write-Host

Write-Host '--- Network adapters (look for VPN/TAP adapters) ---'
Get-NetAdapter -ErrorAction SilentlyContinue |
    Format-Table Name, InterfaceDescription, Status -AutoSize | Out-String | Write-Host

Write-Host '--- Docker Desktop ---'
$dockerProc = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
if ($dockerProc) { Note '  Docker Desktop is RUNNING.' } else { Write-Host '  Docker Desktop is not running right now.' }
$dockerAuto = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'Docker Desktop'
if ($dockerAuto) { Note '  Docker Desktop IS set to start at login -> turn off in Docker Desktop, Settings, General.' }
else { Write-Host '  No Docker Desktop autostart entry in the HKCU Run key.' }

Write-Host ''
Write-Host '--- Fast Startup / sleep current values ---'
$hiberboot = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -ErrorAction SilentlyContinue).HiberbootEnabled
Write-Host ("  HiberbootEnabled (Fast Startup) = {0}   (1 = on, 0 = off)" -f $hiberboot)
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>&1 |
    Select-String 'Current AC|Current DC' | ForEach-Object { Write-Host ("  standby " + $_.ToString().Trim()) }

# ===========================================================================
Section 'PHASE B - Apply fixes (case file 3.1 - 3.5)'
Write-Host ''
Write-Host 'Phase B will:'
Write-Host '  1. Update the WSL platform (wsl --update)'
Write-Host '  2. Restart the WslService and vmcompute services'
Write-Host '  3. Set sleep timeouts to Never (AC + battery) and turn off Fast Startup'
Write-Host ("  4. Write {0} (backing up any existing file)" -f $cfgPath)
Write-Host '  5. Disable network-adapter power saving (best effort)'
Write-Host '  6. Restart WSL (wsl --shutdown) and run a 5x stability test'
Write-Host ''
Note 'Anything running inside WSL will stop and auto-resume from its checkpoints.'
Note 'VSCode will reconnect after a minute. This is expected.'
$ans = Read-Host 'Continue with Phase B? [Y/n]'
if ($ans -ne '' -and $ans -notmatch '^[Yy]') {
    Note 'Stopped after evidence collection. Report saved - share it with Claude.'
    exit 0
}
if ($dockerProc) {
    Read-Host 'Docker Desktop is running. Quit it first (system tray -> right-click whale icon -> Quit Docker Desktop), then press Enter'
}

# ---------------------------------------------------------------------------
Section 'B1 - WSL platform update (case file 3.1)'
wsl.exe --update 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
if ($LASTEXITCODE -ne 0) {
    Note '  Store update failed; retrying with --web-download ...'
    wsl.exe --update --web-download 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
}
Write-Host ''
Write-Host '  Version now:'
wsl.exe --version 2>&1 | ForEach-Object { Write-Host ("  " + $_) }

# ---------------------------------------------------------------------------
Section 'B2 - Restart WSL services (case file 3.3)'
foreach ($svcName in 'vmcompute','WslService','LxssManager') {
    $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if ($svc) {
        try {
            Restart-Service -Name $svcName -Force -ErrorAction Stop
            Ok ("  {0}: restarted (now {1})" -f $svcName, (Get-Service $svcName).Status)
        } catch {
            Note ("  {0}: could not restart -> {1}" -f $svcName, $_.Exception.Message)
        }
    } else {
        Write-Host ("  {0}: not present on this build (fine)" -f $svcName)
    }
}

# ---------------------------------------------------------------------------
Section 'B3 - Power policy (case file 3.4)'
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
Ok '  Sleep + hibernate timeouts set to Never (both AC and battery).'
try {
    Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0 -Type DWord -ErrorAction Stop
    Ok '  Fast Startup disabled (HiberbootEnabled = 0).'
} catch {
    Note ("  Could not disable Fast Startup -> {0}" -f $_.Exception.Message)
}
Note '  (Revert later: powercfg /change standby-timeout-ac 30, etc. - see script header.)'

# ---------------------------------------------------------------------------
Section 'B4 - Write .wslconfig (case file 3.5)'
if (Test-Path $cfgPath) {
    $bak = "$cfgPath.bak_$stamp"
    Copy-Item $cfgPath $bak -Force
    Note ("  Existing .wslconfig backed up to {0}" -f $bak)
}
$wslconfig = @'
# WSL2 VM settings - written by Fix-WSL.ps1 (see WSL_CRASH_FIXES.md section 3.5)

[wsl2]
# Cap the VM at 12GB so heavy model fits cannot starve Windows (32GB host)
memory=12GB
processors=8
swap=16GB
# Keep the VM alive ~24h after the last console/VSCode window disconnects
# (default is ~60s idle teardown; -1 "never" is rejected on some builds)
vmIdleTimeout=86400000

[experimental]
# Gradually return freed Linux memory to Windows. Delete this section if it
# misbehaves on this build - it is an optimization, not a fix.
autoMemoryReclaim=gradual
'@
$wslconfig | Out-File -FilePath $cfgPath -Encoding ascii -Force
Ok ("  Wrote {0}:" -f $cfgPath)
Get-Content $cfgPath | ForEach-Object { Write-Host ("    " + $_) }

# ---------------------------------------------------------------------------
Section 'B5 - Network adapter power saving (case file 3.4, best effort)'
$upAdapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' })
foreach ($ad in $upAdapters) {
    try {
        Set-NetAdapterPowerManagement -Name $ad.Name -AllowComputerToTurnOffDevice Disabled -ErrorAction Stop
        Ok ("  {0}: 'Allow the computer to turn off this device' disabled." -f $ad.Name)
    } catch {
        Note ("  {0}: could not change automatically - do it in Device Manager -> adapter -> Power Management tab." -f $ad.Name)
    }
}
if ($upAdapters.Count -eq 0) { Write-Host '  (no active physical adapters found)' }

# ---------------------------------------------------------------------------
Section 'B6 - Restart WSL + stability test (case file 3.1 / section 5)'
Note '  Restarting WSL now (running jobs checkpoint and auto-resume)...'
wsl.exe --shutdown 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
Start-Sleep -Seconds 8

$distro = (wsl.exe -l -q 2>$null | ForEach-Object { "$_".Trim() } | Where-Object { $_ -and $_ -notmatch 'docker' } | Select-Object -First 1)
if (-not $distro) { $distro = 'Ubuntu' }
Write-Host ("  Test distro: {0}" -f $distro)

$fails = 0
for ($i = 1; $i -le 5; $i++) {
    $out = wsl.exe -d $distro --exec /bin/true 2>&1
    if ($LASTEXITCODE -eq 0) { Ok ("  Launch {0}/5: OK" -f $i) }
    else {
        $fails++
        Note ("  Launch {0}/5: FAILED -> {1}" -f $i, (($out | Out-String).Trim()))
    }
    Start-Sleep -Seconds 3
}

Write-Host ''
Write-Host '  Verifying .wslconfig took effect inside the VM:'
$mem  = (wsl.exe -d $distro --exec grep MemTotal /proc/meminfo 2>&1 | Out-String).Trim()
$cpus = (wsl.exe -d $distro --exec nproc 2>&1 | Out-String).Trim()
Write-Host ("    {0}   (expect roughly 12,000,000 kB)" -f $mem)
Write-Host ("    CPUs: {0}   (expect 8)" -f $cpus)

Write-Host ''
if ($fails -eq 0) { Ok '  STABILITY TEST PASSED - wsl launched cleanly 5/5 times, no E_UNEXPECTED.' }
else { Note ("  STABILITY TEST: {0}/5 launches failed - share this report with Claude (next steps live in case file 3.6/3.7)." -f $fails) }

# ---------------------------------------------------------------------------
Section 'DONE - what remains manual'
Write-Host '  1. Docker Desktop: Settings -> General -> uncheck "Start Docker Desktop when'
Write-Host '     you log in", and quit Docker from the tray when not using it'
Write-Host '     (Docker is a documented source of the E_UNEXPECTED crashes).'
Write-Host '  2. If any adapter in B5 said "could not change automatically": Device Manager'
Write-Host '     -> adapter -> Power Management -> uncheck "Allow the computer to turn off'
Write-Host '     this device to save power".'
Write-Host '  3. Verification over the next hours (case file section 5):'
Write-Host '     - close every WSL window + VSCode, wait 10+ min, reopen, run: uptime -s'
Write-Host '       (the boot time should NOT have changed)'
Write-Host '     - run a heavy fit: vmmem should plateau near 12GB, Windows stays responsive.'
Write-Host ''
Ok ("  Full report saved to: {0}" -f $reportPath)
Write-Host '  Tell Claude the script has run - the report is inside the project folder and'
Write-Host '  Claude will read and interpret it from there.'

} finally {
    try { Stop-Transcript | Out-Null } catch { }
}
