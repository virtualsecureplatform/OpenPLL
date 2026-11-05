#!/usr/bin/env python3
"""Classify SPEF virtual terminal coordinates against actual pin rectangles.

A pin's reported coordinate can be the mean of rectangle centers, outside the
physical conductor. Require that mean to match, and the independently probed
actual rectangles to belong to the expected net. Keep these virtual points
separate from physical internal-R coordinates and capacitor placement.
"""
from fractions import Fraction
import json
from pathlib import Path
from audit_DCO_intercell_wire_rc import canonical,normalized
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def centroid(probes):
    assert probes
    return [sum((Fraction(p['rect_nm'][i]+p['rect_nm'][i+2],2) for p in probes),Fraction(0))/len(probes) for i in [0,1]]


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'current_DCO_intercell_wire_rc_001'
    geometry=base/'DCO_intercell_wire_rc_geometry_001'
    inventory=base/'DCO_signal_pin_geometry_001'
    g=verify(geometry/'assessment.json');i=verify(inventory/'assessment.json')
    assert g['missing_or_split_signal_terminals']==0 and g['distinct_logical_nets_shorted']==0
    original=json.loads((inventory/'terminals.json').read_text())
    resolved=json.loads((geometry/'terminals.json').read_text())
    probes={(canonical(r['instance']),r['pin']):r for r in original}
    components={(canonical(r['instance']),r['pin']):r for r in resolved}
    assert len(probes)==len(components)==2071
    coordinates=json.loads((geometry/'coordinates.json').read_text())
    parsed={c:normalized(source/f'{c}.spef') for c in ['min','nom','max']}
    virtual=[];internal_count=0;physical_terminal_count=0
    for row in coordinates:
        net=parsed[row['corner']][row['net']]
        terminals={n:key for key,(n,d,k) in net['terminals'].items()}
        if row['spef_node'] not in terminals:
            internal_count+=1;assert row['expected_net_found'],row
        elif row['expected_net_found']:physical_terminal_count+=1
        else:
            key=terminals[row['spef_node']];assert key in probes,key
            pin=probes[key];physical=components[key]
            assert pin['logical_net']==physical['logical_net']==row['net']
            assert physical['clusters']==[row['expected_cluster']] and physical['missing_rectangular_probes']==0
            mean=centroid(pin['probes'])
            assert all(abs(Fraction(x)-y)<=1 for x,y in zip(row['point_nm'],mean)),(key,row['point_nm'],mean)
            virtual.append(dict(corner=row['corner'],net=row['net'],spef_node=row['spef_node'],
                reported_point_nm=row['point_nm'],mean_of_actual_pin_rect_centers_nm=[str(v) for v in mean],
                rectangle_probes=len(pin['probes']),actual_rectangles_on_expected_component=True,
                virtual_terminal_point_is_physical_conductor_position=False))
    assert len(virtual)==g['unmatched_RC_coordinates']==354
    assert internal_count+physical_terminal_count+len(virtual)==g['RC_coordinates_checked']==8413
    first=virtual[0]
    wrong=next(r for r in original if r['logical_net']!=first['net'] and
        any(abs(Fraction(x)-y)>1000 for x,y in zip(first['reported_point_nm'],centroid(r['probes']))))
    assert not all(abs(Fraction(x)-y)<=1 for x,y in zip(first['reported_point_nm'],centroid(wrong['probes'])))
    out=base/'DCO_wire_rc_coordinate_classification_001';out.mkdir(exist_ok=False)
    save(out/'virtual_terminals.json',virtual)
    paths=[Path(__file__).resolve(),geometry/'assessment.json',geometry/'coordinates.json',geometry/'terminals.json',
        inventory/'assessment.json',inventory/'terminals.json',Path(__file__).with_name('audit_DCO_intercell_wire_rc.py'),
        *[source/f'{c}.spef' for c in parsed]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'virtual_terminals.json'):sha(out/'virtual_terminals.json')},
        RC_coordinates_classified=8413,physical_internal_R_coordinates_on_expected_net=internal_count,
        physical_terminal_coordinates_on_expected_net=physical_terminal_count,
        virtual_pin_coordinate_records=354,
        all_virtual_coordinates_match_mean_of_actual_pin_rectangle_centers_within_1nm=True,
        all_actual_terminal_rectangle_probes_on_expected_conductor=True,
        unclassified_coordinates=0,wrong_pin_centroid_control_rejected=True,
        virtual_points_reinterpreted_as_physical_positions=False,
        unique_layer_identity_qualified=False,C_to_R_geometry_assignment_qualified=False,
        complete_cell_internal_R_qualified=False,full_RC_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Classified8413 RC records:',internal_count,'physical internal nodes,',physical_terminal_count,
        'physical terminals,354 verified virtual pin centroids; no coordinate waiver.')


if __name__=='__main__':main()
