"""
ops-worker entrypoint.
Run jobs:
- projections builder (rebuild/read-model updates)
- outbox dispatcher
- ledger reconciliation sweeper
- telemetry downsampling & retention purge
- bishop recommendation generator
"""
def main():
    pass

if __name__ == "__main__":
    main()
