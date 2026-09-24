"""OpenCode Go usage plugin — appends subscription usage percentages to the
final gateway message footer via transform_llm_output."""

import json
import logging
import os
import time
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_USAGE_BASE_URL = "https://opencode.ai/zen/go/v1"
_state = {"data": None, "fetched_at": 0.0}


def _usage_url():
    # Full base URL override; deliberately NOT derived from OPENCODE_GO_BASE_URL
    # (that runtime base loses its /v1 suffix — see OpenCodeGoProfile).
    base = (os.environ.get("OPENCODE_USAGE_BASE_URL") or "").strip() or DEFAULT_USAGE_BASE_URL
    return base.rstrip("/") + "/usage"


def _ttl():
    try:
        return max(1.0, float(os.environ.get("OPENCODE_USAGE_TTL_SECONDS")))
    except (TypeError, ValueError):
        return 120.0


def _api_key():
    for name in ("OPENCODE_GO_API_KEY", "OPENCODE_ZEN_API_KEY"):
        key = os.environ.get(name, "")
        if key:
            return key
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime = resolve_runtime_provider(requested="opencode-go")
        # Guard: rung 8 of the ladder always falls back to OpenRouter — never
        # send another provider's key to opencode.ai.
        if "opencode" in str(runtime.get("provider") or ""):
            return str(runtime.get("api_key") or "").strip()
    except Exception:
        pass
    return ""


def _fetch_usage():
    if _state["data"] and time.monotonic() - _state["fetched_at"] < _ttl():
        return _state["data"]
    key = _api_key()
    if not key:
        return None
    try:
        req = Request(_usage_url(), headers={"Authorization": f"Bearer {key}", "User-Agent": "hermes-agent/0.21 (opencode-usage-plugin)"})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        _state["data"] = data
        _state["fetched_at"] = time.monotonic()
        return data
    except Exception as exc:
        logger.debug("opencode-usage fetch failed: %s", exc)
        return None


def _resets_in(value) -> str:
    """Relative countdown from the window's own resetsAt field."""
    text = str(value or "").replace("Z", "+00:00").strip()
    try:
        from datetime import datetime, timezone as _tz
        reset = datetime.fromisoformat(text)
        if reset.tzinfo is None:
            reset = reset.replace(tzinfo=_tz.utc)
        seconds = int((reset - datetime.now(_tz.utc)).total_seconds())
    except ValueError:
        return ""
    if seconds <= 0:
        return "resets now"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or (not days and not hours):
        parts.append(f"{minutes}m")
    return "resets in " + " ".join(parts)


def _pacing(last_percent, resets_at, now=None, *, weekly=False):
    """Proportional pacing verdict: usage % vs expected % of window elapsed.

    Both boundaries come from the limit's own resetsAt: window END is the
    actual reset time, START = reset minus the period (7 days weekly;
    the previous same-length month, 28-31 days, monthly).  2026-09-23
    live sample: weekly resetsAt 2026-09-28T00:00Z, monthly
    2026-10-14T19:53Z.
    """
    if last_percent is None or last_percent == "—":
        return ""
    from datetime import datetime, timedelta, timezone

    if now is None:
        now = datetime.now(timezone.utc)
    text = str(resets_at or "").replace("Z", "+00:00").strip()
    try:
        reset = datetime.fromisoformat(text)
        if reset.tzinfo is None:
            reset = reset.replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    if weekly:
        start = reset - timedelta(days=7)
    else:
        start = reset - _one_month_like(reset)
    total = (reset - start).total_seconds()
    elapsed = (now - start).total_seconds()
    if total <= 0:
        return ""
    expected = max(0.0, min(1.0, elapsed / total)) * 100  # % of window elapsed
    usage = float(last_percent)
    delta = usage - expected
    tag = "AHEAD" if delta > 1.0 else ("UNDER" if delta < -1.0 else "on pace")
    pcts = f"{delta:+.0f}%"
    return f"pace {tag} {pcts}" if tag != "on pace" else "pace ok"


def _one_month_like(reset):
    """Span of the month preceding reset (28-31 days, calendar-correct)."""
    from datetime import datetime, timedelta

    y, m = reset.year, reset.month
    if m == 1:
        y, m = y - 1, 12
    else:
        m -= 1
    prev_m = reset.replace(y, m)
    length = (reset - prev_m).days  # handles 28-31 naturally
    return timedelta(days=length)


# Single source of truth for the footer wrapper: plain text, no emphasis markers.
_FOOTER_MD = "{line}"


def _is_footer_line(line: str) -> bool:
    """True for a usage-footer line, whatever emitted it (plugin or model echo).

    Matches both the plain and the enhanced format ("(resets in …)" / "[pace …]"
    suffixes) plus degenerate model echoes like ``_Go: ..._``.
    """
    s = line.strip().strip("_").strip("*").strip()
    if not s.startswith("Go:"):
        return False
    return " · " in s or s.endswith("...") or (s.startswith("Go: 5h ") and s.endswith("%"))


def _strip_footers(text: str) -> str:
    """Drop every usage-footer line (and the blank lines they leave behind)."""
    kept = []
    for ln in text.split("\n"):
        if _is_footer_line(ln):
            continue
        if ln.strip() == "" and (not kept or kept[-1].strip() == ""):
            continue
        kept.append(ln)
    return "\n".join(kept).rstrip()


def _usage_line():
    data = _fetch_usage()
    if not data:
        return ""
    windows = data.get("usage") or {}
    parts = []
    for label, key_name in (("Go: 5h", "rolling"), ("wk", "weekly"), ("mo", "monthly")):
        w = windows.get(key_name)
        if isinstance(w, dict) and w.get("percent") is not None:
            piece = f"{label} {w['percent']}%"
            reset_in = _resets_in(w.get("resetsAt"))
            if reset_in:
                piece += f" ({reset_in})"
            parts.append(piece)
            if key_name != "rolling":  # pacing only for weekly/monthly limits
                pace = _pacing(
                    w["percent"], w.get("resetsAt"), weekly=(key_name == "weekly")
                )
                if pace:
                    parts[-1] += f" [{pace}]"
    return " · ".join(parts)


def transform_llm_output(response_text, model=None, platform=None, session_id=None, **kwargs):
    try:
        # Only gateway-sourced turns (Telegram etc.) get the footer
        if not platform or platform == "cli":
            return None
        if not response_text or not response_text.strip():
            return None
        # The model echoes footer lines it sees in its own history: strip every
        # one, then append exactly one fresh footer.
        cleaned = _strip_footers(response_text)
        line = _usage_line()
        if line:
            if cleaned:
                return cleaned + "\n\n" + _FOOTER_MD.format(line=line)
            return _FOOTER_MD.format(line=line)
        # No usage data: only report a change when echo footers were actually removed.
        return cleaned if cleaned != response_text.strip() else None
    except Exception as exc:
        logger.debug("opencode-usage transform failed: %s", exc)
        return None


def register(ctx):
    ctx.register_hook("transform_llm_output", transform_llm_output)
