"""Native read-only wire-length diagnostics for planned two-terminal local nets.

OpenROAD Python entry point; OPENPLL_LOCAL_LENGTH_CONFIG names its config.
Centerline lengths exclude supplemental RECT patches and via dimensions.
Instance separation and these lengths are diagnostics, not RC/signoff.
"""
import json
import os
from pathlib import Path
from common_v3 import save, sha, verify


def decode_lengths(odb, wire):
    decoder = odb.dbWireDecoder(); decoder.begin(wire)
    point = None; layer = None; junctions = {}; lengths = {}
    while True:
        op = decoder.next()
        if op == decoder.END_DECODE:
            break
        if op == decoder.PATH:
            point = None; layer = decoder.getLayer().getName()
        elif op in (decoder.POINT, decoder.POINT_EXT):
            values = decoder.getPoint() if op == decoder.POINT else decoder.getPoint_ext()
            current = tuple(values[:2])
            if point is not None:
                lengths[layer] = lengths.get(layer, 0) + sum(abs(a-b) for a, b in zip(current, point))
            point = current; junctions[decoder.getJunctionId()] = current
        elif op in (decoder.VIA, decoder.TECH_VIA):
            layer = decoder.getLayer().getName()
        elif op == decoder.JUNCTION:
            point = junctions[decoder.getJunctionValue()]; layer = decoder.getLayer().getName()
        elif op in (decoder.RULE, decoder.RECT, decoder.ITERM, decoder.BTERM):
            pass
        else:
            # SHORT and other encodings need an explicitly reviewed metric.
            raise ValueError('unsupported local wire length opcode: '+str(op))
    return lengths


def run(config_path):
    import odb
    config = json.loads(config_path.read_text())
    route = Path(config['route']).resolve(); guides = Path(config['guides']).resolve()
    output = Path(config['output']).resolve()
    rr = route/'assessment.json'; r = json.loads(rr.read_text())
    gr = guides/'assessment.json'; g = json.loads(gr.read_text())
    for record in (r, g):
        verify(record['input_sha256']); verify(record['artifacts'])
    corridors = guides/'corridors.json'
    db = route/'route.odb'
    D = odb.dbDatabase.create(); odb.read_db(D, str(db)); block = D.getChip().getBlock()
    if block.getDbUnitsPerMicron() != 1000:
        raise ValueError('nanometer database units required')
    rows = []
    for entry in json.loads(corridors.read_text()):
        net = block.findNet(entry['net'])
        if net is None or net.getWire() is None or list(net.getBTerms()):
            raise ValueError('routed internal local net required')
        terms = list(net.getITerms())
        identities = {(t.getInst().getName(), t.getMTerm().getName()) for t in terms}
        if len(terms) != 2 or identities != {(p['cell'], p['pin']) for p in entry['terminals']}:
            raise ValueError('local connection identity changed')
        boxes = [t.getInst().getBBox() for t in terms]
        gap = (max(0, boxes[0].xMin()-boxes[1].xMax(), boxes[1].xMin()-boxes[0].xMax())
               + max(0, boxes[0].yMin()-boxes[1].yMax(), boxes[1].yMin()-boxes[0].yMax()))/1000
        lengths = {k: v/1000 for k, v in decode_lengths(odb, net.getWire()).items()}
        rows.append(dict(net=entry['net'], terminals=entry['terminals'],
                         instance_bbox_separation_lower_bound_um=gap,
                         length_um_by_layer=lengths, total_length_um=sum(lengths.values())))
    inputs = {str(p): sha(p) for p in (config_path, rr, gr, corridors, db, Path(__file__).resolve())}
    verify(inputs); output.mkdir(parents=True, exist_ok=False)
    save(output/'lengths.json', rows)
    save(output/'assessment.json', dict(input_sha256=inputs,
         artifacts={str(output/'lengths.json'): sha(output/'lengths.json')},
         measured_local_nets=len(rows), supplemental_RECT_patches_excluded=True,
         via_dimensions_excluded=True, diagnostic=True, release_ready=False))
    print(json.dumps(dict(measured_local_nets=len(rows))))


if __name__ == '__main__':
    run(Path(os.environ['OPENPLL_LOCAL_LENGTH_CONFIG']).resolve())
