"""Queue a selected-code full flat transient with all-node voltage capture."""
import argparse,fcntl,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from run_selected_corner_initial_states import full_workers
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency


def transient_deck(text,raw,fine):
    if not 8<=fine<=247:raise ValueError("fine code must stay within release headroom")
    replacements={'.dc VRESET 0 0 1':'.tran 10p 260n 0 10p','VRESET RESET_N 0 0':'VRESET RESET_N 0 PWL(0 0 5n 0 5.1n 1.8 260n 1.8)'}
    for before,after in replacements.items():
        if text.splitlines().count(before)!=1:raise ValueError('one checked DC/reset statement required')
        text=text.replace(before,after)
    lines=text.splitlines();seen=set()
    for i,line in enumerate(lines):
        fields=line.split()
        if len(fields)==4 and fields[1].startswith('STARTUP_FINE['):
            bit=int(fields[1].split('[')[1].rstrip(']'))
            if bit not in range(8) or bit in seen or fields[2]!='0':raise ValueError('unique eight-bit startup interface required')
            seen.add(bit);fields[3]='1.8' if fine&(1<<bit) else '0';lines[i]=' '.join(fields)
    if seen!=set(range(8)):raise ValueError('all eight startup fine bits required')
    ref=[i for i,line in enumerate(lines)if len(line.split())==4 and line.split()[1:]==['REFCLK','0','0']]
    if len(ref)!=1:raise ValueError('one held reference required')
    name=lines[ref[0]].split()[0];lines[ref[0]]=name+' REFCLK 0 PULSE(0 1.8 20n 100p 100p 19.9n 40n)'
    prints=[i for i,line in enumerate(lines)if line.startswith('.print dc ')]
    if len(prints)!=1:raise ValueError('one checked DC print required')
    ports=['PLLOUT','CONFIG_BUSY','CONFIG_READY','TRACKING','FAILED','RESET_N','REFCLK']+[f'COARSE_CODE[{i}]'for i in range(6)]+[f'DCO_CODE[{i}]'for i in range(8)]
    lines[prints[0]]='.print tran format=raw precision=17 file='+str(raw)+' V(*)'
    return '\n'.join(lines)+'\n',ports


def run(smoke,output,fine):
    receipt=smoke/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['normal_native_exit']or not r['finite_reset_DC_point']:raise ValueError('completed checked DC reference required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{20});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));raw=output/'transient.raw';deck=output/'transient.spice';text,ports=transient_deck((smoke/'smoke.spice').read_text(),raw,fine);deck.write_text(text)
    folder=Path(__file__).resolve().parent;binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';pins={**r['input_sha256'],**{str(p):sha(p)for p in [receipt,deck,binary,Path(__file__).resolve(),folder/'run_selected_corner_initial_states.py',folder/'assess_selected_detector_phase_probe_v2.py',folder/'assess_selected_isolated_control.py',folder/'compiled_charge_v2.py']}}
    verify(pins);save(output/'inputs.json',dict(input_sha256=pins,coarse=20,fine=fine,all_node_voltages_requested=True,corner='tt',temperature_C=27,supply_V=1.8,PLL_ENABLE_held_low=True,reset_release_ns=5,simulation_ns=260,max_step_ps=10,CPU=20,memory_GiB=16,queue_cap_s=172800,native_cap_s=86400,max_native_cases=1,automatic_identical_retry=False,distributed_wire_R_included=False,release_ready=False))
    try:
        lockpath=ROOT/'build/signoff400/resources/selected_full_native_slot.lock';lockpath.parent.mkdir(parents=True,exist_ok=True);queue_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
        with lockpath.open('a+')as lock:
            while True:
                save(output/'status.json',dict(state='waiting_for_full_native_slot',release_ready=False))
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('full-native queue limit')
                    time.sleep(10)
            while full_workers():
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('existing full-native worker limit')
                time.sleep(10)
            verify(pins);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400;start=time.monotonic();save(output/'status.json',dict(state='flat_native_programming_transient_running',release_ready=False))
            with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows=read_selected(raw,{p:p for p in ports},260e-9);window=[row for row in rows if row[0]>=200e-9];codes={};ambiguous=False
        for prefix,width in [('COARSE_CODE',6),('DCO_CODE',8)]:
            observed=set()
            for row in window:
                value=0
                for i in range(width):
                    v=row[1+ports.index(f'{prefix}[{i}]')];ambiguous|=.36<v<1.44
                    if v>=.9:value|=1<<i
                observed.add(value)
            codes[prefix]=sorted(observed)
        stationary=codes=={'COARSE_CODE':[20],'DCO_CODE':[fine]}and not ambiguous
        measured=None;frequency_reason=None
        if stationary:
            try:measured=frequency(rows,200,260)
            except ValueError as e:frequency_reason=str(e)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [deck,raw,output/'native.log']},normal_native_completion=True,all_saved_native_values_finite=True,all_node_voltages_requested=True,requested_fine=fine,elapsed_s=time.monotonic()-start,window_ns=[200,260],codes=codes,ambiguous_code_voltage=ambiguous,stationary_requested_code=stationary,frequency_diagnostic=measured,frequency_unavailable_reason=frequency_reason,distributed_wire_R_included=False,transient_correlation_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='flat_native_programming_transient_complete',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fine',type=int,required=True);a=p.parse_args();run(a.smoke.resolve(),a.output.resolve(),a.fine)
