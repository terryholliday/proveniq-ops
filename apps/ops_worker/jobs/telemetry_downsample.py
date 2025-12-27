"""
Telemetry retention + downsampling.
- raw -> 1m aggregates (keep 7d)
- 1m -> 15m aggregates (keep 30d)
- purge raw >24h
- purge agg15m >30d
"""
def run():
    pass
