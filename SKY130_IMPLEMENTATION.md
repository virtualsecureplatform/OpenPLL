# Sky130 Implementation Notes

This repo now separates the PLL into two implementation tracks:

- `rtl/IntegerPLL_DigitalCore.v`: ordinary synthesizable digital logic for the
  loop filter, decoders, feedback divider, and test divider.
- `models/`: behavioral BBPD/DCO models for RTL simulation. The BBPD model is
  a two-flop delayed-reset bang-bang detector, matching the macro topology more
  closely than a one-edge level sampler.
- `sky130/`: experimental Sky130 standard-cell structural BBPD/DCO macro
  candidates. These should be treated as macro netlists, not logic to be
  optimized by normal synthesis.
- `scripts/spice_dco_sweep.py`: generated ngspice validation for the 8-bit
  Sky130 DCO macro candidate, including parallel `--jobs` sweeps.
- `scripts/check_dco_sweep.py`: coverage and monotonicity checker for measured
  DCO sweep CSVs. It verifies expected code/corner coverage, load polarity,
  positive oscillator measurements, minimum span/step thresholds, and writes
  summary CSV/JSON artifacts.
- `scripts/spice_dco_postlayout.py`: post-layout DCO RCX transient runner for
  ngspice or Xyce. The practical no-fill and filled smoke targets use Xyce
  waveform crossings; the ngspice filled target remains a timeout diagnostic.
- `scripts/spice_bbpd_check.py`: generated ngspice validation for BBPD
  reference-leads and feedback-leads behavior.
- `scripts/spice_dco_decoder_check.py`: ngspice operating-point validation for
  the synthesized Sky130 DCO decoder cone.
- `scripts/spice_dlf_static_check.py`: ngspice operating-point validation for
  the synthesized Sky130 DLF proportional DCO-code cone.
- `scripts/spice_dlf_update_check.py`: ngspice/Xyce transient generator for the
  synthesized Sky130 DLF/DCO-code update path. The practical reduced-cone and
  short full-core overlap transient targets use Xyce and can run independent
  cases in parallel with `--jobs`; the same runner also supports filled-BBPD
  RCX outputs driving the mapped DLF update cone and the signed-off final
  digital-core netlist cone, with optional lumped-capacitance or distributed-RC
  extraction from OpenROAD SPEF.
- `scripts/spice_pll_loop_check.py`: PLL-level acquisition check using
  transistor-level Sky130 BBPD cells and a behavioral DCO model fitted to
  measured post-layout DCO smoke data, with an optional all-corner PVT mode
  driven from measured DCO sweep CSVs. The validated loop targets use ngspice;
  an Xyce waveform-output path exists for diagnostics but is not yet a promoted
  loop validation target.
- `scripts/spice_pll_sampled_gain_sweep.py`: diagnostic runner for sampled
  PLL-loop SPICE surrogate gain/aperture sweeps. It runs independent loop decks
  in parallel and writes combined CSV summaries.
- `scripts/spice_pll_continuous_sweep.py`: diagnostic runner for continuous
  PLL-loop gain/polarity/initial-phase sweeps, used by the filled-BBPD Xyce
  in-loop diagnostic target.
- `scripts/pll_top_gain_sweep.py`: RTL top-level behavioral acquisition
  gain-sweep runner. It reuses `IntegerPLL_Top`, the behavioral BBPD/DCO
  models, and the filled-RCX DCO calibration to compare `DLF_KI`/`DLF_KP`
  settings.
- `scripts/check_top_macro_assembly.py`: fast signed-off macro view/interface
  assembly check for the digital core, DCO, and BBPD physical views.
- `scripts/check_hard_macro_top.py`: routed and full-signoff hard-macro top
  integration check. It verifies the Librelane hard-macro top config, fixed
  macro placements, final routed/signoff views and metrics, top-level
  DCO/digital/BBPD interconnects, power pins, SPEF/SPICE extraction, DRC, XOR,
  and LVS evidence.
- `scripts/check_hard_macro_top_einvp.py`: hard-macro top integration check for
  `IntegerPLL_HardMacroTop_EINVP`, which instantiates the
  `IntegerPLL_DCO_EINVP_COARSE` one-loop coarse/fine DCO while preserving the
  same digital-core and BBPD macro interfaces.
- `scripts/check_hard_macro_top_spice.py`: simulator-facing extracted-SPICE
  hard-macro top check. It verifies the final extracted top wrapper's macro pin
  wiring, all 255 DCO thermometer interconnects after antenna repair,
  min/nom/max signoff SPEF coverage through the nominal SPEF, and an Xyce
  `-norun` syntax/topology probe of an inlined hard-top SPICE deck.
- `scripts/check_sky130_pll_validation.py`: promoted validation artifact gate.
  It checks the current signoff metrics, Sky130 structural top smoke,
  signed-off macro assembly views, the routed/signed-off hard-macro top and its
  extracted-SPICE interface, hard-top-SPEF loaded mapped-loop smoke,
  all-code DCO/decoder SPICE evidence, filled-RCX DCO/BBPD evidence, loop
  surrogate acquisition, gain tuning, and stronger-P DLF transistor-level SPICE
  artifacts including the final-netlist cone, plus mapped-loop and extracted-DCO
  startup/first-correction smokes, then writes a consolidated CSV/JSON summary.
- `openlane/IntegerPLL_DigitalCore/config.json`: LibreLane Classic-flow
  configuration for the synthesizable digital core.
- `openlane/IntegerPLL_DigitalCore/pnr.sdc`: PLL-specific PnR constraints for
  the digital core.

## Current Deliverable Snapshot

The current Sky130 high-frequency source/integration path is
`IntegerPLL_HardMacroTop_EINVP`. It combines the digital core RTL, the filled
`IntegerPLL_BBPD` macro, the physical `IntegerPLL_DCO_EINVP_COARSE` oscillator
macro source, and the hard-top hardening flow around those macros. Existing
hard-top/configured-wrapper routed artifacts must be regenerated after the
current 5-bit `DLF_KP` interface update before they are treated as current
post-layout release evidence. The exported fine loop control remains 8 bits:
`DCO_CODE[7:0]` drives a 255-line thermometer control bus connected to 255 local
HD NAND2 loads,
`COARSEBINARY_CODE[5:0]` selects the oscillator band through a 47-line coarse
thermometer bus, and `MMDCLKDIV_RATIO[7:0]` selects the integer feedback
division ratio.

The coarse DCO keeps one macro and one oscillator loop: an HD NAND enable gate,
a 48-position HD NAND/NAND2B turn/pass mirror-delay network driven through the
47-bit coarse thermometer bus, and 255 local HD NAND2 fine loads split between
`osc_node` and `mirror_ret[0]`. The active ring and mirror gates use HD
`nand2_8` and `nand2b_4` cells; the ring-facing output buffer stays
`sky130_fd_sc_hd__buf_1` to limit oscillator-node loading. It is not a set of
parallel DCO macros, it does not select a simple muxed feedback tap, and the
coarse path does not use NOT cells as the ring delay.

The current evidence for the all-HD variant includes the 255-load coarse-DCO
source structure, standalone DCO macro signoff, the 25 MHz
divider/configured-wrapper RTL regressions, and configured behavioral
reset-to-tracking checks using the all-HD DCO model. The configured operating
points are C24/code139, C07/code8, C06/code242, C03/code45, and C02/code149 for
100, 250, 300, 400, and 500 MHz respectively. Hard-top/configured-wrapper
post-layout artifacts must still be regenerated before treating this as
complete physical PLL signoff evidence.

The older filled `IntegerPLL_DCO_EINVP` and sparse72 paths remain documented as
low-frequency and 200 MHz diagnostic history. They are useful evidence for loop
methodology and prior macro-hardening work, but they are not the current
100/250/300/400/500 MHz hardtop target.

The older low-frequency hard-top convergence evidence is the hard-top-loaded
extracted-DCO lock-window set from the previous EINVP artifact: low rail reaches
codes 122..128 with a 58.485654 MHz tail and 0.087865 MHz target error, while
high rail reaches codes 126..132 with a 58.804895 MHz tail and 0.231377 MHz
target error. FF and SS low/high rail PVT lock-window rows are also present in
that legacy artifact audit. Those rows remain useful loop-methodology evidence,
but they are not the current coarse-DCO 25 MHz-reference multiplier signoff
claim.

## Local Checks

Run the consolidated promoted validation artifact audit:

```sh
make -C OpenPLL validate-sky130-pll-artifacts
```

For a heavier sequential run that regenerates the promoted artifacts where
practical before auditing them:

```sh
make -C OpenPLL validate-sky130-pll
```

The heavier `validate-sky130-pll` flow now regenerates the Xyce C-interface
mixed-signal gain sweep before the artifact audit. The v1 artifact set passed
69 evidence groups and wrote
`build/sky130_pll_validation/sky130_pll_validation_summary.csv` plus
`sky130_pll_validation_summary.json`. This fast-path development tree changes
RTL/scripts after those artifacts, so the audit intentionally reports stale
physical/SPICE evidence until the matching LibreLane and long Xyce artifacts
are regenerated. It deliberately excludes diagnostic targets that are known not
to pass from both rails.

Run the digital smoke test:

```sh
make -C OpenPLL sim
```

Run a direct Yosys Sky130 synthesis of the digital core:

```sh
make -C OpenPLL synth
```

The synthesis script uses:

```text
CIEL_SKY130_ROOT=$HOME/.volare/ciel/sky130
PDK_ROOT=$HOME/.volare/ciel/sky130
PDK=sky130A
STD_CELL_LIBRARY=sky130_fd_sc_hd
```

Run `make -C OpenPLL check-pdk-stdcell` to print and validate the selected PDK.
If the shell exports either the legacy default `PDK_ROOT=$HOME/.volare` or the
Ciel registry root `PDK_ROOT=$HOME/.volare/ciel/sky130`, the Makefile and
direct script defaults resolve it to the usable Ciel PDK root. Pass
`PDK_ROOT=...` on the `make` command line or export a non-default root if you
want another Volare PDK target. The current local Ciel tree has usable
`sky130_fd_sc_hd` and `sky130_fd_sc_hs` reference views. HD remains the default
for the promoted low-frequency macros; the coarse 100/250/300/400/500 MHz candidate
explicitly selects `sky130_fd_sc_hs`.

For the independent coarse-band fast-path checks intended to pair with a
wide-range DCO, run:

```sh
make -C OpenPLL synth-coarse4
make -C OpenPLL digital-loop-gain-sweep-coarse4
make -C OpenPLL pll-top-fast100-coarse4-acq
make -C OpenPLL xyce-pll-mixed-signal-fast100-coarse4-smoke
make -C OpenPLL xyce-pll-analog-dco-mixed-fast100-coarse4-acq
make -C OpenPLL spice-pll-mapped-loop-fast100-coarse4-motion
```

`synth-coarse4` keeps `DCO_COARSE_BITS=0`, sets `DLF_FRAC_WIDTH=2`, and enables
`DLF_PROP_RAIL_GUARD=1`. In that mode the loop filter still drives the full
8-bit `DCO_CODE`; `COARSEBINARY_CODE` is an independent band input consumed by
the behavioral DCO model for fast-path acquisition and mixed-signal checks. The
current target uses `COARSEBINARY_CODE=1`, a 16 MHz coarse-band step,
`MMDCLKDIV_RATIO=2`, `REF=63.443725 MHz`, and a 126.88745 MHz output target
near fine code 32. The companion LibreLane config is
`openlane/IntegerPLL_DigitalCore/config_coarse4.json`; use:

```sh
make -C OpenPLL librelane-signoff-coarse4
make -C OpenPLL check-librelane-signoff-coarse4
```

before using the coarse-enabled digital core as a physical macro. The generic
`sky130/IntegerPLL_DCO_sky130.v` wrapper keeps the existing signed-off physical
DCO pin list and does not consume `COARSEBINARY_CODE`. The physical
`IntegerPLL_DCO_EINVP_COARSE` candidate consumes the decoded
`COARSETHERMAL_CODE[46:0]` pass/turn bus while leaving all 8 exported DCO bits
for fine thermometer control.

The 220 ns fast-path mapped-loop motion check uses the synthesized coarse-band
digital core, filled BBPD RCX, and behavioral five-point DCO table with the
independent 16 MHz coarse offset. It passes the intended two-rail motion check:
low-start code 0 moves to 62 and high-start code 255 moves to 183. This is
direction and integration evidence for the 126.88745 MHz target, not a full
settling or post-layout fast-DCO signoff result.

`xyce-pll-mixed-signal-fast100-coarse4-smoke` is a faster bounded mixed-signal
check using the Xyce C-interface: Xyce owns the filled BBPD RCX, while the
compiled driver owns the DLF/divider and the five-point fast DCO table plus the
independent coarse offset. The current low case moves fine code 0 to 36 in 24
cycles; the bounded high-side case moves code 64 to 38 in 15 cycles. Both have
a closest target error of 4 codes around fine code 32. The full 255-to-32 rail
case is not promoted for this C-interface driver because its one-edge-per-cycle
phase model is not robust to large cycle slips.

`xyce-pll-analog-dco-mixed-fast100-coarse4-acq` keeps the fast DCO phase and
feedback divider inside Xyce instead of the compiled driver. The deck uses the
filled BBPD RCX, a behavioral analog DCO phase integrator with the same
five-point fast table, and an independent 16 MHz coarse offset. The external
C++ driver only performs the fixed-point DLF update and drives the DCO code
YDAC. With `KI=128`, `KP=8`, `FRAC=2`, and target fine code 32, the bounded
four-update cases pass from both sides: 0 to 34 with measured `PLLOUT` at
127.389 MHz, and 64 to 30 with measured `PLLOUT` at 126.316 MHz. Both are
within the 2 MHz frequency tolerance around the 126.88745 MHz multiply target.
This is the preferred fast mixed-signal polarity/gain/frequency check, but it
is still not physical fast-DCO signoff or full rail-start settling.

