"""Independently locate all absent G diagonals from raw sparse record bytes."""
import argparse
import json
from pathlib import Path
import struct
import time
import numpy as np
from common import save,sha
from resources import lease


def diagonal_support(path,nodes):
    with path.open('rb') as stream:
        if stream.read(8)!=b'SPCRUN01':raise ValueError('raw sparse matrix format')
        count=struct.unpack('<Q',stream.read(8))[0]
    if path.stat().st_size!=16+40*count:raise ValueError('raw sparse matrix size')
    dtype=np.dtype(dict(names=['key','significand','exponent'],formats=['<u8','<u8','<u2'],offsets=[0,8,16],itemsize=40))
    data=np.memmap(path,mode='r',dtype=dtype,offset=16,shape=(count,));seen=np.zeros(nodes,dtype=np.bool_)
    for start in range(0,count,1000000):
        part=data[start:start+1000000];keys=part['key'];a=keys>>32;b=keys&0xffffffff
        if np.any(b>=nodes):raise ValueError('raw matrix voltage bound')
        nonzero=(part['significand']!=0)|((part['exponent']&0x7fff)!=0)
        seen[a[(a==b)&nonzero].astype(np.intp)]=True
    del data
    return seen


def run(assembly,extension,zero_map,output):
    assembly,extension,zero_map,out=(p.resolve() for p in (assembly,extension,zero_map,output))
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proofs=[p/'assessment.json' for p in (assembly,extension,zero_map)]
    combined,extra,zeros=[json.loads(p.read_text()) for p in proofs]
    if not combined['combined_known_nominal_G_assembled'] or combined['symbolic_material_values_selected']:
        raise ValueError('known G with unresolved symbolic parameters required')
    for proof in proofs[1:]:
        if combined['input_sha256'].get(str(proof))!=sha(proof):raise ValueError('component namespace lineage differs')
    matrix=Path(combined['zero_R_constrained_known_G_matrix']);mapping=zero_map/'voltage_map.bin'
    symbolic_dir=Path(json.loads((extension/'config.json').read_text())['output'])
    sources=sorted(symbolic_dir.glob('symbolic_*.jsonl'))
    units=[Path(r['zero_R_constrained_unit_square_matrix']) for r in combined['symbolic_material_families']['material_families']]
    paths=[*proofs,matrix,mapping,*sources,*units,Path(__file__).resolve(),Path(np.__file__).resolve()]
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths}
        for p in (matrix,*units):
            if pins[str(p)]!=combined['artifacts'][str(p)]:raise ValueError('parameterized matrix artifact changed')
        if pins[str(mapping)]!=zeros['artifacts'][str(mapping)]:raise ValueError('exact zero-R voltage map changed')
        original= zeros['results']['original_voltage_nodes'];nodes=zeros['results']['constrained_voltage_nodes']
        with mapping.open('rb') as stream:
            if stream.read(8)!=b'CNETDOF1' or struct.unpack('<QQ',stream.read(16))!=(original,nodes):raise ValueError('voltage transform header')
        remap=np.memmap(mapping,mode='r',dtype='<u4',offset=24,shape=(original,))
        expected={0}
        for source in sources:
            if pins[str(source)]!=extra['artifacts'][str(source)]:raise ValueError('unresolved end source changed')
            with source.open() as stream:
                for line in stream:
                    row=json.loads(line);end=row['global_voltage_ids'][0]
                    if row['finite_conductance_assigned']:raise ValueError('unresolved end already assigned a law')
                    mapped=int(remap[end])
                    if mapped in expected:raise ValueError('unresolved end voltages unexpectedly aliased')
                    expected.add(mapped)
        del remap
        known=diagonal_support(matrix,nodes);actual=set(map(int,np.flatnonzero(~known)))
        if actual!=expected:raise ValueError('unknown G support extends beyond the explicit semiconductor ends/reference')
        covered=known.copy()
        for unit in units:covered|=diagonal_support(unit,nodes)
        if set(map(int,np.flatnonzero(~covered)))!={0}:raise ValueError('symbolic families leave additional absent voltage support')
        if any(sha(Path(p))!=h for p,h in pins.items()):raise ValueError('G coverage input changed during independent scan')
        ids=out/'unresolved_constrained_voltage_ids.json';save(ids,sorted(expected-{0}))
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(ids):sha(ids)},numpy_version=np.__version__,
             every_known_G_diagonal_independently_scanned=True,
             known_G_absent_diagonals_exactly_reference_plus_unresolved_ends=True,
             all_nonreference_voltages_have_known_or_symbolic_G_support=True,
             constrained_voltage_nodes=nodes,known_G_absent_voltage_diagonals=len(actual),
             unresolved_semiconductor_voltage_states=len(expected)-1,material_values_selected=False,
             full_numeric_spatial_G_matrix_assembled=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(dict(known_absent_diagonals=len(actual),unresolved_ends=len(expected)-1,
             all_nonreference_states_covered_by_known_or_symbolic_G=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('assembly','extension','zero-map','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.assembly,a.extension,a.zero_map,a.output)
