"""Read routed STA slew at every functional pin of every used sequential cell."""
import argparse,csv,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
import sys,re
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_routed_timing import normalize_spef
from resources import lease
from compiled_charge import execute

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def word(s):
    if any(c in s for c in '{}\n\r'):raise ValueError('unsupported Tcl identifier')
    return '{'+s+'}'


def run(route,placement,proof,output):
    rr,pr,er=[p/'assessment.json' for p in (route,placement,proof)];r,p,e=[json.loads(f.read_text()) for f in (rr,pr,er)]
    for receipt in (r,p,e):verify(receipt['input_sha256']);verify(receipt['artifacts'])
    if not e['all_transition_and_output_functions_equivalent'] or e['input_sha256'].get(str(route/'route.v'))!=sha(route/'route.v'):raise ValueError('matching route equivalence required')
    netlist=proof/'proof/physical.json'
    if e['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('pinned physical netlist required')
    module=json.loads(netlist.read_text())['modules']['IntegerPLL_ProgrammedCore']
    sequential={name:cell for name,cell in module['cells'].items() if any(tag in cell['type'] for tag in ('__dfrtp_','__dfstp_'))}
    if not sequential:raise ValueError('no sequential state')
    expected={}
    for name,cell in sequential.items():
        for pin in ('D','CLK','Q','RESET_B' if '__dfrtp_' in cell['type'] else 'SET_B'):
            if len(cell['connections'].get(pin,[]))!=1:raise ValueError('scalar functional sequential pins required')
            expected[(name,pin)]=cell['type']
    output.mkdir(parents=True,exist_ok=False);table=output/'slews.tsv';script=output/'query.tcl'
    lib=next(Path(f) for f in r['input_sha256'] if f.endswith('.lib') and 'antenna' not in f)
    extra_libraries=[Path(f) for f in r['input_sha256'] if f.endswith('/antenna_diode_load.lib')]
    constraints=placement/'diagnostic.sdc';raw_spef=route/'route.nom.spef'
    normalized,changes=normalize_spef(raw_spef.read_text());spef=output/'route.nom.normalized.spef';spef.write_text(normalized)
    supplementary=''.join('read_liberty '+str(p)+'\n' for p in extra_libraries)
    text=f'read_liberty {lib}\n{supplementary}read_db {route}/route.odb\nsource {constraints}\nset_propagated_clock [all_clocks]\nread_spef {spef}\nset_thread_count 1\nreport_worst_slack -max\nset f [open {table} w]\nputs $f "instance\\tpin\\tmaster\\trise_min_s\\trise_max_s\\tfall_min_s\\tfall_max_s"\n'
    for (name,pin),master in expected.items():
        text+=f'set p [sta::get_port_pin_error pin {word(name.lstrip(chr(92))+"/"+pin)}]\nset vertices [$p vertices]\nif {{[llength $vertices]!=1}} {{error "functional pin must have one timing vertex"}}\nset v [lindex $vertices 0]\nputs $f [join [list {word(name)} {pin} {master} [$v slew rise min] [$v slew rise max] [$v slew fall min] [$v slew fall max]] "\\t"]\n'
    text+='close $f\nexit\n';script.write_text(text)
    pins={str(f):sha(f) for f in (rr,pr,er,netlist,lib,*extra_libraries,constraints,raw_spef,spef,ROOT/'verification/timing400/check_compact_routed_timing.py',Path(OPENROAD),script,Path(__file__).resolve())}
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'query.log',deadline,4)
    log=(output/'query.log').read_text()
    if re.search(r'STA-(1648|1650)',log):raise ValueError('unresolved SPEF instance/net annotation')
    rows=[];seen=set()
    for row in csv.DictReader(table.open(),delimiter='\t'):
        key=(row['instance'],row['pin'])
        if key not in expected or key in seen or row['master']!=expected[key]:raise ValueError('functional pin inventory mismatch')
        seen.add(key)
        for k in ('rise_min_s','rise_max_s','fall_min_s','fall_max_s'):
            row[k]=float(row[k])
            if not math.isfinite(row[k]) or row[k]<0:raise ValueError('invalid annotated pin slew')
        rows.append(row)
    if seen!=expected.keys():raise ValueError('incomplete sequential pin coverage')
    detail=output/'slews.json';save(detail,rows);verify(pins)
    summary={pin:max(max(row['rise_max_s'],row['fall_max_s'])*1e12 for row in rows if row['pin']==pin) for pin in {x['pin'] for x in rows}}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(table):sha(table),str(detail):sha(detail),str(spef):sha(spef)},
        spef_clock_buffer_name_entries_normalized=changes,sequential_cells=len(sequential),functional_pins=len(rows),all_functional_sequential_pins_covered=True,
        maximum_slew_ps_by_pin=summary,slew_definition='OpenSTA library 20-to-80-percent thresholds; supplied TT25 library and nominal routed RC',
        conditional_antenna_diode_load_view_included=bool(extra_libraries),native_PVT_slew_envelope_qualified=False,physical_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','placement','proof','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.route.resolve(),a.placement.resolve(),a.proof.resolve(),a.output.resolve())
