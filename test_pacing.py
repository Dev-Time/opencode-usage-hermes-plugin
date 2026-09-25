"""Synthetic pacing seeds: early-window (UNDER even at high %), late-window
(AHEAD even at moderate %), exact-pace edge case, actual-reset anchoring."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _pacing, _one_month_like  # noqa


ISO = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
WEEK = timedelta(days=7)

def run(weekly, resets_at, now, pct, expect_verdict):
    out = _pacing(pct, resets_at, now=now, span=WEEK if weekly else None)
    print(f"weekly={weekly} reset={resets_at} now={now} pct={pct} -> {out!r}")
    assert out, "no verdict"
    # bare signed pace: behind = '-', ahead = '+', exact = '+0%'
    if expect_verdict == "UNDER":
        assert out.startswith("-"), out
    elif expect_verdict == "AHEAD":
        assert out.startswith("+") and out != "+0%", out
    else:
        assert out == "+0%", out
    return out


# --- weekly, Monday-midnight reset -----------------------------------------
W = "2026-09-28T00:00:00Z"          # window = 2026-09-21 00:00 .. reset (7d)
early = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)   # ~36% elapsed
late = datetime(2026, 9, 27, 22, 0, tzinfo=timezone.utc)    # ~98% elapsed
run(True, W, early, 5, "UNDER")      # early window, low % -> UNDER
run(True, W, early, 90, "AHEAD")     # early window, high % -> AHEAD
run(True, W, late, 100, "AHEAD")     # late window, above pace -> AHEAD
run(True, W, late, 30, "UNDER")      # late window, moderate % -> UNDER
# exact pace: now at 50% of window, usage 50 -> ok
mid = ISO(W) - timedelta(days=3, hours=12)
assert _pacing(50, W, now=mid, span=WEEK) == "+0%", "exact pace weekly"

# --- weekly, NON-Monday / non-midnight reset: window must END at resetsAt --
# Old code anchored to truncated-Monday; with reset Wed 19:53Z it built a
# 9.8-day window. Now: start = reset - 7d exactly.
W2 = "2026-09-30T19:53:39Z"         # Wednesday, wall-clock time
start2 = ISO(W2) - timedelta(days=7)
mid2 = start2 + (ISO(W2) - start2) / 2        # exactly 50% elapsed
assert _pacing(50, W2, now=mid2, span=WEEK) == "+0%", "non-Monday exact pace"
run(True, W2, start2 + timedelta(hours=24), 5, "UNDER")    # 14% elapsed, 5% -> UNDER
run(True, W2, start2 + timedelta(hours=24), 80, "AHEAD")   # 14% elapsed, 80% -> AHEAD
run(True, W2, ISO(W2) - timedelta(hours=6), 100, "AHEAD")  # ~96% elapsed, 100% -> AHEAD

# --- rolling 5h: same proportional rule, span = the window's 5h ------------
FIVE_H = timedelta(hours=5)
R = "2026-09-25T18:00:00Z"          # window = 13:00 .. reset (5h)
rstart = ISO(R) - FIVE_H
assert _pacing(40, R, now=rstart + timedelta(hours=2), span=FIVE_H) == "+0%", "rolling exact pace"
under = _pacing(5, R, now=rstart + timedelta(hours=1), span=FIVE_H)      # 20% elapsed
assert under.startswith("-"), under
ahead = _pacing(95, R, now=ISO(R) - timedelta(minutes=30), span=FIVE_H)  # 90% elapsed
assert ahead.startswith("+") and ahead != "+0%", ahead

# --- monthly ---------------------------------------------------------------
M = "2026-10-14T19:53:39Z"          # reset-anchored, previous month span
mstart = ISO(M) - _one_month_like(ISO(M))     # 2026-09-14 19:53 (30d span)
mnow = mstart + (ISO(M) - mstart) / 2
assert _pacing(50, M, now=mnow) == "+0%", "exact pace monthly"
run(False, M, mstart + timedelta(days=3), 3, "UNDER")      # 10% elapsed, 3% -> UNDER
run(False, M, ISO(M) - timedelta(days=2), 95, "AHEAD")     # 93% elapsed, 95% -> AHEAD
# short-month awareness: reset Mar 1 -> Feb window (28d, non-leap 2027)
f27 = _pacing(50, "2027-03-01T00:00:00Z",
              now=datetime(2027, 2, 15, 0, 0, tzinfo=timezone.utc))
print(f"feb short month -> {f27!r}")
assert f27 == "+0%", f27               # 14/28 = 50% elapsed, 50% usage

print("ALL PACING SEEDS PASS")
