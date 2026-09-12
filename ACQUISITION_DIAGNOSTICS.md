# Acquisition diagnostics

The configured regressions check their documented frequency/code criteria. They do not establish acquisition from arbitrary phase and initial fine code. The diagnostic below additionally measures phase over windows and records failures as data.

```sh
python3 scripts/pll_100mhz_acquisition.py --output build/acquisition_100mhz
```

This runs the production RTL/controller with behavioral BBPD and DCO models for 80 us at each of seven initial codes and four reference phases. It requires Icarus Verilog and Python with NumPy. Results include traces, commands, per-window metrics, and `summary.json`. A successful process exit means the simulations completed; inspect `screen_pass` for the tracking outcome.

The diagnostic criteria are a 5120 ns window, frequency within 1 MHz of 100 MHz, unwrapped phase span at most 10 ns, fitted phase drift at most 2 ns, wrapped mean phase within 5 ns, and no code rails. These are screening choices, not a PLL specification or jitter signoff.

For a separately characterized DCO band:

```sh
python3 scripts/pll_100mhz_acquisition.py \
  --coarse-code 17 --seeds 0,219,231,235,239,251,255 \
  --dco-model /absolute/path/to/IntegerPLL_DCO_c17_model.v \
  --output build/acquisition_calibrated
```

The supplied model must implement the same `IntegerPLL_DCO` module interface as `models/IntegerPLL_DCO_25MHzCoarse_model.v`. The coarse override, initial seed, and optional `--ki`/`--kp` gain overrides are diagnostic inputs; they do not modify the production mode table. Preserve model provenance, extraction settings, PDK version, measurement intervals, and interpolation limitations with the results.

Extracted-BBPD C-interface tests use an external C++ loop filter and decisions based on UP/DN pulse widths over a reference period. The RTL captures the first UP/DN event, synchronizes it using PLLOUT, and applies a clocked loop-filter update. Those tests are useful independent checks, but their acquisition results are not interchangeable. Enable the C++ proportional rail guard explicitly when comparing against the configured RTL guard; it is disabled by default in the smoke driver.

A newly regenerated layout/PDK must be characterized before reusing historical presets. An average frequency near 100 MHz, particularly at a fine-code endpoint, does not establish sufficient tuning range or bounded phase.

For frequency calibration with Xyce, select integration accuracy explicitly; `--step-ps` is not a maximum timestep:

```sh
python3 scripts/spice_dco_postlayout.py --simulator xyce \
  --xyce-reltol 1e-4 --xyce-abstol 1e-8 --max-step-ps 20 \
  --sim-time-ns 80 --meas-start-ns 40 \
  --coarse-codes 17 --codes 0,128,255 \
  --rcx-netlist /absolute/path/to/extracted.spice \
  --subckt-name IntegerPLL_DCO_EINVP_COARSE
```

Also supply your Xyce executable and PDK root as needed. Check frequency convergence at tighter tolerances before accepting a preset. The initial default-tolerance regenerated C16 measurements shifted materially when transient accuracy was tightened; those initial numbers must not be used as a physical calibration reference.

Gain diagnostics can use `--ki 4 --kp 4 --duration-ns 160000`. Longer acquisition and smaller steady oscillation are distinct tradeoffs; compare sustained tracking windows as well as the final window. Behavioral period variation excludes transistor noise, supply noise, and switching transients in the extracted DCO.

## Production RTL with extracted BBPD

The optional `xyce_pll_rtl_cosim` target links Verilator's translation of the
unchanged production mode controller, digital core, divider, and DLF to Xyce.
`tb/IntegerPLL_Cosim.v` supplies diagnostic C17/seed/gain overrides. The BBPD
transistors and extracted capacitances run in Xyce with KLS; the oscillator is a
behavioral interpolation of measured frequency points. The Python runner now
defaults to continuous phase accumulation, including phase preservation when
the tuning code changes. This is an actual-RTL hybrid test, not an extracted full PLL or
noise simulation. The production preset table remains unchanged.

Enable the target in an already configured C-interface build:

```sh
cmake -S tools/xyce_cinterface_smoke -B /absolute/path/to/cinterface-build \
  -DOPENPLL_RTL_COSIM=ON
cmake --build /absolute/path/to/cinterface-build --target xyce_pll_rtl_cosim
python3 scripts/pll_rtl_cosim.py \
  --base-deck /absolute/path/to/extracted-bbpd-model-deck.cir \
  --binary /absolute/path/to/cinterface-build/xyce_pll_rtl_cosim \
  --output /absolute/path/to/fresh-result-directory \
  --seed 235 --ki 4 --kp 4 --phase-ns 0 --duration-ns 160000 --step-ps 50
```

