"""Recognize Magic's non-electrical floating-node annotation without dropping elements."""
import re


def strip_floating_annotation(line):
    return re.sub(r'\s+\$\s+\*\*FLOATING\s*$', '', line)
