"""Classify early zero slew at physically unconnected outputs without qualification."""
import argparse,json,re,subprocess,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from inventory_selected_pin_electrical_coverage_v2 import groups


def run(inventory,constant_review,output):
    if output.exists():raise FileExistsError(output)
    receipt=inventory/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    constant=json.loads(constant_review.read_text());verify(constant['input_sha256'])
    if not constant['late_zero_slew_topology_review_complete'] or constant['input_sha256'].get(str(receipt))!=sha(receipt):
        raise ValueError('same-inventory late-zero topology review required')
    odb=ROOT/'build/signoff400/prototype_v3_selected_route_019/route.odb'
    if a['input_sha256'].get(str(odb))!=sha(odb):raise ValueError('unchanged inventory database required')
    output.mkdir(parents=True);script=output/'graph.tcl';graph=output/'unconnected.tsv'
    script.write_text('read_db '+str(odb)+'\nset stream [open {'+str(graph)+r'''} w]
set block [ord::get_db_block]
foreach inst [$block getInsts] {
 foreach pin [$inst getITerms] {
  if {[[$pin getMTerm] getIoType] ne "OUTPUT" || [$pin getNet] ne "NULL"} {continue}
  puts $stream [join [list "[$inst getName]/[[$pin getMTerm] getName]" [[$inst getMaster] getName]] "\t"]
 }
}
puts $stream DONE
close $stream
exit
''')
    binary=Path('/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad');os.sched_setaffinity(0,{31})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600),(output/'native.log').open('x') as log:
        subprocess.run([str(binary),'-exit',str(script)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    lines=graph.read_text().splitlines()
    if not lines or lines[-1]!='DONE':raise ValueError('complete native graph required')
    unconnected=dict(line.split('\t') for line in lines[:-1]);results={};paths=[receipt,constant_review,odb,script,graph,binary,Path(__file__).resolve()]
    for corner in ['tt','ff','ss','sf','fs']:
        pinfile=inventory/f'{corner}_pins.json';rows=json.loads(pinfile.read_text());paths.append(pinfile)
        lib=ROOT/f'build/signoff400/prototype_v3_observed_reset_load_liberty_001/{corner}_early.lib'
        if a['input_sha256'].get(str(lib))!=sha(lib):raise ValueError('same early timing view required')
        paths.append(lib);cells=dict(groups(lib.read_text(),'cell'));records=[]
        expected=set(a['results'][corner]['unconnected_output_pins'])
        if set(unconnected)!=expected:raise ValueError('native unconnected outputs differ from inventory')
        for row in rows:
            if min(row['rise_min_ns'],row['fall_min_ns'])!=0 or max(row['rise_max_ns'],row['fall_max_ns'])==0:continue
            if row['net_connected']!='0' or row['driver']!='1' or unconnected.get(row['pin'])!=row['master']:
                raise ValueError('early-zero pin has a functional connected net or mismatched master')
            pin=dict(groups(cells[row['master']],'pin'))[row['port']];tables=[]
            for direction,body in re.findall(r'(rise|fall)_transition\s*\([^)]*\)\s*\{.*?values\s*\((.*?)\);',pin,re.S):
                values=[float(x) for x in re.findall(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?',body)]
                if not values:raise ValueError('complete transition table values required')
                tables.append(dict(direction=direction,minimum_ns=min(values),zero_entries=sum(v==0 for v in values)))
            if not tables:raise ValueError('propagation slew tables required')
            records.append(dict(pin=row['pin'],master=row['master'],native_output_net_absent=True,rise_min_ns=row['rise_min_ns'],fall_min_ns=row['fall_min_ns'],early_transition_tables=tables))
        results[corner]=dict(early_only_zero_pins=len(records),all_early_only_zeros_physically_unconnected=True,records=records)
    paths += [Path(__file__).with_name(n) for n in ['common_v3.py','resources.py','inventory_selected_pin_electrical_coverage_v2.py']]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,results=results,native_unconnected_output_count=len(unconnected),
        zero_slew_topology_review_complete=True,zero_values_are_physical_slew_measurements=False,
        scope='topology classification only; early library uncertainty floors remain conditional timing models',
        native_timing_views_qualified=False,physical_power_up_or_constant_drive_qualified=False,parent_analog_macros_covered=False,
        electrical_rules_qualified=False,physical_integrity_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['inventory','constant-review','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.inventory.resolve(),a.constant_review.resolve(),a.output.resolve())
