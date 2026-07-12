"""Fixture: an extension using the manual setup(bot) hook."""

calls = []


def setup(bot):
    calls.append(bot)
