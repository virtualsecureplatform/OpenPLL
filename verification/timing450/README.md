# 450 MHz timing candidate

This directory implements the timing repair plan as an isolated candidate.
Selected `rtl/` is promoted only after functional, timing and physical
qualification. The target remains 450 MHz; the approved shared PLL supply
ceiling is 1.95 V, recorded in `verification/engineering.json`.

## Changes

- Register the divider configuration and decode its terminal count directly.
  Preserve three equivalent reload-control registers for separate local load
  banks. Divider output phase and live-ratio behavior are formally compared
  against `reference_mmd.v`, the previously verified Boolean implementation.
- Decode the synchronized Gray counter with a balanced XOR prefix and register
  the result on REFCLK. Both measurement endpoints use the same delayed count.
  Capture scan elapsed edges at the existing window boundary and rank the
  captured result on the following REFCLK edge. Five settling cycles account
  for the additional receiver latency.
- Isolate the retimer Q into internal-clock and signal/output branches. Isolate
  local reset roots, build CTS on the internal branch, and use stronger retimer
  and reload-control flops. Keep PLL-to-FINE tracking paths timed.
- Apply endpoint-specific first-stage CDC exceptions and explicit max/min
  bundled-data bounds. The pinned OpenSTA supports `-ignore_clock_latency`;
  source FF cells, rather than internal Q pins, define valid launch points.
- Register handoff busy state and capture the synchronized pending request
  whenever the destination is idle. The idle-state invariant makes this
  equivalent to qualified-request capture and removes acknowledge's XOR
  from the pending-request mux control. Decode acknowledgement independently
  of capture priority: capture starts only with a zero remaining count, so it
  cannot coincide with the final-count acknowledgement. `make -f
  verification/timing450/Makefile handoff` proves the destination state and
  busy invariant for application delays of one through four cycles and
  checks that the source-domain logic is identical.
- Give aliased output ports separate buffered nets so detailed routing connects
  every exported port. For HS, place the retimer isolation buffers near the
  source and delay only BBPD data branches, keeping pulse-clock sinks timed.
- Repair against routing estimates before detailed routing. An optional
  extracted repair preserves the initial route and uses its maximum-RC SPEF,
  followed by complete rerouting and fresh extraction. HS extracted repair uses
  all nine supplied cell/RC combinations, strengthens reset release paths,
  and preserves that repair through routing without running another optimizer
  against routing estimates. This stage retains `extracted_repaired.odb/.v`.

## Reproduce

Run commands from the repository root inside the pinned release container:

```sh
apptainer shell --bind "$PWD:/work/OpenPLL" --pwd /work/OpenPLL \
  build/apptainer/openpll-release-modern.sif
make -f verification/timing450/Makefile prepare synth
make -f verification/timing450/Makefile rtl divider mapping
make -f verification/timing450/Makefile place cts pdn route extract report
python3 verification/timing450/run.py --stage route --repair-extracted
python3 verification/timing450/run.py --stage route --repair-ports
make -f verification/timing450/Makefile extract report physical gate signoff klayout qualification
```

For HS, install the private overlay and use the same flow:

```sh
make -f verification/timing450/Makefile hs-install
make -f verification/timing450/Makefile LIBRARY=hs \
  PDK_ROOT=/work/OpenPLL/build/timing450/pdk prepare synth rtl divider mapping place cts pdn route extract report
python3 verification/timing450/run.py --library hs --pdk-root /work/OpenPLL/build/timing450/pdk \
  --stage route --repair-ports
make -f verification/timing450/Makefile LIBRARY=hs \
  PDK_ROOT=/work/OpenPLL/build/timing450/pdk extract report
python3 verification/timing450/run.py --library hs --pdk-root /work/OpenPLL/build/timing450/pdk \
  --stage route --repair-critical
make -f verification/timing450/Makefile LIBRARY=hs \
  PDK_ROOT=/work/OpenPLL/build/timing450/pdk extract report physical gate signoff klayout qualification
python3 verification/timing450/run.py --library hs --pdk-root /work/OpenPLL/build/timing450/pdk \
  --stage route --repair-extracted
make -f verification/timing450/Makefile LIBRARY=hs \
  PDK_ROOT=/work/OpenPLL/build/timing450/pdk extract report physical gate signoff klayout qualification
```

