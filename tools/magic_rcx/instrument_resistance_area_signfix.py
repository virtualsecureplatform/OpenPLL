"""Isolated one-expression sign correction, layered on checked lineage logging."""
from instrument_resistance_lineage_v2 import instrument_sources as observe

OLD = 'height * (LEFT(tile) - RIGHT(tile))'
NEW = 'height * (RIGHT(tile) - LEFT(tile))'


def instrument_sources(sources):
    if sources['ResMakeRes.c'].count(OLD) != 1:
        raise ValueError('one pinned horizontal single-breakpoint expression required')
    changed = observe(sources)
    text = changed['ResMakeRes.c']
    # One native statement and its diagnostic copy of the added value.
    if text.count(OLD) != 2:
        raise ValueError('exact native expression and diagnostic mirror required')
    changed['ResMakeRes.c'] = text.replace(OLD, NEW)
    return changed
