# cordless Roadmap

cordless is under active development by a single maintainer, so treat this as
a living list of direction, not a set of dates. Feedback and PRs welcome via
[issues](https://github.com/borhara/cordless/issues).

## Shipped

The current feature surface, for orientation:

- Slash commands with typed options, `parent/sub` and `parent/group/sub`
  subcommand paths, autocomplete, and user/message context-menu commands
- Buttons, selects, and modals, each optionally deferrable
- Components v2
- Cogs/extensions (`load_extension` / `load_extensions`) for splitting a bot
  across files
- Cron-scheduled handlers (`@bot.cron`, `cordless cron`)
- User-installable apps (`user_installable=True`): commands that run in any
  DM or server via user install, not just guild-installed bots
- `cordless.testing`: `invoke(bot, "command")` plus `command()`, `button()`,
  `select()`, `modal()`, and `autocomplete()` interaction builders dispatch
  fake interactions through a bot's real router, so handlers are
  unit-testable without a live Discord round-trip
- Command name/description localization (Discord's per-locale i18n) via
  `name_localizations`/`description_localizations` on `@bot.command`,
  `user_command`, and `message_command`
- `cordless doctor`: diagnose AWS credentials, IAM role, Discord app config,
  and deployed function state, and point at what's wrong
- Deferred interactions handed off to a worker Lambda, so slow commands never
  hit Discord's 3-second limit
- File uploads / multipart attachments
- `cordless dev`: local hot-reload server with an optional cloudflared
  public tunnel
- `cordless deploy`: Function URL or API Gateway (custom domain), IAM role,
  command registration, all in one command; `cordless destroy` to tear down
- Environment-specific config (`--environment`/`--env`, overlay `.env` files)
- Optional cross-invocation rate-limit coordination via DynamoDB
- `cordless logs`: CloudWatch log tailing for the main or worker function
- **Full Discord REST API coverage.** A complete typed client, mirrored
  across three layers (flat `_rest/<resource>.py` functions, `bot.<verb>()`
  mixin methods, and object-method sugar like `guild.create_channel()` /
  `message.reply()`, all calling the same underlying request logic):
  channels, threads, guild management, members and roles, messages,
  reactions and polls, invites and webhooks (including token-authenticated
  webhook execution), emoji and stickers, guild scheduled events,
  auto-moderation, stage instances, guild templates, audit log, users,
  voice, soundboard, entitlements/SKUs, and application command management.
  Endpoints that only work with an OAuth2 Bearer user token, not the bot
  token cordless uses everywhere else, are intentionally excluded.


## In progress
N/A


## Planned next
N/A


## Under consideration

- A lightweight gateway bridge for the handful of things interactions can't
  cover (message-content events, member-join, presence). Most likely a small,
  explicitly opt-in, always-on companion process that forwards selected
  gateway events into your Lambda via EventBridge/SQS, kept separate so the
  zero-idle-cost default for everyone else doesn't change.
- Alternate deploy targets beyond AWS Lambda (Cloudflare Workers, Google
  Cloud Functions) behind the same `cordless deploy` interface.
- Terraform/CDK export, for teams who want the resources cordless provisions
  to live in their own IaC instead of being managed imperatively by the CLI.
- Starter templates (`cordless init --template moderation`, `--template
  economy`, ...).
- `bot.route(method, path)`: register raw HTTP routes on the same Lambda,
  outside the Discord interaction flow, with the handler getting the raw
  event and the `bot` instance (so it can reuse `send_message`,
  `execute_webhook`, etc.). For anything that needs to land on the same
  function without going through Discord signature verification: third-party
  webhooks (Stripe, GitHub, ...), OAuth redirect callbacks, health checks.
  Only viable under `endpoint = "api_gateway"`, since Function URLs are
  single-path; `deploy` would need to diff/sync these routes the same way it
  already diffs/syncs Discord commands, rather than requiring a hand-rolled
  boto3 script like today.

## Non-goals (for now)

- **Voice/music bots.** Discord voice needs a persistent gateway connection
  and an audio pipeline, a fundamentally different runtime model than a
  stateless, cold-starting Lambda function. Possibly revisited later as an
  explicitly separate always-on component, but not on the near-term roadmap.
- **Sharding.** cordless bots don't hold a gateway connection, so the scaling
  problem sharding solves doesn't apply here.
- **Guild-level command permission overwrites.** Discord only accepts these
  from an OAuth2 authorization-code Bearer token tied to a real admin user,
  a bot token or the client-credentials grant cordless uses everywhere else
  is rejected outright. That makes it a one-off, per-guild, per-admin action
  rather than something a `cordless deploy` step can automate. Discord's own
  Server Settings UI already covers this per guild with no bot involvement,
  which is the intended path. `default_member_permissions` (already
  supported) remains the way to gate a command from code.
- Rough cost visibility in cordless deploy/cordless logs output: skipped: almost every cordless bot sits inside AWS's free tier, so a live estimate would mostly just print "~$0.00" while costing us pricing constants and CloudWatch polling to maintain. Not worth it unless that changes.

---

Have a request that isn't listed? Open an issue or start a discussion on
[GitHub](https://github.com/borhara/cordless).
