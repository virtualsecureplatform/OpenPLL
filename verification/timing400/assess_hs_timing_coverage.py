#!/usr/bin/env python3
"""Audit routed timing scope and a six-corner envelope without adopting it.

Existing native traces are reused; this tool launches no analog work. Source
corner enclosure and finite native samples cannot certify missing cell/PVT,
sequential constraints, waveform domains or extracted metal corners.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import sys

from run_dco_qualification import ROOT, REQUIREMENTS, sha, save
sys.path.insert(0,str(ROOT/'verification/timing450'))
from compare_hs_corner_tables_v2 import tables, interpolate

PHYSICAL = ROOT/'build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs'
SOURCE = ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells'
FAST = ['ff_n40C_1v95_ccsnoise','ff_100C_1v95','ff_150C_1v95']
SLOW = ['ss_n40C_1v60_ccsnoise','ss_100C_1v60','ss_150C_1v60']


def combine(source_tables, minimum):
    """Union-grid NLDM bound, restricted to every source's common domain.

Within each union rectangle the original interpolants share bilinear weights.
Taking min/max at its vertices therefore bounds every source interpolant
throughout that rectangle. This says nothing about unmeasured real PVT points.
"""
    if not source_tables:
        raise ValueError('no tables')
    axes=[]
    for key in ('index_1','index_2'):
        low=max(t[key][0] for t in source_tables)
        high=min(t[key][-1] for t in source_tables)
        if low>=high:
            raise ValueError('no common interpolation domain')
        axes.append(sorted({low,high}|{x for t in source_tables for x in t[key] if low<=x<=high}))
    operation=min if minimum else max
    return dict(index_1=axes[0],index_2=axes[1],
                values=[[operation(interpolate(t,(x,y)) for t in source_tables) for y in axes[1]] for x in axes[0]])


def evaluate(native, source):
    bounds={}
    for cell in ('buf_8','nand2_2'):
        for kind in ('cell_rise','cell_fall'):
            for name,corners,minimum in [('fast',FAST,True),('slow',SLOW,False)]:
                bounds[cell,kind,name]=combine([source[cell,c][kind] for c in corners],minimum)
    rows=[]
    for name,sample in native['records'].items():
        cell=next(c for c in ('buf_8','nand2_2') if name.startswith(c+'_'))
        parts=name.split('_')
        slew_ps=int(parts[-2][:-2]);load_ff=int(parts[-1][:-2])
        point=(.6*slew_ps/1000,load_ff/1000)
        for edge in ('rise','fall'):
            kind='cell_'+('fall' if edge=='rise' else 'rise') if cell=='nand2_2' else 'cell_'+edge
            low=interpolate(bounds[cell,kind,'fast'],point)
            high=interpolate(bounds[cell,kind,'slow'],point)
            actual=sample['input_'+edge+'_delay_ns']
            rows.append(dict(case=name,kind=kind,point_ns_pf=point,measured_ns=actual,
                fast_ns=low,slow_ns=high,enclosed=low<=actual<=high,
                below_fast_ns=max(0,low-actual),above_slow_ns=max(0,actual-high)))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        p.error('fresh output required')
    netlist=PHYSICAL/'physical_gate_raw.json'
    native_path=ROOT/'build/timing450/interface_characterization/nominal_hs_propagation_001/assessment.json'
    audit_path=native_path.parent.parent/'nominal_hs_propagation_independent_validation_001.json'
    previous_path=native_path.parent.parent/'nominal_hs_sampled_delay_envelope_001.json'
    native=json.loads(native_path.read_text())
    audit=json.loads(audit_path.read_text())
    previous=json.loads(previous_path.read_text())
    assert native['requested']==native['passing']==120 and audit['pass']
    assert sha(native_path)==audit['sha256'][str(native_path)]
    assert len(previous['comparisons'])==240 and previous['sampled_violations']==20
    pins={str(path):sha(path) for path in [netlist,native_path,audit_path,previous_path,REQUIREMENTS,
        Path(__file__).resolve(),ROOT/'verification/timing450/compare_hs_corner_tables_v2.py']}
    for path,digest in audit['sha256'].items():
        if not Path(path).exists():
            raise ValueError('missing independent-audit artifact: '+path)
        if sha(path)!=digest:
            raise ValueError('stale independent-audit artifact: '+path)
        pins[path]=digest
    module=json.loads(netlist.read_text())['modules']['IntegerPLL_AcquiringCore']
    counts=Counter(cell['type'] for cell in module['cells'].values())
    inventory={};source={};missing=[]
    for cell in sorted(counts):
        family=cell.split('__')[1].rsplit('_',1)[0]
        path=SOURCE/family/(cell+'__tt_025C_1v80_ccsnoise.lib.json')
        if not path.exists():
            path=SOURCE/family/(cell+'__tt_025C_1v80.lib.json')
        if not path.exists():
            missing.append(cell)
            inventory[cell]=dict(instances=counts[cell],missing_source_timing=True)
            continue
        pins[str(path)]=sha(path)
        data=json.loads(path.read_text());tt=tables(data)
        arc_types=Counter(identity[2] or 'combinational' for identity in tt)
        entry=dict(instances=counts[cell],timing_table_count=len(tt),
                   timing_arc_count=len({identity[:-1] for identity in tt}),table_timing_types=dict(arc_types))
        entry['source_corner_files']={}
        for corner in FAST+SLOW:
            view=SOURCE/family/(cell+'__'+corner+'.lib.json')
            entry['source_corner_files'][corner]=view.exists()
            if cell in ('sky130_fd_sc_hs__buf_8','sky130_fd_sc_hs__nand2_2'):
                pins[str(view)]=sha(view)
                source[cell.split('__')[1],corner]={key[-1].split(',')[0]:value
                    for key,value in tables(json.loads(view.read_text())).items()
                    if key[1]=='A' and key[-1].split(',')[0] in ('cell_rise','cell_fall')}
        inventory[cell]=entry
    comparisons=evaluate(native,source)
    failures=[row for row in comparisons if not row['enclosed']]
    functional={cell:row for cell,row in inventory.items() if row.get('timing_table_count',0)}
    spec=json.loads(REQUIREMENTS.read_text())
    report=dict(analysis_complete=True,requirements=str(REQUIREMENTS),
        routed_instances=sum(counts.values()),routed_cell_types=len(counts),
        timing_cell_types=len(functional),timing_arcs=sum(row['timing_arc_count'] for row in functional.values()),
        missing_source_cells=missing,inventory=inventory,source_fast_corners=FAST,source_slow_corners=SLOW,
        native_samples=240,previous_violations=20,extended_envelope_violations=len(failures),
        comparisons=comparisons,remaining_counterexamples=failures,sha256=pins,
        required_nominal_pvt=[dict(corner=c,supply_v=1.8,temperature_c=t)
                              for c,t in itertools.product(spec['corners'],spec['temperatures_c'])],
        timing_coverage_qualified=False,envelope_adopted=False,release_qualified=False,
        next_action='Obtain independently validated nominal-PVT delay/slew and sequential-constraint coverage. Even the expanded source-corner envelope has a native mixed-corner counterexample; no arbitrary fitted guard or FF/SS ordering assumption is adopted.',
        scope='Exact routed cell inventory and six-source-corner union-grid bounds tested against the existing240 native delay samples. Two sampled propagation arcs do not qualify all routed arcs, slew/load domains, sequential constraints, metalRC or nominal15PVT enclosure. No analog work launched.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    save(a.output,report)
    print(json.dumps({k:report[k] for k in ['routed_instances','routed_cell_types','timing_cell_types','timing_arcs','native_samples','previous_violations','extended_envelope_violations','remaining_counterexamples','envelope_adopted']}))


if __name__=='__main__':
    main()
