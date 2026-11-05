"""Separate native SPICE serialization from resistance-extraction C redistribution."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    scratch=Path(tempfile.mkdtemp(prefix='openpll-pre-R-SPICE-C-',dir='/tmp'))
    (output/'native').symlink_to(scratch,target_is_directory=True)
    base=Path('build/signoff400').resolve()
    parent=base/'startup_timing_native_SPICE_C_matrix_001/assessment.json'
    fold=base/'startup_timing_ideal_substrate_references_001/assessment.json'
    comparison=base/'startup_timing_native_reference_delta_001/assessment.json'
    upgrade=base/'sparse_merger_upgrade_controls_001/assessment.json'
    port=base/'startup_timing_external_port_binding_001/assessment.json'
    a,f,c,u,p=[json.loads(n.read_text()) for n in (parent,fold,comparison,upgrade,port)]
    binary=parent.parent/'compile_native_SPICE_C';merger=Path(u['merger_binary']);compare=comparison.parent/'compare_sparse_matrices'
    deck=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/pre_resistance.spice')
    names=base/'startup_timing_spatial_conductor_maps_001/native/net_names.jsonl'
    nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    retained=Path(a['matrix']);reference=Path(f['folded_matrices']['native_trace_delta'])
    paths=[parent,fold,comparison,upgrade,port,binary,merger,compare,deck,names,nodes,retained,reference,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        with lease(8,16,deadline):
            status('hashing_pre_R_native_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if not a['exact_signed_matrix_SI_and_fold_controls_1_4_8_pass']:raise ValueError('controlled native compiler required')
            for proof,path in ((a,binary),(a,retained),(c,compare),(f,reference)):
                if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('controlled artifact changed')
            for path in (names,nodes):
                if a['input_sha256'][str(path)]!=pins[str(path)]:raise ValueError('native name lineage changed')
            if f['input_sha256'][str(names)]!=pins[str(names)] or p['input_sha256'][str(deck)]!=pins[str(deck)]:raise ValueError('pre-R or ideal-basis lineage changed')
            if u['input_sha256'][str(merger)]!=pins[str(merger)]:raise ValueError('merger changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg=output/'compile.json';report=output/'compile.report.json';unknown=output/'unknown_endpoints.jsonl'
            save(cfg,dict(names=str(names),native_nodes=str(nodes),deck=str(deck),threads=8,max_accumulator_entries=500000,output=str(scratch/'runs'),deadline_uptime=deadline,report=str(report),unknown_output=str(unknown)))
            status('compiling_every_pre_R_native_SPICE_capacitor')
            execute([binary,cfg],output/'compile.log',deadline,16)
            r=json.loads(report.read_text());current=sorted((scratch/'runs').glob('*.bin'))
            if len(current)!=r['sparse_runs'] or r['ideal_conductor_nodes']!=f['ideal_native_conductor_nets']:raise ValueError('pre-R compiler coverage')
            artifacts={str(p):sha(p) for p in current};level=0
            status('reducing_pre_R_native_SPICE_C',sparse_runs=len(current))
            while len(current)>1:
                jobs=[];following=[]
                for start in range(0,len(current),16):
                    cfg=scratch/f'merge_{level}_{start}.json';result=scratch/f'merge_{level}_{start}.bin'
                    save(cfg,dict(inputs=list(map(str,current[start:start+16])),output=str(result),deadline_uptime=deadline))
                    jobs.append((cfg,scratch/f'merge_{level}_{start}.log'));following.append(result)
                with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda job:execute([merger,job[0]],job[1],deadline,2),jobs))
                for result in following:artifacts[str(result)]=sha(result)
                current=following;level+=1
            if not current:raise ValueError('empty pre-R matrix')
            matrix=current[0];reports={}
            status('comparing_EXT_trace_pre_R_and_retained_SPICE')
            for label,left,right in (('EXT_trace_to_pre_R_SPICE',reference,matrix),('pre_R_to_retained_SPICE',matrix,retained)):
                cfg=output/f'{label}.json';delta=output/f'{label}.report.json'
                save(cfg,dict(left=str(left),right=str(right),node_count=f['ideal_native_conductor_nets'],absolute_tolerance=1e-8,relative_tolerance=2e-12,require_match=False,deadline_uptime=deadline,report=str(delta)))
                execute([compare,cfg],output/f'{label}.log',deadline,8)
                reports[label]=json.loads(delta.read_text());artifacts[str(delta)]=sha(delta)
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,map(Path,pins)))!=list(pins.values()):raise ValueError('source changed during pre-R comparison')
            for path in (matrix,report,unknown):artifacts[str(path)]=sha(path)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,full_pre_R_native_SPICE_C_matrix_assembled=True,
                 matrix=str(matrix),compile_results=r,diagnostic_comparisons=reports,raw_matrix_unit_SI_farads='1e-18',
                 diagnostic_tolerances_are_not_serialization_acceptance_bounds=True,
                 full_SPICE_matrix_equivalence_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('pre_R_native_SPICE_C_diagnostics_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
