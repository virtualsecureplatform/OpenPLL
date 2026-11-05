#!/usr/bin/env python3
"""Prepare a full-DCO charge-consistent prototype without adopting its placement.

Keep all native split wire R and device-terminal nodes; restore original native
MOS/resistor-wrapper parameters and every nonnegative original C. Deleted C
nodes attach to an existing device terminal on the same original conductor.
This proves the zero-wire-R network limit, including junction parameters. It
still uses lumped C placement, excludes assembled loading/fill/supply effects,
and is not qualified for range/calibration/timing or any long analog sweep.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import json
from pathlib import Path
import signal
import math
import time
from audit_active_dco_rc_capacitance import parse,compare,terminals
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    export=base/'active_dco_lumped_capacitance_export_001'
    assert verify(base/'active_dco_rc_capacitance_audit_001/assessment.json')['actual_live_DCO_source_audited']
    retired=verify(base/'unqualified_dco_RC_retirement_001/assessment.json');assert retired['all_native_processes_stopped_verified']
    source=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    raw_path=source/(top+'.rcx.spice');original_path=export/'lumped_full.spice'
    raw,original=parse(raw_path),parse(original_path)
    assert all(c>=0 for a,b,c in original['C'])
    owner_path=base/'candidate_layout_checks_001/owner.json'
    deadline=json.loads(owner_path.read_text())['deadline_uptime'];left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0;signal.alarm(max(1,math.floor(left)))
    present=set(raw['ports'])|{n for a,b,r in raw['R'] for n in [a,b]}
    candidates=defaultdict(set);replaced=[];device_lines={}
    for name,old in original['X'].items():
        new=raw['X'][name];n=terminals(old)
        assert n==terminals(new) and old[n]==new[n]
        present.update(new[:n])
        for a,b in zip(old[:n],new[:n]):candidates[a].add(b)
        device_lines[name]=' '.join([name,*new[:n],*old[n:]])
        if old[n:]!=new[n:]:replaced.append(dict(instance=name,old_RC_parameters=new[n+1:],restored_original_parameters=old[n+1:]))
    assert len(replaced)==2
    original_nodes={n for a,b,c in original['C'] for n in [a,b]}
    mapping={};assignment=[]
    for n in sorted(original_nodes):
        if n in present:target=n;method='same_existing_native_node_name'
        elif candidates[n]:target=sorted(candidates[n])[0];method='lumped_at_same_original_conductor_device_terminal'
        else:target=n;method='unchanged_unextracted_floating_conductor'
        mapping[n]=target;assignment.append(dict(original_node=n,target_node=target,method=method))
    caps=[]
    for line in original_path.read_text().splitlines():
        if line.startswith('C'):
            f=line.split();f[1],f[2]=mapping[f[1]],mapping[f[2]];caps.append(' '.join(f))
    lines=['* Unqualified lumped-placement RC prototype; do not use for physical range/calibration decisions.']
    for line in raw_path.read_text().splitlines():
        if line.startswith('C'):continue
        if line.startswith('X'):line=device_lines[line.split()[0]]
        if line.lower().startswith('.ends'):lines+=caps
        lines.append(line)
    out=base/'charge_preserving_DCO_RC_prototype_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(prepared_utc=datetime.now(timezone.utc).isoformat(),original_owner=str(owner_path),
        deadline_uptime=deadline,total_budget_restarted=False,native_analog_started=False))
    target=out/(top+'.prototype.spice');target.write_text('\n'.join(lines)+'\n')
    rebuilt=parse(target)
    assert rebuilt['R']==raw['R'] and rebuilt['ports']==raw['ports']
    assert len(rebuilt['C'])==len(original['C'])
    assert all(a[2]==b[2] for a,b in zip(rebuilt['C'],original['C']))
    result=compare(original,rebuilt)
    assert result['transistor_models_parameters_and_collapsed_connections_preserved']
    assert result['complete_capacitor_matrix_preserved_within_rounding']
    assert all(Decimal(r['delta_ff'])==0 for r in result['all_branch_pairs'])
    # A wrong conductor attachment on an actual large signal capacitor fails.
    index=max((i for i,r in enumerate(rebuilt['C']) if mapping['PLLOUT'] in r[:2]),key=lambda i:rebuilt['C'][i][2])
    damaged={**rebuilt,'C':list(rebuilt['C'])}
    a,b,c=damaged['C'][index]
    damaged['C'][index]=('VGND' if a!='VGND' else 'VPWR',b,c*10)
    assert not compare(original,damaged)['complete_capacitor_matrix_preserved_within_rounding']
    save(out/'C_assignment.json',assignment);save(out/'restored_device_parameters.json',replaced)
    save(out/'zero_R_matrix_comparison.json',result)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),
        raw_path,original_path,export/'assessment.json',base/'active_dco_rc_capacitance_audit_001/assessment.json',
        base/'unqualified_dco_RC_retirement_001/assessment.json',owner_path]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        MOS_devices=8618,intrinsic_resistor_wrappers=2,retained_native_wire_resistors=len(raw['R']),
        original_C_count=len(original['C']),original_C_values_in_order_preserved=True,all_C_nonnegative=True,
        all_original_native_device_models_parameters_preserved_in_zero_R_limit=True,
        restored_junction_parameter_records=len(replaced),
        exact_zero_R_capacitor_matrix_preserved=True,wrong_attachment_and_value_control_rejected=True,
        C_attachments_by_method=dict(Counter(r['method'] for r in assignment)),
        spatial_C_distribution_qualified=False,transient_model_error_enclosure_qualified=False,
        assembled_parent_fill_loading_and_supply_R_included=False,
        calibration_or_range_model_qualified=False,physical_timing_qualified=False,
        native_analog_started=False,long_native_sweeps_authorized_by_this_receipt=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('DCO prototype prepared:',len(raw['R']),'wire R,',len(original['C']),'original C,8618MOS+2intrinsic R; exact zero-R C/device limit verified. Placement/timing/range qualification still open.')


if __name__=='__main__':main()
