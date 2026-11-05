"""Strict correction of the pinned HS diode schematic against source GDS."""
import math
import re


def normalize_diode_spice(text, geometry):
    # The pinned GDS has a rectangular n-diffusion junction identified by
    # 81/23. Contacts inside it do not create additional junction sidewalls.
    for key, expected in [('area_um2', .6417), ('perimeter_um', 3.24)]:
        if not math.isclose(geometry.get(key, float('nan')), expected, rel_tol=1e-9):
            raise RuntimeError(f'Unexpected HS diode GDS {key}')
    legacy = '.subckt sky130_fd_sc_hs__diode_2 DIODE VGND VNB VPB VPWR\nX0 VNB DIODE sky130_fd_pr__diode_pw2nd p=7.32e+06u a=6.417e+11p\n.ends'
    if text.count(legacy) != 1:
        raise RuntimeError('Unexpected pinned HS diode schematic')
    canonical = ('.subckt sky130_fd_sc_hs__diode_2 DIODE VGND VNB VPB VPWR\n'
                 'X0 VNB DIODE sky130_fd_pr__diode_pw2nd_05v5 '
                 f'perim={geometry["perimeter_um"] * 1e6:.12g} '
                 f'area={geometry["area_um2"] * 1e12:.12g}\n.ends')
    return text.replace(legacy, canonical)
