"""Pure renderer ladder: L0 single line -> L1 rolling-reset drop -> 3 lines
(FOOTER-SPEC §4/§5). Inputs are segment tuples, outputs exact strings."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _BUDGET, _is_footer_line, _render_footer, _resets_in  # noqa

NORMAL = [
    ("5h", "6", "", "3h14m"),
    ("wk", "7", "+12%", "3d5h"),
    ("mo", "42", "-8%", "20d4h"),
]
L0 = "5h 6% 3h14m · wk 7% +12% 3d5h · mo 42% -8% 20d4h"   # 48 visible
L1 = "5h 6% · wk 7% +12% 3d5h · mo 42% -8% 20d4h"         # 42 visible

# L0 fits the budget -> single line
out = _render_footer(NORMAL)
assert out == L0, out
assert len(out) == 48 <= _BUDGET

# L0 over budget -> L1 (rolling reset dropped, nothing else)
out = _render_footer(NORMAL, budget=47)
assert out == L1, out
assert len(out) == 42 <= 47

# L1 still over budget -> exactly 3 lines, every field kept
out = _render_footer(NORMAL, budget=41)
assert out == "Go: 5h 6% 3h14m\nGo: wk 7% +12% 3d5h\nGo: mo 42% -8% 20d4h", out
assert [len(r) for r in out.split("\n")] == [15, 19, 20]

# canonical escalation (§5): worst-case values -> L0 58, L1 52 > 50 -> 3 lines
assert len("5h 100% 4h59m · wk 100% +100% 6d23h · mo 100% +100% 29d23h") == 58
assert len("5h 100% · wk 100% +100% 6d23h · mo 100% +100% 29d23h") == 52
WORST = [
    ("5h", "100", "", "4h59m"),
    ("wk", "100", "+100%", "6d23h"),
    ("mo", "100", "+100%", "29d23h"),
]
out = _render_footer(WORST)
assert out == "Go: 5h 100% 4h59m\nGo: wk 100% +100% 6d23h\nGo: mo 100% +100% 29d23h", out
rows = out.split("\n")
assert [len(r) for r in rows] == [17, 23, 24]
assert all(len(r) <= _BUDGET for r in rows)

# L1 reachable: 4-char paces at maximal pct/resets -> L1 lands exactly on budget
MID = [
    ("5h", "100", "", "4h59m"),
    ("wk", "100", "+10%", "6d23h"),
    ("mo", "100", "-20%", "29d23h"),
]
out = _render_footer(MID)
assert out == "5h 100% · wk 100% +10% 6d23h · mo 100% -20% 29d23h", out
assert len(out) == 50 == _BUDGET

# absent fields are omitted; empty input renders empty
assert _render_footer([("wk", "41", "", "")]) == "wk 41%"
assert _render_footer([]) == ""

# compact reset: past = 'now', missing/unparseable = omitted
assert _resets_in("2020-01-01T00:00:00Z") == "now"
assert _resets_in("") == "" and _resets_in("garbage") == ""

# matcher recognizes every emitted shape (model-echo dedup)
for row in [L0, L1, "Go: 5h 6% 3h14m", "Go: wk 7% +12% 3d5h", "Go: mo 42% -8% 20d4h"]:
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
assert rows[0] == "Go: 5h 100% 4h59m", rows[0]
assert re.match(r"Go: wk 100% [+-]\d+% \d+d\d+h$", rows[1]), rows[1]
assert re.match(r"Go: mo 100% [+-]\d+% \d+d\d+h$", rows[2]), rows[2]
assert all(len(r) <= _BUDGET for r in rows), rows

# transforming the 3-line footer again strips every row, keeps body, one block
twice = p.transform_llm_output(out, platform="telegram")
assert twice.startswith("Body text."), twice
footers = [l for l in twice.split("\n") if p._is_footer_line(l)]
assert len(footers) == 3, twice  # one fresh block of 3, echoes gone

print("ALL RENDER CHECKS PASS")
