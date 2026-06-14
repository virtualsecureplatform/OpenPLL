# Sky130 SPICE Validation

This file records the current transistor-level SPICE validation status for the
OpenPLL Sky130 DCO, BBPD, and synthesized digital-control candidates.

## Validated Circuit

The DCO validation script generates Sky130 standard-cell SPICE netlists for
8-bit DCO macro candidates:

- Ring core: one `sky130_fd_sc_hd__nand2_1` enable gate plus 16
  `sky130_fd_sc_hd__inv_1` delay stages by default. The `--ring-stages`
  option also supports shorter odd-stage rings such as the 9-stage fast-DCO
  range probe.
- Tuning network: 255 dummy-load cells distributed across the ring nodes. The
  original baseline uses `sky130_fd_sc_hd__nand2_1`; load-style probes also
  support `einvp`, `einvn`, and `dlclkp` cells.
- Coarse mirror mode: `--topology mirror-coarse` can use HS cells, a
  48-position NAND/NAND2B mirror path, and sparse evenly mapped NAND2
  varactor banks. The current physical coarse DCO uses 90 local fine loads and
  no deep-node slow-load bank.
- Control: 8-bit binary `DCO_CODE` decoded to a 255-line thermometer bus.
- PDK model: `sky130A`; HD is the default DCO sweep library and HS is selected
  explicitly for the coarse mirror target probe. The representative sweep uses
  `tt`, and the endpoint PVT sweep uses `tt`, `ff`, `ss`, `sf`, and `fs`.
- Supply: 1.8 V.

The physical load polarity is load-based: a high thermometer bit enables dummy
output switching and increases oscillator load. The RTL top-level default uses
`DCO_THERM_INVERT=1`, so increasing `DCO_CODE` disables more load cells and
raises the free-running oscillator frequency. This matches the loop filter
convention that `BBPD=2'b10` requests an increase in output frequency.

The BBPD validation script generates a Sky130 standard-cell SPICE netlist for
the two-flop detector:

- Set flops: two `sky130_fd_sc_hd__dfrtp_1` cells.
- Reset path: delayed `UP` and `DN` through `sky130_fd_sc_hd__buf_1` chains,
  then common reset from `UP & DN`.
- Output convention: `UP` is `BBPD[1]`, `DN` is `BBPD[0]`.

The DCO decoder validation script reads the synthesized Sky130 digital-core
Verilog netlist, extracts the backward cone from selected `DCO_THERM` taps to
the 8-bit `DCO_CODE` input, and emits a Sky130 standard-cell SPICE operating
point deck with cell pins ordered from the real `.subckt` definitions.

The signed-off digital core also has a Magic-extracted SPICE view under:

```text
OpenPLL/openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/spice/IntegerPLL_DigitalCore.spice
```

That extracted view is currently used as LVS evidence together with Netgen. It
is not a post-layout transient SPICE simulation of the oscillator, bang-bang
detector, or closed PLL loop.

The DCO and BBPD now also have filled, signoff-clean physical macros with GDS,
SPEF, Magic/KLayout DRC, Netgen LVS, and Magic RCX transistor-level decks. A
reduced no-fill DCO RCX deck is used for fast post-layout oscillator smoke
simulation; the no-fill deck is not signoff-clean and is explicitly separated
from the filled layout evidence. The BBPD post-layout transient uses the filled
signoff-clean RCX deck directly.

## Current Validation Boundary

The current high-frequency physical path is `IntegerPLL_HardMacroTop_EINVP`,
using the signed-off Sky130 digital core, filled BBPD RCX, physical
`IntegerPLL_DCO_EINVP_COARSE` RCX, and hard-top SPEF where each diagnostic
requires it. The DCO uses a single HS NAND/NAND2B mirror-delay loop with a
separate 6-bit coarse band input and an 8-bit fine code. The ring-facing output
buffer remains `sky130_fd_sc_hs__buf_1` to avoid adding unnecessary
oscillator-node capacitance.

The older filled `IntegerPLL_DCO_EINVP` path measured 50.955942-72.479371 MHz
across the 8-bit code endpoints and remains useful low-frequency diagnostic
history. It is not the current 100/250/300/400 MHz target path.

The historical 200 MHz sparse72 exploration shortened the EINVP ring and
reduced the enabled load range. The `IntegerPLL_DCO_EINVP_SPARSE72` macro has
Ciel-PDK LibreLane signoff, Magic RCX, and a bounded extracted-DCO transient
probe around the 200 MHz target:
194.469 MHz at fine code 184, 195.968 MHz at code 190, 196.676 MHz at code
191, and 202.264 MHz at code 192. This is post-layout DCO range evidence; the
nearest measured fine codes bracket the 200 MHz target.

`IntegerPLL_DCO_EINVP_COARSE` is the new physical coarse-DCO candidate. It uses
one HS NAND-gated oscillator loop, a 48-position HS NAND/NAND2B turn/pass
mirror-delay network, and 90 local HS NAND2 fine loads split between
`osc_node` and `mirror_ret[0]`. The active ring/mirror gates use HS `_4`
cells, while the first output buffer stays
`buf_1` to avoid adding unnecessary capacitance at the oscillator node. The
earlier C19/C20 deep-node slow-load banks were removed after extracted
simulation showed they made the target bands fragile. The coarse path changes
effective loop length inside one macro rather than selecting among parallel
oscillators, selecting a muxed feedback tap, or using a NOT-chain ring.

The optional pre-layout TT topology diagnostic is:

```sh
make -C OpenPLL check-dco-einvp-coarse-mirror-targets
```

It keeps the output buffer drive at 1 and currently checks sampled 100 and
300 MHz pre-layout brackets with buffered-`PLLOUT` duty/rise/fall quality. It is
not the shipping all-target range claim. The physical DCO macro has clean
LibreLane signoff and Magic RCX, plus post-layout TT Xyce endpoint and local
target-code probes:

| Target | Multiplier | Coarse/fine setting | Post-layout TT evidence |
| ---: | ---: | --- | --- |
| 100 MHz | 4 | C20/code93 | Interpolated from 98.609 MHz at code0 to 100.515 MHz at code128. |
| 250 MHz | 10 | C06/code234 | 249.813 MHz measured directly; C06/code255 is numerically closer than code224 but has weaker duty, so the rail is avoided. |
| 300 MHz | 12 | C04/code90 | Interpolated from 295.760 MHz at code64 to 301.054 MHz at code96. |
| 400 MHz | 16 | C02/code76 | Interpolated from 397.373 MHz at code64 to 404.357 MHz at code96. |

The target-band context remains: C20 spans 98.609/100.515/101.817 MHz at fine
0/128/255, C06 measures 243.384/249.187/249.756/249.813/250.488 MHz at codes
128/192/224/234/255, C04 measures 295.760/301.054/304.371/308.390 MHz at codes
64/96/128/160, and C02 spans
385.207/390.628/397.373/404.357/411.194/425.984/438.705 MHz at codes
0/32/64/96/128/192/255. Full PLL acquisition checks remain required before
using this coarse-DCO path for PLL signoff claims.
If the oscillator needs more speed margin, the validated direction is to change
ring/mirror drive strength, effective coarse path length, or fine-load topology.
Upsizing the ring-facing output buffer is avoided because it increases the load
the oscillator must drive.

The paired configured-mode mixed-signal check is:

```sh
make -C OpenPLL xyce-pll-mixed-signal-25mhz-targets
```

It aliases to the direct extracted-DCO mixed-step hold smoke after refreshing
the post-layout RCX, waveform-qualified DCO tables above. The selected target
codes are code93, code234, code90, and code76. The calibrated configured
tracking row uses `KI=16`, `KP=4`, starts each target at +/-4 fine codes, and
passes the bounded configured tracking gate for all four multipliers. The gate
requires a target-code-neighborhood hit, at least one BBPD decision in the
expected initial direction, final modeled frequency error within 2 MHz, and the
last eight modeled DCO updates also inside the 2 MHz frequency window with no
more than 16 fine-code span. Its intended scope remains configured-mode
integration around measured target settings, not rail-to-rail frequency
acquisition or a full extracted-DCO-in-loop PLL lock signoff.
Short BBPD motion checks are also phase dependent; they are useful only when
the initial divider phase is explicitly controlled and are not promoted as
frequency-acquisition evidence for the 100/250/300/400 MHz coarse-DCO target
set.

The fast artifact gate for this current 25 MHz-reference release evidence is:

```sh
make -C OpenPLL check-sky130-pll-25mhz-release
```

It validates the coarse-DCO RTL topology and `buf_1` output-buffer constraint,
the 25 MHz RTL divider preset table and configured divider-controller/wrapper, the
refreshed `IntegerPLL_HardMacroTop_EINVP` signoff and extracted SPICE/SPEF
interface summaries, the configured behavioral PLL reset-to-tracking regression,
the waveform-qualified target-code rows, the configured tracking rows, the four
direct-RCX hold rows, and the recorded low/high near-seed direct-RCX update
summary for all four divider targets.

The optional direct extracted-DCO mixed-step diagnostic for the highest target
mode is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-400m-hold-smoke
```

This deck keeps the `IntegerPLL_DCO_EINVP_COARSE` RCX and filled BBPD RCX in
Xyce, with the divider and DLF model in the C-interface driver. The current
Ciel-PDK run fixes C02/code76 and uses `NDIV=16`. Because that short
ADC-sampled window is approximate, the standalone post-layout DCO target rows
remain the precise frequency evidence.

The companion direct-RCX near-seed diagnostic is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
```

It checks +/-4 fine-code starts for 100, 250, 300, and 400 MHz with `KI=16`,
`KP=4`, and `FRAC=2`. Low-side rows use REF phase offset -0.25 and divider seed
0; high-side rows use REF phase offset 0.25 and divider seed `NDIV-1`. The
current Ciel-PDK TT summary passes all eight rows with two expected BBPD
decisions and final error of one code: 100 MHz 89->92 and 97->94 around code93,
250 MHz 230->233 and 238->235 around code234, 300 MHz 86->89 and 94->91 around
code90, and 400 MHz 72->75 and 80->77 around code76. This confirms extracted
DCO/BBPD code-update behavior on both sides of each configured target, but it
is still near-seed configured-control evidence rather than full extracted-loop
rail-start acquisition evidence.

The practical 25 MHz reference / 200 MHz output mixed-signal lock target is:

```sh
make -C OpenPLL xyce-pll-postlayout-calibrated-dco-mixed-fast200-sparse72-lock
```

