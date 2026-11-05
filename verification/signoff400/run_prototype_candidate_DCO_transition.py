"""Native electrical tuning transition diagnostic on an explicitly pinned candidate.

Injected thermometer hazards are engineering stimuli, not extracted decoder timing.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from assess_prototype_native_waveform import assess, crossings

def transition_deck(text, initial, final, hazard=None, phase_ns=0.):
    if not all(0 <= value <= 255 for value in (initial, final)) or hazard not in (None, 0, 255):
        raise ValueError('invalid thermometer stimulus')
    if not math.isfinite(phase_ns) or not 0 <= phase_ns <= 2:
        raise ValueError('phase must lie in the declared two-ns stimulus interval')
    pattern = re.compile(r'^VCTRL(\d{3}) DCO_THERM\[(\d+)\] 0 (?:0|\{VDD\})$', re.M)
    matches = list(pattern.finditer(text))
    if len(matches) != 255 or sorted(int(m[1]) for m in matches) != list(range(255)) or any(int(m[1]) != int(m[2]) for m in matches):
        raise ValueError('exactly 255 unique inverted thermometer sources required')
    if text.splitlines().count('.tran 10.0p 40.0n 0 10.0p') != 1:
        raise ValueError('reviewed 40ns baseline required')
    if 'VRESET RESET_N 0 PULSE(0 {VDD} 5.0n 50p 50p 40.0n 80.0n)' not in text:
        raise ValueError('reset must stay released throughout capture')
    edge = 20 + phase_ns
    def value(code, bit):
        return '{VDD}' if bit >= code else '0'
    def source(match):
        bit = int(match[1]); before = value(initial, bit); after = value(final, bit)
        if hazard is None:
            points = f'0 {before} {edge-.1:g}n {before} {edge+.1:g}n {after}'
        else:
            middle = value(hazard, bit)
            points = f'0 {before} {edge-.2:g}n {before} {edge:g}n {middle} {edge+.2:g}n {middle} {edge+.4:g}n {after}'
        return f'VCTRL{bit:03d} DCO_THERM[{bit}] 0 PWL({points})'
    return pattern.sub(source, text)

def run(source, output, initial, final, hazard, phase):
    receipt = source/'assessment.json'; a = json.loads(receipt.read_text()); verify(a['input_sha256'])
    if not a.get('native_worker_completed'):
        raise ValueError('completed native candidate probe required')
    manifest = source/'input_manifest.json'; m = json.loads(manifest.read_text())
    decks = list((source/'native').glob('*.spice'))
    if len(decks) != 1:
        raise ValueError('one native baseline deck required')
    baseline = decks[0]
    reviewed = source/'all_cycle_assessment/assessment.json'
    review = json.loads(reviewed.read_text()); verify(review['input_sha256']); verify(review['artifacts'])
    if review['input_sha256'].get(str(baseline)) != sha(baseline):
        raise ValueError('baseline must match reviewed waveform deck')
    output.mkdir(parents=True, exist_ok=False)
    deck = output/'transition.cir'; deck.write_text(transition_deck(baseline.read_text(), initial, final, hazard, phase))
    init = output/'.spiceinit'; init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    ng = ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins = dict(a['input_sha256'])
    pins.update({str(p):sha(p) for p in (receipt, manifest, baseline, reviewed, deck, init, image, ng, Path(__file__).resolve())})
    save(output/'input_manifest.json', dict(input_sha256=pins, corner=a['corner'], coarse_code=a['coarse_code'],
         initial_fine=initial, final_fine=final, injected_hazard_code=hazard, transition_center_ns=20+phase,
         electrical_ramp_ps=200, hazard_plateau_ps=200 if hazard is not None else 0,
         extracted_decoder_timing=False, parent_loading_complete=False, diagnostic=True))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    save(output/'status.json', dict(state='native_transition_running', release_ready=False))
    log = output/'native.log'
    with lease(1, 4, deadline):
        execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck], log, deadline, 4)
    rows = []
    text = log.read_text()
    if 'Using KLU as Direct Linear Solver' not in text:
        raise ValueError('native KLU required')
    declared = re.findall(r'No\. of Data Rows\s*:\s*(\d+)', text)
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0].isdigit():
            if len(fields) != 3 or int(fields[0]) != len(rows):
                raise ValueError('invalid native output table')
            row = tuple(map(float, fields[1:]))
            if not all(math.isfinite(x) for x in row) or rows and row[0] <= rows[-1][0]:
                raise ValueError('invalid transient samples')
            rows.append(row)
    if len(declared) != 1 or len(rows) != int(declared[0]):
        raise ValueError('incomplete native table')
    before = assess(rows, 8e-9, 19e-9, 1.8)
    after = assess(rows, 27e-9, 40e-9, 1.8)
    rise, fall = crossings(rows, .9)
    edges = sorted([(t,'rise') for t in rise]+[(t,'fall') for t in fall])
    widths = [b[0]-a[0] for a,b in zip(edges,edges[1:]) if a[0] >= 10e-9]
    alternate = all(a[1] != b[1] for a,b in zip(edges,edges[1:]))
    detail = output/'observations.json'
    save(detail, dict(before=before, after=after, rising_edges_s=rise, falling_edges_s=fall,
         alternating_threshold_crossings=alternate, minimum_observed_half_pulse_s=min(widths),
         threshold_pulse_width_is_not_sequential_capture_qualification=True))
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(p):sha(p) for p in (log,detail)},
         native_transition_completed=True, phase_kick_uncertainty_bounded=False,
         final_decoder_loading_included=False, diagnostic=True, release_ready=False))
    save(output/'status.json', dict(state='native_transition_complete', release_ready=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('initial','final'):
        parser.add_argument('--'+name, type=int, required=True)
    parser.add_argument('--hazard', type=int, choices=(0,255))
    parser.add_argument('--phase-ns', type=float, default=0.)
    args = parser.parse_args()
    run(args.source.resolve(), args.output.resolve(), args.initial, args.final, args.hazard, args.phase_ns)
