"""Analyze public watchlists using verified snapshot data, without private holdings."""
import json
from pathlib import Path

def main():
    snapshot = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    config = json.loads(Path("config/watchlist.json").read_text(encoding="utf-8"))
    stocks = snapshot.get("tracked_stocks", [])
    codes = {x["code"] for x in stocks}
    pools = config.get("pools", {})
    groups = {}
    for name, pool in pools.items():
        if not isinstance(pool, dict):
            continue
        members = [str(x) for x in pool.get("codes", [])]
        groups[name] = {"expected": len(members), "found": [x for x in stocks if x["code"] in members],
                        "missing": [x for x in members if x not in codes]}
    # Single-snapshot momentum is only an observation, not a validated buy signal.
    ranked = sorted((x for x in stocks if isinstance(x.get("change_pct"), (int, float))
                     and isinstance(x.get("turnover_cny"), (int, float))),
                    key=lambda x: (x["change_pct"], x["turnover_cny"]), reverse=True)
    result = {"collected_at": snapshot.get("collected_at"),
              "market_data_timestamp": snapshot.get("market_data_timestamp"),
              "data_quality": "single_snapshot_no_verified_quote_time",
              "pools": groups,
              "focus_20": ranked[:20], "next_day_5": [],
              "simulated_positions": [],
              "note": "Top 20 is an activity ranking, not a buy recommendation. Historical strength and breakout signals require dated history."}
    path = Path("data/watchlist_analysis.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Analyzed {len(stocks)} tracked stocks")

if __name__ == "__main__":
    main()
