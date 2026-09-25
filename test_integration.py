"""Integration: footer line shape from a mocked /usage payload."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import __init__ as pl

_now = datetime.now(timezone.utc)
_pl = lambda d, h=0: (_now + timedelta(days=d, hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _full():
    return {
        "usage": {
            "rolling": {"percent": 72, "resetsAt": _pl(0, 3)},
            "weekly": {"percent": 41, "resetsAt": "2026-09-28T00:00:00Z"},
            "monthly": {"percent": 60, "resetsAt": "2026-10-14T19:53:39Z"},
        }
    }


pl._fetch_usage = _full

line = pl._usage_line()
print("LINE:", line)
assert line.startswith("5h 72%"), line
assert "resets in" not in line, line                      # compact relative reset
assert "pace" not in line and "AHEAD" not in line and "UNDER" not in line, line
assert all(len(l) <= pl._BUDGET for l in line.split("\n")), line
rolling = line.split(" · ")[0]
assert not re.search(r"[+-]\d+%", rolling), f"rolling must not pace: {rolling}"
wk, mo = line.split(" · ")[1], line.split(" · ")[2]
assert re.search(r"[+-]\d+%", wk) and re.search(r"[+-]\d+%", mo), line

# degrade: window without resetsAt -> no pace, no reset, no crash
pl._fetch_usage = lambda: {"usage": {"weekly": {"percent": 41}}}
line2 = pl._usage_line()
print("LINE2:", line2)
assert line2 == "wk 41%", line2

# transform: echo-footer stripped, one fresh footer appended
pl._fetch_usage = _full
out = pl.transform_llm_output("hello\n_Go: 5h 72% (resets in 1h) · wk 41% [pace AHEAD +10%]_",
                              platform="telegram")
print("TRANSFORM:", out)
assert out.startswith("hello\n"), out
footers = [l for l in out.split("\n") if pl._is_footer_line(l)]
assert len(footers) == 1, out

print("INTEGRATION OK")
