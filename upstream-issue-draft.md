# plugins enable: tool-override prompt fires for plugins that declare no capabilities

## Description

`hermes plugins enable <plugin>` prompts for the privileged `allow_tool_override` grant even when the plugin's `plugin.yaml` declares **no capabilities** — i.e. when there is nothing being granted and the plugin never requested `register_tool(..., override=True)`.

Observed with a minimal user plugin whose manifest declares only hooks:

```yaml
name: opencode-usage
description: Shows OpenCode Go subscription usage percentages as a footer on gateway messages
version: 0.1.0
hooks:
  - transform_llm_output
```

Interactive `hermes plugins enable opencode-usage` produced:

```
✓ Plugin opencode-usage enabled. Takes effect on next session.
Allow this plugin to replace built-in tools (e.g. shell_exec, write_file)?
  This is a privileged capability: an override can intercept everything the agent routes through that tool.
  Grant it? [y/N]
```

## Why this happens

`cmd_enable` (`hermes_cli/plugins_cmd.py`, `cmd_enable` around the "Capability consent flow" block) is written so that the declared-capabilities consent screen is the canonical path, with a comment saying the legacy prompt "then only runs on an explicit flag":

```python
declared_caps = _declared_capabilities_for_key(key)
if declared_caps:
    _run_capability_consent(...)
    if allow_tool_override is not None:
        _resolve_tool_override_grant(console, key, allow_tool_override)
    return
_resolve_tool_override_grant(console, key, allow_tool_override)
```

But the trailing line runs `_resolve_tool_override_grant` unconditionally on the empty-`declared_caps` branch, and `_resolve_tool_override_grant` asks the yes/no question whenever `allow_tool_override is None` ("tri-state: `None` asks"). So:

- manifest declares capabilities → capability consent screen (correct)
- manifest declares nothing → **legacy override prompt fires anyway with no cause** (this bug)

The docstring intends `None` (ask) for the tri-state, but that default only makes sense when a plugin actually seeks an override grant. A hook-only plugin has no route to `register_tool` at all, so the prompt is noise: it names capabilities the plugin cannot express.

## Expected behavior

- If the manifest declares **no capability ids**, `enable` should not prompt for tool override at all (silent no-grant, matching the fail-closed posture). The flag can still be granted later explicitly via `hermes plugins enable <name> --allow-tool-override` if the operator ever wants to pre-authorize it.
- Alternatively, skip the prompt when the plugin kind/hooks imply no tool registration path (e.g., manifests without `capabilities:` and without a `register_tool` surface), and only ask when either (a) capabilities are declared, or (b) the operator passes `--allow-tool-override` explicitly.

## Notes

- Answering "n" is safe and writes `plugins.entries.<id>.allow_tool_override: false`, which is inert for such plugins — so this is a UX-prompt-noise bug, not a security issue. But the prompt's wording ("Allow this plugin to…") implies the plugin asked for something, which is misleading and trains trust-eroding y/N reflexes on privilege prompts.
- The same unconditional default-ask likely affects any user plugin with no `capabilities:` block on `enable`.

## Environment

- Fork: Dev-Time/hermes-agent, commit at the `plugins_cmd.py` state containing the tri-state `_resolve_tool_override_grant` default (post-#64228 capability consent flow).
- Reproduce: create `~/.hermes/plugins/<any-name>/plugin.yaml` with only name/description/version/hooks (no `capabilities:`), then run `hermes plugins enable <any-name>`.
