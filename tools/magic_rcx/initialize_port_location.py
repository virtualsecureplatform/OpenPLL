"""Candidate fix for an ext port alias with no separate native node record."""
def transform(text):
    before='''    node->drivepoint.p_x = atoi(argv[PORT_LLX]);
    node->drivepoint.p_y = atoi(argv[PORT_LLY]);
'''
    after=before+'''    /* A port alias may have no node record to initialize its location. */
    if (node->location.p_x == INFINITY && node->location.p_y == INFINITY)
        node->location = node->drivepoint;
'''
    if text.count(before)!=1 or after in text:
        raise ValueError('one unmodified native port drivepoint initializer required')
    return text.replace(before,after)