Current Yosys/Liberty estimate for the default `IntegerPLL_DigitalCore` with
the 8-bit DCO thermometer decoder, registered DCO controls, BBPD event capture,
and independent coarse interface is 1159 mapped Sky130 cells and
12833.558400 square microns at `sky130_fd_sc_hd__tt_025C_1v80`. The FRAC=2
guard-enabled `synth-coarse4` fast-path configuration maps to 1226 cells and
13028.745600 square microns.

For the 25 MHz reference / 200 MHz output exploration, the current physically
checked fast DCO is `IntegerPLL_DCO_EINVP_SPARSE72`. Regenerate and check that
macro with:

```sh
make -C OpenPLL dco-einvp-sparse72-librelane-signoff
make -C OpenPLL check-dco-einvp-sparse72-librelane-signoff
make -C OpenPLL dco-einvp-sparse72-magic-rcx
make -C OpenPLL spice-dco-postlayout-einvp-sparse72-200-probe
make -C OpenPLL xyce-pll-postlayout-calibrated-dco-mixed-fast200-sparse72-lock
make -C OpenPLL xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion
```

The Ciel-PDK run is DRC/LVS/XOR clean and the extracted DCO probe measures
194.469 MHz at fine code 184, 195.968 MHz at code 190, 196.676 MHz at code
191, and 202.264 MHz at code 192. The calibrated mixed-signal lock target keeps
the filled BBPD RCX in Xyce and uses a DCO phase model fitted to the sparse72
post-layout RCX points, including the flat lower range below code 184. With
`REF=25 MHz`, `NDIV=8`, `KI=76`, `KP=8`, and `FRAC=2`, it passes from both
rails within a 4 MHz target window: code 0 moves to 192 and measures
202.314 MHz; code 255 moves to 191 and measures 196.767 MHz.

The full extracted-DCO mixed-step transient is still too slow for a complete
rail-start regression, but the bounded direct-RCX companion now performs real
post-decision DCO-code updates through Xyce's mixed-step API. It keeps both the
filled BBPD and sparse72 DCO RCX decks in Xyce, releases reset at 5 ns, drives
REF as a 25 MHz pulse source, and uses `NDIV=8`. The fixed-code row starts and
stays at code 196 and measures `PLLOUT` at 199.734 MHz. The low-side row starts
from code 184 with divider count 0 and `KI=32`, `KP=4`, records six
UP-dominant windows, moves 184 -> 187 -> 189 -> 191 -> 193 -> 195 -> 197, and
measures 200.000 MHz. The high-side row starts from code 220 with divider count 7 and
`KI=96`, `KP=8`, records four DN-dominant windows, moves 220 -> 212 -> 206 ->
200 -> 194, and measures 200.000 MHz. The evidence therefore proves post-layout DCO
range, direct-RCX near-target mixed-step correction, and
post-layout-calibrated mixed lock; it is not yet a full rail-to-rail lock
simulation with the 19k-unknown extracted DCO in every loop cycle.

Run LibreLane synthesis for the digital core:

```sh
make -C OpenPLL librelane-synth
```

Run LibreLane through detailed routing for the digital core:

```sh
make -C OpenPLL librelane-route
```

Run full LibreLane digital-core signoff:

```sh
make -C OpenPLL librelane-signoff
make -C OpenPLL check-librelane-signoff
```

Run full signoff for the promoted FRAC=6 force-to-mid digital-core variant:

```sh
make -C OpenPLL librelane-signoff-force127-s4a2
make -C OpenPLL check-librelane-signoff-force127-s4a2
```

The routed digital-core run uses `$LIBRELANE_ROOT` by default
and can be redirected with `LIBRELANE_ROOT`. `librelane-route` stops after
OpenROAD detailed routing. `librelane-signoff` runs the rest of the Classic
flow, including fill insertion, OpenROAD RCX/SPEF extraction, post-PnR STA,
Magic and KLayout GDS streamout, Magic and KLayout DRC, Magic SPICE extraction
for LVS, and Netgen LVS.

Current full-signoff digital-core results for
`openlane/IntegerPLL_DigitalCore/config.json`:

| Metric | Value |
| --- | ---: |
| Die area | 90000 square microns |
| Core area | 80146.9 square microns |
| Standard-cell area | 15912.8 square microns |
| Instance utilization | 19.8545% |
| Standard-cell instance count | 2786 |
| Detailed-route DRC errors | 0 |
| Antenna-violating nets/pins | 0 / 0 |
| Power-grid violations | 0 |
| Magic DRC errors | 0 |
| KLayout DRC errors | 0 |
| Magic/KLayout XOR differences | 0 |
| LVS errors | 0 |
| Max slew/cap/fanout violations | 0 / 0 / 0 |
| Setup WNS/TNS | 0 ns / 0 ns |
| Hold WNS/TNS | 0 ns / 0 ns |
| Worst setup/hold slack | 2.611 ns / 0.073 ns |
| Routed wire length | 54506 microns |
| Routed vias | 10925 |

Current full-signoff force-to-mid digital-core results for
`openlane/IntegerPLL_DigitalCore/config_force127_s4a2.json`:

| Metric | Value |
| --- | ---: |
| Die area | 90000 square microns |
| Core area | 80146.9 square microns |
| Standard-cell area | 24098.1 square microns |
| Instance utilization | 30.0674% |
| Standard-cell instance count | 3164 |
| Detailed-route DRC errors | 0 |
| Antenna-violating nets/pins | 0 / 0 |
| Power-grid violations | 0 |
| Magic DRC errors | 0 |
| KLayout DRC errors | 0 |
| Magic/KLayout XOR differences | 0 |
| LVS errors | 0 |
| Max slew/cap/fanout violations | 0 / 0 / 0 |
| Setup WNS/TNS | 0 ns / 0 ns |
| Hold WNS/TNS | 0 ns / 0 ns |
| Worst setup/hold slack | 2.794 ns / 0.115 ns |
| Routed wire length | 67207 microns |
| Routed vias | 13321 |
| Reported total power | 3.431 mW |
| Worst IR drop | 0.706 mV |

These full-signoff artifacts were regenerated after the BBPD decision-latch and
DLF rail-escape RTL updates, and again after adding the default-off
same-direction acquisition-boost parameters and the default-off PLLOUT-update
mode, force-to-mid acquisition, and registered DCO control outputs.
`make -C OpenPLL check-librelane-signoff` and
`make -C OpenPLL check-librelane-signoff-force127-s4a2` passed in the v1
artifact set against their final views and zero-violation metrics. The signoff
checker also compares final metrics timestamps against the digital-core RTL,
config, and SDC sources, so this fast-path development tree reports those
physical artifacts as stale until they are regenerated.

The final signoff DEF, GDS, Magic/KLayout GDS, LEF, ODB, netlists, SDC,
metrics, extracted LVS SPICE, corner SPEF, corner SDF, and corner Liberty files
are written under:

```text
OpenPLL/openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/
```

The promoted FRAC=6 force-to-mid variant writes its final signoff views under:

```text
OpenPLL/openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/
```

These results validate the synthesizable digital core through post-layout
digital signoff. The extracted `IntegerPLL_DigitalCore.spice` view is used for
LVS and the SPEF files are used by post-PnR STA; they are not a post-layout
transient SPICE simulation of the DCO, BBPD, or closed-loop PLL.

## DCO Physical Macro Status

The Sky130 DCO structural macro can also be hardened with LibreLane:

```sh
make -C OpenPLL dco-librelane-signoff
make -C OpenPLL dco-magic-rcx
```

The filled signoff DCO layout writes final DEF/GDS/LEF/MAG/ODB/netlist/SPEF/LVS
SPICE views under:

```text
OpenPLL/openlane/IntegerPLL_DCO/runs/librelane_signoff/final/
```

Current filled-layout DCO signoff results:

| Metric | Value |
| --- | ---: |
| Die area | 202500 square microns |
| Standard-cell area | 4306.63 square microns |
| Instance utilization | 2.298% |
| Standard-cell instance count | 2896 |
| Detailed-route DRC errors | 0 |
| Antenna-violating nets/pins | 0 / 0 |
| Power-grid violations | 0 |
| Magic DRC errors | 0 |
| KLayout DRC errors | 0 |
| Magic/KLayout XOR differences | 0 |
| LVS errors | 0 |
| Routed wire length | 8412 microns |
| Routed vias | 1022 |

`dco-magic-rcx` creates a flattened transistor-level RCX deck for the filled
layout at:

```text
OpenPLL/openlane/IntegerPLL_DCO/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO.rcx.spice
```

That filled deck is real post-layout extraction, but it includes filler/decap
devices and is expensive in ngspice. The practical filled signoff smoke target
uses Xyce:

```sh
make -C OpenPLL spice-dco-postlayout-filled
```

This target runs the five canonical filled-RCX code-point decks concurrently
through `make -j$(DCO_POSTLAYOUT_FILLED_JOBS)`, with
`DCO_POSTLAYOUT_FILLED_JOBS ?= 5`. The consolidated calibration check is:

```sh
make -C OpenPLL check-dco-postlayout-filled
```

The denser TT 9-point tuning characterization is:

```sh
make -C OpenPLL check-dco-postlayout-filled-tt-9pt
```

The focused TT high-code tail characterization is:

```sh
make -C OpenPLL check-dco-postlayout-filled-highcode-tail
```

The pre-layout load-cell retuning comparison is:

```sh
make -C OpenPLL check-dco-tail-loadstyle-candidates
```

The hardened filled-RCX `einvp` load-cell candidate flow is:

```sh
make -C OpenPLL dco-einvp-librelane-signoff
make -C OpenPLL check-dco-einvp-librelane-signoff
make -C OpenPLL dco-einvp-magic-rcx
make -C OpenPLL check-dco-einvp-postlayout
```

The older 100 MHz-order fast DCO range probe keeps the same EINVP load style
and thermometer interface, but uses a 9-stage enabled ring instead of the
promoted 17-stage ring:

```sh
make -C OpenPLL check-dco-einvp-fast-9stage-5pt
make -C OpenPLL dco-einvp-fast-librelane-signoff
make -C OpenPLL check-dco-einvp-fast-librelane-signoff
make -C OpenPLL dco-einvp-fast-magic-rcx
```

The pre-layout check currently measures 102.518 MHz at code 0, 119.260 MHz at
code 64, 142.355 MHz at code 128, 176.267 MHz at code 192, and 229.054 MHz at
code 255. These numbers are useful for first-pass loop targeting and gain
sweeps, but the physical range can shift substantially after fill, routing, RCX,
and hard-top loading.

After both the coarse digital-core macro and fast DCO macro are signed off, the
future hard-top integration entry point is:

```sh
make -C OpenPLL hardtop-einvp-fast-librelane-signoff
make -C OpenPLL check-hard-macro-top-einvp-fast-spice
```

That hard top is intentionally separate from the promoted
`IntegerPLL_HardMacroTop_EINVP` path.

The intended one-macro coarse-DCO physical flow is:

```sh
make -C OpenPLL dco-einvp-coarse-librelane-signoff
make -C OpenPLL check-dco-einvp-coarse-librelane-signoff
make -C OpenPLL dco-einvp-coarse-magic-rcx
make -C OpenPLL spice-dco-postlayout-einvp-coarse-target-probe
```

Its RTL-level structural check is already covered by
`make -C OpenPLL check-sky130-macros`. The current local latest-Ciel run passes
the standalone LibreLane artifact checker for the all-HD coarse DCO macro with
1047 standard cells, 0.158011 utilization, 9698 microns routed wire length, and
2151 vias. The current checker uses the KLayout streamout path and skips Magic
streamout/XOR for this standalone DCO artifact. Hard-top RCX/SPEF artifacts
must be regenerated before making full post-layout PLL claims.
Full arbitrary-start extracted-loop lock evidence for the 25 MHz-reference
100/250/300/400/500 MHz target set is still pending.

The current all-HD DCO target probes cover all requested 25 MHz-reference modes
while keeping the ring-facing output buffer at `buf_1`:

| Target | Multiplier | Coarse/fine setting | TT evidence |
| ---: | ---: | --- | --- |
| 100 MHz | 4 | C24/code139 | Interpolated at 100.069 MHz. |
| 250 MHz | 10 | C07/code8 | Bracketed by C07/code8..11 at 249.851..250.146 MHz. |
| 300 MHz | 12 | C06/code242 | Interpolated at 299.854 MHz. |
| 400 MHz | 16 | C03/code45 | Interpolated at 399.904 MHz. |
| 500 MHz | 20 | C02/code149 | Interpolated at 500.154 MHz. |

The endpoint sweeps also keep target-band context: C24 spans
98.225..101.387 MHz, C07 spans 249.071..271.543 MHz, C06 spans
274.037..301.073 MHz, C03 spans 390.798..448.308 MHz, and C02 spans
456.090..535.379 MHz over the measured code range.

Measured duty remains close to 50% on the selected target bands, and rise/fall
times remain well below 25% of period. The rejected root-connected slow-load
attempt showed why the slow loads must not be attached to `osc_node` or
`mirror_ret[0]`: even logically disabled NAND2 inputs added enough capacitance
to open gaps around 300 and 400 MHz.
For the same reason, the output buffer is not a tuning knob for speed recovery:
upsizing it increases the load seen by the oscillator. Speed margin should come
from the ring/mirror cells, selected coarse path, or fine-load placement.

The current mirror-delay coarse DCO no longer uses the earlier mux-selected
feedback tap model. Its structural RTL check is:

```sh
make -C OpenPLL check-sky130-macros
```

