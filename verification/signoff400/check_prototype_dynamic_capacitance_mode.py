"""Search a conventional fixed-rail C network for an exactly verified negative energy mode."""
import argparse
import json
from fractions import Fraction as F
from pathlib import Path
import signal
import time

import numpy as np
import scipy
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import eigsh

from common import save, sha, verify
from resources import lease


def run(source, output):
    output.mkdir(parents=True, exist_ok=False)
    receipt = source / 'assessment.json'
    r = json.loads(receipt.read_text())
    verify(r['artifacts'])
    file = source / 'dynamic.pairs.jsonl'
    pairs = []
    for line in file.open():
        row = json.loads(line)
        pairs.append((tuple(row['nodes']), F(row['farads'])))
    fixed = '__fixed_rail_AC_reference'
    nodes = sorted({n for pair, _ in pairs for n in pair if n != fixed})
    index = {n:i for i,n in enumerate(nodes)}
    rows, cols, data = [], [], []
    diagonal = np.zeros(len(nodes))
    for (a,b), value in pairs:
        value = float(value)
        for n in (a,b):
            if n != fixed:
                diagonal[index[n]] += value
        if a != fixed and b != fixed:
            rows.extend((index[a], index[b])); cols.extend((index[b], index[a])); data.extend((-value,-value))
    if np.any(diagonal <= 0):
        raise ValueError('nonpositive dynamic diagonal requires a direct basis-vector check')
    rows.extend(range(len(nodes))); cols.extend(range(len(nodes))); data.extend(diagonal)
    matrix = coo_matrix((data,(rows,cols)),shape=(len(nodes),len(nodes))).tocsr()
    scale = diags(1 / np.sqrt(diagonal))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 600
    signal.alarm(600)
    pins = {str(p):sha(p) for p in (receipt,file,Path(__file__).resolve(),Path(np.__file__),Path(scipy.__file__))}
    with lease(1,8,deadline):
        eigenvalues, vectors = eigsh(scale @ matrix @ scale, k=1, which='SA', tol=1e-8,
                                    maxiter=2000, v0=np.ones(len(nodes)))
        vector = vectors[:,0] / np.sqrt(diagonal)
        vector /= np.max(np.abs(vector))
        integers = np.rint(vector * 10**9).astype(np.int64)
        voltage = {node:int(integers[i]) for i,node in enumerate(nodes)}
        voltage[fixed] = 0
        energy = sum((value * (voltage[a]-voltage[b])**2 for (a,b),value in pairs), F())
        artifact = output / 'integer_mode.json'
        save(artifact,dict(voltages=voltage, common_scale=10**9,
                          energy_coefficient_before_common_scale_F=str(energy)))
        verify(pins)
        save(output / 'assessment.json',dict(input_sha256=pins,artifacts={str(artifact):sha(artifact)},
             numpy_version=np.__version__,scipy_version=scipy.__version__,
             normalized_eigenvalue_estimate=float(eigenvalues[0]),
             exact_negative_energy_verified=energy<0, exact_energy_coefficient_F=str(energy/F(10**18)),
             fixed_voltage_nodes=r['fixed_voltage_nodes'],global_passivity_proved=False,
             diagnostic=True,validated_for_prototype=False,release_ready=False))
        print('normalized eigenvalue',eigenvalues[0],'exact negative energy',energy<0,flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.source.resolve(),a.output.resolve())
