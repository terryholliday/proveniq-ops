"""
Ledger reconciliation sweeper (bounded).
Rules:
- if LOCKED_PENDING_LEDGER > 1 hour: poll ledger
- every 15m
- max 5 attempts
- verify ledger signature
- emit LOSS_AUTHORIZED / LOSS_DENIED or LEDGER_SYNC_FAILED
"""
def run():
    pass
