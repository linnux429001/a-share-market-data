"""A-share market snapshot collector (Eastmoney unofficial API)."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASES = ("https://push2.eastmoney.com/api/qt/",
         "https://push2delay.eastmoney.com/api/qt/")
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
CST = timezone(timedelta(hours=8))
CONFIG = Path("config/watchlist.json")
OUT = Path("data/latest.json")
FIELDS = "f12,f14,f2,f3,f5,f6,f8,f15,f16,f17,f18"
# Eastmoney market selectors: Shanghai/Shenzhen A-share and Beijing exchange.
STOCK_FILTERS = ("m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,"
                 "m:0+t:81,m:0+t:82,m:0+t:83,m:0+t:87,m:0+t:88,m:0+t:89")

def get(path, params):
    """Try both public Eastmoney hosts; never silently substitute old data."""
    query = urllib.parse.urlencode(params)
    errors = []
    for base in BASES:
        url = base + path + "?" + query
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=HEADERS), timeout=12
                ) as response:
                    payload = json.load(response)
                if payload.get("rc") != 0 or not isinstance(payload.get("data"), dict):
                    raise ValueError("Invalid API response")
                return payload["data"]
            except (OSError, ValueError) as exc:
                errors.append(f"{base}: {type(exc).__name__}: {exc}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
    raise RuntimeError("All Eastmoney endpoints failed: " + " | ".join(errors[-4:]))

def list_all(fs, fields=FIELDS, page_size=100):
    rows, seen = [], set()
    total = None
    for page in range(1, 301):
        d = get("clist/get", {"pn": page, "pz": page_size, "po": 1, "np": 1,
                              "fltt": 2, "invt": 2, "fid": "f3", "fs": fs, "fields": fields})
        if total is None:
            total = int(d.get("total") or 0)
            if total <= 0:
                raise ValueError(f"Invalid total for {fs}")
        batch = d.get("diff") or []
        if isinstance(batch, dict):
            batch = list(batch.values())
        if not batch:
            break
        for x in batch:
            code = str(x.get("f12") or "")
            if not code or code in seen:
                continue
            seen.add(code)
            rows.append(x)
        if len(rows) >= total:
            break
    if len(rows) != total:
        raise ValueError(f"Incomplete or duplicate page results for {fs}: {len(rows)}/{total}")
    return total, rows

def boards(kind):
    total, raw = list_all(f"m:90+t:{kind}")
    return {"total": total, "top": [
        {"code": x["f12"], "name": x.get("f14"), "change_pct": x.get("f3"),
         "turnover_cny": x.get("f6"), "turnover_rate_pct": x.get("f8")}
        for x in raw]}

def stock_row(x):
    return {"code": str(x["f12"]), "name": x.get("f14"), "price": x.get("f2"),
            "change_pct": x.get("f3"), "volume": x.get("f5"),
            "turnover_cny": x.get("f6"), "turnover_rate_pct": x.get("f8"),
            "high": x.get("f15"), "low": x.get("f16"), "open": x.get("f17"),
            "previous_close": x.get("f18")}

def fallback_stock(code):
    secid = ("1." if code.startswith(("6", "9")) else "0.") + code
    d = get("stock/get", {"secid": secid, "fields": "f57,f58,f43,f44,f45,f46,f48,f60,f170",
                          "fltt": 2, "invt": 2})
    return {"code": code, "name": d.get("f58"), "price": d.get("f43"),
            "change_pct": d.get("f170"), "high": d.get("f44"), "low": d.get("f45"),
            "open": d.get("f46"), "previous_close": d.get("f60"),
            "turnover_cny": d.get("f48")}

def config_codes():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    codes = set(["300364", "603533"])
    for group in config.get("pools", {}).values():
        if isinstance(group, dict):
            codes.update(str(code) for code in group.get("codes", []))
    for members in config.get("categories", {}).values():
        if isinstance(members, list):
            codes.update(str(code) for code in members)
    if any(len(code) != 6 or not code.isdigit() for code in codes):
        raise ValueError("Watchlist contains invalid six-digit ticker")
    return sorted(codes)

def main():
    industry, concept = boards(2), boards(3)
    stock_total, raw = list_all(STOCK_FILTERS, page_size=500)
    stocks = [stock_row(x) for x in raw]
    lookup = {x["code"]: x for x in stocks}
    selected = {}
    missing = []
    for code in config_codes():
        item = lookup.get(code)
        if item is None:
            try:
                item = fallback_stock(code)
            except (OSError, ValueError, RuntimeError):
                missing.append(code)
                continue
        selected[code] = item
    if "300364" not in selected or "603533" not in selected:
        raise ValueError("Legacy watchlist stocks missing")
    result = {
        "collected_at": datetime.now(CST).isoformat(),
        "timezone": "Asia/Shanghai",
        "source": "Eastmoney public web API (unofficial)",
        "market_data_timestamp": None,
        "note": "Collection time is not verified quote time; prices may be stale.",
        "industry": industry, "concept": concept,
        "watchlist": [selected[x] for x in ("300364", "603533")],
        "tracked_stocks": list(selected.values()),
        "missing_tracked_codes": missing,
        "stock_universe": {"total": stock_total, "stocks": stocks}
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix(".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(OUT)
    print(f"Collected {len(industry['top'])} industry boards, {len(concept['top'])} concepts, "
          f"{len(stocks)} market stocks, {len(selected)} tracked stocks; missing={missing}")

if __name__ == "__main__":
    main()
