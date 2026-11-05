"""Use the KLayout database API under either supported Python import layout.

Frozen geometry helpers import ``pya``; the pinned Librelane Python exports
that same database API as ``klayout.db``. Register only the missing alias.
"""
import sys
try:
    import pya
except ModuleNotFoundError as error:
    if error.name != 'pya':
        raise
    import klayout.db as pya
    sys.modules['pya'] = pya
