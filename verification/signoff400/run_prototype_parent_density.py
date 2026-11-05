"""Run and independently audit stock density on one DRC/LVS-checked parent."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from extract_prototype_analog_capacitance_v2 import MAGIC


def run(layout,lvs,frame,output):
    import pya
    receipts=[p/'assessment.json' for p in (layout,lvs,frame)]
    a,l,f=[json.loads(path.read_text()) for path in receipts]
    for record in (a,l,f):verify(record['input_sha256']);verify(record['artifacts'])
    if (not a['assembled_drc_pass'] or not a['all_three_macros_expanded'] or not l['assembled_lvs_pass']
            or not l['assembled_drc_pass'] or not f['assembly_frame_pass']
            or l['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])
            or a['input_sha256'].get(str(receipts[2]))!=sha(receipts[2])):
        raise ValueError('same-source expanded parent DRC/LVS and frame required')
    gds=layout/'assembly.gds';top='IntegerPLL_400MHz_PrototypeTop'
    stream=pya.Layout();stream.read(str(gds))
    die=[int(round(v*1000)) for v in f['parent_die_area_um']]
    if stream.dbu!=.001 or stream.cell(top) is None or stream.cell(top).bbox()!=pya.Box(*die):
        raise ValueError('source geometry bounds differ from declared macro die')
    private=ROOT/'build/timing450/pdk/sky130A'
    method=private/'libs.tech/magic/check_density.py'
    auditor=ROOT/'verification/timing400/audit_assembled_density_v2.py'
    inputs={str(p):sha(p) for p in (*receipts,gds,method,auditor,Path(MAGIC),
        private/'libs.tech/magic/sky130A.tech',private/'libs.tech/magic/sky130A.magicrc',
        Path(__file__).resolve(),Path('/usr/bin/python3'),Path(sys.executable),
        Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),
        Path(__file__).with_name('compiled_charge.py'),
        Path(__file__).with_name('extract_prototype_analog_capacitance_v2.py'),
        Path(sys.modules[pya.Layout.__module__].__file__))}
    output.mkdir(parents=True,exist_ok=False);(output/(top+'.gds')).symlink_to(gds)
    save(output/'input_manifest.json',dict(input_sha256=inputs,declared_die_nm=die))
    os.environ.update(PDK_ROOT=str(private.parent),PDK='sky130A',
        PATH=str(Path(MAGIC).parent)+os.pathsep+os.environ['PATH'],OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    os.chdir(output);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    try:
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='native_density_running',release_ready=False))
            execute(['/usr/bin/python3',method,top+'.gds'],output/'density.log',deadline,16)
            verify(inputs)
            completion=output/'native_completion.json'
            save(completion,dict(input_sha256=inputs,artifacts={str(output/'density.log'):sha(output/'density.log')},
                exit_code=0,declared_die_nm=die,release_ready=False))
            execute(['/usr/bin/python3',auditor,'--density',output,'--output',output/'audit'],
                    output/'audit.log',deadline,16)
        measured=json.loads((output/'audit/assessment.json').read_text())
        verify(measured['input_sha256']);verify(measured['artifacts'])
        save(output/'assessment.json',dict(input_sha256=inputs,
            artifacts={str(p):sha(p) for p in (completion,output/'density.log',output/'audit/assessment.json')},
            declared_die_nm=die,native_density_completed=True,
            independently_recomputed_global_and_window_values=True,
            stock_density_checks_passed=measured['stock_density_checks_passed'],
            constrained_density_checks=measured['constrained_density_checks'],
            stepped_windows_available=measured['stepped_windows_available'],
            chip_integration_density_qualified=False,physical_integrity_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='density_pass' if measured['stock_density_checks_passed'] else 'density_nonpass',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','lvs','frame','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('layout','lvs','frame','output')))
