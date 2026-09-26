"""Duplicate-footer regression: transform output carries exactly ONE footer line."""
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

import __init__ as p

LIVE = {
    "usage": {
        "rolling": {"percent": 6, "resetsAt": "2026-09-24T08:01:11.150Z"},
        "weekly": {"percent": 7, "resetsAt": "2026-09-28T00:00:00.000Z"},
        "monthly": {"percent": 42, "resetsAt": "2026-10-14T19:53:39.000Z"},
    }
}

# Real strings harvested from state.db (model echoes + plugin output).
ECHO_IDENTICAL = "Body.\n\n_Go: 5h 6% · wk 7% · mo 42%_\n\n_Go: 5h 6% · wk 7% · mo 42%_"
ECHO_STALE = "Body.\n\n_Go: 5h 5% · wk 7% · mo 42%_\n\n_Go: 5h 6% · wk 7% · mo 43%_"
ECHO_DEGENERATE = "Body.\n\n_Go: 5h 101% · wk 101% · mo 101%_\n\n_Go: ..._\n\n_Go: 5h 6% · wk 7% · mo 42%_"
ECHO_BOLD = "Body.\n\n**_Go: 5h 6% · wk 7% · mo 42%_**"
CLEAN = "Just a reply."


def run(text, data=LIVE):
    p._state = {"data": data, "fetched_at": 0.0}
    p._fetch_usage = lambda: p._state.get("data")
    return p.transform_llm_output(text, model="m", platform="telegram", session_id="s")


def footers(text):
    return [ln for ln in text.split("\n") if p._is_footer_line(ln)]


def main():
    for name, sample in (("identical", ECHO_IDENTICAL), ("stale", ECHO_STALE),
                         ("degenerate", ECHO_DEGENERATE), ("bold", ECHO_BOLD),
                         ("clean", CLEAN)):
        out = run(sample)
        assert isinstance(out, str), f"{name}: returned {out!r}"
        assert len(footers(out)) == 1, f"{name}: {len(footers(out))} footers -> {out!r}"
        assert out.startswith(sample.split("\n")[0]), f"{name}: body lost -> {out!r}"
        print(f"{name}: 1 footer OK")

    # idempotent: transforming an already-transformed reply stays at one footer
    once = run(CLEAN)
    twice = run(once)
    assert len(footers(twice)) == 1, f"not idempotent -> {twice!r}"
    last = footers(twice)[0].strip()
    assert not last.startswith(("*", "_")) and not last.endswith(("*", "_")), twice
    print("idempotent: 1 footer OK")

    # transform never emits leading blank lines and stays a single footer
    out = run(ECHO_STALE)
    assert len(footers(out)) == 1 and not out.startswith("\n"), repr(out)
    print("leading-blank guard OK")

    # no usage data: model-fabricated footers are still removed
    out = run(ECHO_DEGENERATE, data=None)
    assert out == "Body.", f"expected cleaned body, got {out!r}"
    out = run(CLEAN, data=None)
    assert out is None, f"unchanged clean text should stay untouched, got {out!r}"
    print("no-data: echoes stripped, clean text untouched OK")

    # cli platform untouched
    assert p.transform_llm_output(ECHO_STALE, platform="cli") is None
    assert p.transform_llm_output(None, platform="telegram") is None
    print("platform/empty guards OK")

    # echoes the guard used to miss: mangled label, fractional %, backticks, **_…_**
    for echo in ("Body.\n\n6h 1% · wk 11% (-62%) 1.9d · mo 44% (+6%) 18.7d",
                 "Body.\n\n5h 9.5% · wk 11% · mo 44%",
                 "Body.\n\n`5h 0% · wk 11% · mo 44%`",
                 "Body.\n\n**_Go: 5h 6% · wk 7% · mo 42%_**"):
        out = run(echo)
        assert len(footers(out)) == 1 and echo.split("\n")[-1] not in out, repr(out)
    print("escaped echoes: stale footer stripped OK")

    print("ALL DEDUP CHECKS PASS")


if __name__ == "__main__":
    main()