`install_hs.py` pins the HS source, official Liberty generator and Open PDKs
builder. It copies technology views into the private overlay, links the
unchanged baseline libraries and installs HS there. A byte-identical nominal
technology LEF alias avoids OpenROAD's library-name collision and preserves
the HS `unit` placement site. Source revisions and installed-view hashes are
recorded in `build/timing450/hs_library_manifest.json`. Installed private
simulation views repair malformed declarations and missing supply connections;
`hs_sim_helpers.v` maps missing legacy helper names to the shipped HS UDPs.
The tie-cell SPICE view uses the physical poly-resistor model in place of its
undefined `short` primitive. Original views and adaptation hashes remain in
`hs_original_views` and `hs_view_adaptations.json`; Liberty and geometry are
unchanged by these adapters.

Artifacts are under `build/timing450/{hd,hs}`. RTL snapshots and source hashes
identify the candidate, and regression executables remain within that
candidate's directory. Formal comparison excludes generated cell internals
and redundant thermometer-decoder helpers; every top-level port remains
compared. Physical proof compares the proven mapped netlist against the routed netlist,
with explicit aliases for the original FF Q pins and every top-level port.
It rejects missing original state instances and excludes unstable compressed
internal bus aliases. Gate regression reuses the independent oscillator model
and public-interface assertions at two phases; it has no SDF delays.

For handoff control transformations, `handoff-control` extracts the six original
control registers and their complete combinational input cones from both mapped
and routed netlists. It checks the clock/reset origins and permits only the
synchronized request as an external state input, then proves all six state bits
with reset-initialized unbounded induction. Its negative check corrupts the
acknowledgement input and requires a counterexample. `physical-composed` combines
this proof with the full netlist comparison: only unresolved comparisons for
those verified control registers may be covered, and all proof dependencies
must match the current netlists and verification code by hash.

The closure optimizer also preserves each endpoint's maximum-delay margin in
every supplied corner. Previously passing endpoints must retain at least
0.10 ns; failing endpoints must not regress. `test-closure` runs the endpoint
margin and control-cone guard regressions alongside the existing closure tests.

The receiver-reset exception ends only at the two tracking synchronizer reset
pins. The flow validates their shared clock/reset and direct stage connection.
Functional PLL-to-BBPD recovery remains timed. Repair stages preserve their
previous routed databases and timing reports before changing the candidate.
The diagnostic HS critical repair strengthens ratio, terminal and counter FFs and weak cells
on reported PLL paths; slow setup and fast hold corners guide repair together. An optional
`--repair-recovery` stage strengthens reset launch flops, weak reset-path gates
and reset input buffers using the current extracted slow-corner report. Both
measured repair stages reject reports for a different routed database.

Report another operating mode without changing the physical candidate:

```sh
python3 verification/timing450/run.py --stage report --mode-mhz 400
```

The five report modes are 100, 250, 300, 400 and 450 MHz. Reports use propagated
clocks and fresh min/nom/max extraction, with unchanged 0.5 ns interface delays
and 0.15 ns uncertainty. Timing gates require 0.10 ns setup/recovery margin,
0.05 ns hold/removal margin and no electrical or pulse-width violations.

## Qualification boundary

The supplied diagnostic libraries are TT/1.8 V/25 C, SS/1.6 V/100 C and
FF/1.95 V/-40 C. Both HD and HS provide an exact model for only one of the
required 45 corner/voltage/temperature points. `qualification.py` inventories
all available libraries and records missing points rather than extrapolating
qualification. The full release requires 225 mode/PVT combinations, whole-PLL
analog qualification at the approved supply range, characterized interface
loads and pulse widths, CDC resolution/bundle-skew evidence and independent
physical signoff. Diagnostic assessment files always retain
`release_qualified: false` and `selected: false`.

`signoff.py` streams this candidate's powered DEF with its own standard-cell
GDS, audits placement/power/antenna, runs independent full-style Magic DRC,
extracts transistor connectivity and compares against the powered schematic
with Netgen. The `klayout` target runs `verify_klayout.py` on that candidate's
GDS using the pinned KLayout executable and its installed PDK decks. It checks
all FEOL/BEOL/off-grid/floating-metal/seal rule groups with SRAM exclusion
disabled, then the separate global minimum clear-area density deck. It rejects
missing/stale GDS or database evidence, empty geometry, incomplete reports
and absent/nonfinite density ratios, and records the exact commands and input
hashes. These global density ratios do not establish complete windowed
minimum/maximum density qualification. Density/EM/IR remain separate release
gates; results from historical geometry cannot qualify this candidate.

