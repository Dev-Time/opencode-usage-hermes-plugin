"""Differential: old Monday-anchor window vs actual-reset window (non-Monday reset)."""
from datetime import datetime, timedelta, timezone

ISO = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
reset = ISO("2026-09-30T19:53:39Z")  # Wednesday, wall-clock time

# old code: truncate to midnight, back to Monday, minus one week
anchor = reset.replace(hour=0, minute=0, second=0, microsecond=0)
old_start = anchor - timedelta(days=anchor.weekday(), weeks=1)
new_start = reset - timedelta(days=7)

now = new_start + (reset - new_start) / 2  # mid of the TRUE window, usage 50

def expected(start):
    return (now - start).total_seconds() / (reset - start).total_seconds() * 100

print(f"old window: {old_start} .. {reset} ({(reset-old_start).total_seconds()/86400:.1f}d)"
      f" expected_at_same_instant={expected(old_start):.1f}% -> usage 50 tagged "
      f"{'UNDER (WRONG)' if expected(old_start) > 51 else 'ok'}")
print(f"new window: {new_start} .. {reset} ({(reset-new_start).total_seconds()/86400:.0f}d)"
      f" expected_at_same_instant={expected(new_start):.1f}% -> usage 50 tagged "
      f"{'ok' if abs(expected(new_start) - 50) <= 1 else 'WRONG'}")
