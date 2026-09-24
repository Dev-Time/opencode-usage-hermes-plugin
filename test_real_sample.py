"""Heavy check: the real 1143-footer Telegram message collapses to exactly one footer."""
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)
import __init__ as p

LIVE = {"usage": {
    "rolling": {"percent": 6, "resetsAt": "2026-09-24T08:01:11.150Z"},
    "weekly": {"percent": 7, "resetsAt": "2026-09-28T00:00:00.000Z"},
    "monthly": {"percent": 42, "resetsAt": "2026-10-14T19:53:39.000Z"},
}}
p._state = {"data": LIVE, "fetched_at": 0.0}
p._fetch_usage = lambda: p._state.get("data")

if not os.path.exists(PLUGIN_DIR + "/obligation_dump.txt"):
    print("SKIP: obligation_dump.txt (private fixture, not shipped) absent")
    sys.exit(0)
real = open(PLUGIN_DIR + "/obligation_dump.txt").read()
before = len([l for l in real.split("\n") if p._is_footer_line(l)])
out = p.transform_llm_output(real, model="m", platform="telegram", session_id="s")
after = len([l for l in out.split("\n") if p._is_footer_line(l)])
print("real message footers: before=%d after=%d" % (before, after))
assert before > 1000, before
assert after == 1, after
last = [l for l in out.split("\n") if p._is_footer_line(l)][0]
assert "5h 6%" in last and "wk 7%" in last and "mo 42%" in last, last
print("REAL 1143-FOOTER MESSAGE -> exactly 1 footer: OK")
