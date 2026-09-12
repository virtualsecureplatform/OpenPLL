# OpenPLL completion implementation

Baseline: 25 MHz reference, KLS, five output modes (100/250/300/400/500 MHz).
The approved provisional criteria are in `engineering.json`. The configured
external PLL interface is to be preserved. This document separates implemented
infrastructure from verified design outcomes; the complete PLL is not signed off.
The user clarified the optimization policy on 2026-09-12: no power limit;
functional performance takes priority over area. Characterize physical jitter,
area and power, report the measured tradeoff frontier among functional candidates,
then set numerical jitter/area objectives. A finite candidate search does not
establish global Pareto optimality.

Candidate comparison must report total implemented PLL area (with macro area
separately identified), physical RMS jitter with its integration bounds and
measurement method, period/cycle-to-cycle variation, output load, operating mode,
PVT and measured power. Compare candidates under the same conditions; do not rank
different jitter bandwidths as equivalent measurements. Deterministic edge
variation alone cannot supply the physical-noise result. Application-specific
clock timing limits remain deferred until these functional tradeoffs are known.

## Development priority (2026-09-12)

The user requested resuming PLL development after preserving the solver work.
KLS remains the selected solver. A separate singleton-metadata defect has a
deterministic regression and fix; the historical segmentation fault remains
unresolved and is not currently reproducible on demand, including with saved
unfixed executables. Continue DCO compatibility, tuning coverage and acquisition
work, while retaining solver reliability as a qualification gate. See the KLS
repository’s `docs/openpll-crash-investigation.md` for the evidence.

## Current physical candidate and blockers

The experimental `IntegerPLL_DCO_STRENGTH_DIV` combines selectable parallel
inverter strength, 255 independent fine loads and /1, /2, /4, /8 output division.
The `candidate-strength-2` layout completed routing, Magic and KLayout DRC and
LVS with zero reported errors. Its 120 by 120 micrometre die is 14,400 square
micrometres; this is DCO macro area, not total PLL area. Reported maximum-slew
(449) and maximum-capacitance (192) violations remain unresolved, so this is not
timing signoff.

All-net extraction reports 2,241/2,241 nets and 54,675 resistors, reduced to
39,088 while retaining device and capacitor terminals. The initial SS fastest
and FF slowest KLS screens both fail during parsing: extracted antenna-diode
wrappers report no valid model for D0. Six extracted antenna diodes require
validated PDK/Xyce compatibility and parameter scaling before these runs can
establish frequency coverage. No frequency or jitter claim is made from them.

The preceding four-driver candidate reached approximately 542 MHz at its slow
corner with coarse code 0 / fine code 8, but coarse code 1 / fine code 247 was
only approximately 293 MHz. This coarse gap prevents treating its fastest-band
result as proof of complete mode coverage. KLS refactor crashes also remain
unresolved; fresh numerical factorization is a diagnostic option, not an
established solver fix or a replacement performance benchmark.

## Implemented

- Independent trace acceptance: four final 5120 ns windows, 1000 ppm frequency,
  output-period-scaled phase mean/span/drift, cycle-slip and rail rejection,
  acquisition deadline measured from the stimulus. Missing evidence fails.
- Content hashes for simulation inputs, recursive PDK contents, solver binary,
  RTL, and numerical settings. Old cache entries without matching provenance
  are rerun. Failed runs cannot become successful cache hits.
- Explicit voltage/temperature controls in extracted DCO decks and measurements.
- Continuous-phase calibrated DCO in the RTL/Xyce bridge, preserving phase on
  tuning changes. Mode/PVT model metadata is checked before simulation.
  Historical 1 ps rounding is available only as an explicit diagnostic option
  in the Python runner (the low-level binary retains its compatibility default).
- Constant-resistor Schur reduction preserving device/capacitor terminals and
  ports. Independent complex-admittance tests cover DC through 1 THz. Nonlinear
  transient equivalence at converged tolerances still needs verification.
- Resumable band-screen and numerical-convergence campaign runner. Frequency
  uses the complete measurement window; truncated waveforms cannot pass.
- Separate synthesizable frequency-acquisition engine: Gray DCO counter into
  REFCLK, all-band midpoint scan, closest-three endpoint checks, seed
  interpolation for either fine polarity, doubled measurement on ambiguity,
  mode-change restart, frequency/rail monitoring, and retry after stopped-clock
  failure. RUN_FINE means handoff readiness, not phase lock.
- Experimental `IntegerPLL_AcquiringCore` connects that engine to the real DLF
  and divider. A single-outstanding bundled-data transfer holds each seed/mode/
  gain command until acknowledged after three destination clocks. Measurement
  waits for application; a stopped-clock acknowledgement times out and retries.
  Reset release and fine-loop release are synchronized into their clock domains.
  Coarse selection remains reference-owned so it can restart a stopped DCO.
- The mixed bridge accepts `--acquisition` with a complete 48-band JSON model,
  preserving oscillator phase across coarse changes. Replay checks REFCLK and
  coarse outputs as well as the existing fine-loop boundary. `--smoke-only`
  permits short infrastructure diagnostics but forces engineering acceptance false.

