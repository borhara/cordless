"""Worker Lambda entrypoint for deferred interactions (async Lambda invoke)."""
import asyncio
import traceback

from .context import Context


def make_worker_handler(bot):
    """Return a Lambda handler that processes deferred interactions invoked asynchronously."""
    def handler(event, lambda_context=None):
        cron_name = (event or {}).get("_cordless_cron")
        if cron_name:
            return bot.run_cron(cron_name)

        ctx = Context(event, _worker_mode=True)
        try:
            asyncio.run(bot.router.dispatch(event, ctx))
        except Exception:
            traceback.print_exc()
            raise  # re-raise so Lambda sees a failure and can retry

    return handler
