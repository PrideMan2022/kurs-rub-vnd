"""Собирает курсы в site/rates.json. Запускается в GitHub Actions каждый час.

Если источник не ответил, остаётся его прошлое значение со старой датой:
страница показывает дату у каждого источника.
"""
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "site" / "rates.json"
# Корневой сертификат Минцифры (gu-st.ru): им подписан сертификат api.tbank.ru.
RU_CA = ROOT / "certs" / "russian_trusted_root_ca.pem"
HEADERS = {"User-Agent": "kurs-rub-vnd (+github actions)"}
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(url, cafile=None):
    ctx = ssl.create_default_context(cafile=cafile) if cafile else None
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        return json.load(r)


def cbr():
    d = get("https://www.cbr-xml-daily.ru/daily_json.js")
    v = d["Valute"]
    return {
        "date": d["Date"],
        "usd": v["USD"]["Value"] / v["USD"]["Nominal"],
        "vnd_per_rub": v["VND"]["Nominal"] / v["VND"]["Value"],
    }


def vcb():
    d = get("https://www.vietcombank.com.vn/api/exchangerates?date=now")
    r = {x["currencyCode"]: x for x in d["Data"]}
    return {
        "date": d["UpdatedDate"],
        "rub_buy": float(r["RUB"]["transfer"]),
        "usd_buy": float(r["USD"]["transfer"]),
    }


def tbank():
    d = get("https://api.tbank.ru/v1/currency_rates?from=USD&to=RUB", cafile=RU_CA)
    r = next(x for x in d["payload"]["rates"] if x["category"] == "DebitCardsOperations")
    return {"date": NOW, "usd_buy": r["buy"], "usd_sell": r["sell"]}


def usdt():
    d = get("https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=vnd,rub")
    return {"date": NOW, "vnd": d["tether"]["vnd"], "rub": d["tether"]["rub"]}


def main():
    rates = json.loads(OUT.read_text()) if OUT.exists() else {}
    for name, fetch in {"cbr": cbr, "vcb": vcb, "tbank": tbank, "usdt": usdt}.items():
        try:
            rates[name] = fetch()
        except Exception as e:
            print(f"{name}: не получилось ({e}), оставляю прошлое значение")
    rates["updated"] = NOW
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rates, ensure_ascii=False, indent=1))
    print(json.dumps(rates, ensure_ascii=False))


if __name__ == "__main__":
    main()
