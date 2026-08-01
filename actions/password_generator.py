import string
import secrets
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def password_generator(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "generate").strip().lower()

    if player:
        player.write_log(f"[Password] action={action}")

    try:
        if action in ("generate", "gen", "create"):
            length = params.get("length", 16)
            include_upper = params.get("uppercase", True)
            include_lower = params.get("lowercase", True)
            include_digits = params.get("digits", True)
            include_symbols = params.get("symbols", True)
            count = params.get("count", 1)
            exclude = params.get("exclude", "")

            try:
                length = int(length)
                count = int(count)
            except (ValueError, TypeError):
                return "Length and count must be numbers."

            if length < 4:
                return "Password length must be at least 4."
            if length > 128:
                return "Password length cannot exceed 128."

            if count < 1:
                count = 1
            if count > 20:
                count = 20

            return _generate_passwords(
                length, include_upper, include_lower,
                include_digits, include_symbols, count, exclude
            )

        elif action in ("pin", "numeric", "number"):
            length = params.get("length", 6)
            count = params.get("count", 1)

            try:
                length = int(length)
                count = int(count)
            except (ValueError, TypeError):
                return "Length must be a number."

            if length < 3 or length > 20:
                return "PIN length must be between 3 and 20."

            return _generate_pins(length, min(count, 10))

        elif action in ("passphrase", "phrase", "words"):
            word_count = params.get("words", 4)
            separator = params.get("separator", "-")
            capitalize = params.get("capitalize", False)

            try:
                word_count = int(word_count)
            except (ValueError, TypeError):
                return "Word count must be a number."

            if word_count < 2 or word_count > 12:
                return "Word count must be between 2 and 12."

            return _generate_passphrase(word_count, separator, capitalize)

        elif action in ("strength", "check", "analyze"):
            password = params.get("password", "").strip()
            if not password:
                return "A password is required to check strength."
            return _check_strength(password)

        elif action in ("save", "store"):
            name = params.get("name", "").strip()
            password = params.get("password", "").strip()
            if not name or not password:
                return "Both name and password are required to save."
            return _save_password(name, password)

        elif action == "list":
            return _list_saved()

        return (
            f"Unknown action: '{action}'. "
            f"Available: generate, pin, passphrase, strength, save, list"
        )

    except Exception as e:
        return f"Password generator failed: {e}"


def _generate_passwords(
    length: int, upper: bool, lower: bool,
    digits: bool, symbols: bool, count: int, exclude: str
) -> str:
    chars = ""
    if upper:
        chars += string.ascii_uppercase
    if lower:
        chars += string.ascii_lowercase
    if digits:
        chars += string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    if not chars:
        return "At least one character type must be enabled."

    if exclude:
        for ch in exclude:
            chars = chars.replace(ch, "")
        if not chars:
            return "All characters excluded. Nothing to generate."

    passwords = []
    for _ in range(count):
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        passwords.append(pwd)

    if count == 1:
        return f"Password ({length} chars): {passwords[0]}"

    lines = [f"{count} passwords ({length} chars each):"]
    for i, pwd in enumerate(passwords, 1):
        lines.append(f"  {i}. {pwd}")
    return "\n".join(lines)


def _generate_pins(length: int, count: int) -> str:
    pins = []
    for _ in range(count):
        pin = "".join(secrets.choice(string.digits) for _ in range(length))
        pins.append(pin)

    if count == 1:
        return f"PIN ({length} digits): {pins[0]}"

    lines = [f"{count} PINs ({length} digits each):"]
    for i, pin in enumerate(pins, 1):
        lines.append(f"  {i}. {pin}")
    return "\n".join(lines)


def _generate_passphrase(word_count: int, separator: str, capitalize: bool) -> str:
    words = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
        "hotel", "india", "juliett", "kilo", "lima", "mike", "november",
        "oscar", "papa", "quebec", "romeo", "sierra", "tango", "uniform",
        "victor", "whiskey", "xray", "yankee", "zulu",
        "cloud", "storm", "river", "mountain", "ocean", "forest", "flame",
        "crystal", "shadow", "thunder", "silver", "golden", "iron", "steel",
        "falcon", "eagle", "hawk", "wolf", "tiger", "panther",
        "cosmic", "solar", "lunar", "stellar", "nova", "comet",
        "amber", "azure", "crimson", "emerald", "violet", "jade",
    ]

    selected = secrets.SystemRandom().sample(words, min(word_count, len(words)))
    if capitalize:
        selected = [w.capitalize() for w in selected]
    passphrase = separator.join(selected)

    entropy = len(selected) * 4.7
    return f"Passphrase: {passphrase}\nWords: {len(selected)} | Approx. entropy: {entropy:.0f} bits"


def _check_strength(password: str) -> str:
    length = len(password)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password)

    score = 0
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if length >= 16:
        score += 1
    if has_upper:
        score += 1
    if has_lower:
        score += 1
    if has_digit:
        score += 1
    if has_symbol:
        score += 1

    if score <= 2:
        label = "Very Weak"
    elif score <= 3:
        label = "Weak"
    elif score <= 5:
        label = "Moderate"
    elif score <= 6:
        label = "Strong"
    else:
        label = "Very Strong"

    entropy = length * 4.7

    details = ", ".join(
        f for f, v in [
            ("uppercase", has_upper), ("lowercase", has_lower),
            ("digits", has_digit), ("symbols", has_symbol),
        ] if v
    ) or "none"

    return (
        f"Strength: {label}\n"
        f"Length: {length} | Entropy: {entropy:.0f} bits\n"
        f"Types: {details}\n"
        f"Score: {score}/7"
    )


def _save_password(name: str, password: str) -> str:
    vault_path = _get_base_dir() / "config" / "password_vault.json"
    vault_path.parent.mkdir(parents=True, exist_ok=True)

    vault = {}
    if vault_path.exists():
        try:
            import json
            vault = json.loads(vault_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            vault = {}

    vault[name] = password
    vault_path.write_text(
        json.dumps(vault, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return f"Password '{name}' saved to local vault."


def _list_saved() -> str:
    vault_path = _get_base_dir() / "config" / "password_vault.json"
    if not vault_path.exists():
        return "No saved passwords."

    try:
        import json
        vault = json.loads(vault_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return "Could not read password vault."

    if not vault:
        return "No saved passwords."

    lines = ["Saved passwords:"]
    for name in vault:
        lines.append(f"  - {name}")
    return "\n".join(lines)