The ongoing canonical analog calibration and historical full KLayout DRC
remain separate campaigns. Neither baseline PDK contents nor `scripts/*.py`
are changed by this candidate flow, preserving their live provenance.

## Verified checkpoint, 2026-10-05

The historical HS extracted-repair checkpoint passes physical equivalence (916/916),
both gate phases, zero router/Magic DRC violations, and unique transistor LVS.
All 76,824 supply pins are connected. All reported 450 MHz hold/removal/bundle
minima exceed 0.05 ns; the worst is +0.063846 ns.

Timing remains open. SS/max-RC 450 MHz setup is -0.718819 ns and recovery
-0.418278 ns; FINE setup is +0.488707 ns. At 400 MHz, setup is -0.441041 ns
and recovery -0.140500 ns. Electrical violations and 22 antenna net / 24 pin
violations remain. The previous sizing-only route worsened setup to
-1.868308 ns and is preserved under `hs/initial_route`; the earlier HS route
is preserved under `hs/before_critical`. No geometry is selected for release.
Detailed evidence and remaining gates are in `verification/IMPLEMENTATION.md`
and the candidate assessment JSON files.

The historical top-level closure iteration 007 reports: worst 450 MHz setup
−0.631297 ns, recovery −0.633541 ns, hold +0.041910 ns, and 82 router DRC
violations. It fails timing and DRC. The subsequent top-level iteration 009 ECO passes all
916 formal comparisons and both gate phases. The nested handoff-candidate
experiments below supersede these historical timing results.

## Targeted supplied-model closure

Use the HS-only closure operation on a freshly extracted, reported route:

```sh
make -f verification/timing450/Makefile LIBRARY=hs \
  PDK_ROOT=/work/OpenPLL/build/timing450/pdk closure
```

Each operation preserves its inputs and ECOs in `hs/closure/iteration_NNN`,
including source/model hashes, per-corner Liberty copies, a change journal,
and fresh extracted output reports. The corner copies change only the library
name so all nine cell/RC combinations have distinct OpenSTA assignments.
Sizing and delay reduction accept only corner-checked timing improvements.
Compatible FF sizing considers smaller and larger strengths, since intrinsic
delay can favor smaller cells after fanout splitting. Trials check receive
setup/recovery arcs and launched output paths together, retaining the global
max/min guards.
The flow records net connections, master names, positions and orientations
before an ECO. After legal placement, it clears wires whose endpoints changed
and retains other wires as mutable detailed-routing input. Each operation
records the cleared nets and still requires fresh extraction and final checks.
Detailed routing is bounded to 32 iterations; a nonzero final DRC count fails
qualification and requires another measured repair.
Clock roots, pulse guards, direct receiver links and exported signal branches
are protected. Reset distribution uses local parallel banks without changing
reset gating or register latency; overloaded decoder nets receive local banks.
Buffer detection includes compound buffers and clock-buffer cells used on
reset nets; protection follows actual clock connectivity. Overloaded data
drivers may be copied, with data FF copies retaining their original clock,
data, reset and cycle latency. Synchronizer FFs are excluded from replication.
Critical PLL launch FFs can receive a parallel leaf buffer from their existing
clock parent. Trials retain the clock root and check receive and launch timing
across all nine screens. Hold repair protects direct same-clock synchronizer
links; a cross-domain first-stage input remains eligible for repair.
Inherited hold buffers between synchronizer stages are removed only when a
local launch-clock branch meets the nine-corner hold/setup checks. Final
extracted timing, clock pulse widths and structural receiver-link checks are
required; estimates from the previous route are only ECO screening evidence.
The previous special 0.35 ns hold-repair target is removed.

