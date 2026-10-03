"""llm_request middleware: footers stripped from assistant history rows only."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import __init__ as p

FOOTER_A = "Go: 5h 42% (+11%) 2.6h"
FOOTER_B = "Go: wk 7% 1.3d"


def mw(**kwargs):
    return p.strip_footers_from_request(**kwargs)


# assistant str content: footer row removed, body kept
out = mw(request={"messages": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": f"answer\n\n{FOOTER_A}"},
    {"role": "user", "content": "next"},
]})
assert out is not None and out["source"] == "opencode-usage" and out["reason"]
assert out["request"]["messages"][1]["content"] == "answer", out["request"]["messages"][1]
assert out["request"]["messages"][0] == {"role": "user", "content": "hi"}
assert out["request"]["messages"][2] == {"role": "user", "content": "next"}
print("assistant str strip OK")

# multi-line (3-line fallback shape): all footer rows dropped
out = mw(request={"messages": [
    {"role": "assistant", "content": f"body\n{FOOTER_A}\n{FOOTER_B}\nmo 49% 11.1d"},
]})
assert out["request"]["messages"][0]["content"] == "body", out["request"]["messages"][0]
print("multi-row strip OK")

# user/tool rows are never touched even if they contain a footer-shaped line
rows = [
    {"role": "user", "content": FOOTER_A},
    {"role": "tool", "tool_call_id": "c1", "content": FOOTER_A},
    {"role": "system", "content": FOOTER_A},
]
assert mw(request={"messages": rows}) is None
print("non-assistant rows untouched OK")

# clean assistant text with double blank lines: NO change (footer gate, no trace noise)
clean = {"role": "assistant", "content": "para one\n\n\npara two"}
assert mw(request={"messages": [clean]}) is None
print("clean rows byte-identical OK")

# None / non-str / empty content: skipped
assert mw(request={"messages": [{"role": "assistant", "content": None}]}) is None
assert mw(request={"messages": [{"role": "assistant", "content": 42}]}) is None
assert mw(request={"messages": [{"role": "assistant"}]}) is None
assert mw(request={"messages": []}) is None
assert mw(request={}) is None
assert mw(request="not-a-dict") is None
assert mw() is None
print("degenerate inputs OK")

# list content (multimodal text parts): footer-bearing part cleaned, others byte-identical
parts = [
    {"type": "text", "text": "lead"},
    {"type": "text", "text": f"tail\n\n{FOOTER_A}"},
    {"type": "image_url", "image_url": {"url": "x"}},
]
out = mw(request={"messages": [{"role": "assistant", "content": parts}]})
got = out["request"]["messages"][0]["content"]
assert got[0] == parts[0] and got[2] == parts[2]
assert got[1]["text"] == "tail", got[1]
print("list-content text parts OK")

# Responses API: input items with assistant role
out = mw(request={"input": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": f"ok\n\n{FOOTER_A}"},
]})
assert out["request"]["input"][1]["content"] == "ok"
assert out["request"]["input"][0] == {"role": "user", "content": "hi"}
print("responses-api input OK")

# immutability: caller's request is never mutated; no-change returns None (no trace entry)
original = {"messages": [{"role": "assistant", "content": f"answer\n\n{FOOTER_A}"}]}
snapshot = copy.deepcopy(original)
out = mw(request=original)
assert original == snapshot, "input request was mutated"
assert out["request"] is not original and out["request"]["messages"] is not original["messages"]
assert mw(request={"messages": [{"role": "assistant", "content": "clean"}]}) is None
print("immutability + no-change None OK")

# strip_footers_from_request is deterministic: second pass over its own output = no change
first = out["request"]
assert mw(request=first) is None
print("idempotent OK")

# register() wires both surfaces
class _Ctx:
    def __init__(self):
        self.hooks, self.middleware = [], []
    def register_hook(self, name, cb):
        self.hooks.append((name, cb))
    def register_middleware(self, kind, cb):
        self.middleware.append((kind, cb))

ctx = _Ctx()
p.register(ctx)
assert ctx.hooks == [("transform_llm_output", p.transform_llm_output)]
assert ctx.middleware == [("llm_request", p.strip_footers_from_request)]
print("register() wiring OK")

print("ALL MIDDLEWARE CHECKS PASS")
