#!/usr/bin/env python3
"""Four-mode routed RC capacity screens using supplied TT25 timing only.

These screens retain diagnostic cross-domain exceptions. They do not cover
the required nominal15PVT views, physical interface assumptions or full timing.
"""
import argparse
import json
from pathlib import Path
import re

from check_compact_mapping import LIB, TECH, LEF, OPENROAD, run
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def normalize_spef(text):
    # Correct only escaped BBPD clock-buffer instance brackets in NAME_MAP.
    # R/C values and all connectivity outside those name entries stay exact.
    lines=text.splitlines();inside=False;changes=0
    for index,line in enumerate(lines):
        if line=='*NAME_MAP':inside=True
        elif line.startswith('*PORTS'):inside=False
        elif inside and ' clkbuf_' in line and 'BBPD' in line:
            fixed=line.replace('\\[','[').replace('\\]',']')
            if fixed!=line:changes+=1;lines[index]=fixed
    return '\n'.join(lines)+'\n',changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diode-model',required=True,type=Path)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--cts',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.route.resolve();cts=args.cts.resolve();out=args.output.resolve()
    receipt=verify(root/'assessment.json')
    assert receipt['restricted_master_inventory_passed'] and receipt['nominal_signal_rc_extracted']
    assert receipt['input_sha256'][str(cts/'cts.tcl')]==sha(cts/'cts.tcl')
    load=args.diode_model.resolve()
    diode=verify(load/'assessment.json')
    aux=load/'antenna_diode_load.lib'
    assert receipt['conditional_diode_load_model']==str(load/'assessment.json')
    assert receipt['input_sha256'][str(aux)]==sha(aux)
    out.mkdir(parents=True,exist_ok=False)
    models={rc:LIB.parents[3]/f'libs.tech/librelane/rules.openrcx.sky130A.{rc}.magic' for rc in ('nom','min','max')}
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_clock_tree.py').resolve(),
           Path(__file__).with_name('check_compact_mapping.py').resolve(),Path(OPENROAD),LIB,TECH,LEF,
           root/'assessment.json',root/'route.odb',root/'route.nom.spef',cts/'cts.tcl',*models.values()]
    files += [Path(__file__).with_name('check_compact_routed_timing_with_diodes.py').resolve(),load/'assessment.json',aux,Path(__file__).with_name('check_compact_routed_timing.py').resolve()]
    pins={str(p):sha(p) for p in files}
    header=f'read_lef {TECH}\nread_lef {LEF}\nread_liberty {LIB}\nread_liberty {aux}\nread_db {root}/route.odb\nset_thread_count 4\n'
    normalization={}
    for rc,model in models.items():
        raw=out/f'route.{rc}.spef'
        if rc=='nom':raw.write_bytes((root/'route.nom.spef').read_bytes())
        else:
            task=out/f'extract_{rc}.tcl'
            task.write_text(header+f'''define_process_corner -ext_model_index 0 RCX_{rc.upper()}
extract_parasitics -ext_model_file {model} -corner 0
write_spef {raw}
exit
''')
            assert run([OPENROAD,'-exit',task],out/f'extract_{rc}.log')==0
        text,changes=normalize_spef(raw.read_text())
        (out/f'route.{rc}.normalized.spef').write_text(text)
        normalization[rc]=changes
    base=(cts/'cts.tcl').read_text().split('create_clock -name REFCLK',1)[1].split('set_thread_count')[0]
    base='create_clock -name REFCLK'+base
    results={}
    for mode in (100,250,300,400):
        constraints=base.replace('-period 2.5 [get_ports PLLOUT]',f'-period {1000/mode:.9f} [get_ports PLLOUT]')
        constraints=constraints.replace('-divide_by 16 ',f'-divide_by {mode//25} ').replace('-waveform {0 1.25}',f'-waveform {{0 {500/mode:.9f}}}')
        # Apply to event clocks too; they are created after the original
        # all_clocks uncertainty/transition statements in the capacity fixture.
        constraints+='set_clock_transition 0.1 [all_clocks]\nset_clock_uncertainty 0.15 [all_clocks]\n'
        for rc in models:
            label=f'{mode}_{rc}';task=out/f'{label}.tcl'
            task.write_text(header+constraints+f'''set_propagated_clock [all_clocks]
read_spef {out}/route.{rc}.normalized.spef
report_parasitic_annotation -report_unannotated
report_checks -path_delay max -group_path_count 1 -digits 6
report_checks -path_delay min -group_path_count 1 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
check_setup -verbose
exit
''')
            assert run([OPENROAD,'-exit',task],out/f'{label}.log')==0
            log=(out/f'{label}.log').read_text()
            assert not any(token in log for token in ('Error:','STA-1648','STA-1650')),label
            slacks={}
            for block in log.split('Startpoint:')[1:]:
                group=re.search(r'Path Group: ([^\n]+)',block)
                kind=re.search(r'Path Type: (max|min)',block)
                slack=re.search(r'(-?\d+\.\d+)\s+slack',block)
                if group and kind and slack:slacks[f'{group[1]}:{kind[1]}']=float(slack[1])
            assert 'PLLOUT:max' in slacks and 'PLLOUT:min' in slacks,label
            annotations={name:int(value) for value,name in re.findall(r'Found (\d+) (partially unannotated|unannotated) drivers',log)}
            violations=[line.strip() for line in log.splitlines() if '(VIOLATED)' in line]
            results[label]=dict(slack_ns=slacks,annotation_driver_counts=annotations,
                reported_constraint_violations=violations,
                reported_setup_hold_electrical_checks_passed=all(value>=0 for value in slacks.values()) and not violations)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        results=results,spef_name_entries_normalized=normalization,
        all_reported_setup_hold_electrical_checks_passed=all(r['reported_setup_hold_electrical_checks_passed'] for r in results.values()),
        supplied_timing_view='TT25C1.8V only',nominal_15pvt_qualified=False,
        diode_input_capacitance_pf=diode['input_capacitance_upper_pf'],
        diode_load_view_conditional=True,full_timing_load_enclosure_qualified=False,
        adopted=False,physical_timing_qualified=False,release_qualified=False,scope=__doc__))
    print(json.dumps(results),flush=True)


if __name__=='__main__':main()
