def _ps(cmd: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)


def hardware_tools(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[Hardware] {action}")

    try:
        if action in ("specs", "hardware", "system", "info"):
            return _get_system_specs()

        elif action in ("disk", "drives", "storage"):
            return _get_disk_info()

        elif action in ("largest", "big_files", "space_hogs"):
            path = params.get("path", "").strip() or "C:\\"
            count = params.get("count", 10)
            try:
                count = int(count)
            except (ValueError, TypeError):
                count = 10
            return _find_largest(path, count)

        elif action in ("startup", "startup_programs", "autostart"):
            return _list_startup()

        elif action in ("services", "service"):
            name = params.get("name", "").strip()
            svc_action = params.get("service_action", "").strip().lower()
            if name and svc_action:
                return _manage_service(name, svc_action)
            return _list_services(name)

        elif action in ("processes", "procs", "tasks"):
            sort_by = params.get("sort", "cpu").strip().lower()
            count = params.get("count", 15)
            try:
                count = int(count)
            except (ValueError, TypeError):
                count = 15
            return _list_processes(sort_by, count)

        elif action in ("gpu", "graphics", "display"):
            return _get_gpu_info()

        elif action in ("memory", "ram"):
            return _get_ram_info()

        elif action in ("battery", "power"):
            return _get_battery_info()

        elif action in ("temperature", "temp", "sensors"):
            return _get_temperature()

        return (
            f"Unknown action: '{action}'. "
            f"Available: specs, disk, largest, startup, services, "
            f"processes, gpu, memory, battery, temperature"
        )

    except Exception as e:
        return f"Hardware tools failed: {e}"


def _get_system_specs() -> str:
    cpu = _ps(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | "
        "Format-List"
    )
    ram = _get_ram_info(short=True)
    os_info = _ps(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption, Version, OSArchitecture, BuildNumber | Format-List"
    )
    board = _ps(
        "Get-CimInstance Win32_BaseBoard | "
        "Select-Object Manufacturer, Product, Version | Format-List"
    )

    lines = ["=== System Specs ==="]

    for section in [("CPU", cpu), ("Motherboard", board), ("OS", os_info)]:
        parsed = []
        for line in section[1].split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                parsed.append(f"  {key.strip()}: {val.strip()}")
        if parsed:
            lines.append(f"\n{section[0]}:")
            lines.extend(parsed)

    lines.append(f"\n{ram}")

    return "\n".join(lines)


def _get_disk_info() -> str:
    output = _ps(
        "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
        "Select-Object DeviceID, Size, FreeSpace, VolumeName, FileSystem | "
        "Format-List"
    )
    if not output:
        return "No disk information available."

    drives = []
    current = {}
    for line in output.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
        elif line.strip() == "" and current:
            drives.append(current)
            current = {}
    if current:
        drives.append(current)

    lines = ["Disk Usage:"]
    for d in drives:
        did = d.get("DeviceID", "?")
        total = int(d.get("Size", 0))
        free = int(d.get("FreeSpace", 0))
        used = total - free
        pct = (used / total * 100) if total > 0 else 0
        label = d.get("VolumeName", "")
        fs = d.get("FileSystem", "")

        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)

        name = f" {label}" if label else ""
        lines.append(
            f"\n  {did}{name} ({fs})"
        )
        lines.append(f"    Used: {used_gb:.1f} GB / {total_gb:.1f} GB ({pct:.0f}%)")
        lines.append(f"    Free: {free_gb:.1f} GB")

    return "\n".join(lines)


def _find_largest(path: str, count: int) -> str:
    if count > 50:
        count = 50

    output = _ps(
        f"Get-ChildItem -Path \"{path}\" -Recurse -ErrorAction SilentlyContinue "
        f"| Where-Object {{ $_.PSIsContainer -eq $false }} "
        f"| Sort-Object Length -Descending "
        f"| Select-Object -First {count} "
        f"| ForEach-Object {{ $_.FullName + ' | ' + [math]::Round($_.Length/1MB,1) + ' MB' }}",
        timeout=30
    )

    if not output or "timed out" in output:
        return f"Could not scan {path}. Try a subfolder."

    lines = [f"Largest files in {path}:"]
    for i, item in enumerate(output.split("\n")[:count], 1):
        if item.strip():
            lines.append(f"  {i}. {item.strip()}")

    return "\n".join(lines)


