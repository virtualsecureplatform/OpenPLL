"""Wait for exact constrained C, then scan every entry for unresolved-end incidence."""
import argparse
import json
import os
from pathlib import Path
import struct
import time
import numpy as np
from common import save, sha
from resources import identity, lease

DTYPE=np.dtype(dict(names=['key','significand','exponent'],formats=['<u8','<u8','<u2'],offsets=[0,8,16],itemsize=40))


def scan(path,nodes,targets,deadline):
    with path.open('rb') as stream:
        if stream.read(8)!=b'SPCRUN01': raise ValueError('matrix magic')
        count,=struct.unpack('<Q',stream.read(8))
    if path.stat().st_size!=16+40*count: raise ValueError('matrix length')
    data=np.memmap(path,mode='r',dtype=DTYPE,offset=16,shape=(count,))
    selected=np.zeros(nodes,dtype=np.bool_);selected[list(targets)]=True
    incident=set();nonzero_entries=0;diagonals=0;samples=[]
    for start in range(0,count,1000000):
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline: raise TimeoutError('C incidence budget')
        part=data[start:start+1000000];a=part['key']>>32;b=part['key']&0xffffffff
        if np.any(a>b) or np.any(b>=nodes): raise ValueError('matrix indices')
        # All 80-bit encodings except signed zero count as nonzero; no float64 underflow.
        nonzero=(part['significand']!=0)|((part['exponent']&0x7fff)!=0)
        mask=nonzero&(selected[a]|selected[b]);aa=a[mask];bb=b[mask]
        nonzero_entries+=len(aa);diagonals+=int(np.count_nonzero(aa==bb))
        incident.update(int(x) for x in aa if int(x) in targets)
        incident.update(int(x) for x in bb if int(x) in targets)
        if len(samples)<32:samples.extend([[int(x),int(y)] for x,y in zip(aa[:32-len(samples)],bb[:32-len(samples)])])
    del data
    return dict(matrix_entries_scanned=count,nonzero_entries_incident_on_unresolved_states=nonzero_entries,
                nonzero_unresolved_diagonals=diagonals,unresolved_states_with_nonzero_C=sorted(incident),sample_pairs=samples)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('build/signoff400').resolve()
    upstream=base/'startup_timing_spatial_zero_R_followup_003'
    direct=base/'startup_timing_symbolic_end_connections_001/assessment.json'
    coverage=base/'startup_timing_G_parameter_coverage_audit_001/assessment.json'
    unresolved=coverage.parent/'unresolved_constrained_voltage_ids.json'
    owner=upstream/'owner.json';o=json.loads(owner.read_text());pid,birth=o['pid'],o['birth']
    if identity(pid)!=birth:raise ValueError('exact zero-R C followup must be live at registration')
    paths=[owner,direct,coverage,unresolved,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),watched_pid=pid,watched_birth=birth,
                                automatic_identical_retry=False,waiting_budget_s=259200,check_budget_s=43200))
    save(output/'input_manifest.json',dict(input_sha256=pins))
    def status(state,**extra):save(output/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        status('waiting_for_exact_zero_R_spatial_C_followup')
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+259200
        while identity(pid)==birth:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('upstream wait budget')
            time.sleep(10)
        parent=upstream/'assessment.json';p=json.loads(parent.read_text())
        if not p['full_spatial_native_zero_R_constraint_transform_complete'] or not p['final_producer_node_maps_reconciled']:
            raise ValueError('final constrained C and producer reconciliation required')
        c=json.loads(coverage.read_text());d=json.loads(direct.read_text())
        if d['input_sha256'].get(str(coverage))!=pins[str(coverage)]:raise ValueError('direct-connection lineage')
        if c['artifacts'][str(unresolved)]!=pins[str(unresolved)]:raise ValueError('unresolved state hash')
        targets=set(json.loads(unresolved.read_text()));nodes=c['constrained_voltage_nodes']
        matrix=Path(p['constrained_matrix'])
        zero=base/'startup_timing_zero_R_voltage_map_002/assessment.json'
        if p['input_sha256'].get(str(zero))!=c['input_sha256'].get(str(zero)):
            raise ValueError('constrained namespace mismatch')
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(2,4,deadline):
            for path,h in pins.items():
                if sha(Path(path))!=h:raise ValueError('input changed while waiting')
            pins.update({str(parent):sha(parent),str(matrix):sha(matrix)})
            if p['artifacts'].get(str(matrix))!=pins[str(matrix)]:raise ValueError('C matrix hash')
            # Signed zeros, smallest subnormal, diagonal and cross-entry detection controls.
            fixture=output/'incidence_control.bin';rows=np.zeros(4,dtype=DTYPE)
            rows['key']=[1, (1<<32)|1,(1<<32)|2,(2<<32)|2]
            rows['exponent']=[0,0x8000,0,0x3fff];rows['significand']=[0,0,1,1<<63]
            fixture.write_bytes(b'SPCRUN01'+struct.pack('<Q',4)+rows.tobytes())
            control=scan(fixture,3,{1},deadline)
            if control['nonzero_entries_incident_on_unresolved_states']!=1 or control['nonzero_unresolved_diagonals']!=0:
                raise ValueError('x87 zero/subnormal incidence controls')
            status('scanning_all_constrained_C_entries')
            result=scan(matrix,nodes,targets,deadline)
            for path,h in pins.items():
                if sha(Path(path))!=h:raise ValueError('source changed during scan')
            save(output/'assessment.json',dict(input_sha256=pins,results=result,
                 all_constrained_C_entries_scanned=True,x87_zero_subnormal_controls_pass=True,
                 direct_device_terminal_hits=d['direct_device_terminal_hits'],direct_external_port_hits=d['direct_external_port_hits'],
                 unresolved_states_eliminable=False,scalar_rounding_and_junction_allocation_qualified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('symbolic_end_capacitance_incidence_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