It keeps the filled BBPD RCX transistor deck in Xyce and uses a behavioral DCO
phase model calibrated from the sparse72 post-layout RCX frequency points. The
current run passes from both rails within the configured 4 MHz target window:
code 0 moves to 192 with measured `PLLOUT` at 202.314 MHz, and code 255 moves
to 191 with measured `PLLOUT` at 196.767 MHz. A separate full extracted-DCO
mixed-step smoke, using the actual sparse72 RCX DCO deck, covers fixed-code
near-target frequency and both near-target BBPD/DLF correction directions with
post-decision DCO-code updates applied through Xyce's mixed-step API:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion
```

The fixed-code row starts and stays at code 196 and measures `PLLOUT` at
199.734 MHz. The low-side row starts at code 184 with divider count 0 and
`KI=32`, `KP=4`; it records six UP-dominant windows, moves 184 -> 187 -> 189
-> 191 -> 193 -> 195 -> 197, and measures `PLLOUT` at 200.000 MHz. The
high-side row starts at code 220 with divider count 7 and `KI=96`, `KP=8`; it records four
DN-dominant windows, moves 220 -> 212 -> 206 -> 200 -> 194, and measures
`PLLOUT` at 200.000 MHz. These rows use the 19303-unknown direct RCX Xyce deck with the
filled BBPD and extracted sparse72 DCO, a 5 ns reset release, a 25 MHz pulse
REF source, and `NDIV=8`. This is direct-RCX near-lock evidence with real
post-decision control updates; a complete rail-to-rail lock simulation with the
full extracted DCO in every loop cycle remains too slow for routine regression
in the current serial driver.

The full-RCX C-interface driver now advances the feedback divider during
warmup by default and also accepts `--initial-divider-count` for explicit
phase-selected BBPD checks. It is not currently accelerated by launching the
compiled executable with `mpirun`: a two-rank YADC/YDAC smoke test reached Xyce
completion and printed a two-processor timing summary, but the two driver ranks
did not exit cleanly and had to be terminated. Treat C-interface MPI as
unqualified until the driver is made MPI-rank-aware.

The fast-path loop checks keep the fine DCO word at the full 8-bit resolution
and model `COARSEBINARY_CODE` as an independent band offset. The current
126.88745 MHz target uses `COARSEBINARY_CODE=1`, `DCO_COARSE_STEP_MHZ=16`,
`MMDCLKDIV_RATIO=2`, and `REF=63.443725 MHz`; this is behavioral/mixed-signal
range exploration, not post-layout DCO signoff.
`make -C OpenPLL spice-pll-mapped-loop-fast100-coarse4-motion` runs the mapped
digital core with filled BBPD RCX and a behavioral five-point DCO table in Xyce
MPI/KLU. The current 220 ns check passes the motion criterion with low-start
code 0 moving to 62 and high-start code 255 moving to 183. It is two-sided
direction evidence for the 100 MHz-order multiplier setup, not a lock-window
or settled-frequency signoff.

`make -C OpenPLL xyce-pll-mixed-signal-fast100-coarse4-smoke` adds a bounded
Xyce C-interface mixed-signal check for the same independent-coarse fast band.
The filled BBPD RCX remains in Xyce and the compiled driver uses the
102.518/119.260/142.355/176.267/229.054 MHz DCO table plus
`COARSEBINARY_CODE=1` at 16 MHz/step. The low case moves code 0 to 36 in 24
cycles; the bounded high-side case moves code 64 to 38 in 15 cycles. Both pass
with 4-code closest error to the target code 32. This target deliberately does
not claim full 255-to-32 rail-start lock because the current C-interface driver
uses a simplified one-feedback-edge-per-cycle phase model.

`make -C OpenPLL xyce-pll-analog-dco-mixed-fast100-coarse4-acq` is the stricter
fast-band C-interface check. Xyce owns the filled BBPD RCX, analog behavioral
DCO phase integrator, reference source, and divided feedback source; the C++
driver only reads `UP`/`DN` YADCs and drives the DCO code YDAC from a fixed-point
DLF model. With `COARSEBINARY_CODE=1`, 16 MHz coarse-band offset, `REF=63.443725
MHz`, `NDIV=2`, `KI=128`, `KP=8`, and `FRAC=2`, the current short acquisition
passes from both sides around target fine code 32: low start moves 0 to 34 in
four updates and measures 127.389 MHz at `PLLOUT`; bounded high start moves
64 to 30 in four updates and measures 126.316 MHz. Both finish within 2
fine-code LSB of the target and within 0.572 MHz of the 126.88745 MHz output
target. This is better mixed-signal boundary evidence than the older driver-DCO
smoke, but it is still a bounded acquisition check, not full 255-to-32
rail-start settling or physical fast-DCO signoff.

The strongest post-layout convergence evidence is the extracted-DCO lock-window
set, not the short mixed-signal driver smoke. The TT low-rail run reaches codes
122..128 with 58.485654 MHz tail frequency and 0.087865 MHz target error; the
TT high-rail run reaches codes 126..132 with 58.804895 MHz tail frequency and
0.231377 MHz target error. FF/SS low/high rail PVT lock-window rows are also
covered by the promoted artifact checker.

The Xyce C-interface flow is mixed-signal in the app-note sense because Xyce owns
the extracted BBPD analog state and the compiled driver advances the digital
loop through YADC/YDAC bridges. It is deliberately scoped as gain and polarity
evidence: the current `KI=160`, `KP=8`, `FRAC=6` case reaches exact code 128
from the low side in 10 cycles, while the matching `KP=0` case stops at code
126 and never crosses. The high-side rows still overshoot in the short run, so
this mixed path should not be treated as final lock/settling signoff yet.

## Command

For the legacy low-frequency Sky130 PLL validation evidence, run the fast
artifact audit:

```sh
make -C OpenPLL validate-sky130-pll-artifacts
```

That target reads the promoted signoff, SPICE, and RTL summary artifacts and
writes:

```text
OpenPLL/build/sky130_pll_validation/sky130_pll_validation_summary.csv
OpenPLL/build/sky130_pll_validation/sky130_pll_validation_summary.json
```

The heavier target below regenerates the promoted evidence where practical and
then runs the same audit:

```sh
make -C OpenPLL validate-sky130-pll
```

This heavier target now regenerates the Xyce C-interface mixed-signal gain
sweep before running the artifact audit, so the mixed gain CSVs required by the
checker are reproducible from the promoted flow.

Known diagnostic targets that do not pass from both rails are intentionally
excluded from this promoted gate.

## Xyce Mixed-Signal Status

The current mapped-loop and hard-top extracted PLL runs are not Xyce
mixed-signal co-simulations. They are all-SPICE transient decks: the digital
core is emitted as mapped Sky130 standard-cell SPICE instances, the decks include
`sky130_fd_sc_hd.spice`, and Xyce solves the digital gates, BBPD, DCO, and
selected hard-top SPEF RC continuously as analog circuit unknowns. This is why
the extracted closed-loop runs are slow even when using the MPI/KLU Xyce
binary.

The Xyce app-note flow uses `YADC` and `YDAC` bridge devices plus an external
Python or Icarus/VPI driver through `libxycecinterface.so`. In that flow Xyce
keeps the analog circuit state, while the external digital simulator advances
time, reads ADC events, and updates DAC waveforms. A useful OpenPLL version
would keep the BBPD and DCO analog in Xyce, put `YADC` devices on BBPD
`UP`/`DN` and `PLLOUT`, and drive `DCO_THERM[*]` plus `CLKDIV_RETIMED` through
`YDAC` devices from an event-driven RTL or Python digital loop.

The installed Xyce binaries accept `YADC`/`YDAC` device syntax, but the current
`$XYCE_MPI_ROOT` install does not include
`libxycecinterface.so`; its previous CMake cache has `BUILD_SHARED_LIBS=OFF`.
Until a shared Xyce C-interface build is installed, the app-note Python/VPI
mixed-signal loop cannot run here.

There is still a usable compiled co-simulation path: the existing static Xyce
build can build `utils/XyceCInterface/libxycecinterface.a`, and OpenPLL now has
short C++ C-interface smokes for that path. `xyce-cinterface-smoke` proves
`simulateUntil`, `xyce_updateTimeVoltagePairs`, and YADC state retrieval on a
small YDAC/YADC deck. `xyce-bbpd-cinterface-smoke` uses the filled
`IntegerPLL_BBPD` RCX macro at TT, drives REF and feedback through YDACs, reads
UP/DN through YADCs, and verifies both polarities: the REF-leads event produces
a wider UP pulse, while the feedback-leads event produces a wider DN pulse. The
latest passing BBPD C-interface smoke measured 879.587 ps UP versus 652.784 ps
DN in the REF-leads window and 663.737 ps UP versus 852.102 ps DN in the
feedback-leads window.

`xyce-pll-mixed-signal-smoke` extends that bridge into a short closed-loop
mixed-signal PLL smoke. Xyce still owns the filled Sky130 BBPD RCX circuit and
its analog state; a compiled C++ C-interface driver supplies the REF/divider
edges through YDACs, reads BBPD UP/DN pulse widths through YADCs, and updates a
behavioral fixed-point DLF plus a behavioral DCO frequency table calibrated from
the filled `IntegerPLL_DCO_EINVP` RCX TT code points. This is a true Xyce
C-interface mixed-signal run, but it is not yet a full post-layout PLL run
because the DLF/divider/DCO are outside Xyce. With `KI=255`, `KP=8`,
`FRAC=6`, `boost_shift=4`, and `boost_after=1`, the latest smoke passes from
both sides of the target: code 96 moves upward to 143 with a minimum target
error of 1 code, and code 160 moves downward to 78 with a minimum target error
of 2 codes. The overshoot is intentional for this short smoke; the useful
evidence is BBPD polarity, closed feedback, and gain-induced motion through the
target region.

`xyce-pll-mixed-signal-gain-sweep` records a focused gain comparison using the
same filled BBPD RCX mixed setup, but with the current lower-gain acquisition
candidate `KI=160`, `FRAC=6`, `boost_shift=4`, and `boost_after=2`. The default
grid compares `KP=0` against `KP=8` from code 96 and code 160 for 10 reference
cycles. The latest run writes
`build/xyce_pll_mixed_signal_gain_sweep/mixed_signal_gain_summary.csv` and
`mixed_signal_gain_cycles.csv`, with the generated deck and per-case Xyce logs
kept in the same build directory. All four rows pass the mixed-driver motion
check, but the rows are more useful as gain evidence than as final lock
evidence: `KP=0` low-start ends at code 126 and never exactly hits or crosses
128, while `KP=8` low-start reaches exact code 128 at cycle 9. Both high-start
rows cross the target and then overshoot to codes 109 (`KP=0`) and 107
(`KP=8`). This supports keeping a nonzero proportional path for acquisition
responsiveness, while showing that the current short mixed run still needs
better damping or a longer lock/settling policy before being promoted as final
gain signoff.

The promoted artifact checker now includes this mixed C-interface evidence as
`xyce_cinterface_mixed_signal_gain_sweep` and a direct
`objective_deliverable_evidence` row for the Sky130 top, 8-bit control,
frequency range, and extracted lock-window evidence. In the v1 artifact set,
the full artifact audit passed 69 checks. Longer diagnostic probes were also
tried but are not promoted: `KI=160`, `KP=8`, `boost_shift=4`, `boost_after=2` crosses
the target but drifts to codes 156/90 after 20 cycles, and `KI=192`, `KP=8`,
`boost_shift=3`, `boost_after=2` improves the low-start 20-cycle result to code
132 but keeps walking low from the high side. This reinforces that the
C-interface loop is useful for fast polarity/gain evidence, while final
settling claims should stay with the extracted-DCO lock-window SPICE artifacts
for now.

The mixed-signal driver is also parameterized for non-promoted fast-band
experiments: it accepts five DCO calibration points, `--coarse-code`,
`--dco-coarse-step-mhz`, and `--phase-wrap-cycles`. The default arguments keep
the promoted filled-EINVP DCO table. The fast100 coarse4 target passes only the
bounded 0->36 and 64->38 smoke cases described above; full rail-start fast-DCO
settling still belongs in the mapped-loop or future event-driven mixed-signal
flow.

The stricter analog-DCO fast100 target uses
`scripts/xyce_pll_analog_dco_cinterface_deck.py` and
`tools/xyce_cinterface_smoke/xyce_pll_analog_dco_mixed_signal_smoke.cpp`.
That path leaves the DCO phase and divider waveforms in Xyce rather than in the
compiled driver, and uses a quarter-cycle startup phase offset with no transient
`uic` so the extracted BBPD sees clean first post-reset clock edges. The driver
also reads the `PLLOUT` YADC after acquisition and checks the measured output
frequency against `REF * NDIV`, so this target verifies the intended multiply
frequency directly rather than relying only on final fine-code proximity.

Run the status probe:

```sh
make -C OpenPLL xyce-mixed-signal-status
```

After installing a shared Xyce C-interface library, the strict readiness target
should pass:

```sh
make -C OpenPLL check-xyce-mixed-signal
```

Run the compiled C-interface smokes:

```sh
make -C OpenPLL xyce-cinterface-smoke
make -C OpenPLL xyce-bbpd-cinterface-smoke
make -C OpenPLL xyce-pll-mixed-signal-smoke
make -C OpenPLL xyce-pll-mixed-signal-gain-sweep
make -C OpenPLL xyce-pll-analog-dco-mixed-fast100-coarse4-acq
python3 OpenPLL/scripts/check_sky130_pll_validation.py
```

```sh
make -C OpenPLL spice
```

This runs the representative DCO sweep and the BBPD transient checks:

```sh
OpenPLL/scripts/spice_dco_sweep.sh
OpenPLL/scripts/spice_bbpd_check.sh
OpenPLL/scripts/spice_dco_decoder_check.sh
```

The scripts write generated netlists, simulator logs, waveform files where
needed, and CSV output under:

```text
OpenPLL/build/spice/
```

The DCO sweep CSV records both top-level `DCO_CODE` and the actual enabled
load-cell count. The script exits nonzero if measured frequency is not
monotonic in the expected direction for the selected decoder polarity.

Useful narrower targets:

```sh
make -C OpenPLL validate-sky130-pll-artifacts
make -C OpenPLL validate-sky130-pll
make -C OpenPLL spice-dco
make -C OpenPLL spice-dco-all
make -C OpenPLL check-dco-all
make -C OpenPLL spice-bbpd
make -C OpenPLL spice-dco-pvt
make -C OpenPLL spice-dco-pvt-all
make -C OpenPLL check-dco-pvt-all
make -C OpenPLL spice-dco-decoder
make -C OpenPLL spice-dco-decoder-all
make -C OpenPLL spice-dco-decoder-full-taps
make -C OpenPLL spice-dco-decoder-all-taps
make -C OpenPLL dco-librelane-signoff
make -C OpenPLL dco-magic-rcx
make -C OpenPLL dco-librelane-nofill
make -C OpenPLL dco-magic-rcx-nofill
make -C OpenPLL spice-dco-postlayout
make -C OpenPLL spice-dco-postlayout-filled
make -C OpenPLL check-dco-postlayout-filled
make -C OpenPLL check-dco-postlayout-filled-local-gain
make -C OpenPLL check-dco-postlayout-filled-pvt-endpoints
make -C OpenPLL spice-dco-postlayout-filled-ngspice
make -C OpenPLL bbpd-librelane-signoff
make -C OpenPLL bbpd-magic-rcx
make -C OpenPLL spice-bbpd-postlayout
make -C OpenPLL spice-bbpd-postlayout-pvt
make -C OpenPLL spice-bbpd-postlayout-deadzone
make -C OpenPLL spice-bbpd-postlayout-deadzone-pvt
make -C OpenPLL spice-pll-loop
make -C OpenPLL spice-pll-loop-filled-dco
make -C OpenPLL spice-pll-loop-filled-bbpd-xyce-sweep
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-aperture-sweep
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-lock
make -C OpenPLL spice-pll-loop-pvt
make -C OpenPLL spice-dlf-static
make -C OpenPLL spice-dlf-static-kp16
make -C OpenPLL spice-dlf-static-kp32
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
make -C OpenPLL spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu
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
make -C OpenPLL pll-top-model-acq
make -C OpenPLL pll-top-filled-dco-acq
make -C OpenPLL pll-top-filled-dco-gain-sweep
make -C OpenPLL digital-loop-gain-sweep
```

## DCO Typical-Corner Results

Measured in the recorded validation environment with the installed Volare Sky130A PDK:

| DCO code | Enabled loads | Frequency | Period |
| ---: | ---: | ---: | ---: |
| 0 | 255 | 99.836 MHz | 10.016 ns |
| 64 | 191 | 106.626 MHz | 9.379 ns |
| 128 | 127 | 114.338 MHz | 8.746 ns |
| 192 | 63 | 123.135 MHz | 8.121 ns |
| 255 | 0 | 133.013 MHz | 7.518 ns |

The representative sweep validates a monotonic typical-corner frequency span of
approximately 99.836 MHz to 133.013 MHz.

The exhaustive typical-corner command is:

```sh
make -C OpenPLL spice-dco-all
make -C OpenPLL check-dco-all
```

That target now runs a 256-code TT oscillator transient sweep. The recorded CSV
has 257 rows: one header plus one passing row for every 8-bit `DCO_CODE` value.
The measured all-code span is 99.784 MHz to 132.850 MHz. Adjacent-code
frequency increments are strictly positive, with a measured minimum step of
0.0983 MHz and maximum step of 0.186 MHz.

The checker writes a consolidated artifact under
`build/spice_dco_all_check/dco_sweep_summary.csv` and
`build/spice_dco_all_check/dco_sweep_summary.json`.

The reported period is the averaged one-cycle oscillator period from a two-cycle
transient measurement window.

## DCO Endpoint PVT Results

The compact endpoint sweep uses:

```sh
make -C OpenPLL spice-dco-pvt
```

Measured endpoint results:

| Corner | DCO code | Enabled loads | Frequency | Period |
| --- | ---: | ---: | ---: | ---: |
| `tt` | 0 | 255 | 99.836 MHz | 10.016 ns |
| `tt` | 255 | 0 | 133.013 MHz | 7.518 ns |
| `ff` | 0 | 255 | 138.117 MHz | 7.240 ns |
| `ff` | 255 | 0 | 187.985 MHz | 5.320 ns |
| `ss` | 0 | 255 | 66.343 MHz | 15.073 ns |
| `ss` | 255 | 0 | 86.952 MHz | 11.501 ns |
| `sf` | 0 | 255 | 83.423 MHz | 11.987 ns |
| `sf` | 255 | 0 | 111.951 MHz | 8.932 ns |
| `fs` | 0 | 255 | 105.110 MHz | 9.514 ns |
| `fs` | 255 | 0 | 141.153 MHz | 7.085 ns |

This validates endpoint oscillation across a measured span of approximately
66.343 MHz to 187.985 MHz for the tested corners and codes.

The exhaustive all-code PVT command is:

```sh
make -C OpenPLL spice-dco-pvt-all
make -C OpenPLL check-dco-pvt-all
```

That target validates all 256 `DCO_CODE` values across `tt`, `ff`, `ss`, `sf`,
and `fs`, for 1280 oscillator transient runs total. The recorded CSV has 1281
rows: one header plus one passing row for every code/corner pair. The sweep is
strictly monotonic in every corner.

The checker writes consolidated PVT artifacts under
`build/spice_dco_pvt_all_check/dco_sweep_summary.csv` and
`build/spice_dco_pvt_all_check/dco_sweep_summary.json`.

Measured all-code PVT spans:

| Corner | Min frequency | Max frequency | Min adjacent step | Max adjacent step |
| --- | ---: | ---: | ---: | ---: |
| `tt` | 99.784 MHz | 132.850 MHz | 0.098 MHz | 0.186 MHz |
| `ff` | 137.984 MHz | 187.555 MHz | 0.144 MHz | 0.265 MHz |
| `ss` | 66.324 MHz | 86.904 MHz | 0.062 MHz | 0.120 MHz |
| `sf` | 83.412 MHz | 111.872 MHz | 0.085 MHz | 0.153 MHz |
| `fs` | 105.030 MHz | 140.940 MHz | 0.105 MHz | 0.230 MHz |

## DCO Post-Layout RCX Smoke Results

The filled DCO layout has zero final DRC/LVS violations and a Magic RCX deck at:

```text
OpenPLL/openlane/IntegerPLL_DCO/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO.rcx.spice
```

That deck is the real filled post-layout extraction. Transient ngspice runs on
it are expensive because the deck includes filler/decap devices, so the
practical filled smoke target now uses the installed Xyce simulator. The DCO
post-layout runner records simulator type, timeout status, log path, and Xyce
waveform path in its CSV. Xyce results are accepted only when the printed
`PLLOUT` waveform has enough real rising threshold crossings.

In the recorded validation environment, `Xyce -capabilities` reports `Serial`. The current Xyce
binary can run independent decks in parallel through script-level `--jobs` or
recursive `make -j`, but wrapping this binary with `mpirun` would launch serial
processes rather than split one large filled-RCX transient solve across MPI
ranks. The Xyce-enabled runners accept wrapper commands, so the probed
MPI-enabled Xyce install at `$XYCE_MPI_ROOT/bin/Xyce`, whose
capability output starts with `Parallel with MPI`, can be selected with
`XYCE=$XYCE_MPI_ROOT/bin/Xyce` and `XYCE_MPI_PROCS=N`; the runners check
`Xyce -capabilities` and refuse to wrap the current serial binary. Deck
convergence still needs to be checked before promoting MPI-run artifacts.

The filled signoff smoke command is:

```sh
make -C OpenPLL spice-dco-postlayout-filled
```

That target runs the five canonical code-point decks concurrently through
`make -j$(DCO_POSTLAYOUT_FILLED_JOBS)`, with `DCO_POSTLAYOUT_FILLED_JOBS ?= 5`.
For a consolidated pass/fail and calibration artifact, run:

```sh
make -C OpenPLL check-dco-postlayout-filled
```

Measured filled signoff RCX transient results:

| Simulator | Case | Transient setup | Result |
| --- | --- | --- | --- |
| Xyce | Code 0, 255 enabled loads | 70.5 ns, 200 ps max step, measure after 10 ns | Pass, 46.257 MHz, 415.621 s |
| Xyce | Code 64, 191 enabled loads | 85 ns, 200 ps max step, measure after 10 ns | Pass, 47.950 MHz, 510.490 s |
| Xyce | Code 128, 127 enabled loads | 75 ns, 200 ps max step, measure after 10 ns | Pass, 49.762 MHz, 378.787 s |
| Xyce | Code 192, 63 enabled loads | 110 ns, 200 ps max step, measure after 10 ns | Pass, 51.618 MHz, 432.347 s |
| Xyce | Code 255, zero enabled loads | 160 ns, 200 ps max step, measure after 10 ns | Pass, 52.350 MHz, 185.710 s |
| Xyce | Code 0, 255 enabled loads | 75 ns, 200 ps max step, measure after 10 ns | Timed out after 420.155 s, but waveform had enough crossings for 46.257 MHz |
| Xyce | Code 0, 255 enabled loads | 160 ns, 200 ps max step, measure after 10 ns | Timed out after 600.173 s, but waveform had enough crossings for 46.257 MHz |
| Xyce | Code 128, 127 enabled loads | 160 ns, 200 ps max step, measure after 10 ns | Timed out after 600.173 s, but waveform had enough crossings for 49.762 MHz |
| Xyce | Code 255, zero enabled loads | 60 ns, 200 ps max step, measure after 10 ns | Failed measurement: not enough real crossings in 60 ns, 84.357 s |

The consolidated calibration check writes
`build/spice_dco_postlayout_filled_calibration/filled_dco_calibration.csv` and
`build/spice_dco_postlayout_filled_calibration/filled_dco_calibration_summary.json`.
For the current five passing points, the filled DCO spans 46.256726 MHz to
52.349831 MHz. The five-point span is 6.093105 MHz, the average step is
0.023895 MHz/LSB, and the measured segment steps are 0.026464, 0.028308,
0.029005, and 0.011609 MHz/LSB over code ranges 0-64, 64-128, 128-192, and
192-255.

The filled local-gain command is:

```sh
make -C OpenPLL check-dco-postlayout-filled-local-gain
```

It runs the filled signoff Magic RCX deck at TT for codes 120, 128, and 136
using the MPI-enabled Xyce binary at `$XYCE_MPI_ROOT/bin/Xyce`
with `DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS ?= 4`. The consolidated check writes
`build/spice_dco_postlayout_filled_local_gain/filled_dco_local_gain.csv` and
`build/spice_dco_postlayout_filled_local_gain/filled_dco_local_gain_summary.json`.

Measured filled signoff RCX local-gain results:

| Simulator | Corner | MPI ranks | Case | Transient setup | Result |
| --- | --- | ---: | --- | --- | --- |
| Xyce | `tt` | 4 | Code 120, 135 enabled loads | 85 ns, 200 ps max step, measure after 20 ns | Pass, 49.558458 MHz |
| Xyce | `tt` | 4 | Code 128, 127 enabled loads | 85 ns, 200 ps max step, measure after 20 ns | Pass, 49.771679 MHz |
| Xyce | `tt` | 4 | Code 136, 119 enabled loads | 85 ns, 200 ps max step, measure after 20 ns | Pass, 49.977051 MHz |

The local span is 0.418594 MHz over 16 LSBs, or 0.026162 MHz/LSB average.
The lower and upper 8-LSB segment gains are 0.026653 MHz/LSB and
0.025672 MHz/LSB. This is the promoted post-layout gain number to use for
first-pass DLF gain tuning around the nominal lock code; it is not a substitute
for a dense filled-RCX transfer curve.

The filled PVT endpoint command is:

```sh
make -C OpenPLL check-dco-postlayout-filled-pvt-endpoints
```

It runs the same filled signoff Magic RCX deck at the `ff`, `fs`, `sf`, and
`ss` corners for codes 0 and 255, then writes
`build/spice_dco_postlayout_filled_pvt_endpoints/filled_dco_pvt_endpoints.csv`
and
`build/spice_dco_postlayout_filled_pvt_endpoints/filled_dco_pvt_endpoint_summary.json`.
The `ff` endpoints use serial Xyce. The `fs`, `sf`, and `ss` endpoints use the
MPI-enabled Xyce binary at `$XYCE_MPI_ROOT/bin/Xyce` with
`DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS ?= 4`.

Measured filled signoff RCX PVT endpoint results:

| Simulator | Corner | MPI ranks | Case | Transient setup | Result |
| --- | --- | ---: | --- | --- | --- |
| Xyce | `ff` | 1 | Code 0, 255 enabled loads | 55 ns, 200 ps max step, measure after 10 ns | Pass, 63.875 MHz |
| Xyce | `ff` | 1 | Code 255, zero enabled loads | 55 ns, 200 ps max step, measure after 10 ns | Pass, 72.318 MHz |
| Xyce | `fs` | 4 | Code 0, 255 enabled loads | 80 ns, 200 ps max step, measure after 10 ns | Pass, 46.796 MHz |
| Xyce | `fs` | 4 | Code 255, zero enabled loads | 80 ns, 200 ps max step, measure after 10 ns | Pass, 52.659 MHz |
| Xyce | `sf` | 4 | Code 0, 255 enabled loads | 110 ns, 200 ps max step, measure after 10 ns | Pass, 40.092 MHz |
| Xyce | `sf` | 4 | Code 255, zero enabled loads | 110 ns, 200 ps max step, measure after 10 ns | Pass, 46.062 MHz |
| Xyce | `ss` | 4 | Code 0, 255 enabled loads | 120 ns, 200 ps max step, measure after 10 ns | Pass, 30.704 MHz |
| Xyce | `ss` | 4 | Code 255, zero enabled loads | 95 ns, 200 ps max step, measure after 10 ns | Pass, 34.328 MHz |

The FF endpoint span is 8.442674 MHz, or 0.033109 MHz/LSB averaged across the
full 0-to-255 code range. The FS endpoint span is 5.863210 MHz
(0.022993 MHz/LSB), SF is 5.970058 MHz (0.023412 MHz/LSB), and SS is
3.623758 MHz (0.014211 MHz/LSB).

This is real filled-signoff RCX transient smoke evidence at five 8-bit codes
spanning the TT tuning range, plus endpoint smoke across the other four PVT
corners. It confirms the filled-deck RTL-facing polarity: increasing
`DCO_CODE` disables load cells and increases oscillator frequency. It is still
not an exhaustive filled-layout 256-code tuning curve or all-corner
filled-layout PVT oscillator sweep.

The separate `IntegerPLL_DCO_EINVP` candidate endpoint PVT command is:

```sh
make -C OpenPLL spice-dco-postlayout-einvp-pvt-endpoints
```

It runs the filled `IntegerPLL_DCO_EINVP` Magic RCX deck at the `ff`, `fs`,
`sf`, and `ss` corners for codes 0 and 255 using four-rank Xyce. The promoted
validation gate checks that each log records MPI4 timing, both endpoint rows
pass, code 255 is faster than code 0, and every corner has at least 5 MHz
endpoint span.

Measured `IntegerPLL_DCO_EINVP` RCX PVT endpoint results:

| Simulator | Corner | MPI ranks | Case | Transient setup | Result |
| --- | --- | ---: | --- | --- | --- |
| Xyce | `ff` | 4 | Code 0, 255 enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 70.251790 MHz |
| Xyce | `ff` | 4 | Code 255, zero enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 99.895518 MHz |
| Xyce | `fs` | 4 | Code 0, 255 enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 51.688142 MHz |
| Xyce | `fs` | 4 | Code 255, zero enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 70.763937 MHz |
| Xyce | `sf` | 4 | Code 0, 255 enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 44.076396 MHz |
| Xyce | `sf` | 4 | Code 255, zero enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 64.579620 MHz |
| Xyce | `ss` | 4 | Code 0, 255 enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 33.875977 MHz |
| Xyce | `ss` | 4 | Code 255, zero enabled loads | 140 ns, 200 ps max step, measure after 30 ns | Pass, 47.497548 MHz |

The endpoint spans are 29.643728 MHz at FF, 19.075795 MHz at FS,
20.503225 MHz at SF, and 13.621571 MHz at SS. This adds DCO-only PVT endpoint
coverage for the EINVP candidate; it is not closed-loop PVT signoff.

The old bounded ngspice diagnostic command is:

```sh
make -C OpenPLL spice-dco-postlayout-filled-ngspice
```

Prior ngspice filled-deck diagnostic attempts:

| Case | Transient setup | Result |
| --- | --- | --- |
| Code 255, zero enabled loads | 80 ns, 100 ps max step, measure after 20 ns | Timed out after 900.368 s |
| Code 255, zero enabled loads | 60 ns, 200 ps max step, measure after 10 ns | Timed out after 900.362 s |
| Code 255, zero enabled loads | 60 ns, 200 ps max step, measure after 10 ns, `num_threads=4` | Timed out after 120.212 s diagnostic probe |

All ngspice attempts used the filled signoff Magic RCX deck and did not reach a
frequency measurement before the timeout. The `num_threads=4` probe confirms
that ngspice threading is wired into the runner, but it does not make this deck
practical in the recorded validation environment.

For practical oscillator smoke validation, `make -C OpenPLL spice-dco-postlayout`
uses the no-fill RCX deck:

```text
OpenPLL/openlane/IntegerPLL_DCO/runs/librelane_nofill/rcx-magic/IntegerPLL_DCO.rcx.spice
```

The no-fill layout intentionally omits filler, so it is not signoff-clean. It is
used only to validate that the extracted transistor-level oscillator topology
runs and that the 8-bit control polarity is correct.

Measured no-fill RCX transient results with the Xyce post-layout target:

| DCO code | Enabled loads | Frequency |
| ---: | ---: | ---: |
| 0 | 255 | 50.944 MHz |
| 128 | 127 | 55.258 MHz |
| 255 | 0 | 60.003 MHz |

The post-layout smoke sweep confirms the RTL-facing polarity: increasing
`DCO_CODE` disables load cells and increases oscillator frequency.

## BBPD Results

Measured pre-layout BBPD transient cases:

| Case | Expected wider pulse | `UP` width | `DN` width | Result |
| --- | --- | ---: | ---: | --- |
| Reference leads feedback | `UP` | 3.380 ns | 0.379 ns | Pass |
| Feedback leads reference | `DN` | 0.376 ns | 3.376 ns | Pass |

Both cases use a 3 ns input phase offset. The leading-side pulse is wider than
the reset pulse, which confirms the detector polarity needed by the loop.

## BBPD Post-Layout RCX Results

The filled BBPD layout has zero final DRC/LVS violations and a Magic RCX deck at:

```text
OpenPLL/openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice
```

The post-layout command is:

```sh
make -C OpenPLL spice-bbpd-postlayout
```

The post-layout PVT command is:

```sh
make -C OpenPLL spice-bbpd-postlayout-pvt
```

Measured filled-layout RCX transient cases:

| Case | Expected wider pulse | `UP` width | `DN` width | Result |
| --- | --- | ---: | ---: | --- |
| Reference leads feedback | `UP` | 3.680 ns | 0.663 ns | Pass |
| Feedback leads reference | `DN` | 0.665 ns | 3.655 ns | Pass |

Both post-layout cases use the same 3 ns input phase offset as the pre-layout
BBPD deck. The extracted RCX simulation confirms that the detector polarity
survives filled layout and extraction.

Measured filled-layout RCX PVT transient cases:

| Corner | Case | Expected wider pulse | `UP` width | `DN` width | Result |
| --- | --- | --- | ---: | ---: | --- |
| `tt` | Reference leads feedback | `UP` | 3.680 ns | 0.663 ns | Pass |
| `tt` | Feedback leads reference | `DN` | 0.665 ns | 3.655 ns | Pass |
| `ff` | Reference leads feedback | `UP` | 3.483 ns | 0.471 ns | Pass |
| `ff` | Feedback leads reference | `DN` | 0.471 ns | 3.464 ns | Pass |
| `ss` | Reference leads feedback | `UP` | 4.062 ns | 1.034 ns | Pass |
| `ss` | Feedback leads reference | `DN` | 1.039 ns | 4.025 ns | Pass |
| `sf` | Reference leads feedback | `UP` | 3.777 ns | 0.742 ns | Pass |
| `sf` | Feedback leads reference | `DN` | 0.756 ns | 3.739 ns | Pass |
| `fs` | Reference leads feedback | `UP` | 3.683 ns | 0.677 ns | Pass |
| `fs` | Feedback leads reference | `DN` | 0.668 ns | 3.666 ns | Pass |

The PVT run confirms filled-RCX polarity for the tested 3 ns phase offset across
`tt`, `ff`, `ss`, `sf`, and `fs`.

The TT post-layout dead-zone command is:

```sh
make -C OpenPLL spice-bbpd-postlayout-deadzone
```

The generated sweep uses the filled BBPD RCX deck, a 1 ps transient step, and
absolute phase offsets of 0, 1, 2, 5, 10, 20, 50, 100, 200, 500, and 1000 ps.
Positive `phase_offset_ps` means the reference edge leads the feedback edge;
negative values mean feedback leads reference. Tiny-offset polarity inversions
are recorded as characterization data instead of make-target failures, while
ngspice or measurement failures still fail the target.

Measured TT dead-zone summary:

| Metric | Value |
| --- | ---: |
| Zero-offset `UP-DN` pulse-width skew | +13.464 ps |
| Smallest correct reference-leading offset | 1 ps |
| Smallest correct feedback-leading offset | 20 ps |
| Feedback-leading offsets inside skew window | 1, 2, 5, 10 ps |
| Failed ngspice/measurement rows | 0 |

This sweep shows a small UP-side offset in the current extracted layout and
reset path. It is acceptable evidence for loop-level modeling, but the BBPD
reset/delay path should still be rebalanced before tapeout use.

The all-corner post-layout dead-zone command is:

```sh
make -C OpenPLL spice-bbpd-postlayout-deadzone-pvt
```

The PVT sweep uses the same filled BBPD RCX deck at `tt`, `ff`, `ss`, `sf`,
and `fs` with phase offsets of 0, 2, 5, 10, 20, 50, 100, 200, 500, and
1000 ps. One `ss`/feedback-leading 10 ps primary run hit an ngspice
final-time timestep failure at 20 ns, so the script retried that row with an
18 ns stop time; the first BBPD event is still fully measured.

Measured all-corner dead-zone summary:

| Corner | Zero-offset `UP-DN` skew | Smallest correct REF-leading offset | Smallest correct FB-leading offset | Failed rows |
| --- | ---: | ---: | ---: | ---: |
| `ff` | +9.724 ps | 2 ps | 10 ps | 0 |
| `fs` | +4.240 ps | 2 ps | 5 ps | 0 |
| `sf` | +26.404 ps | 2 ps | 50 ps | 0 |
| `ss` | +20.970 ps | 2 ps | 50 ps | 0 |
| `tt` | +13.464 ps | 2 ps | 20 ps | 0 |

Across the sampled PVT grid, reference-leading polarity is correct at the
smallest tested 2 ps offset. Feedback-leading polarity needs up to 50 ps in the
slow-skew corners because the current reset/delay path has a systematic UP-side
offset.

## PLL Loop Acquisition Results

The closed-loop command is:

```sh
make -C OpenPLL spice-pll-loop
make -C OpenPLL spice-pll-loop-filled-dco
```

This is a PLL-level SPICE acquisition check, not a full extracted PLL
post-layout simulation. The generated deck uses:

- The transistor-level Sky130 standard-cell BBPD subcircuits.
- A behavioral DCO frequency model derived from the no-fill post-layout DCO RCX
  smoke measurements: 50.944084 MHz at code 0 and 60.002956 MHz at code 255.
- An ideal feedback divider with `NDIV=5`.
- A numerical digital-code state driven by the BBPD `UP` and `DN` pulse
  outputs. The real RTL loop filter is a fixed-point digital accumulator
  controlled by `DLF_KI` and `DLF_KP`; there is no physical loop current in the
  digital PLL.

The reset source is held deasserted for the full transient after the initial
5 ns release. Earlier long-window sampled-loop runs reused a periodic reset
source that could assert again mid-run, so those sampled acquisition numbers are
not treated as validation evidence.

The reference is 11.2 MHz, so the target DCO frequency is 56.0 MHz. The target
8-bit code for the measured no-fill post-layout DCO span is 142.320.

Measured loop-acquisition cases:

| Case | Start code | End code | Average frequency | Average error | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Low start | 0.0 | 144.590 | 55.991 MHz | -0.009 MHz | Pass |
| High start | 255.0 | 123.152 | 55.343 MHz | -0.657 MHz | Pass |

The pass gate checks that the code moves in the expected direction, the average
frequency error over the final 500 ns is within 0.75 MHz, and the final code is
within 32 LSB of the target code.

The filled-DCO calibrated command uses the same transistor-level BBPD and loop
harness, but replaces the no-fill endpoint DCO model with a smooth five-point
piecewise model fitted to the filled signoff RCX measurements: 46.256726 MHz at
code 0, 47.950391 MHz at code 64, 49.762118 MHz at code 128, 51.618437 MHz at
code 192, and 52.349831 MHz at code 255. It sets
`REF=9.95242356154668 MHz` with `NDIV=5`, so the target DCO frequency is the
measured filled code-128 frequency. The numerical code-slew setting is
24 LSB/us over an 18 us transient.

Measured filled-DCO calibrated loop-acquisition cases:

| Case | Start code | End code | Average frequency | Average error | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Low start | 0.0 | 145.117 | 50.413 MHz | +0.651 MHz | Pass |
| High start | 255.0 | 117.597 | 49.348 MHz | -0.414 MHz | Pass |

The sampled filled-DCO calibrated command is now a diagnostic target:

```sh
make -C OpenPLL spice-pll-loop-filled-dco-sampled
make -C OpenPLL spice-pll-loop-sampled-gain-sweep
make -C OpenPLL spice-pll-loop-sampled-pi-sweep
```

It uses the same five-point DCO model and BBPD cells, but updates the numerical
code state only around feedback-edge sample apertures. Its `DLF_STEP=2.5`
setting is interpreted as LSB/update, not as a physical current. This tests
sampled update-law sensitivity, but after the reset-source fix it is not a
promoted pass/fail validation target. The sampled PI model also includes a held
sampled BBPD decision and an optional `DLF_PROP_LSB` proportional offset;
`DLF_PROP_LSB=1` is approximately the same immediate 8-bit DCO-code step as
RTL `DLF_KP=4`. By comparison, RTL `DLF_KI=255` is only about 0.25 8-bit
DCO-code LSB per update, so large sampled-SPICE `DLF_STEP` values are
accelerated surrogate gains rather than literal RTL settings.

Measured reset-fixed sampled filled-DCO calibrated diagnostic cases:

| Case | Start code | End code | Average frequency | Average error | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Low start | 0.0 | 74.086 | 48.430 MHz | -1.332 MHz | Fail |
| High start | 255.0 | 113.513 | 49.352 MHz | -0.410 MHz | Pass |

Retuning `DLF_STEP`, sample delay, and simulation window without a proportional
term did not find a robust both-rail pass for this sampled surrogate. The useful
conclusion is that the LSB/update tests expose gain and sampling sensitivity;
they are not sufficient lock evidence without the proportional path.

The sampled gain sweep target records a reproducible 9-point reset-fixed grid
under `build/spice_pll_sampled_gain_sweep/`, using `DLF_STEP` values of 2.5,
3.0, and 3.5 LSB/update and sample delays of 0, 150, and 300 ps. It runs
independent ngspice decks in parallel with `SPICE_PLL_SWEEP_JOBS` and writes
`sampled_gain_sweep.csv` plus `sampled_gain_summary.csv`.

Measured I-only sampled gain-sweep summary:

| `DLF_STEP` | `DLF_PROP_LSB` | Sample delay | Low result | High result | Max average error | Both pass |
| ---: | ---: | ---: | --- | --- | ---: | --- |
| 3.5 | 0.0 | 150 ps | Fail, code 105.017 | Fail, code 160.820 | 0.952 MHz | No |
| 3.5 | 0.0 | 0 ps | Pass, code 121.981 | Fail, code 161.842 | 0.982 MHz | No |
| 3.5 | 0.0 | 300 ps | Fail, code 105.951 | Fail, code 162.543 | 1.002 MHz | No |
| 3.0 | 0.0 | 300 ps | Fail, code 91.457 | Fail, code 149.460 | 1.034 MHz | No |
| 3.0 | 0.0 | 0 ps | Fail, code 91.128 | Pass, code 141.136 | 1.044 MHz | No |
| 3.0 | 0.0 | 150 ps | Fail, code 91.045 | Pass, code 142.235 | 1.046 MHz | No |
| 2.5 | 0.0 | 300 ps | Fail, code 76.014 | Pass, code 112.995 | 1.280 MHz | No |
| 2.5 | 0.0 | 150 ps | Fail, code 74.086 | Pass, code 113.513 | 1.332 MHz | No |
| 2.5 | 0.0 | 0 ps | Fail, code 67.665 | Pass, code 113.356 | 1.504 MHz | No |

The sampled PI sweep target records a focused 16-point grid under
`build/spice_pll_sampled_pi_sweep/`, using `DLF_STEP` values of 3.0 and 3.5,
`DLF_PROP_LSB` values of 0, 1, 2, and 4, and sample delays of 0 and 150 ps.
This is the first sampled surrogate that passes both low-start and high-start
with the filled-DCO calibration.

Measured sampled PI passing rows:

| `DLF_STEP` | `DLF_PROP_LSB` | Sample delay | Low result | High result | Max average error |
| ---: | ---: | ---: | --- | --- | ---: |
| 3.5 | 4.0 | 0 ps | Pass, code 123.443 | Pass, code 140.087 | 0.351 MHz |
| 3.5 | 4.0 | 150 ps | Pass, code 120.956 | Pass, code 145.106 | 0.496 MHz |
| 3.5 | 2.0 | 0 ps | Pass, code 127.003 | Pass, code 151.372 | 0.678 MHz |
| 3.0 | 2.0 | 150 ps | Pass, code 147.484 | Pass, code 143.238 | 0.686 MHz |
| 3.0 | 2.0 | 0 ps | Pass, code 147.368 | Pass, code 143.656 | 0.705 MHz |

The PI sweep supports the concern that `P=0` is too weak or too slow in the
sampled surrogate. The best tested sampled-SPICE point uses
`DLF_PROP_LSB=4`. That maps to a sampled-loop proportional step rather than
directly to the RTL `DLF_KP` value: RTL `DLF_KP=4` is about
`DLF_PROP_LSB=1`, while the current filled-DCO behavioral recommendation
`DLF_KP=32` is stronger. The sampled PI sweep is therefore useful gain-tuning
evidence, not a final RTL gain setting.

Post-layout-BBPD in-loop diagnostics have also been attempted with the same
filled-DCO calibrated behavioral model. The ngspice filled-BBPD RCX loop deck
timed out after 240 s per case before reaching the 18 us acquisition window, so
it produced no final code/frequency measurements. The PLL loop checker now has
an Xyce waveform-output diagnostic path and a repeatable sweep target:

```sh
make -C OpenPLL spice-pll-loop-filled-bbpd-xyce-sweep
```

The sweep records continuous-loop Xyce diagnostics under
`build/spice_pll_filled_bbpd_xyce_resolved_sweep/`. Xyce treats the first
`.TRAN` value as the initial timestep, not a maximum timestep, so this target
now sets `DTMAX=1 ns` through the fourth `.TRAN` argument. The earlier 40 us
probe without an explicit `DTMAX` used only about 424 accepted timesteps and
could leave BBPD outputs latched for microseconds, so it is no longer used as
the primary filled-BBPD loop artifact.

With resolved timesteps, the current 4 us continuous-mode grid still does not
find a both-rail passing filled-BBPD setting:

| Code slew | `DTMAX` | Low result | High result | Max average error |
| ---: | ---: | --- | --- | ---: |
| 64 LSB/us | 1 ns | Fail, code 23.778 | Fail, code 242.918 | 2.746 MHz |
| 16 LSB/us | 1 ns | Fail, code 9.110 | Fail, code 245.354 | 3.272 MHz |
| 256 LSB/us | 1 ns | Fail, code 85.123 | Fail, code 0.000 | 3.505 MHz |

A separate 20 us polarity cross-check confirms that `LOOP_SIGN=+1` is the only
polarity that moves both rails, while `LOOP_SIGN=-1` leaves low-start at code
0 and high-start at code 255. The continuous-mode filled-BBPD in-loop Xyce path
is therefore a diagnostic artifact, not promoted lock validation. Runtime is the
limiting factor: the 4 us, `DTMAX=1 ns` two-rail probe needs roughly 110 s per
gain point on the current serial Xyce build. The installed Xyce reports
`Serial` from `Xyce -capabilities`; launching it with `mpirun` starts duplicate
serial processes, so the practical multicore path here is running independent
decks concurrently with the sweep scripts' `--jobs` option. With the
MPI-enabled Xyce at `$XYCE_MPI_ROOT/bin/Xyce`, set
`XYCE_MPI_PROCS=N` and reduce `--jobs` or `SPICE_PLL_SWEEP_JOBS` to avoid
oversubscription, then confirm the deck still converges.

The sampled filled-BBPD Xyce aperture diagnostic is:

```sh
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-aperture-sweep
```

This high-start-only sweep records `DLF_STEP=3.5`, `DLF_PROP_LSB=4`,
`DTMAX=1 ns`, sample delays 0 and 150 ps, and initial DCO phases 0, 0.25, 0.5,
and 0.75 cycles under
`build/spice_pll_filled_bbpd_sampled_xyce_aperture_sweep/`. The best 2 us row
is phase 0.25 cycles with 150 ps sample delay: high-start moves from code 255
to 216.733 with 2.143 MHz average error. Extending just that aperture to 8 us
under `build/spice_pll_filled_bbpd_sampled_xyce_phase025_delay150_8us/` moves
from code 255 to 188.862 with 1.675 MHz average error.

Increasing the sampled integral step at the same aperture finds a passing
two-rail filled-BBPD lock probe:

```sh
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-lock
```

That target uses the filled BBPD RCX deck, filled-DCO five-point behavioral
calibration, `DLF_STEP=17.5`, `DLF_PROP_LSB=4`, 150 ps sample delay, initial
DCO phase 0.25 cycles, 2.5 us simulation time, and `DTMAX=1 ns`. It passes with
low-start ending at code 100.826 and high-start ending at code 123.852; the
worst final-window average frequency error is 0.694 MHz. This is promoted
surrogate loop evidence for the filled BBPD macro, but it remains a fixed
aperture behavioral-DCO loop check rather than a full extracted PLL transient.

A follow-up robustness diagnostic at the same gain scanned initial DCO phases
0, 0.25, 0.5, and 0.75 cycles under
`build/spice_pll_filled_bbpd_sampled_xyce_phase_robustness/`. Only the original
0.25-cycle aperture passes both rails. Phase 0.0 fails low-start at code
176.589 while high-start passes at 152.904; phase 0.5 fails both rails at codes
190.611 and 206.283; phase 0.75 fails both rails at codes 207.462 and 255.000.
This makes the lock probe informative for polarity and one sampled aperture, but
not robust acquisition evidence across arbitrary initial phase.

The reproducible diagnostic targets are:

```sh
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness-4us
make -C OpenPLL spice-pll-loop-filled-bbpd-sampled-xyce-prop8-phase-probe
```

The 4 us run of the same `DLF_STEP=17.5`, `DLF_PROP_LSB=4` point does not fix
the phase sensitivity. It passes only the low-start rail at phase 0.5, passes
only the high-start rail at phase 0.25, and fails both rails at phases 0.0 and
0.75. A KP32-like sampled proportional probe with `DLF_PROP_LSB=8` also fails
all four initial phases; the best row still passes only the high-start rail at
phase 0.25. These negative diagnostics are kept out of the promoted validation
gate.

A separate experimental `sampled_latched` SPICE surrogate was added to model a
first-pulse BBPD decision latch between feedback updates. At the same gain point,
both `LOOP_SIGN=+1` and `LOOP_SIGN=-1` fail the four-phase filled-BBPD Xyce
diagnostic, so this latch surrogate is not promoted as validation evidence.

The PVT loop-acquisition command is:

```sh
make -C OpenPLL spice-pll-loop-pvt
```

This command uses measured all-code DCO PVT spans from
`build/spice_dco_pvt_all/dco_sweep.csv`, selects target code 128 in each
corner, sets `NDIV=5`, and derives a per-corner reference from that target
frequency. A single fixed reference across all five corners is not checked here,
because the measured DCO PVT spans do not fully overlap. The generated SPICE
deck still uses the transistor-level Sky130 BBPD cell subcircuits, behavioral
DCO frequency model, ideal divider, and numerical digital-code surrogate
described above; it is not a full extracted PLL post-layout simulation.

The PVT target uses `--code-slew-lsb-per-us 25`, `--sim-time-us 20`, target
code 128, and an adaptive frequency tolerance of the larger of 1.0 MHz or 32
DCO LSBs for the measured corner span. The code-slew value is only a SPICE
loop-gain knob for the numerical code state; it is not a charge-pump current.

Measured PLL-level PVT acquisition cases:

| Corner | Case | Target frequency | Reference | End code | Average frequency | Average error | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `tt` | Low start | 116.382 MHz | 23.276 MHz | 141.034 | 117.928 MHz | +1.547 MHz | Pass |
| `tt` | High start | 116.382 MHz | 23.276 MHz | 110.906 | 113.570 MHz | -2.811 MHz | Pass |
| `ff` | Low start | 162.867 MHz | 32.573 MHz | 114.397 | 160.963 MHz | -1.904 MHz | Pass |
| `ff` | High start | 162.867 MHz | 32.573 MHz | 151.166 | 166.764 MHz | +3.897 MHz | Pass |
| `ss` | Low start | 76.654 MHz | 15.331 MHz | 119.629 | 75.862 MHz | -0.792 MHz | Pass |
| `ss` | High start | 76.654 MHz | 15.331 MHz | 126.633 | 76.857 MHz | +0.202 MHz | Pass |
| `sf` | Low start | 97.698 MHz | 19.540 MHz | 130.339 | 97.810 MHz | +0.112 MHz | Pass |
| `sf` | High start | 97.698 MHz | 19.540 MHz | 97.924 | 94.273 MHz | -3.425 MHz | Pass |
| `fs` | Low start | 123.055 MHz | 24.611 MHz | 137.170 | 124.313 MHz | +1.257 MHz | Pass |
| `fs` | High start | 123.055 MHz | 24.611 MHz | 112.145 | 120.424 MHz | -2.631 MHz | Pass |

All ten PVT rows pass the same direction-of-motion and final-window convergence
checks. This improves loop-polarity/acquisition confidence across measured DCO
PVT spans, but it remains a PLL-level surrogate rather than transistor-level
closed-loop silicon extraction evidence.

## Top-Level Behavioral Acquisition

The top-level behavioral acquisition command is:

```sh
make -C OpenPLL pll-top-model-acq
```

This is not SPICE. It instantiates `IntegerPLL_Top` with the behavioral DCO and
a two-flop delayed-reset behavioral BBPD model, so the loop is driven by
reference/feedback phase instead of an ideal code comparator. The default target
uses the modeled code-128 DCO frequency, `MMDCLKDIV_RATIO=8`,
`REF=12.742100 MHz`, `DLF_KI=255`, and the legacy `DLF_KP=4`.

The digital core captures raw BBPD UP/DN events in the `PLLOUT` domain and
feeds a held BBPD decision to the DLF. Capture state is flushed while the loop
is disabled or cleared, preventing stale pre-enable BBPD outputs from becoming
the first active command. The latch also prevents a captured UP or DN pulse from
being overwritten into `2'b11` during BBPD reset overlap, which the DLF treats
as idle.