def _list_startup() -> str:
    output = _ps(
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name, Command, Location, User | "
        "Format-List"
    )

    if not output:
        return "No startup programs found."

    programs = []
    current = {}
    for line in output.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
        elif line.strip() == "" and current:
            programs.append(current)
            current = {}
    if current:
        programs.append(current)

    if not programs:
        return "No startup programs found."

    lines = [f"Startup Programs ({len(programs)}):"]
    for p in programs:
        name = p.get("Name", "Unknown")
        cmd = p.get("Command", "")
        loc = p.get("Location", "")
        lines.append(f"\n  {name}")
        if cmd:
            lines.append(f"    Path: {cmd[:80]}")
        if loc:
            lines.append(f"    Location: {loc}")

    return "\n".join(lines)


def _list_services(name: str = "") -> str:
    if name:
        output = _ps(
            f"Get-Service -Name \"*{name}*\" -ErrorAction SilentlyContinue "
            f"| Select-Object Name, DisplayName, Status, StartType | Format-List"
        )
    else:
        output = _ps(
            "Get-Service | Sort-Object Status, Name "
            "| Select-Object Name, DisplayName, Status, StartType "
            "| Format-List"
        )

    if not output:
        return f"No services found matching '{name}'."

    services = []
    current = {}
    for line in output.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
        elif line.strip() == "" and current:
            services.append(current)
            current = {}
    if current:
        services.append(current)

    if name:
        s = services[0] if services else {}
        return (
            f"Service: {s.get('Name', name)}\n"
            f"Display: {s.get('DisplayName', '?')}\n"
            f"Status: {s.get('Status', '?')}\n"
            f"Start Type: {s.get('StartType', '?')}"
        )

    running = [s for s in services if s.get("Status") == "Running"]
    stopped = [s for s in services if s.get("Status") == "Stopped"]

    lines = [f"Services: {len(running)} running, {len(stopped)} stopped"]
    if running:
        lines.append(f"\nRunning ({min(len(running), 15)} shown):")
        for s in running[:15]:
            lines.append(f"  {s.get('Name', '?'):30s} {s.get('StartType', '?'):15s}")
    if stopped:
        lines.append(f"\nStopped ({min(len(stopped), 10)} shown):")
        for s in stopped[:10]:
            lines.append(f"  {s.get('Name', '?'):30s} {s.get('StartType', '?'):15s}")

    return "\n".join(lines)


def _manage_service(name: str, action: str) -> str:
    actions_map = {
        "start": "Start-Service",
        "stop": "Stop-Service",
        "restart": "Restart-Service",
        "pause": "Suspend-Service",
        "resume": "Resume-Service",
    }
    cmd = actions_map.get(action)
    if not cmd:
        return f"Unknown service action: {action}. Use: start, stop, restart, pause, resume"

    output = _ps(f"{cmd} -Name \"{name}\" -ErrorAction SilentlyContinue")
    time.sleep(1)
    status = _ps(
        f"Get-Service -Name \"{name}\" -ErrorAction SilentlyContinue "
        f"| Select-Object -ExpandProperty Status"
    )
    return f"Service '{name}' {action} completed. Current status: {status.strip() or 'Unknown'}"


def _list_processes(sort_by: str, count: int) -> str:
    if sort_by == "memory" or sort_by == "ram":
        sort_field = "WorkingSet64"
        label = "Memory"
    else:
        sort_field = "PercentProcessorTime"
        label = "CPU"

    output = _ps(
        f"Get-Process | Sort-Object {sort_field} -Descending "
        f"| Select-Object -First {count} "
        f"| Select-Object Name, Id, @{{N='CPU(s)';E={[math]::Round($_.CPU,1)}}}, "
        f"@{{N='MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}} "
        f"| Format-Table -AutoSize | Out-String -Width 200"
    )

    if not output:
        return "No process information available."

    lines = [f"Top {count} processes by {label} usage:"]
    for line in output.split("\n"):
        if line.strip():
            lines.append(f"  {line.strip()}")

    return "\n".join(lines[:count + 5])


def _get_gpu_info() -> str:
    output = _ps(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name, AdapterRAM, DriverVersion, CurrentHorizontalResolution, "
        "CurrentVerticalResolution, CurrentRefreshRate | Format-List"
    )

    if not output:
        return "No GPU information available."

    gpus = []
    current = {}
    for line in output.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
        elif line.strip() == "" and current:
            gpus.append(current)
            current = {}
    if current:
        gpus.append(current)

    lines = [f"Graphics ({len(gpus)} adapter{'s' if len(gpus) > 1 else ''}):"]
    for g in gpus:
        name = g.get("Name", "Unknown")
        ram_raw = g.get("AdapterRAM", "0")
        ram_gb = int(ram_raw) / (1024**3) if ram_raw.isdigit() else 0
        res_w = g.get("CurrentHorizontalResolution", "?")
        res_h = g.get("CurrentVerticalResolution", "?")
        hz = g.get("CurrentRefreshRate", "?")
        driver = g.get("DriverVersion", "?")

        lines.append(f"\n  {name}")
        if ram_gb > 0:
            lines.append(f"    VRAM: {ram_gb:.1f} GB")
        lines.append(f"    Resolution: {res_w}x{res_h} @ {hz} Hz")
        lines.append(f"    Driver: {driver}")

    return "\n".join(lines)


