# opencode-usage installed

1. Restart Hermes (or `/restart` in the gateway) so the plugin loads.
2. Send a message from a gateway platform (Telegram/Discord/…) — you should
   see the italic footer `Go: … · wk … · mo …` appended to the reply.
3. No footer? Check your key: `python3 ~/.hermes/plugins/opencode-usage/live_check.py`

Turn it off anytime: `hermes plugins disable opencode-usage`

Full docs: README.md in the plugin repo
(`Dev-Time/opencode-usage-hermes-plugin`).