Verilator must be installed with its CMake package. An initial C-interface build
also requires the Xyce paths/static-library configuration documented by its CMake
cache variables. `--base-deck` supplies only `.lib` and `.include` lines; use
absolute model paths. It must define `IntegerPLL_BBPD` with the generated macro's
pin order. The runner generates its own DAC/ADC, reset and solver configuration.
The default C17 points are unqualified capacitance-only diagnostic values.
Use `--dco-model model.json` for another calibration: the JSON must contain
`mode_mhz`, `corner`, `vdd`, `temperature_c`, `coarse`, and `points`
(objects containing `code` and `mhz`, covering codes 0 through 255).
The selected mode/PVT must match the model metadata. Recalibrate for any change
to the layout, extraction, PDK, voltage, or temperature. Provenance hashes cover
the model files, simulator binary, RTL, and acceptance criteria.

Use `--acquisition` to exercise the experimental reference-clock acquisition
engine, acknowledged tuning handoff, and real digital core. Its JSON model uses
the same mode/PVT metadata but replaces the top-level `coarse`/`points` with
`bands`: 48 objects in coarse-code order, each containing `coarse` and `points`
covering fine codes 0..255. Coarse changes preserve oscillator phase. This path
has no production preset dependency; gains remain explicit diagnostic inputs.
For a short bridge test before handoff, `--smoke-only --duration-ns 2000` permits
completion without tracking and forces engineering acceptance false. Synthetic
models validate infrastructure only. Qualified acquisition runs require measured
curves, converged BBPD coupling, and the full observation/deadline checks.

The replay checker accepts both historical nine-column traces and the current
eleven-column format, which adds REFCLK and expected coarse code. Pass
`--acquisition` to the checker for an acquiring-core run, together with the same
mode divider and gain arguments used in the simulation.

The RTL drives the feedback-divider input and the BBPD reset, including the
controller's clear/enable gating. System reset releases at 200 ns; PLL enable
asserts at 280 ns. Reference edges have 20 ps ramps. Both BBPD outputs use a 0.9 V
threshold without added ADC settling delay. All ADC transitions are applied in
time order at the accepted integration endpoint, followed by scheduled digital
clock events. Simultaneous ADC changes are applied together. The maximum analog
step is also the coupling-step limit (up to 50 ps); repeat at a smaller limit to
check sensitivity. RTL propagation delays, metastability, and transistor noise
are not modeled.

The driver uses the timestep returned by `provisionalStep` to advance accepted
time. In this Xyce version, `getTime()` reads `nextTime`, which can already refer
to a future integration point after `acceptProvisionalStep()`; it is unsuitable
as an accepted-time clock for this bridge.

`trace.csv` records reference, RTL divider, and behavioral oscillator rising
edges. Divider timestamps are at the RTL boundary; reference timestamps include
the 10 ps half-ramp delay at the analog boundary. `summary.json` applies the same
5120 ns windows using `verification/engineering.json`: frequency within 1000 ppm,
phase span and absolute mean within 0.1 output period, drift within 0.02 output
period per window, no rails or missing feedback cycles, four sustained windows,
and acquisition confirmed within 200 us of enable. These are provisional
engineering requirements. Power has no pass/fail limit; physical jitter and total
PLL area must be characterized before numerical application limits are selected.
A run completing successfully does not mean the acquisition screen passed.
Reproduce the historical diagnostic below with `--dco-timing legacy-rounded
--acceptance-profile legacy`; its looser criteria are not release criteria.

Every applied RTL input and resulting boundary output is saved in
`trace.csv.replay`. Check that Verilator preserves the RTL's generated-clock and
asynchronous-event behavior using an independent four-state Icarus replay:

```sh
python3 scripts/check_pll_rtl_cosim_replay.py \
  /absolute/path/to/result-directory/trace.csv.replay --seed 235 --ki 4 --kp 4
```

This compares divider, BBPD reset, tracking, registered DCO code, and DLF code
after every evaluation except the first, before reset assertion. It verifies
digital simulator agreement for the observed sequence; it does not independently
validate the analog model or coupling accuracy.

The 2026-09-12 workspace campaign (`build/openpll-acquisition/rtl-cosim/REPORT.md`)
checked seed235 with reference offsets 0/10/20/30 ns. At KI=4/KP=4, all four
cases passed the final four windows at 160 us total simulation time, versus one
of four at 40.96 us. Window-based sustained-pass starts ranged from 52.47 to
72.94 us. The phase0 20 ps and 50 ps runs had identical recorded clock edges and
DCO codes through 40.96 us; two BBPD samples at oscillator edges differed without
changing that trajectory. Complete traces passed the independent Icarus replay.
These results apply to the stated behavioral DCO and extracted-BBPD configuration.
In particular, rounding the code235 half period to 1 ps makes its modeled frequency
exactly 100 MHz; constant-code settling does not establish physical zero jitter.