Measured top-level behavioral acquisition cases:

| Case | Start code | End code | Lock time | Min code error | BBPD commands | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Low start | 0 | 127 | 37.408 us | 0 | 522 UP / 0 DN / 1927 idle | Pass |
| High start | 255 | 128 | 22.446 us | 0 | 95 UP / 95 DN / 2456 idle | Pass |

The filled-DCO calibrated top-level behavioral command is:

```sh
make -C OpenPLL pll-top-filled-dco-acq
```

This is also not SPICE. It uses the same top-level RTL and behavioral BBPD, but
enables the five-point filled-RCX DCO model, sets `MMDCLKDIV_RATIO=8`, uses
`REF=6.220298 MHz` for target code 128, and now selects the stronger
`DLF_KI=255`, `DLF_KP=32` operating point.

Measured filled-DCO calibrated top-level behavioral acquisition cases:

| Case | Start code | End code | Lock time | Min code error | BBPD commands | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Low start | 0 | 136 | 70.244 us | 0 | 934 UP / 0 DN / 419 idle | Pass |
| High start | 255 | 136 | 66.519 us | 0 | 431 UP / 14 DN / 938 idle | Pass |

The filled-DCO calibrated top-level gain sweep command is:

```sh
make -C OpenPLL pll-top-filled-dco-gain-sweep
```

