"""Lightweight watchlist quotes, independent of full-market pagination."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://push2.eastmoney.com/api/qt/stock/get"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
def quote(code):
    # Exchange selector for Shanghai/Beijing/Shenzhen.
    markets = ["1", "0"] if code.startswith(("6", "9")) else ["0", "1"]
    for market in markets:
        args = urllib.parse.urlencode({"secid": f"{market}.{code}", "fields": "f57,f58,f43,f44,f45,f46,f48,f60,f170", "fltt": 2, "invt": 2})
        try:
            req = urllib.request.Request(BASE + "?" + args, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as response:
                payload = json.load(response)
            d = payload.get("data") or {}
            if str(d.get("f57") or "") == code and isinstance(d.get("f43"), (int, float)):
                return {"code": code, "name": d.get("f58"), "price": d["f43"],
                        "change_pct": d.get("f170"), "high": d.get("f44"),
                        "low": d.get("f45"), "open": d.get("f46"),
                        "previous_close": d.get("f60"), "turnover_cny": d.get("f48")}
        except (OSError, ValueError, TypeError):
            continue
    return None

def main():
    config = json.loads(Path("config/watchlist.json").read_text(encoding="utf-8"))
    codes = {"688827", "300364", "603533"}
    for pool in config.get("pools", {}).values():
        codes.update(str(c) for c in pool.get("codes", []))
    for category in config.get("categories", {}).values():
        if isinstance(category, list):
            codes.update(str(c) for c in category)
    quotes = {}
    for code in sorted(codes):
        if len(code) != 6 or not code.isdigit():
            continue
        item = quote(code)
        if item:
            quotes[code] = item
        time.sleep(0.05)
    if not quotes:
        raise RuntimeError("No watchlist quotes available; keeping prior file")
    path = Path("data/priority_quotes.json")
    path.parent.mkdir(exist_ok=True)
    result = {"collected_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "market_data_timestamp": None,
              "source": "Eastmoney unofficial stock/get",
              "note": "Collection time is not exchange quote time; may be delayed.",
              "expected": len(codes), "count": len(quotes),
              "missing": sorted(codes - quotes.keys()), "quotes": quotes}
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Priority quotes: {len(quotes)}/{len(codes)}; 688827={quotes.get('688827')}")

if __name__ == "__main__":
    main()
