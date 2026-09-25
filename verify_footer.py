"""Independent verification of footer formatting vs spec (kanban t_51702a15).

Runs the spec's own checklist against the shipped renderer; prints PASS/FAIL per
case and a final mismatch table (expected vs actual).
"""
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import __init__ as p

FAILS = []


def check(name, actual, expected):
    ok = actual == expected
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"\n        expected: {expected!r}\n        actual:   {actual!r}"))
    if not ok:
        FAILS.append((name, expected, actual))


SPEC_EXAMPLE = "5h 0% 4.8h · wk 11% (-58%) 2.1d · mo 44% (+7%) 19d"

print("== 1. spec example, byte-exact ==")
check("render_footer segments", p._render_footer([
    ("5h", "0", "", "4.8h"), ("wk", "11", "-58%", "2.1d"), ("mo", "44", "+7%", "19d")]),
    SPEC_EXAMPLE)
check("length <= budget", len(SPEC_EXAMPLE) <= p._BUDGET, True)

# end-to-end through _usage_line: craft resetsAt so pacing + compact reset both
# land on the spec numbers (rolling 4.8h, weekly 2.1d/-58%, monthly 19d/+7%).
now = datetime.now(timezone.utc)
iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
p._fetch_usage = lambda: {"usage": {
    "rolling": {"percent": 0, "resetsAt": iso(now + timedelta(hours=4, minutes=48))},
    "weekly": {"percent": 11, "resetsAt": iso(now + timedelta(days=2, hours=3, minutes=21, seconds=36))},
    "monthly": {"percent": 44, "resetsAt": iso(now + timedelta(days=19))},
}}
check("_usage_line end-to-end", p._usage_line(), SPEC_EXAMPLE)

print("== 2. usage just below 10%: pacing hidden, pct + reset still shown ==")
check("9%", p._render_footer([("wk", "9", "+12%", "3.2d")]), "wk 9% 3.2d")
check("9.9%", p._render_footer([("wk", "9.9", "+12%", "3.2d")]), "wk 9.9% 3.2d")
check("5h at 9%", p._render_footer([("5h", "9", "-40%", "1.2h")]), "5h 9% 1.2h")

print("== 3. usage at/above 10%: pacing parenthesized, all periods ==")
check("10%", p._render_footer([("wk", "10", "+12%", "3.2d")]), "wk 10% (+12%) 3.2d")
check("5h at 11%", p._render_footer([("5h", "11", "-40%", "1.2h")]), "5h 11% (-40%) 1.2h")
check("5h at 100%", p._render_footer([("5h", "100", "+60%", "5.0h")]), "5h 100% (+60%) 5.0h")
check("mo at 44%", p._render_footer([("mo", "44", "+7%", "19d")]), "mo 44% (+7%) 19d")

print("== 4. edge values ==")
check("0% usage, no pacing", p._render_footer([("5h", "0", "-90%", "4.8h")]), "5h 0% 4.8h")
check("exactly 10% shows pacing", p._paced("10"), True)
check("just under 10% hides pacing", p._paced("9.99"), False)
check("4.95h -> 5.0h", p._compact_time(int(4.95 * 3600)), "5.0h")
check("4h49m -> 4.8h", p._compact_time(4 * 3600 + 49 * 60), "4.8h")
check("18d23h -> 19d", p._compact_time(18 * 86400 + 23 * 3600), "19d")
check("2d3h -> 2.1d", p._compact_time(2 * 86400 + 3 * 3600), "2.1d")
check("45m stays minutes", p._compact_time(45 * 60), "45m")
check("60m -> 1.0h", p._compact_time(60 * 60), "1.0h")
check("negative pacing renders", p._render_footer([("wk", "11", "-58%", "2.1d")]), "wk 11% (-58%) 2.1d")
# zero delta: usage exactly equals expected % of window elapsed -> '+0%', never '-0%'
reset4 = now + timedelta(days=4)
check("zero delta never -0%",
      p._pacing(0, iso(reset4), now=reset4 - timedelta(days=7), span=timedelta(days=7)), "+0%")
neg0 = [p._pacing(u, iso(reset4), now=reset4 - timedelta(days=7), span=timedelta(days=7))
        for u in range(0, 100)]
check("no '-0%' anywhere in pacing sweep", [v for v in neg0 if v == "-0%"], [])
check("period with no data omitted", p._render_footer([("5h", "0", "", "4.8h"), ("wk", "41", "", "")]),
      "5h 0% 4.8h · wk 41%")
p._fetch_usage = lambda: {"usage": {"weekly": {"percent": None, "resetsAt": "2026-09-28T00:00:00Z"}}}
check("percent None -> period omitted (no data)", p._usage_line(), "")
p._fetch_usage = lambda: {"usage": {"weekly": {"percent": 41}}}
check("no resetsAt -> no reset, no pace", p._usage_line(), "wk 41%")
p._fetch_usage = lambda: {"usage": {}}
check("empty usage -> empty footer", p._usage_line(), "")
check("past reset -> now", p._resets_in("2020-01-01T00:00:00Z"), "now")

print("== 5. only one time unit ever ==")
UNIT = re.compile(r"^(?:\d+m|\d+h|\d+\.\dh|\d+d|\d+\.\dd|now)$")
COMPOUND = re.compile(r"\d[dhm]\d")
bad = []
s = 1
while s <= 40 * 86400:
    out = p._compact_time(s)
    if not UNIT.match(out) or COMPOUND.search(out):
        bad.append((s, out))
    s += 47
check(f"sweep 40d in 47s steps: no compound/odd forms", bad[:5], [])

rnd = random.Random(5170215)
lines = []
for _ in range(400):
    segs = []
    for label in ("5h", "wk", "mo"):
        pct = rnd.choice([0, 5, 9, 9.9, 10, 11, 44, 75, 100])
        reset = p._compact_time(rnd.randint(1, 40 * 86400))
        pace = rnd.choice(["", "+0%", "-58%", "+7%", "+100%", "-20%"])
        segs.append((label, str(pct), pace, reset))
    lines.append(p._render_footer(segs))
# token-level: every whitespace token (parens stripped) is a unit value, label,
# percent, pace, separator, or the 3-line row prefix.
TOKEN = re.compile(r"^(?:Go:|5h|wk|mo|[+-]?\d+(?:\.\d+)?%|\d+(?:\.\d+)?[dhm]|·)$")
comp = [l for l in lines
        if COMPOUND.search(l)
        or any(not TOKEN.match(t.strip("()")) for t in l.split() if t.strip("()"))]
check("400 random footers: no compound units", comp[:3], [])
check("worst-case within budget or 3-line fallback",
      all(len(l) <= p._BUDGET or len(l.split("\n")) == 3 for l in lines), True)

print()
if FAILS:
    print(f"MISMATCHES: {len(FAILS)}")
    for name, exp, act in FAILS:
        print(f"  - {name}: expected {exp!r}, actual {act!r}")
    sys.exit(1)
print("ALL SPEC CHECKS PASS")