This sweep uses the same top-level RTL, behavioral BBPD, and five-point
filled-DCO model as `pll-top-filled-dco-acq`, but checks `DLF_KI` values 192
and 255 against `DLF_KP` values 0, 4, 8, 16, and 32. It writes
`build/pll_top_filled_dco_gain_sweep/pll_top_gain_sweep.csv` and
`pll_top_gain_summary.csv`.

Measured filled-DCO calibrated top-level gain sweep summary:

| `DLF_KI` | `DLF_KP` | Low lock | High lock | Final codes | Max final error | Result |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 192 | 4 | 99.541 us | 94.094 us | 129 / 127 | 1 | Pass |
| 255 | 8 | 74.385 us | 70.346 us | 126 / 130 | 2 | Pass |
| 255 | 16 | 73.003 us | 68.965 us | 132 / 132 | 4 | Pass |
| 192 | 16 | 96.776 us | 91.491 us | 132 / 132 | 4 | Pass |
| 255 | 32 | 70.244 us | 66.519 us | 136 / 136 | 8 | Pass |
| 192 | 32 | 93.153 us | 88.124 us | 136 / 136 | 8 | Pass |
| 192 | 8 | 98.673 us | 93.333 us | 115 / 130 | 13 | Pass |
| 192 | 0 | 100.571 us | 94.855 us | 138 / 113 | 15 | Pass |
| 255 | 4 | 75.076 us | 70.957 us | 129 / 112 | 16 | Pass |
| 255 | 0 | 75.768 us | 71.568 us | 109 / 134 | 19 | Fail |

The filled top-level phase model therefore supports more proportional gain than
the ideal-detector exact-code setting, but it does not support treating
`DLF_KP=0` as a good filled-DCO operating point at `DLF_KI=255`: that row passes
through the target but ends outside the 16-code endpoint tolerance. `DLF_KI=255`,
`DLF_KP=32` is the current filled-DCO operating recommendation because it is the
fastest passing row in this sweep, stays within eight final codes in the
top-level phase bench, and has transistor-level DLF cone evidence.

This closes the earlier gap where the gain sweep only proved the digital
accumulator under an ideal sign detector. It still does not prove extracted
closed-loop jitter or post-layout phase stability.

## Digital DLF Gain Sweep

The digital gain-sweep command is:

```sh
make -C OpenPLL digital-loop-gain-sweep
```

This is not SPICE. It is RTL evidence for the real digital loop filter update
law using `DLF_KI` and `DLF_KP`. The testbench drives the synthesizable
`IntegerPLL_DigitalCore` with an ideal sign detector: when `DCO_CODE` is below
target it drives `BBPD=2'b10`, and when `DCO_CODE` is above target it drives
`BBPD=2'b01`. That isolates digital accumulator behavior and 8-bit code
acquisition from BBPD analog timing, which is validated separately by SPICE.

The current sweep target checks low-start and high-start acquisition from
`DCO_CODE=0` and `DCO_CODE=255` toward target code 128 using a corrected 200 us
behavioral window. The ideal sign detector is registered on
`CLKDIV_RETIMED`, so nonzero `DLF_KP` settings do not create a zero-delay
testbench feedback loop.

Measured digital gain-sweep summary:

| `DLF_KI` | `DLF_KP` | Low lock | High lock | Final codes | Result |
| ---: | ---: | ---: | ---: | ---: | --- |
| 64 | 0 | 150.308 us | 89.455 us | 128 / 128 | Pass |
| 64 | 4 | 148.561 us | 88.683 us | 128 / 128 | Pass |
| 128 | 4 | 74.324 us | 44.400 us | 128 / 128 | Pass |
| 255 | 0 | 37.846 us | 22.515 us | 128 / 128 | Pass |
| 255 | 2 | 37.627 us | 22.419 us | 128 / 128 | Pass |
| 255 | 4 | 37.408 us | 22.323 us | 127 / 128 | Pass |
| 255 | 16 | 36.102 us | 21.740 us | 121 / 127 | Pass within tolerance |
| 255 | 32 | 34.375 us | 20.948 us | 129 / 127 | Pass within tolerance |

The proportional path is scaled in 10-bit `DLF_CODE` LSBs, so `DLF_KP=4` is
approximately one immediate 8-bit `DCO_CODE` correction. The exact-code
acquisition setting in this ideal bench is `DLF_KI=255`, `DLF_KP=2`, with
37.627 us worst-case lock. `DLF_KP=32` is faster inside the loose +/-32-code
window and now leaves only one final code of error in the ideal detector bench;
in the filled-DCO top-level behavioral bench it is a faster bounded-error row,
not an exact endpoint row. The lowest-gain passing ideal-detector point remains
`DLF_KI=64`, `DLF_KP=0`, but it needs 150.308 us from the low-code start; with
the filled-DCO phase model, `DLF_KI=255`, `DLF_KP=0` fails the 220 us endpoint
check. Final gain selection still needs extracted closed-loop jitter and
phase-stability validation.

A synthesized-DLF transistor-level static SPICE check now exists:

```sh
make -C OpenPLL spice-dlf-static
make -C OpenPLL spice-dlf-static-kp16
make -C OpenPLL spice-dlf-static-kp32
```

It extracts the mapped Sky130 combinational proportional path from DLF state
and held BBPD decision input to top-level `DCO_CODE`. With a directly driven
mid-scale accumulator state and `num_threads=4`, the 109-cell static cone
passes the legacy proportional setting and both stronger-P candidates:

| `DLF_KI` | `DLF_KP` | Case | Expected DCO code | Measured DCO code | Result |
| ---: | ---: | --- | ---: | ---: | --- |
| 255 | 4 | Hold | 128 | 128 | Pass |
| 255 | 4 | Increase | 129 | 129 | Pass |
| 255 | 4 | Decrease | 127 | 127 | Pass |
| 255 | 16 | Hold | 128 | 128 | Pass |
| 255 | 16 | Increase | 132 | 132 | Pass |
| 255 | 16 | Decrease | 124 | 124 | Pass |
| 255 | 32 | Hold | 128 | 128 | Pass |
| 255 | 32 | Increase | 136 | 136 | Pass |
| 255 | 32 | Decrease | 120 | 120 | Pass |

This is transistor-level Sky130 standard-cell evidence for the proportional
DCO-code correction path, not a transient proof of the full sequential
integrator update.

A synthesized-DLF transistor-level transient check also exists:

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
```

That check extracts the mapped Sky130 DCO-code/DLF sequential cone from
`build/synth/IntegerPLL_DigitalCore_sky130.v`, drives both `PLLOUT` and
`CLKDIV_RETIMED`, and verifies the BBPD decision-latch path plus DLF update. It
reduces the 906-cell mapped digital core to a 330-cell DCO-code update cone for
the current KP32 run, uses Xyce with a 45 ns transient window, and verifies real
accumulator/code response. The pass/fail metric now uses the directional
response-window code as well as the final code, because the proportional term
can be a transient correction while `DLF_KI=255` moves the exported 8-bit
`DCO_CODE` by less than one LSB per update. The overlap rows drive the first raw
BBPD polarity, then force raw `BBPD=2'b11` before the enabled update edge; they
verify that the synthesized first-decision latch keeps the original polarity
rather than turning the reset-overlap interval into an idle command:

| `DLF_KI` | `DLF_KP` | Case | Expected movement | Measure time | Start code | End code | Response code | Result |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 255 | 32 | Increase | Up | 44.0 ns | 128 | 128 | 136 | Pass |
| 255 | 32 | Decrease | Down | 44.0 ns | 128 | 127 | 88 | Pass |
| 255 | 32 | UP then `2'b11` | Up | 44.0 ns | 128 | 128 | 136 | Pass |
| 255 | 32 | DN then `2'b11` | Down | 44.0 ns | 128 | 127 | 88 | Pass |

A heavier overlap-only target also runs the same reset-overlap update check
through the full mapped 906-cell digital-core netlist:

```sh
make -C OpenPLL spice-dlf-update-full-kp32-overlap
```

For `DLF_KI=255`, `DLF_KP=32`, the full-core Xyce run passes the UP and DN
reset-overlap response checks. `scripts/spice_dlf_update_check.py` accepts
`--jobs`, and the Makefile DLF-update targets pass `SPICE_PLL_SWEEP_JOBS`, so
independent cases can run concurrently on multiple cores.

A post-PnR final-netlist cone target also reads the signed-off LibreLane
netlist:

```sh
make -C OpenPLL spice-dlf-update-signoff-nl-kp32
```

That target first runs `check-librelane-signoff`, then extracts the DCO-code
update cone from
`openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/nl/IntegerPLL_DigitalCore.nl.v`.
The final netlist contains filler/decap/antenna cells and post-PnR single-line
instance syntax; the shared SPICE parser handles that form and extracts a
540-cell DLF cone. The transient schedule is compressed to a 24 ns window so
the 6658-device, 22328-unknown decks finish cleanly on the serial Xyce build:

| `DLF_KI` | `DLF_KP` | Source netlist | Case | Expected movement | Measure time | Start code | End code | Response code | Result |
| ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 255 | 32 | final signoff netlist, 540-cell cone | Increase | Up | 23.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | Decrease | Down | 23.0 ns | 128 | 127 | 0 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | UP then `2'b11` | Up | 24.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | DN then `2'b11` | Down | 24.0 ns | 128 | 127 | 0 | Pass |

This is transistor-level Sky130 standard-cell evidence from the final post-PnR
gate netlist. It still does not include SPEF interconnect parasitics in the
transient deck and is not a full extracted PLL loop simulation.

The corresponding lumped-SPEF-capacitance target is:

```sh
make -C OpenPLL spice-dlf-update-signoff-spef-kp32
```

It uses the same final netlist cone and adds the nominal OpenROAD SPEF total
capacitance for every modeled cone net as a lumped capacitor to `VGND`. The
current run adds capacitance on 582 routed nets, 2678.819 fF total. The decks
contain 540 standard-cell instances plus 582 `CSPEF_*` capacitors; Xyce reports
7240 total devices for the `inc_mid` deck. The four KP32 rows pass:

| `DLF_KI` | `DLF_KP` | Source netlist | SPEF model | Case | Expected movement | Measure time | Start code | End code | Response code | Result |
| ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 255 | 32 | final signoff netlist, 540-cell cone | 582 lumped caps, 2678.819 fF | Increase | Up | 23.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | 582 lumped caps, 2678.819 fF | Decrease | Down | 23.0 ns | 128 | 127 | 0 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | 582 lumped caps, 2678.819 fF | UP then `2'b11` | Up | 24.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | 582 lumped caps, 2678.819 fF | DN then `2'b11` | Down | 24.0 ns | 128 | 127 | 0 | Pass |

This is stronger post-route loading evidence than the final-netlist-only deck,
but the lumped-capacitance deck still does not insert interconnect resistance
between individual cell pins.

The distributed-RC SPEF target is:

```sh
make -C OpenPLL spice-dlf-update-signoff-spef-rc-kp32
```

It substitutes SPEF instance-pin nodes into the same final-netlist cone, inserts
the nominal SPEF resistance tree, and grounds the current-net capacitance at
the reported SPEF nodes. Coupling entries are represented as grounded
capacitance at the current-net endpoint so the reduced cone does not require
neighbor nets outside the DLF cone. The current decks contain 540 standard-cell
instances, 2056 substituted SPEF pin nodes, 3373 `CSPEF_*` capacitors, and
2513 `RSPEF_*` resistors; Xyce reports 12544 total devices and 25527 unknowns
for the `inc_mid` deck. The four KP32 rows pass:

| `DLF_KI` | `DLF_KP` | Source netlist | SPEF model | Case | Expected movement | Measure time | Start code | End code | Response code | Result |
| ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 255 | 32 | final signoff netlist, 540-cell cone | distributed RC, 3373 caps, 2513 resistors | Increase | Up | 23.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | distributed RC, 3373 caps, 2513 resistors | Decrease | Down | 23.0 ns | 128 | 127 | 32 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | distributed RC, 3373 caps, 2513 resistors | UP then `2'b11` | Up | 24.0 ns | 128 | 128 | 152 | Pass |
| 255 | 32 | final signoff netlist, 540-cell cone | distributed RC, 3373 caps, 2513 resistors | DN then `2'b11` | Down | 24.0 ns | 128 | 127 | 32 | Pass |

This is the strongest current post-route transistor-level evidence for the
digital DLF update cone. It is still not a full extracted PLL loop transient.

BBPD-to-DLF integration targets drive the mapped DLF update path from the
filled post-layout BBPD RCX macro instead of ideal raw BBPD sources:

```sh
make -C OpenPLL spice-bbpd-dlf-integration
make -C OpenPLL spice-bbpd-dlf-integration-full
make -C OpenPLL spice-bbpd-dlf-integration-signoff-spef-rc
```