The optional pre-layout turn/pass mirror-delay diagnostic is:

```sh
make -C OpenPLL check-dco-einvp-coarse-mirror-targets
```

It uses a legacy `sky130_fd_sc_hs` 48-position mirror path, 90 evenly mapped
NAND2 fine loads, and waveform-quality filtering at the buffered `PLLOUT`
(`0.35 <= duty <= 0.65`, rise/fall each below 25% of period), while keeping
the output buffer drive at 1. With the current small output buffer it is a
partial pre-layout diagnostic, not the shipping target-range gate. The recorded
rows below predate the all-HD 255-load source and are retained only as topology
history:

| Target | Multiplier | Coarse turn | Fine code estimate | Bracket |
| ---: | ---: | ---: | ---: | --- |
| 100 MHz | 4 | 40 | 183.545 | 98.024700-100.769000 MHz |
| 300 MHz | 12 | 10 | 59.228 | 293.946000-320.011000 MHz |

The 250 and 400 MHz shipping targets are intentionally qualified from the
all-HD target probes above instead. This keeps the legacy pre-layout check from
encouraging output-buffer upsizing just to close a sampled bracket.

The corresponding configured-mode mixed-signal PLL gate is:

```sh
make -C OpenPLL xyce-pll-mixed-signal-25mhz-targets
```

That target aliases to the direct extracted-DCO mixed-step hold smoke after
refreshing the DCO target probes above. The selected target codes are
code139, code8, code242, code45, and code149. It remains a configured-mode check, not a
blind rail-start acquisition claim:
`COARSEBINARY_CODE` selects a characterized mirror-delay path, the fine code is
seeded near the target estimate, and the DLF then performs phase tracking.
The reusable RTL preset table is `IntegerPLL_25MHzModeConfig`: the external
5-bit `FEEDBACK_DIVIDER` value /4 selects 100 MHz with C24/code139 and
KI=4/KP=2; /10 selects 250 MHz with C07/code8 and KI=4/KP=2; /12 selects
300 MHz with C06/code242 and KI=4/KP=2; /16 selects 400 MHz with C03/code45 and
KI=4/KP=2; and /20 selects 500 MHz with C02/code149 and KI=4/KP=2. It also
emits the 10-bit DLF seed word `target_code << 2` and `CONFIG_VALID`.
Unsupported divider values hold `CONFIG_VALID=0` and do not enable tracking.
The table is checked by:

```sh
make -C OpenPLL check-pll-25mhz-divider-config
```

For normal fixed-mode RTL use, instantiate
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured` instead of driving the DLF pins
manually. It wraps `IntegerPLL_HardMacroTop_EINVP` with
`IntegerPLL_25MHzModeController`: `FEEDBACK_DIVIDER[4:0]` is the public
feedback-loop divider input, and `PLL_ENABLE` starts a
retimed-divider-clocked sequence that holds `DLF_Clear` long enough to load the
preset seed before asserting `DLF_En` for tracking. The wrapper test checks all
five supported divider reloads through the hard-macro instance, not only the
isolated controller. The behavioral check uses the real controller, digital
core, divider, and BBPD with a DCO table fitted to the all-HD coarse-band
measurements to verify reset-to-tracking operation and measured frequency for
all five supported divider values. These checks are:

```sh
make -C OpenPLL check-pll-25mhz-divider-controller
make -C OpenPLL check-pll-25mhz-configured-wrapper
make -C OpenPLL check-pll-25mhz-configured-behavioral
```

The calibrated BBPD/DCO-table tracking row uses the per-mode gains above, starts
each mode from +/-4 fine codes around the target, and passes the bounded
configured tracking gate for all five requested multipliers. That gate requires a
target-code-neighborhood hit, at least one BBPD decision in the expected
initial direction, final modeled frequency error within 2 MHz, and the last
eight modeled DCO updates also inside the 2 MHz frequency window with no more
than 16 fine-code span.

The current fast source/behavioral gate for the 25 MHz coarse-DCO release is:

```sh
make -C OpenPLL check-pll-25mhz-divider-config check-pll-25mhz-divider-controller check-pll-25mhz-configured-wrapper check-pll-25mhz-configured-behavioral check-sky130-macros
```

It validates the HD NAND/NAND2B mirror-delay RTL, rejects ring-facing output
buffer upsizing, checks the 25 MHz divider preset table and configured
divider-controller/wrapper, and checks the configured behavioral PLL
reset-to-tracking row. The heavier
`make -C OpenPLL check-sky130-pll-25mhz-release` audit still checks post-layout
hard-macro artifact freshness, waveform-qualified target-code rows, direct-RCX
hold smokes, and near-seed direct-RCX update summaries. After the 5-bit
physical `DLF_KP` interface change, regenerate the hard-top/configured-wrapper
physical artifacts before using that audit as current post-layout release
evidence.

The optional direct extracted-DCO mixed-step diagnostic for the hardest target
mode is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-500m-hold-smoke
```

It instantiates the `IntegerPLL_DCO_EINVP_COARSE` RCX deck and the filled BBPD
RCX deck in Xyce, fixes the DCO at C02/code149, and drives the divider/filter
from the C-interface. The short ADC-sampled frequency estimate is intentionally
loose; the standalone post-layout DCO rows remain the precise frequency
evidence for the 500 MHz target. Single-cycle BBPD motion checks are phase
dependent and are not promoted as frequency-acquisition evidence for this
coarse-DCO path.

The companion near-seed direct-RCX code-update diagnostic is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
```

The current Ciel-PDK TT run checks low and high starts four fine codes away
from each target. Low-side rows use REF phase offset -0.25 and divider seed 0;
high-side rows use REF phase offset 0.25 and divider seed `NDIV-1`, because the
extracted BBPD decision is intentionally phase dependent. The direct-RCX rows
all pass with the expected two BBPD decisions: 100 MHz moves 89->92 and
97->94, 250 MHz moves 230->233 and 238->235, 300 MHz moves 86->89 and 94->91,
400 MHz moves 72->75 and 80->77, and 500 MHz moves 117->120 and 125->122. The
ADC-sampled PLLOUT estimates are intentionally loose; the standalone DCO rows
remain the precise frequency evidence. This is stronger near-seed
configured-control evidence, not full extracted-loop rail-start acquisition.

The BBPD C-interface deck includes a local compatibility alias for the latest
Ciel Magic-RCX `sky130_fd_pr__special_nfet_01v8` device name, mapped to the
available `sky130_fd_pr__nfet_01v8` model with the RCX geometry parameters.
This keeps the BBPD-RCX mixed-signal target runnable on the current Ciel tree;
it does not replace final device-accurate post-layout signoff.

The filled local-gain check is:

```sh
make -C OpenPLL check-dco-postlayout-filled-local-gain
```

The filled PVT endpoint smoke check is:

```sh
make -C OpenPLL check-dco-postlayout-filled-pvt-endpoints
```

In the recorded validation environment, the filled signoff deck now has a passing TT five-point
transient smoke result from printed Xyce `PLLOUT` crossings: code 0 measures
46.257 MHz, code 64 measures 47.950 MHz, code 128 measures 49.762 MHz,
code 192 measures 51.618 MHz, and code 255 measures 52.350 MHz. This confirms
filled-deck tuning polarity. The consolidated calibration artifact reports a
6.093105 MHz span, a 0.023895 MHz/LSB average step, and measured segment steps
of 0.026464, 0.028308, 0.029005, and 0.011609 MHz/LSB over code ranges 0-64,
64-128, 128-192, and 192-255. The denser TT 9-point check covers codes 0, 32,
64, 96, 128, 160, 192, 224, and 255. It finds positive segment gain through
code 224, peaking at 52.565854 MHz, then a bounded high-code roll-off to
52.349831 MHz at code 255. That 0.216023 MHz roll-off is a real filled-RCX
limitation of the current layout, so this is a tuning characterization rather
than proof of full-range filled-DCO monotonicity. The focused high-code tail
check covers codes 192, 208, 216, 224, 232, 240, 248, 250, 252, 254, and 255.
It localizes the filled-RCX TT peak at code 240, measuring 53.003796 MHz, and
records a 0.653965 MHz roll-off to code 255. This points to the sparse-load
tail ordering/layout as the next DCO retuning target. A pre-layout load-cell
comparison keeps the current NAND load as the baseline and tests a tri-state
`einvp` load candidate. Over high-tail codes 192, 208, 216, 224, 232, 240,
248, 250, 252, 254, and 255, the `einvp` candidate is monotonic and spans
44.101 MHz, versus 9.756 MHz for the NAND load. A representative 5-point
`einvp` sweep at codes 0, 64, 128, 192, and 255 is also monotonic and spans
99.974-210.869 MHz.

The `IntegerPLL_DCO_EINVP` candidate has now also been hardened separately from
the top-level `IntegerPLL_DCO` macro. Its filled signoff metrics are clean
with 2896 standard-cell instances, 2.639% utilization, 9354 microns routed
wire length, 1044 vias, zero Magic/KLayout DRC errors, zero XOR differences,
and zero LVS errors. Magic RCX writes:

```text
OpenPLL/openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice
```

`check-dco-einvp-postlayout` verifies the candidate in MPI-enabled Xyce at TT.
The filled-RCX smoke measures code 0 at 50.955942 MHz, code 128 at
60.174879 MHz, and code 255 at 72.479371 MHz, a monotonic 21.523429 MHz span.
The consolidated five-point calibration adds code 64 at 55.205750 MHz and code
192 at 66.031451 MHz, producing the measured TT calibration table
50.955942/55.205750/60.174879/66.031451/72.479371 MHz for codes
0/64/128/192/255. The focused high-tail check combines codes 192, 224, 240,
248, and 255 and measures 66.031451, 69.378381, 70.929758, 71.718618, and
72.479371 MHz, respectively, a monotonic 6.447920 MHz tail span. This remains
real post-layout evidence for the alternate load topology. The same filled RCX
deck also passes endpoint smoke at the other four PVT corners with four-rank
Xyce: 70.251790-99.895518 MHz at FF, 51.688142-70.763937 MHz at FS,
44.076396-64.579620 MHz at SF, and 33.875977-47.497548 MHz at SS. The PVT
endpoint target is `make -C OpenPLL spice-dco-postlayout-einvp-pvt-endpoints`.

The current high-frequency hard-macro source top,
`IntegerPLL_HardMacroTop_EINVP`, instantiates
`IntegerPLL_DCO_EINVP_COARSE`. The last checked physical artifacts for this path
are useful history, but they predate the current 5-bit `DLF_KP` interface and
must be regenerated before use as current release evidence. Those historical
artifacts include a force127 digital-core signoff with ABC buffering for the
6-bit coarse/47-line thermometer interface, a clean
`hardtop-einvp-librelane-signoff` run, and a `check-hard-macro-top-einvp-spice`
SPICE/SPEF wrapper probe covering the `IntegerPLL_DCO_EINVP_COARSE` oscillator
subcircuit, 255 DCO thermometer connections, and 47 coarse thermometer
connections. The configured physical wrapper flow,
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured`, embeds the lower hard macro and
adds the 25 MHz divider controller in one physical macro; rerun that flow after
the 5-bit `DLF_KP` interface update before treating the wrapper as signed off.
The wrapper locally buffers the `TARGET_MHZ[8]` status output with
`sky130_fd_sc_hd__buf_8`, keeping the long status route off the weak
divider-decode net. The wrapper flow excludes `sky130_fd_sc_hd__o21ai_0` because
the current Ciel KLayout deck reports an `npc.2` marker in that cell; synthesis
uses the clean `o21ai_1` variant.

The older low-frequency E hard-top artifact also has MPI16/KLU extracted-loop
diagnostics with the final force-to-mid digital-core netlist, filled BBPD RCX,
the filled `IntegerPLL_DCO_EINVP` RCX deck, and distributed nominal SPEF RC from
the previous `IntegerPLL_HardMacroTop_EINVP` generation. The selected E hard-top
nets cover all 255 DCO
thermometer interconnects, 261 hard-top SPEF nets, 1744 grounded capacitance
nodes, 1627 resistors, 260 digital pin substitutions, and 25247.633 fF of
selected top-level capacitance. The 50 ns startup deck passes with two PLLOUT
rises and 50.813495 MHz startup frequency. Early-enable 90 ns first-motion
decks pass in both directions: low start moves code 0 to 2, and high start
moves code 255 to 243.019510. Using the measured five-point E RCX calibration
as a piecewise behavioral DCO, the same signed-off E hard-top path also passes
calibrated low/high lock-window diagnostics. The low-start MPI16/KLU run moves
code 0 to 122 with response code 128, observes lock-window codes 121..128, and
measures 59.936383 MHz tail frequency with 0.238496 MHz target error. The
high-start run moves code 255 to 133 with response code 124, observes
lock-window codes 126..133, and measures 60.235253 MHz tail frequency with
0.060373 MHz target error. A distributed-RC extracted-DCO mid-code lock-window
diagnostic also passes when the reference is calibrated to the hard-top-loaded
E DCO target. The standalone E code-128 target row shows the top interconnect
load directly: code 128..125 gives a 58.573518 MHz tail, 1.601361 MHz below the
standalone 60.174879 MHz DCO target. Retargeting the reference to
29.286759 MHz for `NDIV=2` passes with code 125..128 in the 150..219 ns lock
window, 58.591120 MHz tail frequency, and 0.017601 MHz target error.
Normal-enable rail-progress rows at the same hard-top-loaded target run to
360 ns: low start moves code 0->62 with late-window codes 42..62 and
53.728266 MHz tail frequency, while high start moves code 255->172 with
late-window codes 172..192 and 62.952232 MHz tail frequency. Extending the
rail-start decks to lock-window checks produces two-sided extracted-DCO
rail-start lock evidence: low start runs to 900 ns and reaches code 122..128
with 58.485654 MHz tail frequency and 0.087865 MHz target error, while high
start runs to 760 ns and reaches code 126..132 with 58.804895 MHz tail
frequency and 0.231377 MHz target error. The remaining gap is PVT loop lock
evidence for the EINVP top.

