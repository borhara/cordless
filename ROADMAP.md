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

## In progress

- **Full Discord REST API coverage.** Today's REST surface is the handful of
  helpers on `Cordless` (`send_message`, `edit_message`, webhooks, roles,
  ...). That's being replaced with a complete typed client covering the rest
  of Discord's API: channels, guild management, members, roles, bans,
  invites, emoji, stickers, scheduled events, auto-moderation, application
  command management, the interaction-response endpoints, OAuth2, and more.
  Threads are the first resource shipped end-to-end; the rest are landing
  resource by resource.
- **User-installable apps.** Commands that run as a user-installed app in any
  DM or server, not just bots installed to a specific guild.

## Planned next

- Guild-level command permission overwrites (Discord's `/permissions` API),
  as a complement to the existing `default_member_permissions` bitfield.
- Command name/description localization (Discord's per-locale i18n).
- `cordless doctor`: one command to validate AWS credentials, the IAM role,
  Discord app config, and deployed function state, and point at what's wrong.
- Testing helpers for bot authors: fixtures/mocks for interaction payloads
  so people can unit-test their own `@bot.command` handlers without a live
  Discord round-trip.
- Rough cost visibility in `cordless deploy`/`cordless logs` output (Lambda
  invocations, plus DynamoDB if rate limiting is enabled), so "serverless"
  doesn't mean "opaque."

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

---

Have a request that isn't listed? Open an issue or start a discussion on
[GitHub](https://github.com/borhara/cordless).