The BBPD macro is driven by one reference pulse and one divided-feedback pulse;
its `BBPD[1:0]` outputs directly drive the mapped DLF update logic. The reduced
target uses the DCO-code update cone, while the full target uses all 906 mapped
digital-core cells. The BBPD reset is held until `DLF_En=1` and `DLF_Clear=0`,
matching the top-level reset policy. The DLF update clock remains a boundary
source, so this is a BBPD-output/DLF-input integration check, not a closed
oscillator loop.

| Scope | `DLF_KI` | `DLF_KP` | BBPD RCX case | Expected movement | Measure time | Start code | End code | Response code | Result |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 330-cell cone | 255 | 32 | REF leads feedback | Up | 44.0 ns | 128 | 128 | 136 | Pass |
| 330-cell cone | 255 | 32 | Feedback leads REF | Down | 44.0 ns | 128 | 127 | 88 | Pass |
| 906-cell full core | 255 | 32 | REF leads feedback | Up | 44.0 ns | 128 | 128 | 136 | Pass |
| 906-cell full core | 255 | 32 | Feedback leads REF | Down | 44.0 ns | 128 | 127 | 0 | Pass |
| 540-cell final DLF cone + distributed SPEF RC | 255 | 32 | REF leads feedback | Up | 42.0 ns | 128 | 136 | 152 | Pass |
| 540-cell final DLF cone + distributed SPEF RC | 255 | 32 | Feedback leads REF | Down | 42.0 ns | 128 | 120 | 32 | Pass |

The final-DLF-cone integration deck combines the filled BBPD RCX macro with the
post-route distributed-RC DLF cone in one Xyce transient. Each deck contains
the BBPD RCX subcircuit, 540 digital-cell instances, 2056 substituted SPEF pin
nodes, 3373 grounded SPEF capacitance entries, and 2513 SPEF resistors. Xyce
reports 14455 total devices and 30746 unknowns for these integration decks.

On the current serial Xyce build, the refreshed full-core BBPD-RCX cases took
about 306 s each when run concurrently as independent simulator processes. An
MPI-enabled Xyce build is installed at `$XYCE_MPI_ROOT/bin/Xyce`,
but that build currently aborts at the first 25 ps step on the full mapped
standard-cell DLF deck, so the promoted full-core DLF artifacts use the serial
`XYCE` binary.

The mapped-loop smoke target closes the short feedback path through the filled
BBPD RCX macro and all 906 mapped digital-core cells:

```sh
make -C OpenPLL spice-pll-mapped-loop-smoke
```

It uses the mapped MMD divider to generate `CLKDIV_RETIMED`, the filled BBPD
RCX macro to compare that feedback clock against `REF`, and the mapped DLF to
update `DCO_CODE`. The DCO itself is still the five-point behavioral model
fitted to filled-DCO RCX measurements, so this is not a full extracted PLL
transient. The target uses phase-selected initial DCO states to verify both
first-correction polarities in a 180 ns window:

| Case | Initial DCO phase | Start code | End code | Response code | Expected movement | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Low start | 0.0 cycles | 0.0 | 8.0 | 8.0 | Up | Pass |
| High start | 0.25 cycles | 255.0 | 247.0 | 247.0 | Down | Pass |

The installed Xyce binary reports `Serial`; `spice-pll-mapped-loop-smoke`
therefore uses `SPICE_PLL_SWEEP_JOBS` to run the independent low/high decks
concurrently instead of trying to parallelize a single transient solve. The
same target will use per-deck MPI only when `XYCE_MPI_PROCS` is set with an
MPI-enabled Xyce binary.

`spice-pll-mapped-loop-gain-sweep` keeps the same full mapped digital core,
filled BBPD RCX macro, and behavioral filled-DCO calibration, starts at code
128, and sweeps the proportional gain under a phase-selected upward decision:

```sh
make -C OpenPLL spice-pll-mapped-loop-gain-sweep
```

Measured 180 ns mapped-loop gain response:

| `DLF_KI` | `DLF_KP` | Check mode | Start code | End code | Response delta | Result |
| ---: | ---: | --- | ---: | ---: | ---: | --- |
| 255 | 0 | No motion | 128.0 | 128.0 | 0.0 | Pass |
| 255 | 4 | Motion | 128.0 | 129.0 | 1.0 | Pass |
| 255 | 8 | Motion | 128.0 | 130.0 | 2.0 | Pass |
| 255 | 16 | Motion | 128.0 | 132.0 | 4.0 | Pass |
| 255 | 32 | Motion | 128.0 | 136.0 | 8.0 | Pass |

This is useful gain-tuning evidence through the mapped divider, filled BBPD,
and mapped DLF. It is still behavioral on the DCO side; the extracted-DCO
mid-code KP0/KP32 anchors below check the two most important endpoints with the
filled DCO RCX macro.

The mapped-loop generator also has extracted-DCO startup smoke targets:

```sh
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-startup
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu
```

This instantiates the filled DCO RCX macro on the mapped `DCO_THERM[254:0]`
decoder outputs, keeps the filled BBPD RCX macro in the loop, and labels rows
as `dco_model=postlayout_rcx`. The promoted target uses serial Xyce
(``) with `uic` plus a VPWR/VPB rail ramp. In this 50 ns
startup window the digital loop filter has not yet enabled, so the DCO code and
response code remain effectively 0; this is oscillator startup evidence in the
coupled mapped deck, not closed-loop code correction or lock evidence.

| Case | Xyce | Mapped cells | BBPD | DCO | PLLOUT rises after 15 ns | Startup period | Startup frequency | Result |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| Low start | Serial | 906 | Filled RCX | Filled RCX | 2 | 21.616261729 ns | 46.261467988 MHz | Pass |
| Low start | MPI4, `-linsolv KLU` | 906 | Filled RCX | Filled RCX | 2 | 21.616261760 ns | 46.261467923 MHz | Pass |

The MPI4 KLU startup row uses
`$XYCE_MPI_ROOT/bin/Xyce -linsolv KLU` and records a 4-processor
timing summary. In these targets, "MPI4" means four MPI ranks launched by
`mpirun -np 4`, not four Xyce threads. It completed the same 50 ns startup deck
in 226.138 s elapsed time, compared with 440.731 s for the serial startup run on
the recorded validation environment. Four ranks are the current empirical default, not a proven
optimum. A short 12 ns extracted-DCO debug timing sweep with the MPI/KLU binary
measured 169.042 s at 1 rank, 123.398 s at 2 ranks, 84.596 s at 4 ranks,
68.961 s at 8 ranks, and 57.493 s at 16 ranks; a 32-rank launch failed because
Open MPI exposed only 16 slots by default. Those 12 ns rows are timing-only
debug runs, not functional validation rows, because the window captures only one
`PLLOUT` rise. The follow-on FRAC=6 260 ns trend rows below confirm that 16
ranks improve wall time on real extracted-DCO loop decks while preserving the
same endpoint behavior.

The longer extracted-DCO first-correction smoke targets are:

```sh
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-motion
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu
```

These run the same coupled mapped-core, filled-BBPD-RCX, filled-DCO-RCX deck
to 180 ns from both rails. Both serial and MPI4/KLU cases pass the directional
first-correction check with `DLF_KI=255`, `DLF_KP=32`, and
`MMDCLKDIV_RATIO=2`:

| Case | Xyce | Start code | Response code | End code | Integrator start/end | Corrected-code dwell | Startup frequency | Expected movement | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Low start | Serial | 0.0 | 8.0 | 8.0 | 0.00 / 0.00 | 41.612512 ns at code 8 | 46.213639188 MHz | Up | Pass |
| High start | Serial | 255.0 | 166.034845 | 255.0 | 255.00 / 254.75 | 37.150000 ns at code 247 | 51.952310560 MHz | Down | Pass |
| Low start | MPI4, `-linsolv KLU` | 0.0 | 8.0 | 8.0 | 0.00 / 0.00 | 41.609479 ns at code 8 | 46.234150122 MHz | Up | Pass |
| High start | MPI4, `-linsolv KLU` | 255.0 | 166.034845 | 255.0 | 255.00 / 254.75 | 37.150000 ns at code 247 | 51.952310820 MHz | Down | Pass |

The high-start waveform includes a stable code-247 dwell interval in the
response window before returning to the high rail by 179 ns. The visible
`DCO_CODE` response includes the proportional term; the integrator columns show
that the accumulated loop state has moved by at most 0.75 DCO-code LSB in this
short window. The MPI4/KLU first-correction rows completed in 692.448 s
low-start and 512.197 s high-start elapsed time in the recorded validation environment. These
180 ns runs prove startup, feedback divider activity, filled-BBPD decision
propagation, and first DLF output movement through the full 906-cell mapped
digital core. They are still not lock or acquisition validation.

The integrator-trend targets extend the MPI4/KLU extracted-DCO decks to 260 ns:

```sh
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-high-phase0p5-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu
```

They keep the same loop settings and initial phases as the first-correction
rows. Low start keeps visible `DCO_CODE` at code 8 after the first proportional
correction, while the internal DLF integrator advances from 0.00 to 0.25 DCO-code
units by 259 ns. High start ends at visible code 246, reaches a minimum
integrator code of 254.00 DCO-code units, and dwells for 56.925000 ns in the
code-246/247 band. The rows record 11 and 13 `PLLOUT` rises, 46.220481051 MHz
and 52.482096017 MHz startup frequencies, and 818.450 s and 691.313 s elapsed
wall time in the recorded validation environment. This is the current strongest extracted-DCO loop
evidence because it shows the slow integral state accumulating in both
directions, but it is still far short of full acquisition or lock.

The FRAC=6 extracted-DCO trend companion uses the current gain-tuning candidate
netlist with 889 mapped cells and `DLF_KI=255`, `DLF_KP=32`. Low start ends at
visible code 9 after 260 ns, with the integrator moving from 0.00 to 1.75
DCO-code units. High start still ends at visible code 246, but the integrator
ends at 254.00 instead of 254.75 and the measured code no longer dips to the old
code-166 transient. The rows record 11 and 13 `PLLOUT` rises, 46.225404681 MHz
and 52.447728469 MHz startup frequencies, and 800.325 s and 669.374 s elapsed
wall time. This strengthens the case that FRAC=6 increases integral motion in
the coupled extracted-DCO deck, but it still does not prove acquisition or lock.
The audited MPI16 companion rows use the same FRAC=6 netlist, KLU solver, loop
gains, initial phases, and 260 ns windows. They reproduce the MPI4 endpoints and
integrator motion: low start still ends at code 9 with integrator 1.75, and high
start still ends at code 246 with integrator 254.00. They reduce elapsed wall
time to 568.490 s low-start and 467.746 s high-start, speedups of 1.408x and
1.431x versus the MPI4 rows. This makes 16 MPI ranks the better default for
future long FRAC=6 extracted-DCO diagnostics on this host, but it is an
acceleration result rather than new lock evidence.

`spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu` extends
the FRAC=6 extracted-DCO rail-start check to 500 ns using two concurrent
MPI16/KLU Xyce jobs. Low start moves visible code 0 to 15, with the integrator
moving 0.00 to 7.75, 22 startup `PLLOUT` rises, and 46.243607848 MHz tail
frequency. High start moves visible code 255 to 240, with the integrator moving
255.00 to 248.00, 25 startup `PLLOUT` rises, and 53.072273197 MHz tail
frequency. The rows took 1473.445 s and 1408.858 s wall time when run
concurrently. This is stronger true rail-start extracted-DCO progress than the
260 ns trend rows, but both tails remain more than 3 MHz from the
49.762117808 MHz target, so it is not acquisition or lock evidence.

`spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu` is a
non-promoted rail-start release-phase probe. It repeats the FRAC=6 rail-start
deck with `DLF_En=85 ns`, matching the enable timing that helps the local
near-high lock row. That timing is not a global rail-start improvement:
low-start only shows a transient response to code 8 and returns to code 0 by
299 ns, with integrator 0.75 and a 46.204983633 MHz tail. High-start moves
255 to 244 with integrator 252.00 and a 53.133254162 MHz tail. The result says
the enable-85 setting is useful for the phase-selected near-high local check but
should not replace the default rail-start progress target.

`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu` adds a
bounded near-lock extracted-DCO check using `lock_window` mode. It starts from
code 128 with FRAC=6, `DLF_KI=255`, `DLF_KP=32`, runs 220 ns with MPI16/KLU, and
requires code 127..140 plus tail `PLLOUT` frequency within 0.25 MHz of the
49.762117808 MHz target over 139..219 ns. The passing artifact ends at code
137, integrator 129.75, measures 49.676823500 MHz over four tail rises, and has
0.085294 MHz tail error with 79.725 ns dwell in the code-136/137 band. This is
the strongest extracted-DCO near-lock evidence so far, but it starts near target
and is not rail-to-rail acquisition.

`spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu`
is a non-promoted lower-P gain diagnostic based on the lower endpoint error seen
in the filled-DCO behavioral top sweep. It runs the same extracted-DCO mid-code
deck with `DLF_KI=192`, `DLF_KP=8`, a tighter 127..132 code window, and a
0.15 MHz tail-frequency bound. The artifact fails cleanly: code moves 128 to
131, the integrator moves 128.00 to 129.50, and the tail measures
49.488441487 MHz, 0.273676 MHz below target. This reduces visible code
overshoot but gives worse extracted tail accuracy than the promoted KP32 row,
so it is useful gain-tuning evidence rather than a replacement setting.

`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu` is
an intentionally non-promoted high-side diagnostic using `--allow-fail`. It
starts from code 160 and requires downward motion plus the same 0.25 MHz tail
frequency bound. The current artifact fails cleanly: code moves 160 to 169,
integrator 160.00 to 161.75, and the tail frequency is 50.602594662 MHz,
0.840477 MHz above target. This says the 220 ns extracted loop still has a
phase-driven upward transient from this nominally high local start; it is a
tuning/phase diagnostic, not lock evidence.

`spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu`
repeats that high-side start with `DLF_En=85 ns`, after the REF edge and before
the feedback edge. This flips the first captured BBPD decision to DN. The 380 ns
MPI16/KLU artifact passes `lock_window`: code moves 160 to 146, the integrator
moves 160.00 to 154.00, and the tail over 299..379 ns measures
50.001270745 MHz, 0.239153 MHz above target, with four tail rises. The waveform
stays inside the configured 128..161 code band across the lock window and then
dwells for 48.675 ns in the final code-146..148 band. Together with the
mid-code upward row this is stronger two-sided near-lock evidence, but it is
still phase-selected and not rail-start acquisition.

Repeating the FRAC=6 extracted-DCO high-start trend at an initial DCO phase of
0.5 cycles produced the same endpoint and waveform sequence as the 0.25-cycle
row: visible code 255 to 246, integrator 255.00 to 254.00, 13 `PLLOUT` rises,
52.447728469 MHz startup frequency, and 667.423 s elapsed wall time. That makes
the phase-0.5 row a useful robustness/negative diagnostic, not evidence of
faster high-start convergence.

`spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu` starts the same
MPI4/KLU extracted-DCO deck at DLF/DCO code 128 and uses an initial phase that
requests an upward correction. In the 79-179 ns measurement window it moves
visible `DCO_CODE` from 128 to 136, holds the internal integrator at 128.00, and
dwells at code 136 for 47.250000 ns. This is useful proportional-path and gain
polarity evidence from a non-saturated code, but it does not replace the
low/high 260 ns integral-trend checks or prove lock.

`spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu` reruns the same
mid-code upward-decision extracted-DCO deck with `DLF_KP=0`. It finishes cleanly
under MPI4/KLU, but visible `DCO_CODE` stays at 128 for the entire 79-179 ns
measurement window, with 99.725000 ns of code-128 dwell and the internal
integrator still at 128.00. This is promoted as gain-contrast evidence: it
supports the stronger-P choice by showing that the otherwise identical short
extracted loop has no observable 8-bit correction when the proportional path is
disabled.

The promoted artifact audit also measures `PLLOUT` in the 119-179 ns tail window
of those same two extracted-DCO mid-code waveforms. The KP32 row averages
49.699374052 MHz while the otherwise identical KP0 row averages 49.464265788 MHz,
a 0.235108264 MHz separation. This ties the visible proportional code response to
measured oscillator frequency, but it is still a short-window gain contrast, not
closed-loop acquisition or lock.

The MPI-enabled Xyce binary at `$XYCE_MPI_ROOT/bin/Xyce` needs an
explicit direct-solver override for this mixed mapped-core plus DCO-RCX deck.
Without `-linsolv KLU`, the same binary leaves sampled `DCO_THERM_0`,
`DCO_THERM_127`, `DCO_THERM_128`, and `DCO_THERM_254` low even at one rank
after the rail reaches 1.8 V, and `PLLOUT` never starts. With `-linsolv KLU`,
the 4-rank startup and first-correction decks match the corresponding serial
response metrics. Any future extracted acquisition artifacts still need the
same MPI/KLU-vs-serial correlation before promotion.

The final-signoff functional-netlist mapped-loop smoke target is:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-smoke
```

This uses the final digital-core signoff netlist rather than the synthesized
mapped netlist. For Xyce compatibility it drops physical-only tap, fill,
decap, and antenna diode cells from the final netlist; the simulated functional
core contains 1614 mapped standard-cell instances and skips 4029 physical-only
instances. The filled BBPD RCX macro and behavioral filled-DCO model are the
same as the mapped-loop smoke above, so this is still not a full extracted PLL
transient.

| Case | Initial DCO phase | Functional cells | Skipped physical-only cells | Start code | End code | Response code | Expected movement | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Low start | 0.0 cycles | 1614 | 4029 | 0.0 | 0.0 | 8.0 | Up | Pass |
| High start | 0.25 cycles | 1614 | 4029 | 255.0 | 254.0 | 190.0 | Down | Pass |

The hard-top-SPEF loaded mapped-loop smoke target is:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke
```

This uses the hard-top-consistent FRAC=6 force-to-mid final digital-core
signoff netlist, `DLF_KI=160`, `DLF_KP=8`, and the MPI-enabled Xyce/KLU binary
with four ranks per rail-start case. It keeps 2020 functional mapped cells,
drops 4138 physical-only cells, and adds lumped nominal hard-macro-top SPEF
capacitance on 261 loop/inter-macro nets. The modeled top-level load totals
27097.842 fF and covers all 255 DCO thermometer interconnects. The behavioral
DCO observes the loaded `DCO_THERM` bus rather than the debug `DCO_CODE` bus,
matching the hard DCO macro control interface.

| Case | Xyce ranks | Initial DCO phase | Functional cells | Hard-top SPEF cap nets | Hard-top SPEF cap total | Start code | End code | Response code | Expected movement | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Low start | 4 | 0.0 cycles | 2020 | 261 | 27097.842 fF | 0.0 | 20.0 | 22.0 | Up | Pass |
| High start | 4 | 0.5 cycles | 2020 | 261 | 27097.842 fF | 255.0 | 233.0 | 233.0 | Down | Pass |

This promotes top-level loop-net loading evidence into the mapped-loop smoke,
but it is still a lumped-SPEF behavioral-DCO transient. It does not replace a
full closed-loop hard-macro-top extracted transient.