The local-gain check runs the filled RCX deck at TT codes 120, 128,
and 136 with the MPI-enabled Xyce build and measures 49.558458 MHz,
49.771679 MHz, and 49.977051 MHz, giving 0.026162 MHz/LSB average local gain
around the nominal lock code. The same filled RCX deck also passes endpoint
smoke at the other four PVT corners: 63.875-72.318 MHz at FF,
46.796-52.659 MHz at FS, 40.092-46.062 MHz at SF, and 30.704-34.328 MHz at
SS. The FS/SF/SS runs use the MPI-enabled Xyce build at
`$XYCE_MPI_ROOT/bin/Xyce` with four ranks. This is still not yet
a full filled 256-code tuning curve or all-corner filled PVT sweep. The old
ngspice diagnostic remains available as:

```sh
make -C OpenPLL spice-dco-postlayout-filled-ngspice
```

The installed Xyce binary reports `Serial` in `Xyce -capabilities`, so wrapping
this binary with `mpirun` would launch serial processes rather than parallelize
one filled-RCX transient solve. Independent code/corner decks can still be
parallelized at the script or Makefile target level. The Xyce-enabled runners
also accept `XYCE_MPI_PROCS`; the runner checks `Xyce -capabilities` and refuses
to wrap a serial binary. The MPI-enabled Xyce build at
`$XYCE_MPI_ROOT/bin/Xyce` reports `Parallel with MPI`; use it
only after confirming the deck still converges, for example
`XYCE=$XYCE_MPI_ROOT/bin/Xyce XYCE_MPI_PROCS=8 make -C OpenPLL spice-dco-postlayout-filled-code128`.

The ngspice filled code-255 attempts timed out after 900.368 s with an
80 ns / 100 ps deck and after 900.362 s with a 60 ns / 200 ps deck. A
60 ns / 200 ps diagnostic probe with `num_threads=4` also timed out after
120.212 s. `make` exposes `NGSPICE_THREADS ?= 4` for selected single-run
ngspice targets, but threading does not make the filled DCO transient practical
in the recorded validation environment. For a faster three-point oscillator smoke test there is a
separate no-fill extraction path:

```sh
make -C OpenPLL dco-librelane-nofill
make -C OpenPLL dco-magic-rcx-nofill
make -C OpenPLL spice-dco-postlayout
```

The no-fill layout is not signoff-clean; it intentionally omits filler and
therefore reports DRC/LVS errors. Its purpose is only to keep the extracted
transient deck small enough for quick oscillator validation. The current Xyce
no-fill post-layout smoke sweep measures 50.944 MHz, 55.258 MHz, and
60.003 MHz for top-level-style codes 0, 128, and 255 respectively.

The Sky130 BBPD structural macro is also hardened as a filled, signoff-clean
macro:

```sh
make -C OpenPLL bbpd-librelane-signoff
make -C OpenPLL bbpd-magic-rcx
make -C OpenPLL spice-bbpd-postlayout
make -C OpenPLL spice-bbpd-postlayout-pvt
make -C OpenPLL spice-bbpd-postlayout-deadzone
make -C OpenPLL spice-bbpd-postlayout-deadzone-pvt
```

Current filled-layout BBPD signoff results:

| Metric | Value |
| --- | ---: |
| Die area | 14400 square microns |
| Standard-cell area | 280.269 square microns |
| Instance utilization | 2.637% |
| Standard-cell instance count | 163 |
| Detailed-route DRC errors | 0 |
| Antenna-violating nets/pins | 0 / 0 |
| Power-grid violations | 0 |
| Magic DRC errors | 0 |
| KLayout DRC errors | 0 |
| Magic/KLayout XOR differences | 0 |
| LVS errors | 0 |
| Routed wire length | 317 microns |
| Routed vias | 56 |

Unlike the DCO smoke target, the BBPD post-layout transient uses the filled
signoff-clean Magic RCX deck directly. It validates both phase polarities:
reference-leading feedback produces a wider `UP` pulse, and feedback-leading
reference produces a wider `DN` pulse. The post-layout PVT target validates the
same polarity across `tt`, `ff`, `ss`, `sf`, and `fs` using the filled RCX deck.
The TT dead-zone sweep uses the same filled RCX deck from simultaneous edges
through 1 ns of phase offset. It measured +13.464 ps of zero-offset `UP-DN`
width skew, reference-leading polarity correct down to 1 ps, and
feedback-leading polarity correct from 20 ps upward.
The all-corner dead-zone sweep measured worst-case sampled zero-offset skew of
+26.404 ps at `sf`, with feedback-leading polarity correct from 50 ps upward
in the slow-skew `sf` and `ss` corners.

The RTL keeps DCO load polarity separate from the other thermometer decoders.
`DCO_THERM_INVERT=1` is the default so top-level `DCO_CODE=0` enables all 255
dummy loads and `DCO_CODE=255` enables none. This makes increasing
`DCO_CODE` increase oscillator frequency, matching the loop filter's
increase-frequency command.
For the independent coarse-band fast path, the DLF polarity above still applies
to the full 8-bit fine code. Raising `COARSEBINARY_CODE` selects a faster
behavioral DCO band when `DCO_COARSE_STEP_MHZ` is nonzero, while the DLF trims
with the full fine-code span. A legacy packed diagnostic mode can still be built
with `DCO_COARSE_BITS>0`; in that mode raising `COARSEBINARY_CODE` replaces the
high fine-code bits and the DLF trims only the remaining low bits.

Check the structural Sky130 top integration path:

```sh
make -C OpenPLL check-sky130-macros
make -C OpenPLL check-top-macro-assembly
make -C OpenPLL hardtop-librelane-route
make -C OpenPLL check-hard-macro-top
make -C OpenPLL hardtop-librelane-signoff
make -C OpenPLL check-hard-macro-top-signoff
make -C OpenPLL check-hard-macro-top-spice
```

`check-sky130-macros` defines `USE_POWER_PINS`, includes the Sky130 primitive and
standard-cell Verilog models, and elaborates `IntegerPLL_Top` with the real
Sky130 BBPD/DCO wrappers. It also runs a deterministic top-control smoke with
macro-compatible shells, checking external DLF words 0, 512, and 1020 map to
8-bit DCO codes 0, 128, and 255 with matching 255-bit thermometer counts. The
Sky130 library models emit many Icarus timing-check warnings during the
real-wrapper compile; port or module mismatches should still fail the command.

`check-top-macro-assembly` verifies the signed-off digital-core, DCO, and BBPD
LEF/GDS/DEF/netlist/SDC views exist, have the expected macro sizes and pin
directions, and match the top-level interconnect for `BBPD[1:0]`,
`DCO_THERM[254:0]`, `PLLOUT`, and `CLKDIV_RETIMED`.

`hardtop-librelane-route` builds `IntegerPLL_HardMacroTop` from the signed-off
macro views and routes the top-level hard-macro integration through
`OpenROAD.DetailedRouting`. The promoted `check-hard-macro-top` result fixes
`phase_detector` at `(315, 40)`, `digital_core` at `(235, 180)`, and
`oscillator` at `(160, 620)`, with a 140 um DCO-to-digital routing channel. The
current routed top has three hard macros, 7739 standard-cell/tap/fill/antenna
instances, 193161 um route wirelength, 1934 vias, and zero final route DRC,
antenna, design-violation, and power-grid violation counts in the Librelane
detailed-route metrics.

`hardtop-librelane-signoff` runs the full hard-top Librelane signoff. The
promoted signoff artifact writes final DEF, GDS, KLayout GDS, LEF, Magic, ODB,
netlists, SDC, SDF, min/nom/max SPEF, extracted SPICE, Verilog header, render,
and metrics under:

```text
OpenPLL/openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/
```

The current top-level hard-macro signoff has zero final route DRC, antenna,
power-grid, Magic DRC, KLayout DRC, XOR, illegal-overlap, LVS, setup, hold,
max-slew, max-cap, max-fanout, and design-violation counts. The hard-top flow
intentionally black-boxes all three macro timing models so OpenROAD preserves
the physical LEF power pins; the digital-core timing evidence remains the
standalone force127 signoff run.

`check-hard-macro-top-spice` verifies the extracted top SPICE/SPEF wrapper as a
simulator-facing artifact. The current result checks 71 top-level ports, 255
DCO thermometer connections between the digital core and DCO, 44 antenna-repaired
DCO thermometer nets, 325 nominal SPEF nets, 9968 nominal SPEF capacitance
entries, and 1873 nominal SPEF resistance entries. It also generates
`build/hard_macro_top_spice/hard_macro_top_spice_norun.spice` and runs Xyce
`-norun` successfully on that inlined extracted-top deck.

`check-hard-macro-top-einvp-spice` performs the same extracted-interface audit
for the `IntegerPLL_HardMacroTop_EINVP` coarse-DCO signoff path. The current
result checks 73 top-level ports, the `IntegerPLL_DCO_EINVP_COARSE` oscillator
subcircuit, 255 DCO thermometer connections, 47 coarse thermometer
connections, 5 antenna-repaired DCO thermometer nets, 374 nominal SPEF nets,
10082 capacitance entries, and 1670 resistance entries, with Xyce `-norun`
completing syntax and topology analysis.

