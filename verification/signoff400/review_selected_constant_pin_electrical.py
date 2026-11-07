"""Review constant-output constraint absence and model-zero slew provenance.

No capacitance limit is invented. Native power-up and analog-macro electrical
qualification remain separate from constant-function STA classification.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease


def run(inventory,output):
    if output.exists():raise FileExistsError(output)
    receipt=inventory/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    bank=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs'
    supplied=bank/'cells/conb/sky130_fd_sc_hs__conb_1__tt_025C_1v80_ccsnoise.lib.json'
    common=bank/'timing/sky130_fd_sc_hs__common.lib.json'
    definition=json.loads(supplied.read_text());defaults=json.loads(common.read_text())
    if 'default_max_capacitance' in defaults or 'max_capacitance' in definition:
        raise ValueError('source capacitance constraint changed; review before classification')
    for port,value in [('HI','1'),('LO','0')]:
        p=definition['pin,'+port]
        if p['direction']!='output' or p['function']!=value or 'max_capacitance' in p:
            raise ValueError('source constant pin semantics or limits changed')
    output.mkdir(parents=True);script=output/'graph.tcl';graph=output/'graph.tsv'
    odb=ROOT/'build/signoff400/prototype_v3_selected_route_019/route.odb'
    if a['input_sha256'].get(str(odb))!=sha(odb):raise ValueError('same inventory routed database required')
    script.write_text('read_db '+str(odb)+'\nset stream [open {'+str(graph)+r'''} w]
set block [ord::get_db_block]
foreach inst [$block getInsts] {
 if {[[$inst getMaster] getName] ne "sky130_fd_sc_hs__conb_1"} {continue}
 foreach pin [$inst getITerms] {
  set port [[$pin getMTerm] getName]
  if {$port ni {HI LO}} {continue}
  set name "[$inst getName]/$port"
  set net [$pin getNet]
  if {$net eq "NULL"} {puts $stream [join [list TIE $name -] "\t"];continue}
  puts $stream [join [list TIE $name [$net getName]] "\t"]
  foreach other [$net getITerms] {
   if {$other eq $pin} {continue}
   set oi [$other getInst]
   puts $stream [join [list LOAD $name "[$oi getName]/[[$other getMTerm] getName]" [[$oi getMaster] getName] [[$other getMTerm] getIoType]] "\t"]
  }
 }
}
puts $stream DONE
close $stream
exit
''')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    binary='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'
    os.sched_setaffinity(0,{31})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600),(output/'native.log').open('x') as log:
        subprocess.run([binary,'-exit',str(script)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    lines=graph.read_text().splitlines()
    if lines[-1]!='DONE':raise ValueError('complete graph dump required')
    ties={};loads={}
    for line in lines[:-1]:
        f=line.split('\t')
        if f[0]=='TIE':ties[f[1]]=f[2]
        elif f[0]=='LOAD':loads.setdefault(f[1],[]).append(dict(pin=f[2],master=f[3],direction=f[4]))
        else:raise ValueError('unexpected native graph row')
    if len(ties)!=16 or len(loads)!=8 or any(len(v)!=1 or v[0]['direction']!='INPUT' or not v[0]['pin'].endswith('/D') for v in loads.values()):
        raise ValueError('expected sixteen tie outputs and eight single D-pin loads')
    expected_zero=set(ties)|{v[0]['pin'] for v in loads.values()};results={}
    for corner in ['tt','ff','ss','sf','fs']:
        rows=json.loads((inventory/f'{corner}_pins.json').read_text());byname={r['pin']:r for r in rows}
        late_zero={r['pin'] for r in rows if r['rise_max_ns']==0 and r['fall_max_ns']==0}
        if late_zero!=expected_zero:raise ValueError('late-zero set differs from constant topology')
        issues=a['results'][corner]['coverage_issues']
        if {r['pin'] for r in issues}!=set(loads) or any(r['reasons']!=['missing_output_capacitance_limit'] for r in issues):
            raise ValueError('additional constraint coverage issues require review')
        results[corner]=dict(late_zero_pin_count=len(late_zero),all_late_zero_pins_explained_by_constant_topology=True,
            connected_tie_outputs=[dict(pin=n,function=definition['pin,'+n.rsplit('/',1)[1]]['function'],modeled_capacitance_pf=byname[n]['cap_max_pf'],load=loads[n][0]) for n in sorted(loads)],
            source_max_capacitance_specified=False,numerical_max_capacitance_check_available=False,
            disposition='Absent source constraint, not a measured limit violation; physical constant-drive validation remains open')
    paths=[receipt,supplied,common,odb,script,graph,output/'native.log',image,Path(__file__).resolve()]
    paths += [inventory/f'{c}_pins.json' for c in results]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,results=results,source_capacitance_limit_lost_in_rendering=False,
        late_zero_slew_topology_review_complete=True,early_zero_slew_review_complete=False,
        physical_power_up_or_constant_drive_qualified=False,load_models_qualified=False,parent_analog_macros_covered=False,
        electrical_rules_qualified=False,physical_integrity_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.inventory.resolve(),a.output.resolve())