The optional distributed hard-top SPEF RC startup diagnostic is:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-startup-diagnostic
```

This uses the same final signoff netlist, gains, and hard-top SPEF, but keeps
the selected hard-top loop/inter-macro nets as distributed RC. The generated
low-start deck covers 261 hard-top SPEF nets, emits 1752 grounded capacitance
nodes and 1657 resistors, substitutes 260 digital-core pins onto SPEF endpoint
nodes, and covers all 255 DCO thermometer interconnects. The selected
capacitance is 27097.841 fF, matching the lumped-cap smoke within rounding.

| Case | Xyce ranks | Check | Functional cells | Hard-top SPEF nets | Cap nodes | Resistors | Digital pin substitutions | PLLOUT rises | Startup frequency | Result |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Low start | 16 | Startup, 60 ns | 2020 | 261 | 1752 | 1657 | 260 | 3 | 46.270645 MHz | Pass |

Rank-count timing on the same generated 60 ns deck was 223.14 s at one Xyce
process, 132.59 s at four MPI ranks, 104.51 s at eight ranks, 90.09 s at 16
ranks, and 132.82 s at 32 hardware-thread ranks. This makes 16 ranks the best
tested setting for this distributed-RC diagnostic on the current host. The
diagnostic is useful topology evidence, but it is not a two-rail motion check
and not a full extracted hard-macro-top closed-loop transient.

The extracted-DCO companion diagnostic is:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-startup-diagnostic
```

It keeps the same final force-to-mid signoff digital-core netlist and
distributed hard-top SPEF RC, then replaces the behavioral DCO with filled DCO
RCX. The 50 ns low-start deck has 2020 functional mapped cells, skips 4138
physical-only cells, covers the same 261 hard-top SPEF nets, emits 1752
grounded capacitance nodes and 1657 resistors, substitutes 260 digital pins,
and includes 27097.841 fF of selected hard-top capacitance. The Xyce log reports
63443 total devices and 182651 unknowns.

| Case | Xyce ranks | Check | Functional cells | Skipped physical-only cells | Hard-top SPEF nets | Cap nodes | Resistors | Digital pin substitutions | PLLOUT rises | Startup frequency | Result |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Low start | 16 | Extracted DCO startup, 50 ns | 2020 | 4138 | 261 | 1752 | 1657 | 260 | 2 | 46.202763 MHz | Pass |

The measured PLLOUT period is 21.643727 ns after the 15 ns startup measurement
point. The first full Xyce/MPI16/KLU run completed in about 225.884 s, and the
promoted make target uses `--resume` for repeat validation. This is stronger
elaboration and startup evidence for the combined extracted-DCO plus hard-top RC
deck, but it is still not a two-rail motion/lock check and not full extracted
hard-macro-top closed-loop signoff.

The extracted-DCO first-motion companion targets are:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-low-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-high-diagnostic
```

They extend the same final signoff digital-core, BBPD RCX, DCO RCX, and
distributed hard-top SPEF RC deck through the first post-enable DLF update.
`DLF_En` releases at 85 ns and both motion checks measure 84..99 ns. The low
start moves upward from code 0 to code 2, and the high start moves downward from
code 255 to code 253, proving two-sided first closed-loop code motion in the
combined extracted-DCO plus hard-top RC deck.

| Case | Xyce ranks | Check | Functional cells | Skipped physical-only cells | Hard-top SPEF nets | Cap nodes | Resistors | Digital pin substitutions | Start code | End code | Response code | Startup frequency | Result |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Low start | 16 | Extracted DCO first motion, 100 ns | 2020 | 4138 | 261 | 1752 | 1657 | 260 | 0.0 | 2.0 | 2.0 | 46.150194 MHz | Pass |
| High start | 16 | Extracted DCO first motion, 100 ns | 2020 | 4138 | 261 | 1752 | 1657 | 260 | 255.0 | 253.0 | 253.0 | 50.278137 MHz | Pass |

The Xyce log reports the same 63443 total devices and 182651 unknowns as the
startup deck. The low-start 100 ns transient took 487.306 s Xyce elapsed time,
and high-start took 538.010 s. This is stronger than startup-only evidence, but
it is still a first-update diagnostic rather than rail-start acquisition, lock,
or PVT signoff.

The parallel EINVP hard-top extracted-DCO diagnostics are:

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
```

These replace the NAND-load DCO RCX deck and hard-top SPEF/SPICE with the
`IntegerPLL_DCO_EINVP` RCX deck and the signed-off
`IntegerPLL_HardMacroTop_EINVP` extracted views. The selected E hard-top nets
cover all 255 DCO thermometer interconnects, 261 SPEF nets, 1744 capacitance
nodes, 1627 resistors, 260 digital pin substitutions, and 25247.633 fF selected
capacitance. The Xyce logs report 65871 total devices and 184445 unknowns.

| Case | Xyce ranks | Check | Functional cells | Skipped physical-only cells | Hard-top SPEF nets | Cap nodes | Resistors | Digital pin substitutions | Start code | End code | Response code | Startup frequency | Tail frequency | Result |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Low start | 16 | EINVP extracted-DCO startup, 50 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 0.0 | 0.0 | 50.813495 MHz | - | Pass |
| Low start | 16 | EINVP early first motion, 90 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 2.0 | 2.0 | 50.809027 MHz | - | Pass |
| High start | 16 | EINVP early first motion, 90 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 255.0 | 243.019510 | 243.019510 | 67.502112 MHz | - | Pass |
| Mid start | 16 | EINVP hard-top-loaded extracted-DCO lock window, 220 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 128.0 | 125.0 | 128.0 | 58.324010 MHz | 58.591120 MHz | Pass |
| Mid start min RC | 16 | EINVP hard-top-loaded extracted-DCO min-SPEF lock window, 220 ns | 2020 | 4138 | 261 | 1668 | 1551 | 260 | 128.0 | 125.0 | 128.0 | 58.318588 MHz | 58.500163 MHz | Pass |
| Mid start max RC | 16 | EINVP hard-top-loaded extracted-DCO max-SPEF lock window, 220 ns | 2020 | 4138 | 261 | 1905 | 1798 | 260 | 128.0 | 125.0 | 128.0 | 58.336931 MHz | 58.549789 MHz | Pass |
| Low start | 16 | EINVP hard-top-loaded extracted-DCO rail progress, 360 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 62.0 | 62.0 | 51.881504 MHz | 53.728266 MHz | Pass |
| High start | 16 | EINVP hard-top-loaded extracted-DCO rail progress, 360 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 255.0 | 172.0 | 172.0 | 65.751529 MHz | 62.952232 MHz | Pass |
| Low start | 16 | EINVP hard-top-loaded extracted-DCO lock window, 900 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 122.0 | 128.0 | 55.376858 MHz | 58.485654 MHz | Pass |
| High start | 16 | EINVP hard-top-loaded extracted-DCO lock window, 760 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 255.0 | 132.0 | 126.0 | 62.186448 MHz | 58.804895 MHz | Pass |
| Mid start FF | 16 | EINVP hard-top-loaded extracted-DCO mid-code hold, 220 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 128.0 | 128.0 | 128.0 | 81.388343 MHz | 81.712756 MHz | Pass |
| Mid start SS | 16 | EINVP hard-top-loaded extracted-DCO mid-code hold, 200 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 128.0 | 128.0 | 128.0 | 38.570381 MHz | 38.846037 MHz | Pass |
| Mid start FF | 16 | EINVP hard-top-loaded extracted-DCO PVT lock window, 220 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 128.0 | 134.0 | 134.0 | 81.306357 MHz | 81.575035 MHz | Pass |
| Mid start SS | 16 | EINVP hard-top-loaded extracted-DCO PVT lock window, 240 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 128.0 | 126.0 | 128.0 | 38.594707 MHz | 38.821045 MHz | Pass |
| Low start FF | 16 | EINVP hard-top-loaded extracted-DCO PVT low-rail lock window, 700 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 122.0 | 128.0 | 76.646281 MHz | 81.480028 MHz | Pass |
| High start FF | 16 | EINVP hard-top-loaded extracted-DCO PVT high-rail lock window, 700 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 255.0 | 127.0 | 127.0 | 86.972748 MHz | 82.095815 MHz | Pass |
| Low start SS | 16 | EINVP hard-top-loaded extracted-DCO PVT low-rail lock window, 1400 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 0.0 | 122.0 | 128.0 | 37.073168 MHz | 38.769491 MHz | Pass |
| High start SS | 16 | EINVP hard-top-loaded extracted-DCO PVT high-rail lock window, 1400 ns | 2020 | 4138 | 261 | 1744 | 1627 | 260 | 255.0 | 127.0 | 127.0 | 40.786273 MHz | 39.009555 MHz | Pass |

The E first-motion checks use an early diagnostic enable timing
(`DLF_En=40 ns`, measurement window 39..89 ns) because the default enable-85
100 ns low-start probe did not leave enough active decision window for this E
DCO phase/startup condition. This is two-sided first-motion evidence for the
integrated E top. The mid-start extracted-DCO lock-window row uses the same
distributed-RC E hard-top deck and retargets `REF` to 29.286759 MHz, matching
the measured hard-top-loaded E DCO tail rather than the standalone E DCO code
128 target. The standalone-target diagnostic is intentionally not promoted:
it holds code 125..128 but measures 58.573518 MHz, 1.601361 MHz below the
standalone 60.174879 MHz target. The promoted loaded-target row holds code
125..128 in the 150..219 ns lock window with 0.017601 MHz frequency error.
Repeating that same near-lock deck with the E hard-top min/max SPEF views also
passes: min SPEF selects 23096.023 fF, holds code 125..128, and measures
58.500163 MHz with 0.073355 MHz error; max SPEF selects 27119.190 fF, holds
code 125..128, and measures 58.549789 MHz with 0.023730 MHz error.
The loaded-target progress rows use normal `DLF_En=85 ns`. Low start moves
code 0->62 over 84..359 ns and reaches code 42..62 in the 280..359 ns late
window; high start moves code 255->172 and reaches code 172..192 in the same
late window. This is two-sided rail-escape extracted-DCO progress evidence,
not PVT signoff. The low/high rail-start lock rows use the same loaded
reference and normal enable timing. Low start runs to 900 ns, reaches code
122..128 in the 760..899 ns tail window, and measures 58.485654 MHz with
0.087865 MHz target error. High start runs to 760 ns, reaches code 126..132 in
the 650..759 ns tail window, and measures 58.804895 MHz with 0.231377 MHz
target error. This is TT nominal two-sided extracted-DCO rail-start lock
evidence. The FF/SS midpoint hold rows use `DLF_KI=0` and `DLF_KP=0` to keep
the extracted loop at code 128 while applying FF or SS device models through
the filled BBPD RCX, filled `IntegerPLL_DCO_EINVP` RCX, and nominal
distributed hard-top SPEF RC. They calibrate hard-top-loaded code-128
frequencies for later PVT lock targets. The FF/SS PVT lock-window rows then
enable the normal loop gains (`DLF_KI=160`, `DLF_KP=8`) at those calibrated
references: FF stays in code 125..134 with 0.137721 MHz tail error, and SS
stays in code 126..128 with 0.024993 MHz tail error. This is near-lock
closed-loop PVT evidence through the FF/SS device models and nominal E hard-top
distributed RC. Extending the FF case from both rails to 700 ns also passes:
low start moves code 0->122, holds code 122..128 in the 580..699 ns tail
window, and measures 81.480028 MHz with 0.232728 MHz target error. High start
moves code 255->127, holds code 127..133 in the same tail window, and measures
82.095815 MHz with 0.383059 MHz target error. This is FF two-rail PVT
acquisition evidence. Extending the SS case from the low rail to 1400 ns also
passes: it moves code 0->122, holds code 122..128 in the 1160..1399 ns tail
window, and measures 38.769491 MHz with 0.076546 MHz target error. The SS
high-rail 1400 ns diagnostic also passes: it moves code 255->127, holds code
127..133 in the 1160..1399 ns tail window, and measures 39.009555 MHz with
0.163517 MHz target error. Together these rows close FF/SS two-rail
extracted-loop PVT lock evidence for the nominal E hard-top distributed-RC
view.

The calibrated EINVP hard-top behavioral-DCO lock-window diagnostics are:

```sh
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-low-diagnostic
make -C OpenPLL spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-high-diagnostic
```

These use the signed-off `IntegerPLL_HardMacroTop_EINVP` nominal SPEF as
lumped top-level capacitance, the final force-to-mid digital-core netlist, the
filled BBPD RCX deck, and a piecewise behavioral DCO fitted to the measured
`IntegerPLL_DCO_EINVP` five-point RCX table. They are calibrated hard-top loop
checks, separate from the mid-code extracted-DCO row and not rail-start
extracted-DCO signoff.

| Case | Xyce ranks | DCO model | Start code | End code | Response code | Lock observed codes | Tail frequency | Tail abs error | Result |
| --- | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| Low start | 16 | EINVP five-point behavioral | 0.0 | 122.0 | 128.0 | 121..128 | 59.936383 MHz | 0.238496 MHz | Pass |
| High start | 16 | EINVP five-point behavioral | 255.0 | 133.0 | 124.0 | 126..133 | 60.235253 MHz | 0.060373 MHz | Pass |

The promoted initial-phase sweep for that same mapped-loop deck is:

```sh
make -C OpenPLL spice-pll-mapped-loop-phase-sweep
```

It runs both rail-start cases at common initial DCO phases `0`, `0.25`, `0.5`,
and `0.75` cycles. The target now uses the same 180 ns window as the smoke
target and the refreshed sweep passes both rail starts at all four tested
phases:

| Initial DCO phase | Low-start response | High-start response | Result |
| ---: | ---: | ---: | --- |
| 0.0 cycles | 8.0 | 246.0 | Pass |
| 0.25 cycles | 8.0 | 247.0 | Pass |
| 0.5 cycles | 8.0 | 246.0 | Pass |
| 0.75 cycles | 8.0 | 247.0 | Pass |

This keeps the mapped-loop result in the right category: it is useful
electrical connectivity and first-correction polarity evidence across the
tested initial phases, but it is not full extracted PLL lock evidence.

`spice-pll-mapped-loop-progress-1us` extends the same full mapped digital core,
filled BBPD RCX macro, and behavioral filled-DCO model to 1 us with `DLF_KI=255`,
`DLF_KP=32`, phase-selected rail starts, and the MPI-enabled Xyce/KLU binary:

```sh
make -C OpenPLL spice-pll-mapped-loop-progress-1us
```

Measured 1 us mapped-loop progress:

| Case | Start code | End code | Response code | Integrator start/end | Start error | End error | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Low start | 0.0 | 9.0 | 9.0 | 0.00 / 1.75 | -3.505392 MHz | -3.267220 MHz | Pass, progress only |
| High start | 255.0 | 243.0 | 145.808033 | 255.00 / 251.25 | +2.587713 MHz | +2.448400 MHz | Pass, progress only |

This is not a lock result. It proves that the filled-BBPD/mapped-DLF loop keeps
responding beyond the first correction and reduces absolute frequency error from
both rails, but the final frequency error remains multiple MHz after 1 us. The
promoted MPI4/KLU run completed in 356.177 s for low start and 445.105 s for
high start, compared with 611.898 s and 751.432 s for the earlier serial Xyce
artifact with identical endpoint metrics. The current KP32 setting is therefore
too slow for short-window acquisition in this mapped SPICE deck even though MPI
makes the evidence less expensive to reproduce.

A non-promoted KP128 500 ns diagnostic confirms the proportional-path tradeoff.
Low start reaches response code 33 but ends back at code 0, and high start
reaches response code 157.999 but ends back at code 255. The integrator only
moves from 0.00 to 1.50 and from 255.00 to 254.25 over that window. Stronger P
therefore gives a larger visible transient correction, but by itself does not
solve slow held-code convergence from the rails.

The existing RTL already has a `DLF_FRAC_WIDTH` parameter, so a FRAC=6 candidate
was tested as an integral-gain scaling option without changing the exported
8-bit DCO code. The diagnostic commands are:

```sh
make -C OpenPLL digital-loop-gain-sweep-frac6
make -C OpenPLL pll-top-filled-dco-gain-sweep-frac6
make -C OpenPLL spice-pll-mapped-loop-frac6-progress-1us
make -C OpenPLL spice-pll-mapped-loop-frac6-high-phase-500ns
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu
make -C OpenPLL digital-loop-gain-sweep-frac6-acqboost-s2a3
make -C OpenPLL pll-top-filled-dco-gain-sweep-frac6-acqboost-s2a3
make -C OpenPLL spice-pll-mapped-loop-frac6-acqboost-s2a3-progress-1us
make -C OpenPLL spice-pll-mapped-loop-frac6-acqboost-s2a3-extracted-dco-progress-300ns-probe-mpi16-klu
make -C OpenPLL digital-loop-gain-sweep-frac5
make -C OpenPLL pll-top-filled-dco-gain-sweep-frac5
make -C OpenPLL spice-pll-mapped-loop-frac5-progress-1us
make -C OpenPLL spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu
make -C OpenPLL digital-loop-gain-sweep-frac4
make -C OpenPLL pll-top-filled-dco-gain-sweep-frac4
make -C OpenPLL spice-pll-mapped-loop-frac4-progress-500ns
```

Behavioral FRAC=6 results are strong: the ideal digital-loop sweep finds
`DLF_KI=255`, `DLF_KP=32` as the fastest row with 10.063 us worst-case lock and
one final code of error, while `DLF_KI=255`, `DLF_KP=4` reaches exact final
codes with 10.822 us worst-case lock. The filled-DCO top behavioral sweep finds
`DLF_KI=192`, `DLF_KP=8` as the best endpoint row, ending at code 129 from both
rails with 24.963 us worst-case lock and one final code of error; the faster
`DLF_KI=255`, `DLF_KP=32` row locks within 17.901 us but ends at codes 135 and
121.

Mapped-cell SPICE with the filled BBPD RCX macro is more phase/asymmetry
sensitive. The FRAC=6, `DLF_KI=255`, `DLF_KP=32` mapped behavioral-DCO run uses
889 synthesized Sky130 cells, MPI4 Xyce/KLU, and the same 1 us rail-start
window. Low start improves from code 0 to 20, with the integrator moving from
0.00 to 12.75 and frequency error improving from -3.505392 MHz to
-2.976122 MHz. High start now uses the phase 0.5 initial DCO state selected by
the 500 ns high-start phase sweep; it improves from code 255 to 233, with
response code 224.000870, integrator movement from 255.00 to 241.00, and
frequency error improving from +2.587713 MHz to +2.332306 MHz.

An optional same-direction acquisition boost has been added to the DLF and is
disabled by default (`DLF_ACQ_BOOST_SHIFT=0`). With FRAC=6,
`DLF_ACQ_BOOST_SHIFT=2`, and `DLF_ACQ_BOOST_AFTER=3`, the ideal digital-loop
sweep reduces worst-case lock from 10.063 us to 2.870 us for `DLF_KI=255`,
`DLF_KP=32`; the lowest-gain passing row in that boosted sweep is
`DLF_KI=128`, `DLF_KP=8` at 5.663 us. The filled-DCO top behavioral sweep
passes both rails for `DLF_KI=255`, `DLF_KP=32` with 5.598 us worst-case lock,
ending at codes 119 and 121. The boosted Sky130 mapped core synthesizes to 970
cells and improves the 1 us mapped behavioral-DCO SPICE row: low-start ends at
code 40 with integrator 40.75 and 46.828179717 MHz tail frequency, while
high-start ends at code 215 with integrator 223.00 and 52.127168500 MHz tail
frequency. A 300 ns postlayout-RCX DCO follow-up with MPI16/KLU confirms the
direction but not the behavioral-model acceleration: low-start moves from code
0 to 10 with integrator 2.75 and 46.200651370 MHz tail frequency, while
high-start moves from code 255 to 245 with integrator 253.00 and
53.168326147 MHz tail frequency. This is only a small improvement over the
non-boosted 300 ns extracted-DCO probe, so acquisition boost remains
non-promoted.

