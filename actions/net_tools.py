import re
import subprocess
from urllib.request import urlopen, Request


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


def _ping(host: str, count: int) -> str:
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), host],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout
    except subprocess.TimeoutExpired:
        return f"Ping to {host} timed out."
    except Exception as e:
        return f"Ping failed: {e}"

    lines = [f"Ping results for {host}:"]
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and any(x in stripped for x in ["Reply from", "Request timed out",
                                                      "Destination host unreachable",
                                                      "Minimum", "Approximate", "Packets:"]):
            lines.append(f"  {stripped}")

    return "\n".join(lines) if len(lines) > 1 else f"No ping reply from {host}."


def _traceroute(host: str) -> str:
    try:
        result = subprocess.run(
            ["tracert", "-h", "15", host],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout
    except subprocess.TimeoutExpired:
        return f"Traceroute to {host} timed out."
    except Exception as e:
        return f"Traceroute failed: {e}"

    lines = [f"Traceroute to {host}:"]
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and any(x in stripped for x in [" 1", " 2", " 3", " 4", " 5",
                                                      " 6", " 7", " 8", " 9", "10",
                                                      "Trace complete"]):
            lines.append(f"  {stripped}")
    return "\n".join(lines) if len(lines) > 1 else "No traceroute results."


def _dns_lookup(host: str) -> str:
    try:
        result = subprocess.run(
            ["nslookup", host],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout
    except Exception as e:
        return f"DNS lookup failed: {e}"

    lines = [f"DNS Lookup for {host}:"]
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and any(x in stripped for x in ["Name:", "Address:", "Aliases:"]):
            lines.append(f"  {stripped}")
    return "\n".join(lines)


def _public_ip() -> str:
    try:
        req = Request("https://api.ipify.org?format=json", headers={"User-Agent": "curl/8.0"})
        resp = urlopen(req, timeout=10)
        import json
        data = json.loads(resp.read().decode())
        ip = data.get("ip", "unknown")

        loc_req = Request(f"https://ipapi.co/{ip}/json/", headers={"User-Agent": "curl/8.0"})
        loc_resp = urlopen(loc_req, timeout=10)
        loc_data = json.loads(loc_resp.read().decode())
        city = loc_data.get("city", "?")
        region = loc_data.get("region", "?")
        country = loc_data.get("country_name", "?")
        isp = loc_data.get("org", "?")
        return f"Public IP: {ip}\nLocation: {city}, {region}, {country}\nISP: {isp}"
    except Exception as e:
        return f"Public IP lookup failed: {e}"


def _whois_lookup(host: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Resolve-DnsName -Name \"{host}\" -Type ANY -ErrorAction SilentlyContinue | "
             f"Select-Object Name, Type, IPAddress | Format-Table -AutoSize | Out-String -Width 200)"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.strip()
    except Exception as e:
        return f"Domain lookup failed: {e}"

    if not output:
        return f"No DNS records found for {host}."
    return f"DNS Records for {host}:\n{output[:500]}"


def _speed_test() -> str:
    import urllib.request
    import time

    urls = [
        ("http://speedtest.tele2.net/1MB.zip", "Tele2 1MB"),
        ("http://cachefly.cachefly.net/10mb.test", "CacheFly 10MB"),
    ]

    results = []
    for url, name in urls:
        try:
            start = time.time()
            urllib.request.urlretrieve(url, "NUL", timeout=30)
            elapsed = time.time() - start
            speed_mbps = 8 / elapsed if elapsed > 0 else 0
            results.append(f"{name}: {speed_mbps:.1f} Mbps")
        except Exception as e:
            results.append(f"{name}: Failed ({e})")

    return "\n".join(results) if results else "Speed test failed."


def _dns_flush() -> str:
    try:
        result = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return "DNS cache flushed successfully."
        return f"DNS flush returned: {result.stderr.strip()}"
    except Exception as e:
        return f"DNS flush failed: {e}"


def _ipconfig() -> str:
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout
    except Exception as e:
        return f"IP config failed: {e}"

    lines = ["Network Configuration:"]
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and any(x in stripped for x in ["IPv4 Address", "Default Gateway",
                                                      "Subnet Mask", "DNS Servers",
                                                      "Connection-specific DNS",
                                                      "Ethernet adapter", "Wireless",
                                                      "Wi-Fi"]):
            lines.append(f"  {stripped}")

    return "\n".join(lines[:25])


def _wifi_password(ssid: str) -> str:
    if ssid:
        output = _ps(f'netsh wlan show profile name="{ssid}" key=clear')
    else:
        output = _ps("netsh wlan show profiles")

    if "timed out" in output.lower():
        return "WiFi password query timed out."
    if not output:
        return "No WiFi profiles found." if not ssid else f"Profile '{ssid}' not found."

    if ssid:
        lines = [f"WiFi: {ssid}"]
        for line in output.split("\n"):
            stripped = line.strip()
            if "Key Content" in stripped:
                lines.append(f"  Password: {stripped.split(':', 1)[1].strip()}")
            elif "Authentication" in stripped:
                lines.append(f"  {stripped}")
        return "\n".join(lines)

    lines = ["Saved WiFi profiles:"]
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("All User Profile"):
            name = stripped.split(":")[-1].strip()
            lines.append(f"  - {name}")

    return "\n".join(lines)


def _local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"Local IP: {ip}"
    except Exception:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"Local IP: {ip}"
        except Exception:
            return "Could not determine local IP."


def net_tools(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[Net] {action}")

    try:
        if action in ("ping",):
            host = params.get("host", "8.8.8.8")
            count = params.get("count", 4)
            try:
                count = min(int(count), 10)
            except (ValueError, TypeError):
                count = 4
            return _ping(host, count)

        elif action in ("traceroute", "tracert", "trace"):
            host = params.get("host", "8.8.8.8")
            return _traceroute(host)

        elif action in ("dns_lookup", "dns", "nslookup"):
            host = params.get("host", "google.com")
            return _dns_lookup(host)

        elif action in ("public_ip", "my_ip", "ip", "whats_my_ip"):
            return _public_ip()

        elif action in ("whois", "domain_info"):
            host = params.get("host", "")
            if not host:
                return "Please provide a host (e.g. google.com)."
            return _whois_lookup(host)

        elif action in ("speed_test", "speed", "bandwidth"):
            return _speed_test()

        elif action in ("dns_flush", "flush_dns"):
            return _dns_flush()

        elif action in ("ipconfig", "network_config", "net_config"):
            return _ipconfig()

        elif action in ("wifi_password", "wifi_pass", "show_wifi"):
            ssid = params.get("ssid", "")
            return _wifi_password(ssid)

        elif action in ("local_ip", "lan_ip"):
            return _local_ip()

        else:
            return (
                f"Unknown network action: {action}. "
                f"Available: ping, traceroute, dns_lookup, public_ip, whois, "
                f"speed_test, dns_flush, ipconfig, wifi_password, local_ip"
            )

    except Exception as e:
        return f"Network tool error: {e}"