The promoted EINVP extracted-loop diagnostics are:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-startup-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-low-early-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-high-early-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-midcode-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-corner-midcode-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-progress-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-progress-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-hold-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-low-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-high-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-low-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-high-lock-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-low-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-high-diagnostic
```

These use the E hard-top distributed SPEF RC rather than just the extracted
wrapper topology. They pass with 2020 functional mapped digital-core cells,
4138 skipped physical-only cells, 261 selected hard-top SPEF nets, 1744
capacitance nodes, 1627 resistors, 260 digital pin substitutions, and 25247.633
fF selected capacitance. The startup deck measures 50.813495 MHz; the low-start
first-motion deck moves 0->2, and the high-start deck moves 255->243.019510.
The hard-top-loaded mid-code extracted-DCO lock-window deck starts at code 128,
retargets `REF` to 29.286759 MHz for the observed loaded E DCO, and holds
code 125..128 with 58.591120 MHz tail frequency and 0.017601 MHz target error.
The min/max E hard-top SPEF variants of that same near-lock deck also pass:
min SPEF selects 23096.023 fF, holds code 125..128, and measures 58.500163 MHz
with 0.073355 MHz target error; max SPEF selects 27119.190 fF, holds code
125..128, and measures 58.549789 MHz with 0.023730 MHz target error.
The low/high extracted-DCO progress decks use the same loaded reference and
normal enable timing. Low start moves code 0->62 over 84..359 ns; its late
window 280..359 ns spans code 42..62 and measures 53.728266 MHz. High start
moves code 255->172; its late window spans code 172..192 and measures
62.952232 MHz. Extending the extracted-DCO decks to rail-start lock windows
passes both sides: low start runs to 900 ns, holds codes 122..128 in the
760..899 ns tail window, and measures 58.485654 MHz with 0.087865 MHz target
error; high start runs to 760 ns, holds codes 126..132 in the 650..759 ns tail
window, and measures 58.804895 MHz with 0.231377 MHz target error.
The FF/SS mid-code hold diagnostic keeps `DLF_KI=0` and `DLF_KP=0`, holds the
extracted loop at code 128 through the same filled BBPD RCX, filled
`IntegerPLL_DCO_EINVP` RCX, and nominal distributed hard-top SPEF RC, and
measures hard-top-loaded code-128 tails of 81.712756 MHz at FF and
38.846037 MHz at SS. This calibrates PVT lock targets. Enabling normal loop
gains at those calibrated references gives FF/SS near-lock evidence through the
same extracted deck: FF holds code 125..134 and measures 81.575035 MHz with
0.137721 MHz target error, while SS holds code 126..128 and measures
38.821045 MHz with 0.024993 MHz target error. The FF rail-start PVT rows are
700 ns extracted-loop diagnostics: low start moves code 0->122, holds code
122..128 in the 580..699 ns tail window, and measures 81.480028 MHz with
0.232728 MHz target error; high start moves code 255->127, holds code
127..133 in the same tail window, and measures 82.095815 MHz with
0.383059 MHz target error. The SS low-rail 1400 ns extracted-loop diagnostic
also passes: it moves code 0->122, holds code 122..128 in the 1160..1399 ns
tail window, and measures 38.769491 MHz with 0.076546 MHz target error. The SS
high-rail 1400 ns extracted-loop diagnostic also passes: it moves code
255->127, holds code 127..133 in the 1160..1399 ns tail window, and measures
39.009555 MHz with 0.163517 MHz target error. Together these rows provide
FF/SS two-rail extracted-loop PVT lock evidence for the nominal E hard-top
distributed-RC view.
The calibrated behavioral-DCO lock-window decks use the measured E five-point
RCX table and lumped E hard-top SPEF capacitance. They pass from both rails:
low-start moves 0->122 with response 128 and 59.936383 MHz tail frequency,
while high-start moves 255->133 with response 124 and 60.235253 MHz tail
frequency.

Run the representative transistor-level DCO validation:

```sh
make -C OpenPLL spice
```

The current typical-corner sweep validates top-level `DCO_CODE` values 0, 64,
128, 192, and 255 with a measured range of roughly 99.836 MHz to 133.013 MHz.
The compact endpoint PVT target validates codes 0 and 255 at `tt`, `ff`, `ss`,
`sf`, and `fs`, with a measured span of roughly 66.343 MHz to 187.985 MHz. The
BBPD SPICE target validates both phase polarities. The synthesized DCO decoder
target validates sampled thermometer taps at seven boundary/adjacent codes, the
full-tap decoder target validates all 255 DCO thermometer outputs at those
codes, and the all-code/all-tap decoder target validates all 256 `DCO_CODE`
values against all 255 DCO thermometer outputs with a batched ngspice DC sweep.
See
`SPICE_VALIDATION.md` for measured tables and remaining validation gaps. The DCO
SPICE sweep also fails the run if measured frequency is non-monotonic for the
tested code sequence.

Run the PLL-level SPICE acquisition check:

```sh
make -C OpenPLL spice-pll-loop
make -C OpenPLL spice-pll-loop-filled-dco
make -C OpenPLL spice-pll-loop-pvt
```

This uses transistor-level Sky130 BBPD cells, an ideal divider, and a behavioral
DCO frequency model fitted to the no-fill post-layout DCO RCX smoke results. It
currently acquires from both code 0 and code 255 toward the 56.0 MHz target for
`REF=11.2 MHz` and `NDIV=5`, with the current no-fill endpoints mapping that
target to code 142.320. The PVT target uses measured all-code DCO spans at
`tt`, `ff`, `ss`, `sf`, and `fs`, picks target code 128 in each corner, and
derives a per-corner reference because the measured DCO PVT spans do not fully
overlap. Both low-start and high-start cases pass in all five corners with a
25 LSB/us numerical code-slew setting over 20 us.

The filled-DCO calibrated target uses the same loop harness but fits a
five-point DCO model to the filled signoff RCX transient measurements at codes
0, 64, 128, 192, and 255. It targets the measured filled code-128 frequency
49.762118 MHz with `REF=9.95242356154668 MHz` and `NDIV=5`; both low-start and
high-start cases pass with a 24 LSB/us numerical code-slew setting over 18 us.
After the reset-pulse fix, the low-start case ends at code 145.117 with
+0.651 MHz final-window average error, and the high-start case ends at code
117.597 with -0.414 MHz error.

The sampled filled-DCO variant is kept as a diagnostic target:

```sh
make -C OpenPLL spice-pll-loop-filled-dco-sampled
make -C OpenPLL spice-pll-loop-sampled-gain-sweep
make -C OpenPLL spice-pll-loop-sampled-pi-sweep
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-aperture-sweep
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-lock
```

It uses the same five-point DCO model but updates the numerical code state
around feedback-edge sample apertures with `DLF_STEP=2.5` LSB/update. After
the reset-pulse fix and held-decision model update, the default low-start
diagnostic fails at code 74.086 with -1.332 MHz average error, while the
high-start case passes at code 113.513 with -0.410 MHz error. This means the
LSB/update tests are useful for gain and sampling sensitivity, but are not
promoted as lock validation evidence yet. The sampled gain-sweep target covers
`DLF_STEP` values of 2.5, 3.0, and 3.5 LSB/update at 0, 150, and 300 ps sample
delay using independent ngspice jobs. No point in that 9-case grid passes both
low-start and high-start acquisition. The sampled PI target adds a held sampled
BBPD decision and a proportional `DLF_PROP_LSB` offset; five of its 16 tested
points pass both rails. The best tested row is `DLF_STEP=3.5`,
`DLF_PROP_LSB=4`, and 0 ps sample delay, ending at codes 123.443 and 140.087
with 0.351 MHz worst final-window average error. This supports using
proportional gain, but it is not yet a final RTL gain selection because
`DLF_PROP_LSB=4` is a sampled-loop surrogate gain, not the RTL `DLF_KP` value
directly. RTL `DLF_KP=4` is approximately `DLF_PROP_LSB=1`, while the current
filled-DCO behavioral recommendation `DLF_KP=32` is a stronger proportional
setting. RTL `DLF_KI=255` is only about 0.25 8-bit DCO-code LSB per update, so
the larger sampled-SPICE steps are accelerated surrogate gains.

The filled-BBPD sampled Xyce aperture sweep uses the post-layout BBPD RCX deck
with `DTMAX=1 ns` and scans high-start sample aperture phase. The current best
short row uses `DLF_STEP=3.5`, `DLF_PROP_LSB=4`, 150 ps sample delay, and
initial DCO phase 0.25 cycles; it moves high-start from code 255 to 216.733 in
2 us. An 8 us follow-up at the same aperture moves from code 255 to 188.862.
Increasing the sampled integral step at the same aperture gives a passing
two-rail filled-BBPD sampled Xyce lock probe: `DLF_STEP=17.5`,
`DLF_PROP_LSB=4`, 150 ps sample delay, initial DCO phase 0.25 cycles, 2.5 us
simulation time, and `DTMAX=1 ns` end at codes 100.826 and 123.852 with
0.694 MHz worst final-window average error. This is useful promoted surrogate
evidence for the filled BBPD macro, but it is still not a full extracted
transistor-level PLL simulation.

A four-phase robustness check at that same gain under
`build/spice_pll_filled_bbpd_sampled_xyce_phase_robustness/` shows the limit of
the evidence: only the original initial phase 0.25 cycle passes both rails.
Initial phase 0.0 fails low-start, phase 0.5 fails both rails, and phase 0.75
fails both rails. The passing target should therefore be read as a fixed-aperture
filled-BBPD surrogate, not as robust lock across arbitrary initial phase. A
4 us rerun of the same point and a KP32-like `DLF_PROP_LSB=8` phase probe also
fail to pass all four phases, so stronger proportional action in this sampled
surrogate is not enough to promote the post-layout-BBPD loop evidence. An
experimental `sampled_latched` SPICE surrogate was also tried at the same gain;
both loop-current signs fail the four-phase filled-BBPD Xyce diagnostic, so it
is not promoted.

These PLL-level checks are useful loop-polarity and acquisition evidence, but
they are not a substitute for a full extracted transistor-level PLL simulation.
The real RTL loop filter is digital and uses `DLF_KI`/`DLF_KP` fixed-point
updates, not a charge-pump current.

The slow extracted mapped-loop Xyce diagnostics are also not app-note
mixed-signal co-simulations. They elaborate the mapped digital-core netlist as
Sky130 standard-cell SPICE and solve those cells as analog devices together
with the BBPD, DCO, and selected SPEF RC. A faster Xyce mixed-signal path should
use Xyce `YADC`/`YDAC` bridge devices: Xyce owns the analog BBPD/DCO state, and
an external Python, Icarus/VPI, or compiled C-interface digital driver updates
the divider, DLF, and thermometer code. The current reference environment lacks
`libxycecinterface.so`, so
`make -C OpenPLL xyce-mixed-signal-status` reports the bridge-device probe as
available but the shared co-sim interface as missing. A compiled static
C-interface route is available, however: `make -C OpenPLL xyce-cinterface-smoke`
passes a small YADC/YDAC stepping check, and
`make -C OpenPLL xyce-bbpd-cinterface-smoke` passes on the filled BBPD RCX macro
with YDAC-driven REF/feedback and YADC-observed UP/DN pulse polarity.
`make -C OpenPLL xyce-pll-mixed-signal-smoke` now uses that same extracted BBPD
inside a short C-interface mixed-signal loop: an external C++ driver owns the
divider timing, fixed-point DLF update, and a behavioral DCO frequency table
calibrated from filled `IntegerPLL_DCO_EINVP` RCX TT points. This is the
practical base for gain tuning because it moves the divider/DLF out of the
analog matrix. It is not yet full post-layout PLL validation because the DCO
and digital loop are behavioral in the driver; only the BBPD macro is filled
post-layout RCX in this mixed smoke.

`make -C OpenPLL xyce-pll-mixed-signal-gain-sweep` adds a focused comparison at
`KI=160`, `FRAC=6`, `boost_shift=4`, and `boost_after=2`, sweeping `KP=0` and
`KP=8` from codes 96 and 160 for 10 reference cycles. The latest mixed-BBPD RCX
run passes all four motion checks. It also gives useful proportional-gain
evidence: the `KP=0` low-start row ends at code 126 without an exact target hit,
while the `KP=8` low-start row reaches exact code 128 at cycle 9. Both
high-start rows cross the target and overshoot, so the mixed sweep supports
nonzero P for responsiveness but does not yet close the final lock/settling
tuning question.

That mixed-signal CSV is now covered by the promoted artifact checker as
`xyce_cinterface_mixed_signal_gain_sweep`; the checker also includes
`objective_deliverable_evidence`, a direct requirement-level proof of the Sky130
top, 8-bit control, frequency range, and extracted lock-window evidence. The
checker passes 69 artifact checks after refreshing the top-macro assembly
summary. Longer mixed C-interface
diagnostics confirmed the remaining damping issue: the original `KI=160`,
`KP=8`, `boost_shift=4`, `boost_after=2` point walks to codes 156/90 after 20
cycles, and the milder `KI=192`, `KP=8`, `boost_shift=3`, `boost_after=2` point
ends low/high at 132/85 after 20 cycles. Treat those as negative settling
evidence, not as final gain signoff.

Do not assume the C-interface targets can be made faster by wrapping the
compiled driver with `mpirun`. In the current environment, a two-rank YADC/YDAC
smoke reaches Xyce completion but leaves both driver ranks stuck, so
C-interface MPI is not promoted as a usable distributed mixed-signal flow.

Filled post-layout BBPD in-loop continuous-mode diagnostics are not yet practical
validation targets. The ngspice 18 us acquisition deck times out with the filled
BBPD RCX macro, and the reset-stable continuous Xyce diagnostic sweep still does
not pass robust both-rail acquisition:

```sh
make -C OpenPLL spice-pll-loop-filled-bbpd-xyce-sweep
```

The current resolved 4 us grid uses an explicit Xyce `DTMAX=1 ns`; without that
fourth `.TRAN` argument, Xyce takes too few accepted timesteps and can leave
the filled BBPD outputs latched for microseconds. No row passes both rails. The
best max-error row is 64 LSB/us: low-start ends at code 23.778 and high-start
ends at code 242.918, with 2.746 MHz worst average error. A 20 us polarity
cross-check confirms `LOOP_SIGN=+1` is the moving polarity; `LOOP_SIGN=-1`
leaves both rails stuck. Runtime is the practical limit: a 4 us, two-rail
resolved probe takes roughly 110 s per gain point on the current serial Xyce
build. The installed Xyce reports `Serial` from `Xyce -capabilities`; in the
recorded validation environment, `mpirun` starts duplicate serial Xyce
processes, so the practical
multicore speedup is `--jobs` across independent sweep decks. If an MPI-enabled
Xyce deck converges, set `XYCE_MPI_PROCS=N` for each deck and reduce
`SPICE_PLL_SWEEP_JOBS` as needed to avoid oversubscribing the machine.

Run the digital-loop gain sweep:

```sh
make -C OpenPLL digital-loop-gain-sweep
```

This is an RTL acquisition check for the real digital loop filter, not SPICE.
It sweeps `DLF_KI` and `DLF_KP` using a registered ideal sign detector and
verifies that low-start and high-start cases acquire to target `DCO_CODE=128`.
With the corrected 200 us window, the rescaled proportional path, and the
first-decision BBPD latch, `DLF_KI=64`, `DLF_KP=0` is the lowest-gain passing
point at 150.308 us worst-case lock time. The exact-code ideal-detector point is
`DLF_KI=255`, `DLF_KP=2`, which locks in 37.627 us worst-case. The stronger
filled-DCO acquisition candidate is `DLF_KI=255`, `DLF_KP=32`: it locks in
34.375 us worst-case in the ideal bench and leaves only one final code of error
there. Final gain selection still needs phase-domain stability and jitter
validation.

Run the top-level behavioral phase acquisition check:

```sh
make -C OpenPLL pll-top-model-acq
```

This instantiates `IntegerPLL_Top` with the behavioral DCO and two-flop BBPD
models, sets `MMDCLKDIV_RATIO=8` and `REF=12.742100 MHz`, and verifies the
legacy `DLF_KI=255`, `DLF_KP=4` setting from both code 0 and code 255. The
current result is low-start code 0 to 127 with 37.408 us lock, and high-start
code 255 to 128 with 22.446 us lock.

Run the top-level behavioral phase acquisition check with the filled-RCX DCO
calibration:

```sh
make -C OpenPLL pll-top-filled-dco-acq
make -C OpenPLL pll-top-filled-dco-gain-sweep
```

This enables the five-point filled-DCO behavioral model and uses
`MMDCLKDIV_RATIO=8`, `REF=6.220298 MHz`, a 16-code target tolerance, and the
promoted `DLF_KI=255`, `DLF_KP=32` setting. The current result is low-start
code 0 to 136 with 70.244 us lock, and high-start code 255 to 136 with
66.519 us lock. Both cases pass by entering the 16-code target window and
reaching exact code 128 transiently. The gain sweep checks `DLF_KI` 192 and 255
against `DLF_KP` 0, 4, 8, 16, and 32. Nine of ten points pass; the
`DLF_KI=255`, `DLF_KP=0` row reaches the target transiently but fails the
220 us endpoint tolerance, while `DLF_KI=255`, `DLF_KP=32` is the fastest
passing row and finishes within eight codes from both rails. This is behavioral
phase-domain evidence; extracted jitter/stability validation is still required.

Run the synthesized DLF proportional-path SPICE check:

```sh
make -C OpenPLL spice-dlf-static
make -C OpenPLL spice-dlf-static-kp16
make -C OpenPLL spice-dlf-static-kp32
```

This extracts a 109-cell Sky130 combinational cone from the mapped digital core
and verifies that mid-scale hold/increase/decrease cases produce `DCO_CODE`
128, 129, and 127 with `DLF_KI=255`, `DLF_KP=4`. The `kp16` and `kp32`
variants verify stronger-P candidates. KP16 measures hold/increase/decrease
codes 128, 132, and 124; KP32 measures 128, 136, and 120.

Run the synthesized DLF sequential update SPICE check:

```sh
make -C OpenPLL spice-dlf-update
make -C OpenPLL spice-dlf-update-kp16
make -C OpenPLL spice-dlf-update-kp32
make -C OpenPLL spice-dlf-update-full-kp32-overlap
make -C OpenPLL spice-dlf-update-signoff-nl-kp32
make -C OpenPLL spice-dlf-update-signoff-spef-kp32
make -C OpenPLL spice-dlf-update-signoff-spef-rc-kp32
make -C OpenPLL spice-bbpd-dlf-integration
make -C OpenPLL spice-bbpd-dlf-integration-full
make -C OpenPLL spice-bbpd-dlf-integration-signoff-spef-rc
make -C OpenPLL spice-pll-mapped-loop-smoke
make -C OpenPLL spice-pll-mapped-loop-gain-sweep
make -C OpenPLL spice-pll-mapped-loop-phase-sweep
make -C OpenPLL spice-pll-mapped-loop-progress-1us
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-smoke
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-startup-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-low-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-high-diagnostic
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-startup
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-motion
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu
```

This extracts the sequential DCO-code update cone from the mapped digital core
and uses Xyce to verify both BBPD directions and reset-overlap first decision
capture. The `kp32` cone currently contains 330 mapped cells after the
BBPD-event reset gating and DLF rail-escape fix. The check records both final
code and the directional
response-window code, because the proportional term can be a transient bump
while the integral term moves by less than one exported 8-bit DCO-code LSB.
For `DLF_KI=255`, `DLF_KP=32`, the refreshed cone run passes UP, DN,
UP-then-`2'b11`, and DN-then-`2'b11` cases: UP reaches response code 136 from
128, while DN reaches a lower response code and ends at 127. The full-core KP32
overlap target uses all mapped cells and also passes the reset-overlap cases.
The installed Xyce binary reports
`Serial`, so `mpirun` cannot parallelize a single circuit solve with this
build; the DLF-update targets instead use `SPICE_PLL_SWEEP_JOBS` to run
independent cases concurrently. An MPI-enabled Xyce build is available at
`$XYCE_MPI_ROOT/bin/Xyce`, but it currently aborts at the first
25 ps step on the full mapped standard-cell DLF deck, so the promoted full-core
artifacts use `` in serial mode.

`spice-dlf-update-signoff-nl-kp32` checks the current LibreLane signoff metrics
and then reads
`openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/nl/IntegerPLL_DigitalCore.nl.v`.
The parser handles the final post-PnR netlist syntax and extracts a 540-cell
DCO-code update cone from the 5643 parsed `sky130_fd_sc_hd` instances. With a
compressed 24 ns Xyce window, the final-netlist cone passes the same KP32
increase, decrease, UP-then-`2'b11`, and DN-then-`2'b11` checks. This is
post-PnR gate-netlist transistor-level evidence, but the transient deck still
does not include SPEF interconnect parasitics.

`spice-dlf-update-signoff-spef-kp32` adds the nominal final SPEF total
capacitance for every modeled cone net as a lumped capacitor. The current run
adds 582 capacitors totaling 2678.819 fF to the same 540-cell final-netlist
cone, and the four KP32 directional update cases still pass. This validates
post-route capacitive loading for the DLF update cone; distributed SPEF
resistance and coupling topology are not inserted yet.

`spice-dlf-update-signoff-spef-rc-kp32` substitutes final SPEF instance-pin
nodes into that cone and inserts the nominal SPEF resistance tree plus grounded
capacitance at SPEF nodes. The current decks contain 540 cells, 2056 substituted
pin nodes, 3373 `CSPEF_*` caps, and 2513 `RSPEF_*` resistors; all four KP32
directional update cases pass. Coupling entries are grounded at the current-net
endpoint to keep the reduced cone self-contained, so this is distributed
post-route RC evidence for the DLF cone, not a full-chip extracted transient.

`spice-bbpd-dlf-integration` uses the filled BBPD Magic RCX deck to drive the
same mapped DLF update cone. The BBPD reset is held until `DLF_En=1` and
`DLF_Clear=0`, matching the top-level reset policy. With `DLF_KI=255`,
`DLF_KP=32`, REF-leading feedback reaches response code 136 from 128, and
feedback-leading REF reaches a lower response code and ends at 127. The DLF
update clock is still a boundary source in this target, so it verifies the
BBPD-output/DLF-input electrical interface but is not a full closed-loop
oscillator simulation.

`spice-bbpd-dlf-integration-full` runs the same filled-BBPD-RCX stimulus
through the full mapped digital-core netlist. It passes the same directional
response checks. On the current serial Xyce build, those two full-core cases
took about 306 s each when launched as independent simulator processes.

`spice-bbpd-dlf-integration-signoff-spef-rc` drives the final 540-cell DLF
cone plus distributed nominal SPEF RC from the filled BBPD RCX macro. The
REF-leading case ends at code 136 with response code 152, and the
feedback-leading case ends at code 120 with response code 32. Each deck includes
2056 substituted SPEF pin nodes, 3373 `CSPEF_*` caps, and 2513 `RSPEF_*`
resistors, plus the BBPD RCX subcircuit.

`spice-pll-mapped-loop-smoke` closes a short feedback-divider-included path
through the full mapped digital-core netlist. The mapped MMD divider drives
`CLKDIV_RETIMED`, the filled BBPD RCX macro compares it against `REF`, and the
mapped DLF updates `DCO_CODE`; the DCO is still the five-point behavioral model
fitted to filled-DCO RCX measurements. With `DLF_KI=255`, `DLF_KP=32`, and
`MMDCLKDIV_RATIO=2`, phase-selected low/high cases pass in a 180 ns Xyce run:
low start at initial DCO phase 0.0 moves code 0 to 8, and high start at phase
0.25 moves code 255 to 247. This proves the mapped divider/BBPD/DLF loop
connectivity and polarity for one short window, not full extracted PLL lock
robustness.

`spice-pll-mapped-loop-gain-sweep` keeps that same mapped divider, filled BBPD
RCX macro, mapped DLF, and behavioral filled-DCO calibration, then sweeps
`DLF_KP` from a code-128 start under an upward decision. The 180 ns Xyce rows
are monotonic: `DLF_KP=0,4,8,16,32` produces response deltas
0, 1, 2, 4, and 8 DCO-code LSB. This is the mapped-loop gain-tuning companion
to the extracted-DCO KP0/KP32 mid-code anchors below.

The mapped-loop generator also has a diagnostic extracted-DCO mode through
`--dco-impl postlayout`. It instantiates the filled DCO RCX macro on the mapped
`DCO_THERM[254:0]` decoder outputs while keeping the filled BBPD RCX macro in
the loop. `spice-pll-mapped-loop-extracted-dco-startup` promotes a serial-Xyce
startup smoke for the low-start case with `uic` plus a VPWR/VPB rail ramp. The
50 ns run uses the full 906-cell mapped digital core, filled BBPD RCX, and
filled DCO RCX; it observes two `PLLOUT` rises after 15 ns, a 21.616261729 ns
startup period, and a 46.261467988 MHz startup frequency. Because `DLF_En` has
not yet asserted in this window and the DCO code remains effectively 0, this is
startup evidence for the coupled extracted-DCO deck, not code-correction or
lock evidence. `spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu` runs the
same startup deck with `$XYCE_MPI_ROOT/bin/Xyce -linsolv KLU` and
four MPI ranks, meaning `mpirun -np 4` rather than four Xyce threads. That row
also passes, with a 21.616261760 ns startup period and 46.261467923 MHz startup
frequency, and completed in 226.138 s versus 440.731 s for the serial run on
the recorded validation environment. Four ranks are the current empirical default, not a proven
optimum for all extracted-DCO decks. A short 12 ns extracted-DCO debug timing
sweep measured 169.042 s at 1 rank, 123.398 s at 2 ranks, 84.596 s at 4 ranks,
68.961 s at 8 ranks, and 57.493 s at 16 ranks; a 32-rank launch failed because
Open MPI exposed only 16 slots by default. Those 12 ns rows are timing-only
debug runs, not functional validation rows, because the window captures only one
`PLLOUT` rise. The FRAC=6 260 ns companion rows below confirm that 16 ranks
improve wall time on real extracted-DCO loop decks while preserving endpoint
behavior. The explicit KLU override is required: the same MPI-capable Xyce
binary without `-linsolv KLU` leaves the sampled DCO thermometer inputs low and
does not start the oscillator, even at one rank.

`spice-pll-mapped-loop-extracted-dco-motion` extends that coupled extracted-DCO
deck to 180 ns from both rails. Low start moves code 0 to response/end code 8;
high start begins at code 255, reaches a downward response code of 166.034845,
dwells at code 247 for 37.150000 ns in the response window, and returns to code
255 by the endpoint. Low start dwells at code 8 for 41.612512 ns. The debug
CSV now reports the DLF integrator separately from the visible proportional
output: low-start integrator code remains 0.00 across the measurement window,
while high-start moves from 255.00 to 254.75.

`spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu` repeats those 180 ns
first-correction decks with `$XYCE_MPI_ROOT/bin/Xyce -linsolv KLU`
and four MPI ranks. The MPI/KLU rows match the serial response metrics: low
start reaches code 8 with a 41.609479 ns dwell, and high start reaches response
code 166.034845 with the same 37.150000 ns dwell at code 247. The elapsed times
were 692.448 s and 512.197 s, respectively, in the recorded validation environment.

`spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu` and
`spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu` extend the MPI/KLU
decks to 260 ns. Low start keeps visible DCO code at code 8 after the first
proportional correction, while the internal DLF integrator advances from 0.00 to
0.25 DCO-code units by 259 ns. High start ends at visible code 246, reaches a
minimum integrator code of 254.00 DCO-code units, and dwells for 56.925000 ns in
the code-246/247 band. The runs record 11 and 13 `PLLOUT` rises, 46.220481051
MHz and 52.482096017 MHz startup frequencies, and 818.450 s and 691.313 s
elapsed wall time in the recorded validation environment. This is the current strongest extracted-DCO
loop evidence: it proves first directional DLF output movement and slow integral
accumulation in both directions through the full 906-cell mapped digital core
with filled BBPD RCX and filled DCO RCX, but it is still not closed-loop
acquisition or lock validation.

The FRAC=6 extracted-DCO trend targets
`spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu` and
`spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu` repeat that
260 ns coupled check using the 889-cell FRAC=6 mapped core. Low start improves
from visible code 8 to code 9 and raises integrator movement from 0.25 to 1.75
DCO-code units. High start still ends at visible code 246, but the integrator
ends at 254.00 instead of 254.75 and the old transient dip to code 166 is gone.
The phase-0.5 high-start repeat
`spice-pll-mapped-loop-frac6-extracted-dco-high-phase0p5-trend-mpi4-klu`
matches the phase-0.25 waveform sequence and endpoint: visible code 255 to 246,
integrator 255.00 to 254.00, 13 `PLLOUT` rises, 52.447728469 MHz startup
frequency, and 667.423 s elapsed wall time. This is stronger extracted-loop gain
evidence for FRAC=6 and a neutral phase-sensitivity check, but still not lock.
The MPI16 companion targets
`spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu` and
`spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu` reproduce the
same endpoints and integrator motion while reducing wall time to 568.490 s and
467.746 s, respectively, versus 800.325 s and 669.374 s for MPI4.

`spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu` extends
that true rail-start extracted-DCO check to 500 ns. Low start moves visible code
0 to 15 with integrator 7.75, and high start moves visible code 255 to 240 with
integrator 248.00. The rows use two concurrent MPI16/KLU Xyce jobs and record
1473.445 s and 1408.858 s elapsed wall time. The tail frequencies are still
46.243607848 MHz and 53.072273197 MHz against the 49.762117808 MHz target, so
this is stronger rail-start progress evidence but not lock.

`spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu` tests
whether the `DLF_En=85 ns` release timing from the near-high local lock row also
helps rail starts. It does not: low-start only responds transiently to code 8
and returns to code 0 by 299 ns with integrator 0.75, while high-start moves
255 to 244 with integrator 252.00. This keeps enable85 as a phase-selected
near-lock aid, not the promoted rail-start setting.

`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu` is one of
the current strongest extracted-DCO near-lock rows. It starts the FRAC=6,
`DLF_KI=255`, `DLF_KP=32` loop at code 128, runs 220 ns with MPI16/KLU, stays
inside code 127..140 over the 139..219 ns lock window, ends at visible code
137 with integrator 129.75, and measures 49.676823500 MHz against the
49.762117808 MHz target. This supports the local gain setting near the target
code, but it starts near lock and is not rail-start acquisition.

`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu`
checks the lower-P `DLF_KI=192`, `DLF_KP=8` candidate from the behavioral
filled-DCO top sweep in the same extracted mid-code deck. It is intentionally
non-promoted: visible code moves only 128 to 131 with integrator 129.50, but
the 139-219 ns tail is 49.488441487 MHz, 0.273676 MHz below target, so it
misses the tighter 0.15 MHz bound and is worse than the promoted KP32 row.

The non-promoted diagnostic
`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu`
starts the same loop at code 160 and requires downward motion plus the 0.25 MHz
tail-frequency bound, but it currently fails cleanly: code moves upward to 169,
the integrator advances from 160.00 to 161.75, and the 139-219 ns tail frequency
is 50.602594662 MHz. This is useful phase/tuning evidence because it shows the
short extracted loop can still move the wrong way from a nominally high local
start; it is not promoted lock evidence.

`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu`
reruns that local high-side start with `DLF_En=85 ns`, after the REF edge and
before the feedback edge. The first captured BBPD decision is DN, and the 380 ns
MPI16/KLU artifact passes `lock_window`: visible code moves 160 to 146,
integrator moves 160.00 to 154.00, and the 299-379 ns tail measures
50.001270745 MHz, 0.239153 MHz above target, over four rises. The row gives the
mid-code check a useful high-side companion, but it is still release-phase
selected and does not prove rail-start lock.

`spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu` starts that same
extracted-DCO deck at code 128 and phase-selects an upward decision. The 180 ns
run moves visible `DCO_CODE` from 128 to 136, keeps the internal integrator at
128.00, records eight `PLLOUT` rises and a 48.898483569 MHz startup frequency,
and dwells at code 136 for 47.250000 ns. This is mid-code proportional-path and
gain-polarity evidence, not acquisition or lock evidence.

`spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu` uses the same
initial code, phase, BBPD RCX, DCO RCX, and MPI4/KLU solver settings with
`DLF_KP=0`. It completes with visible `DCO_CODE` held at 128 for the full
79-179 ns measurement window and 99.725000 ns of code-128 dwell. This makes the
need for nonzero proportional gain visible in the extracted loop without
claiming acquisition or lock.

The artifact audit also measures `PLLOUT` over 119-179 ns for those two
extracted-DCO mid-code rows. KP32 averages 49.699374052 MHz, KP0 averages
49.464265788 MHz, and the 0.235108264 MHz delta confirms the visible code
movement is reflected at the oscillator output.

`spice-pll-mapped-loop-signoff-nl-smoke` runs the same short first-correction
loop through the final digital-core signoff netlist. The simulator drops
physical-only tap, fill, decap, and antenna diode cells for Xyce compatibility;
the resulting functional signoff deck contains 1614 mapped cells and omits
4029 physical-only cells. Low start moves through response code 8, and high
start reaches response code 190 in the 180 ns window. This is stronger
signoff-netlist connectivity evidence, but the DCO is still behavioral.

`spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke` repeats a short
mapped-loop smoke using the hard-top-consistent FRAC=6 force-to-mid final
digital-core signoff netlist, `DLF_KI=160`, `DLF_KP=8`, and the MPI/KLU Xyce
binary at four ranks per rail-start case. It drops 4138 physical-only cells
from that final netlist, keeps 2020 functional mapped cells, and adds lumped
nominal hard-macro-top SPEF capacitance on 261 loop/inter-macro nets. Those
loads include all 255 DCO thermometer interconnects and total 27097.842 fF.
The behavioral DCO observes the loaded `DCO_THERM` bus rather than the debug
`DCO_CODE` bus, matching the hard DCO macro control interface. With the extra
hard-top loading, low-start moves through response code 22 in a 220 ns window
and high-start moves down through response code 233. This is stronger
top-level interconnect-loading evidence than the plain final-netlist smoke, but
it is still a behavioral-DCO mapped-loop transient with lumped top-level SPEF
capacitance, not a full extracted hard-macro-top closed-loop transient.

`spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-startup-diagnostic` is an
optional topology diagnostic for the same final signoff netlist and gains. It
substitutes the selected digital-core and macro pins onto distributed hard-top
SPEF RC networks rather than collapsing those nets to lumped capacitance. The
generated low-start deck covers the same 261 hard-top loop/inter-macro nets,
emits 1752 grounded capacitance nodes and 1657 resistors, substitutes 260
digital pins, and covers all 255 DCO thermometer interconnects for 27097.841 fF
total selected capacitance. The 60 ns startup check passes with three PLLOUT
rises and a measured 46.270645 MHz startup frequency. On this host, the same
deck completed in 223.14 s at one Xyce process, 132.59 s at four MPI ranks,
104.51 s at eight ranks, 90.09 s at 16 ranks, and 132.82 s at 32 hardware-thread
ranks, so the target defaults to 16 MPI ranks. This is a distributed-RC syntax,
topology, and startup check, not a two-rail motion or lock signoff.

`spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-startup-diagnostic`
is the extracted-DCO companion. It uses the final force-to-mid signoff
digital-core netlist, filled BBPD RCX, filled DCO RCX, and the same distributed
hard-top SPEF RC selection. The 50 ns low-start deck has 2020 functional mapped
cells, skips 4138 physical-only cells, keeps 261 hard-top SPEF nets with 1752
capacitance nodes and 1657 resistors, substitutes 260 digital pins, and includes
27097.841 fF of selected hard-top capacitance. It passes startup with two PLLOUT
rises after 15 ns, a 21.643727 ns period, and 46.202763 MHz measured startup
frequency. The full Xyce/MPI16/KLU run reported 63443 devices, 182651 unknowns,
and about 225.884 s elapsed time. This proves elaboration and startup for the
combined extracted-DCO plus hard-top RC deck, but it is not two-rail motion,
lock, or PVT signoff.

`spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-low-diagnostic`
and
`spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-high-diagnostic`
extend that same combined deck through the first active DLF update. With
`DLF_En=85 ns` and the 84..99 ns measurement window, low-start moves from code 0
to 2 with response code 2 and 46.150194 MHz startup frequency, while high-start
moves from code 255 to 253 with response code 253 and 50.278137 MHz startup
frequency. Both 100 ns decks contain 2020 functional mapped cells, skip 4138
physical-only cells, and include 261 selected hard-top SPEF nets, 1752
capacitance nodes, 1657 resistors, 260 digital pin substitutions, and 27097.841
fF selected hard-top capacitance. Xyce/MPI16/KLU reports 63443 devices and
182651 unknowns; elapsed time was 487.306 s for low-start and 538.010 s for
high-start. This is two-sided first closed-loop motion evidence for the combined
extracted-DCO plus hard-top RC deck, not acquisition, lock, or PVT signoff.

`spice-pll-mapped-loop-phase-sweep` is the corresponding promoted robustness
probe. It runs low/high rail starts at initial DCO phases 0, 0.25, 0.5, and
0.75 cycles using independent Xyce jobs. The target now uses the same 180 ns
window as the smoke target and the refreshed sweep passes both rail starts at
all four tested phases: low-start response code is 8 at every phase, while
high-start response code is 246 or 247. The result is stronger first-correction
evidence, but it is still a short behavioral-DCO transient rather than full
extracted PLL lock evidence.

`spice-pll-mapped-loop-progress-1us` extends the same mapped-core, filled-BBPD
RCX, behavioral filled-DCO setup to 1 us at `DLF_KI=255`, `DLF_KP=32` using
the MPI-enabled Xyce/KLU binary.
Low-start moves from code 0 to 9 and reduces frequency error from -3.505392 MHz
to -3.267220 MHz; high-start moves from code 255 to 243, reaches response code
145.808033 during the window, and reduces frequency error from +2.587713 MHz to
+2.448400 MHz. This proves continued closed-loop progress beyond the first
correction, but it is not acquisition or lock. The MPI4/KLU run completed in
356.177 s for low start and 445.105 s for high start, versus 611.898 s and
751.432 s for the earlier serial Xyce artifact with the same endpoint metrics.
A non-promoted KP128 500 ns diagnostic reaches larger transient response codes
but falls back to the rail endpoints; stronger proportional gain alone is not a
substitute for faster integral convergence.

The current gain-tuning candidate is to keep the 10-bit DLF word and exported
8-bit DCO code, but reduce `DLF_FRAC_WIDTH` from 8 to 6. This uses the existing
RTL parameter as an integral-step scaling knob: `DLF_KI=255` becomes about one
8-bit DCO-code LSB per accepted BBPD decision instead of about 0.25 LSB. The
diagnostic targets are `digital-loop-gain-sweep-frac6`,
`pll-top-filled-dco-gain-sweep-frac6`, and
`spice-pll-mapped-loop-frac6-progress-1us`; the high-start phase diagnostic is
`spice-pll-mapped-loop-frac6-high-phase-500ns`. The extracted-DCO FRAC=6 trend
targets are `spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu` and
`spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu`, plus the
phase-0.5 high-start repeat
`spice-pll-mapped-loop-frac6-extracted-dco-high-phase0p5-trend-mpi4-klu`.
The rank-configurable companion targets are
`spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi-klu` and
`spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi-klu`; the convenience
aliases `spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu` and
`spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu` use 16 ranks on
this host. The longer rail-start progress target is
`spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu`. The
non-promoted rail-start enable-phase diagnostic is
`spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu`. The
bounded near-lock companion target is
`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu`; the
non-promoted lower-P gain diagnostic is
`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu`;
the phase-selected high-side near-lock companion is
`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu`. The
non-promoted default-enable high-side diagnostic is
`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu`. The
non-promoted FRAC=5 extracted-DCO gain-scaling diagnostic is
`spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu`.
The boosted-acquisition reproducers are
`digital-loop-gain-sweep-frac6-acqboost-s2a3`,
`pll-top-filled-dco-gain-sweep-frac6-acqboost-s2a3`,
`synth-frac6-acqboost-s2a3`, and
`spice-pll-mapped-loop-frac6-acqboost-s2a3-progress-1us`. The postlayout-RCX
DCO follow-up probe is
`spice-pll-mapped-loop-frac6-acqboost-s2a3-extracted-dco-progress-300ns-probe-mpi16-klu`.

An optional same-direction acquisition boost is now available in the DLF and is
disabled by default. It watches for repeated accepted BBPD decisions in the same
direction and applies `DLF_ACQ_BOOST_SHIFT` to the integral step after
`DLF_ACQ_BOOST_AFTER` repeats; it falls back to the normal KI path when the
decision stream changes or idles. The first FRAC=6 probe uses
`DLF_ACQ_BOOST_SHIFT=2`, `DLF_ACQ_BOOST_AFTER=3`. It reduces ideal digital-loop
worst-case lock for `DLF_KI=255`, `DLF_KP=32` to 2.870 us, and the filled-DCO
top behavioral row for the same gains passes both rails in 5.598 us worst case.
The boosted Sky130 mapped core has 970 cells and improves the 1 us mapped
behavioral-DCO SPICE endpoints from 0->20 / 255->233 to 0->40 / 255->215. This
is the best current behavioral path toward practical rail-start acquisition,
but the postlayout-RCX DCO follow-up is much weaker: the 300 ns MPI16/KLU probe
ends at 0->10 and 255->245, with only 2.75 low-side and 2.00 high-side
integrator-code movement. The boost remains non-promoted for extracted-DCO
rail-start acquisition.

Two shorter same-direction thresholds were checked as non-promoted diagnostics.
`DLF_ACQ_BOOST_AFTER=1` with `DLF_KI=192`, `DLF_KP=32` passes the filled-DCO
top behavioral sweep, but fails the mapped behavioral-DCO SPICE probe because
the high-start case collapses to the low rail before the measurement window.
`DLF_ACQ_BOOST_AFTER=2` with the same gains passes the mapped behavioral-DCO
probe at 0->18 and 255->236 in 1 us, but its 300 ns postlayout-RCX DCO probe
only reaches 0->12 and 255->245. Digital-only boost tuning is therefore not yet
closing the extracted-DCO rail-start gap.

The legacy mapped behavioral-DCO acquisition candidate uses
`DLF_FRAC_WIDTH=6`, `DLF_PROP_RAIL_GUARD=1`, `DLF_ACQ_RAIL_BOOST=1`,
`DLF_ACQ_FORCE_RAIL_CODE=127`, `DLF_ACQ_BOOST_SHIFT=4`, and
`DLF_ACQ_BOOST_AFTER=2`. The recommended gain point is `DLF_KI=160`,
`DLF_KP=8`, keeping a nonzero proportional path while using deterministic
force-to-mid acquisition from either rail. The reproducible targets are
`digital-loop-gain-sweep-frac6-force127-s4a2`,
`pll-top-filled-dco-gain-sweep-frac6-force127-s4a2`,
`synth-frac6-force127-s4a2`,
`spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-progress-500ns-mpi16-klu`,
and
`spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu`.
The corresponding physical signoff targets are `librelane-signoff-force127-s4a2`
and `check-librelane-signoff-force127-s4a2`; the post-PnR final-netlist
closed-loop motion target is
`spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-motion-220ns-mpi16-klu`,
and the corresponding final-netlist lock-window target is
`spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-lock-820ns-mpi16-klu`.

The filled-DCO top behavioral sweep passes all tested gain points from both
rails; the `KI=160`, `KP=8` row ends at codes 128/127 with 2.010 us worst-case
lock. The registered-control direct Yosys Sky130 mapped core has 1307 cells and
13733.171200 square microns, including 255 registered DCO thermometer outputs.
The force-to-mid LibreLane signoff artifact has 3164 stdcells, 30.0674%
utilization, 2.794 ns worst setup slack, 0.115 ns worst hold slack, 67207
microns routed wire length, 13321 vias, 3.431 mW reported total power, 0.706 mV
worst IR drop, and zero DRC/LVS/STA/power-grid violations.

The old 2 us mapped behavioral-DCO endpoint target is not promoted for the
registered-control RTL. With the binary code observer, mapped bus transition
states can look like low DCO codes; with the thermometer observer, the 2 us
reruns timed out before completing. Current promoted loop validation therefore
uses the extracted-DCO targets below.

The 500 ns force-to-mid extracted-DCO progress target places the filled DCO RCX
macro in that same mapped loop and runs Xyce/KLU with 16 MPI ranks per deck.
Low-start moves from code 0 to 102, and high-start moves from code 255 to 153
after dipping to code 129. Tail-frequency error remains 2.262788 MHz low-start
and 1.791117 MHz high-start over 119..499 ns, so this is strong rail-start
progress evidence rather than extracted-DCO lock.

The 820 ns force-to-mid registered-control extracted-DCO lock-window target
uses the filled DCO RCX macro, filled BBPD RCX macro, thermometer-code
observation, Xyce/KLU with 16 MPI ranks per deck, and two rail-start decks in
parallel. It checks the full 700..819 ns tail window against code bounds
112..144 and a 0.8 MHz frequency-error limit. Low-start passes with code
122..128 and 0.411769 MHz tail error; high-start passes with code 127..133 and
0.257118 MHz tail error. This is the current strongest TT extracted-DCO
rail-start lock-window evidence, though not a full PVT or multi-microsecond
extracted PLL signoff.

The final-signoff-netlist extracted-DCO targets then instantiate the LibreLane
force127 final Verilog netlist in the same loop, skipping 4138 physical-only
filler/decap/tap cells and keeping 2020 functional mapped digital-core cells.
The 220 ns two-rail Xyce/KLU motion run passes with low-start motion 0->22 and
high-start motion 255->222. The stronger 820 ns final-netlist lock-window run
also passes both rails with the same 112..144 tail code bounds and 0.8 MHz
frequency-error limit: low-start ends at code 128 with tail-window code
122..128 and 0.397645 MHz tail error, while high-start ends at code 132 with
tail-window code 126..132 and 0.273624 MHz tail error. This is post-PnR
functional-netlist TT closed-loop lock-window evidence, but not full extracted
PVT or multi-microsecond rail-start signoff.

An optional `DLF_UPDATE_ON_PLLOUT` mode was then added as a diagnostic to remove
one divider-cycle of BBPD-decision-to-integrator latency. The default remains
divider-clocked DLF operation. Because the Sky130 hard top instantiates the
digital core as a placed macro, PLLOUT-clocked DLF operation requires rebuilding
that digital-core macro variant; it is not a runtime knob on the shipped
25 MHz configured wrapper. With FRAC=6 and no boost, the ideal digital-loop
sweep passes with `DLF_KI=255`, `DLF_KP=32` at 10.074 us worst-case lock, while
the filled-DCO top behavioral sweep prefers `DLF_KI=192`, `DLF_KP=8`, ending at
codes 129/124 in 24.795 us. Combining PLLOUT-update mode with
`DLF_ACQ_BOOST_SHIFT=2`, `DLF_ACQ_BOOST_AFTER=2` improves the top behavioral
candidate to `DLF_KI=192`, `DLF_KP=32`, ending at 137/120 in 6.363 us. The
fast+boost mapped Sky130 core synthesizes to 975 cells and 6434.921600 square
microns, but mapped behavioral-DCO SPICE does not justify extracted-DCO
promotion: `KI=192`, `KP=32` ends 0->0 and 255->217 in 1 us, and the lower-gain
`KI=128`, `KP=8` case ends 0->2 and 255->238. The low-start waveform shows
alternating BBPD decisions that pull the proportional output back to the rail,
so this path remains diagnostic rather than a promoted acquisition fix.

The current release promotes the 25 MHz configured RTL/source interface through
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured`; the physical wrapper must be
regenerated after the 5-bit `DLF_KP` interface update before it is signed-off
release evidence. Robust acquisition from arbitrary phase and code remains the
next BBPLL/control architecture extension, not a packaging gap.

