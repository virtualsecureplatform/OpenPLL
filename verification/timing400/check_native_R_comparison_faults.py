#!/usr/bin/env python3
"""Validate R-graph comparison against real numeric, topology and terminal-location faults."""
from pathlib import Path
from decimal import Decimal
import shutil,shlex
from compare_native_R_networks_v4 import compare
from audit_active_dco_rc_capacitance import parse,terminals
from audit_parent_capacitance_network import decimal_value
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';source=base/'DCO_R_node_trace_controls_001/installed'
    out=base/'native_R_graph_comparison_fault_controls_001';out.mkdir(exist_ok=False)
    raw=next(source.glob('*.rcx.spice'));ext=next(source.glob('*.res.ext'))
    d=parse(raw);positive=compare(source,source)
    assert positive['bijective_mapping_proven'] and positive['unchanged_device_parameters_and_mapped_terminals']
    assert positive['exact_mapped_R_branch_multiplicity_preserved'] and not any(positive['R_C_differences'].values())
    results=[]
    for kind in ['R_value','R_topology','MOS_terminal_coordinate']:
        target=out/kind;target.mkdir();shutil.copy2(raw,target/raw.name);shutil.copy2(ext,target/ext.name)
        if kind in ['R_value','R_topology']:
            lines=(target/raw.name).read_text().splitlines();index=next(i for i,l in enumerate(lines) if l.startswith('R'))
            f=lines[index].split()
            if kind=='R_value':f[3]=str(decimal_value(f[3])*2)
            else:f[2]=next(p for p in d['ports'] if p not in f[1:3])
            lines[index]=' '.join(f);(target/raw.name).write_text('\n'.join(lines)+'\n')
        else:
            node=next(row[0] for row in d['X'].values() if terminals(row)==4)
            lines=(target/ext.name).read_text().splitlines();changed=False
            for i,line in enumerate(lines):
                if not line.startswith('rnode '):continue
                f=shlex.split(line)
                if f[1]==node:
                    f[4]=str(int(f[4])+1000000)
                    # native node names are quoted; all remaining fields numeric
                    lines[i]='rnode "'+f[1]+'" '+' '.join(f[2:]);changed=True
            assert changed;(target/ext.name).write_text('\n'.join(lines)+'\n')
        try:
            result=compare(source,target)
            rejected=not (result.get('bijective_mapping_proven') and result.get('unchanged_device_parameters_and_mapped_terminals') and result.get('exact_mapped_R_branch_multiplicity_preserved') and not result.get('R_C_differences',{}).get('R',[1]))
        except AssertionError as error:result=dict(assertion=repr(error));rejected=True
        assert rejected,kind
        result.pop('node_mapping',None);save(target/'comparison.json',result)
        results.append(dict(fault=kind,rejected=True))
    save(out/'results.json',results)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('compare_native_R_networks.py'),
        Path(__file__).with_name('compare_native_R_networks_v4.py'),raw,ext]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()},native_R_comparison_fault_controls_passed=True,
        unchanged_native_network_positive_control_passed=True,numeric_topology_and_terminal_coordinate_faults_rejected=True,
        native_CAD_runs_added=0,physical_spatial_or_transient_model_qualified=False,release_qualified=False))
    print('Native R comparison controls pass: exact source and three real numeric/topology/terminal-coordinate faults.')


if __name__=='__main__':main()
