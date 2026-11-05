"""Trace all source tasks and independently enclose the two failed reference entries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as Q
import json
import os
from pathlib import Path
import struct
import tempfile
import time

from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import identity, lease
from bind_projection_namespace import bind_namespace
from test_fringe_interval import endpoint


def entry(path, key):
    """Read one stored extended-precision coefficient as an exact rational."""
    with path.open('rb') as stream:
        header=stream.read(16)
        if header[:8]!=b'SPCRUN01':raise ValueError('sparse header')
        count=struct.unpack('<Q',header[8:])[0]
        if path.stat().st_size!=16+40*count:raise ValueError('sparse matrix length')
        lower,upper=0,count
        while lower<upper:
            middle=(lower+upper)//2;stream.seek(16+40*middle);record=stream.read(40)
            found=struct.unpack('<Q',record[:8])[0]
            if found<key:lower=middle+1
            else:upper=middle
        if lower==count:return Q(0)
        stream.seek(16+40*lower);record=stream.read(40)
        if struct.unpack('<Q',record[:8])[0]!=key:return Q(0)
        significand,exponent=struct.unpack('<QH',record[8:18]);negative=exponent&0x8000;exponent&=0x7fff
        if exponent==0x7fff:raise ValueError('nonfinite stored coefficient')
        power=(exponent-16383 if exponent else 1-16383)-63
        return Q(-significand if negative else significand)*Q(2)**power if significand else Q(0)


def compare(interval, projected):
    low,high=endpoint(interval['lower_dyadic']),endpoint(interval['upper_dyadic'])
    if low>high:raise ValueError('unordered scalar enclosure')
    error=max(abs(projected-low),abs(projected-high))
    minimum_reference_magnitude=0 if low<=0<=high else min(abs(low),abs(high))
    tolerance=Q(1e-8)+Q(2e-12)*max(abs(projected),minimum_reference_magnitude)
    return dict(reference_interval_lower_exact=str(low),reference_interval_upper_exact=str(high),
                projected_coefficient_exact=str(projected),maximum_error_exact=str(error),
                minimum_coefficient_tolerance_exact=str(tolerance),
                interval_width_within_one_eighth_tolerance=high-low<=tolerance/8,
                whole_reference_interval_within_existing_tolerance=error<=tolerance)


def run(output, controls):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    scratch=Path(tempfile.mkdtemp(prefix='openpll-reference-intervals-',dir='/tmp'))
    (output/'native').symlink_to(scratch,target_is_directory=True)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=16,memory_GiB=16,automatic_identical_retry=False,retained_local_scratch=str(scratch)))
    def status(state,**extra):save(output/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        control_receipt=controls/'assessment.json';c=json.loads(control_receipt.read_text())
        if not c.get('trace_reference_interval_controls_pass'):raise ValueError('controlled scalar trace required')
        verify(c['input_sha256']);binary=controls/'trace_reference_intervals'
        if sha(binary)!=c['artifacts'][str(binary)]:raise ValueError('trace binary changed')
        base=ROOT/'build/signoff400';projection=base/'startup_timing_full_spatial_projection_002'
        p=json.loads((projection/'assessment.json').read_text());cfg=json.loads((projection/'config.json').read_text())
        if not p['spatial_operator_projection_complete'] or not p['full_operator_coverage']:
            raise ValueError('complete source projection required')
        mapping=base/'startup_timing_spatial_conductor_maps_001';map_receipt=mapping/'assessment.json'
        audit=base/'startup_timing_spatial_conductor_maps_audit_001/assessment.json'
        m,a=[json.loads(x.read_text()) for x in (map_receipt,audit)]
        if not a['all_field_and_voltage_conductor_ids_independently_checked'] or a['input_sha256'][str(map_receipt)]!=sha(map_receipt):
            raise ValueError('independently audited conductor map required')
        fieldmap=mapping/'native/field_nets.bin'
        expected={str(fieldmap):m['artifacts'][str(fieldmap)]}
        for task in cfg['shards']:
            for key in ('operators','field_map'):
                path=task[key];expected[path]=p['input_sha256'][path]
        global_fields=json.loads((mapping/'config.json').read_text())['fields']
        if m['global_fields']!=cfg['geometry']['global_fields']:
            raise ValueError('conductor map/global field count mismatch')
        compiler_receipt=Path(global_fields).parent/'assessment.json'
        compiler=json.loads(compiler_receipt.read_text())
        if (m['input_sha256'][str(compiler_receipt)]!=p['input_sha256'][str(compiler_receipt)]
                or sha(compiler_receipt)!=p['input_sha256'][str(compiler_receipt)]
                or m['input_sha256'][global_fields]!=compiler['artifacts'][global_fields]):
            raise ValueError('conductor map/global field identity mismatch')
        expected[global_fields]=compiler['artifacts'][global_fields]
        expected[str(compiler_receipt)]=p['input_sha256'][str(compiler_receipt)]
        expected.update(bind_namespace(projection,mapping))
        old=base/'startup_timing_spatial_equivalence_reconciled_001'
        old_config=old/'compare.json';comparison=json.loads(old_config.read_text())
        collapsed=Path(comparison['right']);scalar=Path(comparison['left'])
        paths=list(dict.fromkeys([control_receipt,binary,projection/'assessment.json',projection/'config.json',
                    map_receipt,audit,old_config,old/'collapse.json',old/'collapse.log',
                    collapsed,scalar,*map(Path,expected),Path(__file__).resolve()]))
        status('waiting_for_sixteen_shared_CPU_slots')
        with lease(16,16,deadline):
            status('hashing_complete_operator_sources_and_reference_inputs')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=digest for path,digest in expected.items()):raise ValueError('reference source input changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            config,report=output/'trace.json',output/'trace.report.json'
            save(config,dict(precision_bits=128,threads=16,field_map=str(fieldmap),shards=cfg['shards'],
                 expected_operators=p['operators'],deadline_uptime=deadline,output=str(scratch/'tasks'),report=str(report)))
            status('tracing_all_operator_tasks_and_integrating_reference_entries')
            execute([binary,config],output/'trace.log',deadline,16)
            result=json.loads(report.read_text())
            checked={}
            for label,key in (('diagonal_0',0),('edge_0_1',1)):
                checked[label]=compare(result[label+'_interval'],entry(collapsed,key))
                checked[label]['old_scalar_coefficient_exact']=str(entry(scalar,key))
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('reference inputs changed during execution')
            retained=[config,report,*sorted((scratch/'tasks').glob('*.operators.jsonl')),
                      *sorted((scratch/'tasks').glob('*.offsets.bin')),*sorted((scratch/'tasks').glob('*.summary.json'))]
            with ThreadPoolExecutor(max_workers=16) as pool:artifacts=dict(zip(map(str,retained),pool.map(sha,retained)))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                 operators=result['operators'],selected_reference_operators=result['selected_reference_operators'],
                 affected_tasks=result['affected_tasks'],total_tasks=len(cfg['shards']),comparisons=checked,
                 complete_source_task_reference_intervals_certified=True,
                 comparison_scope='diagnostic against retained failed conductor-collapse output',
                 full_spatial_equivalence_qualified=False,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('complete_reference_intervals_and_task_trace_available',comparisons=checked)
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--controls',required=True,type=Path)
    args=parser.parse_args();run(args.output.resolve(),args.controls.resolve())