FRAC=6 behavioral results are promising. The ideal digital-loop sweep reaches
10.063 us worst-case lock for `DLF_KI=255`, `DLF_KP=32`, and the filled-DCO top
behavioral sweep finds `DLF_KI=192`, `DLF_KP=8` ending at code 129 from both
rails in 24.963 us worst case. The mapped-cell, filled-BBPD RCX, behavioral-DCO
SPICE result is mixed but improved after phase selection: `DLF_KI=255`,
`DLF_KP=32` moves low-start from code 0 to 20 in 1 us, and high-start at initial
DCO phase 0.5 moves from code 255 to 233 with response code 224.000870. A 500 ns
high-start phase sweep ends near code 243 at phases 0 and 0.25, code 241 at
phase 0.5, and code 255 at phase 0.75 after a transient excursion to code
134.001867. This should guide the next gain/phase sweep, but it is not promoted
as final validation evidence yet.

The FRAC=6 extracted-DCO trend now confirms that the stronger integral scaling
is visible in the coupled RCX deck: low-start ends at code 9 with integrator
movement from 0.00 to 1.75, and high-start ends at code 246 with integrator
movement from 255.00 to 254.00. The MPI16 repeats match those endpoints and are
audited as elapsed-time improvements. The 500 ns MPI16 rail-start progress row
extends that to code 15 from low-start and code 240 from high-start, with
integrators 7.75 and 248.00; it is still more than 3 MHz from target. The MPI16
mid-code lock-window row adds near-target evidence by holding code 127..140 and
measuring 49.676823500 MHz against the 49.762117808 MHz target from 139..219 ns.
The lower-P `KI=192`, `KP=8` extracted diagnostic reduces visible code overshoot
to code 131 but misses the tighter tail-frequency target, so KP32 remains the
promoted near-lock setting. It still does not show rail-start closed-loop
acquisition. The enable-85 high-side companion starts at code 160 and moves down
to code 146 with 0.239153 MHz tail error from 299..379 ns, while the
default-enable probe from the same code moves upward to 169 and measures
50.602594662 MHz in the tail window. This is useful two-sided near-lock
evidence, but it remains BBPD release-phase selected.

