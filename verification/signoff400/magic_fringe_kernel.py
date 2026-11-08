"""Integrate Magic's native rectilinear fringe kernel over a receiver rectangle.

The 0.6366 constant deliberately matches the pinned extractor. This is a
geometric integration helper, not a qualified capacitance-placement model.
"""
import math
from audit_magic_overlap_support import area

LEFT, TOP, RIGHT, BOTTOM = 1, 2, 4, 8


def measure(box, boundary, direction, multiplier):
    area(box)
    area(boundary)
    if not math.isfinite(multiplier) or multiplier < 0:
        raise ValueError('finite nonnegative native multiplier required')
    if direction in (LEFT, RIGHT):
        if boundary[0] != boundary[2]:
            raise ValueError('vertical boundary required')
        length = box[3] - box[1]
        if direction == LEFT:
            near, far = boundary[0] - box[2], boundary[0] - box[0]
        else:
            near, far = box[0] - boundary[2], box[2] - boundary[2]
    elif direction in (TOP, BOTTOM):
        if boundary[1] != boundary[3]:
            raise ValueError('horizontal boundary required')
        length = box[2] - box[0]
        if direction == BOTTOM:
            near, far = boundary[1] - box[3], boundary[1] - box[1]
        else:
            near, far = box[1] - boundary[3], box[3] - boundary[3]
    else:
        raise ValueError('native boundary direction required')
    # Native clipping may include underlap; only the near distance is clamped.
    near = max(0, near)
    if far < near:
        raise ValueError('receiver has no outward fringe support')
    return (0.6366 * math.atan(multiplier * far)
            - 0.6366 * math.atan(multiplier * near)) * length
