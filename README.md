# A-share market data collector

Proof-of-concept using Eastmoney's unofficial public web endpoints. This is **not** a licensed exchange market feed. Data may be delayed, stale, blocked, or changed without notice.

## Test

Run GitHub Actions > Collect A-share market snapshot > Run workflow.

If successful, see `data/latest.json`. The `collected_at` value is collection time, **not** verified exchange quote time.

Scheduled times use UTC. GitHub Actions schedules can be delayed or skipped. No trading automation is included.
