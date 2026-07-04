"""Helpers used by the engine caller."""
from core.engine import Engine


def describe(engine):
    assert isinstance(engine, Engine)
    return "engine with config %r" % (engine.config,)


def double(x):
    return x * 2
