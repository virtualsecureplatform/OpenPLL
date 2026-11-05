"""Inspect every raw G off-diagonal sign without a floating conversion or PSD claim."""
import argparse
import json
from pathlib import Path
import struct
import time
import numpy as np
from common import save,sha
from resources import lease

DTYPE=np.dtype(dict(names=['key','significand','exponent'],formats=['<u8','<u8','<u2'],offsets=[0,8,16],itemsize=40))


def inspect(path,nodes,deadline):
    with path.open('rb') as stream:
        if stream.read(8)!=b'SPCRUN01':raise ValueError('sparse magic')
        count,=struct.unpack('<Q',stream.read(8))
    if path.stat().st_size!=16+40*count:raise ValueError('sparse size')
    data=np.memmap(path,mode='r',dtype=DTYPE,offset=16,shape=(count,));positive=negative=zero=diagonal=0;examples=[]
    for start in range(0,count,1000000):
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('sign scan deadline')
        part=data[start:start+1000000];a=part['key']>>32;b=part['key']&0xffffffff;off=a!=b
        if np.any(a>b) or np.any(b>=nodes) or np.any((part['exponent']&0x7fff)==0x7fff):raise ValueError('index bounds or nonfinite coefficient')
        nonzero=(part['significand']!=0)|((part['exponent']&0x7fff)!=0);sign=(part['exponent']&0x8000)!=0
        p=off&nonzero&~sign;positive+=int(np.count_nonzero(p));negative+=int(np.count_nonzero(off&nonzero&sign));zero+=int(np.count_nonzero(off&~nonzero));diagonal+=int(np.count_nonzero(~off))
        if len(examples)<32:examples.extend([[int(x),int(y)] for x,y in zip(a[p][:32-len(examples)],b[p][:32-len(examples)])])
    del data
    return dict(entries_scanned=count,diagonal_records=diagonal,positive_offdiagonal_records=positive,negative_offdiagonal_records=negative,zero_offdiagonal_records=zero,positive_offdiagonal_examples=examples)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    parent=Path('build/signoff400/startup_timing_known_conductance_001/assessment.json').resolve();a=json.loads(parent.read_text())
    matrix=Path(a['zero_R_constrained_known_G_matrix']);paths=[parent,matrix,Path(__file__).resolve(),Path(np.__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths}
        if a['artifacts'][str(matrix)]!=pins[str(matrix)]:raise ValueError('known G changed')
        fixture=output/'sign_control.bin';rows=np.zeros(5,dtype=DTYPE)
        rows['key']=[0,1,2,(1<<32)|2,(2<<32)|2];rows['significand']=[1<<63,0,0,1,1<<63];rows['exponent']=[0x3fff,0,0x8000,0,0x3fff]
        fixture.write_bytes(b'SPCRUN01'+struct.pack('<Q',5)+rows.tobytes());r=inspect(fixture,3,deadline)
        if r['positive_offdiagonal_records']!=1 or r['negative_offdiagonal_records']!=0 or r['zero_offdiagonal_records']!=2:raise ValueError('subnormal and signed-zero controls')
        rows['exponent'][3]=0x8000;fixture.write_bytes(b'SPCRUN01'+struct.pack('<Q',5)+rows.tobytes());r=inspect(fixture,3,deadline)
        if r['positive_offdiagonal_records']!=0 or r['negative_offdiagonal_records']!=1:raise ValueError('negative subnormal control')
        result=inspect(matrix,a['numerical_matrix_structure']['node_count'],deadline)
        if result['entries_scanned']!=a['numerical_matrix_structure']['upper_entries']:raise ValueError('whole G coverage mismatch')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('sign scan source changed')
        save(output/'assessment.json',dict(input_sha256=pins,results=result,every_known_G_offdiagonal_sign_checked=True,
             bit_exact_signed_zero_and_subnormal_controls_pass=True,
             all_known_G_offdiagonals_nonpositive=result['positive_offdiagonal_records']==0,
             diagonal_dominance_certified=False,full_matrix_passivity_verified=False,
             unresolved_material_family_numeric_values_selected=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