FRAC=5 and FRAC=4 were also probed as stronger integral-scaling candidates. The
new diagnostic targets are `digital-loop-gain-sweep-frac5`,
`pll-top-filled-dco-gain-sweep-frac5`,
`spice-pll-mapped-loop-frac5-progress-1us`,
`spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu`,
`digital-loop-gain-sweep-frac4`, `pll-top-filled-dco-gain-sweep-frac4`, and
`spice-pll-mapped-loop-frac4-progress-500ns`. The behavioral top model likes
some of these rows, but mapped SPICE does not promote them: FRAC=4
`DLF_KI=192`, `DLF_KP=32` snaps high-start back to code 255 in 500 ns, while
FRAC=5 `DLF_KI=192`, `DLF_KP=32` ends the 1 us mapped run at code 5 from
low-start and code 239 from high-start. FRAC=6 therefore remains the best
mapped behavioral-DCO candidate so far.

The FRAC=5 extracted-DCO probe passes the motion check with the postlayout-RCX
DCO and two concurrent MPI16/KLU Xyce jobs, but it is not stronger than the
promoted FRAC=6 extracted evidence. Over the 129..299 ns window, low-start moves
code 0 to 8 with a 46.190967911 MHz tail, and high-start moves code 255 to 244
with a 53.231394237 MHz tail. Both remain more than 3.4 MHz from the
49.762117808 MHz target, so this is useful negative gain-tuning evidence rather
than acquisition or lock. The rows took 1080.527 s and 840.300 s elapsed, and
the logs include Xyce timing summaries for 16 processors.