Shorter boost thresholds were also checked as diagnostics. With
`DLF_ACQ_BOOST_AFTER=1`, `DLF_KI=192`, and `DLF_KP=32`, the filled-DCO
top-level behavioral sweep passes, but the mapped behavioral-DCO SPICE probe
rail-collapses the high-start case to the low side before the measurement
window and fails. With `DLF_ACQ_BOOST_AFTER=2`, `DLF_KI=192`, and
`DLF_KP=32`, the mapped behavioral-DCO probe passes weakly, ending at 0->18
and 255->236 in 1 us. The 300 ns postlayout-RCX DCO follow-up is still weak:
low-start ends at code 12 with integrator 4.50 and 46.217968866 MHz tail
frequency, while high-start ends at code 245 with integrator 253.50 and
53.163603778 MHz tail frequency. This points away from pure digital gain
boosting and toward BBPD/update cadence or analog-loop timing as the rail-start
bottleneck.

The promoted mapped behavioral-DCO rail-start candidate adds three default-off
DLF controls: `DLF_PROP_RAIL_GUARD=1`, `DLF_ACQ_RAIL_BOOST=1`, and
`DLF_ACQ_FORCE_RAIL_CODE=127`. The force-to-mid setting deterministically walks
the integral state inward until the 8-bit DCO code reaches the mid-code
neighborhood, then returns control to the normal BBPD PI loop. The Sky130
configuration also keeps `DCO_CONTROL_REGISTERED=1`, so the binary and
thermometer DCO controls are sampled before they reach the DCO macro boundary.
The reproducible promoted commands are:

```sh
make -C OpenPLL digital-loop-gain-sweep-frac6-force127-s4a2
make -C OpenPLL pll-top-filled-dco-gain-sweep-frac6-force127-s4a2
make -C OpenPLL synth-frac6-force127-s4a2
make -C OpenPLL spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-progress-500ns-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu
make -C OpenPLL librelane-signoff-force127-s4a2
make -C OpenPLL check-librelane-signoff-force127-s4a2
make -C OpenPLL spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-motion-220ns-mpi16-klu
make -C OpenPLL spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-lock-820ns-mpi16-klu
```

The filled-DCO top behavioral sweep with
`DLF_FRAC_WIDTH=6`, `DLF_ACQ_BOOST_SHIFT=4`, `DLF_ACQ_BOOST_AFTER=2`, and
`DLF_ACQ_FORCE_RAIL_CODE=127` passes all 63 tested gain points from both rails.
The promoted nonzero-P row is `DLF_KI=160`, `DLF_KP=8`, ending at codes 128/127
with 2.010 us worst-case behavioral lock and 1-code worst final error. The
direct Yosys Sky130 mapped core for the registered-control configuration has
1307 cells and 13733.171200 square microns. The added area is dominated by the
255 registered thermometer outputs.

The companion LibreLane force-to-mid signoff run,
`librelane-signoff-force127-s4a2`, also passes
`check-librelane-signoff-force127-s4a2`. The final registered-control artifact
has 3164 standard cells, 30.0674% utilization, 67207 microns routed wire length,
13321 routed vias, 2.794 ns worst setup slack, 0.115 ns worst hold slack, zero
DRC/LVS/STA/power-grid violations, 3.431 mW reported total power, and 0.706 mV
worst IR drop.

The older 2 us mapped behavioral-DCO endpoint run is no longer promoted for the
registered-control configuration. A rerun with the binary `DCO_CODE` observer
showed that mapped binary bus transitions can create misleading low-code
samples even when the endpoint is near code 127, and the high-start deck hit the
1800 s timeout. A rerun with the thermometer observer is more faithful to the
DCO macro interface, but both rail-start decks hit the 2400 s timeout before
completing the 2 us transient. The target is therefore diagnostic only; the
promoted current closed-loop evidence comes from the extracted-DCO checks below.

The companion 500 ns extracted-DCO progress target uses the same force-to-mid
mapped core, the filled BBPD RCX macro, and the filled DCO RCX macro in the loop.
It runs Xyce/KLU with 16 MPI ranks per deck and two rail-start decks in
parallel. Low-start moves from code 0 to 102 with integrator code 0 to 100;
high-start moves from code 255 to 153 after dipping as low as code 129, with
integrator code 255 to 155. The measured tail frequencies over 119..499 ns are
47.499330 MHz for low-start and 51.553235 MHz for high-start, with 2.262788 MHz
and 1.791117 MHz absolute error from the 49.762118 MHz target. The elapsed times
were 1499.251 s and 1400.832 s.

The registered-control extracted-DCO lock-window target extends the same setup
to 820 ns and observes the registered thermometer bus. It uses
`check_mode=lock_window`, full-window DCO-code bounds 112..144 from 700..819 ns,
and a 0.8 MHz tail-frequency tolerance. Low-start passes with tail-window code
122..128, 49.350349 MHz tail frequency, and 0.411769 MHz absolute error.
High-start passes with tail-window code 127..133, 49.505000 MHz tail frequency,
and 0.257118 MHz absolute error. The runs used 16 Xyce/KLU MPI ranks per deck,
two rail-start decks in parallel, and elapsed times of 3431.210 s and
3410.386 s. This is the current strongest TT rail-start extracted-DCO
closed-loop evidence, though it is still a targeted 820 ns window rather than a
full PVT or multi-microsecond extracted PLL signoff.

The force-to-mid final-signoff-netlist extracted-DCO targets use the LibreLane
force127 final Verilog netlist, omit physical-only filler/decap/tap cells, and
keep the filled BBPD and DCO RCX macros in the loop. The SPICE deck contains
2020 functional mapped digital-core cells and skips 4138 physical-only cells.
The shorter 220 ns rail-start motion check passes: low-start moves code 0->22
with 46.417721 MHz tail frequency, and high-start moves code 255->222 with
52.724539 MHz tail frequency. The stronger 820 ns lock-window target then uses
Xyce/KLU with 16 MPI ranks per deck and two decks in parallel, checks the
700..819 ns tail against code bounds 112..144 and a 0.8 MHz frequency-error
limit, and passes both rails. Low-start ends at code 128 with tail-window code
122..128, 49.364473 MHz tail frequency, and 0.397645 MHz absolute error.
High-start ends at code 132 with tail-window code 126..132, 49.488494 MHz tail
frequency, and 0.273624 MHz absolute error. The Xyce logs report total elapsed
run times of 5135.0 s and 5328.51 s. This is the strongest current post-PnR
final-functional-netlist TT closed-loop lock-window evidence, though it is still
not full extracted PVT or multi-microsecond rail-start signoff.

That update-cadence hypothesis was tested with an optional
`DLF_UPDATE_ON_PLLOUT` mode. The default remains unchanged, but the diagnostic
mode clocks the DLF from `PLLOUT` and advances the integrator on a delayed
sampled divider-update pulse, while preserving the held proportional term. For
the Sky130 hard-top path this is a rebuilt digital-core macro variant, not a
runtime-selectable option on the shipped configured wrapper. With
FRAC=6 and no boost, the ideal digital-loop sweep passes both rails with
`DLF_KI=255`, `DLF_KP=32` at 10.074 us worst-case lock and 16-code final error;
the filled-DCO top behavioral sweep prefers `DLF_KI=192`, `DLF_KP=8`, ending at
codes 129/124 with 24.795 us worst-case lock. Combining PLLOUT-update mode with
`DLF_ACQ_BOOST_SHIFT=2`, `DLF_ACQ_BOOST_AFTER=2` gives a better top behavioral
candidate: `DLF_KI=192`, `DLF_KP=32` ends at 137/120 with 6.363 us worst-case
lock.

The mapped behavioral-DCO SPICE result for that fast+boost candidate is not
good enough to promote to extracted-DCO simulation. The synthesized diagnostic
core has 975 cells and 6434.921600 square microns. With `DLF_KI=192`,
`DLF_KP=32`, the 1 us mapped run ends low-start at code 0 after a transient
maximum of 15, with integrator 0.00->3.00 and 46.379830515 MHz tail frequency;
high-start improves to 255->217 with integrator 255.00->225.00 and
52.177702655 MHz tail frequency. A lower-gain `DLF_KI=128`, `DLF_KP=8` repeat
does not fix low-start: it ends 0->2 after a transient maximum of 126, while
high-start only reaches 238. Waveform inspection shows alternating low-start
BBPD decisions that repeatedly clamp the proportional output back to the low
rail. The fast-update mode is therefore useful evidence, but not yet a
rail-start solution.

The companion 500 ns FRAC=6 high-start phase sweep shows why this is still
diagnostic evidence rather than a promoted setting: phases 0 and 0.25 end near
code 243, phase 0.5 holds the best endpoint at code 241, and phase 0.75 snaps
back to code 255 after a transient response to code 134.001867. FRAC=6 is now a
stronger gain-tuning candidate than the default FRAC=8 for this phase-selected
mapped behavioral-DCO run, but it still needs all-phase robustness and extracted
DCO loop validation before promotion.

The extracted-DCO FRAC=6 260 ns trends now provide that first coupled check.
Compared with the default-FRAC extracted trends, low-start improves visible code
8 to code 9 and increases integrator movement from 0.25 to 1.75 DCO-code units;
high-start remains at visible code 246 but ends with one full code of integrator
movement instead of 0.25. This is useful extracted-loop gain evidence, not lock.
The 500 ns MPI16/KLU rail-start progress row strengthens that trajectory: low
start reaches code 15 with integrator 7.75, and high start reaches code 240 with
integrator 248.00. It is still far from target, with 46.243607848 MHz and
53.072273197 MHz tail frequencies, so longer-window acquisition remains open.
The MPI16/KLU mid-code lock-window row adds a complementary near-target check:
starting from code 128, it stays inside code 127..140 and measures a
49.676823500 MHz tail frequency against the 49.762117808 MHz target over the
139..219 ns window. A lower-P `KI=192`, `KP=8` diagnostic stays closer in code
at 131 but misses the tighter tail-frequency bound with 49.488441487 MHz,
supporting KP32 as the stronger extracted near-lock choice for now. That local
evidence does not replace rail-start acquisition. The enable-85 high-side companion
starts at code 160 and moves down to code 146 with 0.239153 MHz tail error over
299..379 ns, while the default-enable high-side probe still moves the wrong way
to code 169. This points to BBPD release phase/timing as a remaining condition:
the extracted loop has useful two-sided near-lock evidence, but not robust
rail-start lock.

Follow-up FRAC=5 and FRAC=4 probes bracket that result. In the filled-DCO top
behavioral sweep, FRAC=5 `DLF_KI=96`, `DLF_KP=8` has the cleanest endpoint
row, ending at code 129 from both rails in 24.963 us worst case; FRAC=5
`DLF_KI=192`, `DLF_KP=32` is faster at 12.042 us but ends at code 121 from both
rails. FRAC=4 `DLF_KI=192`, `DLF_KP=32` is faster again at 6.214 us worst case
but still ends at code 121 from both rails in the top model.

Mapped-cell SPICE does not promote either stronger setting. FRAC=4
`DLF_KI=192`, `DLF_KP=32` improves low-start to code 14 in 500 ns, but
high-start snaps back to code 255 after a transient response to code 230.471517.
FRAC=5 `DLF_KI=192`, `DLF_KP=32` needs a longer DLF clear window in the deck so
the high-start seed is captured deterministically. With that setup, the 500 ns
high-start case improves from code 255 to 235, but the 1 us two-rail run ends at
code 5 from low-start after a transient to 20.565868 and at code 239 from
high-start after a transient to 224.000000. These rows are useful negative
gain-tuning evidence: stronger integral scaling helps some transients, but
FRAC=6 remains the best mapped behavioral-DCO candidate so far because it holds
more low-start progress and a better high-start 1 us endpoint.

`spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu`
repeats the FRAC=5 `DLF_KI=192`, `DLF_KP=32`, `NDIV=2`,
clear-100 ns / enable-130 ns setup with the postlayout-RCX DCO and two
concurrent MPI16/KLU Xyce jobs. It passes the motion check cleanly, but it does
not improve the promoted FRAC=6 extracted-DCO evidence: low-start moves code 0
to 8 with 46.190967911 MHz tail frequency, and high-start moves code 255 to 244
with 53.231394237 MHz tail frequency over the 129..299 ns measurement window.
The tail errors remain 3.571150 MHz and 3.469276 MHz from the 49.762117808 MHz
target, so this is reproducible gain-scaling evidence rather than lock or
acquisition validation. The rows took 1080.527 s and 840.300 s elapsed; both
logs include a timing summary for 16 processors.

Longer 220 ns Xyce and ngspice diagnostic runs are still expensive. The default
serial `XYCE` binary reports `Serial` in `Xyce -capabilities`, but the
longer mapped-loop targets use the MPI-enabled build at
`$XYCE_MPI_ROOT/bin/Xyce` with `-linsolv KLU`: older promoted
targets use 4 ranks, while the FRAC=6 extracted-DCO MPI16 trend and lock-window
diagnostics use 16 ranks, including the enable-85 high-side lock-window row and
the force-to-mid extracted-DCO progress and 820 ns registered-control
lock-window rows, plus the EINVP hard-top-loaded mid-code extracted-DCO
lock-window row, FF/SS hard-top-loaded mid-code extracted-DCO PVT lock-window
rows, EINVP hard-top-loaded low/high extracted-DCO progress rows, the EINVP
hard-top-loaded low/high extracted-DCO lock-window rows, and calibrated EINVP
behavioral hard-top lock-window rows. The old
30 ns ngspice direct-clock `inc_mid` run with `KI=255`, `KP=4`, and a 90 s
wall-clock limit timed out after 90.191 s; the same bounded run with
`num_threads=4` also timed out after 90.191 s. The passing Xyce targets
therefore validate the DCO code update path, BBPD-to-DLF interface, a short
feedback-divider-included mapped-loop smoke, a final-signoff functional-netlist
mapped-loop smoke, a four-phase first-correction sweep, 1 us progress with a
behavioral DCO, the FRAC=6 force-to-mid 500 ns extracted-DCO rail-start progress
probe, and the FRAC=6 force-to-mid 820 ns registered-control extracted-DCO
lock-window probe. The
serial and MPI4-KLU extracted-DCO targets add startup and both-rail
first-correction evidence in the coupled mapped deck, but the extracted
closed-loop evidence is still targeted TT validation rather than full PVT
extracted PLL signoff.

## Synthesized DCO Decoder Results

The decoder check uses the mapped Sky130 netlist from `make synth` and extracts
the backward cone for selected thermometer taps. The refreshed current-RTL
artifacts were run after synthesis of the mapped digital core
and written under `build/spice_decoder_current`,
`build/spice_decoder_full_taps_current`, and
`build/spice_decoder_all_taps_current`. The full-tap target verifies all 255
`DCO_THERM` outputs at important adjacent and boundary codes; the all-code,
all-tap target verifies every 8-bit `DCO_CODE` value against every thermometer
tap with a batched ngspice DC sweep.

Command:

```sh
make -C OpenPLL spice-dco-decoder
```

All-code command:

```sh
make -C OpenPLL spice-dco-decoder-all
```

Full-tap boundary command:

```sh
make -C OpenPLL spice-dco-decoder-full-taps
```

Exhaustive all-code, all-tap command:

```sh
make -C OpenPLL spice-dco-decoder-all-taps
```

Measured sampled-tap operating-point cases:

| DCO code | Checked taps | Expected high taps | Measured high taps | Result |
| ---: | --- | ---: | ---: | --- |
| 0 | 0, 1, 2, 126, 127, 128, 253, 254 | 8 | 8 | Pass |
| 1 | 0, 1, 2, 126, 127, 128, 253, 254 | 7 | 7 | Pass |
| 2 | 0, 1, 2, 126, 127, 128, 253, 254 | 6 | 6 | Pass |
| 127 | 0, 1, 2, 126, 127, 128, 253, 254 | 4 | 4 | Pass |
| 128 | 0, 1, 2, 126, 127, 128, 253, 254 | 3 | 3 | Pass |
| 254 | 0, 1, 2, 126, 127, 128, 253, 254 | 1 | 1 | Pass |
| 255 | 0, 1, 2, 126, 127, 128, 253, 254 | 0 | 0 | Pass |

The extracted sampled decoder cone contains 47 Sky130 cells from the mapped
digital core. This validates the synthesized decoder polarity at
the low-end, midpoint, and high-end 8-bit code boundaries. The exhaustive
all-code/all-tap DC sweep below supersedes the older sampled-tap all-code run
for current-RTL coverage.

Measured full-tap operating-point cases:

| DCO code | Checked taps | Expected high taps | Measured high taps | Result |
| ---: | --- | ---: | ---: | --- |
| 0 | all 255 | 255 | 255 | Pass |
| 1 | all 255 | 254 | 254 | Pass |
| 2 | all 255 | 253 | 253 | Pass |
| 127 | all 255 | 128 | 128 | Pass |
| 128 | all 255 | 127 | 127 | Pass |
| 254 | all 255 | 1 | 1 | Pass |
| 255 | all 255 | 0 | 0 | Pass |

The extracted full-tap decoder cone contains 366 Sky130 cells from the mapped
digital core. This validates every DCO thermometer output at the
low-end, midpoint, and high-end 8-bit code boundaries. Its CSV has 8 rows: one
header plus one passing row for each checked code.

The exhaustive all-code, all-tap target uses a batched ngspice DC sweep of the
same 366-cell decoder cone. It validates all 256 `DCO_CODE` values against all
255 `DCO_THERM` outputs. Its CSV has 257 rows: one header plus one passing row
for each 8-bit code. The measured high-count sequence is 255, 254, ..., 1, 0,
with no per-tap errors recorded.

## Coverage

Validated so far:

- Sky130 transistor models and `sky130_fd_sc_hd` SPICE subcircuits load
  successfully in ngspice and Xyce for the tested decks.
- The DCO starts and oscillates in transient simulation.
- The 8-bit control path has working endpoint and midpoint configurations.
- The representative nonfilled tuning curve is monotonic for the tested top-level
  `DCO_CODE` values.
- The full 256-code nonfilled TT tuning curve is monotonic in transient SPICE
  simulation.
- The top-level DCO load polarity is validated: increasing `DCO_CODE` reduces
  the enabled load count. In the current filled RCX deck, frequency increases
  through code 224 but rolls off at the all-off endpoint.
- A synthesized Sky130 DCO decoder cone has SPICE operating-point validation
  for sampled thermometer taps at low-end, midpoint, and high-end 8-bit code
  boundaries.
- A synthesized Sky130 DCO decoder cone has all-255-tap SPICE operating-point
  validation at low-end, midpoint, and high-end 8-bit code boundaries.
- A synthesized Sky130 DCO decoder cone has all-code, all-255-tap SPICE DC
  sweep validation for every 8-bit `DCO_CODE` value.
- Endpoint DCO operation is validated across `tt`, `ff`, `ss`, `sf`, and
  `fs` corners.
- Full 256-code DCO operation is validated across `tt`, `ff`, `ss`, `sf`, and
  `fs`, with monotonic tuning in every corner.
- The BBPD produces the correct wider output pulse for reference-leads and
  feedback-leads cases.
- The current BBPD-decision-latch digital core has post-layout signoff artifacts,
  including GDS, SPEF,
  extracted LVS SPICE, Magic/KLayout DRC, and Netgen LVS, with zero
  route/DRC/LVS/timing/DRV violations reported by
  `make -C OpenPLL check-librelane-signoff`.
- The DCO macro has a filled, signoff-clean GDS/SPEF/LVS/DRC result and a Magic
  RCX transistor-level post-layout deck.
