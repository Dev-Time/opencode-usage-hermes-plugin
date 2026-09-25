"""Pure renderer ladder: L0 single line -> L1 rolling-reset drop -> 3 lines
(FOOTER-SPEC §4/§5). Inputs are segment tuples, outputs exact strings."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _BUDGET, _compact_time, _is_footer_line, _render_footer, _resets_in  # noqa

# Segment resets arrive in compact form (see _compact_time): largest unit only,
# one decimal for hours/days, whole days drop the '.0'.
NORMAL = [
    ("5h", "6", "", "3.2h"),
    ("wk", "7", "+12%", "3.2d"),   # 7% < 10% -> pace suppressed at render
    ("mo", "42", "-8%", "20.2d"),
]
L0 = "5h 6% 3.2h · wk 7% 3.2d · mo 42% (-8%) 20.2d"   # 44 visible
L1 = "5h 6% · wk 7% 3.2d · mo 42% (-8%) 20.2d"       # 39 visible

# L0 fits the budget -> single line
out = _render_footer(NORMAL)
assert out == L0, out
assert len(out) == 44 <= _BUDGET

# L0 over budget -> L1 (rolling reset dropped, nothing else)
out = _render_footer(NORMAL, budget=43)
assert out == L1, out
assert len(out) == 39 <= 43

# L1 still over budget -> exactly 3 lines, every field kept
out = _render_footer(NORMAL, budget=38)
assert out == "Go: 5h 6% 3.2h\nGo: wk 7% 3.2d\nGo: mo 42% (-8%) 20.2d", out
assert [len(r) for r in out.split("\n")] == [14, 14, 22]

# canonical escalation (§5): worst-case values -> L0 55 > 50, L1 50 == budget
assert len("5h 100% 5.0h · wk 100% (+100%) 7d · mo 100% (+100%) 30d") == 55
assert len("5h 100% · wk 100% (+100%) 7d · mo 100% (+100%) 30d") == 50
WORST = [
    ("5h", "100", "", "5.0h"),
    ("wk", "100", "+100%", "7d"),
    ("mo", "100", "+100%", "30d"),
]
out = _render_footer(WORST)
assert out == "5h 100% · wk 100% (+100%) 7d · mo 100% (+100%) 30d", out
assert len(out) == 50 == _BUDGET

# one byte past the budget -> exactly 3 lines, every row within budget
rows = _render_footer(WORST, budget=49).split("\n")
assert rows == ["Go: 5h 100% 5.0h", "Go: wk 100% (+100%) 7d", "Go: mo 100% (+100%) 30d"], rows
assert [len(r) for r in rows] == [16, 22, 23]
assert all(len(r) <= 49 for r in rows)

# L1 reachable: short paces -> L1, never forced to 3 lines
MID = [
    ("5h", "100", "", "5.0h"),
    ("wk", "100", "+10%", "7d"),
    ("mo", "100", "-20%", "30d"),
]
out = _render_footer(MID)
assert out == "5h 100% · wk 100% (+10%) 7d · mo 100% (-20%) 30d", out
assert len(out) == 48 <= _BUDGET

# spec example: one largest unit, one decimal, parenthesized pacing (all 3)
assert _render_footer([("5h", "0", "", "4.8h"), ("wk", "11", "-58%", "2.1d"),
                       ("mo", "44", "+7%", "19d")]) == \
    "5h 0% 4.8h · wk 11% (-58%) 2.1d · mo 44% (+7%) 19d"

# pacing only once 10% of that period's usage is spent
assert _render_footer([("wk", "9", "+12%", "3.2d")]) == "wk 9% 3.2d"
assert _render_footer([("wk", "10", "+12%", "3.2d")]) == "wk 10% (+12%) 3.2d"

# absent fields are omitted; empty input renders empty
assert _render_footer([("wk", "41", "", "")]) == "wk 41%"
assert _render_footer([]) == ""

# largest unit only: 4h49m -> 4.8h, 2d3h -> 2.1d, 18d23h -> 19d (whole day)
assert _compact_time(4 * 3600 + 49 * 60) == "4.8h"
assert _compact_time(2 * 86400 + 3 * 3600) == "2.1d"
assert _compact_time(18 * 86400 + 23 * 3600) == "19d"
assert _compact_time(int(4.95 * 3600)) == "5.0h"
assert _compact_time(45 * 60) == "45m"

# compact reset: past = 'now', missing/unparseable = omitted
assert _resets_in("2020-01-01T00:00:00Z") == "now"
assert _resets_in("") == "" and _resets_in("garbage") == ""

# matcher recognizes every emitted shape (model-echo dedup)
for row in [L0, L1, "Go: 5h 6% 3.2h", "Go: wk 7% 3.2d", "Go: mo 42% (-8%) 20.2d"]:
    assert _is_footer_line(row), row
assert not _is_footer_line("Just a reply.")
assert not _is_footer_line("Go buy milk")

# end-to-end: worst-case data emits the 3-line fallback and dedups its own echo
import __init__ as p
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
at = lambda **kw: (now + timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")
p._state = {"data": {"usage": {
    "rolling": {"percent": 100, "resetsAt": at(hours=4, minutes=59, seconds=59)},
    "weekly": {"percent": 100, "resetsAt": at(days=6, hours=23, minutes=30)},
    "monthly": {"percent": 100, "resetsAt": at(days=29, hours=23, minutes=30)},
}}, "fetched_at": 0.0}
p._fetch_usage = lambda: p._state.get("data")

out = p.transform_llm_output("Body text.", platform="telegram")
rows = out.split("\n\n", 1)[1].strip("*").split("\n")
assert len(rows) == 3, out
assert re.match(r"Go: 5h 100% \([+-]\d+%\) \d+\.\dh$", rows[0]), rows[0]
assert re.match(r"Go: wk 100% \([+-]\d+%\) \d+d$", rows[1]), rows[1]
assert re.match(r"Go: mo 100% \([+-]\d+%\) \d+d$", rows[2]), rows[2]
assert all(len(r) <= _BUDGET for r in rows), rows

# transforming the 3-line footer again strips every row, keeps body, one block
twice = p.transform_llm_output(out, platform="telegram")
assert twice.startswith("Body text."), twice
footers = [l for l in twice.split("\n") if p._is_footer_line(l)]
assert len(footers) == 3, twice  # one fresh block of 3, echoes gone

print("ALL RENDER CHECKS PASS")
