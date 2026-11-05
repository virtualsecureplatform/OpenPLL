"""Bounded 21ns transient control of the selected recorded-boundary partition.

The transient exercises reset and first-reference-edge behavior.
It does not validate oscillation, boundary assumptions, or tuning behavior.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from analyze_xyce_runtime import analyze


def run(bench,replay,output):
    output.mkdir(parents=True,exist_ok=False)
    owner=json.loads((replay/'owner.json').read_text());wait_end=time.clock_gettime(time.CLOCK_BOOTTIME)+3700
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_boundary_files',release_ready=False))
    while True:
        state=json.loads((replay/'status.json').read_text())['state']
        if state in ['boundary_replay_files_complete','bounded_prefix_files_complete','exact_compacted_replay_complete']:break
        if state=='stopped_without_qualification':raise RuntimeError('boundary generation failed')
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('boundary generator exited without completed receipt')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>wait_end:raise TimeoutError('boundary-file wait exhausted')
        time.sleep(10)
    r=json.loads((replay/'assessment.json').read_text());a=json.loads((bench/'assessment.json').read_text())
    verify(r['input_sha256']);verify(r['artifacts']);verify(a['artifacts'])
    if not (r.get('exact_saved_knots_replayed') or r.get('exact_replay_valid_through_s',0)>=21e-9) or r['boundary_files']!=a['required_boundary_files']:raise ValueError('complete exact replay required')
    deck=output/'control.spice';raw=output/'control.raw';binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
    deck.write_text(f'''Selected conditional parser/DC control; diagnostic only
.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" tt
.include "{bench}/devices.spice"
.include "{bench}/boundary_sources.spice"
Vpower VPWR 0 1.8
Vbody VPB 0 1.8
Vground VGND 0 0
Vnb VNB 0 0
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 10p 21n 0 10p
.print tran format=raw file={raw} v(PLLOUT) v(CLKDIV_RETIMED) v(CONFIG_READY) v(CONFIG_BUSY) v(FAILED) v(TRACKING) v(COARSE_CODE[0]) v(COARSE_CODE[1]) v(COARSE_CODE[2]) v(COARSE_CODE[3]) v(COARSE_CODE[4]) v(COARSE_CODE[5]) v(DCO_CODE[0]) v(DCO_CODE[1]) v(DCO_CODE[2]) v(DCO_CODE[3]) v(DCO_CODE[4]) v(DCO_CODE[5]) v(DCO_CODE[6]) v(DCO_CODE[7]) v(DLF_CODE[0]) v(DLF_CODE[1]) v(DLF_CODE[2]) v(DLF_CODE[3]) v(DLF_CODE[4]) v(DLF_CODE[5]) v(DLF_CODE[6]) v(DLF_CODE[7]) v(DLF_CODE[8]) v(DLF_CODE[9]) v(__parent_R_node_617)
.end
''')
    pins={str(p):sha(p) for p in [deck,binary,replay/'assessment.json',bench/'assessment.json',Path(__file__).resolve()]};pins.update(a['artifacts']);pins.update(r['artifacts'])
    save(output/'manifest.json',dict(input_sha256=pins,CPU=25,memory_GiB=48,native_cap_s=3600,diagnostic=True,release_ready=False))
    os.sched_setaffinity(0,{25});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    try:
        with lease(1,48,deadline):
            save(output/'status.json',dict(state='conditional_native_21ns_transient_running',release_ready=False))
            execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,48)
        verify(pins);save(output/'timing.json',analyze(output/'native.log'))
        if not raw.exists():raise ValueError('native waveform missing')
        save(output/'status.json',dict(state='conditional_21ns_completed_comparison_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['bench','replay','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.bench.resolve(),a.replay.resolve(),a.output.resolve())
