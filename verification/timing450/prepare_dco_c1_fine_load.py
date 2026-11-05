#!/usr/bin/env python3
"""Create isolated coarse-1 fine-load experiments; never adopt a candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36'
SOURCE = ROOT/'sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_sky130.v'
BASE_SHA = '8aa12ef9b25c4e6445d538b96bb5bd428704141a2a70002df4d5f1ad724ab304'
COUNTS = (144, 160, 192)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def names(count):
    return (BASE+f'_C1FINE{count}',
            f'IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine{count}_sky130.v')


def bank(count):
    return f'''    // Fine-controlled load on the active coarse-1 turn. TE=1 loads the node.
    // Increasing fine code removes loads; all original 255 controls remain.
    wire [{count-1}:0] coarse1_fine_dummy;
    genvar c1fine;
    generate
        for (c1fine = 0; c1fine < {count}; c1fine = c1fine + 1) begin : gen_coarse1_fine_load
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__einvp_1 load (
                `INTEGERPLL_SKY130_CELL_PG
                .A(mirror_turn_n[1]),
                .TE(DCO_THERM[(255*c1fine)/{count}]),
                .Z(coarse1_fine_dummy[c1fine])
            );
        end
    endgenerate

'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sha(SOURCE) != BASE_SHA:
        raise ValueError('baseline RTL changed')
    # Require fresh experiment paths so rerunning cannot overwrite evidence.
    for count in COUNTS:
        top, filename = names(count)
        if (ROOT/'sky130'/filename).exists() or (ROOT/'openlane'/top).exists():
            raise FileExistsError(top)
    if args.output.exists():
        raise FileExistsError(args.output)
    config_dir = ROOT/'openlane'/BASE
    baseline = SOURCE.read_text()
    candidates = []
    for count in COUNTS:
        top, filename = names(count)
        source = ROOT/'sky130'/filename
        source.write_text(baseline.replace(BASE, top).replace('\nendmodule', '\n'+bank(count)+'endmodule'))
        directory = ROOT/'openlane'/top
        directory.mkdir()
        config = json.loads((config_dir/'config.json').read_text())
        config['DESIGN_NAME'] = top
        config['VERILOG_FILES'] = ['dir::../../sky130/'+filename]
        (directory/'config.json').write_text(json.dumps(config, indent=2)+'\n')
        for auxiliary in ('pin_order.cfg', 'no_clock.sdc'):
            shutil.copyfile(config_dir/auxiliary, directory/auxiliary)
        experiment = dict(top=top, extra_loads=count, source=str(source.relative_to(ROOT)),
                          parent_source=str(SOURCE.relative_to(ROOT)), parent_sha256=BASE_SHA,
                          source_sha256=sha(source), control_indices=[255*j//count for j in range(count)],
                          release_qualified=False, selected=False,
                          scope='Isolated coarse-1 fine-load candidate; native range and extracted qualification required.')
        (directory/'experiment.json').write_text(json.dumps(experiment, indent=2)+'\n')
        candidates.append(experiment)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(candidates=candidates, release_qualified=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
