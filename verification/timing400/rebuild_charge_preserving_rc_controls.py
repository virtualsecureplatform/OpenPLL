#!/usr/bin/env python3
"""Reattach original positive C to native MOS terminals in small RC controls.

Keep native split R and MOS terminal connections, discard its altered C export,
and attach each original capacitor to the matching original node or a MOS
terminal on the same original conductor. No nearest-coordinate guess or model
alias is allowed. Exact original seeds may lie on unrepresented wire stubs.
This restores charge at DC after R collapse, but keeps lumped placement:
it does not qualify capacitance distribution along the real conductor, full
layout geometry, nonlinear device charge, transient error or physical timing.
"""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import json
import shlex
from audit_distributed_rc_coupling import parse,compare
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def seed_mapping(original_ext,res_ext,before,distributed):
    seeds={};positions=defaultdict(set)
    for line in original_ext.read_text().splitlines():
        f=shlex.split(line)
        if f and f[0] in ['node','substrate']:seeds[f[1]]=(int(f[4]),int(f[5]))
    for line in res_ext.read_text().splitlines():
        f=shlex.split(line)
        if f and f[0]=='rnode':positions[(int(f[4]),int(f[5]))].add(f[1])
    present=set(distributed['ports'])
    present.update(n for a,b,r in distributed['R'] for n in [a,b])
    present.update(n for row in distributed['X'].values() for n in row[:4])
    original_nodes={n for a,b,c in before['C'] for n in [a,b]}
    driven_before=set(before['ports'])|{n for row in before['X'].values() for n in row[:4]}
    terminal_candidates=defaultdict(set)
    for name,row in before['X'].items():
        other=distributed['X'][name]
        assert row[4:]==other[4:]
        for a,b in zip(row[:4],other[:4]):terminal_candidates[a].add(b)
    mapping={};records=[]
    for n in sorted(original_nodes):
        if n in present:
            target=n;method='same_native_node_name'
        elif n not in driven_before:
            # An unextracted floating conductor remains explicit and isolated
            # through its original capacitors; no resistor connection is added.
            target=n;method='unchanged_unextracted_floating_conductor'
        else:
            assert n in seeds,n
            candidates=terminal_candidates[n]&present
            assert candidates,(n,candidates)
            target=sorted(candidates)[0];method='lumped_at_existing_native_MOS_terminal_on_same_original_conductor'
        mapping[n]=target
        records.append(dict(original=n,attached_node=target,method=method,seed=seeds.get(n)))
    return mapping,records


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'driven_distributed_rc_coupling_controls_004'
    assert verify(source/'assessment.json')['two_native_controls_completed']
    out=base/'charge_preserving_rc_controls_002';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_distributed_rc_coupling.py'),
        Path(__file__).with_name('audit_parent_capacitance_network.py'),source/'assessment.json']
    results={}
    for name in ['floating_tile','ported_tile']:
        case=source/name;before_path,raw_path=case/'lumped.spice',case/'distributed.spice'
        ext=case/'DRIVEN_COUPLING_CONTROL.ext';res=case/'DRIVEN_COUPLING_CONTROL.res.ext'
        before,raw=parse(before_path),parse(raw_path)
        mapping,details=seed_mapping(ext,res,before,raw)
        assert any(r['method']=='lumped_at_existing_native_MOS_terminal_on_same_original_conductor' for r in details)
        caps=[]
        for line in before_path.read_text().splitlines():
            if line.startswith('C'):
                f=line.split();f[1],f[2]=mapping[f[1]],mapping[f[2]];caps.append(' '.join(f))
        target=out/(name+'.spice');lines=[]
        for line in raw_path.read_text().splitlines():
            if line.startswith('C'):continue
            if line.lower().startswith('.ends'):lines+=caps
            lines.append(line)
        target.write_text('\n'.join(lines)+'\n')
        rebuilt=parse(target)
        assert rebuilt['R']==raw['R'] and rebuilt['X']==raw['X'] and rebuilt['ports']==raw['ports']
        assert len(rebuilt['C'])==len(before['C']) and all(c>=0 for a,b,c in rebuilt['C'])
        check=compare(before,rebuilt)
        assert check['complete_capacitor_matrix_preserved_within_rounding']
        assert not check['changed_branch_pairs']
        # Exact equality is stricter than the checker's print-rounding bound.
        assert all(Decimal(r['delta_ff'])==0 for r in check['all_branch_pairs'])
        # A wrong attachment to a different original R component must fail.
        damaged={**rebuilt,'C':[(('VGND' if a==mapping['X'] else a),b,c) for a,b,c in rebuilt['C']]}
        assert not compare(before,damaged)['complete_capacitor_matrix_preserved_within_rounding']
        results[name]=dict(original_capacitors=len(before['C']),retained_native_R=len(raw['R']),
            negative_capacitors=0,exact_collapsed_capacitor_matrix_preserved=True,
            native_R_MOS_and_port_records_unchanged=True,original_conductor_attachment=details,
            wrong_conductor_attachment_rejected=True,comparison=check)
        paths += [before_path,raw_path,ext,res]
    save(out/'observations.json',results)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},control_cases=2,
        original_capacitor_values_and_count_preserved=True,
        exact_collapsed_capacitor_matrices_preserved=True,
        native_R_MOS_and_port_records_preserved=True,all_capacitors_nonnegative=True,
        original_conductor_MOS_terminal_used_for_deleted_driven_nodes=True,
        exact_original_seed_position_preservation_proven=False,
        nearest_node_guesses_used=False,wrong_conductor_negative_control_rejected=True,
        capacitor_distribution='original lumped C attached at an existing terminal on the same conductor',
        physical_distributed_capacitance_geometry_qualified=False,
        transient_error_or_timing_enclosure_qualified=False,full_layout_RC_qualified=False,
        runtime_model_qualified=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    print('Both controls retain31 native R and all MOS; exact original positive-C matrix restored at original-conductor terminals. Distributed-placement/timing qualification remains open.')


if __name__=='__main__':main()
