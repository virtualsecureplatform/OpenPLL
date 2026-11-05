#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare a fixed-temperature diode translation with the pinned ngspice model.

Diagnostic only. This does not qualify noise or authorize PLL model replacement.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

MODEL_SHA256 = "ca6cc52ed9449e0e57a2d212aa94582083f4c67f94689d3c384a029919d4aded"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(path):
    records = [f"{p.relative_to(path)} {digest(p)}" for p in sorted(path.rglob("*")) if p.is_file()]
    return hashlib.sha256("\n".join(records).encode()).hexdigest()


def data_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields and fields[0].isdigit():
            try:
                rows.append([float(x) for x in fields[1:]])
            except ValueError:
                pass
    return rows


def translated_model(temperature_c, aj, pj):
    t = temperature_c + 273.15
    tref = 303.15
    k = 8.617333262145e-5
    def saturation(value, n):
        return value * math.exp((t / tref - 1) * 1.05 / (n * k * t)
                               + 2 / n * math.log(t / tref))
    # ngspice's omitted NS uses 1 for sidewall temperature scaling, then
    # merges that current with the bottom current for the N-based I/V law.
    return f"""* Diagnostic translation, fixed at {temperature_c:g} C; not release qualified.
.model openpll_pw2nd_candidate D level=1
+ IS={saturation(2.75e-15, 1.2928):.17g} JSW={saturation(6e-16, 1):.17g}
+ N=1.2928 NS=1.2928 RS=981 IKF=1300 BV=11.7 IBV=0.00106 NBV=1.2928
+ CJ={1.3459e-15 * aj * (1 + .000792 * (temperature_c - 27)):.17g}
+ M=.44 VJ={.729 - .0012287 * (temperature_c - 27):.17g}
+ CJSW={3.6001e-17 * pj * (1 + 1e-5 * (temperature_c - 27)):.17g}
+ MJSW=.0009 PHP=.2 EG=1.05 XTI=2 TNOM={temperature_c:.17g}
"""


