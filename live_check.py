import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _usage_line

key = os.environ.get("OPENCODE_GO_API_KEY") or os.environ.get("OPENCODE_ZEN_API_KEY")
print("key present:", bool(key))
print("LIVE:", _usage_line() or "(no data)")
