"""Validate fast preparation against the exact completed diagnostic artifacts."""
import argparse,json,os,time,copy
from pathlib import Path
from common import ROOT,save,sha
from resources import lease,identity
from compiled_charge import execute
from model_preparation_fast import model_closure,line_edits,apply_line_edits


def work(out,deadline):
    reference=ROOT/'build/signoff400/startup_timing_junction_body_network_cause_003/assessment.json';a=json.loads(reference.read_text());module=Path(__file__).with_name('model_preparation_fast.py');future=Path(__file__).with_name('probe_junction_body_network_cause_v3.py');pins={str(p):sha(p) for p in (reference,module,future,Path(__file__).resolve())};results=[]
    for patch in a['model_interventions']:
        source=Path(patch['source']);derived=Path(patch['diagnostic_path'])
        for p,h in [(source,patch['source_sha256']),(derived,patch['diagnostic_sha256'])]:
            pins[str(p)]=sha(p)
            if pins[str(p)]!=h:raise ValueError('completed model artifact changed')
        start=time.perf_counter();before,after=source.read_bytes(),derived.read_bytes();ledger=line_edits(before,after)
        if apply_line_edits(before,ledger)!=after:raise ValueError('exact actual model reconstruction')
        target=out/(source.name+'.edits.json');save(target,ledger);results.append(dict(source=str(source),derived=str(derived),edits=len(ledger['edits']),elapsed_s_nonisolated=time.perf_counter()-start,ledger=str(target),ledger_sha256=sha(target)))
    rejected=0
    for before,after in [(b'',b''),(b'a\n',b'b\n'),(b'a\r\nb\n',b'a\r\nc\n'),('é\n'.encode(),b'x\n'),(b'no-newline',b'last')]:
        record=line_edits(before,after)
        if apply_line_edits(before,record)!=after:raise ValueError('exact synthetic model edits')
    fixture=line_edits(b'a\nb\n',b'x\ny\n')
    for kind in ('wrong_source','duplicate','wrong_preimage','wrong_result','wrong_format'):
        bad=copy.deepcopy(fixture);source=b'a\nb\n'
        if kind=='wrong_source':source=b'c\nb\n'
        elif kind=='duplicate':bad['edits'].append(bad['edits'][-1])
        elif kind=='wrong_preimage':bad['edits'][0]['before']='z\n'
        elif kind=='wrong_result':bad['result_sha256']='0'*64
        else:bad['format']='unknown'
        try:apply_line_edits(source,bad)
        except ValueError:rejected+=1
        else:raise ValueError('invalid edit ledger accepted')
    model=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice');start=time.perf_counter();paths=model_closure(model,deadline);elapsed=time.perf_counter()-start
    expected={Path(n).resolve() for n in a['input_sha256'] if Path(n).suffix in ('.spice','.pm3','.mod','.lib') and not Path(n).is_relative_to(reference.parent)}
    from probe_native_junction_alias_v2 import model_closure as original_closure
    start=time.perf_counter();original=original_closure(model,deadline);original_elapsed=time.perf_counter()-start
    if paths!=original or set(paths)!=expected:raise ValueError('dependency closure differs from original scanner')
    for p in paths:
        pins[str(p)]=sha(p)
        if pins[str(p)]!=a['input_sha256'][str(p)]:raise ValueError('original native model closure changed')
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('fast preparation control inputs changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=results,all_actual_diagnostic_model_bytes_reconstructed_exactly=True,synthetic_edit_controls_pass=True,invalid_edit_controls_rejected=rejected,model_dependency_files=len(paths),dependency_closure_exactly_matches_original_scanner=True,fast_closure_elapsed_s_nonisolated=elapsed,original_closure_elapsed_s_nonisolated=original_elapsed,native_simulations_started=0,future_native_probe_rerun=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='fast_model_preparation_controls_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);producer=ROOT/'build/signoff400/startup_timing_junction_body_network_cause_003';owner=json.loads((producer/'owner.json').read_text());deadline=owner['deadline_uptime']+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_completed_exact_diagnostic_producer',release_qualified=False))
    try:
        while not (producer/'assessment.json').exists():
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=owner['deadline_uptime'] or identity(owner['pid'])!=owner['birth']:raise RuntimeError('diagnostic producer stopped without a receipt')
            time.sleep(2)
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'check.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
