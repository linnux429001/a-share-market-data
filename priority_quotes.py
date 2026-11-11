"""Lightweight watchlist quotes, independent of full-market pagination."""
import json
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def resilient_quote(code):
    for attempt in range(3):
        result = quote(code)
        if result is not None:
            return result
        time.sleep(0.4 * (attempt + 1) + random.uniform(0, 0.2))
    return None

def main():
    config = json.loads(Path("config/watchlist.json").read_text(encoding="utf-8"))
    codes = {"688827", "300364", "603533"}
    for pool in config.get("pools", {}).values():
        codes.update(str(c) for c in pool.get("codes", []))
    for category in config.get("categories", {}).values():
        if isinstance(category, list):
            codes.update(str(c) for c in category)
    codes = {code for code in codes if len(code) == 6 and code.isdigit()}
    quotes = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(resilient_quote, code): code for code in sorted(codes)}
        for future in as_completed(futures):
            code = futures[future]
            try:
                item = future.result()
            except Exception as exc:
                print(f"Quote error {code}: {exc}")
                item = None
            if item:
                quotes[code] = item
    # Reuse only SAME-DAY full-market snapshots for quotes missing from the
    # lightweight endpoint. Never silently copy a prior-day closing price.
    snapshot_path = Path("data/latest.json")
    fallback_codes = []
    now = datetime.now(timezone(timedelta(hours=8)))
    if snapshot_path.exists():
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            stamp = datetime.fromisoformat(snapshot["collected_at"])
            if stamp.date() == now.date():
                full = {x["code"]: x for x in snapshot.get("tracked_stocks", [])}
                for code in sorted(codes - quotes.keys()):
                    item = full.get(code)
                    if item and isinstance(item.get("price"), (int, float)):
                        quotes[code] = {key: item.get(key) for key in
                            ("code", "name", "price", "change_pct", "high",
                             "low", "open", "previous_close", "turnover_cny")}
                        fallback_codes.append(code)
        except (ValueError, KeyError, TypeError) as exc:
            print(f"Full-market fallback unavailable: {exc}")
    if not quotes:
        raise RuntimeError("No watchlist quotes available; keeping prior file")
    path = Path("data/priority_quotes.json")
    path.parent.mkdir(exist_ok=True)
    result = {"collected_at": now.isoformat(),
              "market_data_timestamp": None,
              "source": "Eastmoney unofficial stock/get",
              "note": "Collection time is not exchange quote time; may be delayed.",
              "expected": len(codes), "count": len(quotes),
              "fallback_from_same_day_snapshot": fallback_codes,
              "data_quality": "unverified_exchange_timestamp",
              "missing": sorted(codes - quotes.keys()), "quotes": quotes}
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Bounded local history for detecting changes between collection runs.
    history_path = Path("data/priority_history.json")
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8")).get("snapshots", [])
        except (ValueError, TypeError):
            history = []
    history.append({"collected_at": result["collected_at"],
                    "prices": {code: {"price": q["price"],
                                      "change_pct": q.get("change_pct"),
                                      "turnover_cny": q.get("turnover_cny")}
                               for code, q in quotes.items()}})
    history = history[-120:]
    history_path.write_text(json.dumps({"snapshots": history},
                            ensure_ascii=False, separators=(",", ":")) + "\\n", encoding="utf-8")
    print(f"Priority quotes: {len(quotes)}/{len(codes)}; fallback={fallback_codes}; 688827={quotes.get('688827')}")

if __name__ == "__main__":
    main()
