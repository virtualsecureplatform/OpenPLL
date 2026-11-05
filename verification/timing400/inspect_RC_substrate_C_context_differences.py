#!/usr/bin/env python3
"""Measure exact matrix differences between completed sorted capacitor multisets.

Use streaming comm outputs, then aggregate by unordered endpoint pair with exact
Decimal values. Common records cancel exactly; differences preserve all weights
and floating node names. Report self-connected capacitors separately because
C*(Va-Vb)^2 is identically zero for identical node names. No physical model
qualification is inferred from matching counts or small changes.
"""
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import argparse,hashlib,itertools,json,os,shutil,signal,subprocess,time
from pathlib import Path
from collect_full_capacitance_corners_v2 import live
from check_bbpd_repair_identity import design
from run_dco_qualification import ROOT,sha,save


def sha_stream(path,deadline):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError()
    return h.hexdigest()


def groups(path):
    with path.open() as stream:
        def records():
            for line in stream:
                f=line.rstrip('\n').split('\t');assert len(f)==3
                yield (f[0],f[1]),Decimal(f[2])
        for key,rows in itertools.groupby(records(),lambda r:r[0]):yield key,sum((r[1] for r in rows),Decimal(0))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--corner',required=True,choices=['min','nom','max']);args=parser.parse_args()
    base=ROOT/'build/timing400/release_001';source=base/'RC_substrate_C_context_matrix_comparison_001'/args.corner
    owner_path=source/'owner.json';owner=json.loads(owner_path.read_text());deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'RC_substrate_C_context_matrix_difference_001'/args.corner;out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),original_owner=str(owner_path),
        deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    def status(state,**kwargs):save(out/'status.json',dict(state=state,corner=args.corner,observed_utc=datetime.now(timezone.utc).isoformat(),
        remaining_budget_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,**kwargs))
    children=[]
    try:
        receipt_path=source/'assessment.json'
        while not receipt_path.exists():
            if deadline<=time.clock_gettime(time.CLOCK_BOOTTIME):raise TimeoutError()
            if not live(owner['runner_pid'],'compare_full_RC_substrate_C_context.py'):status('predecessor_stopped_without_completion');return
            status('waiting_for_existing_sorted_comparison',verified_predecessor_live=True)
            time.sleep(min(15,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        receipt=json.loads(receipt_path.read_text());before=source/'C_only.sorted';after=source/'RC_substrate.sorted'
        for path in [before,after]:assert sha_stream(path,deadline)==receipt['artifacts'][str(path)]
        comm=Path(shutil.which('comm'));assert comm.is_file()
        paths=[Path(__file__).resolve(),receipt_path,owner_path,before,after,comm,base/'parent_dco_antenna_targeted_011/route.def']
        outputs={}
        for name,flags in [('old_only','-23'),('new_only','-13')]:
            target=out/(name+'.sorted');outputs[name]=target
            with target.open('x') as stdout,(out/(name+'.comm.log')).open('x') as stderr:
                child=subprocess.Popen([str(comm),flags,str(before),str(after)],stdout=stdout,stderr=stderr,
                    env=dict(os.environ,LC_ALL='C'),start_new_session=True);children.append(child)
        status('streaming_multiset_differences',child_pids=[p.pid for p in children])
        for child in children:assert child.wait(timeout=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))==0
        _,_,netlist=design(base/'parent_dco_antenna_targeted_011/route.def');parents=set(netlist);assert len(parents)==359
        left=iter(groups(outputs['old_only']));right=iter(groups(outputs['new_only']))
        a,b=next(left,None),next(right,None);count=energy_count=self_count=0;maximum=Decimal(0);absolute=Decimal(0);parent_delta=defaultdict(Decimal);examples=[]
        status('aggregating_exact_pair_deltas')
        with (out/'pair_differences.jsonl').open('x') as stream:
            while a is not None or b is not None:
                if count%100000==0 and deadline<=time.clock_gettime(time.CLOCK_BOOTTIME):raise TimeoutError()
                if b is None or a is not None and a[0]<b[0]:key,old=a;new=Decimal(0);a=next(left,None)
                elif a is None or b[0]<a[0]:key,new=b;old=Decimal(0);b=next(right,None)
                else:key,old=a;new=b[1];a,b=next(left,None),next(right,None)
                delta=new-old
                if delta==0:continue
                count+=1;self_branch=key[0]==key[1]
                if self_branch:self_count+=1
                else:
                    energy_count+=1;maximum=max(maximum,abs(delta));absolute+=abs(delta)
                    for node in key:
                        if node in parents:parent_delta[node]+=delta
                row=dict(nodes=list(key),C_only_unmatched_sum_ff=str(old*Decimal('1e15')),
                    RC_substrate_unmatched_sum_ff=str(new*Decimal('1e15')),delta_ff=str(delta*Decimal('1e15')),zero_energy_self_branch=self_branch)
                stream.write(json.dumps(row)+'\n')
                if len(examples)<20:examples.append(row)
        save(out/'parent_diagonal_deltas.json',{k:str(v*Decimal('1e15')) for k,v in sorted(parent_delta.items())})
        summary=dict(changed_capacitor_pair_sums=count,changed_nonself_energy_pairs=energy_count,changed_zero_energy_self_pairs=self_count,
            maximum_nonself_pair_delta_ff=str(maximum*Decimal('1e15')),sum_absolute_nonself_pair_deltas_ff=str(absolute*Decimal('1e15')),
            exact_parsed_nonself_C_matrix_equivalent=energy_count==0,examples=examples)
        save(out/'summary.json',summary)
        pins={str(p):sha_stream(p,deadline) for p in paths}
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha_stream(p,deadline) for p in out.iterdir() if p.is_file() and p.name not in ['owner.json','status.json']},
            **summary,common_records_cancelled_exactly=True,unmatched_sum_fields_are_not_complete_original_capacitances=True,
            parent_diagonal_changes_are_not_effective_input_loads=True,physical_RC_or_transient_enclosure_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
        status('exact_matrix_difference_terminal',changed_nonself_energy_pairs=energy_count)
        print('RC-substrate C matrix difference:',args.corner,{k:v for k,v in summary.items() if k!='examples'})
    except (TimeoutError,subprocess.TimeoutExpired):
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        status('timeout_inconclusive')


if __name__=='__main__':main()
