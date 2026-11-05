#!/usr/bin/env python3
"""Separate recognized poly-resistor bodies from ideal conductor components.

The PDK maps POLYRES(66/13) and POLYSHORT(66/15) to resistor devices. Their
terminals are linked by a finite resistance, not an ideal-wire equivalence.
Other resistor families are outside this helper's validated device coverage.
"""
import pya
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage


def conductor_geometry(layout,top):
    result=geometry(layout,top)
    bodies=pya.Region()
    for datatype in [13,15]:bodies|=pya.Region(top.begin_shapes_rec(layout.layer(66,datatype)))
    bodies=bodies.merged()
    assert (bodies&result['gate']).is_empty(),'resistor marker overlaps recognized MOS gate'
    result['poly']-=bodies
    return result
