#!/usr/bin/env python3
"""Validate/benchmark the compiled P1 charge candidate on observed operators.

Times are for selected local matrices, not full RC attachment or PLL simulation.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from common import ROOT,save,sha,verify
from resources import lease
from check_native_sheet_charge import build as reference_basis,integrate
from compiled_sheet_charge import build,invoke,decode,encode_reference

def run(samples,geometry,contours,reference_control,output):
    samples,geometry,contours,reference_control,out=(Path(p).resolve() for p in (samples,geometry,contours,reference_control,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,max_cpu_slots=32,memory_limit_GiB=8))
    def status(state,**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,release_qualified=False,**extra))
    try:
        with lease(2,8,deadline):
            status('validating_observed_operator_and_reference_receipts');s=json.loads((samples/'assessment.json').read_text());g=json.loads((geometry/'assessment.json').read_text());c=json.loads((contours/'assessment.json').read_text());r=json.loads((reference_control/'assessment.json').read_text())
            if not r['selected_signed_energy_and_charge_controls_passed'] or len({p['shared_geometry_sha256'] for p in (s,g,c,r)})!=1:raise ValueError('compiled sheet controls do not share a passing same-GDS reference')
            verify(r['input_sha256']);verify(r['artifacts']);path=samples/'native/cases.jsonl';polygons=contours/'polygons.jsonl';pins={str(path):s['artifacts'][str(path)],str(polygons):c['artifacts'][str(polygons)]}
            sources=['compiled_sheet_charge.py','check_native_sheet_charge.py','floating_sheet_basis.py','floating_sheet_charge.py','floating_sheet_fringe.py','common.py','compiled_charge.py','resources.py']
            for p in [Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in sources],samples/'assessment.json',geometry/'assessment.json',contours/'assessment.json',reference_control/'assessment.json']:pins[str(p)]=sha(p)
            verify(pins);rows=[json.loads(line) for line in path.read_text().splitlines()];contour_map={x['original_conductor']:x for x in map(json.loads,polygons.read_text().splitlines())};scales={t:x['integer_coordinate_scale'] for t,x in g['per_native_type'].items()}
            if len(rows)!=s['selected_cases']:raise ValueError('selected case count differs')
            status('preparing_exact_and_high_precision_matrix_references');prepared=[];expected={};reference_start=time.clock_gettime(time.CLOCK_BOOTTIME)
            for row in rows:
                for refinement in (1,2,4):
                    source,sp,_=reference_basis(row['source'],refinement,scales,contour_map);target,tp,_=reference_basis(row['target'],refinement,scales,contour_map);name=str(row['operator_byte_offset'])+':'+str(refinement)
                    prepared.append(dict(id=name,operator=row['operator'],source_basis=encode_reference(source,sp),target_basis=encode_reference(target,tp)))
                    expected[name]=integrate(row['operator'],source,target)
            reference_seconds=time.clock_gettime(time.CLOCK_BOOTTIME)-reference_start;save(out/'prepared_cases.json',prepared);binary=build(out/'build',deadline);bp=json.loads((out/'build/build.json').read_text());pins.update(bp['input_sha256']);pins.update(bp['artifacts']);save(out/'input_manifest.json',dict(input_sha256=pins));status('comparing_every_compiled_local_matrix_entry')
            matrices,comparison=invoke(binary,prepared,out/'comparison',threads=1,deadline=deadline);maximum_error=0.;exact_cases=0;fringe_cases=0
            for item in matrices:
                reference=expected[item['id']]
                if 'exact_matrix' in item:
                    if decode(item,exact=True)!=reference:raise ValueError('compiled uniform rational matrix differs')
                    exact_cases+=1
                else:
                    actual=decode(item);norm=max([abs(v) for v in reference.values()]+[0.]);error=max([abs(actual.get(k,0)-reference.get(k,0)) for k in set(actual)|set(reference)]+[0.])
                    if error>2e-12*norm:raise ValueError('compiled fringe exceeds high-precision comparison criterion')
                    maximum_error=max(maximum_error,error/max(norm,1e-300));fringe_cases+=1
            if len(matrices)!=len(prepared):raise ValueError('compiled matrix output count differs')
        # Independent cases share no arithmetic reduction. Repetition measures
        # only selected local integration throughput, not changing layouts or solves.
        expanded=[dict(case,id=case['id']+':replica'+str(i)) for i in range(8) for case in prepared];timings=[]
        for threads in (1,4,8,16,32):
            status('benchmarking_compiled_independent_local_matrices',threads=threads)
            with lease(threads,8,deadline):
                _,timing=invoke(binary,expanded,out/('threads_'+str(threads)),threads=threads,repeat=4,emit_exact=False,deadline=deadline)
                timing['cases_per_second']=timing['integrated_cases']/timing['elapsed_s'];timings.append(timing)
        verify(pins);selected=max(timings,key=lambda x:x['cases_per_second']);result=dict(input_sha256=pins,reference_matrix_seconds=reference_seconds,comparison_native_seconds=comparison['elapsed_s'],base_observed_operators=len(rows),matrix_cases=len(prepared),exact_rational_area_line_cases=exact_cases,high_precision_fringe_cases=fringe_cases,maximum_fringe_relative_matrix_error=maximum_error,timings=timings,best_observed_threads=selected['threads'],selected_local_matrix_comparisons_passed=True,repeated_local_workload_only=True,whole_extraction_or_PLL_speedup_measured=False,full_layout_attachment_qualified=False,unlocated_arithmetic_attachment_qualified=False,global_passivity_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,shared_geometry_sha256=s['shared_geometry_sha256'],elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
        artifacts=[out/'prepared_cases.json',out/'build/build.json',out/'comparison/matrices.jsonl',out/'comparison/native.log',*[out/('threads_'+str(n))/'native.log' for n in (1,4,8,16,32)]];result['artifacts']={str(p):sha(p) for p in artifacts};save(out/'assessment.json',result);status('compiled_sheet_candidate_controls_complete_pending_full_layout');return result
    except BaseException as error:status('failed',reason=repr(error));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('samples','geometry','contours','reference-control','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.samples,a.geometry,a.contours,a.reference_control,a.output);print(json.dumps({k:r[k] for k in ('matrix_cases','maximum_fringe_relative_matrix_error','best_observed_threads','elapsed_s')}))