def _get_ram_info(short: bool = False) -> str:
    output = _ps(
        "Get-CimInstance Win32_PhysicalMemory | "
        "Measure-Object -Property Capacity -Sum | Select-Object -ExpandProperty Sum"
    )

    try:
        total_bytes = int(float(output))
        total_gb = total_bytes / (1024**3)
    except (ValueError, TypeError):
        total_gb = 0

    usage = _ps(
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$used = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1); "
        "$total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); "
        "$pct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0); "
        "Write-Output \"$used/$total/$pct\""
    )

    if short:
        parts = usage.strip().split("/")
        if len(parts) == 3:
            return f"RAM: {parts[0]} GB used / {parts[1]} GB total ({parts[2]}%)"
        return f"RAM: {total_gb:.1f} GB total"

    lines = [f"RAM: {total_gb:.1f} GB total"]
    if usage:
        parts = usage.strip().split("/")
        if len(parts) == 3:
            lines.append(f"  Used: {parts[0]} GB")
            lines.append(f"  Total: {parts[1]} GB")
            lines.append(f"  Usage: {parts[2]}%")

    sticks_output = _ps(
        "Get-CimInstance Win32_PhysicalMemory | "
        "Select-Object Manufacturer, Capacity, Speed, FormFactor | Format-List"
    )
    if sticks_output and "timed out" not in sticks_output:
        sticks = []
        current = {}
        for line in sticks_output.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                current[key.strip()] = val.strip()
            elif line.strip() == "" and current:
                sticks.append(current)
                current = {}
        if current:
            sticks.append(current)

        if sticks:
            lines.append(f"\nMemory Modules ({len(sticks)}):")
            for s in sticks:
                mfg = s.get("Manufacturer", "?").strip()
                cap_raw = s.get("Capacity", "0").strip()
                cap_gb = int(float(cap_raw)) / (1024**3) if cap_raw.replace(".", "").isdigit() else 0
                speed = s.get("Speed", "?")
                lines.append(f"  {mfg} {cap_gb:.0f} GB @ {speed} MHz")

    return "\n".join(lines)


def _get_battery_info() -> str:
    output = _ps(
        "Get-CimInstance Win32_Battery | "
        "Select-Object EstimatedChargeRemaining, BatteryStatus, "
        "DesignCapacity, FullChargeCapacity, Chemistry | Format-List"
    )

    if not output:
        return "No battery found (desktop PC without UPS)."

    lines = ["Battery:"]
    for line in output.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            k = key.strip()
            v = val.strip()
            if k == "EstimatedChargeRemaining":
                lines.append(f"  Charge: {v}%")
            elif k == "BatteryStatus":
                status_map = {"1": "Discharging", "2": "AC Power", "3": "Fully Charged",
                              "4": "Low", "5": "Critical", "6": "Charging", "7": "Charging High"}
                lines.append(f"  Status: {status_map.get(v, v)}")
            elif k == "Chemistry":
                lines.append(f"  Type: {v}")
            elif k == "DesignCapacity":
                try:
                    lines.append(f"  Design Capacity: {int(v)} mWh")
                except ValueError:
                    pass
            elif k == "FullChargeCapacity":
                try:
                    lines.append(f"  Full Charge: {int(v)} mWh")
                except ValueError:
                    pass

    return "\n".join(lines)


def _get_temperature() -> str:
    output = _ps(
        "Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation "
        "-ErrorAction SilentlyContinue | "
        "Select-Object Name, PercentProcessorPerformance | Format-List"
    )

    if not output:
        return "Temperature sensors not available via WMI. Try a third-party tool like OpenHardwareMonitor."

    lines = ["CPU Performance (higher % = more load):"]
    for line in output.split("\n"):
        if ":" in line and "%" not in line:
            key, val = line.split(":", 1)
            lines.append(f"  {key.strip()}: {val.strip()}%")

    return "\n".join(lines)
