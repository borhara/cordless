"""Worker Lambda entrypoint for deferred interactions (SQS-triggered)."""
import asyncio
import traceback

from .context import Context


def make_worker_handler(bot):
    """Return an SQS Lambda handler that processes deferred interactions."""
    def handler(event, lambda_context=None):
        ctx = Context(event, _worker_mode=True)
        try:
            asyncio.run(bot.router.dispatch(event, ctx))
        except Exception:
            traceback.print_exc()

    return handler
