"""Validate exact record ownership and byte-chunked actual-operator projection."""
import argparse,json,os,time,subprocess
from decimal import Decimal,localcontext
from pathlib import Path
from common import save,sha
from resources import lease,identity
from compiled_charge import execute


def run(out, threads):
    if threads not in (2,16):raise ValueError('controlled two- or sixteen-thread execution required')
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400';reference=base/'startup_timing_stream_projection_controls_001';receipt=reference/'assessment.json';a=json.loads(receipt.read_text());cfg_path=reference/'stream.config.json';cfg=json.loads(cfg_path.read_text());source=root/'tools/sheet_charge';merger=base/'sparse_merger_v2_build_001/merge_sparse_runs_v2';merger_proof=merger.parent/'assessment.json'
    paths=[receipt,cfg_path,reference/'operators.jsonl',reference/'field_map.json',reference/'merged.jsonl',reference/'native/R_nodes.jsonl',reference/'native/floating_nodes.jsonl',merger,merger_proof,source/'stream_project_charge_v2.cpp',source/'bounded_jsonl_range.hpp',source/'check_jsonl_ranges.cpp',source/'check_omp_thread_limit_v2.cpp',source/'sparse_runs_v2.hpp',Path(__file__).resolve(),*[Path(p) for p in a['input_sha256']]]
    paths=list(dict.fromkeys(paths));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,build_cpu_slots=1,projection_cpu_slots=threads,OMP_THREAD_LIMIT=threads,memory_GiB=16,automatic_identical_retry=False,full_native_projection_started=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_one_build_CPU_slot')
    try:
        with lease(1,16,deadline):
            pins={str(p):sha(p) for p in paths}
            for p,h in a['input_sha256'].items():
                if pins[p]!=h:raise ValueError('controlled geometry input changed')
            for p in (cfg_path,reference/'merged.jsonl',reference/'operators.jsonl',reference/'field_map.json'):
                if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('controlled stream artifact changed')
            binaries={}
            for name in ('check_jsonl_ranges','stream_project_charge_v2','check_omp_thread_limit_v2'):
                binary=out/name;binaries[name]=binary;execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',source/(name+'.cpp'),'-lgmpxx','-lgmp','-o',binary],out/(name+'.build.log'),deadline,16)
            fixtures=out/'range_fixtures';fixtures.mkdir();execute([binaries['check_jsonl_ranges'],fixtures],out/'range_controls.log',deadline,1);range_result=json.loads((out/'range_controls.log').read_text());save(out/'range_controls.json',dict(results=range_result,source_sha256={str(p):pins[str(p)] for p in (source/'bounded_jsonl_range.hpp',source/'check_jsonl_ranges.cpp')},range_ownership_controls_pass=True,release_qualified=False))
        status('waiting_for_reserved_projection_CPU_slots',cpu_slots=threads,exhaustive_range_trials=range_result['exhaustive_range_ownership_trials'])
        with lease(threads,16,deadline):
            execute(['env','OMP_THREAD_LIMIT='+str(threads),binaries['check_omp_thread_limit_v2'],str(threads)],out/'thread_limit.log',deadline,1)
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('inputs changed while waiting for capacity')
            operator_path=reference/'operators.jsonl';size=operator_path.stat().st_size;tasks=[dict(operators=str(operator_path),field_map=str(reference/'field_map.json'),begin_byte=size*i//17,end_byte=size*(i+1)//17) for i in range(17)]
            cfg.update(shards=tasks,threads=threads,output=str(out/'native'),deadline_uptime=deadline);cfg['geometry']['deadline_uptime']=deadline
            for label,change in [('gap',1),('overlap',-1)]:
                bad=json.loads(json.dumps(cfg));bad['shards'][1]['begin_byte']+=change;bad['output']=str(out/('invalid_'+label));path=out/(label+'.json');save(path,bad)
                try:execute(['env','OMP_THREAD_LIMIT='+str(threads),binaries['stream_project_charge_v2'],path],out/(label+'.log'),deadline,16)
                except RuntimeError:
                    if 'disjoint gap-free operator byte partition' not in (out/(label+'.log')).read_text():raise
                else:raise ValueError('invalid partition accepted')
            path=out/'chunked.config.json';save(path,cfg);status('projecting_97_actual_operators_in_17_byte_ranges');execute(['env','OMP_THREAD_LIMIT='+str(threads),binaries['stream_project_charge_v2'],path],out/'projection.log',deadline,16)
            summary=json.loads((out/'projection.log').read_text());runs=sorted((out/'native').glob('shard_*_run_*.bin'));merge=out/'merge.json';save(merge,dict(inputs=list(map(str,runs)),output=str(out/'merged.bin'),json_output=str(out/'merged.jsonl'),deadline_uptime=deadline));execute([merger,merge],out/'merge.log',deadline,16)
            def rows(path):
                result={}
                for line in path.read_text().splitlines():
                    i,j,value,absolute,terms=json.loads(line);key=(i,j)
                    if key in result:raise ValueError('duplicate matrix key')
                    result[key]=(Decimal(value),Decimal(absolute),terms)
                return result
            with localcontext() as ctx:
                ctx.prec=90;old,new=rows(reference/'merged.jsonl'),rows(out/'merged.jsonl')
                if set(old)!=set(new) or any(old[k][2]!=new[k][2] for k in old):raise ValueError('exact per-entry contribution inventory differs')
                norm=max([abs(v[0]) for v in old.values()]+[Decimal(0)]);error=max([abs(old[k][0]-new[k][0]) for k in old]+[Decimal(0)]);ratio=error/norm if norm else error
                if ratio>Decimal('1e-14'):raise ValueError('chunked matrix differs from controlled oracle')
            for name in ('R_nodes.jsonl','floating_nodes.jsonl'):
                if sha(out/'native'/name)!=pins[str(reference/'native'/name)]:raise ValueError('node namespace changed')
            if summary['operators']!=a['operators'] or not summary['disjoint_gap_free_byte_partitions_validated']:raise ValueError('exact complete operator coverage')
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('chunked projection source changed')
            artifacts=[*binaries.values(),out/'range_controls.json',path,merge,out/'projection.log',out/'merged.bin',out/'merged.jsonl',*runs]
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},range_controls=range_result,compiled_summary=summary,byte_range_projection_controls_pass=True,whole_process_OpenMP_thread_limit=threads,geometry_loader_included_in_CPU_bound=True,gap_and_overlap_partitions_rejected=True,node_maps_identical=True,all_sparse_contribution_counts_identical=True,maximum_normalized_coefficient_difference=str(ratio),actual_operators=a['operators'],byte_range_tasks=17,threads_checked=threads,full_native_projection_started=False,physical_RC_qualified=False,release_qualified=False));status('byte_range_projection_controls_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--threads',type=int,required=True,choices=(2,16));args=p.parse_args();run(args.output.resolve(),args.threads)
