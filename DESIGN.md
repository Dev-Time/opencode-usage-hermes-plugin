# DESIGN — Making opencode-usage shareable

Status: approved by Wyatt 2026-09-24 (dashboard comment on t_2ba13682); repo
setup implemented same day. Implementation notes at the end of this doc.

## Goal

Another Hermes user running an OpenCode Go subscription installs this plugin and
gets the same footer (Go 5h / wk / mo percentages on gateway messages, e.g. Telegram)
that Wyatt gets today, without touching any Wyatt-specific paths or secrets.

## Current state (facts verified against Hermes 0.21.4 source)

- Plugin lives at `/hermes/plugins/opencode-usage/{__init__.py,plugin.yaml}`; working
  copy at `/workspace/opencode-usage-plugin` (identical files). Not a git repo yet.
- `plugin.yaml` declares hooks `transform_llm_output` + `post_llm_call`, but
  `register(ctx)` only registers `transform_llm_output`. `post_llm_call` is dead
  declaration — either drop it from the manifest or register a refresher.
- Hardcoded in code:
  - `USAGE_URL = "https://opencode.ai/zen/go/v1/usage"` — literal; ignores
    `OPENCODE_GO_BASE_URL` (core supports that override env var).
  - Cache TTL 120s (module-level `_state`, single-process cache).
  - Footer formatting (`Go: 5h · wk · mo` labels), gateway-only filter
    (`platform == "cli"` skipped), markdown italic wrapper.
- API key: already the *standard* OpenCode Go provider env var
  (`OPENCODE_GO_API_KEY`, fallback `OPENCODE_ZEN_API_KEY`). On real installs
  `hermes auth` / `.env` already sets it — no new secret format needed.
- Core overlap (important!): upstream already ships
  `OpenCodeGoProfile.fetch_account_usage()` (`/usage` → `AccountUsageSnapshot`,
  surfaced by the built-in `/usage` slash command and the desktop status-bar
  plugins). This plugin's unique value is the **automatic footer on gateway
  messages**, not the usage fetch itself. Design should re-use the provider
  profile resolver (`hermes_cli.runtime_provider.resolve_runtime_provider`) so key
  resolution, base-url override and rotation match core behavior.
- Payload is relative (percent + resetsAt per window), **no tier/pacing constants
  in the plugin** — OpenCode Go tier limits are server-side. Nothing to
  externalize there.

## Distribution path (recommendation)

Hermes has no marketplace/registry beyond git installs + a curated catalog:

1. **Primary (this task): standalone GitHub repo.**
   `hermes plugins install <owner>/opencode-usage-hermes-plugin`
   works today out of the box — the installer accepts `owner/repo` shorthand,
   clones, prompts for `requires_env` (masked, saved to `~/.hermes/.env`), and we
   pin nothing (repo = "[yellow] custom (unreviewed) source" warning, fine for v1).
   Also `hermes plugins update` works via git pull.
2. **Follow-up (separate task, optional): catalog submission.** One YAML in the
   upstream `plugin-catalog/` via PR — owner-submitted, 40-hex SHA pin, declared
   capabilities must match exactly, no self-updater. Requires the repo to be
   public and stable first. Item for later discovery, not part of v1.

No HACS-style packaging needed: a repo with `plugin.yaml` + `__init__.py` at any
depth (or a `#subdir`) suffices. Formatting/lint per Hermes plugin norms is bookkeeping.

## Config surface (plugin.yaml `requires_env` + optional plugin yaml config)

Must be user-set (masked prompt at install):
- `OPENCODE_GO_API_KEY` — secret:true, url: opencode.ai key page. Users who set it
  for the provider already have it; the installer only prompts when unset in `.env`.

Auto-detected / sane defaults (no user action):
- Base URL: default `https://opencode.ai/zen/go/v1/usage`; overridable via
  `OPENCODE_USAGE_BASE_URL` (plugin-level, falls back through
  `OPENCODE_GO_BASE_URL`-style derivation so multi-env setups work).
- Refresh TTL: constant 120s, overridable `OPENCODE_USAGE_TTL_SECONDS`.
- Footer on/off: implicit — only via `hermes plugins disable opencode-usage`.
- Plan tier: **not needed** — API returns per-account percents directly.

Optional polish (only if trivial): `OPENCODE_USAGE_SKIP_PLATFORMS=cli,desktop`
comma-list replacing the hardcoded `platform == "cli"` skip. Single knob,
one-line parse. Skip unless trivially testable.

## Secrets handling (per user)

