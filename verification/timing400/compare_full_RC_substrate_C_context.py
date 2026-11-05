#!/usr/bin/env python3
"""Compare nominal C exports independently of IDs, order and terminal direction.

Use exact Decimal values and external sorting of all positive C records. Equal
sorted multisets prove the parsed capacitor matrix is unchanged; inequality
remains unproven equivalence, not an inferred physical failure. Keep floating
nodes explicit. Reuse the original CAD deadline, no native extraction/retry.
"""
from datetime import datetime,timezone
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from audit_parent_capacitance_network import decimal_value
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def canonical(line):
    f=line.split();assert f[0].startswith('C') and len(f)>=4
    value=decimal_value(f[3]);assert value>0
    return '\t'.join([*sorted(f[1:3]),str(value.normalize())])+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corner',required=True,choices=['min','nom','max']);args=parser.parse_args()
    base=ROOT/'build/timing400/release_001'
    owner_path=base/'poly_metal_full_RC_substrate_capacitance_001'/args.corner/'owner.json'
    deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    previous=base/'DCO_RC_substrate_C_equivalence_001/assessment.json'
    report=verify(previous);assert report['installed_RC_and_opt_in_C_only_exact_C_and_devices_identical']
    old=(base/'nominal_wrapper_capacitance_collection_001/positive' if args.corner=='nom' else base/'poly_metal_full_capacitance_corner_collection_002'/args.corner/'positive')
    inputs={'C_only':old,'RC_substrate':base/'RC_substrate_capacitance_collection_002'/args.corner/'positive'}
    collector=base/'RC_substrate_capacitance_collection_002'/args.corner
    waitout=base/'RC_substrate_C_context_matrix_comparison_001'/args.corner
    waitout.mkdir(parents=True,exist_ok=False)
    save(waitout/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    from collect_full_capacitance_corners_v2 import live
    while not (collector/'assessment.json').exists():
        state=json.loads((collector/'status.json').read_text())
        if deadline<=time.clock_gettime(time.CLOCK_BOOTTIME):
            save(waitout/'status.json',dict(state='timeout_inconclusive_waiting_for_existing_assessment',release_qualified=False));return
        owner=json.loads((collector/'owner.json').read_text())
        if not live(owner['runner_pid'],'collect_full_layout_RC_substrate_capacitance_v2.py'):
            save(waitout/'status.json',dict(state='predecessor_stopped_without_pass',predecessor_state=state,release_qualified=False));return
        save(waitout/'status.json',dict(state='waiting_for_existing_network_assessment',verified_collector_live=True,release_qualified=False))
        time.sleep(min(15,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    sort=Path(shutil.which('sort'));assert sort.is_file()
    out=waitout
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),sort,previous,owner_path]
    for name,directory in inputs.items():
        receipt=verify(directory/'assessment.json');assert receipt['no_nonzero_capacitor_values_changed']
        paths += [directory/'assessment.json',directory/'capacitance_positive.spice']
    pins={str(p):sha(p) for p in paths};save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def left():
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('original CAD deadline expired')
        return remaining
    def status(state,**kw):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
        remaining_budget_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,native_analog_jobs_added=0,**kw))
    # Actual record controls exercise semantic reorder/endpoint/ID invariance.
    sample=[]
    with (inputs['C_only']/'capacitance_positive.spice').open() as stream:
        for line in stream:
            if line.startswith('C'):sample.append(line)
            if len(sample)==100:break
    transformed=[]
    for index,line in enumerate(reversed(sample)):
        f=line.split();transformed.append(f'Cchanged{index} {f[2]} {f[1]} {f[3]}\n')
    expected=sorted(map(canonical,sample));assert sorted(map(canonical,transformed))==expected
    assert sorted(map(canonical,transformed[:-1]))!=expected
    counts={};hashes={}
    try:
        for name,directory in inputs.items():
            canonical_path=out/f'{name}.canonical';count=0
            status('canonicalizing_positive_C',dataset=name,completed_records=0)
            with (directory/'capacitance_positive.spice').open() as incoming,canonical_path.open('x') as target:
                for line in incoming:
                    if not line.startswith('C'):continue
                    target.write(canonical(line));count+=1
                    if count%1000000==0:left();status('canonicalizing_positive_C',dataset=name,completed_records=count)
            expected_count=json.loads((directory/'assessment.json').read_text())['retained_positive_capacitors']
            assert count==expected_count;counts[name]=count
            sorted_path=out/f'{name}.sorted'
            command=[str(sort),'--parallel=2','-S','1G','-T',str(out),'-o',str(sorted_path),str(canonical_path)]
            with (out/f'{name}.sort.log').open('x') as log:
                child=subprocess.Popen(command,env=dict(os.environ,LC_ALL='C'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                status('sorting_canonical_C',dataset=name,sort_pid=child.pid)
                try:code=child.wait(timeout=left())
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                    raise TimeoutError('sort exhausted original CAD deadline')
                assert code==0
            h=hashlib.sha256()
            with sorted_path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block);left()
            hashes[name]=h.hexdigest()
        for p,d in pins.items():assert sha(p)==d,p
        same=counts['C_only']==counts['RC_substrate'] and hashes['C_only']==hashes['RC_substrate']
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['owner.json','status.json']},
            counts=counts,canonical_multiset_sha256=hashes,
            exact_positive_capacitor_multisets_preserved=same,
            exact_parsed_C_matrix_equivalence_proven=same,
            C_ID_order_and_terminal_direction_ignored_only=True,values_normalized_with_exact_Decimal=True,
            original_positive_C_and_floating_nodes_preserved=True,
            reorder_ID_endpoint_positive_control_passed=True,missing_actual_C_negative_control_rejected=True,
            native_device_names_still_require_three_corner_match=True,
            full_RC_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
        status('canonical_C_comparison_terminal',exact_C_multisets_preserved=same)
        print('RC-substrate context C comparison:',args.corner,same,counts)
    except TimeoutError:
        status('timeout_inconclusive');return


if __name__=='__main__':main()
