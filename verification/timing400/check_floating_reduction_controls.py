#!/usr/bin/env python3
"""Check floating reduction against native controls and exact series solutions."""
from decimal import Decimal,localcontext
import json
from pathlib import Path
import sys
import numpy as np
import scipy
from scipy.sparse.linalg import cg
from reduce_floating_capacitance import build_graph,certificate
from audit_parent_capacitance_network import decimal_value
from run_dco_qualification import ROOT,sha,save


def exact(path):
    branches=[]
    for line in path.read_text().splitlines():
        if line.startswith('C'):
            f=line.split();branches.append((f[1],f[2],decimal_value(f[3])*Decimal('1e15')))
    floating={node for a,b,c in branches for node in [a,b]}-{'SIG','VSUBS'}
    assert len(floating)==1
    node=next(iter(floating))
    def edge(a,b):return sum((c for x,y,c in branches if {x,y}=={a,b}),Decimal(0))
    sf,fg,direct=edge('SIG',node),edge(node,'VSUBS'),edge('SIG','VSUBS')
    assert sf>0 and fg>0
    with localcontext() as context:
        context.prec=60
        return direct+sf*fg/(sf+fg)


def main():
    base=ROOT/'build/timing400/release_001'
    out=base/'floating_capacitance_reduction_controls_001'
    controls=[base/'lower_fill_capacitance_controls_001/poly_drawing/control.spice',
        base/'fill_capacitance_control_001/drawing_purpose/control.spice']
    paths=[Path(__file__).resolve(),Path(__file__).with_name('reduce_floating_capacitance.py'),*controls]
    assert not out.exists()
    out.mkdir()
    records=[]
    for index,source in enumerate(controls):
        graph=build_graph(source,['SIG'])
        trial,info=cg(graph['matrix'],graph['rhs'][0][graph['keep']],rtol=1e-14,atol=0)
        assert info==0
        result,_=certificate(graph,0,trial)
        expected=exact(source)
        assert Decimal(str(result['wire_capacitance_lower_ff']))<=expected<=Decimal(str(result['wire_capacitance_upper_ff']))
        assert result['interval_width_ff']<1e-8
        zero,_=certificate(graph,0,np.zeros_like(trial))
        assert Decimal(str(zero['wire_capacitance_lower_ff']))<=expected<=Decimal(str(zero['wire_capacitance_upper_ff']))
        assert zero['interval_width_ff']>.1
        isolated=out/f'isolated_{index}.spice'
        isolated.write_text(source.read_text()+'\nCisolated TEST_FLOAT_A TEST_FLOAT_B 2f\n')
        alternate=build_graph(isolated,['SIG'])
        assert alternate['unanchored_nodes']==2 and alternate['unanchored_components']==1
        x,code=cg(alternate['matrix'],alternate['rhs'][0][alternate['keep']],rtol=1e-14,atol=0)
        assert code==0
        added,_=certificate(alternate,0,x)
        assert Decimal(str(added['wire_capacitance_lower_ff']))<=expected<=Decimal(str(added['wire_capacitance_upper_ff']))
        bad=out/f'negative_{index}.spice'
        bad.write_text(source.read_text()+'\nCnegative SIG VSUBS -1f\n')
        try:build_graph(bad,['SIG'])
        except AssertionError:negative=True
        else:raise AssertionError('negative capacitor accepted')
        records.append(dict(source=str(source),exact_series_result_ff=str(expected),computed=result,
            zero_trial_certificate=zero,unanchored_component_certificate=added,
            inaccurate_trial_does_not_meet_narrow_width_target=True,negative_capacitor_rejected=negative))
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},native_control_cases=2,
        exact_decimal_series_values_enclosed=True,unanchored_component_zero_port_effect_verified=True,
        wrong_trial_reported_with_wide_interval=True,negative_capacitor_controls_rejected=True,
        numpy_version=np.__version__,scipy_version=scipy.__version__,results=records,
        full_layout_numerical_reduction_complete=False,full_rc_or_material_enclosure_qualified=False,
        native_analog_jobs_added=0,physical_timing_qualified=False,release_qualified=False))
    print('Two native controls enclose exact Decimal series results; isolated components preserve port C; wrong trials and negative C rejected.')


if __name__=='__main__':main()
