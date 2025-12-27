"""
Deliver webhooks from outbox with retry and backoff.
- select PENDING where next_attempt_at <= now
- send HTTP with signature
- update status SENT or FAILED
- increment attempts and schedule next_attempt_at
"""
def run():
    pass
