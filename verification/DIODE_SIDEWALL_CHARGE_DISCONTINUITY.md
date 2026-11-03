# Diode sidewall depletion-charge discontinuity: investigation and upstream status

Date: 2026-11-03. This report is intended as a reproducible starting point for simulator bug reports and pull requests. It distinguishes the observed defect, the local diagnostic corrections, ngspice's existing upstream fix, and validation still needed before a general-purpose patch is adopted.

## Findings

The ngspice and Xyce builds tested here use the **bottom-junction charge continuation constant in the forward sidewall charge branch**. When bottom and sidewall junction parameters differ, the two sidewall charge branches do not join continuously. Both simulators can abort with a timestep-too-small error when a transient crosses that transition.

This was reproduced independently of the PLL and PDK. Correcting the sidewall charge offset allows the small transient to finish. It does not by itself solve the PLL's runtime problem.

There is already an ngspice upstream fix. **Do not submit the same fix as a new ngspice issue or PR without checking the existing work.** Xyce still contains the shared-offset expression in the upstream revision inspected below.

## Versions and source provenance

| Item | Revision or scope |
|---|---|
| ngspice failing executable | Our pinned ngspice-47 KLU build; this is not a claim about every ngspice distribution |
| Xyce failing executable | Stock Xyce 7.10.0, MPI-enabled, using KLU |
| Existing ngspice report | [Bug #870: diode transient aborts at sidewall-capacitance transition](https://sourceforge.net/p/ngspice/bugs/870/), reported September 18, 2026; closed-fixed |
| ngspice fix author | Dietmar Warning |
| Exact upstream fix | [`149688cd39b5890eaa09a98b674d320e755784a0`](https://sourceforge.net/p/ngspice/ngspice/ci/149688cd39b5890eaa09a98b674d320e755784a0/), September 18, 2026, on `pre-master-48` |
| ngspice branch tip inspected | `3adcd96a02ff5aa408e5bc63d8e93dcfd84a14e3` |
| Xyce upstream revision inspected | [`e5b7b9bb5b221630c66654c059fc2d33524f5b21`](https://github.com/Xyce/Xyce/blob/e5b7b9bb5b221630c66654c059fc2d33524f5b21/src/DeviceModelPKG/OpenModels/N_DEV_Diode.C) |

The Xyce revision above contains the problematic expression in both normal evaluation and analytic-sensitivity evaluation. The exact ngspice fix was backported without fuzz to a separate copy of our ngspice-47 source. Only `diodefs.h`, `diotemp.c`, and `dioload.c` changed. The full diode library was rebuilt because the patch changes the diode instance layout.

Stock executables, installed PDK files, and manufacturing artifacts were not modified. Local corrected binaries were built separately. The source fixes described here are distinct from the fixed-temperature SKY130 model translation used to accommodate Xyce's supported diode models.

## Why charge is discontinuous

Let a junction have zero-bias capacitance `C0`, temperature-adjusted junction potential `phi`, grading coefficient `m`, and forward continuation fraction `f`. For `m != 1`, define:

```text
Vt = f * phi
F1(phi, m, f) = phi * [1 - (1 - f)^(1 - m)] / (1 - m)
```

Below the transition:

```text
Q(V) = C0 * phi * [1 - (1 - V/phi)^(1 - m)] / (1 - m)
C(V) = dQ/dV = C0 * (1 - V/phi)^(-m)
```

Above the transition, the usual linear-capacitance continuation can be written independently as:

```text
Q(V) = Q(Vt) + C(Vt)*(V - Vt) + 0.5*Cprime(Vt)*(V - Vt)^2
C(V) = C(Vt) + Cprime(Vt)*(V - Vt)
```

Each junction must therefore use **its own** `F1`. The sidewall uses its own potential, grading coefficient, and `FCS`; it must not reuse the bottom junction's `F1`, which depends on bottom potential, grading, and `FC`.

The failing implementations start the above-threshold sidewall term with a coefficient corresponding to:

```text
C0_sidewall * F1_bottom
```

The required coefficient is:

```text
C0_sidewall * F1_sidewall
```

The resulting charge jump is:

```text
DeltaQ = C0_sidewall * (F1_bottom - F1_sidewall)
```

The reported capacitance can remain continuous despite this charge jump. A finite capacitance does not make a discontinuous charge law valid for transient integration. This is why checking only DC current or small-signal capacitance misses the defect.

### Numerical example from the SKY130 investigation

For bottom potential `0.729 V`, bottom grading `0.44`, sidewall potential `0.2 V`, sidewall grading `0.0009`, and `FC=FCS=0.5`:

| Quantity | Value |
|---|---:|
| Sidewall transition | 0.1 V |
| Bottom `F1` | 0.41878164758093506 V |
| Continuous sidewall `F1` | 0.10002762215129181 V |
| Offset mismatch per unit sidewall capacitance | 0.31875402542964325 V |
| Charge jump for perimeter 2.64 um and unit corner multiplier | approximately 3.03e-17 C |

The last terminal samples from 20 failed stock traces—two geometries, five corners, and two simulators—place the inferred junction voltage within 1.39e-6 V of the sidewall transition. This inference uses terminal current and series resistance; the last failed internal Newton state is not asserted to be converged.

## Self-contained reproducer, without a PDK

The following generic model intentionally has unequal bottom and sidewall parameters. Its coefficients are a diagnostic example, not a foundry model. Run each simulator in a separate fresh directory.

### ngspice

Save as `diode_ngspice.cir`:

```spice
* Self-contained diode sidewall charge regression; no PDK required.
.model DSW D IS=1e-14 N=1 RS=0 CJ=1p M=.44 VJ=.729
+ CJSW=.25p MJSW=.2 PHP=.2 FC=.5 FCS=0.5 TM1=0 TNOM=27
VDRV drive 0 PWL(0 0 1n 0 2n -.5 3n -.5 4n 0 5n 0)
RDRV drive node 50
DTEST 0 node DSW AREA=1 PJ=1
.tran 5p 5n 0 5p
.temp 27
.options reltol=1e-6 abstol=1e-12 vntol=1e-9
.control
set wr_singlescale
set wr_vecnames
set numdgt=17
run
wrdata trace.tsv v(node)
quit
.endc
.end
```

Run:

```sh
ngspice -n -b diode_ngspice.cir > ngspice.log 2>&1
```

The `-n` option avoids startup-file changes. The control block writes `trace.tsv` in the working directory. Check both the log and the **last trace time**: the tested failing ngspice build returns process exit status zero even though transient analysis aborts.

### Xyce

Save as `diode_xyce.cir`:

```spice
* Self-contained diode sidewall charge regression; no PDK required.
.model DSW D IS=1e-14 N=1 RS=0 CJ=1p M=.44 VJ=.729
+ CJSW=.25p MJSW=.2 PHP=.2 FC=.5 FCS=0.5 TNOM=27
VDRV drive 0 PWL(0 0 1n 0 2n -.5 3n -.5 4n 0 5n 0)
RDRV drive node 50
DTEST 0 node DSW AREA=1 PJ=1
.tran 5p 5n 0 5p
.options device temp=27
.options nonlin reltol=1e-6 abstol=1e-12
.options timeint reltol=1e-6 abstol=1e-12
.PRINT TRAN FORMAT=STD PRECISION=17 FILE=trace.prn V(node)
.end
```

Run:

```sh
Xyce -linsolv klu diode_xyce.cir > xyce.log 2>&1
```

`trace.prn` is explicitly named in the netlist. No PDK translation or project-specific code is needed. The requested endpoint is 5 ns.

### Observed baseline results

| Executable | Baseline result |
|---|---|
| Pinned stock ngspice-47 | Stops near 1.264969941 ns; process exit status 0 |
| Stock Xyce 7.10.0 | Stops near 1.264968396 ns; process exit status 1 |
| Locally corrected ngspice | Reaches 5 ns |
| Locally corrected Xyce | Reaches 5 ns |
| Exact upstream ngspice #870 fix backported to our build | Reaches 5 ns |

These failures are from the self-contained generic reproducer above. They are different from the approximately 1.712 ns failure times in the project's SKY130 diode fixture.

## What upstream ngspice already changed

The September 18 fix contains seven insertions and one deletion across three files:

1. `diodefs.h` adds sidewall grading/continuation storage, including `DIOtF1SW`.
2. `diotemp.c` computes a separate sidewall continuation constant after updating temperature-dependent quantities.
3. `dioload.c` uses `DIOtF1SW` in the forward sidewall charge branch.

This is the same core correction as our diagnostic inline calculation. Upstream caches the value during temperature update rather than recomputing it inside the transient load function.

### Exact-backport comparison

The exact upstream commit was applied to an isolated copy of the same ngspice-47 build, without taking unrelated pre-master-48 changes. Both that backport and our local correction were run on the generic reproducer with these independent changes:

| Case | Temperature | FCS | TM1 | Upstream endpoint | Comparison with local fix |
|---|---:|---:|---:|---:|---|
| Nominal | 27 C | 0.5 | 0 | 5 ns | Entire waveform table exactly equal |
| Non-default sidewall fit | 27 C | 0.4 | 0 | 5 ns | Entire waveform table exactly equal |
| Cold | -40 C | 0.4 | 0 | 5 ns | Entire waveform table exactly equal |
| Hot | 125 C | 0.4 | 0 | 5 ns | Entire waveform table exactly equal |
| Cold grading-temperature coefficient | -40 C | 0.4 | 0.001 | 5 ns | Not identical; maximum interpolated node-voltage difference approximately 86.7 uV |
| Hot grading-temperature coefficient | 125 C | 0.4 | 0.001 | 5 ns | Not identical; maximum interpolated node-voltage difference approximately 0.330 uV |

Set `FCS` in the model, `.temp` in the ngspice deck, and add `TM1=0.001` to the model to reproduce the corresponding variations. Both corrected builds complete all six cases. A hot stock case also completes: not every temperature/source trajectory necessarily exposes a timestep failure.

The nonzero-`TM1` results are **not a generic equivalence certificate or a universal error bound**. Upstream computes the new offset using `DIOtGradingCoeffSW`, whereas our inline correction uses the sidewall grading coefficient used by the existing sidewall charge branches. In the inspected code, below-threshold sidewall charge and continuation coefficients still refer to `model->DIOgradingSWCoeff`. Consistent temperature treatment across those expressions deserves review before claiming equivalence for arbitrary `TM1/TM2`. This report does not assert that transient completion alone proves that broader behavior correct.

The pinned SKY130 diode model used in our 27 C investigation has `TM1=TM2=0`, so the distinction does not affect that tested model context. We should reuse or backport ngspice's existing fix for that scope rather than present our equivalent correction as a newly discovered upstream patch.

## Local Xyce correction and checks

For the diagnostic build, both normal and analytic-sensitivity expressions use a sidewall-specific offset derived from the sidewall potential, transition, and grading coefficient. The isolated rebuilt Xyce library differs in exactly `N_DEV_Diode.C.o`. No other archive member changes.

A production-quality Xyce patch should follow the same separation concept, including its temperature and sensitivity paths. It should not substitute a capacitance parameter or remove sidewall capacitance just to make a transient finish.

Checks completed in the project:

- Independent mathematical checks of charge continuity and `dQ/dV` versus capacitance on both sides of the transition, plus a negative control detecting the shared-offset defect.
- Ten paired native diode cases: both actual extracted geometries (`area=0.4347, perimeter=2.64` and `area=0.6417, perimeter=3.24`), all five process corners, at 27 C.
- DC, three sampled AC biases, and completed 3 ns forward/reverse transient comparisons using the explicitly corrected ngspice reference and corrected Xyce candidate.
- A complete 834-device fixture with the explicit resistor/diode adapters at one and four MPI ranks. MPI outputs match exactly at the sampled operating points.

The diode comparison limits were reused from the existing project comparison screen; they were not loosened after observing results:

| Comparison | Worst observed error | Existing limit |
|---|---:|---:|
| DC current, relative with a 1 pA denominator floor | 5.400e-4 | 1e-3 |
| AC complex current, relative | 4.863e-10 | 1e-4 |
| Integrated transient terminal current, relative | 1.535e-4 | 1e-3 |

Integrated terminal current includes conduction current; it is not claimed to be pure depletion charge. The mathematical continuity/derivative checks address the depletion-charge equation separately. These are sampled electrical controls, not statistical or universal device qualification. Noise and grading coefficients near one still need dedicated review.

The earlier test with extremely tight Xyce transient tolerances stopped at the first ramp. Correcting those numerical settings allowed it to advance, but the stock build still failed at forward sidewall continuation. Both failures were preserved. Tolerance relaxation alone was not accepted as a fix.

## What a simulator PR should contain

For Xyce:

- The self-contained failing netlist and explicit endpoint check.
- The continuity derivation and a minimal source change, covering normal and analytic-sensitivity code.
- A regression with unequal junction parameters and non-default `FCS`, and a zero-sidewall-capacitance control.
- Temperature coverage and a declared policy for grading-temperature coefficients.
- Charge/capacitance consistency and finite-difference sensitivity checks.
- Careful behavior near grading coefficient one. The analytic limit is `F1 = -phi*log(1-f)`; a numerically stable formulation should be considered rather than assuming the ordinary quotient remains well-conditioned.
- Confirmation that DC and applicable small-signal behavior remain unchanged.

For ngspice, reference issue #870 and commit `149688cd39b5890eaa09a98b674d320e755784a0`; do not submit a duplicate base fix. Additional regression coverage or a separately demonstrated temperature-consistency problem would be distinct contributions.

No PR, issue, comment, or message has been sent to either simulator project as part of this investigation.

## Scope and remaining PLL work

The charge correction removes a reproduced small-circuit failure. It does **not** establish a PLL speedup, loaded-model validity, or release readiness.

The assembled DC benchmark completed in 152.8 s at one MPI rank and 67.7 s at four ranks, a 2.26x speedup for that specific DC test. The subsequent full-capacitance Xyce run used the corrected executable, retained all 1,269,218 capacitor cards, and timed out after a 3,300-second native budget at approximately 19.05 ns of the requested 175 ns. Its partial waveform is not a completed programming assessment.

The PLL's remaining transient-runtime problem therefore persists **with the diode correction applied**. Neither the cause nor a solution to that broader performance bottleneck is established by these diode tests. All release gates remain open.

## Evidence retained locally

Raw project artifacts are not included in this documentation-only commit. The following relative workspace paths identify the retained investigation data:

- `build/signoff400/prototype_v3_diode_charge_discontinuity_review_027/assessment.json`: original stock endpoint/transition review.
- `build/tools/Xyce_diode_charge_fix_001/assessment.json`: isolated Xyce build and archive-member comparison.
- `build/tools/ngspice47_diode_charge_fix_001/assessment.json`: isolated local ngspice correction.
- `build/tools/ngspice_upstream_fix_review_001/backport_build.json`: exact upstream patch provenance and backport binary hash.
- `build/signoff400/diode_upstream_fix_reproducer_031/`: self-contained stock/local/upstream runs and waveform comparisons.
- `build/signoff400/prototype_v3_diode_charge_fix_controls_026/completed_review.json`: ten sampled SKY130 diode comparisons.
- `build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030/stop_review.json`: full-C run's terminal result.

This report embeds the small reproducer so maintainers can independently investigate without access to those workspace artifacts or the PLL layout.
