#!/usr/bin/env python3
"""Pin matching upstream RC source beside native path-isolation controls.

Source version identity is not a claim of binary/source equivalence. Native
controls remain authoritative for the installed tool's measured behavior.
No tool source or existing physical/extraction model is modified or adopted.
"""
from pathlib import Path
import json
import subprocess
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';out=base/'rc_extraction_source_analysis_001'
    repo=ROOT/'build/timing400/magic_source_inspection_001'
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','8.3.623^{}'],text=True).strip()
    assert commit=='fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    out.mkdir(exist_ok=False)
    texts={}
    for path in ['resis/ResReadExt.c','resis/ResRex.c','resis/ResPrint.c','doc/html/extresist.html','VERSION']:
        data=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+path])
        target=out/path;target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(data)
        texts[path]=data.decode()
    assert texts['VERSION'].strip()=='8.3.623'
    assert 'ResOptionsFlags |= ResOpt_Signal;' in texts['resis/ResRex.c']
    assert 'if (ResOptionsFlags & ResOpt_Signal)' in texts['resis/ResReadExt.c']
    assert 'node1->capacitance += MagAtof(argv[COUPLEVALUE]);' in texts['resis/ResReadExt.c']
    assert 'node2->capacitance += MagAtof(argv[COUPLEVALUE]);' in texts['resis/ResReadExt.c']
    paths=[Path(__file__).resolve(),base/'single_pass_distributed_rc_coupling_audit_002/assessment.json',
        base/'single_pass_distributed_rc_coupling_audit_002/comparison.json',
        base/'automatic_distributed_rc_coupling_audit_001/assessment.json',
        base/'automatic_distributed_rc_coupling_audit_001/comparison.json',
        base/'charge_preserving_rc_controls_002/assessment.json']
    observations={}
    for name,rel in [('manual','single_pass_distributed_rc_coupling_audit_002'),('automatic','automatic_distributed_rc_coupling_audit_001')]:
        details=json.loads((base/rel/'comparison.json').read_text())
        observations[name]={}
        for case,r in details.items():
            lost=[d for d in r['changed_branch_pairs'] if float(d['before_ff'])>0 and float(d['after_collapsed_ff'])==0]
            observations[name][case]=dict(changed_capacitor_pairs=len(r['changed_branch_pairs']),
                completely_lost_coupling_pairs=lost,negative_C_count=len(r['negative_exported_capacitors']),
                retained_positive_R=r['distributed_resistors'],matrix_preserved=False)
    assert all(len(r['completely_lost_coupling_pairs'])==5 for r in observations['manual'].values())
    assert all(not r['completely_lost_coupling_pairs'] for r in observations['automatic'].values())
    save(out/'observations.json',observations)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()},
        upstream_repository='https://github.com/RTimothyEdwards/magic',upstream_commit=commit,upstream_tag='8.3.623',
        source_version_matches_installed_version_identifier=True,binary_source_equivalence_proven=False,
        manual_command_sets_signal_mode=True,signal_mode_cap_reader_adds_coupling_to_both_node_totals=True,
        single_manual_native_controls_complete=True,automatic_only_native_controls_complete=True,
        both_native_paths_fail_complete_capacitor_matrix_preservation=True,
        manual_path_loses_five_internal_coupling_pairs=True,automatic_path_retains_those_pairs=True,
        both_paths_export_four_negative_capacitors=True,
        tool_sources_modified=False,installed_tools_replaced=False,upstream_changes_submitted=False,
        charge_preserving_reconstruction_is_lumped_and_unqualified=True,
        full_RC_geometry_or_transient_error_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,native_analog_jobs_added=0,scope=__doc__))
    print('Pinned Magic8.3.623 source and independent native observations; manual grounding and automatic substrate changes retained as nonpasses.')


if __name__=='__main__':main()
