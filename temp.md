## Summary

- `bot.send_message`/`edit_message` (the REST path) serialised Components v2 blocks (`Container`, `TextDisplay`, etc.) but never set the `IS_COMPONENTS_V2` message flag (`1 << 15`), so Discord rejected the payload with a 400 (`UNION_TYPE_CHOICES`), parsing it as legacy-components instead.
- Interaction responses (`ctx.send`/`ctx.edit`) and `execute_webhook` already auto-detected this via `_contains_uikit` and set the flag correctly — only the two REST helpers in `app.py` were missing it.
- Fix: reuse `context._contains_uikit`/`_FLAG_UI_KIT` in `send_message`/`edit_message`, same as the other two paths.

## Test plan

- [x] `pytest` — 289 passed
- [x] New tests: flag set when components contain a uikit block, flag omitted otherwise, both for `send_message` and `edit_message`
- [x] `ruff check` — clean
- [x] Manually reproduced the reported payload (`Container`/`TextDisplay` via `send_message`) and confirmed `flags: 32768` is now present
