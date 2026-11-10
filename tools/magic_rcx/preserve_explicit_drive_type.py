"""Keep an explicit drive location paired with its recorded physical layer."""
MODE = 'getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def transform(text):
    start = text.index('int\nResProcessNode(')
    end = text.index('\n/*', start)
    part = text[start:end]
    needle = '\tif (node->status & PORTNODE)'
    replacement = '\tif ((node->status & PORTNODE) || ((' + MODE + ') && (node->status & DRIVELOC)))'
    if part.count(needle) != 1:
        raise ValueError('one native explicit driver type restoration required')
    return text[:start] + part.replace(needle, replacement) + text[end:]