def run(command, deck, log, cwd):
    with log.open("w") as output:
        result = subprocess.run(command + [str(deck)], cwd=cwd, stdout=output,
                                stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise RuntimeError(f"simulation failed ({result.returncode}): {log}")


def charge(rows, start=0.9e-9, stop=1.5e-9):
    # Integrate the complete rising edge, including the capacitor's series-R tail.
    samples = [(r[0], r[-1]) for r in rows if start <= r[0] <= stop]
    if len(samples) < 20:
        raise ValueError("insufficient transient samples for charge comparison")
    return sum((b[0] - a[0]) * (a[1] + b[1]) / 2
               for a, b in zip(samples, samples[1:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", type=Path, required=True)
    parser.add_argument("--ngspice", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corners", default="tt,ff,ss,sf,fs")
    parser.add_argument("--temperatures", default="-40,27,125")
    parser.add_argument("--ac-biases", default="0,0.81,1.62,1.8,1.95")
    parser.add_argument("--reference-geometry", choices=("scaled-by-option", "explicit"),
                        default="scaled-by-option",
                        help="ngspice 42 scales explicit diode geometry; ngspice 47 requires explicit effective geometry")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    pdk = args.pdk.resolve(strict=True)
    image = args.image.resolve(strict=True)
    ngspice = args.ngspice.resolve(strict=True)
    model = pdk / "libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice"
    if digest(model) != MODEL_SHA256:
        parser.error("diode model differs from the model used to derive this diagnostic")
    corners = args.corners.split(",")
    temperatures = [float(t) for t in args.temperatures.split(",")]
    ac_biases = [float(v) for v in args.ac_biases.split(",")]
    if (not corners or any(c not in ("tt", "ff", "ss", "sf", "fs") for c in corners)
            or any(not math.isfinite(t) or t <= -273.15 for t in temperatures)
            or not ac_biases or any(not math.isfinite(v) or v < 0 or v > 1.95 for v in ac_biases)
            or len(set(ac_biases)) != len(ac_biases) or args.jobs < 1):
        parser.error("invalid corner, temperature, or worker count")
    out = args.output.resolve()
    if out.exists():
        parser.error("use a fresh output directory")
    out.mkdir(parents=True)
    input_hashes = {str(model): digest(model), str(ngspice): digest(ngspice),
                    str(image): digest(image), str(Path(__file__)): digest(Path(__file__)),
                    "pdk_tree": tree_digest(pdk)}
    xyce_prefix = ["apptainer", "exec", "--userns", "--writable-tmpfs", "--cleanenv",
                   "--bind", f"{root}:{root}", "--pwd", str(root), str(image),
                   "/opt/xyce/bin/Xyce", "-linsolv", "KLU"]
    lib = pdk / "libs.tech/ngspice/sky130.lib.spice"

    def corner_parameters(corner):
        deck = out / f"parameters_{corner}.cir"
        deck.write_text(f"""* Evaluate junction multipliers from the complete pinned PDK.
.lib "{lib}" {corner}
BA aj 0 V={{sky130_fd_pr__nfet_01v8__ajunction_mult}}
BP pj 0 V={{sky130_fd_pr__nfet_01v8__pjunction_mult}}
.op
.options numdgt=15
.print op V(aj) V(pj)
.end
""")
        log = deck.with_suffix(".log")
        run([str(ngspice), "-b"], deck, log, lib.parent)
        rows = data_rows(log)
        if len(rows) != 1 or len(rows[0]) != 2:
            raise ValueError(f"missing corner multipliers: {log}")
        return corner, rows[0]

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        parameters = dict(pool.map(corner_parameters, corners))
    wrapper_text = (pdk / "libs.tech/ngspice/sky130_fd_pr__model__r+c.model.spice").read_text()
    wrapper = re.search(r"(?im)^\.subckt sky130_fd_pr__diode_pw2nd_05v5 N P[^\n]*\n.*?\n\.ends", wrapper_text)
    if wrapper is None:
        raise ValueError("the pinned diode wrapper is missing")

    def case(item):
        corner, temperature = item
        aj, pj = parameters[corner]
        folder = out / f"{corner}_{temperature:g}C"
        folder.mkdir()
        results = {}
        for simulator in ("ngspice", "xyce"):
            if simulator == "ngspice":
                geometry = ("area=.6417 perim=3.24" if args.reference_geometry == "explicit"
                            else "area=6.417e11 perim=3.24e6")
                device = "XD 0 bias sky130_fd_pr__diode_pw2nd_05v5 " + geometry
                models = f""".option scale=1u
.param sky130_fd_pr__nfet_01v8__ajunction_mult={aj:.17g}
.param sky130_fd_pr__nfet_01v8__pjunction_mult={pj:.17g}
.include "{model}"
{wrapper.group(0)}
"""
                options = ".options gmin=1e-18 reltol=1e-8 abstol=1e-24 vntol=1e-12 numdgt=15"
            else:
                device = "D0 0 bias openpll_pw2nd_candidate area=.6417 pj=3.24"
                models = translated_model(temperature, aj, pj)
                options = ".options device gmin=1e-18\n.options nonlin reltol=1e-8 abstol=1e-24"
            analyses = [("dc", None), *(("ac", v) for v in ac_biases), ("tran", None)]
            for analysis, bias in analyses:
                analysis_options = options
                if analysis == "dc":
                    source, sweep, quantity = "0", ".dc Vbias -.2 1.95 .025", "V(bias) I(Vbias)"
                elif analysis == "ac":
                    source, sweep = f"{bias:.17g} AC 1", ".ac dec 5 1meg 10g"
                    quantity = ("real(vbias#branch) imag(vbias#branch)" if simulator == "ngspice"
                                else "ir(Vbias) ii(Vbias)")
                else:
                    source = "PULSE(0 1.95 1n 20p 20p 4n 10n)"
                    sweep, quantity = ".tran 2p 8n 0 2p", "V(bias) I(Vbias)"
                    analysis_options = (".options gmin=1e-18 reltol=1e-6 abstol=1e-14 vntol=1e-10 numdgt=15"
                                        if simulator == "ngspice" else
                                        ".options device gmin=1e-18\n.options nonlin reltol=1e-6 abstol=1e-14\n"
                                        ".options timeint reltol=1e-6 abstol=1e-12")
                label = analysis if bias is None else f"ac_{bias:g}V"
                base = folder / f"{simulator}_{label}"
                deck = Path(str(base) + ".cir")
                deck.write_text(f"""* Pinned diode translation diagnostic: {corner}, {temperature:g} C.
{models}
Vbias bias 0 {source}
{device}
{'.options device temp=' if simulator == 'xyce' else '.temp '}{temperature:.17g}
{analysis_options}
{sweep}
.print {analysis} {quantity}
.end
""")
                log = Path(str(base) + ".log")
                command = ([str(ngspice), "-b"] if simulator == "ngspice" else
                           xyce_prefix + ["-o", str(base)])
                run(command, deck, log, folder)
                data = (log if simulator == "ngspice" else
                        Path(str(base) + (".FD.prn" if analysis == "ac" else ".prn")))
                rows = data_rows(data)
                if not rows:
                    raise ValueError(f"simulation produced no rows: {data}")
                results[simulator, label] = rows
        dc_ref, dc_got = results["ngspice", "dc"], results["xyce", "dc"]
        ac_pairs = [(results["ngspice", f"ac_{v:g}V"], results["xyce", f"ac_{v:g}V"])
                    for v in ac_biases]
        if (len(dc_ref) != len(dc_got) or len(dc_ref) != 87
                or any(len(a) != 21 or len(a) != len(b) for a, b in ac_pairs)):
            raise ValueError("incomplete DC or AC comparison")
        if any(abs(a[-2] - b[-2]) > 1e-10 for a, b in zip(dc_ref, dc_got)):
            raise ValueError("DC biases differ")
        if any(abs(a[0] / b[0] - 1) > 1e-6 for ar, ag in ac_pairs for a, b in zip(ar, ag)):
            raise ValueError("AC frequencies differ")
        dc_error = max(abs(a[-1] - b[-1]) / max(abs(a[-1]), 1e-18)
                       for a, b in zip(dc_ref, dc_got))
        ac_error = max(abs(a[-1] - b[-1]) / abs(a[-1])
                       for ar, ag in ac_pairs for a, b in zip(ar, ag))
        ac_complex_error = max(abs(complex(a[-2], a[-1]) - complex(b[-2], b[-1]))
                               / abs(complex(a[-2], a[-1]))
                               for ar, ag in ac_pairs for a, b in zip(ar, ag))
        q_ref = charge(results["ngspice", "tran"])
        q_got = charge(results["xyce", "tran"])
        q_error = abs(q_ref - q_got) / abs(q_ref)
        falling_ref = charge(results["ngspice", "tran"], 5e-9, 5.6e-9)
        falling_got = charge(results["xyce", "tran"], 5e-9, 5.6e-9)
        falling_error = abs(falling_ref - falling_got) / abs(falling_ref)
        return {"corner": corner, "temperature_c": temperature,
                "dc_relative_error": dc_error, "ac_imaginary_current_relative_error": ac_error,
                "ac_complex_current_relative_error": ac_complex_error,
                "reference_rising_charge_c": q_ref, "candidate_rising_charge_c": q_got,
                "charge_relative_error": q_error,
                "falling_charge_relative_error": falling_error,
                "screen_passed": dc_error < .001 and ac_error < .0001
                                 and ac_complex_error < .0001 and q_error < .001
                                 and falling_error < .001}

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(case, [(c, t) for c in corners for t in temperatures]))
    report = {"qualified": False, "effective_geometry": {"area_um2": .6417, "perimeter_um": 3.24}, "noise_verified": False,
              "scope": "fixed-temperature diode DC, multiple-bias AC, and rising/falling charge screening only",
              "ac_biases_v": ac_biases,
              "reference_geometry": args.reference_geometry,
              "corner_parameters": parameters, "cases": results,
              "all_screens_passed": all(r["screen_passed"] for r in results),
              "input_sha256": input_hashes}
    if digest(Path(__file__)) != input_hashes[str(Path(__file__))] or tree_digest(pdk) != input_hashes["pdk_tree"]:
        raise ValueError("diagnostic inputs changed while simulations were running")
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "input_sha256"}, indent=2))
    return 0 if report["all_screens_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
