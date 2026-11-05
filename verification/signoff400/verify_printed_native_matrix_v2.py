"""Reconstruct every printed native EXT coefficient and compare the folded trace."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
from common import save, sha
from compiled_charge import execute
from resources import lease


def run(folded, units, controls, merger_upgrade, output):
    folded, units, controls, merger_upgrade, out = (p.resolve() for p in
        (folded, units, controls, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix='openpll-printed-native-matrix-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    def status(state, **extra):
        save(out/'status.json',dict(state=state,retained_local_scratch=str(scratch),
             release_qualified=False,**extra))
    try:
        receipts = [p/'assessment.json' for p in (folded,units,controls,merger_upgrade)]
        fold,unit,control,upgrade = [json.loads(p.read_text()) for p in receipts]
        if not fold['ideal_substrate_reference_matrices_prepared'] or not unit['nonzero_printed_capacitance_unit_controls_pass']:
            raise ValueError('complete ideal references and unit binding required')
        if not control['printed_EXT_matrix_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
            raise ValueError('controlled printed parser/comparator and merger required')
        if unit['native_trace_units_per_printed_EXT_unit'] != '1' or not unit['trace_already_normalized_by_EXT_cap_scale']:
            raise ValueError('printed native trace unit identity differs')
        # Both receipts must bind the same original conductor reference and substrate audit.
        common = set(fold['input_sha256']) & set(unit['input_sha256'])
        for suffix in ('startup_timing_native_conductor_ledger_002/assessment.json',
                       'startup_timing_substrate_reference_binding_001/assessment.json'):
            matching = [p for p in common if p.endswith(suffix)]
            if len(matching)!=1 or fold['input_sha256'][matching[0]] != unit['input_sha256'][matching[0]]:
                raise ValueError('printed/unit/fold lineage differs')
        ext = next(Path(p) for p in unit['input_sha256'] if p.endswith('Prototype400_FilledCapacitanceView.ext'))
        names = folded/'ideal_net_names.jsonl'
        matrix = Path(fold['folded_matrices']['native_trace_delta'])
        if not control['zero_extension_and_three_negative_controls_pass']:
            raise ValueError('controlled explicit zero extension required')
        parser,compare = (controls/name for name in ('compile_printed_EXT_v2','compare_printed_EXT_matrix_v2'))
        merger = Path(upgrade['merger_binary'])
        expected = {str(ext):unit['input_sha256'][str(ext)],str(names):fold['artifacts'][str(names)],
                    str(matrix):fold['artifacts'][str(matrix)],str(parser):control['artifacts'][str(parser)],
                    str(compare):control['artifacts'][str(compare)],str(merger):upgrade['input_sha256'][str(merger)]}
        paths = [*receipts,*map(Path,expected),Path(__file__).resolve()]
        artifacts = {}
        with lease(8,16,deadline):
            status('hashing_printed_native_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins = dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):
                raise ValueError('printed native matrix input changed')
            cfg = out/'compile.json'
            save(cfg,dict(ext=str(ext),names=str(names),threads=8,max_accumulator_entries=1000000,
                 output=str(scratch/'runs'),deadline_uptime=deadline,
                 native_internal_units_per_printed_EXT_unit=float(unit['native_internal_units_per_printed_EXT_unit'])))
            status('compiling_every_printed_native_capacitance')
            execute([parser,cfg],out/'compile.log',deadline,16)
            summary = json.loads((out/'compile.log').read_text())
            if summary['known_conductor_nodes']!=fold['ideal_native_conductor_nets'] or not summary['zero_extension_has_no_printed_coupling_endpoints']:
                raise ValueError('complete printed node coverage differs')
            extension=scratch/'runs/zero_extension_nodes.jsonl'
            artifacts[str(extension)]=sha(extension)
            matrices = {}
            for kind in ('value','error'):
                current = sorted((scratch/'runs').glob('*.'+kind+'.bin'))
                if len(current)!=summary['paired_sparse_runs'] or not current:
                    raise ValueError('complete paired printed sparse runs required')
                artifacts.update({str(p):sha(p) for p in current})
                level = 0
                while len(current)>1:
                    next_level=[]
                    for start in range(0,len(current),128):
                        cfg=scratch/f'{kind}_{level}_{start}.json'
                        result=scratch/f'{kind}_{level}_{start}.bin'
                        save(cfg,dict(inputs=list(map(str,current[start:start+128])),
                             output=str(result),deadline_uptime=deadline))
                        status('merging_printed_native_matrix',matrix=kind,level=level,group=start)
                        execute([merger,cfg],scratch/f'{kind}_{level}_{start}.log',deadline,2)
                        artifacts[str(result)]=sha(result)
                        next_level.append(result)
                    current=next_level
                    level+=1
                matrices[kind]=current[0]
            cfg,report = out/'compare.json',out/'comparison.json'
            save(cfg,dict(actual=str(matrix),printed=str(matrices['value']),
                 serialization_bounds=str(matrices['error']),node_count=summary['conductor_nodes'],
                 absolute_tolerance=1e-8,relative_tolerance=2e-12,report=str(report),
                 require_match=True,deadline_uptime=deadline))
            status('comparing_every_native_printed_matrix_coefficient')
            execute([compare,cfg],out/'compare.log',deadline,4)
            result=json.loads(report.read_text())
            if not result['within_bounds']:
                raise ValueError('full native printed reconstruction comparison failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):
                    raise ValueError('printed comparison input changed during verification')
            artifacts.update({str(p):sha(p) for p in (report,out/'compile.log',cfg)})
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                 full_printed_native_matrix_reconstruction_verified=True,
                 printed_native_matrix=str(matrices['value']),serialization_bound_matrix=str(matrices['error']),
                 complete_printed_record_counts=summary,full_comparison=result,
                 scope='ideal original conductors with abstract reference identified with declared VGND substrate, explicitly extended by all printed zero-only nodes',
                 explicit_zero_extension_node_map=str(extension),
                 finite_R_substrate_target_assignment_qualified=False,
                 scalar_rounding_spatial_assignment_complete=False,global_passivity_qualified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('full_printed_native_matrix_reconstruction_verified')
            print(json.dumps(dict(full_printed_native_matrix_reconstruction_verified=True,
                 compared_upper_entries=result['union_upper_entries'])))
    except BaseException as error:
        status('failed',reason=repr(error))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('folded','units','controls','merger-upgrade','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    run(args.folded,args.units,args.controls,args.merger_upgrade,args.output)
