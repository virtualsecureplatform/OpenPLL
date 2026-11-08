"""Join flat MOS equivalence classes to physical regions, without cutting a circuit."""
import argparse
import json
import shlex
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save, sha, verify
from native_spice_comments import strip_floating_annotation

class Aliases:
    def __init__(self):
        self.parent = {}
    def find(self, node):
        node = node.lower()
        self.parent.setdefault(node, node)
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != node:
            node, self.parent[node] = self.parent[node], root
        return root
    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)

def signature(model, length, width, body, gate, diffusion, aliases):
    return (model.lower(), F(length), F(width), aliases.find(body),
            aliases.find(gate), tuple(sorted(aliases.find(n) for n in diffusion)))

def run(flat, regions, output):
    receipt = regions / 'assessment.json'
    prior = json.loads(receipt.read_text())
    verify(prior['input_sha256'])
    if not prior['all_primitive_counts_and_MOS_dimensions_match']:
        raise ValueError('verified physical regions required')
    ext = flat / 'IntegerPLL_400MHz_KeeperFlatC.ext'
    spice = flat / 'capacitance.spice'
    if prior['input_sha256'].get(str(ext)) != sha(ext):
        raise ValueError('same EXT required')
    extraction = flat / 'assessment.json'
    source = json.loads(extraction.read_text())
    verify(source['input_sha256']); verify(source['artifacts'])
    pins = {str(p): sha(p) for p in [receipt, extraction, ext, spice, Path(__file__).resolve(), Path(__file__).with_name('native_spice_comments.py')]}
    aliases = Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            fields = shlex.split(line); aliases.union(fields[1], fields[2])
    grid = F(prior['EXT_coordinate_unit_um'])
    gds_unit = F(prior['GDS_coordinate_unit_um'])
    boxes = {name: [F(v)*gds_unit/grid for v in placement['bbox_dbu']]
             for name, placement in prior['physical_macro_placements'].items()}
    physical = defaultdict(Counter)
    for line in ext.open():
        if not line.startswith('device msubckt '):
            continue
        f = shlex.split(line)
        if 'nfet' not in f[2] and 'pfet' not in f[2]:
            continue
        i = 7; params = {}
        while '=' in f[i]:
            key, value = f[i].split('=', 1); params[key] = value; i += 1
        if len(f[i:]) != 10:
            raise ValueError('unsupported MOS terminal encoding')
        x0,y0,x1,y1 = map(int, f[3:7])
        inside = [name for name,(a,b,c,d) in boxes.items() if a<=x0 and b<=y0 and x1<=c and y1<=d]
        if len(inside)>1:
            raise ValueError('overlapping regions')
        key = signature(f[2],F(params['l'])*grid,F(params['w'])*grid,f[i],f[i+1],[f[i+4],f[i+7]],aliases)
        physical[key][inside[0] if inside else 'parent'] += 1
    emitted = defaultdict(list)
    for line in spice.open():
        if not line.startswith('X'):
            continue
        f = strip_floating_annotation(line).split()
        if len(f)<6 or ('nfet' not in f[5] and 'pfet' not in f[5]):
            continue
        params = dict(token.split('=',1) for token in f[6:])
        if F(params.get('m','1')) != 1:
            raise ValueError('unit multiplicity required')
        key = signature(f[5],params['l'],params['w'],f[4],f[2],[f[1],f[3]],aliases)
        emitted[key].append(f[0])
    mismatches = []; ambiguous = []; mapping = {}; totals = Counter()
    for key in physical.keys() | emitted.keys():
        counts = physical.get(key, Counter()); names = emitted.get(key, [])
        if sum(counts.values()) != len(names):
            mismatches.append(dict(signature=repr(key), physical=dict(counts), emitted=names))
        elif len(counts)!=1:
            ambiguous.append(dict(signature=repr(key), physical=dict(counts), emitted=names))
        else:
            region = next(iter(counts)); totals[region] += len(names)
            mapping.update({name:region for name in names})
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output/'MOS_regions.json', mapping)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(output/'MOS_regions.json'):sha(output/'MOS_regions.json')}, physical_MOS_count=sum(sum(c.values()) for c in physical.values()), emitted_MOS_count=sum(map(len,emitted.values())), signature_count=len(physical), region_counts=dict(totals), count_mismatches=mismatches, cross_region_ambiguous_classes=ambiguous, all_MOS_region_ownership_verified=not mismatches and not ambiguous, individual_parallel_device_bijection_claimed=False, diffusion_area_and_perimeter_correspondence_verified=False, non_MOS_correspondence_verified=False, circuit_partitioned=False, boundary_loading_qualified=False, model_qualified=False, release_ready=False))

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['flat','regions','output']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); run(a.flat.resolve(),a.regions.resolve(),a.output.resolve())