- API key NEVER in the repo. Repo contains only `plugin.yaml` declaring
  `requires_env: [{name: OPENCODE_GO_API_KEY, secret: true, description: ..., url: ...}]`.
- With `requires_env` declared, `hermes plugins install` masks the input and
  `save_env_value()` writes it into `~/.hermes/.env` (0600). Verify no other
  secret-ish content ships (no tokens in comments, no `.env*` in the repo; add
  `SECURITY-SCAN.md` / disclosure note per catalog norm).
- This session's own key already lives in `/hermes/.env` and is untouched.

## Repo shape (proposed, after approval)

```
opencode-usage/
├── __init__.py        # current code, plus: resolve_runtime_provider for key/url,
│                      # TTLC/env override, drop dead post_llm_call or wire refresher
├── plugin.yaml        # + requires_env block, capabilities declared honestly
├── README.md          # user-facing: what it does (footer screenshot), install,
│                      # config, uninstall, troubleshooting, /usage relationship
├── DESIGN.md          # this doc (repo-internal design record)
├── after-install.md   # 2-line post-install hint (shows during install)
└── LICENSE            # MIT
```

Rename of the repo directory is cosmetic; the installer deduces name from
`plugin.yaml` ("opencode-usage"), so the GitHub repo can be
`opencode-usage-hermes-plugin` while the plugin install name stays `opencode-usage`.

## Per-user setup walkthrough (target acceptance)

1. `hermes plugins install <owner>/opencode-usage-hermes-plugin`
   → clones, security-scans, prompts once for `OPENCODE_GO_API_KEY` (or skips if
   already set in ~/.hermes/.env), offers "Enable now? [y/N]".
2. Restart Hermes (or let the activate-now hook note what requires restart).
3. Any gateway message (Telegram/discord/etc.) — see footer, e.g.
   `Go: 5h 42% · wk 18% · mo 7%`. CLI/local sessions show nothing (by design).
4. `hermes plugins disable opencode-usage` turns the footer off; `/usage` slash
   command covers detailed windows/resets regardless.

## Risks / open questions

- `transform_llm_output` hook availability depends on platform; nothing to do.
- Known upstream UX bug (see `upstream-issue-draft.md`): enabling a hookless
  capability-set plugin still asks the confusing tool-override prompt. Known,
  separate PR; users answer "n" safely until fixed.
- If Wyatt wants desktop status-bar/display, note existing catalog entries
  (`provider-usage`, `ai-usage-tracker`) already do richer UI — our plugin is the
  gateway-message-footer niche; worth stating in README to avoid feature duplication.
- Credits/attribution: headers already send Hermes-standard
  HTTP-Referer/X-Title; keep.

## Explicitly out of scope for v1

- Catalog submission PR (follow-up card).
- Any change to core `/usage` or desktop UI.
- Multi-profile / multiple OpenCode accounts simultaneously.

## Implementation notes (2026-09-24, post-approval)

- `plugin.yaml`: dead `post_llm_call` declaration dropped (register() never
  hooked it); added `requires_env` dict entry for `OPENCODE_GO_API_KEY`
  (secret: true, url hint) + author/license; version 0.2.0.
- Base URL override `OPENCODE_USAGE_BASE_URL` holds the BASE (plugin appends
  `/usage`). Deliberately NOT derived from `OPENCODE_GO_BASE_URL`: core's
  OpenCodeGoProfile documents that the runtime base loses its `/v1` suffix and
  `/usage` only exists under `/v1` — deriving would build a broken endpoint.
- Key resolution: env first (`OPENCODE_GO_API_KEY`, then
  `OPENCODE_ZEN_API_KEY`), `resolve_runtime_provider(requested="opencode-go")`
  as fallback — guarded so only an opencode* runtime's key is accepted
  (ladder rung 8 always falls back to OpenRouter; that key must never be sent
  to opencode.ai).
- `_fetch_usage` checks the cache BEFORE resolving the key, so the resolver
  runs at most once per TTL instead of once per message.
- TTL override `OPENCODE_USAGE_TTL_SECONDS` (min 1.0s, default 120).
- Tests externalized: hardcoded `/workspace/opencode-usage-plugin` sys.path
  entries replaced with `__file__`-relative paths; `test_real_sample.py`
  skips cleanly when its private fixture (`obligation_dump.txt`, gitignored)
  is absent.
- Repo = this directory as a git repo, published as GitHub
  `Dev-Time/opencode-usage-hermes-plugin` (public, install via
  `hermes plugins install Dev-Time/opencode-usage-hermes-plugin`).