- A filled signoff DCO RCX five-point transient smoke run passes in Xyce at
  `DCO_CODE` 0, 64, 128, 192, and 255, measuring 46.257 MHz, 47.950 MHz,
  49.762 MHz, 51.618 MHz, and 52.350 MHz from printed `PLLOUT` crossings.
  The consolidated calibration check passes with a 6.093 MHz span and
  23.895 kHz/LSB average five-point step.
- A filled signoff DCO RCX TT 9-point characterization passes at `DCO_CODE` 0,
  32, 64, 96, 128, 160, 192, 224, and 255. It records positive gain from
  code 0 through code 224, a 52.565854 MHz peak at code 224, and a bounded
  0.216023 MHz high-code roll-off to 52.349831 MHz at code 255.
- A focused filled signoff DCO RCX high-code tail characterization passes at
  `DCO_CODE` 192, 208, 216, 224, 232, 240, 248, 250, 252, 254, and 255. It
  localizes the TT peak at code 240, measuring 53.003796 MHz, and records a
  0.653965 MHz roll-off to 52.349831 MHz at code 255.
- A pre-layout DCO load-style candidate comparison passes for the existing
  NAND load and a tri-state `einvp` load candidate. In the high-code tail,
  `einvp` is monotonic from code 192 to 255 and spans 44.101 MHz, compared with
  9.756 MHz for the NAND load. The `einvp` representative 5-point sweep is
  also monotonic and spans 99.974-210.869 MHz. This is not post-layout evidence.
- A pre-layout 9-stage `einvp` DCO range check passes at TT for codes
  0/64/128/192/255, measuring
  102.518/119.260/142.355/176.267/229.054 MHz. This supports the
  100 MHz-order range target before layout, but the fast candidate is still not
  post-layout RCX evidence.
- A separate filled signoff `IntegerPLL_DCO_EINVP` candidate now passes
  LibreLane signoff and Magic RCX post-layout SPICE checks. TT filled-RCX smoke
  at codes 0, 128, and 255 measures 50.955942 MHz, 60.174879 MHz, and
  72.479371 MHz. The consolidated five-point calibration adds code 64 at
  55.205750 MHz and code 192 at 66.031451 MHz, giving a monotonic
  50.955942-72.479371 MHz calibration span across codes 0/64/128/192/255.
  Focused high-tail TT filled-RCX checks at codes 192, 224, 240, 248, and 255
  measure 66.031451 MHz, 69.378381 MHz, 70.929758 MHz, 71.718618 MHz, and
  72.479371 MHz, so the candidate high tail is monotonic in the promoted sparse
  post-layout check. The same candidate also passes four-rank Xyce endpoint
  smoke at the other PVT corners: 70.251790-99.895518 MHz at FF,
  51.688142-70.763937 MHz at FS, 44.076396-64.579620 MHz at SF, and
  33.875977-47.497548 MHz at SS.
- The current `IntegerPLL_HardMacroTop_EINVP` hard-macro top instantiates the
  `IntegerPLL_DCO_EINVP_COARSE` candidate and passes full LibreLane signoff.
  The extracted-interface check verifies 73 top ports, the
  `IntegerPLL_DCO_EINVP_COARSE` oscillator subcircuit, 255 DCO thermometer
  connections, 47 coarse thermometer connections, 5 antenna-repaired DCO
  thermometer nets, 374 nominal SPEF nets, 10082 capacitance entries, 1670
  resistance entries, and a passing Xyce `-norun` syntax/topology probe.
- The previous low-frequency EINVP hard-top artifact also passes MPI16/KLU
  distributed-RC extracted-loop diagnostics using the final force-to-mid
  digital-core netlist, filled BBPD RCX, `IntegerPLL_DCO_EINVP` RCX, and the
  older `IntegerPLL_HardMacroTop_EINVP` nominal SPEF. Those historical rows
  cover 261 hard-top SPEF nets, 1744 capacitance nodes, 1627 resistors, 25247.633 fF
  selected capacitance, startup at 50.813495 MHz, low first motion 0->2, and
  high first motion 255->243.019510. A hard-top-loaded mid-code extracted-DCO
  lock-window diagnostic also passes with code 125..128, 58.591120 MHz tail
  frequency, and 0.017601 MHz target error. FF/SS mid-code PVT lock-window rows
  also pass at calibrated references, holding code 125..134 at FF and 126..128
  at SS with 0.137721 MHz and 0.024993 MHz tail error. Normal-enable extracted-DCO
  progress rows at the same loaded target move low start 0->62 and high start
  255->172 by 360 ns, measuring 53.728266 MHz and 62.952232 MHz respectively
  in the late tail window. With the measured
  five-point E RCX table used as a calibrated behavioral DCO, the same
  signed-off E hard-top path also passes low/high lock-window diagnostics:
  low-start moves 0->122 with response 128 and 0.238496 MHz tail error, while
  high-start moves 255->133 with response 124 and 0.060373 MHz tail error.
- A filled signoff DCO RCX TT local-gain transient smoke run passes in
  MPI-enabled Xyce at `DCO_CODE` 120, 128, and 136, measuring 49.558458 MHz,
  49.771679 MHz, and 49.977051 MHz. The consolidated local-gain check passes
  with a 0.026162 MHz/LSB average step around code 128.
- Filled signoff DCO RCX PVT endpoint smoke passes in Xyce at `ff`, `fs`,
  `sf`, and `ss`. Endpoint ranges are 63.875-72.318 MHz at FF,
  46.796-52.659 MHz at FS, 40.092-46.062 MHz at SF, and 30.704-34.328 MHz
  at SS. The FS/SF/SS endpoints use four MPI ranks.
- Bounded filled-DCO RCX endpoint diagnostics in ngspice are reproducible and
  produce CSV/log timeout evidence; `num_threads=4` does not make the filled
  ngspice transient practical in the recorded validation environment.
- A reduced no-fill DCO RCX deck passes a three-point post-layout transient
  smoke sweep at codes 0, 128, and 255.
- The BBPD macro has a filled, signoff-clean GDS/SPEF/LVS/DRC result and its
  filled RCX deck passes post-layout transient polarity validation.
- The filled BBPD RCX deck passes the same post-layout transient polarity
  validation across `tt`, `ff`, `ss`, `sf`, and `fs`.
- The filled BBPD RCX deck has a TT small-offset dead-zone sweep from 0 ps to
  1 ns. The current layout shows +13.464 ps of zero-offset `UP-DN` skew,
  reference-leading polarity correct down to 1 ps, and feedback-leading polarity
  correct from 20 ps upward.
- The filled BBPD RCX deck has all-corner small-offset dead-zone sweeps from
  0 ps to 1 ns. The worst sampled zero-offset skew is +26.404 ps at `sf`, and
  the worst sampled feedback-leading threshold is 50 ps at `sf` and `ss`.
- A PLL-level SPICE acquisition harness, using transistor-level Sky130 BBPD
  cells and a post-layout-measured behavioral DCO model, acquires from both
  low-code and high-code starting points.
- The PLL-level harness also passes a TT filled-DCO calibrated target fitted to
  filled RCX measurements at codes 0, 64, 128, 192, and 255.
- The sampled-update filled-DCO harness has reset-fixed diagnostic coverage,
  but the default `DLF_STEP=2.5` LSB/update case no longer passes from both
  rails and is not promoted as validation evidence.
- A diagnostic sampled-loop SPICE gain sweep covers 9 reset-fixed
  `DLF_STEP`/sample-delay combinations with independent ngspice jobs. No tested
  combination passes both low-start and high-start acquisition.
- A diagnostic sampled-loop PI sweep covers 16 reset-fixed
  `DLF_STEP`/`DLF_PROP_LSB`/sample-delay combinations. Five combinations pass
  both rails, with the best tested row using `DLF_STEP=3.5`,
  `DLF_PROP_LSB=4`, and 0 ps sample delay.
- Filled post-layout BBPD in-loop diagnostics now include a passing resolved
  sampled Xyce lock probe using the filled BBPD RCX deck, the filled-DCO
  five-point behavioral calibration, `DLF_STEP=17.5`, `DLF_PROP_LSB=4`, 150 ps
  sample delay, and initial DCO phase 0.25 cycles. The same filled-BBPD path is
  still not a full extracted PLL transient; ngspice times out on the 18 us
  acquisition deck and the resolved 4 us continuous Xyce sweep with `DTMAX=1 ns`
  does not find a both-rail passing setting.
- The same PLL-level acquisition harness passes low-start and high-start cases
  across `tt`, `ff`, `ss`, `sf`, and `fs`, using measured all-code DCO PVT
  spans and per-corner references for target code 128.
- The RTL digital loop filter has a gain-sweep acquisition check using real
  `DLF_KI` and `DLF_KP` inputs. With corrected nanosecond timing and a
  registered ideal sign detector, `DLF_KI=64`, `DLF_KP=0` is the lowest-gain
  passing point but takes 150.308 us worst-case. After rescaling the
  proportional path, `DLF_KI=255`, `DLF_KP=2` is the exact-code acquisition
  point at 37.627 us worst-case in the ideal detector bench. `DLF_KI=255`,
  `DLF_KP=32` is a stronger-P filled-DCO candidate: it leaves at most one code
  of final error in the ideal detector bench and stays within eight final codes
  in the filled-DCO top-level behavioral bench.
- A top-level behavioral PLL acquisition check passes with the behavioral DCO
  and two-flop delayed-reset BBPD model: `DLF_KI=255`, `DLF_KP=4`,
  `MMDCLKDIV_RATIO=8`, and `REF=12.742100 MHz` acquire from code 0 to 127 and
  from code 255 to 128 toward target code 128.
- A filled-DCO calibrated top-level behavioral gain sweep passes nine of ten
  `DLF_KI`/`DLF_KP` settings. The promoted `pll-top-filled-dco-acq` target now
  uses `DLF_KI=255`, `DLF_KP=32`, which is the fastest passing row in the
  current sweep and finishes within eight codes from both rails. The
  `DLF_KI=255`, `DLF_KP=0` row reaches the target transiently but fails the
  filled-DCO phase-model endpoint check.
- The synthesized Sky130 DLF proportional DCO-code cone has a static
  transistor-level SPICE check: 109 mapped cells pass hold, increase, and
  decrease cases for stronger-P `DLF_KI=255`, `DLF_KP=16` and
  `DLF_KI=255`, `DLF_KP=32` candidates.
- The synthesized Sky130 DLF sequential DCO-code update cone has a transient
  Xyce check: the current 330-cell KP32 cone passes increase, decrease,
  UP-then-`2'b11`, and DN-then-`2'b11` reset-overlap response checks. A heavier
  full mapped-core 906-cell Xyce check also passes the KP32 UP/DN
  reset-overlap cases, and a final-signoff-netlist 540-cell DLF cone passes the
  same four KP32 directional update cases in compressed 24 ns Xyce runs:
  without extra interconnect loading, with 582 nominal SPEF lumped
  capacitances totaling 2678.819 fF, and with distributed nominal SPEF
  resistance plus 3373 grounded capacitance nodes.
  Filled-BBPD-RCX to mapped-DLF Xyce integration checks pass KP32 REF-leading
  and feedback-leading cases for the synthesized cone, the full 906-cell mapped
  digital core, and the final 540-cell DLF cone with distributed SPEF RC.
- `make -C OpenPLL validate-sky130-pll-artifacts` passed 69 promoted evidence
  groups in the v1 artifact set and wrote consolidated CSV/JSON under
  `build/sky130_pll_validation/`. In this fast-path development tree it
  intentionally reports stale physical/SPICE artifacts until regenerated. The
  gate covers digital-core, DCO, and BBPD
  signoff metrics; the separate `IntegerPLL_DCO_EINVP` candidate signoff;
  Sky130 structural top compile/control smoke; signed-off
  macro view/interface assembly; routed hard-macro top integration through
  OpenROAD detailed routing; full hard-macro top signoff with GDS streamout,
  min/nom/max SPEF, extracted SPICE, DRC, XOR, and LVS checks; an extracted
  hard-macro-top SPICE interface and Xyce `-norun` syntax/topology probe;
  parallel `IntegerPLL_HardMacroTop_EINVP` signoff and extracted-SPICE
  interface checks; parallel EINVP hard-top distributed-RC extracted-DCO
  startup, early low/high first-motion, hard-top-loaded mid-code lock-window
  across nominal/min/max E hard-top SPEF,
  FF/SS hard-top-loaded mid-code hold calibration and lock-window diagnostics,
  FF/SS low/high rail PVT lock-window diagnostics, low/high rail-progress, and
  low/high rail-start lock-window diagnostics;
  the Xyce C-interface mixed-signal gain sweep with filled-BBPD RCX; the
  `objective_deliverable_evidence` row tying the architecture markdown, Sky130
  hard-top implementation, 8-bit control resolution, frequency range, and
  extracted lock-window evidence together;
  parallel EINVP hard-top calibrated
  behavioral-DCO low/high lock-window diagnostics;
  all-code DCO and decoder SPICE; filled-DCO
  five-point RCX calibration, TT 9-point RCX characterization with the bounded
  high-code roll-off recorded, focused TT high-code tail RCX characterization,
  separate `einvp` candidate TT filled-RCX smoke/mid-code/five-point
  calibration/high-tail post-layout checks, separate `einvp` candidate
  FF/FS/SF/SS endpoint smoke, TT local-gain RCX smoke, and FF/FS/SF/SS endpoint
  smoke;
  filled-BBPD PVT/dead-zone SPICE; PLL-loop surrogate acquisition; the
  filled-BBPD sampled Xyce lock probe; RTL gain tuning; stronger-P DLF
  transistor-level SPICE including the
  final-netlist cone; the mapped-core filled-BBPD loop smoke; the mapped-core
  filled-BBPD proportional-gain sweep; the mapped-core filled-BBPD four-phase
  first-correction sweep; the mapped-core filled-BBPD MPI4-KLU 1 us progress
  probe; the FRAC=6 force-to-mid 820 ns extracted-DCO lock-window probe; the
  serial and MPI4-KLU extracted-DCO startup smokes; the serial and MPI4-KLU
  extracted-DCO first-correction smokes;
  the MPI4-KLU low/high extracted-DCO integrator trends;
  the MPI16-KLU FRAC=6 low/high extracted-DCO integrator trends;
  the MPI16-KLU FRAC=6 500 ns rail-start extracted-DCO progress check;
  the MPI16-KLU FRAC=6 force-to-mid 820 ns rail-start extracted-DCO
  lock-window check;
  the force-to-mid final-signoff-netlist 220 ns extracted-DCO motion check;
  the force-to-mid final-signoff-netlist 820 ns extracted-DCO lock-window check;
  the MPI16-KLU FRAC=6 mid-code extracted-DCO lock-window check;
  the MPI16-KLU FRAC=6 enable-85 high-side extracted-DCO lock-window check;
  the MPI4-KLU mid-code extracted-DCO proportional response; the MPI4-KLU
  mid-code KP0 extracted-DCO hold contrast; the MPI4-KLU mid-code extracted-DCO
  measured-frequency contrast; the final-signoff functional-netlist
  filled-BBPD loop smoke; a force-to-mid final-signoff-netlist mapped-loop
  smoke with 27097.842 fF of lumped nominal hard-top SPEF capacitance on 261
  loop/inter-macro nets, including all DCO thermometer interconnects; and
  hard-top distributed-RC extracted-DCO startup and low/high first-motion
  diagnostics. The signoff
  checks also reject final metrics files older than their RTL/config/SDC sources,
  so stale physical artifacts do not satisfy the promoted gate.

Not yet complete:

- Full coarse-DCO RCX tuning-curve and PVT transient coverage. The current
  `IntegerPLL_DCO_EINVP_COARSE` evidence includes clean standalone signoff/RCX,
  clean hardtop signoff/SPICE-interface checks, and post-layout TT endpoint
  plus near-target probes for the 100, 250, 300, and 400 MHz targets. It still
  needs broader all-band PVT DCO coverage and full extracted-DCO-in-loop
  lock/acquisition evidence before the 25 MHz-reference multiplier targets can be
  treated as final PLL signoff.
- Full closed-loop transistor-level transient SPICE. Current passing DLF
  transient evidence covers the reduced DCO-code update cone, a short full-core
  reset-overlap update check, and final-signoff-netlist DLF cones with no extra
  interconnect loading, lumped nominal SPEF capacitance, and distributed
  nominal SPEF RC. Filled-BBPD-RCX to mapped-DLF integration also passes through
  the reduced cone and all mapped digital-core cells. A short
  feedback-divider-included mapped-loop smoke, a final-signoff functional-netlist
  mapped-loop smoke with physical-only cells omitted, a force-to-mid
  final-signoff-netlist mapped-loop smoke with lumped hard-top SPEF loop-net
  capacitance, behavioral-DCO and extracted-DCO hard-top distributed-RC startup
  diagnostics, low/high hard-top distributed-RC extracted-DCO first-motion
  diagnostics for both NAND and EINVP hard-top paths, calibrated behavioral-DCO
  E hard-top low/high lock-window diagnostics, a hard-top-loaded mid-code E
  extracted-DCO lock-window diagnostic, FF/SS low/high rail E extracted-DCO PVT
  lock-window diagnostic, hard-top-loaded low/high E extracted-DCO progress
  diagnostics, hard-top-loaded low/high E extracted-DCO rail-start lock-window
  diagnostics, a four-phase first-correction
  sweep, an MPI4-KLU 1 us progress probe, and a FRAC=6
  force-to-mid behavioral-DCO lock probe remains diagnostic for the
  registered-control RTL because the 2 us reruns timed out. A FRAC=6
  force-to-mid 500 ns extracted-DCO progress probe moves both rails strongly,
  from 0->102 and 255->153, and the registered-control 820 ns extracted-DCO
  lock-window probe keeps both rail-start tails inside code 112..144 with less
  than 0.42 MHz TT frequency error. A force-to-mid final-signoff-netlist
  extracted-DCO 820 ns lock-window check also keeps both rail-start tails inside
  code 112..144 with less than 0.40 MHz TT frequency error. The
  extracted-DCO startup, both-rail first-correction smokes, low/high
  integrator-trend probes, a 500 ns FRAC=6 rail-start progress probe, and FRAC=6
  mid-code, enable-85 high-side, and force-to-mid rail-start lock-window checks
  now pass in the coupled mapped deck, while full extracted PVT signoff and
  multi-microsecond rail-start lock remain future work.
- BBPD reset-delay optimization and denser metastability characterization around
  the measured small-offset transition windows.
- Top-level extracted closed-loop transient using the hard-macro signoff SPICE
  and SPEF views. Current top-level hard-macro physical signoff covers GDS
  streamout, DRC, XOR, RCX/SPEF, extracted SPICE, LVS, macro-interface
  connectivity through the extracted wrapper, and an Xyce `-norun`
  syntax/topology probe. The hard-top-SPEF mapped-loop smoke adds lumped
  nominal top-level loop-net capacitance, and the promoted distributed-RC
  diagnostics elaborate selected hard-top loop/inter-macro RC nets with
  behavioral and extracted DCO decks through startup and low/high first-motion
  rows, including the parallel EINVP hard-top path. The E hard-top path also
  has a hard-top-loaded mid-code extracted-DCO lock-window row, low/high
  extracted-DCO progress rows, hard-top-loaded low/high extracted-DCO
  rail-start lock-window rows, FF/SS hard-top-loaded mid-code extracted-DCO
  lock-window rows, and calibrated behavioral-DCO low/high lock-window rows with
  lumped top SPEF capacitance, plus FF/SS low/high rail PVT extracted-DCO
  rail-start lock-window rows.
- Full closed-loop transistor-level or post-layout PLL validation.
- Extracted phase-domain loop stability and jitter optimization for final
  `DLF_KI` / `DLF_KP` settings.
- Single-fixed-reference closed-loop PVT lock validation.
