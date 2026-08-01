import json
import urllib.request
import urllib.error


def currency_converter(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "convert").strip().lower()

    if player:
        player.write_log(f"[Currency] action={action}")

    try:
        if action in ("convert", "exchange"):
            amount = params.get("amount", 1)
            from_cur = params.get("from", "USD").strip().upper()
            to_cur = params.get("to", "INR").strip().upper()

            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return f"Invalid amount: {amount}"

            return _convert_currency(amount, from_cur, to_cur)

        elif action in ("list", "rates", "supported"):
            return _list_supported()

        elif action == "base":
            base = params.get("base", "USD").strip().upper()
            return _get_rates(base)

        return (
            f"Unknown action: '{action}'. "
            f"Available: convert, list, base"
        )

    except Exception as e:
        return f"Currency converter failed: {e}"


def _convert_currency(amount: float, from_cur: str, to_cur: str) -> str:
    if from_cur == to_cur:
        return f"{amount} {from_cur} = {amount} {to_cur}"

    rates = _fetch_rates(from_cur)
    if isinstance(rates, str):
        return rates

    if to_cur not in rates:
        return f"Currency '{to_cur}' not found. Use 'list' action to see supported currencies."

    converted = amount * rates[to_cur]
    return f"{amount:.2f} {from_cur} = {converted:.2f} {to_cur} (rate: 1 {from_cur} = {rates[to_cur]:.4f} {to_cur})"


def _get_rates(base: str) -> str:
    rates = _fetch_rates(base)
    if isinstance(rates, str):
        return rates

    majors = ["USD", "EUR", "GBP", "JPY", "INR", "CNY", "CAD", "AUD", "CHF", "BRL", "KRW", "SGD"]
    lines = [f"Exchange rates for {base}:"]
    for cur in majors:
        if cur in rates:
            lines.append(f"  {cur}: {rates[cur]:.4f}")

    return "\n".join(lines)


def _fetch_rates(base: str) -> dict | str:
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{base}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "VAYU/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("rates", {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Currency '{base}' not recognized by the exchange rate API."
        return f"Exchange rate API error: {e.code}"
    except urllib.error.URLError as e:
        return f"Could not fetch exchange rates: {e.reason}"
    except json.JSONDecodeError:
        return "Failed to parse exchange rate data."
    except Exception as e:
        return f"Error fetching rates: {e}"


def _list_supported() -> str:
    rates = _fetch_rates("USD")
    if isinstance(rates, str):
        return rates

    currencies = sorted(rates.keys())
    lines = [f"Supported currencies ({len(currencies)} total):"]
    for i, cur in enumerate(currencies):
        lines.append(f"  {cur}")
        if i >= 30:
            lines.append(f"  ... and {len(currencies) - 30} more")
            break

    return "\n".join(lines)
