"""Conditional enabled-phase timing experiment; startup/reset timing remains separate."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from compiled_charge import execute
from compare_mapped_routed_CDC import clock_roots

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def launch_edges(phase):
    if phase not in range(8):raise ValueError('eight enabled high-phase source edges required')
    return [2*phase+1,2*phase+17,2*phase+33]


def source_pins(module):
    bits=module['netnames']['core.bbpd_decision']['bits']
    if len(bits)!=2 or len(set(bits))!=2:raise ValueError('two decision state bits required')
    result=[];roots=clock_roots(module)
    for bit in bits:
        matches=[(n,c) for n,c in module['cells'].items() if c['connections'].get('Q')==[bit] and c['type']=='sky130_fd_sc_hs__dfrtp_1']
        if len(matches)!=1:raise ValueError('unique decision FF required')
        name,cell=matches[0]
        if tuple(roots(cell['connections']['CLK'][0]))!=('primary','PLLOUT',0,0):raise ValueError('decision FF clock root differs')
        result.append(name.lstrip('\\')+'/CLK')
    return result


def run(baseline,inventory,proof,output):
    receipts=[p/'assessment.json' for p in (baseline,inventory,proof)]
    b,i,p=[json.loads(f.read_text()) for f in receipts]
    for record in (b,i,p):verify(record['artifacts'])
    if not p.get('decision_changes_only_during_sampled_divided_clock_high_phase_proved') or not p.get('decision_update_enable_negative_control_rejected'):
        raise ValueError('actual-divider controlled high-phase proof required')
    candidates={name:digest for name,digest in p['input_sha256'].items() if name.endswith('/assessment.json') and 'candidate' in name}
    if len(candidates)!=1 or any(b['input_sha256'].get(name)!=digest for name,digest in candidates.items()):raise ValueError('phase proof/candidate lineage mismatch')
    lineage={name:digest for name,digest in i['input_sha256'].items() if name.endswith('/assessment.json') and 'equivalence' in name}
    if len(lineage)!=1 or any(b['input_sha256'].get(name)!=digest for name,digest in lineage.items()):raise ValueError('routed inventory/screen lineage mismatch')
    routed=inventory/'routed.json';module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore'];pins=source_pins(module)
    original=baseline/'fixed_divide16/screen.tcl';sdc=baseline/'fixed_divide16/screen.sdc'
    if b['artifacts'].get(str(original))!=sha(original) or b['artifacts'].get(str(sdc))!=sha(sdc):raise ValueError('baseline Tcl/SDC changed')
    output.mkdir(parents=True,exist_ok=False);constraints=output/'enabled_phase.sdc'
    extra='\n# Analysis launch clocks: proved continuously enabled high phase only.\n'
    extra+='set decision_pins [get_pins {'+' '.join(pins)+'}]\n'
    extra+='if {[llength $decision_pins] != 2} {error "decision pin binding failed"}\n'
    extra+='set_clock_sense -stop_propagation -clock [get_clocks PLLOUT] $decision_pins\n'
    for phase in range(8):
        extra+='create_generated_clock -name DECISION_PHASE_'+str(phase)+' -source [get_ports PLLOUT] -master_clock PLLOUT -edges {'+' '.join(map(str,launch_edges(phase)))+'}'+(' -add' if phase else '')+' $decision_pins\n'
    extra+='set_clock_uncertainty 0.15 [get_clocks DECISION_PHASE_*]\n'
    constraints.write_text(sdc.read_text()+extra)
    queries='''
foreach pin $decision_pins {
 set names {}
 foreach c [all_clocks] {
  foreach q [all_registers -clock $c -clock_pins] {
   if {[get_full_name $q] == [get_full_name $pin]} {lappend names [get_full_name $c]}
  }
 }
 puts "DECISION_PHASE_PIN\t[get_full_name $pin]\t[join [lsort $names] ,]"
}
'''
    text=original.read_text()
    if text.count('source '+str(sdc))!=1 or text.count('\nexit\n')!=1:raise ValueError('unique baseline constraints and exit required')
    script=output/'screen.tcl';script.write_text(text.replace('source '+str(sdc),'source '+str(constraints)).replace('\nexit\n','\n'+queries+'\nexit\n'))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'screen.log',deadline,4)
    log=(output/'screen.log').read_text()
    if re.search(r'\[ERROR|Error:|invalid command name|STA-(1648|1650)',log):raise ValueError('conditional timing parser/binding failed')
    observed={}
    for line in log.splitlines():
        if line.startswith('DECISION_PHASE_PIN\t'):
            _,name,clocks=line.split('\t');observed[name]=clocks.split(',')
    expected={'DECISION_PHASE_'+str(k) for k in range(8)}
    if set(observed)!=set(pins) or any(set(names)!=expected for names in observed.values()):
        save(output/'clock_bindings.json',observed)
        raise ValueError('decision FF clock mask not applied exactly; original full-rate launch clock may remain')
    worst={kind:float(value) for kind,value in re.findall(r'worst slack (max|min) ([-+0-9.eE]+)',log)}
    if set(worst)!={'max','min'}:raise ValueError('timing results incomplete')
    paths=[*receipts,routed,original,sdc,script,constraints,Path(__file__).resolve(),Path(OPENROAD)]
    bound={str(f):sha(f) for f in paths};verify(bound)
    save(output/'assessment.json',dict(input_sha256=bound,artifacts={str(output/'screen.log'):sha(output/'screen.log')},
        native_model_corner=b['native_model_corner'],conditional_worst_slack_ns=worst,decision_clock_pin_bindings=observed,
        all_eight_high_phase_launch_positions_retained=True,continually_enabled_capture_and_filter_assumed=True,
        source_FF_actual_clock_pulse_width_check_covered_by_baseline_only=True,
        capture_disable_reset_and_startup_timing_covered=False,full_mode_timing_qualified=False,
        conditional_experiment_only=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','inventory','proof','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.proof.resolve(),a.output.resolve())