`make ... clock-roles` corrects inherited local-clock net classifications and
reroutes those wires while retaining existing cells, placement and other
signal wires as routing input. It also archives its inputs and requires fresh
extraction/reporting. New local launch-clock branches are explicitly marked
`CLOCK`, and the final audit checks their actual database routing roles.
The pinned router also discovers clock nets automatically. Its leaf-clock
nets use the signal minimum routing layer; this metadata audit alone cannot
establish routing-layer compliance. See the pinned
[OpenROAD implementation](https://github.com/The-OpenROAD-Project/OpenROAD/blob/dcf36133/src/grt/src/GlobalRouter.cpp#L1436).

Repeat measured ECO operations as needed; routing estimates cannot establish
closure. After the final route, run reports for all five modes, physical proof,
gate regression and independent signoff, then run `closure_audit.py`. This audit
rejects incomplete corner/path coverage, stale evidence and unannotated
functional nets and modified direct synchronizer links, and distinguishes supplied-model closure from release
qualification. It reports antenna violations without treating this timing
stage as antenna or full-PVT qualification. `make test-closure` checks the
provenance and synchronizer safeguards.

### Handoff timing overlay and routed trials (2026-10-06)

The timing-only handoff overlay registers `transfer_busy`, with the invariant
`transfer_busy == (capture_pending || remaining != 0)`. Request qualification
uses this register instead of the capture-pending/counter-zero decode. Payload
capture and acknowledgement cycles remain identical. Root RTL is preserved.
`make -f verification/timing450/Makefile handoff` checks that the source-domain
always block is byte identical and proves every original destination state bit,
output and busy invariant after reset, with unrestricted payload, request and
subsequent reset inputs. Formal induction and the handoff regression pass for
WIDTH=34 and APPLY_CYCLES=1,2,3,4. Evidence and hashes are in
`build/timing450/handoff_proof/assessment.json`.

A separate full implementation is under
`build/timing450/hs/closure/handoff_candidate`. The full PLL RTL regression
passes at phases 7 ns and 0 ns, including all five modes and disturbance
recovery. Iteration 000 finishes with zero router violations, SS/max-RC PLL
setup -0.440024 ns, recovery +0.093271 ns and worst minimum +0.066404 ns.
All nine 450 MHz timing screens use fresh extraction of the PG-fixed route
(SHA256 c1391e248caf9f009c67074d506d4b2970873feda1aaa4bbb4010f8733b071bd).
Routed formal equivalence passes all 918 comparisons and gate simulation
passes both phases. Magic DRC is zero, unique transistor LVS passes, and all
81,294 supply pins are connected. Antenna violations remain (19 nets, 20 pins).
Setup and recovery miss the +0.10 ns target; slew violations also remain.
This is an unselected diagnostic candidate, not timing or release qualification.
Iteration 001 prepares further BBPD/counter sizing and local banks for five
measured electrical drivers; fresh routing and extraction are required.

Completed iteration-009 full reroutes are rejected: the 50% met2/met3
reservation trial has SS/max-RC setup -1.259550 ns, recovery -0.104901 ns,
worst minimum +0.080069 ns and 2,918 router violations. The 20% trial has
setup -1.467244 ns, recovery -0.064011 ns, worst minimum +0.079256 ns and
4,026 violations. The retained-wire iteration-010 run was stopped at
iteration 10 with 3,345 violations; its original root geometry was verified
unchanged and `stopped.json` records the reason and hashes.

The small ECO with unchanged cells temporarily fixed during legalization
retains 6,930 cells and clears only 18 original wires. It finishes with 46
router violations, SS/max-RC setup -0.715267 ns, recovery -0.487661 ns and
worst minimum +0.077314 ns. It is also unselected. New cells move as far as
149.7 um, so placement preservation alone does not provide timing closure.
A local-neighbor legalization experiment remains build-only. Ordinary
legalization finishes with 665 router violations, SS/max-RC setup -0.731315 ns,
recovery -0.257648 ns and worst minimum +0.077843 ns; it is also rejected.

The root physical checkpoint remains iteration 007: SS/max-RC setup
-0.631297 ns, recovery -0.633541 ns, worst minimum +0.041910 ns and 82
router violations. These are failures against the agreed +0.10 ns maximum
and +0.05 ns minimum margins. Older all-mode/signoff reports do not qualify
this geometry. No timing or release qualification is claimed.


Iteration 001 adds bounded all-nine-screen cell sizing and local electrical
banks. A signal `clkinv` omitted by the candidate filter was included; clock
cells remain protected. A second sizing pass produces the accepted trial
netlist `inverter.v`. Its full reroute finishes with zero router DRC. Fresh
450 MHz extraction gives worst PLL setup -0.067084 ns, recovery +0.075227 ns
and worst minimum +0.078769 ns. The counter setup path, a state-FF output
capacitance violation and a logic-driver slew violation remain. These fail
closure; this checkpoint is diagnostic and unselected. The preceding
`route_margin` run was stopped before completion and supplies no evidence.
Iteration 002 continues from the fresh iteration-001 route; root geometry
remains unchanged.


Iteration 002 routes cleanly and its fresh 450 MHz screens give PLL setup
-0.023444 ns, reset recovery +0.201845 ns and minimum +0.082372 ns. Routed
formal equivalence and both gate phases pass. The reporting command now uses
`-violators`: the earlier reports exposed only the worst electrical row per
type. The complete SS/max report contains 4,870 violated pin rows, so this
route is still unqualified despite its improved timing and zero router DRC.
Iteration 003 trials broad electrical sizing, guarded hold repair and local
residual banks. Native placement-estimate setup sizing crashes in the pinned
router callback and is not accepted; failed/stopped trials are recorded.
The combined trial is routing and requires fresh extraction, all five modes
and physical checks before selection. Root iteration 007 remains unchanged.


The completed iteration-003 diagnostic route has zero router DRC, fresh
450 MHz PLL setup +0.048786 ns and recovery +0.160270 ns, but its minimum
+0.011068 ns misses the hold floor. Routed formal equivalence and both gate
phases pass. Complete electrical reports still fail; the route is unselected.

Iteration 004 duplicates the BBPD seen register without changing its clock,
reset, input or latency. The pre-route netlist passes all 918 equivalence
comparisons and both gate phases. The completed met1 route has zero router
DRC and all 45 mode/corner reports are fresh on that geometry: worst PLL
setup at 450 MHz is +0.048656 ns, recovery +0.152917 ns and worst minimum
+0.069207 ns. The slow max/min screens contain 70/39 electrical violation
rows. Routed formal equivalence passes all 918 comparisons. This route fails
qualification: setup is below +0.10 ns and electrical violations remain.
Independent PG checking also finds a protected clock leaf with the wrong
row orientation, despite all 75,078 supply pins having logical connections.
The met2 routing trials were stopped without accepted routed checkpoints.

The flow now corrects protected ECO clock-leaf row orientation before
invalidating changed signal wiring, and checks physical VDD/VSS connectivity
before final routing. Verification invalidates old physical/gate assessment
files before reruns, and electrical reports request every violated pin row.
A separate met1 trial combines measured paired receive-FF sizing, acquisition
gate sizing, midpoint electrical banks and endpoint hold repair. Its estimated
maximum/minimum are +0.077799/+0.083656 ns; these are not extracted results.
Fresh extraction rejects that broader ECO: setup -0.041443 ns and minimum
+0.033354 ns miss both floors. Its zero router/Magic DRC, formal/gate passes,
unique LVS and connected supplies do not override the timing failures.

A narrower repair starts from the completed met1 route, preserves placement,
aligns one clock leaf to its row and invalidates only its two clock nets. It
finishes with zero router DRC and fresh 450 MHz setup +0.048415 ns, recovery
+0.152930 ns and worst minimum +0.072265 ns. All 918 routed formal comparisons
and both functional gate phases pass; disturbance recovery is about 145.5 us.
Magic DRC is zero, unique transistor LVS passes, and all 75,078 supply pins
are connected logically and physically. Setup still misses +0.10 ns, the
slow min/max reports contain 40/73 electrical violation rows, and 13 antenna
net/pin violations remain. All-mode reports and the final audit record these
failures. The candidate stays unselected and unqualified.
Root iteration 007 remains unchanged; no closure or release claim is made.

The subsequent BBPD/handoff trial factors the event decision and uses HS
AND-OR cells for capture/hold selection. The timing overlay also removes the
acknowledge XOR from idle pending-request capture and removes capture priority
from final-count acknowledgement. Handoff formal induction and regression pass
for application delays of one through four cycles; all original destination
state bits are compared, and source-domain logic remains byte identical.
The combined route before final sizing has setup -0.161041 ns and minimum
+0.083903 ns, zero router/Magic DRC, unique LVS, and all 74,982 supply pins
connected. Both functional gate phases pass. Its electrical reports contain
161 violated pin rows and its antenna check has 15 failing nets/pins. Full
routed equivalence proves 916 of 918 comparisons; acknowledge and
pending-request remain unproven. The passing compositional RTL proof does not
replace that physical qualification gate.

The final sizing trial strengthens the remaining-count and BBPD ready/down
receive flops and sizes their local gates against the extracted parasitics.
It freezes unchanged placements and preserves the clock connections during
routing. Artifacts from this historical sizing trial are under
`build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_004`
and `build/timing450/hs/closure/bbpd_factor_progress.json`. These experiments
remain isolated from the selected RTL and are not release-qualified.

The historical `variant_bbpd_final_sized` experiment reports 450 MHz setup
-0.109634 ns, recovery +0.023063 ns and minimum +0.083912 ns. Its resized
remaining-count receiver moves during legalization, creating a new limiting
capture path. Subsequent isolated experiments repair placement, receiver
loading, BBPD input assignment and the limiting data routes.

The current verified checkpoint is
`build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs`.
Fresh 450 MHz setup is +0.122951 ns, recovery +0.169483 ns and minimum
+0.078696 ns. All 45 supplied cell/RC/mode margin screens meet +0.10/+0.05 ns.
All 918 functional comparisons pass: 916 direct comparisons and two composed
through the independently proven six-state handoff control. Both gate phases
pass without SDF. Router/Magic DRC are zero, unique transistor LVS passes,
and all 74,778 supply pins connect. The evidence audit finds no changed direct
synchronizer links, incorrect local clock roles or unannotated functional pins.

All 45 supplied diagnostic timing, electrical and pulse screens pass.
Antenna checks report zero violating nets or pins. A compatible NAND2 strength
increase clears the additional 150 C electrical violations. All 45 additional
model/RC/mode screens pass, for 90 original/additional diagnostic screens.
These additional points add no exact release PVT-grid coverage. Full PVT coverage,
interface/CDC/pulse characterization,
density/EM/IR and whole-PLL qualification remain open. The repeatable full
KLayout FEOL/BEOL/off-grid/floating-metal/seal run checks the populated GDS
and reports zero violations. The PDK global minimum clear-area density deck
also passes; full density qualification remains open. The current model
inventory covers only one exact point of the required 45-point PVT grid.
`build/timing450/implementation_assessment.json` pins the current evidence;
`verification/IMPLEMENTATION.md` records the measured experiments. Further
routing and antenna trials remain isolated until fresh checks pass. No
candidate has been adopted into selected RTL or qualified for release.

HS antenna-diode verification reads `hs_formal_helpers.v` only for formal
checks; the input-only cell supplements the Liberty reader, which omits
cells without Boolean outputs. Gate simulation retains the actual functional
library model. The helper is included in proof hashes.

Independent signoff stages a candidate-local HS diode SPICE correction. It
requires the pinned legacy schematic and independently measures the original
library GDS junction (matching diffusion 65/20 and diode marker 81/23), requiring
one rectangular junction with area 0.6417 um2 and perimeter 3.24 um. It retains
terminal order and uses the installed `diode_pw2nd_05v5` primitive in native
area/perimeter units. The shared PDK and GDS are unchanged. Strict source and
geometry checks reject unrecognized views. Netgen property errors fail LVS
acceptance even when the topology matches uniquely; reversed-polarity and
doubled-area native controls confirm that neither error is waived.

Additional model suites can be screened without changing the installed PDK
or the candidate's base qualification snapshots:

```sh
python3 verification/timing450/verify_extended_models.py \
  --candidate <candidate>/build/timing450/hs \
  --model-suite build/timing450/extended_models/suite_150C.json \
  --mode-mhz 450 --output <new-report-directory>
```

Run inside the pinned container. The suite names explicit ss/tt/ff Liberty
paths, requires matching model metadata and enforces the 1.95 V ceiling.
The checker validates baseline input hashes, repeats the actual extracted
STA recipes, requires every clock/path group and rejects electrical/pulse
violations or SPEF mismatch. Additional characterized points retain their
actual voltage/temperature labels and do not substitute for missing exact
points in the required release grid.

The verification unit suite requires Tcl for its endpoint-margin guards. In
the pinned container, include `/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16/bin`
in PATH before running `python3 -m unittest discover -s verification/timing450
-p 'test_*.py'`. The default container PATH does not expose that interpreter.

Routed interface loads and SDF can be reproduced independently of the
accepted candidate:

```sh
python3 verification/timing450/characterize_interfaces.py \
  --candidate build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs \
  --output build/timing450/interface_characterization/checkpoint026
```

Run inside the pinned container. The helper verifies baseline hashes, reuses
the SS/1.60 V/100 C maximum-RC recipe and records capacitance in pF. It rejects
missing interfaces, inconsistent capacitance totals and extraction errors,
exports SDF with interconnect/cell delays and timing checks, and pins inputs,
tools, recipes and logs. It probes simulator timing checks using a deliberate
setup violation and compiles the actual HS timing views without `FUNCTIONAL`.
Neither SDF export nor a successful model compilation constitutes a timed
gate-simulation pass.

Checkpoint 026 input loads are 0.189715251 pF on BBPD[0], 0.166840822 pF on
BBPD[1] and 0.142693922 pF on PLLOUT. These are extracted loads at this model/RC
point; loaded analog slew/pulse and full PVT characterization remain required.
The installed Icarus 12.0 fails to detect the deliberate setup violation.
The HS timing-view compilation also fails and warns that delayed timing-check
signals will not be driven. Results and hashes are in the output assessment;
timed gate simulation and release qualification remain false.

Static power-grid characterization is available as a separate diagnostic:

```sh
python3 verification/timing450/characterize_power_grid.py \
  --candidate build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs \
  --magic-tech build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech \
  --output build/timing450/power_grid/checkpoint026/verified_matrix
```

Run inside the pinned container. Default coverage is all five modes and nine
supplied cell/RC combinations; `--modes 450` restricts a diagnostic run.
The helper validates baseline hashes, extracts nominal/minimum/maximum metal
and contact resistances from the pinned installed Magic technology and
converts their units for the native OpenROAD solver. This supplies the via
resistances absent from the HS technology LEF. It writes no candidate database.
Before power analysis, the helper forces timing propagation and verifies every
clock period, including the generated 40 ns FINECLK period. That clock initially
has a zero period in the pinned OpenSTA until timing initializes it. Explicit
activity density uses 0.5 transitions per operating-mode clock cycle with duty
0.5 on non-clock pins. An earlier `-activity` invocation before initialization
produced nonfinite power; both the failure and the clock probes are retained.

Each run solves VDD and VSS using a declared 140 um bump pitch, 70 um bump
size, interval one and zero external resistance. It records power components,
all per-instance rail voltages, segment currents and the minimum effective
VDD-minus-VSS supply at a matching instance. Missing matrix entries, nonfinite
power/current/voltage, disconnected grids, incomplete resistance tables,
empty native reports and mismatched rail instance populations fail the check.
All inputs, tools, recipes and native outputs are pinned in its assessment.

This uniform activity and bump model does not qualify the actual acquisition
or tracking workload, package supply, transient noise or analog macro power.
Segment current alone does not establish temperature/lifetime EM compliance.
The assessment keeps EM/IR signoff and release qualification false pending
those requirements and voltage-aware timing at the local supply.

The isolated fixes to the HS timing views are now reproducible with
`normalize_hs_timing_views.py`, `hs_timing_helpers.v` and
`flatten_hs_timing_cells.py`. These preserve timing checks/notifiers and move
cell timing paths into the physical SDF instance. Native positive controls
verify notifier/power UDP behavior and SDF buffer delay. The tested Icarus and
CVC builds still do not support the delayed signals required by the HS FF
views; full timed gate simulation remains open.

The sampled BBPD candidate is retained in `candidates/sampled_bbpd`. Its phase
transfer analyzer reads terminal receipts without writing to a live campaign:

```sh
python3 verification/timing450/analyze_phase_transfer.py \
  --directory build/timing450/interface_characterization/bbpd_sampled/phase_transfer \
  --output build/timing450/interface_characterization/bbpd_sampled/phase_transfer_snapshot_NEW.json
```

Run inside the pinned container with the workspace mounted at `/work/OpenPLL`
and its original absolute path. Use a fresh output path. It verifies pinned
inputs and recomputes each observed point's measurement from native waveforms.
Missing points remain explicit; only complete exclusive monotone curves with
both directions receive a transition bracket. All 90 phase/slew/PVT curves must
be bracketed before a grid-wide detector bound is available. That bound is a
deterministic detector measurement and cannot establish whole-PLL phase error,
metastability settling, acquisition or release readiness.

Run the sampled detector with the mapped nonlinear receiver across all primitive
PVT points, +/-200 ps offsets and 20/200 ps input edges in a separate directory:

```sh
python3 verification/timing450/characterize_coupled_bbpd.py \
  --sampled-directory build/timing450/interface_characterization/bbpd_sampled \
  --receiver-directory build/timing450/interface_characterization/receiver_fixture \
  --pdk /opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A \
  --xyce /opt/xyce/bin/Xyce \
  --output build/timing450/interface_characterization/coupled_receiver_sampled_pvt200ps_NEW \
  --jobs 2
```

Use the pinned container and both workspace mounts described above. The helper
requires a fresh directory, validates the exact physical/extraction/model inputs
and checks two received events with the expected sign. It records native failures
and retains unqualified status even if every deterministic capture screen passes.

`bbpd_reset_metrics.py` checks first-sample inhibition from a native coupled
trace. The initial-reset campaign under
`build/timing450/interface_characterization/coupled_receiver_sampled_startup`
pins its runner, physical macro, receiver fixture and native model/deck inputs.
It tests reset release before the first reference edge, during the high phase
and during the following low phase at two primitive PVT extremes. Quiet output
until the first post-reset reference sample and subsequent expected receiver
events are required. These startup screens do not establish reset aperture or
metastability guarantees, in-flight reset behavior or whole-PLL qualification.

Standalone-core density windows can be measured without changing the GDS:

```sh
/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3 \
  verification/timing450/characterize_density.py \
  --candidate build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs \
  --output build/timing450/density/checkpoint026_windows_NEW
```

Run inside the pinned container. The helper validates the candidate GDS against
its existing density receipt and writes a fresh separate report. It measures
unions of drawing/fill polygons in complete 50/700 um windows with 25/70 um
steps, following the window dimensions in the [published periphery rules](https://skywater-pdk.readthedocs.io/en/main/rules/periphery.html).
No outside-core geometry or partial-window area is assumed. The standalone core
has no complete 700 um windows; this cannot satisfy the assembled-chip density
gate. Process applicability, derived masks/waffles/exclusions and die-edge policy
remain open, and full windowed density/release qualification stays false.

`characterize_sampled_bounds.py --directory <completed-pvt250ps-directory>
--output <fresh-json>` verifies the complete sampled detector's native PVT grid
and derives independent guarded high and low interval bounds. Use the pinned
container with both workspace mounts. The low interval uses actual consecutive
pulse edges; it is not 40 ns minus the minimum high bound.

`verify_sampled_pulses.py --prior-directory <pvt_timing-directory> --bounds
<bounds-json> --output <fresh-directory> --jobs 2` replays all 180 supplied-model
STA screens at both pulse extremes. It validates native clock properties and
source slews, and preserves baseline inputs/receipts. It does not adopt the
sampled macro or claim exact required PVT/whole-PLL qualification.

To reproduce the checkpoint 026 event receiver and both tracking synchronizers:

```sh
python3 verification/timing450/extract_receiver_cdc.py \
  --output build/timing450/interface_characterization/receiver_cdc_fixture_NEW
```

Use the pinned container and a fresh directory. The helper validates the exact
routed netlist, maximum-RC SPEF and library inputs against the previous checkpoint
extraction. It retains the two synchronizer stages, direct data links and clock
paths, exposes first-stage clock/data nodes, and separates ideal event/pipe reset
roles. The native pilot under `receiver_cdc_pilot` verifies two received events
at one SS125/450 MHz alignment. An alignment campaign is under
`receiver_cdc_aperture`. Shipped transistor views lack explicit cell-internal
routing R/C; neither fixture nor pilot proves statistical metastability/MTBF,
full reset/ready behavior, physical DCO/noise or whole-PLL qualification.
