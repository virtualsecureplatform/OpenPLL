"""Observe ten native tile-area contributions without fixing or redistributing them."""


def instrument(text):
    marker = '#include "resis/resis.h"'
    if text.count(marker) != 1:
        raise ValueError('pinned resistance includes differ')
    text = text.replace(marker, marker + '\n#include "resistance_area_trace.h"')
    for horizontal in [True, False]:
        name = 'ResCalcEastWest' if horizontal else 'ResCalcNorthSouth'
        start = text.index('bool\n' + name + '(')
        end = text.find('\nbool\n', start + 1)
        if end < 0:
            end = len(text)
        body = text[start:end]
        if horizontal:
            rules = [
                ('p1->br_this', 'height * (LEFT(tile) - RIGHT(tile))', 'LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile)', '1.0'),
                ('p2->br_this', 'height * (p2->br_loc.p_x - LEFT(tile))', 'LEFT(tile), BOTTOM(tile), p2->br_loc.p_x, TOP(tile)', '1.0'),
                ('resistor->rr_connection1', 'rArea', 'p1->br_loc.p_x, BOTTOM(tile), p2->br_loc.p_x, TOP(tile)', '0.5'),
                ('resistor->rr_connection2', 'rArea', 'p1->br_loc.p_x, BOTTOM(tile), p2->br_loc.p_x, TOP(tile)', '0.5'),
                ('p2->br_this', 'height * (RIGHT(tile) - p2->br_loc.p_x)', 'p2->br_loc.p_x, BOTTOM(tile), RIGHT(tile), TOP(tile)', '1.0'),
            ]
        else:
            rules = [
                ('p1->br_this', 'width * (TOP(tile) - BOTTOM(tile))', 'LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile)', '1.0'),
                ('p2->br_this', 'width * (p2->br_loc.p_y - BOTTOM(tile))', 'LEFT(tile), BOTTOM(tile), RIGHT(tile), p2->br_loc.p_y', '1.0'),
                ('resistor->rr_connection1', 'rArea', 'LEFT(tile), p1->br_loc.p_y, RIGHT(tile), p2->br_loc.p_y', '0.5'),
                ('resistor->rr_connection2', 'rArea', 'LEFT(tile), p1->br_loc.p_y, RIGHT(tile), p2->br_loc.p_y', '0.5'),
                ('p2->br_this', 'width * (TOP(tile) - p2->br_loc.p_y)', 'LEFT(tile), p2->br_loc.p_y, RIGHT(tile), TOP(tile)', '1.0'),
            ]
        for index, (node, expression, box, weight) in enumerate(rules):
            old = node + '->rn_float.rn_area += ' + expression + ';'
            if body.count(old) != 1:
                raise ValueError('pinned resistance assignment differs: ' + old)
            body = body.replace(old, f'OPENPLL_RES_AREA({node}, {old[:-1]}, {expression}, {box}, {weight}, "{name}:{index}");')
        text = text[:start] + body + text[end:]
    return text