Run a heavier exhaustive typical-corner oscillator transient sweep when needed:

```sh
make -C OpenPLL spice-dco-all
```

This target now validates all 256 top-level `DCO_CODE` values at TT. The latest
passing run measured a monotonic 99.784 MHz to 132.850 MHz span with strictly
positive adjacent-code frequency steps.

Run the exhaustive all-code PVT oscillator transient sweep:

```sh
make -C OpenPLL spice-dco-pvt-all
```

This validates all 256 top-level `DCO_CODE` values across `tt`, `ff`, `ss`,
`sf`, and `fs`. The latest passing run measured a monotonic 66.324 MHz to
187.555 MHz total span across 1280 code/corner transient cases.

Run only the synthesized decoder SPICE check:

```sh
make -C OpenPLL spice-dco-decoder
```

Run sampled-tap synthesized decoder SPICE for every 8-bit code:

```sh
make -C OpenPLL spice-dco-decoder-all
```

Run full-tap synthesized decoder SPICE at low-end, midpoint, and high-end code
boundaries:

```sh
make -C OpenPLL spice-dco-decoder-full-taps
```

Run all-code, all-tap synthesized decoder SPICE:

```sh
make -C OpenPLL spice-dco-decoder-all-taps
```

The DLF uses an active-low async reset only for constant reset-to-zero. Loading
an external initial control word is done synchronously through `DLF_Clear`;
this avoids non-constant async reset behavior that does not map cleanly to
Sky130 standard-cell flip-flops.

## LibreLane Direction

`openlane/IntegerPLL_DigitalCore/config.tcl` is retained as the original
OpenLane-style starter. The active physical-flow configuration is
`openlane/IntegerPLL_DigitalCore/config.json`, which runs with LibreLane v3.0.4
from `$LIBRELANE_ROOT`.

The PnR SDC intentionally treats slow SPI/config-style inputs and DCO macro
control outputs as false paths. The synchronous timing target is the 8 ns
`PLLOUT` domain plus the BBPD and feedback-divider interface. This is the right
constraint shape for a PLL control block, because the 255 DCO thermometer
outputs drive analog/macro controls rather than conventional one-cycle
registered outputs.

Do not send the full `IntegerPLL_Top` through ordinary digital synthesis until
the BBPD and DCO have been hardened as physical macros. A ring oscillator and
bang-bang detector delay/reset path are intentionally timing-sensitive and can
be broken by optimization.

The digital core includes a small `PLLOUT`-domain BBPD event-capture latch
before the DLF. It captures the first non-idle BBPD polarity in an update
interval and holds that decision across the next DLF update. The capture state
is cleared while `DLF_En=0` or `DLF_Clear=1`, and the top-level BBPD reset is
held over the same inactive window. This prevents stale pre-enable BBPD state
from becoming the first active DLF command and prevents a captured UP or DN
pulse from being overwritten into `2'b11` during BBPD reset overlap. The event
toggles are gated by a consumed marker, so one long BBPD pulse contributes at
most one captured event before the `PLLOUT` domain acknowledges it.

## Macro Work Still Required

The Sky130 DCO in `sky130/IntegerPLL_DCO_sky130.v` is a first structural
standard-cell ring with an 8-bit decoded NAND load bank. It still needs:

- Coarse-DCO PLL promotion. `IntegerPLL_DCO_EINVP_COARSE` is now the current
  high-frequency macro path, with HD NAND2 fine loads in source. Standalone DCO
  signoff/RCX, post-layout TT endpoint probes for 100, 250, 300, 400, and
  500 MHz from a 25 MHz reference, and hard-top/configured-wrapper signoff
  artifacts must be regenerated after the all-HD DCO and 5-bit `DLF_KP` interface
  updates. The path still needs broader PVT range coverage and full
  extracted-DCO-in-loop lock/acquisition evidence before it can be treated as
  final PLL signoff.

- Full transistor-level or post-layout closed-loop lock and acquisition
  validation. Current loop-level evidence includes behavioral DCO targets
  fitted to no-fill and filled DCO RCX measurements, DLF update evidence from
  the final digital-core signoff netlist cone with nominal SPEF distributed RC,
  plus a short mapped-core filled-BBPD loop smoke, a final-signoff functional
  mapped-loop smoke, a mapped-loop proportional-gain sweep, a four-phase
  first-correction sweep, hard-top distributed-RC startup diagnostics with
  behavioral and extracted DCO decks, hard-top distributed-RC extracted-DCO
  low/high first-motion diagnostics for both the NAND and EINVP hard-top paths,
  an MPI4-KLU 1 us mapped-loop progress probe, the FRAC=6 force-to-mid 500 ns
  extracted-DCO progress probe, the FRAC=6
  force-to-mid 820 ns registered-control extracted-DCO lock-window probe,
  serial and MPI4-KLU
  extracted-DCO startup smokes, FF/SS low/high rail EINVP extracted-DCO PVT
  lock-window diagnostics, and serial and MPI4-KLU both-rail extracted-DCO
  first-correction smokes, plus low/high MPI4-KLU extracted-DCO integrator trend
  probes, MPI16-KLU FRAC=6 trend repeats, a 500 ns MPI16-KLU FRAC=6 rail-start
  progress check, and MPI16-KLU FRAC=6 force-to-mid, mid-code, and enable-85
  high-side lock-window checks, plus force-to-mid final-signoff-netlist 220 ns
  motion and 820 ns lock-window extracted-DCO checks, but not full extracted
  PVT signoff or multi-microsecond rail-start lock.
- Full filled signoff DCO RCX 256-code tuning-curve and PVT transient coverage.
  Current passing filled evidence is a TT five-point smoke run in Xyce, a
  consolidated five-point calibration artifact, a TT local-gain artifact around
  code 128, and FF/FS/SF/SS endpoint smoke.
- Placement constraints or manual layout to preserve symmetry and loading.
- Top-level extracted closed-loop transient using regenerated hard-macro SPICE
  and SPEF views. The previous top-level hard-macro physical signoff covered GDS
  streamout, DRC, XOR, RCX/SPEF, extracted SPICE, LVS, macro-interface
  connectivity through the extracted wrapper, and an Xyce `-norun`
  syntax/topology probe, but those artifacts must be refreshed after the current
  5-bit `DLF_KP` interface update. Historical force-to-mid mapped-loop and
  distributed-RC diagnostics remain useful methodology evidence, including
  hard-top-loaded extracted-DCO startup, first-motion, lock-window, rail-progress,
  PVT, and calibrated behavioral-DCO rows, but they are not current physical
  release evidence until regenerated.

The Sky130 BBPD in `sky130/IntegerPLL_BBPD_sky130.v` follows the two-flop
set/reset concept from the report and uses buffer delay chains for the reset
race. It now has filled-layout DRC/LVS/RCX evidence and post-layout transient
polarity validation across the standard Sky130 corners, plus TT small-offset
dead-zone characterization and all-corner sampled small-offset sweeps. It still
needs reset-delay optimization and denser metastability characterization around
the measured transition windows before tapeout use.
