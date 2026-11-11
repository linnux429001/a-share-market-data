"""Detect board acceleration from successive full-market snapshots; no trade recommendations."""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path("data")
HISTORY = ROOT / "board_history.json"
OUTPUT = ROOT / "board_signals.json"
MAX_SNAPSHOTS = 240

def number(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def extract(snapshot):
    result = {}
    for kind in ("industry", "concept"):
        for row in snapshot.get(kind, {}).get("top", []):
            code = str(row.get("code", ""))
            if not code:
                continue
            result[kind + ":" + code] = {
                "code": code, "name": row.get("name"), "kind": kind,
                "change_pct": number(row.get("change_pct")),
                "turnover_cny": number(row.get("turnover_cny")),
                "turnover_rate_pct": number(row.get("turnover_rate_pct")),
            }
    return result

def main():
    snap = json.loads((ROOT / "latest.json").read_text(encoding="utf-8"))
    collected = snap.get("collected_at")
    if not collected:
        raise ValueError("Missing snapshot collection time")
    datetime.fromisoformat(collected)
    boards = extract(snap)
    if len(boards) < 30:
        raise ValueError("Insufficient board coverage")
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    history = [h for h in history if h.get("collected_at") != collected]
    # Compare within the same market date; turnover is cumulative and cannot be compared as a flow.
    today = collected[:10]
    previous = next((h for h in reversed(history) if h.get("collected_at", "")[:10] == today), None)
    alerts = []
    if previous:
        elapsed = (datetime.fromisoformat(collected) - datetime.fromisoformat(previous["collected_at"])).total_seconds()
        if 0 < elapsed <= 7200:
            for key, now in boards.items():
                old = previous.get("boards", {}).get(key)
                if not old:
                    continue
                current, earlier = now["change_pct"], old.get("change_pct")
                if current is None or earlier is None:
                    continue
                delta = round(current - earlier, 2)
                # Candidate threshold; not a validated predictive signal.
                if delta >= 1.5 and current >= 2.0:
                    alerts.append({**now, "delta_change_pct_points": delta,
                                   "previous_change_pct": earlier,
                                   "signal": "board_acceleration_candidate",
                                   "requires_validation": True})
    alerts.sort(key=lambda x: (x["delta_change_pct_points"], x["change_pct"]), reverse=True)
    output = {
        "collected_at": collected, "previous_snapshot_at": previous.get("collected_at") if previous else None,
        "source": snap.get("source"), "market_data_timestamp": snap.get("market_data_timestamp"),
        "data_quality": "unverified_quote_time",
        "signal_scope": "board_acceleration_only",
        "alert_count": len(alerts), "alerts": alerts[:30],
        "note": "Threshold-based observation, not a buy signal. Verify timestamps, news and constituent stocks independently. No alert does not prove no opportunity."
    }
    ROOT.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history.append({"collected_at": collected, "boards": boards})
    HISTORY.write_text(json.dumps(history[-MAX_SNAPSHOTS:], ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Board signals: {len(alerts)} candidates; previous={bool(previous)}")

if __name__ == "__main__":
    main()
