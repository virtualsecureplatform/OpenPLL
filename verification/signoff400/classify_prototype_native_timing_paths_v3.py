"""Classify reported timing samples against proved CDC stages; generate no exceptions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from common_v3 import save, sha, verify
from compare_mapped_routed_CDC import identifier


def category(endpoint,description,stages):
    if 'removal check' in description or 'recovery check' in description:return 'asynchronous_control_protocol_and_aperture'
    stage=stages.get(identifier(endpoint))
    if stage and stage['index']==0:return 'first_synchronizer_stage_data_aperture'
    if stage:return 'synchronizer_interstage_timing'
    return 'ordinary_or_interface_timing'


def run(screens,obligations,proof,output):
    op=obligations/'assessment.json';o=json.loads(op.read_text());verify(o['artifacts'])
    pr=proof/'assessment.json';p=json.loads(pr.read_text());verify(p['artifacts'])
    if not p['all_transition_and_output_functions_equivalent']:raise ValueError('proved routed logic required')
    definitions=obligations/'obligations.json';stages={}
    for chain in json.loads(definitions.read_text())['synchronizers']:
        for i,stage in enumerate(chain['stages']):
            name=identifier(stage['routed_cell'])
            if name in stages:raise ValueError('ambiguous CDC stage identity')
            stages[name]=dict(chain=chain['id'],index=i,role=chain['role'])
    pins={str(f):sha(f) for f in (op,definitions,pr,Path(__file__).resolve(),
          Path(__file__).with_name('compare_mapped_routed_CDC.py'))};corners=set();records=[];seen=set()
    for screen in screens:
        receipt=screen/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
        if r.get('conditional_experiment_only'):
            parents=[]
            for name,digest in r['input_sha256'].items():
                if not name.endswith('/assessment.json'):continue
                candidate=Path(name)
                if sha(candidate)!=digest:raise ValueError('conditional parent receipt changed')
                data=json.loads(candidate.read_text())
                if 'corner_worst_slack_ns' in data and 'native_model_corner' in data:
                    parents.append(candidate)
            if len(parents)!=1:raise ValueError('unique baseline native screen required')
            parent=json.loads(parents[0].read_text())
            if r['input_sha256'][str(parents[0])]!=sha(parents[0]) or parent['input_sha256'].get(str(pr))!=sha(pr):raise ValueError('conditional screen/proof lineage mismatch')
        elif r['input_sha256'].get(str(pr))!=sha(pr):raise ValueError('screen/proof lineage mismatch')
        corner=r['native_model_corner']
        if corner in corners:raise ValueError('duplicate native corner screen')
        corners.add(corner);log=screen/('screen.log' if r.get('conditional_experiment_only') else 'fixed_divide16/screen.log');pins[str(receipt)]=sha(receipt);pins[str(log)]=sha(log)
        for block in log.read_text().split('Startpoint: ')[1:]:
            start=block.splitlines()[0].strip();end=re.search(r'^Endpoint: ([^\n]+)',block,re.M)
            kind=re.search(r'^Path Type: (min|max)',block,re.M);group=re.search(r'^Path Group: ([^\n]+)',block,re.M)
            slack=re.search(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',block)
            if not all((end,kind,group,slack)):raise ValueError('reported native path missing fields')
            endpoint=end[1].strip();value=float(slack[1]);key=(corner,start,endpoint,group[1],kind[1],value)
            if key in seen:continue
            seen.add(key);description=block.split('Path Group:')[0]
            records.append(dict(corner=corner,startpoint=start,endpoint=endpoint,path_type=kind[1],path_group=group[1],
                 slack_ns=value,conditional_enabled_phase_experiment=bool(r.get('conditional_experiment_only')),classification=category(endpoint,description,stages),
                 destination_CDC_stage=stages.get(identifier(endpoint)),waived=False))
    if corners!={'tt','ff','ss','sf','fs'}:raise ValueError('complete five-corner report set required')
    counts=Counter(row['classification'] for row in records if row['slack_ns']<0)
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'paths.json';save(detail,records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         reported_unique_path_samples=len(records),violating_sample_counts_by_class=dict(counts),
         report_is_sampled_not_an_exhaustive_violation_inventory=True,
         conditional_enabled_phase_experiments_do_not_qualify_other_modes=True,
         CDC_first_stage_aperture_requires_protocol_and_native_resolution_evidence=True,
         all_reported_paths_retained=True,timing_exceptions_generated=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--screens',nargs=5,type=Path,required=True)
    for n in ('obligations','proof','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run([x.resolve() for x in a.screens],a.obligations.resolve(),a.proof.resolve(),a.output.resolve())
