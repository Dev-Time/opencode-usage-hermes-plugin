# opencode-usage — Hermes plugin

Shows your OpenCode Go subscription usage as an italic footer on every gateway
message (Telegram, Discord, Slack, …):

> …reply text…
>
> _Go: 5h 8% (resets in 4h) · wk 8% (resets in 3d 19h) [pace UNDER -37%] · mo 42% (resets in 20d 15h) [pace AHEAD +11%]_

- **5h / wk / mo** — rolling 5-hour, weekly and monthly limit windows
- **resets in …** — countdown to that window's own reset time
- **[pace …]** — are you ahead or under quota vs. the proportion of the window
  already elapsed (weekly/monthly only)

CLI/desktop sessions are intentionally left untouched; the footer is a
gateway-message feature.

## Requirements

- Hermes with plugin install support (tested against Hermes 0.21.4)
- An OpenCode Go subscription and API key: https://opencode.ai/zen

## Install

```bash
hermes plugins install Dev-Time/opencode-usage-hermes-plugin
```

The installer:

1. clones the repo and security-scans it,
2. prompts once for `OPENCODE_GO_API_KEY` (masked; skipped if already set in
   `~/.hermes/.env`) and saves it to `~/.hermes/.env` — **your key never
   enters the repo**,
3. shows the post-install notes,
4. asks `Enable now? [y/N]` — answer `y`, then restart Hermes (or
   `/restart` in the gateway).

If Hermes asks a confusing tool-override question during enable, answer
**`n`** — this plugin needs no tool overrides (known upstream prompt bug,
see `upstream-issue-draft.md`).

## Configuration

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `OPENCODE_GO_API_KEY` | yes | — | OpenCode Go API key. `OPENCODE_ZEN_API_KEY` works as a fallback. |
| `OPENCODE_USAGE_BASE_URL` | no | `https://opencode.ai/zen/go/v1` | Usage endpoint base; the plugin appends `/usage`. Deliberately **not** derived from `OPENCODE_GO_BASE_URL` (that runtime base loses its `/v1` suffix). |
| `OPENCODE_USAGE_TTL_SECONDS` | no | `120` | Cache lifetime for the usage payload. |

Nothing else is user-set: plan tier, limits and reset times come from the
`/usage` response itself (server-side), and there are no Wyatt-specific or
machine-specific paths in the plugin.

On/off is the standard plugin switch — no config key:

```bash
hermes plugins disable opencode-usage    # footer off
hermes plugins enable  opencode-usage    # footer on
```

## What if I don't see a footer?

- Not a gateway turn — CLI/desktop sessions are skipped by design.
- Key missing or invalid: run `python3 ~/.hermes/plugins/opencode-usage/live_check.py`
  (prints `key present: …` and a live payload, or `(no data)`).
- Cached: changes appear after the TTL (default 2 minutes).
- Plugin disabled: `hermes plugins list`.

For detailed windows/resets, the built-in `/usage` slash command and the
desktop status-bar catalog plugins (`provider-usage`,
`ai-usage-tracker`) already cover richer UI. This plugin's niche is the
automatic footer on gateway messages.

## Uninstall

```bash
hermes plugins remove opencode-usage
```

## Development

Layout: `__init__.py` (plugin code), `plugin.yaml` (manifest),
`after-install.md` (shown by the installer), `DESIGN.md` (design record),
tests (`test_*.py`, `golden_test.py` — all offline except `live_check.py`).

```bash
python3 test_pacing.py        # pacing seeds
python3 test_integration.py   # footer shape from mocked payload
python3 test_dedup.py         # exactly one footer, idempotent
python3 golden_test.py        # byte-identical consecutive renders
python3 live_check.py         # live API check (needs key in env)
```

`test_real_sample.py` needs a private fixture (`obligation_dump.txt`, not
shipped) and skips when absent.

Secrets: put keys in `~/.hermes/.env` only — never commit them. The manifest
(`requires_env`, `secret: true`) makes the installer prompt and store the key
for you.

## License

MIT — see `LICENSE`.
