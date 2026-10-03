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
            "weekly": {"percent": 41, "resetsAt": _pl(7)},
            "monthly": {"percent": 60, "resetsAt": _pl(30)},
        }
    }


pl._fetch_usage = _full

line = pl._usage_line()
print("LINE:", line)
rows = line.split("\n")
assert len(rows) == 3, line                       # three paced limits exceed L1
assert re.match(r"Go: 5h 72% \([+-]\d+%\) \d+\.\dh$", rows[0]), rows[0]
assert re.match(r"Go: wk 41% \([+-]\d+%\) \d+(?:\.\d)?d$", rows[1]), rows[1]
assert re.match(r"Go: mo 60% \([+-]\d+%\) \d+(?:\.\d)?d$", rows[2]), rows[2]
assert "resets in" not in line, line                      # compact relative reset
assert "pace" not in line and "AHEAD" not in line and "UNDER" not in line, line
assert all(len(l) <= pl._BUDGET for l in rows), line
rolling, wk, mo = rows
assert re.search(r"\([+-]\d+%\)", rolling), f"rolling must pace: {rolling}"
assert re.search(r"\([+-]\d+%\)", wk) and re.search(r"\([+-]\d+%\)", mo), line

# degrade: window without resetsAt -> no pace, no reset, no crash
pl._fetch_usage = lambda: {"usage": {"weekly": {"percent": 41}}}
line2 = pl._usage_line()
print("LINE2:", line2)
assert line2 == "wk 41%", line2

# transform: echo-footer stripped, one fresh footer block appended
pl._fetch_usage = _full
out = pl.transform_llm_output("hello\n_Go: 5h 72% (resets in 1h) · wk 41% [pace AHEAD +10%]_",
                              platform="telegram")
print("TRANSFORM:", out)
assert out.startswith("hello\n"), out
footers = [l for l in out.split("\n") if pl._is_footer_line(l)]
assert len(footers) == 3, out                       # one fresh block, echo gone
assert "[pace" not in out and "resets in" not in out, out

print("INTEGRATION OK")
