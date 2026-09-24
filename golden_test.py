"""Footer format determinism — golden snapshot test (no network).

Goal: rendered footer byte-identical across consecutive runs unless the
underlying usage content actually changed. The italic wrapper template lives
in exactly one place (_footer) and is unconditional — no per-run conditional
italics, no alternate em-dash/asterisk variant.
"""
import os
import sys
from datetime import datetime, timezone

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

FROZEN = datetime(2026, 9, 24, 3, 30, 0, tzinfo=timezone.utc)

LIVE_SHAPE = {
    "usage": {
        "rolling": {"percent": 1, "resetsAt": "2026-09-24T08:01:11.150Z"},
        "weekly": {"percent": 5, "resetsAt": "2026-09-28T00:00:00.000Z"},
        "monthly": {"percent": 41, "resetsAt": "2026-10-14T19:53:39.000Z"},
    }
}

def run(plugin, data):
    plugin._state = {"data": data, "fetched_at": 0.0}
    plugin._fetch_usage = lambda: plugin._state.get("data")
    return plugin.transform_llm_output("Body text.", model="m", platform="telegram", session_id="s")

def golden():
    import __init__ as p
    out = run(p, LIVE_SHAPE)
    out2 = run(p, LIVE_SHAPE)
    assert isinstance(out, str) and out == out2, "consecutive runs differ!"
    assert out.encode() == out2.encode(), "not byte-identical"
    return out

def content_differs():
    import __init__ as p
    a = run(p, LIVE_SHAPE)
    changed = {"usage": {k: dict(v) for k, v in LIVE_SHAPE["usage"].items()}}
    changed["usage"]["monthly"]["percent"] = 42
    b = run(p, changed)
    assert a != b, "content change should change footer"
    return True

def wrapper_invariant():
    """The SOURCE carries exactly one footer template — any conditional wrapper
    or second italic/em-dash variant is a structural regression."""
    src = open(PLUGIN_DIR + "/__init__.py").read()
    assert src.count('_FOOTER_MD = "*{line}*"') == 1, "footer wrapper must be a single template constant"
    assert src.count("_FOOTER_MD.format(") == 2, "both emit sites must render the one template"
    assert "_{line}_" not in src, "raw underscore wrapper reintroduced"
    assert "*_{line}" not in src and "_{line}*" not in src, "mixed asterisk/underscore variant"
    return True

def asterisk_wrapper():
    """Output is wrapped in standard-markdown `*...*` so Telegram's format_message
    converts it to a parse-safe, italic MarkdownV2 `_..._`."""
    g = golden()
    assert g.endswith("*") and g.rindex("*") > g.rindex("\n"), f"footer must brace with *: {g!r}"
    inner = g.rsplit("\n\n", 1)[1]
    assert inner.startswith("*") and inner.endswith("*"), inner
    assert not inner.startswith("_") and not inner.endswith("_"), f"underscore wrapper leaked: {inner!r}"
    return True

if __name__ == "__main__":
    g = golden()
    print("GOLDEN:", g)
    assert g.rindex("*") > g.rindex("\n"), "wrapper braces the footer line"
    assert content_differs()
    assert wrapper_invariant()
    assert asterisk_wrapper()
    print("ALL GOLDEN CHECKS PASS")
