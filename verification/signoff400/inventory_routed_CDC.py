"""Trace routed sequential cones with retained Yosys cell definitions; no timing/MTBF promotion."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from inventory_mapped_CDC import inventory
from resources import identity,lease


def inside(config):
    c=json.loads(config.read_text());verify({c['yosys']:c['yosys_sha256']})
    remaining=c['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    if remaining<=0:raise TimeoutError('routed CDC conversion deadline')
    subprocess.run([c['yosys'],'-s',c['script']],check=True,timeout=remaining)
    save(Path(c['native_receipt']),dict(yosys=c['yosys'],yosys_sha256=sha(Path(c['yosys'])),conversion_completed=True))


def run(mapping,route,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    try:
        mreceipt=mapping/'assessment.json';rreceipt=route/'assessment.json'
        m,r=[json.loads(p.read_text()) for p in (mreceipt,rreceipt)]
        mapped=mapping/'mapped.json';routed=route/'route.v';image=ROOT/'build/apptainer/openpll-release-modern.sif'
        expected={str(mapped):m['artifacts'][str(mapped)],str(routed):r['artifacts'][str(routed)]}
        yosys=next(p for p in m['input_sha256'] if p.endswith('/bin/yosys'))
        paths=[mreceipt,rreceipt,mapped,routed,image,Path(__file__).resolve(),Path(__file__).with_name('inventory_mapped_CDC.py')]
        status('waiting_for_routed_CDC_conversion_lease')
        with lease(1,4,deadline):
            pins={str(p):sha(p) for p in paths}
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('routed CDC source changed')
            modules=json.loads(mapped.read_text())['modules'];modules.pop('IntegerPLL_ProgrammedCore')
            if any(v.get('cells') for v in modules.values()):raise ValueError('retained leaf library must contain only blackboxes')
            library=output/'library.json';save(library,dict(modules=modules))
            # These routed physical-only instances have no combinational outputs or state.
            # Stubs preserve connections as loads only; they make no capacitance/timing claim.
            stubs=output/'physical_loads.v';stubs.write_text('\n'.join([
                *[f'(* blackbox *) module sky130_fd_sc_hs__fill_{n}(); endmodule' for n in (1,2,4,8)],
                '(* blackbox *) module sky130_fd_sc_hs__tapvpwrvgnd_1(); endmodule',
                '(* blackbox *) module sky130_fd_sc_hs__diode_2(input DIODE); endmodule'])+'\n')
            converted=output/'routed.json';script=output/'convert.ys'
            script.write_text(f'read_json {library}\nread_verilog -lib {stubs}\nread_verilog {routed}\nhierarchy -check -top IntegerPLL_ProgrammedCore\ncheck -assert\nwrite_json {converted}\n')
            cfg=output/'convert.json';native=output/'native_receipt.json'
            save(cfg,dict(yosys=yosys,yosys_sha256=m['input_sha256'][yosys],script=str(script),native_receipt=str(native),deadline_uptime=deadline))
            status('converting_routed_connectivity_with_pinned_Yosys')
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',
                Path(__file__).resolve(),'--inside',cfg],output/'convert.log',deadline,4)
            status('tracing_every_routed_sequential_data_and_control_cone')
            design=json.loads(converted.read_text());module=design['modules']['IntegerPLL_ProgrammedCore'];result=inventory(module)
            expected_states=sum(v for k,v in r['cell_inventory'].items() if '__dfrtp_' in k or '__dfstp_' in k)
            if result['sequential_cells']!=expected_states:raise ValueError('routed sequential inventory count mismatch')
            report=output/'inventory.json';save(report,result);verify(pins)
            artifacts={str(p):sha(p) for p in (library,stubs,converted,script,cfg,native,report)}
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                all_routed_sequential_data_and_control_cones_traced=True,sequential_cells=result['sequential_cells'],
                data_crossing_candidates=len(result['data_crossing_candidates']),asynchronous_control_groups=len(result['asynchronous_control_groups']),
                physical_only_cells_represented_as_loads_without_logic=True,
                mapped_ASYNC_REG_attributes_not_present_in_routed_verilog=True,
                complete_structural_inventory_qualified=False,clock_intent_qualified=False,
                final_GDS_connectivity_binding_qualified=False,physical_CDC_qualified=False,release_qualified=False))
            status('routed_CDC_cone_inventory_complete',sequential_cells=result['sequential_cells'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path)
    for name in ('mapping','route','output'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    elif all((a.mapping,a.route,a.output)):run(a.mapping.resolve(),a.route.resolve(),a.output.resolve())
    else:p.error('mapping, route and output required outside the native worker')