## Evidence recorded in the workspace

Artifacts are under `../build/openpll-verification/` relative to this repository.

- Initial resistance-enabled DCO: 106,848 resistors; BBPD: 74,726 resistors.
  Audit found that Magic's default threshold extracted only 308 of 1,300 DCO
  nets (mostly external nets). These are not yet verified all-net RC models.
  `magic_full_rcx.py` explicitly runs `extresist all` with simplification off;
  replacement models are under `all-net-rc/DCO-v3` and `all-net-rc/BBPD-magic`.
  DCO extraction now reports 1,298/1,300 nets and 132,239 resistors (59,780 after
  exact resistor reduction); BBPD reports 56/58 nets and 75,077 resistors.
  Body-bias nets have zero lumped route resistance; the remaining-net accounting
  still needs to be included in extraction qualification.
  DCO source SHA256:
  `d16164da76ffa408a0008bff96a82472c879a0b0d9639b53c60c3dee76e132b5`.
  BBPD source SHA256:
  `c7332d9731980be69e587f386700f469cd793f14e08f63a63451a6f7b7535511`.
- Degree-eight DCO reduction: 42,613 resistors, 50,832 eliminated internal nodes.
  The 40 ns TT/1.8 V/27 C C17/code235 KLS pilot completed, reporting about
  88.3127 MHz from the existing short measurement. This is a startup screen,
  not a converged calibration. The older capacitance-only ~100 MHz preset is
  therefore not suitable for promotion based on the current evidence.
- Unreduced and degree-three reduced KLS pilots crashed. Stack traces point to
  BSIM4 Jacobian loading and KLU transpose solve called through KLS respectively.
  Root cause remains under investigation; solver memory instrumentation and an
  unreduced KLU control run are used diagnostically. KLS remains the baseline.
  The KLU control reached 40.056 ns without a crash and was deliberately stopped;
  its partial waveform is not calibration evidence.
  A KLS AddressSanitizer/UndefinedBehaviorSanitizer build completed the reduced
  40 ns deck without an error report. This does not resolve the intermittent
  optimized-build crashes. Reproduction provenance is retained in
  `crash-diagnostic/asan-provenance.json`.
- A separate 60 ns KLS run at SS/1.62 V/125 C, C0/code255 completed. Across nine
  periods after 20 ns it measured 233.14094 MHz; the two half-window estimates
  differed by 7.68 Hz. Timestep/tolerance convergence has not yet been established.
  This setting is intended to be the fastest (shortest mirror path, no enabled
  fine loads), so the 500 MHz PVT requirement is a serious DCO redesign gate.
  Do not treat this one setting as a completed all-band coverage sweep.
- Continuous-phase 2 us RTL/Xyce smoke completed; 503 boundary evaluations
  matched independent Icarus replay. It correctly fails engineering acceptance
  for insufficient observation time and uses an unqualified capacitance model.
  A second 2 us smoke loaded an explicit JSON calibration at 3 ns reference
  offset; all 483 recorded boundary evaluations matched replay.
- Nine trace/provenance, three numerical-calibration, three resistor
  reduction, and five parallel-driver validation tests pass. The C++ oscillator test passes with assertions active
  in Release builds. Existing four configured PLL regressions pass.
- Standalone acquisition simulation covers all five modes, nonmonotonic band
  ordering, reverse fine polarity, misleading closest-band rejection, invalid
  mode, mode changes, frequency/rail loss, stopped oscillator and automatic
  recovery, with oscillator offsets 0/7/10/20/30 ns. Synthetic handoff is about
  80 us normally and 111 us with a rejected candidate; this excludes subsequent
  BBPD settling and is not a lock-time result.
  Yosys process/check and Verilator lint were run on the standalone module.
- Integrated acquisition tests pass at all five offsets, with about 86 us normal
  handoff and 119 us for the rejected-candidate case. They exercise the real DLF
  seed loading, mode changes, invalid mode, disable, stopped-clock recovery and
  reset during a command transfer. These synthetic-clock results exclude BBPD
  settling. Integrated Verilator lint and Yosys process/check also pass; physical
  CDC constraints and timing are still required.
- A 2 us KLS/BBPD/48-band synthetic-model bridge smoke completed; all 1,763
  boundary evaluations matched independent Icarus replay. It does not reach
  tracking and correctly reports engineering acceptance false. The historical
  nine-column 503-evaluation replay still passes after the bridge extension.

## Experimental DCO redesign

`sky130/IntegerPLL_DCO_einvp_coarse_v2_sky130.v` and its matching OpenLane
configuration are experimental. They retain all external macro ports, replace
NAND fine loads with enabled-inverter loads, parallel three shortest-path
drivers, reduce the die to 140 x 140 um, and distribute controls across four
sides. Production source and preset tables have not been replaced.

V2 completed layout with zero routing/Magic/KLayout DRC and LVS errors. Its
all-net extraction has 1,812/1,814 nets and 92,801 resistors (72,035 after exact
reduction). SS/1.62 V/125 C C0/code247 completed 30 ns, with an initial two-period
estimate of 306.66 MHz. Code8 crashed in KLS mapped refactor at about 12.19 ns.

