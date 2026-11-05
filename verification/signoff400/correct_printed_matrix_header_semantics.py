"""Correct EXT header metadata while retaining proven unchanged matrix arithmetic."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import difflib
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease


def run(comparison,old_controls,controls,units,output):
    comparison,old_controls,controls,units,out=(p.resolve() for p in (comparison,old_controls,controls,units,output))
    out.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json' for p in (comparison,old_controls,controls,units)]
    numeric,old,new,unit=[json.loads(p.read_text()) for p in receipts]
    if not numeric['full_printed_native_matrix_reconstruction_verified'] or not new['explicit_R_C_D_header_and_two_negative_scale_controls_pass']:
        raise ValueError('complete native numeric comparison and corrected header controls required')
    if not unit['previous_distance_as_capacitance_metadata_error_corrected'] or unit['EXT_scale_field_order']!='resistance capacitance distance':
        raise ValueError('source-backed EXT R C D unit correction required')
    if numeric['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('numeric comparison/control lineage differs')
    old_source=next(Path(p) for p in old['input_sha256'] if p.endswith('/compile_printed_EXT_v2.cpp'))
    new_source=next(Path(p) for p in new['input_sha256'] if p.endswith('/compile_printed_EXT_v3.cpp'))
    oldlines,newlines=old_source.read_text().splitlines(True),new_source.read_text().splitlines(True)
    def without_header(lines):
        removed=[s for s in lines if 'else if(text.starts_with("scale "))' in s]
        if len(removed)!=1:
            raise ValueError('unique header-validation branch required')
        return [s for s in lines if s!=removed[0]]
    if without_header(oldlines)!=without_header(newlines):
        raise ValueError('parser arithmetic changed beyond the isolated header-validation branch')
    patch=out/'header_validation_only.patch'
    patch.write_text(''.join(difflib.unified_diff(oldlines,newlines,fromfile=str(old_source),tofile=str(new_source))))
    fixture_files=[f'threads_{t}/{kind}.bin' for t in (1,4,8) for kind in ('value','error')]
    fixtures=[root/name for root in (old_controls,controls) for name in fixture_files]
    ext=next(Path(p) for p in unit['input_sha256'] if p.endswith('Prototype400_FilledCapacitanceView.ext'))
    config=comparison/'compile.json'
    result=comparison/'comparison.json'
    products=[Path(numeric[key]) for key in ('printed_native_matrix','serialization_bound_matrix','explicit_zero_extension_node_map')]
    paths=[*receipts,old_source,new_source,*fixtures,ext,config,result,*products,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins=dict(zip(map(str,paths),pool.map(sha,paths)))
        for p,proof in ((old_source,old),(new_source,new)):
            if pins[str(p)]!=proof['input_sha256'][str(p)]:
                raise ValueError('controlled parser source changed')
        for name in fixture_files:
            a,b=old_controls/name,controls/name
            if pins[str(a)]!=old['artifacts'][str(a)] or pins[str(b)]!=new['artifacts'][str(b)] or pins[str(a)]!=pins[str(b)]:
                raise ValueError('corrected header changes controlled numeric output bytes')
        if pins[str(ext)]!=unit['input_sha256'][str(ext)] or pins[str(ext)]!=numeric['input_sha256'][str(ext)]:
            raise ValueError('numeric comparison/unit source differs')
        with ext.open() as stream:
            scales=next(line.split()[1:] for line in stream if line.startswith('scale '))
        if scales!=[unit[k] for k in ('native_EXT_resistance_scale','native_internal_units_per_printed_EXT_unit','native_EXT_distance_scale')]:
            raise ValueError('corrected EXT header scales differ from actual source')
        # The old branch validated argv[3] under a wrong key name. It never
        # scaled a matrix coefficient. Its actual checked value is the D field.
        if str(json.loads(config.read_text())['native_internal_units_per_printed_EXT_unit']).removesuffix('.0')!=unit['native_EXT_distance_scale']:
            raise ValueError('old parser did not validate the actual distance field')
        report=json.loads(result.read_text())
        if report!=numeric['full_comparison'] or not report['within_bounds'] or report['outside_serialization_and_numerical_bounds']!=0:
            raise ValueError('retained complete numeric proof differs')
        for p in [result,*products]:
            if pins[str(p)]!=numeric['artifacts'][str(p)]:
                raise ValueError('retained full numeric artifact changed')
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('header correction input changed during verification')
        assessment={k:numeric[k] for k in ('printed_native_matrix','serialization_bound_matrix',
             'explicit_zero_extension_node_map','complete_printed_record_counts','full_comparison','scope')}
        assessment.update(input_sha256=pins,artifacts={str(p):sha(p) for p in [patch,result,*products]},
             full_printed_native_matrix_reconstruction_verified=True,
             numeric_comparison_receipt=str(receipts[0]),numeric_math_reused_without_reexecution=True,
             EXT_scale_header_semantics_corrected=True,native_EXT_R_C_D_scales=scales,
             parser_change_is_only_stronger_header_validation=True,
             six_control_matrix_outputs_byte_identical=True,
             old_incorrect_capacitance_scale_metadata_superseded=True,
             finite_R_substrate_target_assignment_qualified=False,
             scalar_rounding_spatial_assignment_complete=False,global_passivity_qualified=False,
             physical_RC_qualified=False,release_qualified=False)
        save(out/'assessment.json',assessment)
        print(json.dumps(dict(full_native_numeric_comparison_preserved=True,EXT_R_C_D=scales)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('comparison','old-controls','controls','units','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.comparison,a.old_controls,a.controls,a.units,a.output)
