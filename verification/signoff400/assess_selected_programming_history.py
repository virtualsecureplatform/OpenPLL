"""Measure physical programming input transitions; never infer charge causality."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify


def summarize(points, threshold=0.9):
    previous = None
    crossings = []
    minimum = math.inf
    maximum = -math.inf
    count = 0
    first = last = None
    for time, value in points:
        if not math.isfinite(time) or not math.isfinite(value):
            raise ValueError('finite time and voltage required')
        if previous is not None and time <= previous[0]:
            raise ValueError('strictly increasing source knots required')
        if previous is not None and (previous[1] >= threshold) != (value >= threshold):
            crossing = previous[0] + (time-previous[0])*(threshold-previous[1])/(value-previous[1])
            crossings.append(dict(time_ns=crossing*1e9, direction='rise' if value > previous[1] else 'fall'))
        if first is None:first = value
        last = value
        minimum = min(minimum, value)
        maximum = max(maximum, value)
        previous = time, value
        count += 1
    if count < 2:raise ValueError('at least two knots required')
    return dict(samples=count, initial_voltage=first, final_voltage=last,
                initial_high=first >= threshold, final_high=last >= threshold,
                minimum_voltage=minimum, maximum_voltage=maximum, crossings=crossings,
                transient_logic_excursion=first >= threshold and last >= threshold and len(crossings) >= 2 or
                    first < threshold and last < threshold and len(crossings) >= 2)


def run(capture, output):
    if output.exists():raise FileExistsError(output)
    data=json.loads(capture.read_text())
    if not data.get('source_complete_and_all_values_finite'):raise ValueError('complete native capture required')
    channels=data['clock_driver_waveforms']
    expected={*[f'DCO_THERM[{i}]' for i in range(255)],
              *[f'COARSETHERMAL_CODE[{i}]' for i in range(47)], 'DCO_reset_driver_input'}
    if set(channels)!=expected:raise ValueError('all 303 physical input channels required')
    receipts={str(capture):sha(capture), str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    result={}
    for role, entry in channels.items():
        path=Path(entry['file'])
        digest=data['artifacts'][str(path)]
        verify({str(path):digest})
        with path.open() as stream:
            result[role]=summarize(tuple(map(float,line.split())) for line in stream if line.strip())
        verify({str(path):digest})
        receipts[str(path)]=digest
    codes={}
    for epoch in ['initial','final']:
        codes[epoch]=dict(fine=sum(result[f'DCO_THERM[{i}]'][epoch+'_high'] for i in range(255)),
                         coarse=sum(not result[f'COARSETHERMAL_CODE[{i}]'][epoch+'_high'] for i in range(47)))
    save(output,dict(input_sha256=receipts, logical_endpoint_counts=codes, channels=result,
         transient_logic_excursion_channels=[p for p,r in result.items() if r['transient_logic_excursion']],
         threshold_voltage=0.9, physical_driver_inputs_observed=True,
         floating_charge_causality_proven=False, programming_history_qualified=False, release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.capture.resolve(),args.output.resolve())
