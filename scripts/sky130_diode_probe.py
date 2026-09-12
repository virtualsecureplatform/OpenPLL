#!/usr/bin/env python3
"""Compare one extracted SKY130 antenna diode in ngspice and Xyce/KLS.

Retains the PDK model and its geometry scaling unchanged. This is a model
compatibility diagnostic, not a substitute for PLL or physical-noise signoff.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess

from pll_verification import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdk', type=Path, required=True, help='sky130A directory')
    parser.add_argument('--xyce', type=Path, required=True)
    parser.add_argument('--ngspice', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corner', choices=['tt', 'ss', 'ff', 'sf', 'fs'], default='tt')
    parser.add_argument('--temperature-c', type=float, default=27)
    parser.add_argument('--bias-v', type=float, default=1.8)
    parser.add_argument('--area', type=float, default=4.347e11)
    parser.add_argument('--perim', type=float, default=2.64e6)
    args = parser.parse_args()
    if not all(math.isfinite(x) for x in [args.temperature_c, args.bias_v, args.area, args.perim]):
        parser.error('parameters must be finite')
    if args.area <= 0 or args.perim < 0 or args.temperature_c <= -273.15:
        parser.error('invalid geometry or temperature')
    out = args.output.resolve()
    if out.exists():
        parser.error('use a fresh output directory')
    out.mkdir(parents=True)
    pdk = args.pdk.resolve(strict=True)
    model_dir = pdk / 'libs.tech/ngspice'
    model = pdk / 'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    wrapper = model_dir / 'sky130_fd_pr__model__r+c.model.spice'
    parameters = {k: v for k, v in vars(args).items() if not isinstance(v, Path)}
    results = []
    inputs = [Path(__file__), pdk / 'libs.tech/ngspice', pdk / 'libs.ref/sky130_fd_pr/spice']
    for simulator in ['ngspice', 'xyce']:
        executable = getattr(args, simulator).resolve(strict=True)
        inputs.append(executable)
        for analysis in ['dc', 'ac']:
            base = out / f'{simulator}-{analysis}'
            deck = base.with_suffix('.cir')
            source = '0' if analysis == 'dc' else f'{args.bias_v:.17g} AC 1'
            sweep = '.dc Vbias -0.2 1.98 0.02' if analysis == 'dc' else '.ac lin 1 1meg 1meg'
            quantities = ('i(Vbias)' if analysis == 'dc' else
                          'real(vbias#branch) imag(vbias#branch)' if simulator == 'ngspice' else
                          'ir(Vbias) ii(Vbias)')
            deck.write_text(f'''* Unmodified extracted SKY130 antenna diode compatibility probe
.lib "{model_dir}/sky130.lib.spice" {args.corner}
Vbias bias 0 {source}
XD 0 bias sky130_fd_pr__diode_pw2nd_05v5 area={args.area:.17g} perim={args.perim:.17g}
.temp {args.temperature_c:.17g}
.options gmin=1e-18
{sweep}
.print {analysis} {quantities}
.end
''')
            inputs.append(deck)
            command = ([str(executable), '-b', str(deck)] if simulator == 'ngspice' else
                       [str(executable), '-linsolv', 'KLS', '-o', str(base), str(deck)])
            with base.with_suffix('.log').open('w') as log:
                try:
                    proc = subprocess.run(command, cwd=model_dir, stdout=log,
                                          stderr=subprocess.STDOUT, timeout=120)
                    returncode = proc.returncode
                except subprocess.TimeoutExpired:
                    returncode = None
            text = base.with_suffix('.log').read_text(errors='replace')
            warnings = [line.strip() for line in text.splitlines()
                        if re.search(r'warning|unrecognized|ignored|no valid model', line, re.I)]
            rows = []
            if simulator == 'ngspice':
                for line in text.splitlines():
                    fields = line.split()
                    if len(fields) >= 3 and fields[0].isdigit():
                        try:
                            rows.append([float(v) for v in fields[1:]])
                        except ValueError:
                            pass
            else:
                for data in [base.with_suffix('.FD.prn'), base.with_suffix('.prn')]:
                    if data.exists():
                        for line in data.read_text().splitlines():
                            fields = line.split()
                            if len(fields) >= 3 and fields[0].isdigit():
                                rows.append([float(v) for v in fields[1:]])
            result = dict(simulator=simulator, analysis=analysis, command=command,
                          returncode=returncode, completed=returncode == 0 and bool(rows),
                          warnings=warnings, data=rows)
            if analysis == 'ac' and rows and len(rows[0]) == 3:
                result['capacitance_f'] = -rows[0][2] / (2 * math.pi * rows[0][0])
            results.append(result)
    report = dict(parameters=parameters, model=str(model), wrapper=str(wrapper),
                  provenance=fingerprint(inputs, parameters), results=results,
                  completed=all(r['completed'] for r in results), qualified=False,
                  limitation='Unmodified-model compatibility only; warnings and cross-simulator differences require review.')
    (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['provenance', 'results']}, indent=2))
    return 0 if report['completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