V3 (`IntegerPLL_DCO_einvp_coarse_v3_sky130.v`) uses four parallel copies of each
of the three critical drivers and 128 physical fine loads on even thermometer
bits. Paired external codes alias, so effective resolution must be characterized
explicitly; the existing adjacent-code convergence checker must not be bypassed.
V3 also has zero routing/Magic/KLayout DRC and LVS errors. Both candidates have
19,600 um^2 DCO die area; this is not total PLL area. V3 all-net extraction has
1,312/1,314 nets and 88,476 resistors (70,934 after exact reduction).
Its SS code247 SERIAL-backend run crashed at about 22.39 ns; the partial waveform
suggests approximately 603 MHz, but cannot establish tuning coverage or convergence.
SERIAL selects a different factor policy but still reaches KLS mapped refactor.
A fresh-factor diagnostic (`KLS_REFACTOR=0`, exposed by `--kls-fresh-factor`) is
being evaluated. Default refactor behavior is preserved; the defect is not fixed.
Both one-rank and four-rank adapter regressions pass with refactor on and off.
The instrumented V2/code8 rerun completed 30 ns without an ASAN/UBSAN report;
its four-period mean is 248.98485 MHz. This does not explain the optimized crash.
A separately fingerprinted `-fno-strict-aliasing` build is another compiler
diagnostic, not an adopted fix or a performance comparison.

Initial ideal-wire SS/1.62 V/125 C screens of a two-position fast-path proxy show
about 341--591 MHz with one driver copy and up to 897 MHz with two copies.
The high-code points still show settling sensitivity, so these are feasibility
screens, not qualified tuning curves. The actual 48-band layout must be
extracted and recharacterized. Files are in `drive-screen/`.

The parallel drivers intentionally trigger three Yosys multiple-driver checks.
`check_parallel_dco.py` verifies identical cell types, parameters, and complete
connections, exactly three known parallel output groups, and no additional synthesis
diagnostics. Its hashed report permits this experimental layout to continue
with a run-local `ERROR_ON_SYNTH_CHECKS=false` override after synthesis. This is
not a general synthesis-check waiver or production signoff. The tracked config
keeps the normal checker enabled. Physical DRC/LVS and extracted behavior remain
required; the candidate flow is under `physical/IntegerPLL_DCO_EINVP_COARSE_V2/`.

## Execution gates still open

1. **Reliable extracted simulation.** Resolve the crash, compare reduced/full
   transients, converge timestep/tolerances and settling. Pin resulting binaries
   and all source hashes again after any fix.
2. **Physical tuning coverage.** Screen all 48 bands, measure suitable bands
   across 45 PVT points, require target inside codes 8..247. Qualify numerical
   convergence against both 100 ppm and a quarter local fine LSB. Validate
   interpolation independently (the campaign currently marks it unvalidated).
   Redesign and regenerate DCO layout if any target is unreachable.
3. **Controller integration.** Qualify the implemented handoff with measured
   oscillator curves, constrain Gray-bus skew and bundled-data paths, audit CDC
   and timing, then connect the qualified configuration to production wrappers.
   The experimental acquiring core is connected to the mixed simulator.
   Its parameter ranges must stay within the 16-bit edge/count counters.
4. **Acquisition/relock campaign.** Load qualified multi-band/PVT models, sweep
   initial fine code and reference phase, tune gains, and test enable, reset,
   every mode change and disturbances. Confirm four passing windows by 200 us
   from each stimulus. Select representative extracted BBPD/DCO convergence
   runs; retain replay and complete provenance.
5. **Physical characterization.** Characterize device noise, mismatch, period
   jitter/phase noise, supply sensitivity, power and area. Agree application
   limits after measuring the functional candidates, following the user's
   performance-first tradeoff policy. Deterministic co-simulation is not physical jitter.
6. **Production release.** Promote only qualified presets and controller logic,
   regenerate layouts, run DRC/LVS, timing/reset/CDC and the existing
   `check-sky130-pll-25mhz-release` gate. Its old preset assertions must change
   only with corresponding replacement evidence. No release claim is justified
   by the historical acquisition diagnostics alone.

## Reproduction entry points

Run from the OpenPLL repository:

```sh
make check-pll-verification check-frequency-acquisition
cmake --build ../build/openpll-cinterface --target test_calibrated_dco
ctest --test-dir ../build/openpll-cinterface -R calibrated_dco_phase --output-on-failure
python3 scripts/dco_calibration.py --help
python3 scripts/magic_full_rcx.py --help
```

`dco_calibration.py screen` defaults to all 48 coarse bands at codes 8/128/247.
Use `--pvt-grid` for the approved 45 PVT points. `qualify --coarse N --mode-mhz M`
compares baseline, tighter tolerances, half timestep, and longer settling/window
on anchors and adjacent codes. Each command requires explicit `--xyce`,
`--pdk-root`, `--rcx-netlist`, and `--output`. The runner always selects KLS and
uses provenance-checked resume. Its sparse table does not by itself establish
interpolation accuracy or physical-noise qualification.
