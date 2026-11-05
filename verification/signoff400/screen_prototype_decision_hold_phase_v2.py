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
    bits=module['netnames']['core.gen_registered_decision.decision_q']['bits']
    target=[]
    for bit in bits:
        matches=[n.lstrip('\\')+'/D' for n,c in module['cells'].items() if c['connections'].get('Q')==[bit] and c['type']=='sky130_fd_sc_hs__dfrtp_1']
        if len(matches)!=1:raise ValueError('unique decision capture FF required')
        target.extend(matches)
    launch=[name.rsplit('/',1)[0]+'/Q' for name in pins]
    extra='\n# Conditional enabled-phase check: source updates absent at the capture edge.\n'
    extra+='set decision_launch [get_pins {'+' '.join(launch)+'}]\n'
    extra+='set decision_capture [get_pins {'+' '.join(target)+'}]\n'
    extra+='if {[llength $decision_launch] != 2 || [llength $decision_capture] != 2} {error "decision state pin binding failed"}\n'
    extra+='set_multicycle_path -hold -start 2 -from $decision_launch -to $decision_capture\n'
    constraints.write_text(sdc.read_text()+extra)
    queries='''
puts "CONDITIONAL_DECISION_PATHS_BEGIN"
report_checks -from $decision_launch -to $decision_capture -path_delay min_max -group_path_count 20 -digits 6
puts "CONDITIONAL_DECISION_PATHS_END"
'''
    text=original.read_text()
    if text.count('source '+str(sdc))!=1 or text.count('\nexit\n')!=1:raise ValueError('unique baseline constraints and exit required')
    script=output/'screen.tcl';script.write_text(text.replace('source '+str(sdc),'source '+str(constraints)).replace('\nexit\n','\n'+queries+'\nexit\n'))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'screen.log',deadline,4)
    log=(output/'screen.log').read_text()
    if re.search(r'\[ERROR|Error:|invalid command name|STA-(1648|1650)',log):raise ValueError('conditional timing parser/binding failed')
    checked=log.split('CONDITIONAL_DECISION_PATHS_BEGIN',1)[1].split('CONDITIONAL_DECISION_PATHS_END',1)[0]
    minimum=[block for block in checked.split('Startpoint: ')[1:] if 'Path Type: min' in block]
    if not minimum:raise ValueError('conditional decision hold paths absent')
    for block in minimum:
        launch_time=re.search(r'([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+clock PLLOUT \(rise edge\)',block)
        capture_time=re.search(r'([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+clock FINECLK[^\n]*\(rise edge\)',block)
        latency=re.search(r'([-+0-9.eE]+)\s+[-+0-9.eE]+\s+clock network delay \(propagated\)',block)
        if not launch_time or not capture_time or not latency:raise ValueError('conditional clock edge/latency evidence absent')
        if abs(float(launch_time[2])-float(capture_time[2])-2)>1e-5 or float(latency[1])<=0:
            raise ValueError('hold shift is not one later physical 2ns launch with preserved clock latency')
    worst={kind:float(value) for kind,value in re.findall(r'worst slack (max|min) ([-+0-9.eE]+)',log)}
    if set(worst)!={'max','min'}:raise ValueError('timing results incomplete')
    paths=[*receipts,routed,original,sdc,script,constraints,Path(__file__).resolve(),Path(OPENROAD)]
    bound={str(f):sha(f) for f in paths};verify(bound)
    save(output/'assessment.json',dict(input_sha256=bound,artifacts={str(output/'screen.log'):sha(output/'screen.log')},
        native_model_corner=b['native_model_corner'],conditional_worst_slack_ns=worst,decision_launch_pins=launch,decision_capture_pins=target,
        conditional_source_hold_shift_cycles=1,SDC_hold_start_multiplier=2,physical_launch_clock_latency_retained=True,
        all_setup_checks_retained=True,continually_enabled_capture_and_filter_assumed=True,
        source_FF_actual_clock_pulse_width_checks_retained=True,
        capture_disable_reset_and_startup_timing_covered=False,full_mode_timing_qualified=False,
        conditional_experiment_only=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','inventory','proof','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.proof.resolve(),a.output.resolve())
