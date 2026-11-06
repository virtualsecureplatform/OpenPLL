# Programmed 400 MHz hard-macro signoff

The active profile is `requirements_v3.json`: prototype tapeout macro
integration with a 25 MHz reference, 400 MHz output, nominal 1.80 V, and
TT/FF/SS/SF/FS at 27°C. Startup configuration remains externally programmed
and stable until reset. Qualification requires 60 startup/recovery/phase
cases and one common gain pair across the five corners. Native-correlated
hierarchical validation is the selected method. Temperature/supply sweeps,
production lifetime, precision jitter and a 1 FIT target are later work.

**The macro is not release ready.** The five current gates are physical
integrity, analog models/tuning, digital timing/CDC, closed-loop operation,
and reproducible handoff. Passing diagnostic geometry, waveforms or unit
tests cannot substitute for their direct qualification evidence.

Reference-phase coverage uses `tb_programmed400_closed_loop_phased.v` and
`Prototype400ReferencePhase.v`. On each tracking entry, the external reference
is held low for at least 20 ns and its acquisition edge is placed 0, 10, 20 or
30 ns after an observed physical feedback edge. It then resumes its 40 ns
period. This avoids offsets being absorbed by synchronous startup. The actual
controller RTL is unchanged. `selected_reference_phase.py` checks every
initialization against recorded REF/DIV edges in the first observation window;
the release audit requires those coordinates for every scenario segment.
`run_selected_mixed_signal_v4.py` and `run_selected_matrix_v4.py` are the current
diagnostic runners for this phase convention. They compile the exact RTL bytes
pinned by the selected filled-layout receipt, retained in `rtl/selected400`.
The older version-3 runners compile a different controller revision and cannot
qualify this physical candidate. See
`verification/prototype400/selected_physical_RTL_binding.json`. Synthetic
phase-engine controls validate coverage only and cannot qualify analog models
or release readiness.

`prepare_selected_release_manifest.py --output NEW_MANIFEST` prepares the
selected layout-bound candidate identity and empty qualification slots for
`audit_prototype_v3.py --manifest NEW_MANIFEST --output NEW_AUDIT`. Diagnostic
receipts are not automatically attached as gate evidence. Baseline `461`/`462`
verifies nine RTL files and the selected physical identity, while rejecting all
five unfilled gates. Portable handoff and direct qualification remain open.

For read-only state checks, use `report_selected_job_state.py --case CASE`
(repeat `--case` for more jobs). It checks PID/birth identities and live resource
leases, distinguishes queued owners from actual native workers, preserves
uncertain observations, and reports worker exit separately from controller life.
A declared running/completed label never establishes native execution or success.
The reporter neither mutates jobs nor infers qualification.

Current simulation speed trial:

The leading configuration is isolated diode-corrected Xyce with checked UMFPACK
factor reuse, CSR kernels, sixteen individually pinned ranks, and
`.options DIST STRATEGY=2` in the simulation deck. All physical primitives,
1,269,218 capacitors, wire resistors, stimuli and nonlinear/integration tolerances
are retained. The 21.003 ns prefix completed in 1,183.01 s versus 1,928.79 s for
the completed four-rank mixed-solver reference (1.63x). All 494 saved samples and
25,734 physical voltages agree with the fresh reference within 10 nV on identical
times. This does not establish full-duration performance or numerical convergence.

The unchanged 175 ns programming diagnostic in
`build/signoff400/prototype_v3_UMFPACK_device_balanced_full_102` timed out at its
original 10,800-second cap near 160.35 ns. It did not qualify full completion or
endpoint programming state. The first 1,500 complete samples through 61.31 ns
agree with the fresh reference within 10 nV on identical saved times. The
provisional two-hour runtime target was missed; full-run practical speed and
every release gate remain unproven.

An isolated diagnostic build adds `--timestep-diagnostics` to the build command
below. It logs TRAP error ratio, integration order, proposed step and step limits
every 100 steps without changing timestep decisions. Native controls through
16 ranks passed in `build/signoff400/timestep_diagnostic_controls_103`.
The bounded full-circuit diagnostic
`build/signoff400/prototype_v3_timestep_diagnostic_prefix_104` completed its 22 ns
prefix in 1,375.67 s. All 586 saved samples are bit-identical to the uninstrumented
run. Three sampled steps were retained by the growth threshold and one reduced
by the error estimate, all below the hard maximum. A lower growth threshold
reduced analytic-control work but increased error; tested stricter tolerances
removed the benefit. That experimental policy is not adopted.

The current full 175 ns trial is
`build/signoff400/prototype_v3_UMFPACK_CSR_double_full_112`, with the original
three-hour cap, sixteen pinned ranks, and unchanged electrical inputs. Its
opt-in `krylov-csr-double` policy uses double precision for GMRES matrix products
while retaining the high-precision residual checks and fresh fallback. A native
system replay measured 1.11–1.19x speedup; seven changed-matrix cases and native
controls through sixteen ranks passed. Full-PLL performance and waveform
qualification remain pending. The default backend remains unchanged.

Reproduce the backend and controls from the repository root inside the pinned
release CAD image, using fresh output directories:

```sh
python3 tools/xyce_umfpack/build.py --experimental-checked-reuse \
  --reuse-policy krylov-csr --output build/tools/my_csr --cpus 16,17
python3 tools/xyce_umfpack/check.py --experimental-checked-reuse \
  --binary build/tools/my_csr/Xyce --output build/signoff400/my_csr_controls \
  --extra-ranks 16 --pin-ranks --distribution-strategy 2 --hierarchical-mos \
  --cpus 16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
```

For an already Xyce-compatible deck, include `.options DIST STRATEGY=2` in that
deck and use its own output filename. The launcher preserves model and output
directives:

```sh
python3 tools/xyce_umfpack/run.py --experimental-checked-reuse --pin-ranks \
  --binary build/tools/my_csr/Xyce --deck path/to/new_output_deck.spice \
  --log build/signoff400/my_run/native.log --ranks 16 --memory-gib 64 \
  --wall-limit-s 10800
```

The launcher records process identity and native exit; waveform assessment is
separate. The build defaults remain fresh-factorization mode unless explicitly
selecting the experimental backend. Detailed trial history follows below.

Current checkpoint (2026-11-03):

The active qualification snapshot is `campaign_prototype_v3_004`. It binds
the unchanged frozen RTL to the selected filled-parent manufacturing GDS
from `_selected_parent_filled_layout_019`. Identity verification passes;
all five qualification gates remain open. Diagnostic observations are
listed separately and cannot qualify a gate. Campaign 003 remains archived.

The original ngspice execution audit is
`campaign_prototype_v3_004/audit_after_programming_threads4_timeout_019.json`.
Frozen source and GDS identity still pass. Both full-model programming pilots
ended at their native runtime budgets without a completed 175 ns waveform;
the four-thread successor last reported 60.3823 ns. No large native pilot is
left running by these controllers. The five gates lack direct qualifying
receipts, including the five-corner validated models, timing/CDC coverage,
60-case common-gain loop campaign and clean handoff replay. The detailed
entries below retain their historical execution states and diagnostics.

A separate Xyce backend trial has since corrected a shared diode sidewall
charge discontinuity in isolated simulator builds and passed ten sampled
fixed-temperature diode comparisons. The assembled DC benchmark takes
152.8 s at one MPI rank and 67.7 s at four ranks (2.26x). The full-C
175 ns programming successor `_Xyce_full_C_programming_pilot_030` retained
all 1,269,218 capacitor cards but exhausted its 3,300-second native budget
after reaching approximately 19.05 ns. That pilot produced no completed 175 ns transient assessment.

The latest analog reference uses the complete context-matched parent
extraction. All 62,450 physical primitives and their terminal connectivity
match the checked manufacturing candidate. Its complete geometric operator
passes an exact parallel-path passivity certificate. The guarded reduced
reference removes 63,873 floating capacitor nodes, preserves every active
primitive and supply identity, and passes the source-Schur/diagonal-error
passivity certificate with a total normalized row error of 1.81e-7 against
the unchanged 1e-6 budget. Numerical guards are explicit model components.
Domain assembly, routed wire R, interface stimuli, neighborhood/FOM coverage,
loaded native validation, final timing and loop qualification remain open.

The 20 µm context extraction now passes the same 62,450-primitive physical
correspondence check and an independently replayed exact geometric passivity
certificate. Its floating-node inventory and complete flat reference are being
prepared for a comparison with the 10 µm model; neighborhood convergence is
not yet established.

The wider model has 77,608 capacitor-only nodes in three positive components.
Its original-deadline pipeline prepares the flat reference, runs the unchanged
controlled solver through `reduce_prototype_context_floating_C_v2.py`, reviews
the exported numerical products with the v3 reviewer, and applies the explicit
bounded passivity guard. The numerical producer leaves its passivity flag
false; only the guarded stage can certify that property. This avoids repeating
the archived dense-graph integer-reporting failure and preserves the original
1e-6 numerical error budget. The queued neighborhood comparison uses the two
proved physical conductor bijections and includes numerical guards. It reports
exact fixed-supply matrix row differences without claiming loaded-waveform
convergence. Two focused matrix-difference tests pass.

The 20 µm guarded reference is complete: all 77,608 floating nodes are reduced,
all 62,450 primitives remain, and the final normalized numerical row error is
1.86e-7 within the unchanged 1e-6 budget. The completed physical-node comparison
finds a maximum 16.75% matrix-row difference between the 10 µm and 20 µm models,
on a parent-driver conductor. Thus the DCO-only neighborhood does not establish
loaded-model convergence. Pure oscillator-only conductor rows differ by at most
1.59e-5, which does not resolve the parent-driver difference. The successor v3
view selects neighborhoods around the actual retained domain cells, resolving
their native placement paths against the manufacturing GDS and using the
independently checked native-to-GDS grid.

Both expanded views now pass direct GDS placement matching for all 1,948
retained physical cells. The 10 µm view maps 148,522 fill polygons. Native
extraction of this view is running; the expanded 20 µm extraction is queued
behind it. Device correspondence, exact passivity, bounded reduction and
physical-node neighborhood comparison are queued under the original checkpoint
deadline. The native KLayout control checks nested rotation/reflection and exact
margin geometry, and rejects missing, uninventoried and coincident placements.
The manufacturing GDS remains unchanged. No convergence or release gate passes
are inferred from these view/export controls.

The conditional loaded-domain reference is complete. It retains all oscillator
and parent primitives plus both whole PLLOUT receiver cells: 10,887 primitives,
3,171 private KCL nodes, and 790 explicit boundary-voltage ports. Its 991,189
main capacitors and separate 320,809-capacitor boundary-current network reconstruct
every capacitor in the complete guarded reference. The 51,563 exterior primitives
are exported separately as well. Source cards are checked again after export.
The partition preserves private-node KCL under identical boundary trajectories;
those trajectories have not been supplied or validated. It is not a standalone
native domain model. Two focused partition/header controls pass.

`prune_prototype_context_C.py` removes only positive dynamic Schur edges and
adds an explicit diagonal numerical correction. The correction minus the
removed edge Laplacians is symmetric diagonally dominant and PSD. Its exact
row error, including decimal/native-binary coefficient enclosures and the
source reduction error, must remain within the original 1e-6 budget. Physical
Cflat cards, devices, wire cards and supply identity stay unchanged. On the
completed DCO-only 20 µm context reference, it removes 525,734 positive edges
and adds 3,212 guards, reducing total capacitor cards from 1,364,382 to 841,860.
The final normalized numerical row error is 9.92e-7. The separate reviewer
reparses exported cards and replays the witness against actual guard values;
this passes. Four focused pruning/replay controls pass. Native speed and
waveform correlation have not been measured, and this diagnostic source is
not neighborhood-converged. Pruning and independent replay are queued for
both expanded-domain references after their guarded reductions complete.

The parent-wire LVS hierarchy and stock native capacitance hierarchy now have
a verified physical primitive/conductor bijection. Composing this with the
context graph proof binds all 973 routed parent networks in each min/nom/max
wire corner to the complete context model. All native resistor values are
retained in the inventory; SPEF capacitance is not added to the complete native
C model. Primitive terminal attachments, spatial C placement, actual wire-R
insertion and loaded qualification remain open.

The physical terminal review now binds all 2,480 signal instance terminals to
17,307 actual flat primitive terminal positions, with identical incidence in
the three wire corners. Six VNB/VPB terminals are classified under the existing
ideal-supply assumption; their wire R is not adopted as a PDN model. Five
primitive positions have two physical macro accesses, `digital:TRACKING` and
`digital:BBPD_RESET_N`. Wire insertion must retain their shared internal
conductor junction, rather than reassigning those primitive terminals twice.
The first helper fails on escaped-name handling; its successor fixes that and
then explicitly rejects supply-only ports without primitive incidence. The v3
review separates the fixed supply ports and passes. All failed receipts remain
archived. No transistor transient was restarted.

The updated full software regression passes: 769 tests across 18 commands,
with five optional host skips. Its source hashes and log are recorded in
`_selected_context_regression_launch_012/assessment.json`; actual CPU affinity
is restricted to cores 0–3. This does not qualify native analog models or any
release gate.

The oscillator child-wire binding now matches all 4,210 physical primitives
against each expanded parent context through exact local placement paths and
local device cards. Its 308 physical macro ports are anchored to the assembled
interface; 356 routed networks contain 1,498 signal instance terminals and
3,729 primitive terminal positions. All three wire corners pass, with 304
explicit parent/child signal-port junctions. Neither instance counters nor
extra extraction-export ports define physical identity.

`build_prototype_context_hierarchical_wire_R.py` combines those interfaces with
the parent wires. Macro boundaries join child SPEF ports; leaf terminals claim
primitive positions. This prevents shorting internal wire R by assigning both
the macro access and leaf device to one point. The first expanded 10 µm nominal
driver model contains 6,054 positive wire resistors over 1,022 original
conductors, 304 parent/child port junctions, and 20,145 rebound primitive terminal
positions. Actual-file contraction recovers every source primitive and signed
C card. The injective C lift preserves its existing numerical error budget.
Min/nom/max driver/farthest variants are queued for both expanded contexts.
Three physical child-mapping tests and three hierarchical-junction tests pass;
the updated full regression is running in `_selected_context_regression_launch_013`.

Both expanded reference reductions and their matrix comparison are complete.
The maximum row difference is 35.46% on an exterior conductive boundary input;
among the retained 3,171 private KCL rows the maximum is 2.91%, at PLLOUT.
Oscillator-only rows differ by at most 4.78e-6, and private parent/shared rows by
at most 5.52e-4. These are operator differences, not native waveform error bounds
or a convergence pass. The PLLOUT wire/fill environment and boundary drivers
still need review. Detector/digital internal R, spatial C attachment, loaded
native correlation and all five release gates remain open.

`build_prototype_context_parent_wire_R.py` now inserts parent signal-wire R
through the proved primitive terminal incidence. The nominal driver-attachment
control adds 3,544 positive resistors on 971 routed signal networks representing
970 original conductors, rebinding all 17,307 terminal positions. The five
shared digital macro terminal positions use one native internal junction;
their two wire accesses are merged at that junction without adding an artificial
zero-ohm resistor. Original fixed-supply assumptions remain explicit, and no
SPEF capacitance is added. Both the in-memory export and actual written SPICE
are reparsed: contracting the actual wire resistors recovers every original
primitive and signed capacitor card. The C lift is injective and preserves the
source numerical error budget and fixed-supply PSD certificate. Driver and
farthest attachment remain diagnostic placements. Four focused tests pass,
including shared access, signed C, changed/missing export rejection, complete
incidence, and preservation of the fixed-supply boundary. These four tests
postdate the 769-test full regression.

The expanded 10 µm reference completes all native device/C reviews and its
bounded reduction of 148,522 floating nodes onto 3,863 retained boundaries.
Pruning reduces 1,547,168 capacitor cards to 941,313; independent replay passes
with final normalized row error 9.92e-7. Its nominal driver parent-wire model
also passes exact contraction. The remaining min/nom/max driver/farthest
variants are queued for both expanded neighborhoods. Both native extractions
are complete; the expanded 20 µm model reviews are in progress. Child-internal
wire R, spatial capacitor attachment, boundary stimuli, loaded native validation
and neighborhood convergence remain open. These artifacts do not qualify a
release gate.

`inventory_prototype_context_interfaces.py` resolves all 304 oscillator/parent
cone cuts through the same native extraction and physical LEF directions.
There are 303 externally driven control cuts and one output requiring receiver
loading, PLLOUT. The latter touches a digital HS diode and HS clkbuf_16;
retaining their complete physical cells requires 41 primitives. This inventory
does not remove receivers, ground remote capacitor terminals, or validate
interface stimuli. Its two focused direction/parser tests pass separately from
the previously completed 757-test regression.

The mapped-fill DCO model contains one connected block of 63,873
capacitor-only floating nodes. `_selected_oscillator_driver_schur_019`
reduces this block to its 2,753 retained boundary nodes, preserving every
primitive and wire-resistor card. Native CHOLMOD fixtures agree with exact
rational elimination, and a perturbed-solution control fails the error
budget. The actual reduction passes independent fixed-supply passivity;
its maximum normalized row error is 8.342e-7 against a 1e-6 budget.
This is a bounded numerical reduction, not exact operator identity or
native electrical correlation. Original models and certificates remain
archived. FOM coverage, exterior loading and physical model validation
remain open.

The unreduced reset-start transient advanced only about 1 ps after 18
minutes and was stopped after over an hour, with its native output and
stop receipt retained. This establishes a throughput limitation, not a
circuit failure. `_selected_schur_DC_native_launch_019` runs the reduced
80 ns TT reset-start test with normal DC initialization, a byte-preserving
live native log and the original checkpoint deadline. The earlier UIC
case is archived. No release gate is promoted.

Latest checked candidate: `_selected_route_019` passes native detailed-route
DRC, independent Magic DRC, raw unique LVS, PG connectivity, native antenna,
and independent forming-antenna geometry (all zero violations). Fresh
extraction passes slew and capacitance limits at all five corners. Boolean
proof reuse is bound to byte-identical functional and powered netlists.

All 65 synchronizer interstage hold checks and ordinary holds pass. The
five 402.1 MHz setup screens pass (minimum SS WNS +0.16 ns); that diagnostic
rate still does not establish the final loaded startup frequency bound.
All 481 capture clocks at each corner remain within the tightest native
240 ps constraint-table maximum. The only reported failing endpoint in
each conditional phase screen is the separately reviewed first-stage
tracking-release aperture. Full startup/reset timing coverage remains open.

This closes the measured child repair loop. `_selected_parent_launch_019`
integrates this child into the 650 x 500 um parent, preserving the checked
analog macros, parent control buffers, power grid and placements. New
obstructions cover the actual child GDS. The unfilled parent passes Magic
DRC, the exact-zero-ohm child-port alias native LVS replay, native antenna,
independent forming antenna and flat-mask/gate-area preservation checks.

`_selected_parent_fill_019` adds PDK fill and proves all original geometry
and labels preserved. The filled parent passes fresh Magic DRC and the
unique exact-alias native LVS replay. Its 61,616 MOS bulk connections pass;
all 2,097 placed instances and parent wire-RC terminals are bound. Eighty
native stock density tiles support all seven filled macro-global checks;
the matching unfilled control fails all seven. The unchanged stock wrapper
retains its 700 um applicability failure; chip-window density remains an
integration obligation. `_selected_final_checks_resume_019` completes
stock full capacitance extraction before model validation. Filled native antenna,
forming antenna and flat-mask/gate-area preservation checks pass.
The first final launcher stopped before any native job because it tried
to verify image-only Nix paths on the host; the resumed launcher validates
them through the helpers inside the pinned image.

The stock extraction aliases exclude fill-purpose types from their ordinary
conductor capacitance rules. The stock whole-parent extraction therefore
cannot certify complete fill-aware loading. The extraction-only
`_selected_oscillator_fill_view_019` preserves original DCO drawing and gate
regions and maps 63,873 nearby poly/LI/metal fill polygons to conductors,
retaining whole polygons in a 10 um neighborhood. The manufacturing GDS
is unchanged. `_selected_oscillator_fill_capacitance_019` completes native
extraction of that view. Its 634,367-pair dynamic operator passes exact
fixed-supply passivity. The driver/farthest resistance variants use one
voltage-map congruence and preserve exact device/C topology at zero wire R;
both pass fixed-supply passivity. Original native placements are reused with
a fresh exact extraction join. FOM fill, exterior active loading,
neighborhood convergence and model adoption remain unqualified.

The complete assembled boundary inventory retains 304 physical signal
ports and 2,530 exported internal nodes. The corrected inventory excludes
the exported SUB alias of VGND from signal boundaries, retaining 20,435
incident signed capacitor pairs and 1,253 exterior device instances. The
previous inventory is archived; its ground-connected exterior counts are
not used for model loading. Both supply-alias regression controls pass.
All 55 standard-cell geometry
feature sets match the native extraction. The ngspice47 unit conversion
is applied to 814 diodes, with an independent expanded-card comparison.

The first TT/driver diagnostic was explicitly stopped and archived after
its singular floating-node DC bias attempts failed and it remained in
transient operating-point initialization. It had not completed the requested
80 ns transient; no physical DCO failure is inferred. Five small native
floating-charge controls establish UIC agreement with the exact linear
Schur equivalent within 7.4 nV; grounding the float gives 0.105 V error.
The UIC cases are archived. The reduced model now obtains a normal DC
reset-held operating point and runs the 80 ns reset-start transient under
the same original checkpoint deadline. Large-model convergence remains
unqualified.

Loaded analog/loop validation, full startup/reset timing coverage and
reproducible handoff remain open. No release gate is qualified.

The compact-pair checkpoint `_compact_pair_checkpoint_014` preserves all
5,960 existing non-spacer instances and adds 14 inverter pairs, eight source
buffers and four local diodes. Its original absolute deadline applies to
all subsequent routing variants. The broad selection in route014 passed
all 22 targeted drivers but created 32 failing nonincident drivers. Route016
retained 4,010 wires and selected only 78 incident or unrouted nets; it left
17 failing drivers. Route017 additionally guides the 36 new local nets on
met3/met4, reducing the failing-driver count to 11. These are measured
candidate comparisons, not qualification receipts.

`_direct_local_route_018` replays the same pre-detailed-route database with
36 bounded local guide corridors. All 4,035 nonlocal guide geometries are
unchanged. The total measured local centerline length falls from 2,232.72 um
to 1,208.89 um (supplemental RECT patches and via dimensions excluded).
For example, a 452.90 um local wire becomes 73.46 um. These diagnostics do
not substitute for the fresh extraction above.

Route018's five remaining slew nets included substantial detours, including
252.68 um on `DCO_THERM[2]` despite an approximately 84 um vertical span.
`_selected_route_019` clears only these five wires and the violating
`net66`, and constructs bounded met3/met4 guide trees from actual terminal
boxes. Native preparation retains all 4,065 other wires and all cell
placements. All other guides and logical connections are retained. Each
attempt retains the original checkpoint014 deadline and requires renewed
detailed routing and independent checks.

The expanded regression passes 714 tests across 18 commands, with five
optional host skips (`_selected_regression_010.log`). Run009 was stopped because its
outer 16 GiB address-space cap prevented the tests from setting their
configured 32 GiB merge-process limit. Run010 preserves a 48 GiB memory
lease and four-CPU affinity while allowing the nested process limits.
The suite includes guide geometry, launcher provenance/deadline, native
capture-axis and nested proof-receipt controls. The reusable
`inventory_prototype_capture_clock_ranges.py` checks all 481 capture
clocks at each corner after native timing. It derives the tightest maximum
from every relevant early/late native constraint table. SF capture-table
coverage on the older route013 checked all 481 capture cells (maximum
213.546 ps, characterized maximum 240 ps); every corner of the final
candidate still needs that model-domain review.

- `_wire_branch_fresh_route_003` passes routed equivalence and independent
  Magic DRC. Its raw LVS port serialization loses `BBPD_RESET_N`; the separate
  `_wire_branch_digital_alias_lvs_003` replay proves its raw merge chain to
  `TRACKING` and achieves a unique match without altering the original SPICE.
  Final antenna remains two nets/two pins. Fresh min/max RC leaves three
  capacitance failures per corner and TT/FF/SS/SF/FS slew findings of
  8/0/187/270/0. These checks do not qualify that candidate.
- `_wire_branch_followup_route_004` completes fresh routing after 68 further
  characterized resizes and six output-source buffers. All 13 first-stage
  masters remain unchanged. Final equivalence, fresh wire views, and independent
  layout checks complete. Independent Magic DRC, PG connectivity, and native
  antenna checks pass (zero antenna nets/pins). Raw LVS again needs the separately
  checked port-alias replay; `_wire_branch_followup_alias_lvs_004` now passes.
  All 65 synchronizer interstage hold checks pass, and the finite native
  clock-train comparison has minimum observed margin 0.133 ns. First-stage
  maxima are Q load 10.625 fF, D slew 897.141 ps, clock slew 184.337 ps,
  and reset slew 974.845 ps. These observations retain their finite scope.
  Electrical findings are one capacitance failure per
  corner and TT/FF/SS/SF/FS slew 4/3/98/181/3. A 402.1 MHz sensitivity screen
  still has SS setup WNS −0.403 ns; this diagnostic rate does not qualify the
  physical clock bound. `_wire_branch_followup_route_005` applies 46 measured
  resizes and ten source buffers, with new namespaces and retained deadlines.
- `_small_macro_density_controls_001` replays the unchanged stock global
  arithmetic on the native tile measurements. All seven filled checks pass;
  all seven matching unfilled checks fail. The fill-only geometry pair and
  all eight reported area-weighted values agree. The stock small-macro wrapper
  exits remain unchanged. Final-candidate density and chip-window integration
  remain unqualified.
- `_wire_measured_sizing_route_001` completes with zero router DRC; routed
  equivalence, independent Magic DRC, unique LVS and PG connectivity pass.
  Fresh RC screening reduces capacitance-limit failures from 72 to 10
  drivers and SF slew findings from 2640 to 695 pins. Four nets/five pins
  have new antenna violations; this candidate does not qualify closure.
  `_wire_branch_repair_plan_001` targets the remaining 120 measured drivers:
  82 next-strength resizes, 34 stronger output-source buffers, and four
  high-fanout clock-net splits into groups of at most eight sinks. All cells
  have native early/late tables, and all 13 first-stage masters remain fixed.
  `_wire_branch_repair_route_001` stopped before antenna repair because its
  command used the older `-diode_cell` option. The pinned tool help requires
  a positional cell argument. `_wire_branch_repair_route_002` corrects that
  invocation and saves a pre-antenna database checkpoint. Independent
  postroute physical and RC checks remain mandatory. The corrected attempt
  inserts four diodes and reports zero antenna violations, then stops at
  detailed-router pin access for NOR2_8 instance `$...74594/Y`. The retained
  pre-antenna checkpoint supplies `_wire_branch_fresh_route_003`: it clears
  ordinary signal wires, rebuilds global guides on the original met1–met4
  routing stack, and preserves special power geometry and the original
  checkpoint deadline. Logical ECOs are not applied a second time.
- The 005 pre-routing checkpoint passes its separately scoped transition/output
  equivalence proof. Final routed equivalence and physical checks remain required.
  `build_prototype_candidate_parent_frame_v4.py` accepts an independently proved
  alias LVS receipt only for the exact child layout, while retaining zero DRC,
  zero antenna, and complete PG requirements. Actual 004 evidence is accepted;
  missing and stale 003 alias receipts are rejected. Five regression tests
  also reject missing/stale proofs, unproved merges, changed extraction, and
  DRC/antenna/PG defects while retaining the raw unique-match path. This prepares parent
  integration and does not select the electrically failing 004 candidate.
- `screen_prototype_decision_hold_phase_v5.py` derives the checked one-cycle
  shift from the baseline SDC period rather than assuming 2 ns. All five
  402.1 MHz native phase screens complete; three parser controls pass.
  Their exhaustive endpoints identify four SS setup deficits and five small
  ordinary input-data hold deficits, in addition to the separately reviewed
  first-stage aperture. `_wire_branch_followup_timing_plan_004` preserves all
  005 electrical changes and adds measured timing repairs: 60 total resizes,
  ten source buffers, and two local buffers at each of five D inputs. All
  13 first-stage masters and timing exceptions remain unchanged. Eight planner
  and ECO controls pass. `_wire_branch_timing_checkpoint_007` prepares this
  successor from the same checked 004 source; no 005 changes are discarded.
  `_wire_branch_timing_route_007` is now routing the prepared checkpoint.
  Checkpoint 006 stopped before native execution because the helper accepted
  only reset flops; the observed DFSTP D-input repair is now explicitly allowed.
- `_wire_branch_followup_route_005` completes zero-DRC routing, final routed
  equivalence, and all three wire views. Its electrical driver count falls
  from 56 to 47, but capacitance still fails once per corner and slew findings
  are TT/FF/SS/SF/FS = 3/0/131/189/0. At 402.1 MHz, SS setup WNS is −0.41 ns.
  It remains an intermediate nonpass. Independent Magic DRC and all 44,708
  power pins pass, but detailed antenna has two nets/two pins. Raw LVS retains
  its port mismatch; the separate `_wire_branch_followup_alias_lvs_005` replay
  passes.
  The combined timing candidate 007 completes zero-DRC routing; final equivalence,
  wire views, and independent layout checks are running. The expanded full
  regression passes all 17 commands, 667 tests, with five optional host skips
  in `_wire_electrical_regression_003.log`. Those same optional checks previously
  passed in the pinned CAD image; their implementations remain unchanged.
- Candidate 007 has 54 electrical drivers still flagged: TT/FF/SS/SF/FS
  slew findings are 4/0/157/225/0, with two capacitance failures per corner.
  Its exhaustive timing endpoint lists contain only the separately reviewed
  first-stage release aperture. All ordinary data holds now pass. Native
  streamed-GDS LVS matches uniquely without an alias replay; the replay guard
  correctly refuses to modify this already matching source. Magic DRC is zero
  and all 44,700 PG pins connect. Two detailed antenna receivers remain.
  `_wire_branch_electrical_antenna_plan_008` adds exact measured local diode
  targets to the 37-resize/17-source-buffer electrical plan. The existing
  same-footprint local filler replacement retains its 20 µm placement bound;
  its three parser/Tcl controls pass. Checkpoint 008 completes with diode
  distances 4.29/2.40 µm, and `_wire_branch_closure_route_008` is routing it.
- The draft `integration_contract_v3.json` now binds the exact frozen
  fixed-divider candidate source bank and its receipt, matching candidate 007.
  The previous source hashes were valid for an earlier RTL bank. Qualification,
  calibrated presets, reset/input timing, startup clock bounds, loading,
  clock/power characterization, and portable handoff remain explicitly pending.
- Checkpoint 008 passes its separately scoped transition/output equivalence
  proof and negative reset control. Final routed proof remains required.
  `_wire_branch_timing_clock_train_margin_007` compares all 65 actual 007
  budgets with the retained finite native clock-train observations; minimum
  observed margin is 0.609 ns. Its receipt now distinguishes the 2 ns native
  stimulus period from the 2.48694354638 ns routed source period. Three new
  metadata controls reject stale periods and changed constraints. Continuous
  metastability, statistical FIT, and physical CDC qualification remain open.
- `_wire_branch_closure_route_008` completes zero-DRC routing, final equivalence,
  and checked min/nom/max wire views. Independent Magic DRC, alias-proved LVS,
  and all 44,432 PG pins pass. The two targeted antenna sites are fixed; three
  different receiver sites now fail. Electrical drivers fall from 54 to 33,
  with TT/FF/SS/SF/FS slew findings 2/0/66/112/2 and one capacitance failure
  per corner. Ordinary holds pass; SS has one setup deficit of 12.171 ps at
  402.1 MHz. Plan 009 starts with 30 resizes/three source buffers, plus measured
  setup and antenna repairs. The successor router uses a 50% global antenna
  repair margin (previously 10%); final detailed antenna remains mandatory.
  A parameterized fresh ECO namespace preserves references to prior buffers;
  three additional namespace controls pass.
- `_wire_branch_closure_checkpoint_009` prepares the combined 36-resize,
  three-source-buffer, three-local-diode repair. Diode distances are
  12.93/8.58/3.81 µm, within the retained 20 µm bound. The successor worker's
  fresh namespace is explicit and checked against existing source instances.
  `_wire_branch_closure_route_009` uses the larger global antenna margin,
  preserves its original deadline, and requires renewed final checks. Its
  pre-routing checkpoint passes equivalence and the negative reset control.
  The larger global margin inserts 48 additional diodes; final extracted
  loading, detailed antenna, and timing must be checked again.
- Candidate 009 passes routed equivalence, Magic DRC, raw unique LVS, and
  PG connectivity for all 44,360 pins. Capacitance checks pass at all five
  corners, and setup WNS is positive (SS +0.10 ns). Slew findings remain
  SS/SF = 84/110 pins on 30 distinct drivers; TT/FF/FS have zero. Exhaustive
  endpoint review finds one 0.974 ps FF hold deficit in addition to the
  separately reviewed asynchronous aperture. Antenna has one programming-input
  net/two receiver pins. The static programming interface has 75 direct
  receiver pins across 66 cells; the next repair protects that bounded set.
- A fixed-geometry pre-route sizing pass uses native five-corner models and
  extracted min/max RC with a 0.9 ns proposal guard. Changed master pin loads
  propagate upstream; pending source buffers are not inserted in this estimate.
  Fresh routed RC and all final checks remain mandatory. The first controller
  stopped while binding a physical diode removed from the logic projection.
  Its successor maps diode nets through retained named-net aliases, reuses
  the exact completed round-zero reports, and retains the original deadline.
  Four diode-mapping controls pass, in addition to four sizing and four static
  programming-interface protection controls. No duplicate native round is run.
- The resumed sizing proposal completes three five-corner rounds, reusing
  round zero and preserving its original deadline. It proposes 74 same-family
  resizes and 21 source buffers; the last fixed-geometry estimate has no failing
  drivers outside those pending buffer sites. Buffer topology is not estimated
  by this pass. Master pin-load changes are included; changed routed geometry
  still needs fresh extraction. Its four sizing controls and four physical-diode
  mapping controls pass. The static-interface protection tool has four passing
  controls and selects only the five static programming fields, with unchanged
  primary-input antenna checks and explicit LEF/logic pin bindings.
- Checkpoint 010 stopped when its two-site-only diode donor search could not
  find a filler within 20 µm. Checkpoint 011 retains that original deadline
  and partitions two-, four-, or eight-site donors into one diode plus exact
  remaining spacers. Runtime checks preserve complete, nonoverlapping donor
  bounds, existing logic placement, PG connections, and the actual 20 µm
  diode-distance limit. All 75 placements succeed; maximum distance is 9.57 µm
  (47 two-site, 18 four-site, ten eight-site donors). Three partition controls
  pass and are included in `signoff400-test`. The expanded full regression
  passes all 18 commands and 688 tests, with five optional host skips, in
  `_wire_electrical_regression_004.log`. The same optional checks previously
  passed in the pinned CAD image; those implementations remain unchanged.
- `make signoff400-test` passes all 17 commands (646 tests, five optional
  host skips) in `_wire_electrical_regression_002.log`. The five skipped
  Icarus/KLayout tests also pass in the pinned CAD image. The initial run
  exposed an unguarded missing-host-tool error in the startup-clock test;
  that log remains preserved, and the test now checks tool availability.
- `_exercised_model_clock_review_001` independently scans 30,823,475 delivered
  clock edges across all 105 retained diagnostics, checks every frequency
  against its pinned model table, and excludes reset gaps from cycle lengths.
  Rates span 398.047–401.985 MHz; the shortest observed high/low intervals
  across corners are 1.311/1.101 ns. Maximum programmed fine step is one.
  Acquisition visits TT fine 103–119, FF 171–186, SS 93–110, SF 82–97,
  FS 128–146, broader than the three-point near-lock fits. Final loaded
  native holdouts must cover acquisition as well as steady operation.
  These are model observations, not a qualified physical clock bound. Two
  additional parser controls pass. Shifted workers retain their original
  false twelve-case aggregate flags; the review checks each of their three
  actual cases and the complete combined 105-case matrix directly.
- `_observed_load_parent_layout_001` passes assembled Magic DRC, and
  `_observed_load_parent_alias_lvs_001` gives a unique match after the retained
  exact-zero-ohm child-port alias proof. Both native antenna and all 13
  independent formation stages report zero violations. Bulk tracing passes
  for all 51,921 MOS devices. Three parent wire views cover all 973 signal nets.
- The digital min/nom/max wire-RC screen exposes a remaining release issue.
  Fresh nominal extraction exactly reproduces the preceding routed SPEF;
  all three rule decks match the pinned stock image and supplied PDK source.
  At the diagnostic 500 MHz setting, slew violations are TT/FF/SS/SF/FS =
  644/41/2318/2640/174, plus 72 capacitance-limit failures at every corner.
  `inventory_prototype_electrical_limits_v2.py` separates their units; its two
  controls pass. Prior nominal-wire closure does not qualify wire variation.
  Sensitivity at 400.4 MHz still has SS setup/recovery WNS −0.19 ns, while SF
  setup/recovery WNS is +0.32 ns. Neither frequency screen establishes the
  actual startup/operating clock envelope.
- `_wire_electrical_digital_repair_001` uses the characterized native library
  and the extracted maximum wire RC to repair slew/capacitance with OpenROAD.
  It freezes all 13 first-stage DFRTP1 masters, preserves RTL and existing
  timing exceptions, and requests no 500 MHz setup optimization. Fresh routed
  equivalence, physical checks and five-corner RC checks remain mandatory.
  Fill and final loaded analog models await a stable electrical candidate.
  Fresh postroute checks show that resizer variants `_001`/`_002` retain
  capacitance violations on 58/71 drivers, and SF slew findings on 2587/2611
  pins; neither qualifies closure. `_wire_measured_sizing_plan_001` instead
  binds each failing driver to the smallest larger same-family size present
  in all ten native views: 425 changes, no first-stage changes, and 34
  explicitly unresolved drivers without a larger characterized strength.
  `_wire_measured_sizing_route_001` is routing this plan. The original route,
  both resizer candidates, and all nonpassing reports remain preserved.
- `_observed_reset_branch_delay_route_001` passes independent routed
  equivalence, streamed Magic DRC, unique LVS, antenna and PG connectivity.
  All five native-view capacity screens have positive setup margin and
  zero slew violations. Enabled-phase endpoint inventories show no ordinary
  D-input hold or reset-removal failures; the sole negative path at each
  corner is the explicitly reviewed asynchronous first-stage fine aperture.
  All 65 interstage hold checks pass. Reusing the unchanged first-stage
  native capture campaign, the minimum observed resolution margin against
  new routed budgets is 180.229 ps. This is finite observed coverage, not
  a statistical metastability bound or full startup/parent timing signoff.
- `_observed_load_parent_frame_001` selects this digital revision with its
  refreshed GDS obstruction abstract and unchanged analog macros. All 686
  macro-pin bindings pass. Parent protection/routing is being reintegrated;
  the older physical template does not qualify this new assembly. Exact LEF
  interface comparison retains all 369 digital pins. The native parent
  database retains its 302 buffer pairs, diode banks, PG geometry and leaf
  bindings, with conservative obstructions added for the new digital GDS.
  `_observed_load_parent_protection_scope_001` corrects inherited template
  scope flags while preserving the original native artifacts and receipt.
  `_observed_load_parent_route_001` is the fresh parent route in progress.
  DEF reconstruction probes are retained as failed diagnostics; their PG
  checks failed and neither probe supplies qualification evidence.
- `_observed_load_digital_followup_001` passes routed equivalence, streamed
  Magic DRC, unique LVS, antenna and PG connectivity. Five-corner slew checks
  now report zero violations. All 13 interstage hold paths pass at each of
  the five corners, and ordinary D-input hold failures are gone. Four
  reset-removal endpoints remain on one branch at FF and FS. The measured
  `_observed_reset_branch_delay_plan_001` inserts two characterized CLKBUF2
  stages before that branch; routing is in progress with fresh namespaces.
- `review_prototype_first_stage_ranges.py` reviews the saved native reports
  without repeating OpenROAD: its predecessor rejected ranged capacitance
  text after native reporting finished. The upper first-stage Q load is
  6.823 fF; maximum D/reset/clock 20–80% slews are 536/921/120 ps across the
  five corners. Scalar/ranged values and rejection controls pass two tests.
  Original postprocessing failures remain retained; this is scoped evidence,
  not final CDC qualification.
- The `_fine_grain_parent_buffered_*_010` template passes assembled Magic
  DRC, alias-proved unique LVS, native antenna, and all 13 independent
  formation stages. Filled layout and alias LVS also pass. This template
  still contains the preceding digital revision and cannot qualify its ECO.
- The stock density wrapper stops because the declared 650 × 500 µm macro
  is smaller than its 700 µm window. All 80 native tile measurements completed.
  `review_prototype_small_macro_density.py` retains the stock clipped-edge
  weights and seven global limits: all seven pass. The failed stock wrapper,
  geometry warnings, unavailable windows, and chip-integration density scope
  remain explicit; this review does not qualify the density gate.
- `_observed_load_digital_repair_001` applies seven characterized driver
  upsizes and six ordinary D-input hold buffers without changing RTL or
  timing exceptions. Routed equivalence, Magic DRC, unique LVS and antenna
  pass. Five-corner capacity screening retains positive setup slack;
  remaining slew violations are TT/FF/SS/SF/FS = 0/0/0/16/0, on two SF
  drivers. All 13 interstage hold checks pass at FF and SF. FF still has
  17 downstream reset-removal failures after the stronger reset driver,
  plus one ordinary D-input hold failure. A follow-up plan splits all 20
  reset-net receivers into branches of at most eight, upsizes the two SF
  drivers, and adds one D-input buffer. Native path reports bind the actual
  reset and D endpoint pins before each repair is planned.

Earlier implementation checkpoints (retained for provenance):

- `_fine_grain_parent_control_buffers_007` buffers all 302 thermal-control
  inputs while retaining the original diode banks and 166 prior buffer
  locations. Routing completes all 973 signal nets with zero router DRC
  violations. Assembled DRC/LVS and bulk connectivity pass; native Magic
  antenna reports zero feedback with exact mask/channel preservation.
  Independent formation geometry still finds one metal3 component at detector
  `CLKDIVR`. `_fine_grain_parent_buffered_protection_008` adds eleven measured
  diodes with the established 25% etch allowance while retaining every prior
  leaf binding and buffer identity proof. Its route passes; assembled checks
  are running. Both antenna methods must pass before fill proceeds.
- `_DCO_fine_grain_high_startup_phase_review_001` independently checks 45
  additional scenarios, 75 recovery segments and 300 final windows. Measured
  first-edge shifts are exactly 625/1250/1875 ps in every corner; all added
  cases pass with KI=1, KP=2. Maximum acquisition is 112.48 us. The original
  enable offsets partly alias after startup synchronization, so their count
  alone is not evidence of distinct oscillator launch phases. These added
  samples address that diagnostic gap without claiming continuous phase
  coverage or a final loaded native startup model.
- All five static reset-charge campaigns complete their 60 fixtures and
  known-capacitor controls. The preloaded TT campaign also completes; actual
  Q observations verify both captured D and final asynchronous-reset values.
  Other preloaded corners are running. Native charge intervals remain finite
  observations, not certified impedance bounds. The load-view sensitivity
  writer requires all five static/preloaded pairs and checks actual Q states
  before using them; non-reset pin loads retain the broad supplied envelope.
- `_fine_grain_parent_buffered_route_005` routes 699 signal nets with zero
  router DRC violations and verified physical pin bindings. Its assembled
  layout and alias-proved LVS pass. Independent formation-stage geometry
  again reports zero violations. Native antenna reports 28 feedback rectangles
  from one gate record, traced to `fine_therm[204]`. Candidate006 retains all
  165 prior buffer locations and adds this one input. No fill or physical gate
  is promoted by the independent zero count.
- `_DCO_fine_grain_high_native_duty_common_gain_review_001` independently
  checks all 400 final windows and 100 startup/recovery segments. Worst
  acquisition is 97.12 us, phase span 187 ps and phase drift 39.954 ps.
  Common KI=1, KP=2 passes; KP=0/1 fail actual completed traces under the same
  tuning, detector, clock bridge and duty configuration. This remains a
  diagnostic result without final loading or native startup uncertainty.
- `measure_prototype_reset_input_charge.py` adds a native reset-pin current
  diagnostic over static D/CLK states and 20/200/2000 ps ramps. A known 20 fF
  capacitor checks charge sign and units. Integration unit tests pass and the
  TT pilot completes all 60 fixtures and reproduces the known capacitor as
  20 fF for both directions. Measured effective reset-pin capacitances remain
  inside the broad supplied bounds; the DFRTP2 maximum is 6.432 fF versus the
  timing view's 5.710 fF TT assumption. FF/SS/SF/FS are running. These finite
  static-side-input observations do not replace routed electrical correlation.
- The active manifest now selects `requirements_v3.json` at its top level:
  five nominal operating points and 60 scenarios. Its previous contents are
  preserved byte-for-byte in `active_release_before_prototype_v3.json`.
  `campaign_prototype_v3_003` records the exact frozen source bank and
  provisional parent geometry; its initial audit leaves every gate open.
- The 163-buffer successor `_fine_grain_parent_buffered_layout_004` passes
  assembled DRC and alias-proved LVS. Independent formation-stage geometry
  reports zero violations across all thirteen stages. Native full-GDS antenna
  still reports 49 feedback rectangles from two gate records. Direct channel
  coordinate tracing maps these to `fine_therm[174]` and `[208]`. This native
  nonpass takes precedence over the independent diagnostic's zero count;
  no antenna waiver or fill promotion is made. Candidate005 retains all 163
  placements and adds these two buffered inputs. `fill_parent_v7.py` requires the matching native antenna,
  formation, geometry-preservation and alias-LVS receipts before adding fill.
  A real negative admission control rejects candidate003's 166 native findings
  before starting fill generation. Filled geometry and loading remain open.
- A native-duty sensitivity replay now uses a separate integer phase bridge
  with each corner's observed upper duty rounded upward to one ppm. Exact
  tests cover symmetric-clock compatibility, duty, retuning and reset. All
  sixty loop scenarios across five corners pass at KI=1, KP=2.
  Native startup transients and final loaded models remain absent.
- The preceding parent is `_fine_grain_parent_buffered_layout_003`, with 141
  diode-protected and 161 buffered DCO thermal control inputs. All 302 inputs
  are covered by the protection plan; this is not an antenna pass. Assembled
  DRC and alias-proved LVS pass. Native antenna reports 166 feedback rectangles;
  independent formation topology finds two metal3 components on
  `fine_therm[188]` and `[190]`. All sixteen mask regions and extracted channel
  area are preserved; all 48,990 MOS bodies trace to the correct parent rail.
  The successor `_fine_grain_parent_control_targets_004` retains all 161
  buffer targets and adds these two measured inputs, retaining their diodes.
  Successor placement is running; new routing and physical checks are required.
  `_fine_grain_parent_buffered_SPEF_003` extracts min/nom/max wire views for
  all 691 signal nets with resistively connected terminals; receiver cell
  capacitance and final analog loading remain unqualified.
  `_fine_grain_parent_buffered_SPEF_binding_003` binds all terminals in all
  three views to the checked LVS hierarchy and all 1,514 placed instances.
- Five local native tuning fits pass the 60-case diagnostic loop matrix with
  common KI=1, KP=2. Independent native holdouts differ by at most 0.330 ps
  in average period. Lower KP=0/1 controls fail. The 40-case native hazard
  campaign completes without simulation failures; extracted decoder timing
  and final parent loading remain absent, so neither result qualifies lock.
  `_DCO_fine_grain_high_numerical_review_001` compares the five retained
  80 ns baseline/strict runs over every complete measurement cycle. The
  largest observed average-frequency shift is 155.654 ppm and average-period
  shift is 0.390 ps. These are observed differences, not certified error bounds.
- A supplied-library input-capacitance envelope screen exposes small FF
  hold/removal deficits and SS/SF slew violations. That envelope includes
  supplies and temperatures beyond the active nominal profile. It identifies
  sensitivities for native load correlation and repair; it does not establish
  nominal-profile hardware failure or justify relaxing hold checks.
- The evidence below retains the earlier candidate history and its limits.
- No release gate is qualified. Final integrated physical checks, calibrated
  analog models, CDC disposition, common-gain capture and selected-macro clean
  replay remain required on one source set.
- `_native_fine_reset_repair_001` preserves all 481 state-transition functions
  and passes independent Magic DRC/LVS/antenna and main-rail connectivity
  (48,144/48,144 power pins). The complete five-corner timing review reports
  zero slew violations, no ordinary data hold or reset-removal failures, and
  positive setup/hold checks on all thirteen synchronizer interstage paths.
  Only the intentional first-stage fine-domain capture aperture remains
  negative. This is a conditional capacity screen, not full CDC qualification.
- `_integrated_mask_rearm_proof_001` proves five actual-parent phase,
  disabled-output and re-enable properties without continuous-enable
  assumptions. Removing the actual filter-output mask produces assertion-4
  counterexample frame 222. Analog resolution and statistical reliability
  remain separate from these sampled logical proofs.
- `_DFRTP1_observed_resolution_002` reviews 3,225 native cases from 94 capture
  points, retaining old and new captured values and all sampled excursions.
  All final observations reach a rail; the largest observed tail is 3.423 ns.
  `_fine_release_observed_resolution_margin_001` compares these observations
  with the actual routed fine-domain setup budget and finds a minimum sampled
  margin of 27.669 ns. No continuum, other-first-stage, or FIT bound is claimed.
- The original drive-trim DCO routes cleanly and brackets 400 MHz in five
  corners. Interior native measurements expose curvature and calibration
  errors hidden by endpoint interpolation. Neither the original controller
  nor its private half-cycle experiment passes the refined full matrix yet.
- The corrected finer-step DCO keeps 510 load cells: 255 variable loads and
  255 fixed-high loads, with one variable load per fine bit alternating ring
  stages. High is required by the inverted thermometer encoding to retain
  the lower-end load. Its five-corner schematic brackets pass; the private
  physical build completes router/Magic/KLayout DRC and LVS with zero reported
  errors and no inserted antenna diodes. Independent full-GDS antenna reports
  zero feedback; all sixteen checked mask regions and extracted channel areas
  are preserved. Stock capacitance extraction, three RC views, primitive
  geometry and junction-rounding reviews complete. Routed fine-code 8/247
  probes bracket 400 MHz in all five corners. All seventy interior points
  complete without failures. `_DCO_fine_grain_high_grid_review_001` reviews
  eighty points including endpoints: all sixteen measured frequency intervals
  in each corner strictly increase and bracket 400 MHz. This does not qualify
  unmeasured codes, interpolation uncertainty, dynamic response or parent loading.
  The earlier fixed-low experiment is preserved and unselected.
- `_CDC_resolution20f_observed_001` reviews a further 3,375 native captures at
  20 fF over five corners and the measured first-stage slew envelope. Every
  sampled final observation reaches a rail; the largest observed tail is
  0.703 ns. These isolated two-clock captures do not establish resolution under
  a continuous 500 MHz clock train or a statistical metastability bound.
  `_all_interstage_observed_resolution_margin_001` compares the observations
  with all thirteen actual chains in all five corners. Every sampled margin
  is positive; the minimum is 0.191 ns. This comparison retains the isolated
  fixture limitation and does not qualify physical CDC by itself.
- `_fine_grain_parent_frame_001`, `_fine_grain_parent_power_001` and
  `_fine_grain_parent_route_001` assemble the reset-repaired digital macro,
  corrected fine-grain DCO and detector. Exact pin mapping, power database
  connectivity, port clearance and parent signal routing pass. Assembled
  Magic DRC reports zero errors. `_fine_grain_parent_alias_lvs_001` proves
  unique LVS after propagating only the independently checked exact-zero-ohm
  child-port alias; the raw nonmatching comparison is retained. The bulk
  trace checks all 45,770 MOS bodies against the correct parent rail. Full-GDS
  antenna reports 6,047 feedback rectangles with exact sixteen-mask and gate
  area preservation. Independent formation-stage topology identifies 145
  violating components on 143 parent nets, all mapped to macro ports. Most
  failures occur at metal3; seven occur at metal4. A separate MOS-only native
  check uses the previously validated stock `ngspice(orig)` diode style and
  also reports 6,047 feedback rectangles. Its debug log retains 190 violating
  gate/stage records. The original postprocessor rejected the different
  `mosfet` record format; `_fine_grain_parent_MOS_antenna_review_001` reviews
  the retained native output without rerunning it and confirms 45,770 MOS,
  fourteen explicit diodes, and exact source channel area. This confirms an
  antenna nonpass; changing extraction style does not close it.
  Restricting the whole parent to metal4/metal5 fails
  global-route congestion; that attempt is preserved and unselected. Targeted
  protection, native rechecks and full-parent capacitance review remain open.
  Macro selection remains provisional and no physical release gate is
  promoted by these intermediate results.
- `_CDC_clock_train_pilot_ss_001` observes 75 SS captures under a 500 MHz
  clock train with one-nanosecond high pulses. Its rail-observation window ends
  at 21.8 ns, before the next rising edge at 22 ns. Every sampled case resolves;
  the largest observed tail is 0.609 ns. The full five-corner campaign completes
  and reuses the pilot without an identical native rerun.
  `_CDC_clock_train_observed_001` verifies all 3,375 cases resolve before the
  next rising edge. The largest observed tail is 0.699 ns.
  `_CDC_clock_train_resolution_margin_001` compares all sixty-five actual
  routed interstage budgets and finds a minimum observed margin of 0.195 ns.
  Statistical and continuous-aperture reliability remain open.
- `_fine_grain_parent_protection_001` places 581 measured-geometry antenna
  diodes and 286 well taps on 143 mapped parent nets. Sizing includes a 25%
  etch allowance and actual 0.6417 um2 diode diffusion. Banks occupy legal
  row sites in the powered corridor outside unchanged macro interiors.
  `_fine_grain_parent_protected_route_001` preserves all original and added
  bindings with router DRC zero. Independent assembled DRC is zero and the
  exact-alias LVS replay passes. The bulk trace verifies all 45,770 MOS bodies.
  Protected full-GDS antenna still fails: feedback falls from 6,047 to 2,626
  entries and native gate/stage violation records from 190 to 75. Independent
  topology reports 53 remaining failing components (48 metal3, five metal4).
  Macro/flat mask preservation passes. The full lower-metal route cannot
  access digital ports exposed only on metal4. A separate route retains that
  access while reducing metal4 capacity by 95%; it remains a repair candidate.
  Protected parent capacitance extraction is running. Neither antenna closure
  nor final parent loading is inferred from placement or LVS.
- The reduced-metal4-capacity parent still fails antenna checking with 3,419
  feedback rectangles. Its three conventional SPEF views extract all 369
  routed signal nets, with exact units, excluded pin capacitance and connected
  resistive terminal graphs. Native macro binding remains separate.
  `_fine_grain_parent_peripheral_protection_001` instead places the same
  measured protection near ports around all macro sides and supplies them
  through macro-clear trunks. Its route passes router DRC, assembled DRC and
  exact-alias LVS. Full-GDS antenna checking still reports 2,039 feedback
  rectangles; remaining formation-stage components are being localized.
  All earlier failed
  routes and comparisons remain archived; none is silently promoted.
- `_fine_grain_parent_control_buffers_001` adds characterized INV8/INV2 pairs
  at forty measured DCO control receivers. All ten native libraries implement
  the exact inverter function; their composition is Boolean identity. The
  composition test rejects an incorrect cell function. The actual source
  admission check also rejects a corrupted proof digest, absent identity
  proof and absent routed-binding attestation. Physical net names change;
  admission therefore uses the explicit composition proof rather than
  claiming literal preservation of the original macro connections.
  The buffered parent passes router/assembled DRC, exact-alias LVS and the
  46,570-MOS bulk trace. All three SPEF views bind 449 signal networks to an
  exact 1,030-instance placement join and the alias-proved LVS hierarchy.
  Cell-internal capacitance combination and parent timing remain open.
  Native antenna feedback is 1,637 entries; independent topology has 23
  remaining metal3 failures and no metal4 failures. Every previously targeted
  buffered net is clean; the remaining nets are different unbuffered inputs.
  `_control_targets_002` is explicitly a cumulative repair inventory, not a
  current-defect count. The 63-pair successor retains all forty original
  control-net positions and adds the twenty-three new targets. Its placement
  and PG checks pass; routing is running.
- The complete TT interior grid drives the unchanged nine-source digital
  candidate in `_DCO_fine_grain_high_TT_loop_ki1_kp3_001`. All twelve diagnostic
  startup/recovery/phase cases pass with KI=1, KP=3 and interpolated seed 111.
  All five complete grids now pass the full sixty-case diagnostic matrix with
  KI=1, KP=2 (TT/FF/SS/SF/FS seeds 111/178/101/90/137 and coarse codes
  20/9/47/26/20). KI=1 with KP=0 or KP=1 fails the TT phase-zero screen.
  `_DCO_fine_grain_high_common_gain_review_001` independently checks all 400
  final observation windows in 100 recovery segments, verifies one exact RTL
  bank across the sixty cases and confirms actual completed-trace failures
  for lower KP values. These models remain explicitly synthetic pending
  native holdout, dynamic-response and final-parent loading qualification.
  All five 80 ns seed references complete: TT/FF/SS/SF/FS average frequencies
  are 400.086/400.082/400.071/400.204/400.061 MHz, within 511 ppm of target.
  TT per-cycle frequencies range from 399.949 to 400.163 MHz. Longer native
  measurements at seed offsets -2/-1/+1/+2 and five stricter timestep/tolerance
  controls are running; they do not rerun the completed center references.
- The actual-source calibration reference-pause control passes after explicit
  reset initialization. A second fixture uses five public REFCLK pulses after
  phase-controlled reset release, verifies a stable preset with tracking off
  while REFCLK is stopped, then checks resume and reset/reprogram. The oscillator
  is ideal in this protocol test; analog calibration is not qualified by it.
- `_isolated_functional_native_smoke_001` passes actual functional and native
  replay with checkout, home and host scratch hidden. It compiles the exact
  source bundle and reproduces the pinned native capture waveform byte for
  byte using only explicit read-only inputs and private work. This validates
  the staging replay mechanism, not the final selected macro package.
- Full regression: 560 tests, four skips, successful. Sixteen additional
  focused tests pass, covering branch identity, exact R contraction,
  reset-only rewiring, diagnostic reseeding, inverted fine-load mapping and
  rail-resolution classification. Native model discrepancy and final parent
  loading remain unqualified; rejected nonpassive attachments stay excluded.

Earlier implementation evidence (2026-11-01; superseded where noted below):

- Follow-up checkpoint: the first ten routed DCO endpoints complete but do
  not bracket 400 MHz at their schematic-selected coarse codes. Fine-247
  averages are TT 358.346, FF 354.400, SS 365.359, SF 374.540 and FS
  343.917 MHz. `_DCO_drive_trim_routed_endpoint_coverage_001` preserves that
  measured failure. Higher-drive native bands are running on the same GDS:
  TT=20, FF=7, SS=47, SF=26, FS=19.
- Branch repair 002 leaves only 67 SS and 117 SF reported slew failures;
  TT/FF/FS have none. Complete data checks expose two ordinary hold deficits:
  FF handoff payload 17246 -3.332 ps and SS startup coarse state 17346
  -9.393 ps, plus the explicitly unqualified first-stage CDC aperture 17893.
  Repair 004 routes seventeen further driver sizes, one branch buffer and
  those two local D repairs. Attempt 003 stopped on a reused instance name;
  the successor uses a fresh namespace and explicit collision checks.
- Exact-candidate schematic loop diagnostics complete all sixty cases with
  KI=1/KP=3 and again KI=1/KP=1. Both campaigns fail the phase-span criterion;
  these sparse schematic models provide no release evidence. Routed fine
  curves and common-gain capture still require qualification.
- The complete geometric C zero-R probe and the exact-contracted SPEF C
  zero-R probe compare capacitor models with the same wire-delay assumption.
  These diagnostic comparisons do not substitute for finite-R validation.
  Two contraction tests and four electrical branch-helper tests pass.

- Latest checkpoint: the drive-trim candidate completed router/Magic/KLayout
  DRC and LVS with zero reported errors and no inserted antenna diodes.
  Its full-GDS Magic antenna check reports zero feedback on 4,208 MOS
  primitives. Independent comparison preserves all sixteen checked masks
  and exactly matches the 488.1923 um² channel/gate area. Six cell masters
  pass primitive/cell-capacitance checks; junction review covers 4,210
  primitive instances including two non-MOS devices. Ten routed endpoint
  simulations are running.
- The signed source C operator has a failed unconstrained sufficient
  certificate. Exact ideal-supply projection has no negative edges and is
  passive. The proposed distributed full-C attachment still lacks a dynamic
  passivity certificate and is rejected; no invalid attachment is simulated
  or promoted. Model discrepancy and final parent loading remain open.
- Electrical branch repair 002 applies 129 characterized resizes and 26
  buffers. Routing completes with zero DRC, but the original finalizer rejects
  newly used BUF2 absent from its predecessor inventory. The separate
  `_native_electrical_branch_reviewed_002` receipt verifies that BUF2 was
  explicitly planned and characterized in all ten native views, then exposes
  byte-identical completed route files. Independent equivalence, Magic DRC,
  LVS, antenna and PG checks pass (48,148/48,148 power pins). New five-corner
  timing, complete data budgets and electrical inventories are being reviewed.
- The full regression ran 560 tests successfully with four skips (532.426 s).
  Two additional branch-ECO tests pass. `loop_fixed_candidate_diagnostic.py`
  now executes the exact nine synthesized RTL sources, avoiding reconstruction
  of a merely similar divider variant; its schematic-model runs remain
  unqualified diagnostic work.

- Latest evidence supersedes the historical candidates below. The integrated
  actual-core decision-phase proof passes with arbitrary enable/disable and
  stable programming between resets; analog resolution and disabled-state
  masking remain open. Targeted data/BBPD/reset repairs preserve equivalence
  and pass independent physical checks. The newest electrical route has
  positive setup at all five corners (SS 0.06 ns); exhaustive data checks
  retain only the intentional first-stage CDC aperture failure.
- Native Liberty revision 008 restores the PDK's 1 ns library-wide driver
  transition limit; all delay/capture tables are unchanged and parser review
  005 is clean. Electrical repair 002 resizes 36 cells and adds four buffers,
  but `_electrical_limit_inventory_002` still finds TT/FF/SS/SF/FS
  8/0/872/1024/10 violating pins. This route is not electrically qualified.
- `_DCO_drive_trim_schematic_bands_002` observes 400 MHz endpoint brackets
  at every corner using coarse FF=2, SS=27, TT=10, SF=14, FS=10. The source
  has a reset NAND and two inversion stages, each with eight always-enabled
  and 47 controlled drivers, plus 510 fine loads (two per fine bit).
  `build_prototype_DCO_drive_trim_candidate.py` now routes that architecture
  privately with met2 as the minimum routing layer. It remains unselected;
  routed tuning, numerical/model uncertainty and closed-loop cases are open.
- Full-GDS antenna analysis of the provisional compact parent reports 3,039
  feedback entries. Flattening exactly preserves all sixteen checked masks
  and the 48,872 MOS devices' total gate area. The geometric engine control
  002 passes: stock wrapped buffer has zero entries; a connected metal3 pad
  produces nine entries with identical four-device geometry/connectivity.
  Final-source parent antenna closure remains required.
- Six focused drive-trim tests pass, including exact physical-source driver
  counts and the two-load-per-fine-bit mapping. Broader historical test
  counts below do not include this latest test.

- `_state_data_budgets_{corner}_001` explicitly queries every one of the 481
  state D pins under the retained conditional capacity constraints. Every
  corner reports min/max data paths for 467 endpoints. The remaining fourteen
  comprise eight constant-driven D pins and six first-stage asynchronous
  crossings excluded by that capacity view; they are not silently qualified.
  Across five corners, 89 data endpoints initially have negative hold slack.
- `_ordinary_data_hold_repair_plan_001` selects 85 measured ordinary D
  endpoints, leaving first-stage apertures and three critical BBPD endpoints
  separate. `_native_data_hold_repair_001` adds 152 local data buffers and
  passes routed equivalence, router/Magic DRC zero, unique LVS, zero antenna
  violations and main-rail connectivity. Five-corner setup stays positive
  (SS minimum 0.08 ns). `_ordinary_repaired_data_budgets_{corner}_001`
  reduces FF negative data endpoints to seven: the first-stage aperture,
  three intentionally untouched BBPD endpoints and three newly exposed
  deficits below 5 ps. The other four corners retain only the first-stage
  data aperture failure in this view. This candidate remains unselected.
- `_native_BBPD_branch_repair_001` tests four buffers on the two exact logic
  fanouts of `clkdiv_sampled_d`. Equivalence and independent physical checks
  pass; setup stays positive at every corner. Its full data review exposes
  another short branch from `clkdiv_sampled`, with residual FF deficits up
  to 18.349 ps; no BBPD timing closure is claimed.
  `_native_selective_hold_repair_001` combines both branch repairs and three
  residual D repairs in thirteen buffers on the ordinary-repaired route.
  Independent geometry/LVS/antenna/PG checks pass, but SS setup regresses to
  -83.417 ps. FF data hold retains two short FF-feedback deficits and one
  consumed-event input deficit (maximum 6.824 ps), plus the first-stage
  aperture. This candidate is also unselected.
  `_native_chain_size_preview_ss_001` tests same-function gate sizes with
  original wire RC. Coupled NOR2_1-to-NOR2_2 changes on the critical chain
  give approximately 100 ps setup margin in memory; this is not physical
  timing evidence. `_native_path_closure_repair_001` completes a fresh route
  with those two resizes and three local short-path buffers, router DRC zero
  and fresh RC. Independent equivalence, timing and layout checks are pending.
- `_DCO_drive_trim_cell_capacitance_001` extracts isolated stock models for
  EINVn0, EINVn1 and EBUFn1. `_DCO_drive_trim_cell_review_001` checks primitive
  and junction units, exact capacitor passivity, transistor topology/width/
  length LVS and a wrong-width negative control. `_DCO_drive_trim_schematic_001`
  uses a fixed reset NAND, six drive-controlled inversion stages with one
  always-enabled and 47 thermometer-controlled units per stage, and 1,020
  fine loads distributed across the six stages. All 255 fine controls are
  preserved. TT/SS maximum-drive midpoint probes are running. This is a
  schematic architecture experiment without intercell wire RC or parent
  loading; it supplies no physical candidate or tuning qualification.
- The current prototype unit regression contains 226 passing tests.

- `_complete_endpoint_inventory_{corner}_001` expands the conditional
  enabled-mode timing review to all failing endpoints and explicitly checks
  all thirteen synchronizer interstage paths. The five corner reports contain
  TT/FF/SS/SF/FS 6/81/24/8/8 failing endpoint paths. Eleven interstage paths
  have negative hold slack at FF, with a maximum deficit of 90.077 ps;
  all thirteen interstage setup checks pass. These reports retain ordinary,
  asynchronous-control and first-stage aperture failures without waivers.
  `_interstage_hold_repair_plan_001` pins a diagnostic 26-buffer ECO affecting
  only the eleven measured capture data paths. `_native_interstage_repair_001`
  completes routing with zero router DRC violations and fresh nominal RC;
  `_native_interstage_equivalence_001` proves routed transition/output
  equivalence. `_native_interstage_timing_{corner}_001` preserves positive
  setup capacity in all five corners (minimum 0.09 ns, SS).
  `_repaired_endpoint_inventory_{corner}_001` reports positive setup and
  hold slack for all thirteen explicit interstage paths in every corner;
  the smallest interstage hold slack is 1.745 ps at FF on the unchanged fast
  reset chain. Other endpoint failures remain: TT/FF/SS/SF/FS 5/70/24/8/6
  paths, including ordinary, asynchronous-control and first-stage checks.
  The independent digital layout audit completes with Magic DRC zero,
  unique LVS, zero antenna net/pin violations and all 48,332 power terminals
  connected. Full KLayout/density checks, final parent context and mode/load
  envelopes remain required before release selection.
- `_handoff_payload_{fast,fine}_{corner}_002` measures actual source snapshot
  registers through each handoff capture mux, covering the one fast and
  twenty-nine fine implemented capture registers in every corner. Maximum
  source-clock-to-capture-D delays are 0.619789 ns (fast, SS) and 0.923165 ns
  (fine, SS). Attempt 001 retained the capacity screen's interclock false
  paths and correctly rejected missing coverage. Version 2 removes those
  interclock exceptions in a separate measurement-only SDC. Reported
  cross-clock setup slack is diagnostic; request synchronization, earliest
  capture budget, hold and mode coverage still require qualification. These
  paths are distinct from applied-command-to-loop-integrator seed loading.
- `_DCO_broad_fine320_endpoint_coverage_001` binds all ten completed
  conventional endpoint probes to one physical candidate and their actual
  RC models. Only SF coarse 2 brackets 400 MHz. The tested TT coarse 2,
  FF coarse 3, SS coarse 1 and FS coarse 2 bands remain above target.
  No tuning setting or analog gate is promoted from this experiment.
- The prototype unit regression currently contains 220 passing tests.

- The completed `_final_capture_remaining_aperture_campaign_001` supplies
  5,265 additional cases at 135 points with no unresolved/glitching reviewed
  cases. `_final_capture_constraints_003` combines both disjoint refinement
  campaigns with the original coarse samples: 15,525 cases, all 225 slew
  points and all 25 master/corner tables. `_final_native_liberty_007` and
  parser `_004` supply ten views without parser warnings. Generation attempt
  006 stopped before output creation because its image-owned OpenROAD input
  was unavailable on the host; generation 007 completed inside the pinned
  image without repeating measurements.
- `_aperture_boundary_numerics_002` replays 227 distinct clean endpoint
  fixtures covering 300 worst-boundary/fast-axis selection checks across all
  25 master/corner groups. It tightens the maximum step to 1.25 ps, relative
  tolerance to 1e-7 and absolute tolerance to 1e-11. All selected outcomes
  and target-window crossing counts are preserved; the maximum output
  crossing shift is 6.28241 ps against the existing 10 ps allowance.
  Equivalent original and prior numerical reference runs are retained and
  compared after checking model/load identity and exact normalized fixture
  stimuli. Preflight attempt 001 rejected duplicate references before any
  native launch. This is sampled numerical support, not a continuum or
  stochastic metastability guarantee.
- Timing screens `_final_native_timing_{corner}_004` retain positive setup
  slack in every corner at the 500 MHz diagnostic capacity point (minimum
  0.09 ns at SS). Conditional enabled-phase screens
  `_decision_enabled_hold_{corner}_005` still fail hold. Sampled path review
  `_decision_enabled_path_classes_003` retains the 90.077 ps BBPD synchronizer
  interstage deficit and 110.105 ps fine-payload-to-integrator deficit, with
  no waiver. Mode-specific static/reload obligations, complete endpoint
  review and targeted physical repair remain open.
- `prototype_v3_final_capture_constraints_002` retains 10,260 native capture
  cases, including 3,510 aperture-refinement cases. Native early/late Liberty
  views `prototype_v3_final_native_liberty_005` parse without warnings. The
  original route has positive setup slack at the 500 MHz capacity screen in
  all five corners, but ordinary and CDC hold obligations remain open.
- `prototype_v3_native_timing_repair_001` completed a fresh route with zero
  router DRC violations after inserting hold buffers. All 481 state elements
  pass independent equivalence and the reset-corruption negative control.
  Normalized-SPEF timing still fails: SS setup is -0.27 ns at the 500 MHz
  capacity screen; conditional hold remains negative in every corner. The
  independent antenna audit reports six pin violations on five nets, while
  Magic reports zero DRC rectangles and LVS matches uniquely. This candidate
  is not selected. Its raw
  internal timing reports have unresolved SPEF-name warnings and are
  ineligible as evidence. `repair_prototype_native_timing_route_v2.py`
  re-estimates placement parasitics after netlist changes and omits raw-SPEF
  timing reports; the separate `_native_timing_repair_002` attempt is active.
- `prototype_v3_candidate_parent_alias_lvs_001` establishes assembled Magic
  DRC zero and unique LVS for the earlier digital route with provisional
  eight-driver DCO. The replay propagates only an independently verified
  zero-ohm child-port alias. Parent antenna, density, electrical integrity,
  and any successor digital/DCO integration remain unqualified.
  `prototype_v3_candidate_parent_bulk_connectivity_002` independently traces
  all 48,128 expanded MOS body terminals to the correct parent supply or
  body-bias rail. The checker preserves hierarchy scopes and exact zero-ohm
  aliases, rejects high/low shorts and unexpected or floating bodies, and
  never collapses finite resistance. Two-terminal PDK poly resistors in tie
  cells and explicit diodes are counted separately from four-terminal MOS
  devices. Attempt 001 stopped on the then-unsupported poly-resistor model;
  the versioned successor performs this offline audit without re-extraction.
  This covers the provisional assembly only; external body-bias contract,
  tap-spacing/latchup rules and EM/IR qualification remain separate.
  A separate `prototype_v3_compact_parent_frame_001` uses the provisional
  broad-fine DCO and original independently checked digital route. Its
  650-by-500 um footprint places the digital macro at (50,100), DCO at
  (450,100), and BBPD at (450,300) um. All 686 connections and nonoverlap
  checks pass. `_compact_parent_power_001` passes main-rail database
  connectivity and actual-GDS clearance checks. `_compact_parent_route_001`
  completed with router DRC zero, all 686 bindings preserved, connected main
  rails, and 369 routed nets; its global wire estimate is 172,605 um. The
  independent streamed-layout DRC/LVS audit is active. This assembly still
  needs independent signoff, density, interface extraction and final source
  selection. Versioned router v2 preserves actual input PG rectangles rather
  than hardcoding the old large-frame contacts; layout checker v2 binds
  streamed macro transforms to the pinned frame receipt.
  The first compact assembly reports 18 independent Magic met2 spacing
  rectangles despite router DRC zero. A GDS/LEF comparison identifies actual
  child via enclosures absent from the digital abstract's obstructions.
  `extend_prototype_macro_obstructions.py` adds only missing actual routing
  and cut geometry outside existing ports, preserves all original
  obstructions and the complete pin interface, and validates coverage against
  the source GDS. `_digital_GDS_obstructions_001` supplies the corrected view
  to frame/power/route attempt 002, whose route has DRC zero; its independent
  audit is active. Source GDS bytes are unchanged. The digital abstract also
  lacks antenna gate/diffusion areas, so a parent antenna result using it
  would be incomplete; no parent antenna qualification is claimed.
  `_compact_parent_alias_lvs_002` now establishes Magic DRC zero and unique
  assembled LVS with all three macros expanded. The replay propagates only
  the independently verified exact-zero-ohm child-port alias.
  `_compact_parent_bulk_connectivity_002` verifies all 48,872 MOS bodies on
  this updated assembly. Density, antenna, parent interface loading and final
  analog/digital candidate selection are still open.
- The eight-driver DCO has an SF band gap around 400 MHz in conventional
  endpoint probes. `review_prototype_DCO_band_coverage.py` checks exact
  candidate/model lineage and both measured endpoint intervals; it never
  promotes sparse brackets to tuning qualification. The seven-driver
  candidate has completed conventional extraction, geometry/junction checks,
  and exact fixed-supply passivity checks for locality-preserving full-C
  attachment variants. Its new native endpoint probes are in progress.
  The source also reveals that the additional 160 fine loads are attached to
  `mirror_turn_n[1]`, which is constant in coarse bands >=2. A separate
  `prototype_v3_DCO_broad_fine320_out8_candidate_002` experiment moves 320
  thermometer-controlled loads to the continuously switching forward node,
  removes the 36 fixed loads, and retains eight coarse-1 drivers. Its route
  completed with router/Magic/KLayout DRC zero, LVS difference counts zero,
  and antenna zero; six synthesis warnings for intentional parallel drivers
  and oscillator feedback remain. Conventional extraction is active; native
  tuning and assembled qualification are still open. Attempt 001 failed a
  source-pattern guard before launching CAD and remains retained. The
  versioned successor builder explicitly sets DRT, STA and KLayout DRC to
  four threads; `--jobs 4` alone did not constrain the completed flow's
  internal thread settings. No duplicate physical build is requested.
  The broad-fine conventional RC model and its geometry/junction checks are
  complete, and five-corner endpoint probes are active. These are fresh
  measurements of the new geometry, not transferred eight-driver results.
- `prototype_v3_tracking_configuration_proof_001/baseline/proof.log` ends
  with `Property UNDECIDED` after 3,600 solver seconds. This is neither proof
  nor counterexample and does not discharge a configuration/startup gate.
  The separate decision-phase and event-reset proofs retain their narrower
  sampled-RTL scope.
  `prototype_v3_tracking_configuration_stability_001` separately attempts the
  stability property while cutting the core to arbitrary loaded-code and
  feedback-clock inputs; it cannot prove initial seed loading.
  The strengthened `_tracking_configuration_stability_002` baseline proves
  three joint assertions in 2.04 solver seconds: stable tracked payload,
  ready configuration matching the static presets, and running fine payload
  matching those presets. The auxiliary invariants are assertions, not added
  assumptions. `_tracking_configuration_stability_BMC_control_001` checks the
  exact single-assertion inversion and finds the negative control at frame
  64 in 39.93 seconds. This discharges sampled configuration stability for
  the conservative core cut; initial seed loading and physical timing remain
  separate obligations. The original PDR reachability attempts remain intact.
  `_tracking_configuration_proof_002/baseline` proves the full-core seed and
  stability properties in 1,960.41 solver seconds, with both auxiliary
  payload assertions proved jointly rather than assumed. The actual core,
  startup controller, both handoffs and divider are retained.
  `_tracking_seed_witness_002` rejects the inverted seed assertion at frame
  1,047 in 253.30 seconds. Its deterministic 16:1 clocks and legal fixed
  presets constrain only the negative reachability control, leaving the
  successful baseline scope unchanged. The earlier general BMC timeout
  (300 seconds) and shorter 512-frame witness without a counterexample remain
  retained. These results establish sampled logical safety and reachability,
  not physical aperture or recovery/removal timing.
- `_final_capture_remaining_aperture_campaign_001` refines only the remaining
  dfrtp_2, dfrtp_4 and dfstp_2 cells (135 points, 5,265 native cases), retaining
  all prior cases. The failing fine-reset second stage uses dfrtp_2, whose
  earlier hold constraint still reflects the coarse 250 ps phase grid.
  `merge_prototype_capture_apertures_v2.py` requires disjoint complete
  five-master coverage and preserves ambiguous samples and model lineage.
  New timing views must await independently reviewed results; no constraint
  has been relaxed by assumption. Broad timing repair attempt 002 also
  remains unselected: normalized SS setup slack is -0.39 ns at the 500 MHz
  capacity screen and hold checks remain negative.
- `package_prototype_v3.py` stages only artifacts pinned by passing prototype
  qualification evidence, with explicit relative destinations. In addition
  to physical/model/integration files it requires RTL, replay and toolchain
  roles. Each `handoff_artifacts` entry has `source` and `destination` fields;
  source bytes are copied unchanged. Conflicting hashes, duplicate paths,
  traversal, metadata collisions and file/directory collisions are rejected.
  Staging never claims portability, clean replay, or release qualification.
  The current campaign was rejected before any package directory was created,
  as expected. Final clean functional/native replay remains required.
  `prototype_v3_clean_replay_isolation_control_001` verifies the container
  flags `--containall --cleanenv --no-home --no-mount
  home,cwd,hostfs,bind-paths`: both the source checkout and a host `/tmp`
  probe are inaccessible, while the explicitly bound private work directory
  is writable. This control runs no native simulation and does not qualify
  the final package replay.
- `prototype_v3_physical_core_affinity_001` restricts active task controllers
  and descendants to CPUs 0..31, the unique logical representatives of this
  machine's 32 physical cores. All original process identities and outputs
  remain intact; no native process was restarted. Future compute launches
  must retain this mask (for example `taskset -c 0-31`) as well as the shared
  CPU/RAM lease. The thread-count settings and the physical-core mask serve
  different purposes; no SMT throughput benefit has been qualified.
- The prototype unit regression contains 216 passing tests. Native waveform
  convergence, final parent loading, common gains across all 60 lifecycle
  cases, and the clean portable handoff replay remain required evidence.

The older 15-PVT/180-scenario hard-macro scope remains archived in
`requirements_v2.json`. The historical extraction research below retains its
original scope and results; the known-invalid custom spatial-C route is not
an eligible release model. Conventional hierarchical PDK extraction is the
primary route for the active prototype profile.

## Current model qualification work

`fit_prototype_native_timing_surfaces_v2.py` combines the retained cell-RC
and final cell-C observations at each measured load/slew grid point before
checking the independent off-grid observations. Reset/set assertion output
slews belong to their control arcs; clock-triggered slews belong to CLK.
`write_prototype_native_liberty_v2.py` consumes this explicit two-model fit.
These remain diagnostic views until the routed load/slew coverage, native
path correlation and CDC/reset obligations are qualified. Neither the
observed holdout residuals nor an engineering allowance prove a continuous
error bound.

The full-C DCO driver/farthest variants preserve the contracted capacitor
operator but do not preserve all cell-pin capacitance locations. The
independent `audit_prototype_C_attachment_locality.py` audit of the drive8
candidate found 1,466 of 1,668 cell-pin C endpoints relocated in the driver
variant and 1,164 in the farthest variant. The evidence is in
`build/signoff400/prototype_v3_DCO_drive8_C_attachment_locality_001`.
Their frequency spread therefore cannot qualify a physical uncertainty
bound or justify selecting a new oscillator strength. A locality-preserving
conventional model and correlation of the omitted private-conductor
interactions are still required.

`prepare_prototype_DCO_scope_controls.py` constructs a separate comparison
with cell-local C retained: the conventional model with only routed wire R
contracted to zero, and the original complete hierarchical C extraction.
It independently verifies exact device topology and signed-C identity under
that contraction. `run_prototype_DCO_scope_probe.py` measures those controls
with the lossless duplicate-row parser and its matching supply-current
control. These finite scope comparisons require the conventional finite-R
measurements as well; none alone qualifies parent loading or the complete
tuning model.

The final-route BBPD receiver is rebuilt by
`build_prototype_BBPD_receiver_RC_v2.py` and
`extend_prototype_receiver_synchronizers_v2.py`. Event aliases determine the
current wire bits; stale bit numbers are rejected by the actual sink binding.
The final-route model has 48 wire resistors, 186 wire capacitors and 68
explicit external aggressor ports. Both native polarity controls passed in
`prototype_v3_fixed_divider_local_BBPD_receiver_control_002`.

`prove_prototype_event_reset_release_v2.py` proves, on the actual isolated
candidate RTL with synchronized resets and event CDC enabled, that both
first synchronizer stages remain zero at sampled fast-reset release. Its
faulty-reset negative control fails. This supports a conditional second-stage
reset-aperture investigation; it generates no timing exceptions and proves
no analog recovery/removal bound. The evidence is
`build/signoff400/prototype_v3_event_reset_release_proof_002`.

The locality-preserving DCO diagnostic successor uses
`build_prototype_full_C_wire_R_v3.py` and
`prepare_prototype_DCO_full_C_wire_R_v5.py`. Local cell capacitors remain at
their bound routed terminals; only macro-level C attachment varies.
Its zero-wire-R device topology and complete signed-C operator match the
original extraction exactly. Each distributed dynamic C operator has a
separate exact passivity certificate with all four supply voltages fixed.
This is not a single global matrix congruence and does not qualify moving
supply rails. The evidence is
`build/signoff400/prototype_v3_DCO_drive8_local_C_wire_R_002`.

`prove_prototype_decision_update_phase_v3.py` proves that decision updates
occur only in the divided-clock high phase under its continuously enabled
capture/filter assumptions and actual constant-divider parameters. The
removed-update-enable negative control fails. Native FF/SS path fixtures
with legal high-phase updates both passed independent capture review,
using the actual 23-cell path and clock cones, routed RC and 128 supplied-TT
conditional outside pin loads. Their generated-clock source latency,
other update phases, enable withdrawal/reset and numerical uncertainty
remain open. No timing exception or full timing qualification follows from
these fixtures alone.

## Historical extraction and verification

`tools/charge_compiler` replaces the Python local-charge hot loop with C++20.
It streams aligned kernel/owner/surface/contribution byte ranges, preserves
native global event/kernel IDs, restores finite-R self-conductor pair energy,
normalizes contact residues using actual native observations, and checks native
physical integrals with the existing `1e-8 + 2e-12*max(abs(a),abs(b))` tolerance.
Length and capacitance units remain 5 nm and 1e-18 F. Signed shielding and
floating fields remain explicit. Fast math and FMA contraction are disabled.

The output remains `operators.jsonl`, `fields.json`,
`collapsed_matrix_ledger.json` and the established shard assessments. The merged
`operators_manifest.json` carries local-to-global field maps; consumers must
apply them. No plain concatenation of shard-local fields is valid.

The retained two-million-kernel prefix took 187.1 s with the independent Python
reference and 16.7 s with 16 compiled workers (11.2× for this sample). Every
operator matched the Python reference. Compiled timings at 1/8/16/32/64 workers
were 81.0/17.2/16.7/20.4/25.9 s. These are single-run prefix measurements; this
prefix contains area/edge contributions and does not qualify the full coupling
trace or predict its scaling. Synthetic controls separately cover the other
kernel kinds and signed shields. Small jobs can be slower because each worker
loads the complete node dictionary.

The full controller also uses a compiled parallel sparse event index and bounded
parallel file reads for **ordinary SHA-256**, consumed in byte order. Hashes are
identical to sequential hashlib, not a replacement hash format. Read buffers
are bounded; file identity/size/timestamps are checked during hashing. Disk and
network throughput remain part of the measured check cost.

Run on the host with Python 3, NumPy and GCC supporting C++20:

```sh
make signoff400-test
python3 verification/signoff400/benchmark_charge.py \
  --trace build/timing400/prototype_001/filled_capacitance_004/trace \
  --output build/signoff400/benchmark_NEW --kernels 2000000
make signoff400-charge SIGNOFF400_CHARGE_OUTPUT=build/signoff400/charge_NEW
```

Use `SIGNOFF400_WORKERS=16` to reproduce the prefix's measured best worker count.
The full-data attempt `build/signoff400/compiled_charge_003` used 16
workers; its bounded-memory continuation is `compiled_charge_004` (see below). Attempt 002 failed on a native self-conductor SIDEWALL with no rule
entries (retained kernel 50400955). The compiled implementation now treats
empty SIDEWALL/HALO rule collections as zero terms, matching the independent
Python reference, while required scalar/geometry records remain checked.
Regression controls compare both empty-rule kinds against Python. Errors now
include kernel ID and kind. Attempt 001 was stopped during hashing to introduce
the parallel I/O/index algorithm, before any operator compilation. All attempts
retain their records; the new attempt still requires full-data validation.

Benchmarking compares actual retained native data to the independent Python
reference, then measures 1/8/16/32/64 workers. The default is 32 workers; 64 is
eligible only with ≥10% measured throughput improvement over 32 and adequate
RAM. Prefix benchmarks do not establish full-file scaling. Build, indexing,
metadata, compilation, merging and hashing all count toward the 12-hour check.
All output directories are fresh; retained attempts are never overwritten.

Shared process leases account for internal tool threads and requested RAM:
32 default CPU slots, 200 GiB aggregate reservation, 32 GiB host reserve and
4 GiB address-space limit per compiler worker. The explicit 64-worker option
needs a smaller per-worker allowance, e.g. `--worker-memory-gib 2`. Resource
requests above the aggregate budget are rejected. Legacy jobs outside this
controller do not acquire these leases; available-memory admission still applies.
Large native transients retain exclusive legacy admission until concurrent
solver/memory controls justify expansion. No simulator is made multithreaded
merely by raising an environment variable.

Each completed shard pins the compiler, source, range configuration, metadata
and artifacts. The controller pins the full retained trace and original
extraction dependencies. Compilation success explicitly leaves physical-domain
completeness, passivity and runtime-model eligibility false.

## Temperature-aware electrical qualification

`requirements.json` is a new profile rather than an edit to the frozen prototype.
`common.py` expands the matrix; `native.py` requires exact temperature-matching
decks and final-loaded extraction/mapping/solver/equation receipts. Each large
transient retains 48 hours including preparation/assessment and the full-equation
scaled residual bound of 1e-12. Timeouts are inconclusive; automatic identical
retries remain disabled.

`loop.py --models MANIFEST --output NEW --ki KI --kp KP` requires a model
manifest with `corner`, `temperature_c`, `supply_v`, profile/source/final-physical
hashes, and qualifying receipts covering the exact DCO table and detector RTL.
Every model receipt must match all three PVT coordinates. Unknown frequency
lookups halt the driver. Synthetic models require `--diagnostic` and cannot
qualify. Historical prototype model manifests cannot be relabeled.

`search_gains.py --models MANIFEST_1 ... MANIFEST_15 --output NEW` evaluates
PVT groups concurrently using shared leases. Start at KI=4/KP=0, then select
the lowest passing KI followed by KP from the established search grid. A driver
failure or uncovered model stops gain expansion. All 180 scenarios must pass
with one pair; the original acquisition, frequency, sustained-phase, cycle-slip
and fine-code criteria remain unchanged.

## Campaign audit and deliverables

```sh
make signoff400-prepare SIGNOFF400_OUTPUT=build/signoff400/campaign_NEW
make signoff400-audit SIGNOFF400_OUTPUT=build/signoff400/campaign_NEW
```

Preparation freezes source/physical identities, imports the scoped passing
geometry receipt, and emits the complete blocked functional matrix. The audit
returns nonzero until direct matching evidence closes every gate. It checks
receipt hashes, input/artifact hashes, candidate/profile identities, all 15 PVT
points, complete scenario coverage and a common KI/KP pair. Diagnostic,
synthetic, stale or missing evidence never qualifies.

Manifest `evidence` maps gate names to lists of `{path, sha256}` receipts.
Receipts carry `profile_sha256`, `candidate_source_sha256`,
`candidate_physical_sha256`, nonempty `input_sha256` and `artifacts`, and the
gate's direct passing flag. PVT receipts additionally require `corner`,
`temperature_c`, `supply_v`. See `audit.py` for the exact gate flags.

Only after the six prerequisite gates pass may `package.py --manifest MANIFEST
--output NEW` collect evidence-pinned GDS, LEF, logical/powered netlists,
parasitics, timing views, constraints, calibration, models and integration
instructions. Each role contains a nonempty list of artifact paths. Packaging
verifies copied hashes and generates the final reproducible-handoff receipt.
Add its path/hash as `handoff_receipt` to the campaign manifest and re-audit.

Jitter, power and output-load capability must be measured and published without
inventing application limits. Final integration instructions must state the
1.8 V-only supply scope, characterized load/input/reset bounds, invalid-clock
intervals, startup programming and any remaining chip-level supply/density
obligations. Other output modes, automatic acquisition, voltage variation and
chip/shuttle submission are outside this qualification profile.

## Startup withdrawal correction

`prove_startup.py` inserts verification-only assertions into the exact startup
RTL and runs temporal induction with arbitrary inputs after the first reset.
It checks programmed bounds, frozen captured settings, failure containment and
absorption, invalid-program/change rejection, and two consecutive matching seed
observations for each LOAD visit. It requires rejecting counterexamples for
single-observation, invalid-fine-range and ignored-program-change mutants.
This sampled REFCLK proof uses `async2sync`; it does not establish physical reset,
metastability, cross-clock handoff or macro timing bounds.

The first proof (`build/signoff400/startup_invariants_001`) found a real early
START-withdrawal counterexample. `tb_programmed_startup_early_disable.v`
independently reproduces it: disabling before RUN retained `settle_count=2`,
allowing READY after one new LOAD observation. The corrected START withdrawal
clears both counters. `startup_invariants_002` proves the corrected controls
and rejects all three mutants; `startup_early_disable_002` passes the focused
simulation. The original 38 integrated controls and fresh allowed-cell mapping
pass in `startup_corrected_digital_001`.

```sh
python3 verification/signoff400/prove_startup.py \
  --container build/apptainer/openpll-release-modern.sif \
  --output build/signoff400/startup_invariants_NEW
```

**The corrected RTL requires a new matching physical implementation.** The
retained filled-layout extraction remains evidence for its original geometry;
it cannot qualify the changed startup logic. New mapping equivalence, digital
routing, assembled geometry, electrical extraction and timing evidence must
match before handoff. The proof receipt deliberately leaves
`digital_startup_qualified` and `release_qualified` false.

The raw group-preserving R-domain index completed at
`build/timing400/prototype_001/filled_domain_index_006`: 1,465,072 private nodes,
639,629 tile snapshots and 914,860 contacts, with exact native record totals.
`build/signoff400/native_group_audit_001` finds 371 repeated conductor labels;
only 68 have equal exact printed-node/incident-edge fingerprints. These hashes
include node coordinates/status and full incident-edge multiplicity. They are
conservative diagnostics; unequal fingerprints are not automatically proof of
a physical network difference. Neither equal nor unequal fingerprints select
final-export lifetimes or establish tile/contact coverage. Do not attach all
raw snapshots or silently take the last conductor-name entry.

## Explicit candidate assembly inputs

`build_assembly_frame_v2.py` replaces historical fixed digital-macro paths with
explicit `--digital-route`, `--digital-checks`, and `--placement` inputs. The
`candidate_macro.py` guard verifies current-source placement identity, pinned
route ancestry (including intervening repair stages), routed equivalence and
its negative control, matching independent layout evidence, and exact selected
GDS/LEF/database hashes. Nonpassing or unrelated checks cannot supply a macro.
The three macro view selections are retained in the frame receipt;
`build_parent_power_v2.py` consumes those exact selections instead of historical
paths. Original runners and their receipts remain unchanged.

After independent checks pass, run these with the same CAD container/tool
Python used for routing (the power stage also needs KLayout):

```sh
python3 verification/prototype400/build_assembly_frame_v2.py \
  --digital-route build/signoff400/startup_corrected_local_antenna_001 \
  --digital-checks build/signoff400/startup_corrected_local_antenna_audit_001 \
  --placement build/signoff400/startup_corrected_placement_001 \
  --output build/signoff400/startup_corrected_frame_NEW
python3 verification/prototype400/build_parent_power_v2.py \
  --frame build/signoff400/startup_corrected_frame_NEW \
  --output build/signoff400/startup_corrected_power_NEW
```

Neither assembly framing nor database rail connectivity closes assembled
DRC/LVS/antenna/density, supply integrity, final electrical extraction or timing.

The first corrected route (`startup_corrected_route_001`) completes routing
with zero routing violations and nominal RC extraction. Independent checks
confirm zero Magic DRC rectangles, 48,636/48,636 connected power pins and
489-state routed Boolean equivalence, but reject top-level output pin matching
(`TRACKING`/`BBPD_RESET_N` alias) and three antenna nets. This route is not an
assembly input. `repair_output_alias.py` checks that exact measured nonpass,
requires the audited Boolean proof, isolates the reset output, renames its
source net to avoid a Verilog alias collision, reroutes and applies antenna
repair. Attempt `startup_corrected_alias_001` stopped during receipt validation because
the container lacked the historical `/work/OpenPLL` mount; no layout was mutated
and no native repair started. Its launch log and preflight record are retained.
Attempt `startup_corrected_alias_002` corrects that bind and uses a reduced outer
42,000-second cap including preflight; fresh independent checks are queued as
`startup_corrected_alias_audit_002`. All physical gates must pass.

`repair_measured_antennas.py` is also prepared for any residual antenna-only
failure after a uniquely matched LVS result. It parses exact violated pin
sections, reconciles both net and pin counts with the audit, and exchanges
nearby filler cells for matched-footprint qualified diode cells. It refuses a
missing target, changed pin connectivity, unsafe Tcl name, unavailable local
filler or unequal footprint. It retains a pin-specific plan and reroutes with
a total 12-hour budget. No old instance names or DLF bit numbers are hard-coded.
`test_measured_antennas.py` checks selection, layer deduplication, missing context
and Tcl-name handling. Additional diode loading still needs final timing and
analog characterization, plus independent layout and equivalence checks.


## Compiled native R export reconciliation

`audit_r_export.py` builds `tools/native_r_export_audit/main.cpp` with C++20,
fast math disabled and FMA contraction disabled. It checks group/branch alignment,
both native branch incidences, printed node name/coordinate multiplicities,
resistor multiplicity and total exported incidence per printed node. Resistance
uses the native float32 division by the export's resistance scale, followed by
native `%g` six-significant-digit printing. Equal printed snapshots remain
ambiguous. Unpaired branches, inconsistent incidence, nonfinite values,
malformed quotes and truncated groups fail. Fresh outputs, pinned sources and
artifacts, input identity checks, an 8 GiB worker cap, shared admission and the
whole 12-hour check budget apply. The existing charge compiler is unchanged.

```sh
python3 verification/signoff400/audit_r_export.py   --native build/timing400/prototype_001/filled_domain_004/trace/R_provenance.log   --export build/timing400/prototype_001/filled_domain_004/trace/Prototype400_FilledCapacitanceView.res.ext   --output build/signoff400/native_r_export_NEW
```

The first full comparison completed in 77.7 seconds including hashing/build:
18,414 snapshots, 18,114 matching groups, 999,187 exported node cards and
1,158,216 resistor cards. All 18,043 conductor labels have at least one match;
17,972 have one and 71 have multiple matches. This timing is for this diagnostic,
not an apples-to-apples speedup over the earlier Python fingerprint audit.
`native_r_last_group_check_001.json` further confirms all last groups match.
The old 999,187-node index therefore agrees with final **printed** topology;
the earlier raw-record count discrepancy does not by itself prove lost final
nodes. Complete raw snapshot retention still permits provenance/coverage audits.
Capacitance/device cards, physical lifetime equivalence, contact impedance and
voltage-domain coverage are outside this comparison; runtime eligibility and
release qualification remain false.

The whole-export extension is `audit_r_export_v2.py` with immutable
`main_v2.cpp`. It additionally sums all last-snapshot node and resistor card
multisets and compares them to the **entire** native export. This catches an
unrepresented exported node or cross-label double counting even when each
individual group appears to match. `native_r_export_002` confirms both complete
multiset equalities on the retained data (39.1 s including hashing/build, with
warmer inputs). Version 1 remains intact with its original evidence. Neither
version establishes physical voltage-domain or capacitance/device coverage.

## Corrected assembled implementation

The corrected digital macro at `startup_corrected_local_antenna_001` passes
independent Magic DRC0, unique LVS, zero antenna violations, all 48,652 power
pins connected and 489-state routed equivalence. The explicit candidate frame
(`startup_corrected_frame_001`) passes all 686 macro pin bindings. The first
power attempt stopped on a missing Python binding before CAD or output creation;
its source/log are retained. `startup_corrected_power_002` uses the pinned
Librelane Python and passes database rail connectivity and GDS port clearance.
`klayout_compat.py` aliases the available `klayout.db` database API to `pya` for
retained helpers; backend extension and compatibility code are pinned.

`startup_corrected_parent_route_001` finishes with zero router DRC violations
and exact macro bindings. `check_parent_layout_v3.py` verifies explicit
`--frame`/`--power` ancestry and selects the actual macro views, avoiding the
historical digital paths. `startup_corrected_parent_layout_001` passes assembled
Magic DRC0 and unique LVS with all three macros expanded and source geometry
and labels preserved. Its antenna, extracted-model and power-integrity flags
remain false. `parent_macro_views.py` tests reject stale or unrelated frames
and power databases. Candidate ancestry also handles hash-pinned side receipts
with a different schema without mistaking them for the placement chain.

The next measurement campaign is `startup_corrected_parent_geometry_001`, using
`check_parent_geometry_v3.py`: min/nom/max parent RC, independent forming/native
antenna and stock PDK density execution. Database-only child helpers run through
`run_klayout_script.py` under the same KLayout backend. Antenna/density applicability,
final fill, supply integrity and final complete electrical extraction still
require direct qualifying evidence. The retained old filled-layout charge run
continues as algorithm/native-data validation and cannot qualify this changed
physical candidate.


## Bounded-memory charge continuation

Attempt 003 stopped when a worker finished numerical compilation but exhausted
its 4 GiB allowance constructing the entire collapsed-ledger JSON tree and
serialized string. Fourteen completed shard receipts remain intact. Immutable
`main_stream_ledger.cpp` writes the same sorted ledger incrementally;
`test_streamed_ledger.py` compares all numerical artifact bytes against the
original and checks a 200,000-row writer under a 64 MiB address-space limit.
`resume_charge.py` rehashes all retained native inputs and completed shard
artifacts, verifies ranges, metadata, units and native proof flags, links valid
completed shards without changing them, and compiles only incomplete shards
with `compiled_charge_v2.py`. The whole continuation has a fresh 12-hour limit;
merging runs separately with a 32 GiB allowance and shared admission. Real
small-data continuation and receipt rejection controls are in
`test_resume_charge.py`. Production `compiled_charge_004` completed its two new shards but its Python
merge failed during final serialization; see the compiled merge section below.
No completed full-data compilation, complete-model or runtime qualification is claimed.

## Assembled antenna repair and planning

The corrected unprotected assembly measured 46 forming violations on 44 nets
and 1,449 native antenna feedback entries. Stock density execution returned zero
but reported below-minimum layer densities; that is a density failure.
The compiled integer bank planner matches all 44 independent exhaustive sites.
Its cold planning campaign took 28.9 s including build/setup, compared with
8.10 s for just the old KLayout search; this is not an end-to-end speedup.
Reusing a hash-verified compiled binary produced an identical plan in 9.49 s,
including 1.43 s search. These measurements have different cache/setup costs.

The first placement attempt stopped before routing because signal IO shapes
were not present at that pipeline stage. Version 4 retains the full placement
check in `route_parent_v6.py` after IO placement. The resulting
`startup_corrected_protected_route_003` passes router DRC0;
`startup_corrected_protected_layout_001` passes assembled DRC0 and unique LVS.
The 44 banks reduced forming violations to 15 and native feedback to 497.

`add_targeted_parent_banks_v3.py` uses existing M1 supply rails to add 60 diodes
and 15 taps on those 15 residual nets. `startup_corrected_targeted_banks_002`
passes router DRC0, retains all macro/cell placements and pin bindings, and
verifies 354 background routes unchanged. Its inherited scope prose says ten
nets; the explicit target list and counts correctly record fifteen. The prior
attempt stopped on a DEF serialization difference: OpenROAD added `SPECIAL`
to existing VPWR/VGND ports. `def_pin_equivalence.py` permits only this optional
metadata for correctly bound INOUT POWER/GROUND ports; all other pin bytes
remain checked. Negative controls cover geometry, net, use and signal changes.
The route ancestry helper verifies the targeted route back to its exact power
and frame sources. Fresh assembled checks are
`startup_corrected_targeted_layout_001` and antenna/RC/density measurements are
`startup_corrected_targeted_geometry_001`; neither is adopted before checking.
All added diode loading requires final electrical characterization.


The fifteen-net repair passes full assembled DRC0 and unique LVS; native antenna
feedback is zero, while forming retains one M3 violation on `fine_therm[101]`.
The final local-bank derivative is `add_targeted_parent_banks_v6.py`. It checks
localization against the actual streamed route, includes the prior additional
banks as occupied sites and uses a source-derived instance namespace. One
preflight attempt stopped because the stream receipt has no artifact map; one
native attempt stopped at a background-route count before routing. Both logs
are retained. `freeze_parent_routes.py` now counts both prior FIXED routes and
newly frozen ROUTED routes; its tests check repeated application and reject
duplicate nets. `startup_corrected_last_bank_003` adds four diodes and one tap,
passes router DRC0 and verifies all 368 background routes unchanged.
`startup_corrected_last_layout_003` passes full assembled DRC0 and unique LVS.
Its fresh geometry measurements are `startup_corrected_last_geometry_003`.

`fill_parent_v6.py` requires matching, passing forming/native antenna evidence
before generating fill and pins its exact route and KLayout backend. It retains
all original drawing geometry and labels. `startup_corrected_fill_001` waits
for those checks; its queued independent layout checks are
`startup_corrected_filled_layout_001`. Fill generation is not density or final
parasitic qualification. `audit_parent_topology_v3.py` selects macro ports and
offsets from the exact current-source frame instead of historical LEF paths.
The regression suite passed 65 tests, plus two new route-freezing controls.


The latest unfilled corrected assembly passes both forming (zero) and native
antenna (zero feedback) checks. This is geometry-screen evidence, not a claim
that every foundry rule or electrical model is qualified. The queued filled
geometry closure is `startup_corrected_filled_closure_001` using
`close_parent_geometry.py`: it reconciles exact GDS/route pins, repeats the
complete macro-port topology screen and independently recomputes all stock
PDK density windows from raw measurements. A zero density process exit alone
never passes this closure. `extract_filled_loading_v5.py` supports the current
KLayout backend for the subsequent separate fill-aware electrical view.


The guarded continuation queues `startup_corrected_filled_loading_001`, followed
by `startup_corrected_filled_domain_001`, only after filled geometry closure
passes. These stages inherit the fill campaign's original 12-hour check budget;
queueing does not reset it. Raw signed capacitance, floating nodes, complete
external boundary labeling and native retained R provenance remain required.
The old compiled-charge continuation remains independent algorithm-validation
evidence; it cannot qualify this corrected filled geometry.


## Direct native-to-compiled path for the corrected layout

`trace_filled_capacitance_v3.py` retains the controlled native C/device-card
comparisons and exact signed trace, then terminates with a pinned native-trace
receipt. It does not run the old serial operator compiler. Its original
12-hour extraction/check budget still includes waiting, native extraction,
comparison and artifact hashing. Native extraction and operator compilation
are separate explicitly scoped checks; no numerical-qualification flag is
inferred from successful tracing.

`compile_native_charge_v2.py` consumes that completed receipt directly. It checks
the exact generator source, required native proof flags, completion marker and
all consumed native artifact hashes, uses the bounded-ledger C++ compiler,
parallel aligned-stream indexing and ordered SHA256, and runs the compiled merge in a
separate 16 GiB bounded process. A fresh 12-hour compilation budget includes
all verification, build, indexing, metadata, shards, merging and final hashes.
Its controls execute the 27-kernel native-format fixture end to end and reject
changed artifact bytes, missing proof, stale generator code and synthetic
receipts. This removes the old requirement to experience a serial timeout
before invoking the compiled path. It does not claim a full electrical model.

```sh
make signoff400-charge-native SIGNOFF400_WORKERS=16 \
  SIGNOFF400_CHARGE_SOURCE=build/signoff400/CORRECTED_NATIVE_TRACE \
  SIGNOFF400_CHARGE_OUTPUT=build/signoff400/CORRECTED_COMPILED_NEW
```


## Corrected filled geometry closure and current campaign

`startup_corrected_filled_closure_001` passes full assembled Magic DRC0 and
unique LVS, zero forming violations, zero native antenna feedback, all 743
macro-port probes with no missing connections/shorts/splits, and all 175 stock
PDK density checks independently recomputed over 195 raw tiles. All original
geometry and labels remain preserved. These are geometry checks, not complete
process, timing, power-integrity or extracted-electrical qualification.

`make signoff400-prepare` now uses `prepare_candidate_v2.py` with explicit
`SIGNOFF400_CLOSURE` (default the corrected closure) and the pinned CAD Python
inside the release image. `SIGNOFF400_CAD_PYTHON` can override that invocation.
Auditing also runs in this environment so pinned `/nix/store` executables can
be verified. The original implicit historical preparer remains intact.
The first host preflight could not resolve the CAD interpreter; the first
CAD preflight then caught the absence of the temperature requirements file
in geometry-only receipts. Both preflight logs are retained.

The corrected preparer requires every current RTL/dependency identity and a
recognized, unchanged geometry profile. It explicitly imports only geometry
from the prototype profile into the fifteen-PVT signoff profile, recording
both identities and `temperature_qualification_imported=false`. Wrong RTL,
unknown geometry profiles, changed GDS and nonpass density are rejected.
`campaign_corrected_001` pins the exact corrected filled GDS and contains all
180 required scenarios. Every qualifying gate remains open; geometry is never
promoted into qualifying electrical or temperature evidence. The tests cover
that distinction. The regression suite passed 69 tests plus two new campaign
preparation controls.

The live current-candidate electrical path is
`startup_corrected_filled_loading_001`, then retained R-domain extraction
`startup_corrected_filled_domain_001`, followed by native owned-C tracing
`startup_corrected_filled_capacitance_001` using version 3. The latter stops on
upstream failure and does not invoke serial Python operator compilation.
All three inherit the fill campaign's original extraction/check budget.


## Native wire creation geometry and interpolation limits

`audit_r_geometry_v3.py` builds the C++ auditor in
`tools/native_r_geometry_audit/main_v3.cpp`. It streams indexed nodes/tiles and
all provenance/creation groups, checks both branch incidences, exact native
node identities, creation values/types/status, tile identity and resolved
breakpoints. Pointer reuse and moved representative node coordinates are
controlled explicitly. It retains every snapshot and never chooses final
lifetimes or attaches capacitors by nearest-node distance. The first audit
stopped on an exact zero-resistance native `ndiode` wire; version 2 counts zero
branches without claiming a runtime treatment. Failed attempts remain intact.

`native_r_geometry_003` completed on the retained historical data in 86.2 s
including hashing/build. It accounts for all 18,414 snapshots, 1,465,072 nodes,
639,629 tiles and 1,767,906 branches. All wire-branch creation identities match; contact creation geometry is outside this audit.
There are 1,878 zero-valued wire branches and no zero-valued contact branches.
However, 5,631 native branches have creation-axis breakpoints outside their
recorded tile extents: metal3 4, metal4 2, ndiff 1,249, pdiff 2,950, nwell 966
and pwell 460. Rectangular interpolation therefore remains nonpass; this audit
does not relax the extent check, move the native points, or qualify an RC
model. Contact impedance, snapshot selection, substrate/domain coverage and
zero-resistance runtime handling remain open. Six controls cover corruption,
malformed records, repeated snapshots, zero resistance and the distinction
between creation identity and valid interpolation. The old dataset only
validates the algorithm; corrected-layout extraction must be checked separately.

## Compiled charge merge

The two missing shards of `compiled_charge_004` completed successfully, bringing
all sixteen shards to direct native-integral checks. Its separate Python merge
then exhausted the 32 GiB bound serializing the final ledger, after 7,297.9 s
for the whole continuation. All completed shards and the failed merge remain
intact. No overall completed charge-compilation receipt is claimed.

`tools/charge_compiler/merge.cpp` streams local fields and ledger rows, retains
the exact ordered local-to-global maps and numerical addition order, and
streams the final sorted ledger without building another complete JSON tree
or dump string. Fast math and FMA contraction are disabled. The four merge
controls compare every artifact against the independent Python implementation,
exercise cancellation-sensitive sums and bitwise numeric comparisons, reject
malformed arrays/out-of-range IDs, and execute actual compiled-shard receipt
verification including a changed-artifact rejection.

`benchmark_charge_merge.py` pins and rehashes every consumed field/ledger and
shard receipt, checks native shard proofs/metadata/range coverage, and applies
shared admission and a 16 GiB bound. The full-data run is
`compiled_charge_merge_001`. It is a separate merge-algorithm check: it does
not rehash all native source traces and cannot substitute for full native
qualification. Build, input/artifact hashing and merging count toward its
12-hour bound. No full-data speedup or complete-model result is claimed while
that run is in progress.

The corrected geometry's `startup_corrected_filled_loading_001` has completed
raw extraction with 41,836,122 signed capacitor records; floating nodes and all
signed values remain preserved. Retained native R extraction is now running.
The record count alone does not establish physical-domain or model completeness.


`compile_native_charge_v2.py` and the `signoff400-charge-native` Make target now
use the same controlled compiled merge for future corrected-layout work. Its
compiler, source, binary, configuration and summary are included in the final
compiled evidence; build and merge remain inside the whole compilation budget.
The earlier direct controller is retained as the independent small-fixture
Python-merge reference. The complete regression suite passed 81 tests; the
two direct-controller controls were rerun successfully after this integration.

A successful `compiled_charge_merge_001` will still require full retained
native-input and shard-artifact verification before an overall completed
charge-compilation receipt can be produced. Its intermediate assessment must
not be relabeled as such a receipt. The corrected physical candidate is also
a different geometry and still needs its own complete native extraction.


## Completed compiled merge and inherited-budget verification

`compiled_charge_merge_001` completed on the full retained data. It consumes
68,325,170 local ledger rows, produces 49,753,395 global rows and 2,400,607 global
fields, and accounts for 298,366,009 kernels and 822,707,320 signed operators.
The merge itself took 599.0 s; the whole merge-algorithm check took 721.9 s
including build and consumed-input/output hashing. Child peak RSS was
4,284,724 KiB (about 4.1 GiB), within the 16 GiB limit. The earlier Python merge
failed at its 32 GiB bound; there is no completed legacy run from which to
claim an apples-to-apples full-data runtime speedup.

`verify_charge_merge_maps.py` independently compares the full global field
list and every local-to-global map against the retained Python producer's
completed outputs from before its final serialization failure. The reference
controller must be dead and its producer identity must match. This comparison
checks exact field identities, integer/range validity and stable artifact
hashes. `compiled_charge_maps_001` passes all 2,400,607 global fields and
14,435,258 local fields across all sixteen maps (120.2 s including hashing).
This does not compare the full global numerical ledger; controlled small-data
ledger comparisons remain separate from this full mapping check.

`finish_charge_merge.py` now runs `compiled_charge_005`: it inherits attempt
004's original deadline and rehashes every native input, all shard inputs and
artifacts, and all compiled-merge inputs/artifacts. Physical files referenced
through multiple aliases are hashed once, with alias provenance retained.
It rejects a live prior controller, exhausted original budget, incomplete
native artifact roles, conflicting identities, changed data and unverified
operator-manifest references. It reuses all sixteen shards and emits canonical
operator/map paths without resetting the check budget or recompiling shards.
The two controls include an actual small compiled-shard/merge continuation,
changed-native rejection, live-controller rejection and expired-budget
rejection. Its eventual receipt will still leave physical-domain completeness,
global passivity and runtime eligibility false. It completed full-input verification in `compiled_charge_005`; the result remains
operator-compilation evidence pending physical voltage-domain attachment.

For the corrected physical candidate, domain indexing and the two compiled
R audits are queued behind the owned native extraction:
`startup_corrected_domain_index_001`, `startup_corrected_r_export_001` and
`startup_corrected_r_geometry_001`. They do not consume partial native files.
No historical algorithm result qualifies the changed layout.


The complete suite now passes 84 tests (`make signoff400-test`), including the
inherited-budget finalization and full-map comparison controls. Production
`compiled_charge_005` continues rehashing all retained data; corrected native
R extraction is still live. Neither a successful map comparison nor this
regression result closes an electrical, PVT, timing or handoff gate.


## Routed timing gap and physical repair

`check_candidate_timing.py` screens the selected current-source digital route
using three extracted RC views and the supplied TT25C/1.80V, FF−40C/1.95V and
SS100C/1.60V libraries. Up to four CAD processes run concurrently, with four
threads per process and shared CPU/RAM leases. These libraries are not the
required fifteen nominal-voltage PVT points. Assumed output loads (5 fF),
clock uncertainty (150 ps), conditional diode capacitance, and omitted final
parent fill/interface loading prevent timing qualification.

The earlier placement fixture excluded every pair of distinct clocks,
including the related oscillator and divided feedback clocks. The new screen
preserves PLLOUT↔FINECLK paths and retains explicit asynchronous-group/reset
limitations. A real Tcl control checks both related directions and unrelated
exceptions; report controls reject negative slack, missing fast/divided groups
and absent/unannotated RC coverage.

`startup_corrected_digital_timing_screen_001` is nonpass. At TT25C/1.80V,
fast-clock setup slack is +0.7385 ns or better across these RC views, but
related divided-clock hold slack reaches −1.4611 ns. One path enters the
intended tracking synchronizer; two others enter actual BBPD decision
registers. Those data paths are not excluded. Slew/capacitance limits also
fail, and 100 unannotated drivers need explicit connectivity classification.
SS100C/1.60V additionally fails setup, but is outside the 1.80V target profile
and must not be relabeled as a required-PVT failure or success.

`repair_candidate_timing.py` retains the related-clock constraints, uses
routed RC and the supplied electrical limits, preserves taps/endcaps, restricts
masters, and runs post-route resizing/hold repair before fresh routing. The
first route, `startup_corrected_timing_repair_001`, resized 323 cells and added
109 hold buffers. It passes router DRC0, database rail connectivity and
independent digital layout checks. `startup_corrected_timing_repair_audit_001`
also proves all 489 state primitives' transition/output functions against the
current-source mapping and rejects the corrupted-reset control. This route
still has a reported capacitance violation and remains unselected. The fresh
nine-case screen is `startup_corrected_digital_timing_screen_002`.

`audit_timing_annotation.py` checks every unannotated pin against actual native
database connectivity and the constant-source functions in every supplied
library. It distinguishes outputs without logical fanout and verified tie
sources from unresolved active/multiple-driver nets. No clockload-name-based
waiver is allowed. `startup_corrected_timing_annotation_001` is in progress;
classification never qualifies power noise, cell admittance or full timing.

The owned-C tracer on the previous corrected assembly was cancelled while
waiting, before a native child started; its stop receipt is retained. Changed
digital geometry will need new assembled extraction. The running retained-R
trace and its queued indexing/audits continue as model-algorithm evidence.
No physical candidate is adopted from timing/Boolean diagnostics alone.

## Completed retained operator revalidation

`compiled_charge_005` completed full native/shard/merge artifact verification
in 3,620.2 s, preserving attempt 004's original whole-check deadline and reusing
all sixteen completed shards. It accounts for 298,366,009 kernels,
328,779,389 events and 822,707,320 signed operators. All native inputs and every
shard artifact were rehashed; canonical operator paths and complete field maps
are pinned. No shard was recompiled during finalization. This is completed
operator compilation for the **historical** geometry, not qualification of the
current or repaired macro. Physical-domain attachment, global passivity and
runtime eligibility explicitly remain false.


The renewed screen `startup_corrected_digital_timing_screen_002` shows the
first repair clears the related-clock hold failures in all nine diagnostic
cases. At TT25C/1.80V, divided-clock hold slack is +0.1809 ns or better and
setup slack is +0.2646 ns or better over the three RC views. Electrical limits
still fail, and the supplied 1.60V slow view still fails setup. Neither result
qualifies the required nominal-voltage temperature/corner grid.

`startup_corrected_timing_annotation_001` accounts for all 100 unannotated
drivers: every one has no logical fanout. No active transition net remains
unresolved in this annotation screen. This classification does not waive
capacitance, slew, waveform, power or PVT requirements. The next annotation
check is `startup_corrected_timing_annotation_002` on the repaired route.

`repair_candidate_timing_v2.py --mode electrical` preserves the hold-buffer
work and repairs electrical limits without another setup/hold optimization
pass. `startup_corrected_timing_repair_002` resized another 155 cells and added
three buffers. It passes router DRC0, power connectivity, independent digital
layout checks and the same 489-state equivalence/negative control. Its own
final RC report still flags `$abc$74280$auto$blifparse.cc:397:parse_blif$75158/Y`
(`sky130_fd_sc_hs__a21oi_4`, net `$abc$74280$new_n2158`) at 0.37 pF against a
0.20 pF limit. Resizing has not resolved this load; the next step is explicit
inspection/isolation of that measured fanout. The fresh nine-case screen is
`startup_corrected_digital_timing_screen_003`. Both repaired routes remain
unselected pending closure. The complete regression suite passes 88 tests.


`startup_corrected_digital_timing_screen_003` confirms the second repair keeps
TT25C/1.80V setup/hold positive over all three freshly extracted RC views:
PLLOUT setup ≥0.7325 ns, PLLOUT hold ≥0.1385 ns, FINECLK setup ≥0.2545 ns and
FINECLK hold ≥0.1829 ns. The nominal-RC case has no reported electrical
violations. The min/max RC cases still show 1.51/1.60 ns input slew against a
1 ns limit and 0.31/0.33 pF on the same A21OI output against 0.20 pF. The slew
sink `$abc$74280$auto$blifparse.cc:397:parse_blif$76152/A` is on that same
`$abc$74280$new_n2158` net. Acceptance uses these clean-process RC extractions;
the immediate repair log's 0.37 pF report is not used as final loading evidence.
`startup_corrected_timing_annotation_002` independently confirms all 100
unannotated drivers on repair 001 have no logical fanout. No repaired route
has been adopted and no fifteen-PVT timing gate is closed.


The measured-load ECO isolates the remaining A21OI load with one BUF16,
transferring its twelve original sinks onto the buffer output. The library
function and drive limit are checked before modifying connectivity, and the
measured slew/capacitance rows are resolved to nets before deduplicating the
repair. Three parser/identity controls pass. The first attempt rejected the
parenthesized library identity before CAD; the second inserted the buffer but
failed incremental router pin access on an existing flip-flop reset. Both
failed attempts remain recorded. `buffer_measured_loads_v3.py` uses a fresh
route of all signal nets after legalization; its current work directory is
`startup_corrected_load_buffer_003`, followed by independent checks in
`startup_corrected_load_buffer_audit_003`. No ECO is selected before renewed
equivalence, physical checks and clean-process timing extraction. Parent
assembly, fill and electrical extraction must then be rebuilt for the selected
macro.


`startup_corrected_load_buffer_003` completed fresh routing with zero router
DRC violations and connected database power pins. All 489 transition/output
functions match the mapped RTL, including rejection of the corrupted-reset
control. Independent layout checks are running; the nine-case timing screen
`startup_corrected_digital_timing_screen_004` is queued behind a passing
layout receipt. The full regression suite passes 91 tests. These results do
not select the candidate or close the final timing and electrical gates.


The independent layout result for load-buffer candidate 003 is DRC0, unique
LVS and all 46,528 power pins connected, with three antenna violations on
`$abc$74280$new_n1685`, `$abc$74280$new_n1709` and
`$abc$74280$new_n2380`. The timing waiter correctly stopped before launching
screen 004. `repair_measured_antennas_v2.py` adds one local same-footprint
diode per measured violating pin without moving existing cells, uses a
source-specific instance namespace with collision guards and reserves eight
CPU slots/eight GiB. Its three parser/namespace controls pass in addition to
the earlier 91-test suite. Work `startup_corrected_buffer_antennas_001` is
followed by independent checks in `startup_corrected_buffer_antennas_audit_001`;
screen 004 now waits for that candidate to pass. All routes remain unselected.


The three local diodes in `startup_corrected_buffer_antennas_001` close the
router antenna report to zero net/pin violations. Its independent layout and
logic audits are now running. The source-pin and artifact receipts retain the
buffer repair and the preceding three-violation route as separate stages.


`startup_corrected_buffer_antennas_audit_001` passes independent digital
layout: DRC0, unique LVS, zero antenna violations, connected power pins and
all 489 transition/output functions equivalent with the corrupted-reset
negative control rejected. `startup_corrected_digital_timing_screen_004`
is now running four concurrent jobs on this route. It remains an unselected
diagnostic candidate pending timing, parent rebuild and full qualification.


Screen 004 is complete. The original A21OI_4/buffered net has no reported TT
electrical violation. Across all three TT25C/1.80V RC views, PLLOUT setup is
at least +0.728073 ns and hold +0.132095 ns; FINECLK setup is at least
+0.232052 ns and hold +0.185661 ns. A different A21OI_1 driver,
`$abc$74280$auto$blifparse.cc:397:parse_blif$75722/Y`, now reports min/max-RC
slew 1.47/1.60 ns against 1 ns and capacitance 0.10/0.11 pF against 0.07 pF.
The supplied SS100C/1.60V diagnostic still fails setup. No fifteen-PVT gate
is closed. `startup_corrected_timing_repair_003` runs the existing electrical
repair flow on these fresh loads, followed by independent audit 003 and
screen 005 only if layout passes. Annotation audit 003 checks the antenna-
repaired route separately. The earlier screened route remains unselected.


Annotation audit 003 completes with all 100 unannotated drivers classified as
no logical fanout and zero unresolved active drivers. Repair 003 resized 29
instances and inserted one buffer; routing and subsequent independent checks
remain pending. This annotation classification does not qualify final fill,
power/noise or timing.


Repair 003 completed routing with DRC0 and connected database power rails;
the measured A21OI_1 is now A21OI_4. Independent audit 003 is running. Its
immediate post-route electrical report is retained as diagnostic evidence;
acceptance still requires the fresh screen 005 after independent layout passes.


Screen 005 on repair 003 has no reported TT25C/1.80V or supplied FF−40C/1.95V
electrical/pulse-width violations across min/nom/max RC, with positive setup
and hold. Across TT RC views the worst PLLOUT setup/hold are +0.720173/
+0.132095 ns and FINECLK setup/hold +0.237048/+0.185840 ns. The supplied
SS100C/1.60V view remains nonpassing and these libraries do not cover the
required fifteen nominal-voltage PVT points. Annotation audit 004 is complete
with zero unresolved active drivers. This is the candidate for a fresh parent
physical build, not a qualified release. `startup_timing_frame_001` and
`startup_timing_power_001` pass; `startup_timing_route_001` routes the parent
with router DRC0 and preserved macro/PG bindings. Independent assembled layout
and antenna/density measurements are running in `startup_timing_layout_001`
and `startup_timing_geometry_001`. Old parent extraction remains tied to the
older digital body and is retained only for algorithm work.


The new unprotected parent has 45 forming-stage antenna violations (one on
metal2, 39 on metal3, five on metal4); native antenna and assembled LVS checks
are still running. A continuation waits for passing assembled DRC/LVS before
localization, fresh compiled bank planning and an independent exhaustive
KLayout coordinate/tie comparison. `benchmark_parent_bank_search_v2.py`
checks input/artifact identities before and after the reference calculation
and emits the `nets_compared` receipt required by the protection stage. It
preserves the original benchmark source. The planned follow-on directories
are `startup_timing_localization_001`, `startup_timing_bank_plan_001`,
`startup_timing_bank_reference_001`, `startup_timing_protected_power_001`,
`startup_timing_protected_route_001`, `startup_timing_protected_layout_001`
and `startup_timing_protected_geometry_001`. None is promoted by a queued job.


`startup_timing_layout_001` passes DRC0 and unique LVS. Localization accounts
for all 45 forming-stage violations on 43 nets. The fresh compiled plan reuses
the verified binary and matches every coordinate/tie from the independent
KLayout reference for all 43 nets. Measured search times on this data are
0.123081 s compiled and 7.823514 s reference; the compiled controller took
0.809034 s with binary reuse. These are search/controller measurements,
not a complete-CAD speedup claim. Protection power 001 places 43 banks
(172 diodes, 43 taps), and protected route 001 completes with router DRC0 and
preserved macro/PG connectivity. Its independent layout checks are running;
antenna closure and fill remain pending.


The protected parent passes independent DRC0/LVS; forming-stage antenna is
reduced from 45 to 21 violations on 21 distinct nets. Targeted existing-rail
banks in `startup_timing_target_banks_001` add 84 diodes/21 taps while preserving
348 unaffected signal routes. That candidate passes independent DRC0/LVS.
Its forming-stage report has two residual metal3 violations; native antenna
is still running. Localization `startup_timing_last_localization_001` prepares
the next targeted stage; no fill or extraction is adopted yet.

`check_parent_geometry_v4.py` runs the three parent RC views, forming antenna,
native antenna and stock density as six independent jobs. Per-job CPU/RAM
leases, native address-space limits, process-group cancellation and one whole-
check deadline apply. Five native-process controls pass, including overlap,
address-space enforcement, peer failure with an uncooperative child, whole-
check timeout, changed inputs and retained density exit evidence. Three
comparison controls retain all numerical digits, duplicate feedback and
density measurements while permitting only specified run metadata changes.
The full regression suite is rerunning with these eight controls added.

`startup_timing_parallel_geometry_control_001` repeats the serial unprotected
parent geometry on identical native inputs. Comparison 001 failed host CAD-
dependency preflight; 002 correctly rejected raw density run timestamps.
`compare_parallel_geometry_v2.py` normalizes only the output directory and
three explicit density timestamps (SPEF ignores only its DATE header).
Comparison 003 verifies exact three-view RC contents, every forming component,
the full 1,391-record native feedback multiset and all density transcript
measurements. Serial whole-check time was 234.870269 s versus 145.500120 s
parallel, a measured 1.6142x improvement on this geometry. This does not qualify
the physical RC model or establish a universal CAD speedup. The serial v3
controller and prior comparator versions remain unchanged.


The targeted parent completes with native antenna feedback zero. The two
remaining forming violations are `fine_therm[77]` and `fine_therm[99]`.
`startup_timing_last_banks_001` adds a further bank to each while retaining
other routes, followed by independent last-layout/last-geometry 001 checks.
The fill continuation waits for DRC/LVS and both antenna methods to pass;
then it produces `startup_timing_fill_001`, rechecks assembled filled layout
and parallel geometry, and reconciles topology/density in
`startup_timing_filled_closure_001`. Queued stages do not imply passing results.


The expanded full regression suite passes all 102 tests (log:
`/tmp/openpll-signoff-parallel-geometry-all-tests.log`). The two-net last-bank
repair routes with router DRC0 and preserves 367 unaffected routes.
Independent layout checks are running, and the fill controller is waiting.


Last-bank candidate 001 passes independent DRC0/LVS and native antenna zero,
but has one forming-stage metal3 violation, so fill 001 and its electrical
continuation stop before fill generation or new extraction. Their failed
receipts/logs remain. Repair 002 uses `add_targeted_parent_banks_v7.py`:
`parent_bank_ancestry.py` follows only hash-pinned source-route assessments
and collects every prior stage-local bank plan. All 66 existing sites are
reserved before another bank is placed, including the 21-bank intermediate
stage that the previous helper omitted when traversing more than one repair.
Five controls pass for complete recovery, changed plans, missing receipt
pins, duplicate sites and ambiguous ancestry. Earlier repair sources remain
unchanged. Candidate last-layout/last-geometry 002 checks follow the new route.

The older `startup_corrected_filled_domain_001` native R extraction completed
with 1,148,303 resistor cards, 40,131,647 signed capacitance cards and 47,541
device subcircuit cards. Its all-snapshot index and compiled reconciliation
checks are running. It remains evidence for the older digital geometry and
does not qualify the timing-repaired candidate.


Last-bank repair 002 confirms all 66 prior bank sites reserved (two ancestor
extra plans), adds four diodes/one tap on `fine_therm[99]`, and routes with
DRC0 while preserving 368 unaffected routes. Independent last-layout 002 is
running. The distinct fill/filled-layout/filled-geometry/filled-closure 002
continuation again waits for passing antenna evidence; it uses the new
physical input and preserves attempt 001. Electrical continuation 002 is
stored in `build/signoff400/startup_timing_electrical_002/driver.py` with its
own owner/status/launch records. After filled closure passes it performs
loading, retained-domain extraction, independent R indexing/reconciliation,
controlled native owned-C extraction, and 16-worker bounded C++ compilation.
Native work inherits fill 002's original 12h budget; compilation is its own
explicit 12h check. No physical-domain or release gate is inferred from a
queued controller or completed operator construction.


Last-bank candidate 002 passes independent DRC0/LVS and both forming-stage
and native antenna zero. Fill 002 completes with every original geometry and
label preserved and only fill-purpose layers added on the required grid.
Independent filled layout is running; parallel filled geometry, topology and
density closure follow before the electrical continuation can launch.

The older corrected-body R index preserves 18,350 snapshots, 1,451,744 private
nodes and 636,279 tiles. The compiled export check matches all 992,511 printed
node cards and 1,148,303 resistor cards against the entire last-group export,
with no uncovered labels and 63 labels matching multiple snapshots. All
branch-creation identities and snapshot geometry records reconcile, but
`startup_corrected_r_geometry_001` reports 5,672 creation-axis points outside
their tiles (metal3:2, metal4:6, ndiff:1,290, pdiff:2,964, nwell:958,
pwell:452) and 994 zero-wire-resistance branches. Rectangular interpolation,
zero-R constraints, contacts and snapshot selection remain unqualified;
physical-domain completeness/runtime eligibility stay false. Export agreement
alone does not resolve these attachment requirements.


Filled candidate 002 passes all scoped geometry prerequisites: independent
DRC0/LVS, zero forming/native antenna, 743 macro-port probes without missing,
shorted or split logical nets, and all 175 constrained stock density checks
over 195 raw tiles. `campaign_timing_001` freezes its exact GDS/current RTL
under the fifteen-PVT profile. Geometry alone is imported; all electrical,
PVT and handoff gates remain open. This supersedes the earlier geometry-only
campaign as the active physical candidate.

Electrical continuation 002 received an unintentional SIGINT at 12:54 UTC;
its controller and native child were confirmed terminal. The user explicitly
requested continuation. Attempt 003 retains the interrupted files, uses a
fresh output directory and the same fill-002 budget start (12:36:54 UTC),
without resetting the original native deadline. Its native loading extraction
is confirmed live. The subsequent R, owned-C and 16-worker compiled stages
remain queued behind their exact prerequisites.

`main_v4.cpp` / `audit_r_geometry_v4.py` classify all unsupported R endpoints
against the complete 898,792 indexed contact-plane records. Five new native
controls pass for overlap/touch/disjoint/missing contacts, plane identity,
reversed resistor endpoint order, changed contact artifacts and unchanged
nonpass behavior. The full regression suite now passes 112 tests. Real audit
`startup_corrected_r_contact_geometry_001` preserves every prior geometry
failure/count and emits all 5,686 out-of-tile endpoint records for the 5,672
branches. None matches a recorded contact center, even without private-node
filtering. A separate device-binding point scan also finds no exact coordinate
matches. Native NODE origin tags, however, unambiguously identify 5,554 device
nodes and 132 extraction-origin nodes, with no ambiguous coincident-node tags.
These findings narrow the needed basis work to device/extraction-origin
breakpoints, rather than permitting contact-based clipping or moving nodes.
The voltage basis and runtime model remain unqualified. Analysis receipts are
`startup_corrected_r_endpoint_center_scan_001`,
`startup_corrected_r_endpoint_device_scan_001`, and
`startup_corrected_r_endpoint_origin_scan_001`.


The resumed timing-candidate loading stage completes with 41,811,123 signed
capacitor records, preserving floating nodes and the external feed points.
Retained-R extraction is live in `startup_timing_electrical_003/domain`, using
the original fill-002 budget. Native owned-C tracing and the bounded 16-worker
compiler remain behind that exact R reference.

`prove_handoff_pdr.py` proves the actual 34-bit, APPLY_CYCLES=3 tuning-handoff
sampled safety contract with independently changing/stalled clocks. Both resets
start asserted and any subsequent assertion is joint; releases may differ.
It checks source payload/request stability while outstanding, destination
capture consistency, at least three consumer cycles before acknowledgement,
and APPLIED data consistency. Three RTL mutants and removal of the joint-reset
assertion assumption produce counterexamples; a successful-transfer witness
prevents a vacuous protocol proof. Separate engine controls check constraint
folding, ordinary counterexamples and unknown initial-state preservation.
The AIGER inventory must retain six safety assertions, three environmental
constraints and no ordinary output properties for the baseline. Inputs,
recipes, models, invariants and native outputs are hash-pinned.

The first sampled induction attempt omitted SAT assumption activation and
retains its baseline counterexample. Attempt 002 enables assumptions and
passes the mutant/witness cases, but its baseline global-step induction was
still growing after more than ten minutes. The byte-identical instrumented
34-bit baseline is proved by the controlled AIG/PDR run in 31.53 s; the redundant
induction process group was stopped after verifying its PID birth identity
and the completed proof. This is an algorithm change, not a claim of an
apples-to-apples completed-run speedup. The reusable guarded tool repeats the
proof and all eight companion controls in `handoff_pdr_002`; its baseline PDR
time is 36.83 s. These are partial digital protocol receipts, leaving integrated
startup, physical payload delays, metastability, reset recovery/removal and all
release flags unqualified.

Run a fresh protocol proof with:
`make signoff400-handoff SIGNOFF400_HANDOFF_OUTPUT=build/signoff400/handoff_protocol_NEW`.
`signoff400-prepare` now defaults to the timing-repaired filled closure 002.


`merge_flat.cpp` replaces the global tree-map ledger with a flat vector whose
rows retain their exact original append sequence. Parallel sorting orders by
(global field pair, original sequence), followed by serial addition within
each pair. Floating-point addition order, field-ID assignment and signed
values remain unchanged; fast-math/FMA stay disabled. Six controls pass,
including 360,000 duplicate/cancellation-sensitive rows compared against the
independent Python merge at 1/2/16 threads, malformed inputs, one-bit numeric
changes, consumed-shard integrity and full small-reference comparison.

`compiled_charge_flat_merge_001` benchmarks the completed retained historical
shards with 16 sort threads and a 16-GiB address-space bound. It compares every
global field, all local-to-global mappings and all 49,753,395 reference ledger
rows bitwise before reporting success. It also compares aggregate counts,
components and arithmetic residuals. This is a new merge algorithm test, not
a repeated native extraction, and it cannot qualify the changed physical
candidate or its RC domain. The full comparison passed: all 2,400,607 fields,
16 field maps and 49,753,395 ledger rows agree, including every numeric bit.
The merge took 611.925 s versus the reference 599.048 s, so this algorithm
is not adopted and no speedup is claimed.


`merge_buffered.cpp` is a separate experiment preserving the flat-sort source.
It reads JSON through a 1-MiB buffer, reuses row storage, assigns first-encounter
field IDs through an exact-key hash table, and serializes ledger numbers with
17-digit `to_chars` directly. Addition order remains unchanged. Seven controls
pass, including a field identity crossing the buffer boundary with escaped
quotes/brackets, numeric round trips, the independent Python oracle, malformed
inputs and consumed-shard integrity. Input/sort/output phase times are emitted.
`compiled_charge_buffered_merge_001` benchmarks the same retained shards with
16 threads and a 16-GiB bound, followed by the complete established-reference
comparison. It is not adopted pending that result; the current extraction
continues using its pinned established compiler and original deadlines.


`inventory_rc_coverage.py` and `tools/native_rc_coverage/main.cpp` inventory
all compiled capacitance fields against every retained resistance snapshot and
its raw tile-plane/material signatures. Before comparing, the controller
requires the charge and index receipts to pin the exact same domain assessment
and GDS, and the export/index to pin that domain's native provenance. It rehashes
all consumed derived artifacts before and after execution, preserves every
snapshot, and checks indexed group/conductor/tile counts. It does not rehash
all native traces or qualify aliases, spatial ownership, lifetime selection,
finite-R bases, substrate references or passivity. Three controls pass,
including missing/duplicate snapshot and field rejection, geometry mismatch and
artifact mutation rejection.

Historical same-geometry `rc_coverage_inventory_001` completes in 57.16 s:
2,400,607 fields, 18,414 snapshots, 18,043 conductor labels and 639,629 tiles.
There are 66,989 fields with one label-matching snapshot, 3,756 with multiple
snapshots, 2,329,861 with no exact native conductor label, and one explicit
reference. Of the unmatched fields, 446,822 are arithmetic/unlocated; the rest
include 180,357 poly, 77,130 LI and 1,625,552 metal fields. Every field ID and
identity is retained in `native/fields.jsonl`; raw signature agreement alone
is not spatial/electrical coverage. These results are for the retained older
GDS, not the newly repaired candidate.

The inspected native `ResRex.c::ResProcessNode` returns before the
`ResOpt_ExtractAll` branch when no driving device/location is available
(`minRes == FLT_MAX` or `rg_devloc == NULL`). Thus `extresist all` alone does
not establish floating-fill resistance coverage. This source observation is
not a per-field cause assignment or permission to collapse missing conductors.
A controlled finite-R treatment of the missing domains remains required before
full physical-model qualification. Existing default-extresist capacitor-matrix
nonpasses remain in the historical coupling audit receipts.


The buffered merge's native phases complete (398.194 s input, 2.219 s sort,
88.398 s output), but its controller receives SIGINT during the final ledger
comparison. Attempt 001 and its failed state are retained. The main timing-
repaired extraction is independently verified live and unaffected. No buffered
algorithm is adopted from an incomplete receipt. `compare_completed_charge_merge.py`
compares retained completed outputs against the established reference without
rerunning merging, and preserves the candidate's original absolute deadline.
It rechecks original consumed-shard/reference pins, every field/map/ledger
numeric bit and aggregate counts/components/residuals, then rehashes inputs.
Its end-to-end control passes unchanged outputs and rejects a numeric mutation.
`compiled_charge_buffered_comparison_001` is the separate recovery comparison.

`merge_parallel.cpp` is a distinct algorithm experiment based on the frozen
buffered source. It assigns global field IDs serially, reads independent local
ledgers concurrently, catches worker exceptions and joins peers, then appends
in original shard/local-row order and assigns sequence IDs before sorting.
Within-key arithmetic is still serial and order-identical. Partial vectors are
released as they are flattened; native address space remains bounded at 16 GiB.
Eight controls pass, including the Python cancellation oracle at 1/2/16 threads,
buffer-boundary identities, malformed inputs, joined peer failure, complete
small reference comparison and changed consumed artifacts. Full retained-data
benchmark `compiled_charge_parallel_merge_001` runs at 16 threads; no adoption
or whole-check speedup is inferred before its complete comparison.

`classify_rc_ext_inventory.py` and `tools/native_rc_coverage/classify_ext.cpp`
refine the same-geometry inventory using EXT node declarations, ports, explicit
equivalence records and quoted device-token incidence. They retain all original
field IDs. The synthetic control covers transitive aliases, port/device-only
components, declared unconnected components and undeclared names. Device-token
incidence is a textual inventory, not a device-physics or connectivity proof.
Historical `rc_EXT_inventory_001` completes in 57.25 s: all 2,329,861 previously
unmatched fields belong to declared components without port/device/native-R
incidence; 70,745 fields have an R-label-bearing component, plus the reference.
The raw EXT has 1,923,119 node records, 371 ports, 47,601 devices and zero explicit
equivalence records. Thus explicit EXT aliases do not close the inventory gap.
No floating conductor is grounded, collapsed or relabeled as qualified.

The complete `make signoff400-test` run passes 128 tests (log:
`/tmp/openpll-signoff400-all-tests-buffered-coverage.log`). The parallel-reader,
EXT inventory and retained-output comparison then pass 8/1/1 additional targeted
controls separately. Physical-model/PVT/lock/timing/handoff gates remain open.


Both completed candidate outputs pass `compare_completed_charge_merge_v2.py`:
`compiled_charge_buffered_comparison_002` (43.57 s) and
`compiled_charge_parallel_comparison_001` (59.56 s). The improved comparator
uses a literal bounded-memory byte comparison when output hashes equal those
of the pinned reference. It therefore compares all bytes of the 95,474,515-byte
field file and 3,701,476,069-byte ledger, with row counts inherited explicitly
from the byte-identical validated reference (2,400,607 / 49,753,395). All 16 maps
also match, and aggregate counts/components/residuals agree. Differing byte
representations fall back to strict parsed numeric-bit comparison. Its control
accepts whitespace-only differences and rejects a numeric mutation. A separate
binary control checks a buffer boundary, embedded NUL/high-byte values, one-bit
changes, changed length and expired deadlines.

Only after rehashing both successful replacement receipts and checking native
PID birth identities, the two redundant long parsing comparisons were stopped.
Their failed wrapper states and `algorithm_replacement.json` records are retained;
they are not presented as completed parsing runs. No merge or extraction was
rerun. The successful replacement receipts preserve each original deadline and
leave physical-domain, passivity, runtime and release qualification false.

The parallel merge's measured phases are 81.316 s field mapping, 39.546 s ledger
read/flatten, 2.110 s sort and 102.861 s output (225.833 s total). These phase
timings, the 599.048 s established merge-stage time, and the separate comparison
checks are distinct measurements; no full-extraction speedup is claimed.
`compile_native_charge_v3.py` selects this source for future native compilations,
with a 16-CPU / 16-GiB merge lease, OpenMP compilation and exact source/build
pins. Three end-to-end controls pass, including an independent Python-produced
field/ledger comparison. `make signoff400-charge-native` now uses v3.
The already-running `startup_timing_electrical_003` keeps its pinned v2 driver.

After the 128-test complete suite, 15 further targeted controls pass: parallel
merge 8, EXT inventory 1, retained comparison 1, byte-fast comparison 1, binary
byte comparison 1 and v3 native pipeline 3. The adoption receipt records their
logs and all selected sources. This accelerates future preparation; it does
not close the newly measured floating-conductor resistance coverage gap or any
remaining macro signoff gate.


The compiled `floating_geometry.cpp` / `inventory_floating_geometry.py` refine
that inventory to **1,883,039 distinct native conductors** carrying 2,329,861
unmatched voltage fields. Every conductor has exactly one spatial plane/material
key and one nonzero native resistance class; 446,822 also have an unlocated
arithmetic field. Native coordinates, all field IDs, area/perimeter pairs and
raw sheet-class values remain explicit. Missing/duplicate/truncated native node
controls are rejected. No sheet-class unit/PVT choice or arithmetic attachment
is inferred from this inventory.

`audit_floating_gds_geometry.py` runs seven independently leased KLayout jobs
(1 CPU / 8 GiB each), using the tested process-group cancellation scheduler.
On the same retained historical GDS, all 1,883,039 native probes identify one
unique conductor polygon, with exact native-to-GDS area/perimeter scaling and
matching material. There are 1,882,983 rectangles and 56 nonrectangles (3 M4,
53 M5). The 60.69 s audit retains per-node identities and never relabels the
nonrectangles as rectangles; its `all_native_conductors_exact_rectangles` flag
is correctly false. Controls check the native corner probe, area, material,
duplicate attribution, missing geometry and nonrectangle rejection.

`capture_floating_nonrectangles.py` retains all 56 complete hull/hole contours.
All have Manhattan edges, at most eight hull vertices and no holes in this
physical sample. Separate controls retain an actual hole and reject changed,
ambiguous or rectangular exception geometry. These are source-GDS geometry
observations, not a qualified electrical resistance model.

`floating_sheet_basis.py` constructs a conforming Cartesian-grid P1 triangular
sheet basis for rectangles and simple Manhattan polygons with holes. Rational
coordinates and exact rational triangle stiffness/mass avoid tolerance-based
geometry or passivity decisions in these controls. It preserves the floating
constant-voltage nullspace; it does not ground the floating sheet. Certificates
check exact area/boundary coverage, connected nonnegative edge conductances,
constant mass and continuum energy for affine voltage fields. A quadratic-
voltage rectangle control has the exact expected second-order refinement
error; perturbing conductance or mass is rejected. Non-Manhattan, intersecting
and touching-hole contours are rejected.

`floating_sheet_controls_001` checks all 56 retained exceptional polygons and
one actual rectangle per material (63 cases) at refinements 1/2/4, in eight
bounded processes. All 189 certificates pass in 8.31 s. These matrices use unit
sheet conductance and coordinate-squared mass units. Physical sheet resistance
and temperature/corner scaling, spatial signed-capacitance integration,
unlocated-arithmetic attachment, numerical/full-model convergence and global
passivity remain open. No physical basis/runtime/release qualification flag is
set, and none of this historical geometry substitutes for the currently live
timing-repaired candidate extraction.

Ten new targeted tests pass: native floating inventory 2, GDS matching 2,
exact sheet basis 4 and exceptional-contour capture 2. The KLayout tests run
inside the pinned CAD image; host discovery explicitly skips them when KLayout
is unavailable. Source manifests and full per-conductor outputs are retained
under `floating_geometry_inventory_001`, `floating_GDS_geometry_001`,
`floating_nonrectangles_001` and `floating_sheet_controls_001`.


The next complete `make signoff400-test` run reports 153 tests, with the four
KLayout tests skipped on the host. Those four controls separately pass in the
pinned image. Log: `/tmp/openpll-signoff400-all-tests-floating-sheet.log`.

`floating_sheet_charge.py` is an exact-rational reference integrator for signed
uniform AREA and LINE operators on spatial P1 sheets. It clips actual triangle
supports, integrates degree-two products exactly, and retains each conductor's
independent sheet coordinates. Shared-line patches must give the same restricted
basis. Support gaps/overlaps are rejected; no nearest-node clamp or constant
floating-conductor fallback is used. Four controls pass: independent continuum
polynomial energy, two different meshes, signed-density/constant-collapse
checks, charge conservation and finite-R self-line energy that vanishes only
when the sheet is constrained to constant voltage.

`floating_sheet_fringe.py` extends that reference oracle to the recorded
arctangent fringe density. Exact geometric partitions and polynomial tangent
integrals reduce each convex patch to four Lorentzian normal moments, evaluated
with high-precision standard-library Decimal arctan/log arithmetic. Source
voltage is evaluated on its own projected edge; target voltage retains both
spatial gradients. Signed shields are retained. Four controls cover independent
adaptive integration of moments, all four directions, positive/negative density,
charge conservation, native scalar collapse, zero multiplier and missing support.
The first independent quadrature test used an absolute tolerance too loose for
its requested relative comparison of a small result; normalizing that reference
integral resolves the fixture without changing production formulas or physical
criteria. Both logs remain retained. These are reference oracles, not full-layout
runtime or integration-error qualification.

The compiled real-operator sampler's initial source omitted `<array>` and failed
to build; attempt 001 is retained. Version 2 fixes the header and checks a
prefix; version 3 samples four separated byte windows to include later coupling
phases. Exact operator byte offsets and local-to-global maps are retained.
The corrected attempts conservatively inherit attempt 001's original 12-hour
check deadline. Three sampler controls pass, including separated-window offsets,
unique selected cases and invalid map/geometry rejection. The selected complete
operator shard (not just sampled bytes), maps, fields and geometry are rehashed
before and after sampling. Full native trace rehashing is explicitly false.

`floating_native_operator_samples_003` scans 2,000,000 rows in four windows of
historical shard 0 and selects 12 actual operators: two each of positive area
to reference, positive/negative line to reference, positive line between sheets,
and positive/negative fringe between sheets. These do not include native
same-sheet/restored cases; the separate exact self-line control is not promoted
to evidence of that missing real-data coverage.

`floating_native_charge_controls_001` checks all 12 at mesh refinements 1/2/4
in eight bounded processes (36 integrations, 2.13 s). Every integrated matrix
is symmetric and charge-conserving; constant sheet collapse agrees with the
native scalar integral, including a stated binary64 arctan/summation bound.
Signed squared-voltage energy keeps its original sign and affine voltage
energy is invariant under refinement. Native fringe entries also pass an
80-versus-120-digit precision control. Geometry coordinates are converted with
the audited integer native/GDS scale. The model still needs compiled full-data
integration, nonuniform-field numerical bounds, all active-conductor/device/
contact domains, unlocated-arithmetic attachment, PVT resistance values and
global passivity. All full physical/runtime/release flags remain false.

Eleven additional targeted tests pass after the complete suite: exact area/line
charge 4, high-precision fringe 4 and compiled operator sampling 3.


`tools/sheet_charge/main.cpp` is a compiled integration candidate. GMP rationals
preserve exact geometry partitions and P1 area/line matrix coefficients; no
geometric tolerance or outside-support clamp is introduced. Fringe integration
uses exact polygon partitions and positive eight-point normal / two-point
tangent quadrature, with panel width bounded in the arctangent transition
coordinate. Coordinates are centered on the operator's source point. Original
signed densities, projected source geometry, target gradients and shared node
identities remain explicit. OpenMP parallelizes independent cases; a failed
case joins/stops peers before emitting a matrix batch. Build receipts pin GCC,
GMP headers/libraries, source and the compiled binary; fast-math/FMA stay off.

Five compiled-kernel controls pass: exact uniform matrices versus the Python
rational oracle, all four signed fringe directions versus the high-precision
oracle at 1/2/16 threads, outside-support cancellation, shared lines/two meshes,
polygon/hole boundaries, exact coordinate serialization and extreme fringe
normal ranges/multipliers with panel refinement. Uniform numerator/denominator
outputs are compared exactly, not just after conversion to binary64.

`compiled_sheet_charge_001` checks 36 matrices from the 12 observed operators at
refinements 1/2/4: 24 area/line cases match exactly and 12 fringe cases have a
maximum normalized entry error of 1.018e-17 against the high-precision reference.
The selected native matrix stage takes 0.126 s; its separate 1.545 s Python
reference-preparation time also includes mesh/input preparation, so these are
not equivalent-work whole-check timing measurements. The repeated local trial
integrates 1,152 selected cases in 2.272/0.574/0.312/0.210/0.183 s at
1/4/8/16/32 threads. These short, repeated-geometry trials do not establish
full-layout throughput or a universally preferred worker count.

`main_cached.cpp` is a separate, bounded-reuse candidate. The canonical key
contains normalized exact support geometry, all affine basis coefficients,
local shared-node topology, operator kind, exact density/multiplier and fringe
panel setting. Event IDs, conductor names and absolute translation are excluded
only because they do not change the local matrix. Shared versus independent
nodes remain distinct. Each thread has a conservative 16-MiB storage estimate
limit and clears its cache when adding an entry would exceed that limit; the
native process still has an 8-GiB address-space bound. Cached exact/extended-
precision coefficients are copied without changing their arithmetic or mapping.

Eight cache-candidate controls pass, including translated/renamed geometry,
coefficient/direction changes, same-sheet versus independent-sheet aliases,
forced eviction, mixed cases and all base-kernel extreme-fringe controls.
An expanded test fixture initially translated one aliased sheet twice; the
kernel correctly rejected its line as outside support. The fixture now applies
each translation once per shared object. The failed native input/output is
retained in `cached_sheet_fuzz_failure_001`; production formulas did not change.

`compiled_sheet_charge_cached_001` repeats the same 36 reference comparisons and
retains the same 1.018e-17 maximum fringe error. In the short repeated local
trial, its 16-thread time is 0.158 s versus 0.161 s at 32 threads; hit rates and
scheduling differ, and this is not a full-stream performance qualification.
`sheet_cache_equivalence_001` checks 2,880 emitted replica records from both
candidates at all five thread counts. Each has the exact coefficient bits of
its pinned base case, and each cached/uncached batch is literally byte-identical.
Two controls reject one-bit, missing/duplicate and identity mutations.

These compiled candidates are not selected as a physical runtime or substituted
for the in-flight extraction. Complete operator registration/streaming and
assembly, actual repeated-template coverage, active-device/contact domains,
unlocated arithmetic, PVT scaling, integration/discretization uncertainty and
global passivity remain mandatory. All corresponding physical/runtime/release
flags stay false. Fifteen targeted tests pass in this increment: base compiled
kernel 5, cache candidate 8 and emitted-batch verifier 2.


The next full `make signoff400-test` run completes **179 tests** with four
CAD-only skips on the host. The unchanged four CAD tests have separately passed
inside the pinned image. Log: `/tmp/openpll-signoff400-all-tests-compiled-sheet.log`.
The compiled sheet candidates require GMP development headers/libraries;
build receipts currently pin GMP 6.3.0 and their resolved host files.

`audit_r_geometry_v5.py` / `main_v5.cpp` extend the retained-geometry auditor
with complete raw branch and attributed wire-creation streams. Every record
includes its native group, original conductor, raw branch identity, original
private node IDs, raw resistance text/value and status/type. Wire records also
retain actual creation points (not moved representative points), exact working
plane, box, axis, width and split/outside status. Pointer reuse across groups
never merges records. Contact branches and zero wire resistances remain explicit.
The new synthetic export control retains outside-tile wires and reversed endpoint
identities without promoting interpolation. The initial copied test module had
an indentation error; the corrected six-control run passes, with both logs kept.

Historical same-GDS `native_r_registration_001` emits **1,767,906** native branch
records and **1,303,120** attributed wire records across all 18,414 snapshots.
All indexed nodes/tiles/contacts and every native branch are accounted for.
The earlier geometry nonpass is unchanged: 5,631 out-of-tile branch cases,
5,651 outside endpoints, 1,878 zero wire branches, plus 464,786 contact branches
whose physical impedance remains unqualified. No last-snapshot-by-name selection
or geometric point relocation is performed. The full registration takes 140.06 s;
this includes additional output and is not compared as an equal-work speedup.

`main_registered.cpp` extends the exact-geometry cached charge candidate with
explicit `point_nodes` identities. Repeated native node IDs at different mesh
vertices add their barycentric coefficients; they cannot overwrite them. This
supports axis fields shared across the cross section and explicit native aliases
without changing the floating-sheet candidate sources or their receipts.
`native_axis_basis.py` supplies strict fully covered axis-tile templates and an
independent nonuniform one-dimensional mass formula. Open ends, out-of-tile axis
knots, nonincreasing knots and inconsistent identity counts are rejected rather
than clamped. Eleven controls pass: the eight inherited candidate controls plus
nonuniform x/y axis mass, repeated/shared private identities and strict coverage.

`native_axis_registration_controls_001` anchors this algebra to 24 observed
nonzero branch subrectangles from the fully registered historical stream. It
preserves each raw branch/group/private identity and explicitly records the
restricted strip versus its complete creation tile. Synthetic **unit-density**
area operators produce 48 exact matches to the independent axis-mass formula at
1/8 threads, in 20.86 s including build/input checks. These are registration
controls, not observed capacitance operators or full-creation-tile coverage.
They do not choose R units, snapshot lifetime, contact impedance, zero-R quotient,
PVT values or an active physical runtime. All such qualification flags remain
false. Seventeen additional targeted tests pass after the complete suite:
branch export 6 and explicit-node compiled registration 11.

The fresh timing-repaired retained-R extraction completes at 16:33 UTC under
its original native budget. Its retained export contains 1,214,771 R cards,
40,122,880 C cards and 51,829 native device/subcircuit cards. Post-resistance C
cards are not substituted for the pre-resistance charge kernels. The pinned
electrical driver automatically starts independent R indexing/export/geometry
checks and the owned-C trace concurrently. Owned-C native PID 99538 and R index
PID 99434 are verified live at launch. No driver/source/deadline is changed,
and no physical macro gate is closed by native extraction completion alone.


`classify_native_wire_chains.py` / `classify_wire_chains.cpp` classify every
wire segment by snapshot, working plane, exact native material/type, tile box
and flow axis. Repeated conductor names are never merged. Sorted chains retain
every branch/private identity and raw resistance. Unsupported creation geometry,
gaps/overlaps, private-node discontinuities, uncovered ends and zero-R constraints
remain separate reasons. Three controls reject cross-snapshot identity reuse and
keep incomplete/outside/overlapping chains nonpassing.

Historical `native_wire_chain_inventory_001` retains all 1,303,120 wire segments
in 572,337 tile-axis chains (63.95 s): 298,554 cover the full tile with positive R,
268,276 have uncovered ends and 5,507 have unsupported creation geometry. Reasons
can overlap: 272,577 chains have an uncovered end and 939 have a zero-R constraint.
No axis gap/overlap or private-node discontinuity is observed in this dataset.
These counts establish registration coverage, not a qualified voltage basis.

`native_axis_stubs.py` adds finite passive end resistors and new latent voltage
states only in uncovered end strips. Existing native resistor values remain
unchanged; optional series refinement preserves each original total resistance.
An exact Schur elimination of all generated states recovers the original DC
native graph. Repeated native identities retain the original parallel graph.
Zero-R chains and outside endpoints are rejected pending their own treatment.
The full tile's unit-density mass uses the augmented basis, so end capacitance
is not silently placed on its nearest original node.

Five controls pass: exact DC preservation, preserved floating states, explicit
contrast with nearest-anchor capacitance assignment, repeated native identities,
unsupported input rejection and refinement toward the independent uniform open-
RC-line admittance `sqrt(s)*tanh(s)`. The normalized RC systems recompute original
scaled equation residuals and require <=1e-12. These local controls do not qualify
full physical discretization or the nonlinear solver domain.

`nominal_sheet_resistance.py` reads the seven non-device sheet values directly
from the pinned technology's explicit nominal `ngspice()` variant block and
milliohms-per-square declaration. It refuses incomplete, ambiguous or adjusted
rules; two controls pass. No temperature/process scaling is invented.

`native_end_stub_controls_001` applies this construction to 24 observed uncovered
historical chains with at most six native segments. It checks 72 exact DC Schur
identities and 72 exact compiled full-tile **synthetic unit-density** matrices at
refinements 1/2/4. The normalized-frequency passive RC systems have maximum
original-equation residual 1.781e-16. The 37.81 s check includes input validation
and compilation. These are not actual signed capacitance operators, physical
400 MHz responses, PVT resistance qualification or full-layout runtime evidence.
All such flags stay false; active-device/contact/outside/zero-R domains remain
mandatory. Ten new targeted tests pass: chain inventory 3, end states 5 and
nominal sheet parser 2.

For the current timing-repaired GDS, R indexing completes with 1,527,930 private
nodes, 18,578 snapshots and 18,207 original conductors. The independent printed
card comparison completes; its 18,264 matching groups do not select physical
snapshot lifetimes. The current wire geometry audit retains a nonpass on 5,554
of 1,360,481 wire branches. `startup_timing_r_registration_001` is producing full
records for this actual candidate while the owned-C trace runs. Native PID
100471 is verified live waiting for storage I/O; PID 99538 remains active in the
owned-C extractor. Observation delays do not restart either job or its budget.


The current-candidate `startup_timing_r_registration_001` subsequently completes
in 754.64 s while the owned-C trace is active; its known storage waits remain
part of that wall time. Full wire/branch record emission completes and the same
5,554 geometry nonpasses remain. `startup_timing_wire_chain_inventory_001` now
classifies this current data; it does not import the historical chain counts or
end-stub control results as qualification of the repaired candidate.


The current chain inventory completes in 180.95 s: 601,117 chains retain all
1,360,481 segments; 318,861 are full-tile positive-R, 276,810 have uncovered
ends and 5,446 have unsupported creation geometry. Current-candidate
`startup_timing_end_stub_controls_001` checks 24 observed chains with 72 exact
DC Schur identities and 72 compiled synthetic unit-density mass comparisons;
maximum normalized equation residual is 1.7804062e-16. These remain normalized
controls, not physical 400 MHz qualification.

`startup_timing_axis_registry_001` prepares every current chain in 81.13 s
including verified local-SSD staging and publication. Its compiled GMP registry
references every native segment without rewriting core resistors. Of 601,117
chains, 318,861 need no added ends, 209,908 have nominal numeric finite ends,
66,346 retain symbolic end-resistance requirements, 5,446 defer creation
geometry and 556 defer zero-R constraints. It introduces 383,034 latent end
states: 286,678 numeric nominal and 96,356 symbolic end resistors. All source
chains are accounted for; three targeted registry controls pass. Snapshot
selection, material/contact/PVT models, full signed-C attachment and runtime
eligibility remain unqualified. The original source chain file is rehashed;
`full_native_inputs_rehashed=false` explicitly limits deeper lineage validation.
The owned-C extractor continues under its existing absolute deadline; this
registry preparation does not restart or change that extraction.


`startup_timing_axis_registry_audit_001` independently streams all 601,117 source
and registry rows in 40.72 s. It checks original byte offsets, snapshot/private
node identity and aliases, all 1,360,481 referenced segments, full-tile coverage,
exact rational nominal end values, symbolic requirements, deferred cases and
all unqualified flags. Both complete streams match their producer SHA-256 pins;
aggregate counts match independently. Three targeted controls reject numerical,
identity and qualification mutations, truncation, surplus rows and expired
budgets. This is registry-construction evidence only: 66,346 symbolic-end chains
and 6,002 deferred chains remain explicit, and no physical RC gate is promoted.


`nominal_sheet_resistance_v2.py` adds only explicitly documented nominal
non-device diffusion, tap and well materials: pwell/nwell and ndiff/pdiff plus
nsubdiff/psubdiff aliases. It validates the canonical plane/type declarations
and the nsd/psd aliases from the same technology file, rejects ambiguous,
adjusted, missing or nonpositive rules, and retains the original seven
interconnect values. Three parser controls pass; transistor-region material
models and all process/temperature scaling remain absent.

The compiled `startup_timing_axis_registry_002` uses this expanded nominal table
and retains all 601,117 chains and native R references. Construction completes
in 47.14 s using bounded local SSD staging. It resolves 63,166 additional chains
to nominal numeric end values: 273,074 finite-end chains, 318,861 full-axis
chains, 3,180 symbolic transistor-region chains and 6,002 deferred chains.
There are 376,674 nominal numeric and 6,360 symbolic end resistors.
`startup_timing_axis_registry_audit_002` independently checks the complete
registry in 37.57 s against original rows, exact ratios and content hashes.
No physical RC, material/device-interface, snapshot or PVT gate is promoted;
older registries and their evidence remain preserved.


`startup_timing_native_sheet_values_001` independently compares all current
chain segments against the documented nominal sheet table using the binary32
multiply/divide sequence in retained native ResMakeRes.c. All 1,244,491 compared
native resistor values match exactly; 115,990 device-region/diode segments
without a documented model remain explicitly counted and unresolved. No rows
are dropped. This 12.54 s consistency check rehashes the entire chain stream
and pins source/parser/technology inputs. Three additional controls cover native
rounding, a one-float-step mutation, unknown materials and bad geometry.
`exact_native_build_lineage_revalidated=false` limits this to source/arithmetic
consistency; it does not recertify the extractor binary, physical sheet values,
contact interfaces, snapshots, C attachment or resistance PVT.


`nominal_sheet_resistance_v3.py` resolves the four observed scnmos/scpmos gate
region types through explicit technology aliases from allpolynonres to allfets
and the relevant allnfets/allpfets leaves. It checks the native type plane and
rejects missing membership, wrong planes, ambiguity and cycles. It does not
infer wildcard/contact expansion or assign a sheet to ndiode. Two controls
pass after correcting a fixture that initially removed an unrelated alias;
the initial failed fixture log remains retained.

`startup_timing_native_sheet_values_002` checks the expanded table against the
original current chain stream. All 1,359,369 covered branches match the native
binary32 multiply/divide arithmetic exactly in 13.38 s. The 1,112 ndiode
segments remain explicitly unresolved. The retained source is pinned, but
extractor build-lineage recertification and physical gate/diode interfaces are
not claimed. All physical/PVT/runtime/release flags remain false.

`startup_timing_axis_registry_003` completes in 49.35 s, retaining every source
chain and core resistor reference. Its 595,115 prepared axes comprise 318,861
full-axis and 276,254 nominal finite-end chains; all 383,034 end resistors now
have documented nominal rule values. This eliminates symbolic *rule-value*
requirements only. The 5,446 creation-geometry cases and 556 zero-R constraint
cases remain deferred, and transistor interfaces, physical snapshot selection,
full signed-C attachment and PVT qualification remain mandatory. The complete
independent audit runs separately as startup_timing_axis_registry_audit_003.

The complete startup_timing_axis_registry_audit_003 subsequently passes in
37.53 s: all 601,117 rows and 1,360,481 segment references are independently
checked, including exact nominal end ratios, identities, offsets and stream
hashes. Three adversarial controls also pass against this v3 audit implementation.
No physical qualification flags change.


`native_anchored_sheet.py` constructs an exact P1 unit-sheet basis for a native
tile with one private voltage and no resistor chain. It keeps every actual
anchor coordinate/identity, permits multiple locations of that same voltage,
and assigns fresh latent states elsewhere. Exact unit-sheet stiffness and
area mass come from the frozen geometry-certified mesher. It rejects outside
anchors, split/nonpositive tiles, distinct native ports, identity collisions
and unbounded refinements. Four targeted tests pass, including exact DC Schur
preservation and a normalized-frequency response that differs from a constant
voltage tile. This is a parameterized basis, not physical resistance accuracy.

`startup_timing_anchored_sheet_controls_001` inventories all 672,808 current
native tile records with complete stream SHA validation: 601,117 multi-voltage
wire domains and 71,691 single-voltage tiles. All single-voltage records are
unsplit rectangles with inside anchors and a documented nominal sheet rule.
The inventory includes all snapshots without selecting their physical lifetime.
Eight bounded worker processes check 22 selected tiles (two per each of 11
observed materials) at refinements 1/2/4. All 66 exact native DC Schur identities
and 66 independent compiled GMP unit-density full-tile capacitance matrix
comparisons pass. The complete check takes 21.69 s including inventory,
compilation and input rehashing. These are synthetic local controls: full-layout
basis construction, actual signed-C attachment, physical contact/device
interfaces, snapshot selection and resistance PVT remain unqualified.


`catalog_native_tiles.cpp` joins the complete native tile stream to audited
axis-registry references and anchored-sheet descriptors. Its key includes
native snapshot group, working plane, raw type/material and exact box; matching
also requires the same private node set and conductor label. It rejects
ambiguous/duplicate/missing/multiply-consumed axes or tile serials and cross-
snapshot nodes. Each row retains its original source offset and tile identity;
axis rows retain immutable registry offsets and deferred cases. Single-voltage
rows keep actual anchor coordinates, exact base grid cuts, a fresh latent-node
namespace and documented nominal rule value. No snapshot is selected and no
physical qualification flag is promoted. Three controls pass, covering all
states/offsets plus malformed joins, outside anchors and deadline enforcement.
The bounded controller stages verified source streams on local SSD and records
all source hashes before publishing byte-verified catalog artifacts.

The owned-C native engine terminates normally and its retained controller moves
to checking_native_capacitance_equivalence. Exact native card/device checks,
node indexing and artifact receipts are still pending; the existing driver and
original deadline remain unchanged. Its compiler starts only after those checks.


`startup_timing_native_tile_catalog_001` completes the full compiled join in
83.89 s including compilation, local staging, verified publication and rehashing.
All 672,808 native tiles are accounted for: 595,115 nominal axis candidates,
71,691 anchored-sheet candidates and 6,002 explicitly deferred axis cases.
Every one of the 601,117 input axis records matches exactly one native tile,
including exact private-node set, label and snapshot/geometry checks. The
666,806 prepared entries are parameterized descriptions only:
finite_element_matrices_materialized=false. Physical lifetimes, signed-C
attachment, contact/device interfaces, PVT and runtime eligibility remain
unqualified; this does not count floating-fill-only domains as covered.


`compare_native_cards.cpp` provides a compiled sufficient equality proof for
native capacitance matrices and device statements. It interns node/value tokens,
normalizes unordered node pairs, preserves the original value-token sequence
within each pair, sorts on up to 16 OpenMP threads, and compares normalized
device-statement multisets including duplicate multiplicity. Identical
per-pair sequences imply the same existing Decimal accumulation even under
finite-precision cancellation. Changed numeric spellings or record
representations are inconclusive rather than treated as equivalent. Values
and ASCII inputs are validated within explicit bounded grammar/exponent limits.
Three controls cover random pair reorder/orientation/name changes at 1/4/16
threads, cancellation-order changes, device multiplicity, malformed values,
unsupported spellings and deadline rejection. The v2 candidate preserves the
algorithm while avoiding error-string construction in the byte scan and sorted
comparison loops; the same three controls pass. Both candidates retain the
original native deadline and run separately from the unchanged reference
controller. Full-layout comparisons are pending in
startup_timing_native_card_comparison_001 and _002. No speedup or whole-layout
card equality is claimed before their complete, rehashed receipts exist.


`startup_timing_native_card_comparison_001` and `_002` both pass on the complete
current reference/owned trace files: 41,911,533 C records each, 1,893,230 distinct
node labels, 67,408 raw value tokens and 51,829 native device statements each.
Per-pair value-token sequences and device multiplicities match exactly, implying
the same Decimal-fold matrix despite differing file order/identifiers. Both
checks preserve the original deadline and rehash all four complete card files
and pinned inputs after comparison. Baseline native/complete times are
204.75/230.82 s; optimized v2 times are 98.86/124.77 s. These overlapping runs
have different cache conditions, so no isolated speedup ratio is claimed.
The source checks run under a 12 GiB address-space bound with up to 16 sort
threads. The original trace controller continues unchanged, including node-ID
indexing and full raw-trace artifact hashing. This proves native card equality,
not signed spatial C assembly, global passivity, PVT or timing qualification.
The optimized verifier is available as make signoff400-native-card-equivalence
with SIGNOFF400_CARD_SOURCE and a fresh SIGNOFF400_CARD_OUTPUT.

`startup_timing_native_tile_catalog_audit_001` independently verifies the entire
catalog in 29.90 s. All 672,808 source tile rows, source byte offsets, native
snapshot/plane/type/material/box/private identities, original anchor locations,
base cuts, nominal values and unqualified flags match. All 601,117 axis offsets
resolve to their actual numbered source records exactly once; duplicate,
missing and swapped references fail. Complete source/catalog SHA pins and
aggregate counts agree. Two adversarial controls pass, including a deliberately
swapped reference with otherwise self-consistent producer hashes. Physical RC
qualification remains false.


`startup_timing_outside_device_bindings_001` retains exact current outside-
endpoint/private-device associations. All 5,566 outside endpoints on 5,554
branches survive the 3.23 s check. Of these, 5,556 associate with a device by
snapshot group and exact private identity, with different creation and BIND
coordinates; ten have no device binding. All matching bindings, including
multiplicity, are retained. Materials are pwell 70, nwell 958, ndiff 1,624,
pdiff 2,904, metal4 6 and metal3 4. Associated terminal occurrence counts are
SOURCE(2) 3,192, DRAIN(3) 1,340, SUBS(4) 1,348; shared nodes may have multiple
bindings, so these are not unique endpoint counts. Two identity/multiplicity
controls pass. Source pins show ResPrint.c emits dev->location and ResReadExt.c
loads the device location; these coordinates are not certified terminal
contact geometry. No endpoint moves and no geometry/interface gate is waived.

An exploratory exact same-snapshot/plane tile scan finds each of the ten
non-device endpoints inside a neighboring same-metal native tile, whose private
voltage set does not include that endpoint's native identity. The cases are
five conductors appearing in two retained snapshots each: fine_therm[89],
fine_therm[22], fine_therm[85], KP[3] and osc_reset_n. This identifies a cross-tile
continuity question; mere conductor coverage cannot qualify a basis or authorize
clamping/relocating the native node. The formal outside-geometry gate remains
false pending a validated interface/basis construction.


`native_label_breakpoint_source_control_001` isolates a likely origin-breakpoint
cause. ResMakeLabelBreakpoints/ResMakePortBreakpoints scan all tiles overlapping
a label rectangle; the retained NEWPORT macro copies the single node drivepoint
into every tile, and resAllPortNodes uses that coordinate without per-tile
containment. A C harness compiles the exact frozen macro with a two-rectangle
label spanning case: two ports are created and one lies outside its assigned
tile. A proposed ResAddBreakpointFunc containment guard retains the original
drivepoint and skips only tiles not containing it. The patch is retained for
review but not applied; native_source_modified=false,
candidate_patch_applied=false, full_native_regression_passed=false. Closed
boundary inclusion avoids dropping points exactly on conductor boundaries.

Two attempted minimal native CAD controls remain preserved: reproducer_001
fails before extraction because PDK_ROOT was unset; reproducer_002 uses the
correct PDK but its metal-only two-port control exits 139 during R extraction
before segment/binding records. Their logs and failure statuses are retained.
These failures do not validate the candidate fix and do not change the running
full-design extraction, native R source, existing receipts or physical gates.
A driven-device native regression is required before any source-fix adoption.


The original owned-C controller completes node_ids.json and advances to complete
raw artifact SHA hashing. startup_timing_trace_readahead_001 assists that exact
birth-identified live PID using eight independent read-only handles, 8 MiB blocks
and at most 512 MiB ahead of its observed cursor. Its lease is 8 CPUs/2 GiB with
about 64 MiB outstanding read buffers. It never changes the controller FD,
trace bytes, checksums, deadline or pass flags, and stops when that reader exits.
This is cache assistance only; no isolated throughput improvement is claimed.

native_label_breakpoint_reproducer_003 succeeds with a retained NAND cell plus
a driven L-shaped local-interconnect extension and spanning LABEL_SPAN label.
The unchanged native extractor creates a final LABEL_SPAN origin at (988,265)
on a tile beginning at y=266; this outside-origin branch appears in both retained
snapshots. Complete native logs, source/control hashes and final-branch evidence
are retained. Earlier unsuccessful minimal controls remain preserved.

An unadopted source variant adds only the proposed ResAddBreakpointFunc point-
containment guard. magic_origin_guard_build_001 prepares a fresh isolated Git
worktree on shared storage; its checkout remains live. An independent archive-
verified local-SSD build, magic_origin_guard_build_002, reaches compilation using
four workers within the remaining resource lease. The existing source/extractor
and live full-layout trace remain unchanged. The current native regression
controller is check_magic_origin_guard_v3.py in guard_controls_003. Earlier
checker versions assumed final identity for interior creation nodes subsequently
merged away; the versioned correction checks geometry before inspecting only
outside origin nodes. The baseline control confirms two final outside origins.
Regression must preserve pre-R C/devices and the original valid drivepoint.
Full native/physical/PVT qualification and adoption remain false.


The local-source experimental build reaches successful make completion and its
install stage. Installation includes documentation on shared storage; native
regression remains gated on a completed immutable build receipt. The source
worktree variant also remains live. No experimental binary is substituted into
the current full-design trace or the pinned driver. The owned trace's node index
is published and its original controller hashes the complete raw kernel file;
the cache-only assistant observes reader progress without supplying any digest.


magic_origin_guard_build_002 completes using the archive-verified local source,
with its runtime/library and full immutable build inputs pinned. Its status is
excluded from immutable artifacts. native_label_breakpoint_guard_controls_003
passes the driven native case: two outside LABEL_SPAN origin branches become
zero, the original (988,265) drivepoint remains, and pre-R C/device statements
are unchanged. The shared-storage duplicate build is intentionally stopped only
after rechecking the completed local build/control receipts and identical base
archive/baseline patch. Its algorithm_replacement.json retains PID birth/group
and scope; the original full-layout trace controller is never signaled. The
obsolete v2 checker fails on merged interior-node lookup and is preserved.

native_origin_guard_corner_controls_001 runs 24 native jobs with six workers
on local SSD: four label geometries (Y-spanning, contained, exact boundary,
X-spanning) at min/nom/max extraction RC rule corners, original and candidate.
Its graph parser mistakenly expected GROUP rather than native BEGIN and fails
after native runs complete. The failure and all raw outputs remain retained.
The versioned correction and native_origin_guard_corner_audit_001 audit those
same completed runs without repeating any native extraction. All 12 pairs pass:
12 original outside origins become zero; all original drivepoint sets and
pre-R C/device comparisons agree. Six contained/boundary pairs also preserve
all native R nodes/edge multiplicities under unambiguous coordinate/name
identity. Each raw case archive is byte-verified against its retained source,
all pinned inputs rehash, and the corrected audit takes 19.21 s.

These are RC rule-corner extractor controls, not the required 15 transistor
PVT points or full-layout geometry closure. Full native regression, device
interfaces, the remaining device-origin geometry failures, signed-C attachment,
PVT and release/runtime qualification stay false. The isolated variant remains
unadopted; no current production source, GDS, native R receipt or live extraction
is rewritten or replaced by the experimental source fix.


The retained ResBasic.c source identifies six device breakpoint locations using
whole-device midpoint/center coordinates rather than the actual receiving-tile
interface: four adjacent S/D edges and the cross-plane S/D/substrate callbacks.
native_device_interface_patch_001 proposes rectangular shared-edge/overlap
centroids, retaining the existing behavior for split or empty-overlap cases.
13,412 independent lattice/continuum-centroid interval checks pass; 2,503 sampled
old midpoint choices lie outside the receiving interval. The NFET interval
example is illustrative (its extent is inferred, not independently measured);
interpretation.json explicitly limits that arithmetic example's scope.

magic_device_interface_build_001 applies the candidate on top of the isolated
label-origin guard. Both source and complete runtime build locally on SSD; the
runtime archive and exact binary/library/source inputs are retained. The active
extractor/source and existing native receipts remain unchanged. In
native_device_interface_controls_001, a driven NAND partial-diffusion synthetic
stress control reproduces an old S/D creation point at (392,148) on a tile
[392,74,414,102]. The candidate removes this outside point with all 208 creation
segments retained; all candidate endpoints lie within assigned tile boxes.
Pre-R C and native device statements remain exactly unchanged. This is a
synthetic geometry/source control, not a manufacturable-cell or physical model
qualification. Full native regression/PVT/adoption flags remain false.

startup_timing_interface_electrical_001 now runs a distinct full-layout diagnostic
with that exact unadopted build and the existing checked filled GDS bytes. Its
fresh 12-hour native budget is explicitly for the changed coordinate algorithm;
the original campaign/deadline continue independently. New trace data and runtime
are retained on local SSD with workspace links. The driver requires compiled
full pre-R C/device equality against the original before producing a native
receipt, then automatically indexes every snapshot and runs the compiled full
geometry audit. No backannotated native C is adopted, and no release/runtime or
physical RC gate is promoted based on starting this diagnostic.


The original owned-C check subsequently completes its node index and full raw
artifact hashes. Its retained driver advances to compiled_charge_running with
16 configured workers; the current compiler phase hashes trace inputs. The
birth-identified cache assistant exits on the original reader's termination.
The separate interface-corrected full-layout native R process remains live.

native_R_mask_hoist_patch_001 moves the two unchanged style/material mask bodies
out of their per-plane loops, computing each once per tile. Each plane still
receives a fresh value copy, preserving even hypothetical search-side mutation.
Geometry, callback order, plane order and R arithmetic are unchanged. The first
isolated harness omits the Tcl ClientData typedef and fails compilation; its
failure log is retained. The corrected fixture compiles the actual old/new
native loop bodies and passes 600 mask comparisons over 256 synthetic types,
multiple device/terminal lists and zero/one/19-plane cases. It deliberately
mutates every search mask, detects 200 missing-copy mutants, and counts
6,120,000 old versus 1,147,500 hoisted membership checks. These are fixture work
counts, not a native full-design throughput measurement.

magic_mask_hoist_build_001 reconstructs the exact completed interface-candidate
parent on local SSD, applies only that performance patch and retains a separate
runtime archive/binary/source receipt. native_mask_hoist_equivalence_001 passes:
all native R snapshot nodes/edges, C/device statements and 208 creation segments
match the retained partial-diffusion native reference, with zero new outside
endpoints. Full-layout numerical equivalence and measured native speedup remain
false; the performance candidate is unadopted and does not replace either live
pipeline.

startup_timing_breakpoint_profile_001 independently hashes and profiles all
672,808 retained original tile records: 604,506 initial lists have at least two
breakpoints, with a maximum of 708. Its sum-of-squared-initial-sizes proxy is
146,080,441; this is not measured sort time or an exact sort-comparison count.
The scan takes 10.74 s. A low-overhead perf capture attempt is denied by the OS
perf-event policy; no permissions are escalated and the native process is
unchanged. Further hotspot decisions require timing evidence rather than just
asymptotic source inspection.

The pinned PDK selects res_typical__cap_typical and its linear companion for
all five accepted transistor libraries (tt/ff/ss/sf/fs). This does not establish
an extracted-resistor PVT mapping. resistor_temperature_laws_001 retains the
strict parser failure on the fixed short utility model; v2 excludes exactly
that declaration and runs three independent native Xyce/KLU probes concurrently.
All native runs complete. Its checker initially assumes an extra DC sweep
column; the retained tables contain only the index and requested currents.
The v3 future runner corrects the parser without rerunning native simulations.
The first retained audit expects the wrong native completion phrase; audit v2
uses the actual Xyce end marker. All failed outputs remain retained.

resistor_temperature_law_audit_002 validates all 22 model coefficient laws at
-40/27/125 C (66 checks), explicit model TNOM values (30 C, or 25 C for RDL),
1-kohm normalization and the TC1R/TC2R to Xyce TC1/TC2 translation. Worst relative
current error versus Decimal polynomial evaluation is 2.30841254e-16. Four
adversarial controls reject changed coefficients, operating temperature, current
column names and pinned PDK source bytes. The audit reuses all completed native
outputs and records their hashes. No full-design resistance values are changed.

Magic-to-generic-model nominal discrepancies remain unresolved, including LI
12.8 versus 12.2 ohm/square, nwell 950 versus 1700 and M5 .029 versus .0285.
Magic reference temperature is not established by these generic model TNOMs;
width adjustments, contacts, device regions and full extracted resistance PVT
qualification remain separate. All mapping and physical release flags stay false.

startup_timing_resistance_calibration_001 pins the exact Magic technology from
the nominal native arithmetic receipt and the retained PDK nominal parameters.
It accounts for all 1,360,481 original native wire segments. Candidate generic
sheet models differ nominally for 521,208 segments (LI, nwell and M5); 59,600
segments have no candidate generic model (58,488 pwell plus 1,112 ndiode).
Material-name and gate-region candidates are inventory proposals only, with
physical_mapping_qualified=false for every row. Model width corrections and
contact resistance are outside this inventory. All segments still lack an
established Magic reference temperature; generic model TNOM cannot substitute.
No extracted resistors or release qualifications are changed.

During this inventory the original charge compiler finishes its eight-worker
native contribution index and publishes 16 aligned spans. Its existing compiled
metadata child then scans the retained surfaces stream (PID 129951, birth
42917104); the coarse controller status still says indexing_aligned_streams.
The original parent and separate full-layout geometry candidate remain live.

startup_timing_repeated_snapshot_inventory_001 scans and hashes every native
R provenance byte, then compares all 18,578 group graphs using eight independent
workers. All 371 repeated conductor names occur exactly twice. Of these,
310 have different exported graph fingerprints, 56 share a fingerprint, and
five have ambiguous coordinate/name/why/status node identities. The five are
fine_therm[89], fine_therm[22], fine_therm[85], KP[3] and osc_reset_n, matching
the previously retained unbound-origin conductor list. This correlation does
not establish physical equivalence or select a snapshot. Fingerprints preserve
node names, coordinates, why/status, raw R values/material/status and distinct
parallel-branch multiplicity, ignoring process pointers and endpoint direction.
Four controls verify pointer renaming, edge reversal, changed values/multiplicity
and ambiguity handling; a separate native fixture independently matches all
15 group identities, original labels and node counts with the existing parser.
No snapshots are dropped, and physical snapshot selection remains false.

The original charge controller subsequently reaches compiling_native_workers;
all sixteen native worker PID birth identities are checked live. The separate
interface-corrected full-layout extraction remains active and unadopted.

A retained direct comparison of fine_therm[93] groups 6 and 18213 finds swapped
printed terminal names: .t0/.t1 exchange coordinates (54776,94416) and
(54750,94084), with matching why/status values. Its name-sensitive graph
fingerprints therefore differ. This is evidence of terminal-name instability,
not proof that all 310 pairs are physically different, nor permission to merge
them. Coordinate-based graph comparison and exact device-binding lineage remain
necessary. A separate KP[4] comparison finds its named node/edge rows identical.

The name-independent comparison with exact resolved device-marker/model/terminal
incidence completes for all groups, but every repeated-name pair still contains
at least one ambiguous coincident node. Six controls pass; no graph-isomorphism
or snapshot selection is inferred from this inconclusive geometric comparison.

A stronger independent source/export reconciliation resolves native pass lifetime.
ExtMain.c explicitly runs resistance extraction during extract all when
EXT_DOEXTRESIST is set. The retained recipe enables this before extract all,
then explicitly calls extresist all. The completed log records 371 networks from
the automatic pass, then 18,207 from the explicit full pass. ResCheckExtNodes
opens the .res.ext output in write mode for each pass, replacing the first.

startup_timing_final_snapshot_export_check_001 checks the full final .res.ext
against native groups 372 through 18,578 with compiled C++: all 1,052,269 rnode
name/coordinate records and all 1,214,771 resistor endpoint/value records match
as multisets, preserving parallel multiplicity. Native float milliohm division
and default-six-significant-digit %g formatting reproduce ResPrintExtRes
exactly. Raw provenance, final export, log, recipe and relevant source bytes are
pinned and rechecked. The first checker build misses iostream and remains retained;
the separately built v2 fixes the include. Six synthetic controls pass, rejecting
wrong prefix selection, changed resistance, omitted nodes, extra parallel edges
and altered coordinates. All historical raw snapshots remain intact.

This proves which snapshots belong to the final native R export, not physical
C attachment, contact impedance, material interfaces or PVT. The older all-pass
index has 1,527,930 private nodes; the final-export subset has 1,052,269, excluding
475,661 superseded private nodes from future final-domain assembly. Existing
catalogs and live extraction are unchanged; consumers must explicitly apply the
new pinned selected-group manifest. Electrical/physical release flags stay false.

startup_timing_final_R_catalog_001 applies the independently verified final
R-export group manifest to the previously audited complete tile catalog. Its
compiled streaming selector copies each source JSONL row verbatim into either
the final subset or a retained superseded subset, preserving private IDs,
source tile offsets, axis-registry references, geometry, values and all existing
unqualified flags. Unknown groups, mismatching conductor labels, crossed private
namespaces and premature physical/runtime/release flags are rejected.

The final subset contains 525,638 tiles across all 18,207 final-export groups:
459,528 axis candidates, 62,344 anchored-sheet candidates and 3,766 deferred axes.
The retained superseded subset contains 147,170 tiles. The independent stdlib
checker audits every one of the original 672,808 row bytes, membership decision,
state count and complete SHA-256, ensuring both outputs form an exact partition.
Eight selector/audit controls pass, including wrong groups/labels, duplicate
membership, crossed IDs, qualification flags, extra rows and changed row bytes.

Membership here refers only to the final native R export. Existing axis-registry
references intentionally point to the pinned all-pass registry, with original
row/byte offsets unchanged. Signed C assembly, material/device/contact models,
remaining axis cases, PVT, runtime behavior and release qualification stay open.
The live pipelines and all historical sources remain unchanged.

The final-pass catalog has 3,766 deferred axes: 3,486 creation-geometry cases
(2 metal3, 3 metal4, 1,092 ndiff, 423 nwell, 1,935 pdiff and 31 pwell) and 280
zero-R ndiode axes. All 280 zero-R chains have uncovered ends. The initial
strict full-tile zero-R checker correctly refuses them; its source, failure log
and classification remain retained rather than extending native voltages over
the uncovered area.

native_zero_R_axis_v2 preserves every native voltage identity and every native
branch. Zero-ohm branches become exact voltage/current constraint equations in
[G B; B^T 0], with no epsilon R or implicit native grounding. Actual uncovered
ends receive fresh latent voltages and symbolic finite end resistances, with
exact length/width ratios and an explicit missing ndiode sheet-model requirement.
Full-tile P1 charge basis and unit-density mass retain these end states.

startup_timing_zero_R_axis_controls_002 checks all 280 selected native chains,
560 native zero-voltage constraints and 560 latent ends. Exact rational original
DC residuals are zero under a synthetic normalized source/load and positive
unit sheet parameter. Full-area mass, reference gauge and independent strip
quadrature all match exactly. Ten unit tests pass, covering mixed finite/zero R,
rotated axes, malformed topology, cross-snapshot IDs, preserved voltage states
and missing sheet-parameter refusal. Exact Schur elimination at sheet parameters
1, 7/3 and 100000 recovers the original core DC matrix without changing native
branches. These parameters and charge densities are synthetic controls; no
ndiode material law, actual C attachment, global constraint rank, PVT or physical
release qualification is inferred or promoted. The original 3,766 deferred
catalog rows remain unchanged. The separate geometry-corrected trace stays live.

All sixteen current native charge shards subsequently complete. The retained
v2 controller advances to its original bounded C++ merge; it is not restarted
or changed to the separately validated future parallel merger.
startup_timing_charge_shard_coverage_001 independently checks every shard's
completed status, actual range counts, exact consumed-span identity, continuous
kernel/event IDs, and contiguous byte intervals in all four native input streams.
Native terminal footers and the independently generated event index agree on
302,171,994 kernels, 332,770,508 events and 267,262,021 owned-pair kernels. The
shards report 830,933,570 operators, with exact operator-kind accounting. This
coverage audit checks consumed-hash manifest lineage and small receipt hashes;
it does not independently rehash every large operator payload or qualify RC.

A separately compiled global-field auditor reconstructs first-encounter IDs
from every ordered shard's full field triples. It checks each local/global map,
explicit substrate reference, operator-manifest paths and complete use of global
fields, preserving distinctions between floating fields and substrate. Six
synthetic controls pass, rejecting wrong IDs, a floating field collapsed to
reference, unused global fields, changed material identity and a wrong operator
path. startup_timing_compiled_field_map_audit_001 is launched against the current
compiler and waits for its completed receipt. It retains the original compiler
PID birth check and deadline, never reruns extraction/compilation, and requires
the completed native coverage audit. Actual full-layout map verification remains
pending until that audit publishes its own completed assessment. No physical or
runtime gate is promoted by these coverage or field-identity checks.

The current v2 merge stays untouched while a separately compiled metadata
candidate parallelizes complete-line ranges using the original retained grammar.
Each worker independently checks its rows and local residue consistency; the
ordered reducer detects duplicate type/plane declarations and conflicting
cross-range residues, enforces one initial BEGIN and one terminal END, then
emits the same sorted JSON metadata. Thirty-two serial/parallel controls pass
across one/four/eight/sixteen threads, including malformed, duplicate, conflicting,
missing-footer and no-final-newline cases.

startup_timing_parallel_metadata_001 hashes the entire retained 12,911,606,800-byte
surfaces input before and after execution and pins the completed serial metadata
from the current shard receipts. Eight-thread native parsing takes 35.868 s;
its output is literally byte-identical to the completed serial reference.
Input hashing and comparison are outside that native-phase time. No isolated
serial-versus-parallel speedup ratio is claimed. The original compilation's
deadline and source artifacts remain unchanged.

The future signoff400-charge-native Make target now uses compile_native_charge_v4.py: eight-thread
metadata parsing plus the already validated sixteen-thread parallel merge. Its
metadata builder pins the exact included serial-parser source/header, compiler,
binary and build command. The controller integration fixture passes and checks
that its receipts include the new source and generated binary/build proof.
The current live v2 pipeline is neither restarted nor switched. Metadata
byte equivalence establishes parsing equivalence only; electrical, full-domain,
PVT and release gates remain open.

The original current-layout charge compilation now completes independently with
its immutable v2 controller, publishing compiled_pending_R_domain_attachment.
It contains 830,933,570 local operators, 2,394,896 global fields and 49,663,543
collapsed-ledger rows (68,189,257 consumed local ledger rows). The independent
startup_timing_compiled_field_map_audit_001 subsequently passes all 14,343,422
local field references across sixteen shards, reconstructing the exact global
IDs and preserving the explicit substrate-reference identity. This validates
all field mappings and pinned metadata artifacts, not all operator payloads or
an assembled physical energy matrix. Original production receipts keep physical
coverage, global passivity, runtime eligibility and release qualification false.
The separate geometry-corrected native R trace remains live; physical signed-C
attachment to verified final R snapshots is the next integration dependency.

A dry run confirms the future command uses v4 with explicit native inputs:

```sh
make -n signoff400-charge-native SIGNOFF400_CHARGE_SOURCE=build/signoff400/startup_timing_electrical_003/native_charge SIGNOFF400_CHARGE_OUTPUT=build/signoff400/metadata_controller_preview_NEW SIGNOFF400_WORKERS=16
```

No new full compilation or extraction is launched by this dry run.

startup_timing_charge_R_domain_map_001 joins all completed C field triples to
the independently audited final R tile catalog using the exact shared native
layout/domain receipt and the observed native plane/type residue table. Its
eight-thread classifier retains source catalog row/byte offsets, snapshot IDs,
tile serials, raw types and effective types. It produces 72,286 typed R bundles
covering all 525,638 selected native tiles, with no located-R material mismatches.
1,875,023 fields have no native R snapshot for their conductor; their geometry
and connectivity remain required, without assuming they are floating or grounding
them. 447,586 fields are tagged arithmetic/unlocated. The initial independent
checker completes row comparisons but omits a zero-count state from Counter;
that failure is retained. Corrected audit_002 explicitly includes every state,
and passes all 2,394,896 field associations and every R tile bundle reference.
Six mapper controls pass, including observed-residue-only normalization, unknown
raw namespace, conflicting residues, duplicate fields and explicit-reference checks.

The arithmetic/unlocated tags are resolved separately rather than assigned a
spatial support. Native ExtBasic output_zero_clamp emits ROUNDING/NODE_ROUNDING
bookkeeping at node output. The pinned compiled ops(ROUNDING) explicitly emits
no physical operator. startup_timing_rounding_field_roles_001 verifies source
and native traced-library build lineage, scans every native SURFACE event using
eight threads, and proves that every unlocated source belongs to the terminal
447,586 G-event suffix, with no unlocated pair target. The corresponding complete
kernel suffix consists exclusively of one ROUNDING/NODE_ROUNDING event per
kernel, with no spatial rectangles/values. Its consumed suffix bytes are hashed;
the retained whole-kernel SHA is referenced, not independently reread in full.
Full surface/field hashes are rechecked before/after. Six surface-classifier cases
and four mixed-record kernel-boundary controls pass.

The role manifest marks global IDs [0,1947310) as physical operator fields
(including reference 0) and [1947310,2394896) as arithmetic-only bookkeeping.
These proven no-op IDs must not allocate physical voltage states; all original
field tables and arithmetic ledger records remain preserved. No spatial field
is collapsed into a reference. This resolves missing-support ambiguity for the
bookkeeping fields, not actual C projection: the remaining 1,947,310 operator
fields still require physical bases/attachment, material/contact models, global
energy passivity, PVT and transient qualification. The geometry-corrected full
native R extraction remains live (last checked beyond snapshot 16,552).

startup_timing_unextracted_geometry_inventory_002 applies the established native
EXT declaration/explicit-alias/port/quoted-device-incidence classifier to the
current audited typed support map and verified final-pass R labels. Its schema
adapter initially tries to erase through the read-only JSON accessor; that
compile failure is retained under inventory_001. The corrected v3 C++ adapter
uses the mutable object, with a separate v2 controller/output. Three adapted
unit tests and six field-role controls pass, including missing/duplicate/truncated
nodes and wrong physical/arithmetic ID intervals. Original classifier sources
remain untouched.

All 2,394,896 current C fields are accounted for: 72,301 lie in components with
native R labels (72,286 physical plus 15 arithmetic), one is explicit reference,
and 2,322,594 lie in declared components without ports, quoted device tokens or
native R labels. Native EXT contains no equivalences, hierarchy, explicit resistor,
connect or merge records. The unextracted set contains 1,875,023 distinct native
conductors with exactly one nonzero resistance class and one spatial field key;
none has only arithmetic fields. Physical IDs and 447,571 associated arithmetic
IDs are retained separately, without assuming ideal conduction or grounding.

The seven leased KLayout jobs in startup_timing_unextracted_GDS_geometry_001
check the exact current cap-view GDS. Every one of the 1,875,023 native probes
matches a unique polygon with exact area/perimeter scaling and plane/material
agreement. There are 1,874,968 rectangles and 55 nonrectangles (one M4, 54 M5),
with no missing/ambiguous probes or duplicate component boxes. Full geometry
attribution takes 114.37 s in this run; no cross-run speedup ratio is claimed.
The all-rectangles flag remains correctly false. Material counts are 74,826 LI,
597,430 M1, 569,020 M2, 252,358 M3, 193,490 M4, 8,385 M5 and 179,514 poly.

All 55 complete Manhattan hulls/hole lists are retained under
startup_timing_unextracted_nonrectangles_001 (up to eight hull vertices, no holes
in this sample). startup_timing_unextracted_sheet_controls_001 checks every
exception and seven real material rectangles at refinements one/two/four:
186 exact area, boundary, floating-nullspace, connected-conductance, affine-energy
and unit-density mass checks pass. Actual C projection, complete basis instance
construction, calibrated resistance/temperature models, global passivity, PVT
and release qualification remain open. The geometry-corrected native R trace
continues under its unchanged owner/deadline.

startup_timing_unextracted_sheet_instances_001 constructs compact spatial-basis
specifications for all 1,875,023 current unextracted conductors with seven
independent compiled material workers. Every instance preserves its physical
field ID, conductor name, actual translated polygon origin, native/GDS source
row and byte offsets, nominal sheet class and distinct voltage namespace.
447,571 arithmetic IDs remain separate metadata and receive no physical states.
The documented nominal rules are parsed inside the pinned PDK environment;
every native class matches the applicable LI/poly/M1-M5 rule, with explicit
milliohms-per-square units. Reference temperature and PVT remain unqualified.

The geometry cache reduces 94 material-local template requests to 74 shared
translation-free shapes, without coalescing conductor identities or sheet
parameters. Exact rational P1 stiffness/mass and geometry certificates are
stored at refinements one/two/four (222 variants). Instance origins and template
coordinates retain the exact GDS-to-native coordinate ratio. Unit-sheet
stiffness scales to nominal siemens by 1000/native-sheet-milliohms; mass remains
unit area, with no actual C density attached. Templates retain each floating
constant-voltage nullspace. No global matrix is materialized by these descriptors.

The independent seven-process instance audit checks every native/GDS/instance
row and consumed hash, every source offset, nominal class, field-role partition,
namespace and shared-shape alias. It reconstructs all saved element matrices
from serialized triangles using rational gradients and checks measures, reference
units and floating row sums. A supplemental lineage receipt binds all semantic
source metadata and explicit global template IDs to the parent proofs. Logical
floating node specifications total 7,500,317 / 16,875,883 / 46,877,831 at the three
refinements; these are alternative discretizations, not simultaneously allocated
physical circuits. Seven constructor controls pass, including cache reuse with
distinct namespaces and rejection of wrong identities, sheet rules, scales,
physical IDs, missing contours and arithmetic roles. Matrix-audit tests reject
corrupted stiffness/mass/vertices and duplicate variants.

The separate corrected native R pipeline also completes. Its pre-R C/device
comparison matches the original reference; all 18,578 snapshots and 18,207
original conductors are indexed, with 1,527,578 private nodes. Full registration
checks all 1,360,129 wire creation records and 472,181 contact branches: zero
wire geometry failures, zero rectangular interpolation failures and zero outside
endpoints. This closes the original measured creation-geometry defect on the
actual layout. The candidate remains explicitly unadopted: final-export snapshot
selection, contact/material qualification, updated R bases and actual signed-C
projection must still be established. No physical, runtime, PVT or release gate
is promoted by these geometry/basis checks.

The corrected-R final-export check also passes in
`startup_timing_interface_final_snapshot_export_001`: all 18,207 final snapshot
node/resistor multisets match the overwritten `.res.ext` exactly (1,051,995
nodes and 1,214,497 resistors). The 371 automatic-pass snapshots are retained
as superseded history. The v2 wrapper binds the actual diagnostic source and
build receipt to the completed domain, verifies native overwrite/pass semantics,
and reuses the controlled compiled multiset checker. This selects the final
geometry without qualifying contact materials, temperature laws or C attachment.

The corrected all-pass chain/axis rebuild is retained separately as
`startup_timing_interface_wire_chains_001` and
`startup_timing_interface_axis_registry_001`. All 1,360,129 wire segments and
601,117 chains are preserved; 600,561 geometric axes are prepared, including
280,852 chains requiring 387,636 finite nominal end resistors. No creation
geometry or topology deferral remains; 556 zero-R chains require exact constraint
treatment. These counts include superseded snapshots and do not yet describe
the selected final basis. All nominal values remain temperature/material
unqualified; no native core resistor is rewritten.

Both independent corrected axis and tile-catalog audits pass. The final snapshot
partition and independent byte/identity audit pass in
`startup_timing_interface_final_R_catalog_001` and its audit: 525,638 selected
tiles (463,014 axis candidates, 62,344 anchored sheets, 280 zero-R deferred
axes), with 147,170 superseded rows retained verbatim. The original final
creation-geometry deferrals are eliminated. The new C/R mapping wrapper requires
the original C reference domain and pre-R cards, common GDS/technology digests,
and the corrected producer's completed pre-R equivalence proof. One positive
bridge control and six mutated lineage/equivalence cases pass. Physical C
projection and material/contact/PVT qualification remain pending.

The corrected C/R candidate map completes: all 2,394,896 global fields are
accounted for, 72,286 typed R bundles cover all 525,638 selected tiles, and no
located R material is unmatched. The independent full mapping audit is separate.
Corrected zero-R controls in `startup_timing_interface_zero_R_axis_controls_002`
pass for all 280 selected chains, 560 exact voltage constraints and 560 latent
ends, preserving current private-node identities. The first attempt is retained
as failed: the v2 checker hardcoded historical axis/chain paths. The v3 checker
resolves and verifies the catalog-bound registry and its chain source before
reading offsets. Zero-R end-sheet parameters remain synthetic and diode
material/PVT qualification remains false.

The independent corrected C/R map audit passes for every field and selected
tile. `startup_timing_interface_field_role_stability_001` streams both complete
old/new field maps and verifies their producer hashes: every field key and
support role is identical, and every non-R field payload is unchanged. Thus the
existing 1,875,023 unextracted-conductor sheet instances retain their C-field
identities. 396 R-candidate payloads differ, so corrected R bundles/private-node
registries must be used exclusively. Arithmetic bookkeeping fields remain
nonphysical. This stability check does not project any operator or assemble C.

The concrete floating basis resolver is now available.
`startup_timing_floating_basis_index_001` uses seven compiled material workers
to index all 1,875,023 audited instances into a 38,318,352-byte little-endian
field lookup (2,394,896 slots), retaining absence for R/reference/arithmetic
fields. `FloatingBasisResolver` verifies source/index/audit bytes, resolves
instance offsets lazily, translates atlas coordinates exactly, and emits named
P1 payloads `_fmesh_<field>:r<ref>:n<point>`. It also resolves nominal-Siemens
stiffness with the shared atlas and instance sheet value, preserving floating
row sums and separate conductor identities. No global mesh is allocated.

`startup_timing_floating_basis_resolver_controls_001` independently streams every
instance/index offset and projects one interior rectangle for each of 94 local
shapes at refinements 1/2/4: 282 compiled results match the exact rational oracle.
Unsupported reference/R/arithmetic/out-of-range fields and refinement requests
are rejected. The derived rational-coordinate compiled engine passes 23
compatibility/control tests, including nonbinary coordinates and cancellation
of identical named fields. These are unit-density integration controls, not
actual native-C operator projection, assembled C, material/PVT or release proof.

Actual signed-C controls now use the current field index and named payloads.
`startup_timing_floating_native_operator_samples_001` rehashes the complete
selected retained operator shard, field table/map and current GDS geometry
partitions. Its compiled sampler scans 2,000,000 rows in 16 byte windows and
retains 22 material/sign/support buckets. These include A/L reference cases,
poly-to-poly line coupling, and positive/negative poly-to-LI/M1-M5 fringe
operators. Unsupported R-domain fields remain excluded from this selected
floating-only control; no ideal-conductor substitute is introduced.

`startup_timing_floating_native_projection_001` resolves each actual field
against current audited instances and conductor identities, and projects all
22 operators at refinements 1/2/4 (66 matrices) using the eight-thread compiled
GMP/long-double engine. Independent eight-process rational A/L and 90-digit
fringe oracles pass: A/L entries agree exactly, maximum normalized fringe
error is 1.1672636815349157e-16. Signed local energy controls pass. This closes
the actual-operator hookup for selected floating fields, not full operator
coverage, mixed R/floating projection, global C assembly/passivity or PVT.

Corrected native-R fields now have a compact bundle index in
`startup_timing_R_basis_index_001` (72,286 R fields in 2,394,896 global slots).
`RBasisResolver` verifies the current mapping audit and exact source bytes,
looks up the catalog-bound axis/chain records, and constructs bases only for
tiles intersecting an operator's area/line support. It handles existing axis
knots, finite nominal end states, anchored sheets and explicit zero-R voltage
constraints, preserving private native identities. Payloads retain auxiliary
unit-sheet/end-stub/symbolic-zero-R metadata; unknown material laws remain
unqualified. The initial resolver supports native R refinement one only.

`startup_timing_mixed_native_operator_samples_001` rehashes the retained shard
and scans 2,000,000 rows in 16 windows, retaining 97 sign/material/support
buckets, including native/restored R-to-R and R-to-floating cases.
`startup_timing_mixed_native_projection_001` projects all 97 cases through
current resolved bases with eight compiled workers and independent eight-process
exact/90-digit oracles. A/L matrices agree exactly; maximum normalized fringe
error is 8.354941572717516e-18. Selected signed-energy controls pass. This is
mixed-operator hookup at native R refinement one, not full operator coverage,
refinement convergence, native scalar-rounding density assignment, global C
assembly/passivity, calibrated materials/PVT, transient or release qualification.

The independent R index audit also passes: every one of 2,394,896 field slots
is checked, with exact bundle offsets, lengths and field keys for all 72,286
R fields and explicit absence in every non-R slot. Current producer hashes
match the streamed source bytes.

Full native-R mesh preparation is now compiled and parallel.
`startup_timing_R_runtime_meshes_001` materializes every selected R tile with
eight C++ workers: 525,638 tiles, 3,707,661 mesh points and 2,659,222 triangles.
The separate eight-process exact audit reconstructs every tile using the
existing axis, anchored-sheet and zero-R constructors, checks every point/name/
triangle and auxiliary-model record, and verifies exact selected catalog
coverage and all consumed hashes. All rows pass. These counts describe the
mesh descriptions, with shared native voltage names retained.

`RuntimeGeometry` now loads the audited R meshes and floating instance/shape
specs in compiled code, interns native/latent node names, builds per-field
spatial trees, and resolves only intersecting R tiles. Floating shape reuse
preserves separate conductor potentials. The resulting deterministic node map
contains 9,147,614 voltage identifiers, including the explicit reference; this
is a projection basis, not a qualified assembled circuit or runtime unknown
count. Arithmetic fields have no physical basis.

`startup_timing_compiled_runtime_geometry_controls_001` projects the same 97
actual mixed operators using that provider and eight compiled workers. All A/L
matrices match exactly, and fringe matrices have zero observed delta from the
independently controlled Python-resolved payload path. Native geometry load
plus these projections takes 22.4367 seconds on this run; no isolated speedup
claim is made. Full operator streaming, external sparse reduction, complete C
assembly/passivity, refinement convergence, numerical scalar-rounding spatial
assignment and material/PVT/transient/release qualification remain pending.

The compiled geometry provider now feeds full operator streaming. The derived
provider prunes triangles using conservative integer support bounding boxes;
all surviving geometry still passes exact area/line coverage and shared-edge
checks. `stream_project_charge` consumes local-to-global field maps, retains
native signed coefficients, validates per-operator matrix symmetry, uses
canonical geometry caches and Neumaier long-double accumulation, and writes
bounded sorted upper-triangle sparse runs with absolute contribution sums and
term counts. Reference, physical R and floating fields remain distinct; no
physical state is allocated for arithmetic fields. Exact zero-density/measure
operators are counted separately.

The SPCRUN01 format stores little-endian packed 32-bit row/column identifiers,
10-byte x87 extended-precision value and absolute sum, and a 64-bit term count
in a 40-byte record, with explicit ABI assertions and zero reserved bytes. The
controlled merger checks sorted unique keys, finite complete records and
headers, and performs compensated external reduction with bounded fan-in.
`startup_timing_stream_projection_controls_001` streams all 97 actual control
operators through forced 32-entry flushes: 27 sparse runs reduce to 735 upper
entries, matching the independent 90-digit sum of the previously controlled
matrices to 1.4805915468302991e-18 normalized error. This fixture is not full
native operator coverage.

`startup_timing_full_spatial_projection_001` starts the full 830,933,570-operator
pass with 16 compiled workers, a 12-hour whole-check limit, full pre/post input
hashing, bounded one-million-entry accumulators and local retained scratch.
It reuses the completed native extraction and frozen controlled binaries.
Sorted runs and node-map ranges are retained on success or failure. The
separate reduction controller is ready to merge the complete run set after
projection succeeds; no full projection/reduction gate is promoted while the
pass is live. Native scalar-clamp spatial assignment, global matrix/passivity,
refinement, materials/PVT and transient/release requirements remain open.

Sparse-stream adversarial controls found a reader-validation omission while
the full projection continued: the original merger accepted a finite absolute
contribution sum below the signed magnitude. The failed control receipt is
retained in `sparse_run_format_controls_001`. The independently derived v2
reader/writer validates that bound (with an explicit 32-long-double-epsilon
rounding allowance) and requires upper-triangle keys. SPCRUN01 bytes remain
compatible, and the live producer and its pinned sources are unchanged.

`sparse_run_format_controls_002` passes severe-cancellation/term-count controls
and rejects all 15 malformed cases, including bad/truncated headers or records,
trailing bytes, duplicate/descending keys, nonfinite values, nonpositive term
counts, negative/inadequate absolute bounds, reserved bytes and lower-triangle
keys. The corrected lower-triangle fixture remains sorted so the check isolates
that semantic invariant. `sparse_merger_upgrade_controls_001` remerges all 27
actual-control runs with the hardened binary and proves byte identity with the
previous 97-operator reduction. The external reduction controller now requires
that validated upgrade and its passing format controls. Full projection remains
a separate running check; none of these storage controls promote physical RC.

The ideal-conductor collapse maps are prepared and independently audited in
`startup_timing_spatial_conductor_maps_001` and its audit. Every one of
2,394,896 fields and 9,147,614 voltage identifiers maps to the correct original
conductor among 1,893,231 names (including the explicit reference). Native/
latent R names are checked against the 18,207 selected final groups; floating
ranges are checked against physical fields. Arithmetic fields are mapped only
for scalar bookkeeping and allocate no voltage states. The live producer's
node maps are closed before shard execution; their final parent-assessment
hashes must still be reconciled when the projection completes.

Source inspection confirms that `collapsed_matrix_ledger.json` stores scalar
capacitor edges, with columns [field_a, field_b, native_delta, physical_operator_
integral, absolute_error]. Expected conductor matrices therefore expand an
edge as +C on both diagonals and -C off diagonal, cancelling same-conductor
scalar edges, rather than interpreting the ledger as expanded matrix entries.
The expansion/alias/column/signed-capacitor controls pass at 1, 4 and 8 threads
in `native_ledger_collapse_controls_002`. The first harness attempt is retained
with its log-name collision; it is not a numerical failure.

All 49,663,543 native scalar-ledger rows are expanded with eight compiled
workers and externally reduced into two references: physical-integral upper
matrix (45,780,221 entries) and native-output upper matrix (45,833,579 entries).
98,226 same-conductor scalar edges cancel. The original preparation controller
finished the native calculations but failed its completion check because its
path list contained duplicates while its hash dictionary did not. That failed
attempt remains intact. `startup_timing_native_conductor_ledger_002` uses the
corrected checker to verify all current producer-pinned inputs and existing
merge configurations/logs/outputs, seal the results, and record explicit reuse
without re-executing the calculation. Spatial equivalence, clamp-density
assignment and physical/PVT/release gates remain false.

`startup_timing_spatial_projection_followup_001` watches the exact original
controller PID/birth, without restarting it. It launches the controlled external
reduction only after that controller terminates successfully and publishes full
operator coverage and completed input/output hashes. It stops without promotion
on upstream failure or expiry of the original check deadline. The validated
reduction controller and follow-up sources are now pinned for that pending job.

`spatial_matrix_collapse_controls_001` prepares the compiled P^T C P path
needed for full spatial/native equivalence. A separate full symmetric matrix
oracle checks conductor aliases, conductor permutations and the factor of two
for off-diagonal spatial coefficients that collapse onto a conductor diagonal.
All six cases (two permutations at 1/4/8 threads) pass, with original upper-
source term counts retained. The binary reader checks complete finite sorted
upper-triangle slices and global slice-boundary ordering. This is controlled
comparison tooling; the full projected matrix is still being computed.

`startup_timing_native_reference_delta_001` quantifies the complete difference
between the physical-integral and native-trace references over 45,884,385
union upper entries. All 42,188,275 conductor-to-conductor coupling entries
are within the declared 1e-8 absolute + 2e-12 relative tolerance. The large
differences are reference/ground and diagonal terms: reference-edge signed
delta sums to -4,479,662.489730426 retained native capacitance units. 884,503
entries exceed that tolerance, all in the reference/diagonal categories. This
is an analysis-only result, not an equivalence or passivity failure of the
still-running projection, and it does not assign scalar-clamp spatial density.

Additional native-source inspection clarifies reference semantics. The EXT
declares substrate `VGND`; `extRelocateSubstrateCoupling` moves pair coupling
to that substrate onto each node's printed ground-capacitance record. Thus
the historical `native_output_reference_matrix` metadata points to an UNFOLDED
native-trace-delta matrix: its abstract reference and physical VGND conductor
remain separate. Native ideal-netlist comparisons must identify those two
conductors. This identification is solely an ideal-collapse comparison step,
not a change to the live finite-R voltage basis or qualification of finite-R
substrate targets. Full printed-native reconstruction remains unverified.

`startup_timing_substrate_reference_binding_001` pins the native EXT, trace
reference, conductor names and relocation source. It identifies substrate
`VGND` as conductor 1, separate from abstract reference 0. Two actual M5
clamp examples confirm that the sum of their abstract-reference and VGND
off-diagonal coefficients predicts the printed ground capacitance: residuals
are approximately 9.38e-13 and 1.19e-12 native units against printed zero.
The lookup decodes extended-precision coefficients exactly as rational values.
This is a selected relocation/binding control; full printed-native matrix
reconstruction and finite-R substrate target qualification remain false. The
current spatial projection and its immutable basis are unchanged.

`verify_spatial_conductor_equivalence.py` is prepared to reconcile the live-
prepared conductor maps with the FINAL projection node-map hashes, collapse
every reduced spatial coefficient by P^T C P with eight compiled workers,
externally merge the result, and compare all coefficients with the physical-
integral reference using the declared 1e-8 absolute + 2e-12 relative tolerance.
Its scope is explicitly the unfolded abstract-reference physical-integral
matrix, not printed-native reconstruction or scalar-clamp spatial assignment.
`startup_timing_spatial_equivalence_followup_001` watches the exact existing
projection/reduction follow-up PID/birth and starts this check only after full
upstream success. All relevant sources/receipts are pinned while it waits.

`startup_timing_material_passivity_screen_001` supplies an early NECESSARY
passivity check on a seven-dimensional subspace: each floating material shares
a voltage, while the abstract reference and all extracted conductors are fixed.
Every one of 1,875,023 floating conductors is assigned to its actual material
through the independently verified field/conductor maps; 18,208 conductors
remain fixed. Full native-reference matrices are collapsed with the controlled
parallel P^T C P engine. Both seven-material matrices have positive sampled
minimum eigenvalues (physical-integral 11,767,605.443209022; native-trace
12,528,064.079291075 in retained native units under unit Euclidean group-
voltage normalization). Exact-rational evaluation of the selected numerical
eigenvector finds no negative-energy witness beyond the recorded accumulated
roundoff allowance. This does not establish PSD outside those seven modes;
full-matrix passivity and all physical/PVT/release flags remain false.

`matrix_structure_controls_001` validates the compiled two-pass matrix auditor
with 21 cases across 1/4/8 threads. Controls include charge imbalance, negative
diagonals, negative 2x2 principal minors, zero diagonal with coupling, and an
indefinite matrix whose every 2x2 minor is positive. That last matrix has an
independent exact grounded voltage witness with energy -2; the auditor correctly
reports only necessary checks and never claims full PSD.
`startup_timing_reference_matrix_structure_001` checks every coefficient in both
complete unfolded conductor references: 45,780,221 physical-integral and
45,833,579 native-trace upper entries over 1,893,231 conductors. Maximum scaled
charge residuals are 6.477e-20 and 5.901e-20, respectively, against 1e-12.
Neither contains a significant negative diagonal or 2x2 principal minor.
These are representation checks with abstract reference separate from VGND;
they establish neither full spatial passivity nor printed-native equivalence.

`startup_timing_ideal_substrate_references_001` applies the controlled eight-worker
P^T C P engine to both complete conductor references, identifying abstract
reference 0 with native substrate VGND (old conductor 1). The resulting ideal
comparison matrices contain 1,893,230 conductors. Complete map serialization,
the single intended alias, all conductor names, and input/output hashes are
checked. The live spatial basis is unchanged; this fold supplies no finite-R
substrate target assignment or scalar-clamp spatial assignment.

`startup_timing_native_printed_cap_scale_003` pins the actual Magic sources and
checks three nonzero native couplings against printed EXT values. The source
defines the header order as R C D: resistance 1000, capacitance 1, distance
500000. Both OpenPLLTraceGround and OpenPLLTracePair divide by capacitance
scale 1, so compiled trace coefficients use the SAME units as printed EXT values.
The initial `_001` control incorrectly divided by the distance factor and failed.
Version 2 checked the correct numerical coefficient values but incorrectly
described the third header field as capacitance metadata; version 3 supersedes
that metadata using pinned writer AND reader source semantics. Printed values
use default C `%lg` precision, so full native reconstruction must account for
serialization bounds. These selected controls do not claim that full comparison.

`printed_EXT_matrix_controls_003` validates the C++20 printed-EXT matrix compiler
and bounded streamed comparator against an independent exact-decimal edge
assembly at 1/4/8 threads. Controls cover byte-window boundaries, all declared
nodes, substrate identity, same-conductor cancellation, signed couplings,
zero ground capacitance, scientific notation, suppressed trailing zeroes and
an intentionally changed native coupling. Each printed edge contributes its
default six-significant-digit `%lg` rounding allowance to all affected matrix
coefficients; the independent error matrix also retains the parsing allowance.
The comparator adds the declared 1e-8 absolute + 2e-12 relative numerical bound
and an accumulated roundoff allowance. The earlier two failed control outputs
are retained with their oracle/representation-guard failure explanations.

`startup_timing_full_printed_native_matrix_001` runs this controlled parser over
the complete native EXT using eight workers, externally merges both coefficient
and serialization-bound matrices, and compares every entry with the complete
substrate-folded native trace matrix. Its work directory is evidence of a run,
not successful comparison: require its final assessment before claiming full
printed-native reconstruction. Even success would establish ideal-conductor
trace/native equivalence, not finite-R substrate binding, clamp spatial
allocation, full spatial PSD or physical/PVT/release qualification.

The first full printed parse stopped on `a_198560_864#`, a printed `fomfill`
node absent from the charge-field namespace, with exactly zero printed ground
capacitance. It did not silently discard that node. The derivative parser in
`printed_EXT_matrix_controls_004` retains unmapped zero-only nodes as explicit
additional zero matrix rows, with deterministic new IDs and a complete sorted
name ledger. Every known conductor must still appear exactly once. Any unmapped
nonzero node capacitance, unmapped coupling endpoint, or duplicate zero-only
node fails; three negative controls verify these failures. All 1/4/8-thread
matrix and precision controls pass with the extra row present.
`startup_timing_full_printed_native_matrix_002` uses this controlled derivative
for a new full comparison, retaining `_001` as a failed work directory. Require
the new final assessment and its explicit zero-extension ledger before claiming
full printed-native reconstruction. This only qualifies the capacitance matrix
comparison, including zero rows; it supplies no physical model for fill material.

`startup_timing_spatial_structure_followup_001` watches the exact live
projection/reduction follow-up PID and birth identity. Only after full upstream
success does it run the controlled eight-thread necessary matrix checker over
every reduced spatial coefficient, with a 16 GiB bound and its own twelve-hour
check budget. Charge conservation uses the 1e-12 scaled limit. Diagonal and
2x2-minor diagnostics apply to the unfolded, unconstrained FEM matrix; zero-R
and actual substrate constraints have not yet been imposed. Any negative mode
needs a constraint-compatibility check, and passing these necessary tests does
not establish full spatial PSD. No qualification is promoted automatically.

`startup_timing_full_printed_native_matrix_002` has now completed successfully:
44,252,422 union upper-matrix entries compare within their accumulated printed
serialization and declared numerical bounds, with ZERO out-of-bound entries.
The complete parse covers 1,915,189 printed nodes, 40,470,849 coupling records
and 21,959 explicitly retained zero-extension nodes. The folded trace and
printed matrices have 447,659 trace-only and 7,036 printed-only stored entries;
these also pass the same zero/missing-entry comparison rather than being
discarded. Maximum absolute coefficient delta is 5.023409318226186 retained
native units; its accumulated serialization bound contains it. This closes
the full ideal-conductor capacitance trace/printed-native comparison only.
Finite-R substrate binding, scalar-clamp spatial assignment, complete spatial
passivity and all physical/PVT/release gates remain unqualified.

`startup_timing_printed_zero_extension_audit_001` independently re-reads every
extra node from the full native EXT and verifies its unique identity, zero
printed capacitance, native position and type. All 21,959 rows match: 21,935
`fomfill` and 24 `rmp`. Their deterministic additional IDs and complete node
inventory are retained. Absence as a coupling endpoint remains supported by
the controlled full parent parser, not a second independent endpoint scan.

`startup_timing_final_device_basis_001` uses a controlled C++ identity mapper
to select only the 18,207 final native R groups and bind every retained device
private node to the spatial voltage namespace. It retains 206,708 terminal
records and excludes 100,882 superseded records without deleting their source.
All retained bindings resolve to existing spatial voltage IDs: 203,930 unique
nodes, zero missing/R-only device nodes. Controls distinguish an absent spatial
state from a valid private node and reject missing or wrong-conductor private
identities. Device locations are never substituted for terminal coordinates.

`startup_timing_final_device_basis_audit_001` independently joins all 51,829
unique devices by native model and device location to the final `.res.ext`
export. Every one of their 206,708 terminal names agrees exactly with its
private-node binding, and all global voltage IDs are independently re-read from
the spatial node ledger. Native model coverage is 5,190 nfet_01v8, 20,104
nfet_01v8_lvt, 21,025 pfet_01v8, 5,198 pfet_01v8_hvt, eight special nfet,
280 pw2nd diodes and 24 generic-poly resistors. Native terminal enums and
printing source bytes are pinned. This proves native-export terminal identity,
not the SPICE device-parameter join or physical interface qualification. The
closed startup voltage ledger still needs reconciliation with the final live
projection receipt. Finite-R substrate binding, material/PVT and runtime model
eligibility remain unqualified.

The attempted `startup_timing_spatial_device_parameters_001` join failed rather
than silently accepting pre/post-R device parameter changes. Its partial
`devices.spice` fragment is INELIGIBLE and must not be used as a runtime deck.
The actual extractor already retains a two-phase `SPICE_devices.log` mapping
every SPICE instance to native model, geometry and L/W; both phases contain the
same 51,829 device identities. The parameter-preserving join detects an actual
native export issue, not a missing physical-device identity.

`startup_timing_native_device_parameter_delta_001` compares every complete
pre/post-R device card, retaining the complete paired-card cache and exact
parameter difference ledger. Exactly TWO devices change, only in `as` and `ps`:
`X14` nfet_01v8 changes `as=2.73235k ps=25.27059k` to zero; `X52` pfet_01v8_hvt
changes `as=4.74784k ps=39.46998k` to zero. Aggregate source area falls from
15308.81944 to 7828.62944 and source perimeter from 133939.13 to 69198.56 in
retained native SPICE parameter units. Drain area/perimeter totals are unchanged.
The native EXT record for X14 has a zero-length source terminal with attribute
`0`; its R export supplies a nonzero source width while still lacking explicit
source area/perimeter. The pinned `spcnAP` implementation can source implicit
area/perimeter from the original node, whereas renamed R nodes no longer carry
that original aggregate. This identifies a junction-geometry allocation gap;
neither silently copying the original lumped geometry onto a spatial terminal
nor accepting the missing post-R geometry qualifies a finite-R nonlinear model.
Native device parameter preservation and spatial junction assignment remain open.

`printed_EXT_matrix_controls_005` corrects the parser's header validation to
check R, C and D separately and rejects two deliberately interchanged scale
configurations. `verify_printed_native_matrix_v3.py` uses the corrected unit
receipt and explicit field names for future full comparisons.
`startup_timing_printed_matrix_header_semantics_001` seals the existing successful
full numeric comparison with the corrected metadata, without rerunning it.
It proves the parser source change is confined to the stronger header-validation
branch, verifies all six 1/4/8-thread coefficient/error matrices are byte identical,
and rehashes the complete retained final matrices, comparison and zero-node map.
The old parser validated the actual D field under a wrong configuration key;
it never applied that value to matrix arithmetic. Full numerical comparison
therefore remains verified. Earlier incorrect header metadata is superseded;
physical/PVT/release qualification remains false.

`startup_timing_native_junction_fallback_001` traces both changed native devices
to their original zero-width source terminal and whole-node fallback class.
X14 uses VGND class 4: native node area/perimeter 109294046/5054118, predicting
2732.35115/25270.59 in the printed native parameter units. X52 uses VPWR class 5:
189913666/7893996, predicting 4747.84165/39469.98. Both agree with the original
six-significant-digit parameter tokens. Independent native trace L/W and SPICE
L/W establish the 1/200 length conversion for these cases. The full EXT scan
retains 2,144 implicit terminals; all are sources with zero terminal edge length,
attribute `0`, and the same original source/bulk conductor. Explicit terminal
area/perimeter inventories are retained separately. This establishes whole-node
fallback behavior, not a valid spatial placement for that aggregate junction.

`startup_timing_native_junction_alias_probe_001` retained a DC-table shape
failure: Xyce omits the sweep coordinate unless explicitly printed. The revised
`_002` decks print that coordinate and probe the original two devices with their
native D/S/B external aliases, plus deliberately split source/body controls.
The revised check fails its strict native-response comparison; it is not promoted.
`startup_timing_native_junction_alias_failure_analysis_001` reuses all eight
completed PVT cases without rerunning simulations. Maximum complex-current
relative difference is 1.3034575810408396e-8, maximum absolute phasor difference
1.1007373875495617e-12 A across retained 1 MHz/400 MHz responses. Split-node
controls show at least 2.157117173492607e-5 A sensitivity to the geometry change.
Tiny standalone real-current components must not be confused with whole-phasor
relative error; the diagnostic does not replace the failed strict test with a
looser acceptance gate. The failed controller did not publish pre-run native
model hashes, which is explicitly recorded as a provenance limitation. All-15-PVT
equivalence, native runtime eligibility and spatial junction qualification
remain false. The result rules out assuming exact equivalence from external
node aliases alone; it supplies no permission to ignore finite-R junction terms.

`startup_timing_native_junction_support_001` resolves the complete geometric
support of both whole-node fallback junctions against final native R tiles.
VGND ndiff uses 15,453 tiles with exact area/perimeter 109294046/5054118;
VPWR pdiff uses 17,934 tiles with exact area/perimeter 189913666/7893996.
The packet retains each tile's catalog byte offset, native group/private nodes
and box, plus every uniquely owned outer boundary interval: 60,073 ndiff and
69,273 pdiff segments with outward normals. Internal subdivision edges cancel
exactly, including nonconforming splits; hole and duplicate controls pass.
The packet is NOT an extra junction to add on top of existing MOS junctions.
Whole-node-minus-explicit-MOS bookkeeping gives area/perimeter differences
5927546/338772 for VGND and 10099732/495704 for VPWR; these totals do not identify
a spatial residual partition or establish physical additivity.

`startup_timing_native_junction_support_audit_001` independently builds polygon
unions in compiled KLayout geometry, rechecks every tile against its exact native
catalog offset, and verifies both aggregate area/perimeter AND every directed
owned boundary interval. All 33,387 tiles and 129,346 boundary segments pass.
This closes geometric support for the two aggregate terms, while overlap with
explicit MOS junction allocation, nonlinear law/PVT qualification and finite-R
bulk support binding remain open. Runtime and physical/release flags stay false.

`startup_timing_final_native_R_core_002` joins every final native core R node
and branch to the immutable spatial voltage ledger. All 1,051,995 nodes and
1,214,497 branches map to existing voltage IDs; there are no missing/R-only
core nodes, no missing branch endpoints and no self branches. The core contains
1,213,937 positive native resistors and 560 exact zero-voltage branches. Positive
values retain their native float32 bit pattern, original milliohm trace token,
printed native ohm token and nominal conductance; zero branches receive no
finite conductance or epsilon resistor. All selected 18,207 snapshots retain
their private identities, endpoint coordinates and native branch/type metadata.
Controls verify positive/zero semantics, explicit missing-state reporting and
wrong-coordinate rejection. `_001` retains a missing-header build failure and
its archived source; `_002` corrects that build without rerunning extraction.

The expanded conductance assembly must retain these native core values and add
only the required end-stub, anchored-sheet and floating-sheet conductance models.
Adding a full unit sheet on top of an already represented native axis chain
would double count its longitudinal conductance. The complete G matrix,
material/PVT laws, all symbolic semiconductor ends and final producer-receipt
reconciliation remain open; this namespace join promotes no physical/runtime
qualification.

`startup_timing_zero_R_voltage_map_002` prepares the exact voltage transform
for all 560 native zero-ohm branches. All 1,214,497 native core branches are
accounted for; the 1,213,937 positive resistor values are unchanged. Zero edges
touch 840 native voltages in 280 components and have rank 560 with no redundant
equations. The compacted basis contains 9,147,054 voltage states versus the
original 9,147,614. A separate graph traversal checks every original map slot,
and every native zero-R equation is independently matched against its compiled
R-mesh counterpart by native group, branch pointer and private endpoints.
Cycle/transitivity controls and reference-alias rejection pass. The initial
`_001` failure came from a malformed minimal positive-branch fixture; its failed
controller is retained, and `_002` uses the actual producer schema.

The CNETDOF1 transform is ready for controlled P^T C P/G assembly. It introduces
no epsilon resistor and performs no substrate/reference identification. Its
voltage count excludes any additional device/internal or MNA current unknowns.
Final live-projection receipt reconciliation, full G assembly, physical material
and substrate/junction qualification remain open; no runtime or release gate is
promoted by this exact native constraint transform.

`zero_R_matrix_transform_controls_001` validates a compiled streaming P^T C P
path specialized to the exact compacting zero-R map. Entries whose endpoints
survive retain strict key order and bypass sorting; only entries touching
removed voltage IDs enter bounded exceptional accumulators. Every map slot is
validated before this fast path is used. Three independent full-symmetric
24-node references, forced small flushes, symmetry factors, the no-alias case
and a rejected noncompacting permutation pass. Complete reduced output bytes
match the existing controlled general transform, including absolute bounds and
term counts. No full-production speedup is claimed before measurement.

`startup_timing_spatial_zero_R_followup_001` watches the exact existing
projection/reduction follow-up PID and birth. After successful full coverage,
it reconciles both final producer node-map hashes, applies the controlled
streaming zero-R transform, merges any exceptional runs and runs the eight-thread
matrix structure checker on every constrained row and nonzero 2x2 minor.
All sources/binaries are pinned while it waits. The result will retain exact
native zero-R constraints but no substrate fold or scalar-rounding allocation.
Necessary checks remain distinct from full PSD and physical qualification.

`startup_timing_floating_conductance_001` assembles the complete nominal
floating-sheet G component in compiled C++, covering all 1,875,023 conductors
and 7,500,317 voltage states. Exact rational checks establish symmetry, connected
nonnegative edge conductances and the constant nullspace of all 74 refinement-one
unit templates. Positive documented nominal sheet values scale them into
siemens using 1000/sheet_milliohms; 81 shared shape/sheet pairs are cached.
Sorting the instance blocks by their already assigned voltage ranges permits
direct output of 15,000,747 ordered upper coefficients without a global sparse
sort. All 447,571 linked arithmetic IDs retain no voltage state. Floating
conductors are not grounded.

The independent numerical structure checker reads every resulting coefficient
and row. Maximum scaled G constant-voltage residual is 3.6520142519221052e-20,
with no negative diagonal or significant negative 2x2 principal minor. The
1,647,297 zero rows are the abstract reference and native-R prefix, which this
floating-only component intentionally does not populate. Exact square-sheet
controls check node order and nominal scaling; zero and negative sheet values
are rejected. The exact template certificates and numerical checks do not
promote full-matrix/physical passivity. Native core G, end stubs and anchored
sheets still need assembly, and nominal reference temperature, material/PVT and
final producer-map reconciliation remain unqualified.

`startup_timing_native_core_conductance_001` assembles all 1,213,937 positive
native core resistors with eight compiled workers. Original float32 milliohm
bit patterns are decoded directly and independently checked against their
retained trace tokens before conversion to siemens. Sixteen bounded sparse
runs containing 3,641,811 upper contributions reduce to 2,257,561 unique upper
entries. All 560 zero-ohm branches remain separate exact voltage constraints;
they receive neither finite conductance nor epsilon resistors.

The complete native core G passes the numerical row and principal-minor audit:
maximum scaled constant-voltage residual is 5.0715692599115594e-20, with no
negative diagonal or significant negative 2x2 minor. The reported 8,095,621
empty rows are outside this positive-core component, including floating sheets,
latent extension states, the reference and two zero-R-only native nodes.
Exact two-resistor/zero-constraint controls produce identical matrix bytes with
1/4/8 threads; a mismatched native float/token identity is rejected. Native core
values are unchanged. End-stub/anchored-sheet assembly, full combined G,
material/PVT and final producer-map reconciliation remain open; this component
does not promote physical or runtime eligibility.

`startup_timing_R_extension_conductance_002` assembles all currently known
nominal R extensions with eight compiled workers: 62,344 anchored sheets and
274,510 finite end stubs across all 525,638 selected R tiles. Exact rational
triangle stiffness is combined by private/global voltage identity before
rounding. Each added sheet is connected to exactly one native anchor, and each
finite end is a single-anchor leaf, preserving the original native DC graph.
The 463,014 native-axis tiles receive no redundant longitudinal sheet G.
The 560 native zero-voltage constraints are counted without being stamped twice.

The resulting 1,653,173 upper entries pass the full numerical structure audit:
maximum scaled constant-voltage residual 5.8608486923279888e-20, no negative
diagonal or significant negative 2x2 minor. Independent exact Python square-sheet
and end-stub controls give identical bytes at 1/4/8 threads; a second native
anchor is rejected because it would alter the native DC graph. `_001` retains
a failed schema assumption (nominal R-sheet values are decimal strings); its
source/controller are archived. `_002` handles that exact schema without
changing resistance values or rerunning extraction.

All 560 unresolved semiconductor end stubs remain in per-part symbolic ledgers
with exact resistance-square factors, private/global endpoints, native group,
tile and required `ndiode` material law. They receive no guessed conductance.
Known nominal native core, floating-sheet and extension G components are now
available, but complete numeric G, semiconductor ends, material/PVT and final
producer reconciliation remain unqualified. Runtime/physical/release gates
remain false.

`startup_timing_known_conductance_001` combines all known nominal G components
and applies the exact native zero-R voltage transform. Only overlapping native
core/extension entries are merged: 3,577,405 upper entries form the R prefix,
and the 15,000,747 already ordered floating entries are copied as a disjoint
suffix without a global sort. The zero-R-constrained known matrix contains
18,577,590 upper entries over 9,147,054 voltage states. Every row and nonzero
2x2 principal minor passes the numerical audit; maximum scaled constant-voltage
residual is 7.2335680195141337e-20.

The 560 unresolved `ndiode` ends are compiled separately as exact geometric
Laplacians. Their dimensionless coefficients multiply
`1000 / material_sheet_milliohms_per_square` to obtain siemens after a qualified
material law is selected. No numeric material value is assigned. The unit matrix
has 1,680 original upper entries and 1,400 after exact native zero-R constraints.
Exact rational fixture controls verify the factors, and a preassigned numeric
law is rejected from this unresolved path. These parameterized terms must not
be omitted when constructing an eventual numeric circuit.

`startup_timing_G_parameter_coverage_audit_001` independently scans raw sparse
diagonal records with compiled array operations. Exactly 561 known-G diagonals
are absent: the preserved abstract reference and the 560 explicitly listed
unresolved semiconductor end states. The symbolic families cover every missing
nonreference voltage. This rules out additional hidden unpopulated G states;
it establishes neither numeric material values nor full physical/PVT/runtime
qualification. Final producer-map reconciliation also remains pending.

The initial MOS batch's worst absolute AC difference belongs to profile 0,
which is shared by ordinary devices and the post-R X14 alternative (1,159
pre/post instance observations). It is not the large-source-area pre-R X14
profile 1. Accordingly, the 0.305895 uA difference at 400 MHz cannot be
attributed solely to the unresolved X14 fallback geometry.
`review_MOS_backend_profiles.py` independently recomputes sealed response
aggregates and partitions them by exact model/parameter profile, retaining
pre/post usage counts and each profile's worst terminal/bias response. Work
`startup_timing_MOS_profile_review_001` is admitted through the shared CPU/RAM
lease; no additional simulations or physical parameter selections are made.
The finite-grid diagnostic screen remains distinct from an acceptance budget.

MOS gate-sidewall default diagnostic: the local candidate Xyce source
`N_DEV_MOSFET_B4p61.C` assigns omitted PBSWGD from DsidewallJctPotential
(PBSWD), whereas ngspice47 `bsim4v5/b4v5set.c` assigns it from
SGatesidewallJctPotential (PBSWGS). The stock TT nfet_lvt model explicitly
sets PBSWS=0.1 and PBSWGS=0.79644 while omitting PBSWGD. This is a concrete
backend-default hypothesis, not proof that the local candidate source is
the exact source of the image binary or that it explains all differences.
`probe_MOS_gate_sidewall_default.py` /
`startup_timing_MOS_gate_default_probe_001` compares original and private
explicit-inheritance copies for the first-used profile of each of five
MOS families at TT -40 C, under the same independent DC/AC bias grid.
Only model/wrapper identifiers and explicit PBSWGD additions may change;
reversible edit ledgers are retained. Both ngspice and Xyce execute both
alternatives, so the reference response's sensitivity to the intervention
is measured directly. No foundry files or live full-grid inputs change.
The diagnostic is queued under the shared resource budget and does not
qualify any release model.

For the completed TT -40 C nfet_lvt profiles with W=0.74 um, L=0.15 um,
VDS=VGS=0 and reverse body bias 0.2 V, the observed drain-excitation/drain
current difference is about 1.305885122e-7 A at 400 MHz across differing
source/drain areas. The foundry parameters CJSWGS=1.795291232e-10 F/m,
MJSWGS=0.8, PBSWGS=0.79644 V, PBSWS=0.1 V and DWC=26 nm predict
`2*pi*400e6 * (0.74e-6-2*26e-9) * CJSWGS *
((1+0.2/PBSWGS)^(-0.8)-(1+0.2/PBSWS)^(-0.8))`
=1.3058851228683988e-7 A. This exploratory analytic match supports the
PBSWGD inheritance hypothesis; it does not replace the queued simulator
intervention, account for every mismatch, or establish a physical error bound.

Gate-default diagnostic attempt 001 stopped before any simulator call because
its added continuation lines violated the line-preserving edit-ledger helper's
contract. The failed source and output are retained. Derivative
`probe_MOS_gate_sidewall_default_v2.py` /
`startup_timing_MOS_gate_default_probe_002` instead appends PBSWGD on the
existing PBSWGS continuation line, preserving line count and the same exact
reversible edit checks. This changes model-copy preparation, not the intended
physical intervention or the live full-grid inputs. Attempt 002 is the active
diagnostic, still subject to CPU/RAM admission and native-response verification.

`startup_timing_MOS_profile_review_001` completed and exactly reproduced
all 2,688 DC and 6,912 complex AC terminal comparisons, including the
producer's aggregate maxima and numeric-screen counts. The retained TT27
batch has AC differences in all five used MOS families. Profile 0's maximum
0.305895 uA difference is on a profile used by 580 actual post-R devices,
not merely the isolated pre-R X14 alternative. Other ordinary nfet, pfet,
pfet_hvt, nfet_lvt and special_nfet profiles also retain nonzero gaps.
The per-profile receipt preserves exact parameters, pre/post usage counts,
terminal bias/excitation and complex reference/native currents; no physical
parameter or release-model qualification follows from this diagnostic review.

Gate-default attempt 002 passed reversible model editing but ngspice rejected
the diagnostic's guessed special_nfet source because its mismatch parameters
were undefined. The stock native model closure actually defines
`sky130_fd_pr__special_nfet_01v8` as an auxiliary wrapper in the ordinary
`sky130_fd_pr__nfet_01v8__tt.pm3.spice` file. Attempt 003
(`probe_MOS_gate_sidewall_default_v3.py`) now reuses the renamed auxiliary
wrapper from that exact ordinary-NFET copy and rejects source files outside
the audited library closure. It also pins the runtime image. Attempt 002 and
its pre-run manifests, edit ledgers and ngspice failure remain retained.
The original full-grid worker already uses the full native library rather
than guessed individual files and is unaffected by this diagnostic error.

Gate-default attempt 003 completed both simulators for all five first-used
MOS profiles at TT -40 C: 1,680 DC and 4,320 AC terminal comparisons across
original/private explicit-PBSWGD alternatives. All five ngspice AC responses
are exactly unchanged in the retained printed complex output. Explicit
reference inheritance reduces the maximum cross-backend AC gaps for nfet_lvt
69.8497 nA -> 0.666205 nA, pfet 108.445 nA -> 1.47457 nA and special_nfet
72.3413 nA -> 0.648604 nA. The long-channel nfet and pfet_hvt still retain
159.124 nA and 214.502 nA maxima respectively, so this single correction
does not establish backend compatibility. DC differences are unchanged;
the private pfet ngspice DC intervention changes printed currents by at most
1.38778e-17 A, while the other four are identical. Original library files
remain untouched. `review_MOS_gate_default_probe.py` locates each residual
in the sealed terminal-current data without another native simulation.

`startup_timing_MOS_gate_default_review_001` independently reproduces every
per-profile aggregate from attempt 003 and locates all five corrected-profile
AC maxima at 400 MHz, |VDS|=0.9 V, |VGS|=1.8 V, zero reverse body bias,
and bulk excitation. Long-channel nfet profile 0 retains a drain-current
gap of 159.124 nA (1.98233% of that response); pfet_hvt profile 2 retains
a bulk-current gap of 214.502 nA (1.42284%). These are selected-profile
finite-grid diagnostic observations, not universal MOS error percentages.
This localizes the next investigation to the remaining bulk-excitation
response after the demonstrably partial gate-sidewall-default correction.

All 15 `startup_timing_sequential_step_control_001` native points completed
with the compiled streaming assessor: 1,620 fixture comparisons, zero changed
outcomes, zero unmatched metrics. Halving max step from 2 ps to 1 ps changes
the largest matched metric by 4.6867961624e-5 ns (0.046868 ps). This is a
measured timestep perturbation, not a numerical enclosure or qualification
of setup/hold/recovery/removal or physical extracted timing.

`startup_timing_chunked_projection_controls_002` also completed: all 209
byte-range ownership tests and three invalid controls, exact node namespaces
and per-entry term counts for 97 actual operators in 17 tasks, with maximum
normalized coefficient difference 1.8217272424e-22. The whole process, including
the geometry loader, is limited to two OpenMP threads. This corrects the
resource-admission defect retained in controls 001. The original full
projection remains live and untouched; no duplicate full run has started.

`probe_MOS_body_response.py` / `startup_timing_MOS_body_response_001` compares
paired body-network selectors 1 and 0 in five private explicit-PBSWGD model
profiles at TT -40 C, retaining exact source/clone reversibility and all
independent DC/AC bias cases. It tests the remaining bulk-excitation gap's
dependence on the internal body network. Disabling that physical model is
a diagnostic intervention only; no disabled-body model is selected for release.

`startup_timing_MOS_body_response_001` completed paired native/reference
body-network controls after explicit PBSWGD inheritance: 1,680 DC and 4,320
complex AC terminal comparisons over five profiles at TT -40 C. All DC
responses pass the diagnostic numeric screen. Disabling the internal body
network does not remove the AC mismatch: long-channel nfet retains
159.113 nA versus 159.124 nA with body resistance, while pfet_hvt falls
from 214.502 nA to 17.4772 nA. The remaining three profiles retain about
0.648--1.473 nA. Body-enabled results reproduce the prior explicit-inheritance
probe maxima. Every corrected/disabled maximum remains at 400 MHz, |VDS|=.9 V,
|VGS|=1.8 V, zero reverse body bias and bulk excitation. This is evidence
against a body-network-only explanation, not a release-model workaround.
The private disabled-body models, raw data, exact reversible edits and
pre-run model/engine/image manifests are retained; native model compatibility,
intrinsic charge agreement and all-PVT physical qualification remain open.

`startup_timing_MOS_body_admittance_review_001` independently reproduces
all 4,320 AC comparisons and checks 1,080 four-terminal KCL sums per engine.
Ngspice has no diagnostic KCL exceedances (maximum 2.50434e-17 A); Xyce has
82 under the absolute 1e-15 A + relative 1e-8 L1 screen, with maximum
9.31089e-14 A. These small KCL residuals do not explain the observed
~1e-7 A long-channel cross-backend gap. With body resistance disabled,
the long-channel nfet's imaginary residual divided by omega is
-6.33090913509e-17 F at both 1 MHz and 400 MHz; every frequency-normalized
imaginary residual agrees to about 4.06e-30 F for that profile. This is an
observed admittance difference, not an accepted physical capacitance bound.

`startup_timing_CV_body_derivative_controls_001` independently differentiates
the shared CTM VdseffCV expression in its T0<0 branch using 90-digit Decimal
central differences. All 95 scalar controls pass: the local Xyce T4 form
(which is also used in ngspice BSIM4v6) has maximum absolute error
8.03e-48. Ngspice BSIM4v5 instead uses 1.0 in that derivative and retains
an extra dVdsatCV/dVb*T3 term; all nonzero-rate controls expose the difference.
This proves only the scalar derivative issue and does not yet bind the local
Xyce source to the image binary or explain the full observed current gap.

`build_CV_derivative_reference.py` /
`startup_timing_CV_derivative_reference_build_001` builds isolated unmodified
and single-CTM-derivative diagnostic ngspice binaries under a two-core lease.
It reuses exact historically pinned bison/flex package versions and hashes,
retains baseline/diagnostic source and build evidence, and leaves the stock
reference and all live full-grid inputs untouched. This is a reference
diagnostic, not a selected release simulator or a model-parameter adjustment.

`compare_CV_derivative_reference.py` /
`startup_timing_CV_derivative_reference_comparison_001` is waiting on the
exact isolated reference builder PID/birth and will stop without simulation
if that producer terminates without sealed binaries. Once available, it runs
the original and CTM-derivative reference binaries on the exact retained
TT -40 C five-profile/body1-body0 decks, relocating only wrdata destinations.
It compares the freshly built baseline against retained stock-reference
responses with an explicit 1e-20 A + relative 1e-12 diagnostic screen before
reporting per-profile baseline/corrected-reference versus sealed Xyce gaps.
All 1,680 DC and 4,320 complex AC observations must align; both DC and AC
are retained so an unintended static-model effect cannot be hidden.
The live full-PVT sweep, foundry files, stock reference binary and release
simulator remain unchanged. Baseline reproduction and residual explanation
are pending native results, not assumed from the scalar derivative controls.

`project_full_native_operators_v2.py` prepares the validated C++ byte-range
algorithm for a future complete projection: 64 disjoint byte ranges per
source, 1,024 dynamic tasks over the sixteen retained input files, shared
immutable field maps, 16 CPU slots, 32 GiB address-space bound and whole-process
OMP_THREAD_LIMIT=16 including geometry loading. It retains full input
pre/post hashing, exact expected operator counts, sparse-run manifests and
all existing physical-qualification exclusions. No future full run is started.

The controller requires an explicitly failed, terminal predecessor and refuses
a predecessor with a complete assessment. The actual live predecessor test
`startup_timing_byte_projection_admission_controls_001` confirms refusal
before creating output or launching a native worker. Its syntax is checked,
but full controller execution remains unvalidated. The currently running
full projection and its waiting consumers remain unchanged; partial shard
status is not treated as a reusable transactional checkpoint.

The byte-range control is extended to sixteen threads in
`check_chunked_stream_projection_v4.py` /
`startup_timing_chunked_projection_16thread_controls_002`, using the same
97 actual operators, 17 byte tasks, independent sparse oracle, term counts
and node-map checks. The new `check_omp_thread_limit_v3.cpp` probes both
eight-thread loader-like and 32-thread projector-like requests under an
explicit sixteen-thread process limit. Compilation uses one CPU slot;
native projection requires a separate complete sixteen-core lease.
This work is queued and does not promote sixteen-thread validation yet.
The queued attempt 001 retains an identified const JSON-array API error in
its newly introduced resource probe; its source and outcome are preserved.
The corrected derivative uses Json::push, without changing the established
projector, frozen two-thread control, live full projection or model sweep.

`startup_timing_CV_derivative_branch_join_controls_002` independently checks
the symmetric smooth expression
`(s+v+delta-sqrt((s-v-delta)^2+4*delta*s))/2` for effective drain voltage.
All 56 100-digit finite-difference/closed-form controls pass for both
partial derivatives, including both source branches; maximum native-form
error is 8.267e-59. Five positive-drain-voltage branch joins prove the native
T4 derivative continuous, while the old reference branch formula has a
jump sqrt(delta/s). This is a scalar mathematical result; it does not bind
actual device operating states or establish how much of each native current
gap is explained. Attempt 002 explicitly respects both implementations'
zero-drain-voltage derivative override and restricts jump claims to positive
drain voltage; the initial raw-formula attempt 001 is retained. Native
full-PVT and reference-build comparisons remain required.

`startup_timing_floating_charge_gauge_controls_001` establishes a conditional
solver contract, not a physical initialization choice. For fixed linear C,
exact incidence G with GZ=0, and nonlinear equations/observations unchanged
by a constant unattached-conductor shift Za, the trajectories V and V+Za
have identical attached voltages and internal conductor gradients. Total
floating charges differ by H a, H=Z^T C Z. An SPD H allows any static
charge representative within this model without grounding floating dynamics.

Three exact-rational coupled C/G/nonlinear-KCL controls demonstrate charge
representative changes with zero equation residual and conserved total
charges. Six negative controls reject rounded G diagonals, grounding,
floating nonlinear devices, voltage-dependent C without a separate proof,
time-dependent shifts and changed internal gradients. Fixture charge values
are algebraic test data, never assigned physical initial charges.

The receipt binds the actual graph/role/operator audits: 1,875,023 unattached
floating components over 7,500,317 states have no native device/port terminal
attachment, and the incidence evaluator annihilates conductor constants.
Grounded original-conductor C is independently SPD, but full spatial
projection/collapse and node-map reconciliation remain pending. Therefore
this contract is not implemented or qualified in the release solver; physical
linearity/validity of C, initial internal gradients, device-model integration
and full physical/PVT qualification remain open.

`prepare_MOS_library_view.py` / `startup_timing_private_MOS_library_view_001`
prepares a private MOS-only include view. It conservatively omits 69 unused
pure-definition leaf files, reducing the complete multi-corner dependency
closure from 319 files to 250. Files with global parameters, global options,
other outside-wrapper behavior or child includes are retained. The five
actual MOS wrapper families are required; retained parameter/model text is
unchanged. Only include directives are rewritten or commented, with exact
line-preserving edit reconstruction. Original foundry files remain untouched.
This is not a whole-PLL library: non-MOS definitions may be omitted.

`check_private_MOS_library_view.py` /
`startup_timing_private_MOS_library_native_controls_001` runs eight paired
native analyses: fresh original/private libraries, each simulator, DC/AC.
Both use the exact first sixteen TT27 MOS profiles and physical fixture
tokens, with all five actual families. Fresh original results are compared
to retained originals, and private results to fresh originals. The only
permitted deck changes are library selection and output paths. Timings are
paired observations under a one-core lease, not an isolated throughput
benchmark. No speedup, all-PVT equivalence, release eligibility or model
compatibility is assumed before assessment.

Private MOS library native controls completed successfully: all 19,200
terminal response comparisons (DC/AC across both simulators) are exactly
identical between fresh original and private views, with fresh originals
also exactly matching retained original responses. Nonisolated baseline/private
wall ratios are ngspice DC 1.065, Xyce DC 1.450, ngspice AC 1.112 and
Xyce AC 1.022. These are single paired TT27/first-sixteen-profile observations,
not a repeated throughput benchmark or proof for all PVT/profile cases.
The private view remains unselected for release and the live full sweep
continues to use its frozen full-library inputs.

The full MOS finite grid completed all 450 batches, 7,140 profile/PVT
observations and 4,284,000 terminal comparisons. Independent compiled audit
`startup_timing_full_MOS_compiled_response_audit_001` verifies every named
terminal header, DC/AC coordinate, bounded batch and native completion marker,
and reproduces every producer aggregate under the controlled numeric screen
using eight workers. No native simulations are repeated. Controls 002
include full/short batches and five malformed-response rejections; failed
controls 001 retain the missing-iostream compile error and original source.
The full audit's largest raw DC delta is 6.97845e-12 A at FS125/profile450;
largest raw AC delta is 3.51875e-7 A at SF27/profile0/400MHz. These are finite
response observations, not device-error enclosures or PLL frequency errors.

The sixteen-thread byte projection controls completed successfully, with
identical node maps and term counts and normalized coefficient difference
1.8217272424e-22 on 97 actual operators/17 tasks. The thread probe observed
eight threads for a request of eight and sixteen for a request of 32 under
OMP_THREAD_LIMIT=16. This does not claim a completed full byte-range projection.

The isolated baseline and CTM-derivative reference builds and paired native
comparison completed. Fresh unmodified reference results reproduce retained
results with zero screen exceedances. After explicit PBSWGD inheritance,
correcting the reference CTM derivative reduces the long-channel nfet AC gap
from 159.124 nA to 9.339e-14 A; nfet_lvt, pfet and special_nfet gaps also
fall to about 1.26e-13--3.71e-13 A at this point. The pfet_hvt body-enabled
gap remains 207.894 nA, at VDS=0, |VGS|=.9 V and bulk excitation; the
body-disabled counterpart falls to 5.369e-14 A. Thus the scalar derivative
issue explains much of the selected-point discrepancy, while an additional
body-network-dependent residual remains. No disabled-body or diagnostic
reference model is adopted for release. All-PVT corrected-model compatibility
and full physical/PLL signoff remain open.

The user explicitly extended the full projection limit to 24 hours after
attempt 001 terminated at 12 hours with 778,684,000 observed operators.
The old output is preserved as a failed partial attempt, not a transactional
checkpoint. Fresh attempt `startup_timing_full_spatial_projection_002` uses
`project_full_native_operators_v3.py`, a scoped 86,400-second wall limit,
the native byte-range projector validated at sixteen threads, 1,024
disjoint tasks, a sixteen-core lease and 32 GiB address-space bound.
It hashes inputs before native execution and must still prove all
830,933,570 operators before any reduction or qualification.

The new attempt started 2026-10-29 14:19:54 UTC, with projection deadline
2026-10-30 14:19:54 UTC. All six downstream consumers were registered
against the exact new PID/birth chain under fresh `_002` outputs. Their
waiting windows cover the longer projection and upstream checks; their
actual computation limits remain unchanged. Original failed consumers and
all their evidence remain retained. The general CAD and native DCO budgets
are unchanged; the user's override is scoped in
`projection_budget_override_24h.json`.

Investigation after successful full projection/reduction: the failed equivalence
and zero-R registration guards compared the conductor map's original producer
path (`...projection_001`) to the completed producer (`...projection_002`).
`startup_timing_final_projection_namespace_reconciliation_001` rehashes both
complete old/new node maps and the independently audited map receipts. The R
node files are byte-identical (SHA721de99d...), as are the floating node files
(SHA300e3191...). The 9,147,614-state namespace is therefore unchanged.

`bind_projection_namespace.py` permits reuse only through this exact sealed
producer/map reconciliation, checking all original/final map bytes and receipt
hashes. Versioned consumers `verify_spatial_conductor_equivalence_v2.py` and
`finish_spatial_zero_R_v3.py` retain the original controls and independent
physical reference, add the reconciliation to their pinned inputs, and run
under fresh outputs `startup_timing_spatial_equivalence_reconciled_001` and
`startup_timing_spatial_zero_R_followup_003`. They do not edit prior failures
or weaken a genuinely different namespace check. Fresh symbolic-end and
floating-charge consumers follow the exact zero-R PID/birth.

The separate unconstrained charge-conservation failure remains preserved.
`diagnose_full_spatial_charge_residual.py` scans every original sparse row,
reporting signed residuals, reduced row L1, and original absolute contribution
sums without modifying coefficients or qualification limits. A controlled
fixture distinguishes cancellation-sized errors from a larger error. The
source-normalized roundoff screen is explicitly heuristic, not a rigorous
arithmetic enclosure or passivity/physical-qualification proof.

Full row diagnosis completed for all 483,154,675 upper entries over 9,147,614
voltage states. Exactly 336 rows exceed the original reduced-row-relative
charge limit. The worst-ratio row 1,196,557 (`_rmesh_18208_1211140`) has
residual -1.70448837023e-19 native units and reduced L1 1.82340385509e-19,
but original absolute contribution sum 9.88631399389 native units. Its
0.934783792 ratio therefore reflects near-total coefficient cancellation;
the absolute residual is 1.70449e-37 F. Across the complete matrix, maximum
absolute residual is 2.09784519423e-12 native units (2.09785e-30 F), and
maximum residual/source-absolute-contribution ratio is 4.02293e-18. No row
exceeds the heuristic 256-long-double-epsilon source-contribution screen.
This is diagnostic evidence consistent with cancellation/roundoff, not a
rigorous arithmetic enclosure; the original charge gate remains failed,
coefficients are not clamped or altered, and passivity remains unproved.

The provenance-reconciled full conductor comparison ran and exposed two
remaining original-tolerance misses, both involving explicit reference 0:
one diagonal and one reference edge. All 42,188,289 conductor-coupling union
entries are within tolerance. The largest raw difference is 1.94288e-5
native units at (0,0). The complete failed report and collapsed matrix are
retained in `startup_timing_spatial_equivalence_reconciled_001`. No tolerance
is loosened and no physical-equivalence success is claimed. Zero-R transform
and its new dependent consumers remain active pending constrained results.

Targeted repair implementation has begun with an exact dyadic C-row audit
(`audit_C_dyadic_residual.cpp`, `certify_spatial_C_dyadic_residual.py`).
Unlike the G-only predecessor it accepts signed off-diagonal coefficients,
uses exact integer accumulation at the stored binary quantum, and emits
per-row residual/L1 integers for the complete zero-R-constrained matrix.
Work `startup_timing_exact_C_residual_certificate_001` preserves all source
bytes, hashes the matrix before/after, and runs under a one-core/eight-GiB
lease. Its result is pending independent fixture controls and completion;
it certifies stored arithmetic only, not upstream integration error or
physical passivity. Conservative assembly, MPFR reference correction and
targeted replacement remain unimplemented and all physical gates stay open.

## Tapeout implementation, requirements version 2

`requirements_v2.json` preserves the 400 MHz/1.8 V/fifteen-PVT scope and adds
the selected aggregate 1 FIT command/reset synchronizer requirement and
constrained redesign fallback. `common_v2.py`, `audit_v2.py`, and the versioned
preparation, native, loop, gain-search, acceptance, and packaging tools bind
new evidence to this profile. Original profiles, tools, and receipts are retained.
CDC receipts require a pinned, candidate-matching complete structural inventory;
their expected crossings cannot omit inventory entries. BBPD decision noise is
classified separately. Every included crossing needs pinned characterization,
declared event-rate bounds and resolution-time justification. The summed failure
rate bound must not exceed 1 FIT at each PVT point. Numerical native holdouts
now support independently tightened relative and absolute tolerances.

`make signoff400-v2-prepare`, `signoff400-v2-audit`, `signoff400-v2-package`,
and `signoff400-v2-test` select the new flow. Preparation and audit run in the
CAD image so its pinned Nix executables can be verified. The fresh campaign is
`build/signoff400/campaign_tapeout_v2_001`; imported geometry does not close any
release gate. `release_v2_controls_001` records 42 passing control tests covering
profile/model binding, timing-trace acceptance, numerical settings, CDC inventory
and aggregate bounds, incomplete evidence, and packaging tamper detection.

`conservative_C_controls_001` independently checks the original exact C auditor,
new diagonal certificate, and signed-edge evaluator against rational arithmetic,
including an indefinite signed example, malformed files, and thread counts 1/4/8.
`startup_timing_conservative_C_001` then certifies all 9,147,054 full-matrix rows:
all implicit-diagonal corrections meet the unchanged coefficient tolerance.
It preserves all original offdiagonals and matrix bytes, explicitly retaining the
original 336 gauge-screen failures. Full-vector results match an independent
streamed edge scatter at every row and are identical across 1/4/8 threads.
Observed apply times were 28.13/8.65/4.65 seconds; these are nonisolated timings.
The logical operator is described in that output's `operator.json`. Conservation
does not prove full passivity, upstream integration accuracy, or solver eligibility.

`fringe_interval.hpp` uses exact rational polynomial coefficients and directed
MPFR arithmetic for analytic cubic fringe moments. The original binary64
`.6366` constant is preserved. `fringe_interval_controls_001` checks independent
rational-series bounds at 128/256/512/1024 bits; `registered_mpfr_controls_001`
checks every spatial matrix coefficient against independent triangle-series
integrals for all four directions and constant/distributed source bases.
Matching MPFR 4.2.1 development headers are locally extracted in
`mpfr_headers_001`; the system installation is unchanged.

`reference_interval_trace_controls_002` verifies complete byte ownership, exact
source offsets, aliases, scalar intervals, and rejection of gaps, overlaps,
missing tasks, incorrect totals, and changed task maps. The prior `_001` fixture
failure is retained: its independent expectation omitted a reference-to-conductor-2
diagonal contribution; `_002` corrects that expectation. The full followup is
`startup_timing_reference_intervals_003`, with a PID/birth owner and resource
lease. It scans all 830,933,570 operators, independently bounds entries (0,0)
and (0,1), and retains selected source records with their original byte offsets.
Its two earlier preflight failures are retained; the current controller validates
field count and the shared compiler receipt's exact field-table lineage.
This work diagnoses the failed reference comparison and does not promote a
physical, passivity, or release gate.

Further exact replay in `startup_timing_conservative_C_row_replay_001` finds
128 negative conservative diagonals. These are exact negative-energy witnesses
for this stored-coefficient derivative, with minimum diagonal about
-4.016e-18 native capacitance units. Conservation and small correction bounds
therefore do not make this operator passive. No coefficient is clipped and no
runtime eligibility is granted. `startup_timing_negative_C_fields_002` resolves
all 128 states through the exact zero-R map and producer namespace to native
group 18208. Its twelve candidate physical fields are a conservative support
overapproximation; native group IDs are not global field IDs. The next projection
repair must resolve the affected P1 triangle supports and original operator/task
coverage before recomputing contributions. The first resolver failure is retained;
the corrected resolver accepts all audited native, axis-end and sheet node names
and joins the pinned R bundle/index tables.

The new `startup_timing_body_zero_VDS_001` diagnostic covers nine signed drain
biases around zero at 1 kHz and 400 MHz. The remaining high-Vt PFET discrepancy
persists across that neighborhood. Retained operating-parameter output shows
source-junction capacitance changes between body1/body0 while internal DC body
voltages differ only near machine precision. `startup_timing_junction_zero_bias_continuity_002`
checks the actual model bin 92: PS=0, PERMOD=1, and effective width .87 um produce
negative sidewall perimeter -.87 um and signed sidewall capacitance
-8.271841767e-17 F. Both retained simulator sources include that component at
exactly zero bias but omit it in the reverse-bias branch. Its predicted jump
matches all nine observed low-frequency source/bulk capacitance gaps within
the declared diagnostic screen (maximum prediction error 9.173e-26 F).
This identifies a junction-geometry/branch-continuity problem to resolve before
claiming a body-network stamping defect. No simulator or foundry model is edited,
and neither a disabled-body model nor guessed junction geometry is adopted.

The completed full reference trace in `startup_timing_reference_intervals_003`
covers all 830,933,570 operators. Its exact source-derived intervals at (0,0)
and (0,1) match the retained projection within unchanged tolerances; their
maximum raw differences are about 1.835e-12 and 3.979e-15, respectively.
`interval_reference_comparator_controls_001` tests whole-interval comparisons,
interval widths, unchanged entries, retained reference 0, and exact tolerance
boundaries. A fresh complete collapse/comparison in
`startup_timing_spatial_equivalence_intervals_001` passes all 45,967,654 union
entries: 42,188,289 conductor couplings, 1,893,231 diagonals and 1,886,134
explicit-reference edges. It uses the original scalar reference at other entries
and the independently certified intervals at the two repaired entries. Original
failed comparisons and scalar matrices remain unchanged. This is ideal-conductor
projection equivalence, not material, full passivity, or transient qualification.

`startup_timing_negative_C_support_001` scans every one of the 525,638 R tiles
and resolves the 128 negative states to 293 P1 triangles in 102 tiles, all in
physical field 1903113 (`VGND`, active `psubdiff`). The controlled inclusive-box
selector scans the complete original operator stream, retaining exact source
bytes/offsets for 2,114 operators in 66 original tasks in
`startup_timing_negative_C_operators_001`. Field IDs are joined through the
original R bundles/index; native group 18208 is not used as a field ID.

`selected_C_diagonal_controls_002` verifies native geometry integration, exact
area/line results, independently bounded fringe results, zero-measure terms and
zero-R alias double counting. It also reproduces the earlier spatial MPFR
outputs byte-for-byte at all four precisions. The `_001` fixture failure is
retained; its shape-alias filename collided with a case configuration filename.
`startup_timing_analytic_negative_C_diagonals_001` then bounds all 128 diagonals
at 128 bits: every interval contains zero, excludes the stored negative value,
and is narrower than one eighth of that stored defect.

`symbolic_fringe.hpp` represents the same analytic fringe moments as exact GMP
rational constants and canonical `atan(q)`/`log1p(q)` atoms. Its controls in
`symbolic_C_zero_row_controls_001` check full signed A/L/F cancellation, split
interval telescoping, gauge conservation, zero-R aliasing, and rejection of a
one-ULP noncancellation. `startup_timing_symbolic_C_zero_rows_001` proves that
all 1,224 assembled coefficients in the 128 complete target rows cancel exactly.
No numerical threshold is used. This justifies source-level zero C rows while
retaining every voltage state and the entire G network.

`zero_row_C_operator_controls_001` checks exact coefficient corrections and
signed-edge evaluation, large-change rejection and mask/reference guards at
1/4/8 threads. The fresh derivative in
`startup_timing_conservative_C_source_zero_rows_001` uses only the source-proven
zero rows, keeps the original sparse matrix immutable, and must certify every
changed offdiagonal and implicit diagonal against the unchanged coefficient
tolerances before emitting `operator.json`. Full PSD and native-solver eligibility
remain separate, unqualified gates; an absence of negative diagonals is not a PSD
certificate.

The completed first derivative exposed one further negative implicit diagonal,
row 1242335. `startup_timing_source_zero_C_followup_001` independently scans
the full source stream for that state's complete support and proves its entire
row exactly zero. `startup_timing_combined_source_zero_C_rows_001` binds the
union of 129 rows to the same projection and zero-R voltage namespace.
The fresh derivative `startup_timing_conservative_C_source_zero_rows_002`
certifies all 846 removed nonzero offdiagonals and every implicit diagonal
against the unchanged tolerance, with zero remaining negative diagonals.
Its full-vector checks are separate from full passivity.

`logical_C_weighted_DD_controls_001` checks a new exact GMP passivity verifier
on a signed operator requiring nonuniform positive scaling, an indefinite
operator, isolated zero rows, and malformed diagonal/vector/reference inputs.
`startup_timing_full_logical_C_weighted_DD_001` waits for the second derivative,
then searches a positive scaling and independently verifies every implicit
diagonal identity and grounded weighted margin exactly. Explicit reference 0
and finite-R VGND remain distinct. A failed sufficient certificate does not
prove indefiniteness. Physical materials, device semantics, native integration
and all release gates remain unqualified.

The second derivative's complete vector evaluation matches independent streamed
edge scatter in every row and is bit-identical at 1/4/8 threads. Final receipt
publication also requires unchanged-input hash verification.
`logical_C_principal_pair_controls_001` independently checks exact two-state
negative-energy witnesses with Python Fraction arithmetic, including a coupled
zero diagonal. A globally indefinite matrix whose every two-state minor passes
checks that this necessary screen never becomes a PSD claim.
`startup_timing_full_logical_C_principal_pairs_001` applies this exact screen to
the same second derivative; it retains up to 32 constructive witnesses if any
pair fails, and independently checks every implicit diagonal identity.

The completed full pair check finds 26 negative principal minors in the 129-row
derivative. Every retained two-coordinate witness has exactly negative energy;
this operator is indefinite despite its nonnegative diagonals. Twenty endpoints
have zero or very small diagonal coefficients.
`startup_timing_source_zero_C_pair_followup_001` selects those endpoints for
complete source-support selection and exact symbolic full-row proof. Its raw
`1e-8` selection threshold never authorizes changing a coefficient: only an
exact zero-row proof can do that. `startup_timing_combined_source_zero_C_rows_002`
and `startup_timing_conservative_C_source_zero_rows_003` wait for that proof and
stop without promotion if it is incomplete. The prior indefinite derivatives
and constructive witnesses remain retained.

All 20 pair-selected rows now have exact source-zero proofs; the combined proof
contains 149 rows. The complete original row-norm scan independently selects
215 remaining small nonzero rows from the 129-row derivative, excluding already
masked rows and 3,337 original exactly-zero-norm rows. The inventory controls
check the exact selection boundary and prevent proof/PSD promotion.
`startup_timing_source_zero_C_inventory_followup_001` batches source proofs for
those 215 candidates. A further composition and coefficient/vector certificate
are queued in `startup_timing_combined_source_zero_C_rows_003` and
`startup_timing_conservative_C_source_zero_rows_004`; they require every candidate
to pass exact complete-row cancellation. The next passivity driver releases its
16-CPU search lease before obtaining a 1-CPU exact-verification lease.

`startup_timing_implicit_MOS_terminal_geometry_003` traces all 2,144 implicit
source terminals. Each has zero source edge, source/drain/bulk on the same
original conductor, and nonzero drain edge equal to twice the channel width.
All match channel/edge geometry in six retained decap cell prototypes; this is
geometry equivalence, not hierarchical instance ownership. The flattened drain
area/perimeter differs from the isolated-cell attributes in 186 cases, which
remain explicit rather than being equated. Every combined non-gate perimeter is
nonnegative. No geometry, foundry model or simulator is changed or qualified.

`startup_timing_mapped_CDC_inventory_001` traces all 489 mapped sequential data
and asynchronous-control cones. It retains 421 data-crossing candidates, 18
control groups and 13 directly connected marked two-stage chains. Unmarked
sources are included; clock relationships and stable-input exceptions are not
assumed. Synthetic controls reject missing/multiple drivers, combinational
cycles, unknown logic and unreviewed sequential masters. The routed inventory
uses the pinned Yosys and retained blackbox interfaces; passive physical cells
are loads only. Neither inventory qualifies clock intent, post-layout timing,
metastability, final GDS binding or the aggregate 1-FIT target.

The routed inventory completed with all 489 sequential cells and 103 raw clock
leaves. `startup_timing_routed_CDC_comparison_001` follows explicit buffer and
inverter chains to primary or sequential clock roots, retaining inversion
parity, and scopes generated-identifier unescaping to Yosys FF names. Every
sequential identity, source cone and clock root matches the mapped inventory;
both have 421 normalized data-crossing candidates. Controls check buffer/even
inverter equivalence, odd inversion retention, unknown clock gates/cycles and
identifier scope. This is not logic-function equivalence or physical clock/CDC
qualification; no crossing is waived by the comparison.

The batched source proof completed: every one of the 215 selected rows is
exactly zero. The composed proof in `startup_timing_combined_source_zero_C_rows_003`
contains 344 rows, and its coefficient/vector certificate is running. Full
pair and weighted-DD checks are queued against that derivative, independently
of the retained checks on the earlier 149-row derivative.

`C_factor_pattern_controls_002` compares every CHOLMOD symbolic factor column
count with independent graph elimination for path, cycle, complete and masked
patterns, including the returned permutations. The `_001` unsorted-fixture
failure is retained. `startup_timing_full_C_factor_pattern_001` benchmarks AMD
symbolic fill on the completed full 129-row C pattern under a 4-CPU/32-GiB lease
and 12-hour computation limit. It includes every voltage state, explicit
reference 0 and all retained nonzero C edges. It reports exact factor column
counts/storage estimates for this simplicial ordering only. No numeric
factorization, G/nonlinear-device assembly, KLU fill bound, passivity or native
solver qualification is implied.

The full 344-row coefficient audit passes: all 2,202 removed nonzero
offdiagonals and every implicit diagonal meet the unchanged tolerance, with
zero negative diagonals. Independent full-vector and passivity checks remain
separate and pending.

`startup_timing_CDC_obligations_001` binds all 13 marked two-stage chains to
their actual routed cells/masters. Eleven command/reset chains belong to the
aggregate <=1 FIT scope; two BBPD chains remain a separate noise obligation.
The two logical 34-bit bundles retain 2 and 29 destination registers after
synthesis, explicitly enumerated rather than presumed to contain 68 physical
flops. All 421 crossing candidates remain unwaived, with separate tags for
static programming, enable withdrawal/release, bundle capture and other clock
relationships. Event rates remain undeclared, no multicycle exception is
authorized, and characterization/resolution/bundle/initial-setup obligations
remain open. Controls reject missing chains, unreviewed marked storage,
changed routed flop polarity and changed profile scope.

`startup_timing_full_C_factor_pattern_001` completed symbolic AMD analysis:
27,338,076,683 factor entries require 437,409,226,928 bytes (about 407.37 GiB)
for simplicial indices/values alone. Analysis used about 15.1 GiB of CHOLMOD
peak allocations and 362 seconds, without numeric factorization. This measured
ordering exceeds the 48-GiB native-process budget; it is not a lower bound on
all orderings or KLU. Component/block preconditioning and full-equation GMRES
remain the intended bounded-memory direction. The 149-row derivative passes
every exact principal-pair screen; its positive-scaling search reached its
growth cap, and full passivity remains unproved.

`startup_timing_CDC_physical_binding_001` reads the frozen routed database with
the pinned OpenROAD and binds all 26 synchronizer FF instances, masters,
locations, clock/data/control nets and first-stage fanout. Only one pair is a
direct Q-to-D net. `startup_timing_CDC_interstage_paths_001` traces the remaining
12 pairs through two `clkbuf_2` hold buffers each, preserving signal order and
inversion parity. Controls reject odd inversion, unrelated source state,
unreviewed gates and cycles. Intermediate buffer physical pin/net binding and
complete-path resolution/metastability characterization remain open. Instance
origin distance is neither routed wire length nor a timing bound.

The 344-row derivative completed coefficient, independent full-vector and
unchanged-input checks, and its full exact principal-pair screen has no negative
minor. Full passivity remains unproved.

`component_CG_pattern_controls_001` independently checks symbolic counts,
C/G duplicate coalescing, retention of G edges on source-zero C states and
cross-component-G/memory rejection. `startup_timing_component_CG_factor_pattern_001`
binds the completed C namespace to the certified G components and original/final
projection reconciliation. Its conductor-block preconditioner pattern includes
all G-family edges, with unknown-law ndiode geometry used only as a pattern.
All 9,147,054 states are retained. AMD gives 36,952,592 factor entries and
591,241,472 bytes (about 0.55 GiB) of simplicial index/value storage. The largest
component has 277,343 states. Cross-component C remains mandatory in the full
equations; floating charge constraints and physical material laws remain open.
This is a structural benchmark, not numeric factorization or a KLU memory bound.

`C_vector_energy_controls_001` verifies full signed-edge vector energies and
absolute contributions independently with Fraction arithmetic, including signed,
zero and wide-exponent vectors and malformed inputs. `C_negative_energy_search_controls_001`
checks two-pass scaled Lanczos reconstruction on signed PSD and higher-order
indefinite examples. Floating Ritz estimates never become proof. The full job
`startup_timing_full_C_negative_energy_001` searches a 256-step candidate under
a 16-CPU/32-GiB lease, then releases it before a 1-CPU/12-GiB exact GMP energy
check. Only exactly negative full-operator energy proves indefiniteness; a
nonnegative candidate energy does not certify PSD.

### Prototype tapeout release v3

The current approved release contract is `requirements_v3.json`: 400 MHz,
25 MHz reference, 1.8 V, TT/FF/SS/SF/FS at 27 C, with five mandatory gates.
The 60-case correlated hierarchical campaign preserves the functional lock
limits. Calibration requires a measured bracket and demonstrated capture;
temperature and <=1 FIT qualification are later milestones. Historical v1/v2
qualification semantics and evidence remain unchanged. The custom spatial
capacitance operator is rejected for release use after a verified negative
energy witness; its research completion is not a v3 prerequisite.

`campaign_prototype_v3_002` separates physical/source identity from profile
identity and currently has no qualifying receipts. `acceptance_v3.py` passes
16 trace controls, and `loop_v3.py` passes seven model-binding/scope controls.
Loop traces alone cannot qualify the release or substitute for uncertainty
holdouts. The current implementation does not yet supply the final validated
analog models or a passing full campaign.

The conventional hierarchy work is in `prototype_v3_analog_reference_001` and
`prototype_v3_analog_capacitance_002`. All 1,782 detector and 8,620 DCO primitive
cards match after collision-checked standard-cell instance-label normalization.
Exact aggregation retains every signed capacitor. Positive-path certificates
in `prototype_v3_analog_capacitance_passivity_001` establish passivity of the
isolated capacitor networks, including their one/15 remaining negative pairs.
They do not validate parent loading, resistance or transistor behavior.

`prototype_v3_DCO_rcx_lineage_001` binds the original nominal/minimum/maximum
OpenRCX SPEF files to the exact DCO GDS selected by the assembly: RCX and
stream-out carry the same routed database, and final copies match. Pin binding,
capacitance scope/double-counting checks and parent/final-fill effects remain
open. The reference TT pilot `_002` is a bounded simulator compatibility check,
not release PEX evidence; its earlier memory failure is retained. The corrected
run uses PDK compatibility mode and has its native threads constrained to the
one-CPU lease. Future pilot launchers explicitly bound BLAS/OpenMP threads.

Subsequent conventional RC work resolves the routed pin binding for all three
interconnect corners (`prototype_v3_DCO_spef_binding_002`): 505 networks and
1,924 terminals per corner. `join_prototype_physical_instances.py` independently
derives the 5 nm extraction grid from six transistor length/width controls and
regenerates all 1,736 placement mappings, exactly matching the original join.
Its receipt is `prototype_v3_DCO_reproducible_instance_join_001`.

`build_prototype_DCO_rc.py` produces provisional nominal/minimum/maximum models
in `prototype_v3_DCO_hierarchical_RC_001`. It retains cell-local capacitances,
replaces macro-level Magic capacitances with routed SPEF wire RC, and emits each
mirrored coupling once. All 1,620 routed cell pins are rewired. Three regression
controls exercise capacitance scope, mirrored coupling consistency, zero-R
rejection and failed terminal binding. These models still require native
correlation and final assembly loading before qualification.

The completed unloaded TT reference pilot measured 911.039 MHz at coarse 1,
fine 128; this is not a loaded operating-point result or a 400 MHz bracket.
The isolated capacitance pilot is retained separately. The hierarchical RC
pilot launcher is `run_prototype_hierarchical_RC_pilot.py`; it verifies the RC
receipt and artifact hashes before execution. Full-assembly loading extraction
uses `extract_prototype_assembly_capacitance.py`. Neither launching a job nor
producing a netlist supplies a passing analog release receipt.

`inventory_prototype_interface_loading.py` removes the selected analog block
while retaining external transistor terminals and signed assembled capacitances.
It does not replace coupled nodes by ground or infer intrinsic transistor
capacitance from geometry. The preliminary LVS-only DCO receiver inventory in
`prototype_v3_DCO_reference_receiver_inventory_001` identifies eight MOS gate
terminals and one antenna diode on PLLOUT. Full-assembly extraction must supply
the external wiring/cell capacitances; the inventory alone is not a qualified
load model. The diode numeric area/perimeter use the pinned PDK scaled model
convention (physical geometry 0.6417 um^2 / 3.24 um), consistent with retained
`startup_corrected_alias_002/signoff/diode_geometry.json` and the earlier native
`hs_diode_geometry_comparison_001` results.

`export_prototype_digital_placements.py` and the geometry join regenerate all
12,334 digital placement identities against the filled assembly's LVS extraction
(`prototype_v3_digital_instance_join_001`). The join includes non-electrical
fill cells, which need not appear as SPICE instances.
`bind_prototype_CDC_to_assembly.py` then checks the 13 retained synchronizer
chains against extracted cell pins and conductor equivalences. All 50 cells
(26 flops and 24 interstage buffers) bind in
`prototype_v3_CDC_assembly_binding_001`. Distinct routed interstage nets must
remain distinct, and each routed net must remain continuous. This closes the
connectivity comparison for those chains, not their delay, recovery/removal,
metastability behavior or the complete CDC release gate.

`scripts/spice_dco_postlayout_prototype_v3.py` retains the previous worker as
history and adds explicit ngspice relative/absolute tolerances, high precision
printed waveform retention, and waveform-based measurement across the captured
window. The printed-table parser rejects missing interior indices, duplicated
indices and nonmonotonic time. The native observer check in
`prototype_v3_waveform_observer_002` recovered exactly 400 MHz and 50% duty from
3,008 samples of a known sine source. `_001` retains the Apptainer startup
failure under an insufficient 1 GiB virtual-address limit; `_002` uses 4 GiB
and bounded runtime threads. This is an observer check, not DCO qualification.
`run_prototype_hierarchical_RC_waveform_pilot.py` prepares the next diagnostic
RC pilot with the new waveform worker and explicit 1e-5 / 1e-15 tolerances.
It has not supplied a native-correlated model or convergence holdout receipt.

`inventory_prototype_clock_loading.py` traces the PLLOUT receiver cone in
the filled-assembly LVS extraction. `prototype_v3_clock_receiver_cone_001`
retains eight extracted buffers and 57 terminal frontiers. PLLOUT directly
drives a clkbuf_16 and antenna diode; the receiver output drives four further
clkbuf_16 input loads. The inventory retains frontier cell/pin identities and
inversion rather than assigning guessed lumped capacitances. It does not yet
measure boundary capacitances or qualify clock timing.

Full assembled hierarchical capacitance extraction completed in
`prototype_v3_assembly_capacitance_001` (55 MiB netlist, warnings retained).
`prototype_v3_DCO_assembled_interface_loading_001` identifies 484 signed
external PLLOUT capacitor pairs plus the nine external primitive loads. Their
positive/negative sums are 88.12352 / -0.01007 fF; these are network sums, not
a grounded equivalent capacitance. Intrinsic receiver capacitance is additional.
The raw analog-card comparison `_assembled_analog_device_comparison_001`
retains the differences caused by boundary exposure. The separate
`prototype_v3_assembled_analog_device_projection_001` verifies that SUB binds
to VGND in the actual assembly and removes only the macro root path prefix;
all 1,782 detector and 8,620 DCO cards then match exactly. These diagnostic
receipts do not qualify the final dynamic loading model.

The assembled capacitor audit `_assembly_capacitance_audit_001` expands
791,266 capacitors into 255,085 signed pairs and 18,207 nodes. Its unrestricted
capacitance matrix has a negative VGND basis-vector energy, dominated by a
negative fixed-rail VGND/VPWR term. This is not a transistor-inclusive dynamic
model result. With ideal supply/bulk perturbations fixed to zero, exact
aggregation leaves 242,178 dynamic pairs, including 413 negative pairs
(`prototype_v3_assembly_fixed_rail_capacitance_001`). The positive-path proof
in `_assembly_fixed_rail_passivity_001` is inconclusive due to overallocated
paths; it does not prove a negative dynamic energy.
`check_prototype_dynamic_capacitance_mode.py` prepares a bounded sparse-mode
search with exact rational verification of any integer candidate. These
diagnostics neither qualify the full native model nor add an unrestricted
supply-port/global-PSD release gate. Intrinsic transistor capacitance is
separate from this extracted capacitor-only analysis.

The isolated TT capacitance pilot completed at 616.428 MHz, coarse 1 /
fine 128, versus 911.039 MHz in the unloaded reference. These remain diagnostic
points rather than a loaded 400 MHz bracket. The provisional routed-RC waveform
pilot is a separate run with explicit reltol=1e-5, abstol=1e-15.

The bounded sparse fixed-rail search `_assembly_dynamic_mode_001` found a
positive lowest normalized eigenvalue estimate (~0.10784), and no exact
negative energy in the integerized candidate. More strongly,
`certify_prototype_fixed_rail_capacitance.py` produced positive integer weights
that satisfy exact strict weighted diagonal dominance for all 18,203 free
nodes. `_assembly_fixed_rail_diagonal_certificate_001` retains the weights and
every exact row margin; `replay_prototype_fixed_rail_certificate.py` independently
replayed them with Python fractions in `_assembly_fixed_rail_certificate_replay_001`.
This certifies the extracted capacitor network with ideal supply/bulk nodes
held fixed. It does not qualify transistor models, unrestricted supply-port
behavior, transient convergence, final RC correlation or functional lock.

`evaluate_prototype_calibration.py` implements the prototype measured-bracket
calculation. Each corner supplies coarse code, measured seed, tuning polarity,
and frequency intervals (`minimum_hz`, `maximum_hz`) for measured fine codes.
Intervals must include measurement, numerical and model/holdout uncertainty.
A below-target interval and an above-target interval must bound the selected
seed in the declared code direction. Five-corner coverage is checked; the
former 100 ppm / quarter-LSB precision gate is not reinstated. The evaluator
reports diagnostics only: it does not verify native provenance, waveform
startup/headroom or capture under uncertainty, and cannot qualify calibration
or the release by itself. Four controls cover erased brackets, reversed
polarity, missing measured seeds and incomplete process coverage.

`assess_prototype_native_waveform.py` corrects a reporting limitation in the
waveform worker: the inherited CSV frequency still uses the first two cycles,
even though a full waveform is retained. The separate assessor measures every
complete period and duty cycle in the declared window, requires end-of-run
coverage, and reports the fastest observed startup cycle. Observed frequency
variation is explicitly separate from numerical and model/holdout uncertainty.
Its real native observer replay `_all_cycle_observer_001` measured nine complete
cycles at 399999998.27 Hz mean; the small spread around 400 MHz is retained.
Regression controls detect a period change late in a trace and reject truncated
or insufficient captures. Use this assessor on completed waveform pilots.

`run_prototype_native_successor.py` queues one changed native operating point
after a completed predecessor. It verifies owner PID/birth identity, successful
CSV status and a full-window waveform assessment; failures stop the successor.
It rejects an identical case and weaker-than-profile numerical controls, uses
a shared successor slot plus aggregate CPU/RAM leases, and never promotes a
measurement to release qualification. `prototype_v3_TT_RC_lower_bracket_001`
queues coarse 1 / fine 8 behind the routed-RC fine-128 pilot to measure the
lower fine-code endpoint. Parent loading and final model correlation remain
open; these provisional RC measurements cannot qualify calibration alone.

`compare_prototype_numerical_holdout.py` compares full-window native
assessments only when the physical command is unchanged and at least one
solver control is tightened without weakening another. It verifies input and
artifact hashes, matching operating points, and an equally long or longer
capture. It retains the mean-frequency difference and the observed combined
frequency envelope. Those observations do not establish a total numerical
error bound or include independent model/holdout uncertainty, and remain
nonqualifying until related to validated functional/timing margins. Three
controls reject identical cases, weakened controls, changed physical inputs
and shorter captures.

`check_prototype_power_bulk_topology_v2.py` checks the final assembled
primitive topology and parameter signs. `_power_bulk_topology_001` retains
the initial 24 unreviewed-poly-model findings. The pinned PDK r+c wrapper
review `_resistor_wrapper_review_001` confirms the generic-poly two-terminal
interface and w/l parameters. `_power_bulk_topology_002` then passes all
51,829 primitives: 51,525 MOS devices, 280 antenna diodes and 24 poly resistors.
MOS bulk terminals connect to the declared supply polarity; explicit MOS
dimensions/junction signs and diode/poly parameter signs pass. These checks
assume externally tied nominal supply/bulk rails and do not qualify absolute
geometry, voltage stress, dynamic ERC or the entire physical-integrity gate.

`check_prototype_cell_geometry_conversion_v2.py` checks every extracted
standard-cell master against the native SPICE primitive geometry features.
The initial `_cell_geometry_conversion_001` retained two tie-cell mismatches
because it ignored Magic rsubckt records. `_cell_geometry_conversion_002`
explicitly handles those records and matches all 62 masters: MOS width/length,
generic-poly width/length and the PDK scaled diode area/perimeter convention.
The grid is anchored by the earlier independent primitive-dimension control.
Unknown native record types and implicit multiplicity are rejected. MOS
source/drain area/perimeter conversion and device-model physics remain separate.

`check_prototype_junction_conversion_v3.py` extends the conventional
geometry-conversion review to MOS source/drain area and perimeter attributes.
The first parser stopped on a decap zero-attribute convention. `_002`
explicitly resolves those records using node ndiff/pdiff geometry (pinned
SKY130 classes 4/5) and retains one mismatch from using significant-digit
rather than decimal-place precision. `_junction_conversion_003` checks the
observed five-fractional-decimal-place export convention: all 62 masters are
consistent within half a fifth-place unit (um^2 for areas, um for perimeters).
It uses one-to-one geometry groups and permits source/drain exchange. This
does not prove independent diffusion-polygon geometry or device-model physics.

`run_prototype_capture_boundaries_v2.py` observes 21 native data-rise,
data-fall and asynchronous-release cases per used FF master/corner. The first
fixture preflight (`prototype_v3_capture_TT_dfrtp1_001`) rejected additional
extracted internal ports before any native launch. `_002` preserves these
ports as distinct private nodes and completed all 21 TT dfrtp_1 cases, with
all pretest states and six separated controls passing. The review receipt
`prototype_v3_capture_TT_dfrtp1_review_001` retains sampled transition brackets
[-200,0] ps for all three observation types, without claiming behavior inside
them or setup/hold/recovery/removal qualification.

The declared 200 ps input edge is the full 0–100% linear PWL ramp (120 ps
20–80% slew); edge offsets refer to 50% crossings. Output load is 20 fF.
`run_prototype_capture_campaign.py` reuses that completed pilot and covers all
five used FF masters at TT/FF/SS/SF/FS, 27 C / 1.8 V, with four small-cell
workers and shared aggregate leases. The campaign is
`prototype_v3_capture_five_corner_campaign_001`. All five TT points completed
(105 cases / 30 separated controls); other corners continue. Sparse boundaries,
this single load/ramp point and isolated cell capacitance do not qualify the
complete sequential timing tables or final intercell-coupling envelopes.

`assess_prototype_capture_waveforms.py` verifies the complete printed table,
clock/input edge timing, measured 20–80% slew and every post-test Q 50%
crossing. Separated controls require the expected crossing count and direction,
so a final correct state cannot hide an extra pulse. The TT dfrtp_1 review
`prototype_v3_capture_TT_dfrtp1_waveforms_001` passes all 21 waveform integrity
checks and all six separated output-crossing controls. Clean measured CQ
delays at this point are about 240–271 ps at 20 fF / 120 ps 20–80% input slew.
Signed output delays and near-boundary behavior are retained rather than
converted into qualified constraints. Printed sample precision remains that
actually emitted by ngspice; interpolation does not imply exact timestamps.

`inventory_prototype_FF_wire_loads.py` reconciles all 489 routed FF Q
outputs with the pinned conventional nominal SPEF and physical instance join.
`prototype_v3_FF_wire_loads_001` finds 47 outputs above 20 fF in wire
capacitance alone. Per-master wire maxima are 65.3672 fF (dfrtp_1), 97.2426 fF
(dfrtp_2), 162.576 fF (dfrtp_4), 23.0473 fF (dfstp_1) and 159.82 fF (dfstp_4).
PIN_CAP NONE excludes receiver input capacitance; final parent/fill loading
is also separate. Consequently the initial 20 fF capture grid is not a
qualified load envelope, and these statistics must guide its extension.

The capture campaign completed all 25 master/corner points (525 native
cases). `prototype_v3_capture_five_corner_waveform_review_001` verifies exact
coverage and reviews all 525 complete waveform tables, input/clock timing
and all 150 separated output-crossing controls, with no failed points.
These are the 20 fF / 200 ps full-ramp observations; wider loads and
sequential timing-table qualification remain open.

The retained ngspice47 binary was configured with KLU disabled. A separate
stock-KLU build (`build/tools/ngspice47_klu_001`) retained its missing-libtool
bootstrap failure. `build_prototype_ngspice_klu_v2.py` uses host bootstrap and
the pinned image compiler, local temporary build scratch, and a permanent
installation plus bootstrapped-source archive in `ngspice47_klu_002`. Runtime
dependencies resolve inside the pinned image; temporary build scratch is not
a runtime requirement. `prototype_v3_KLU_device_source_identity_001` compares
1,212 compact-device C/header files byte-for-byte against the original source
archive. The new capture regression explicitly selects `.option klu` and
requires the native KLU-selection banner. It remains experimental until its
regressions and numerical comparisons pass; the running SPARSE reference
continues unchanged. Host perf sampling was unavailable under the host's
existing perf_event_paranoid policy, retained in `_RC_solver_profile_001`.

The stock KLU capture regression completed all 21 TT dfrtp_1 cases and six
separated waveform controls. `_KLU_capture_comparison_001` reports identical
capture outcomes/crossing counts and 0 ps maximum observed clock-to-Q
change at printed precision; this does not establish exact numerical identity.
The full routed-RC DC setup completed with KLU (48.735 s wall, approximately
539 MB native maximum program size). Two bounded 30 ns transient probes
reached their 240 s terminal budgets: approximately 6.01 ns with 1 fA abstol
and 8.53 ns with the approved 1 nA profile abstol. Neither produced a complete
frequency measurement. Their partial logs remain retained without promotion.

`run_prototype_RC_KLU_profile_pilot.py` launches the 80 ns full routed-RC
waveform case with the profile's reltol=1e-5/abstol=1e-9, explicit KLU, and a
1 CPU/4 GiB resource lease. The older SPARSE 1 fA reference continues as a
separate retained numerical comparison. Both require completed all-cycle
review and uncertainty assessment; neither includes final parent loading.

`group_prototype_FF_loads_by_clock.py` preserves the actual clock-root groups
for all 489 outputs. Six PLLOUT-domain dfrtp_1 outputs already exceed 20 fF
in nominal wire capacitance alone, so this gap affects the fast domain.
`run_prototype_capture_boundaries_v3.py` parameterizes output load and full
input/clock ramp. `run_prototype_capture_load_campaign.py` measures all
five masters at five corners with 200 ps full ramps and loads of 100, 150,
250, 50 and 250 fF for dfrtp_1/2/4 and dfstp_1/4 respectively. These declared
loads exceed observed wire-only maxima; receiver-pin and final parent/fill
bounds remain unproven. A separate TT dfrtp_1 100 fF pilot is also retained.

The older waveform assessor hard-codes 20 fF/200 ps in its summary; its
high-load summary metadata must not be used. The versioned
`assess_prototype_capture_waveforms_v2.py` instead preserves native load/ramp
metadata and checks measured 20–80% input slew against the declared ramp.
`review_prototype_capture_load_campaign.py` waits for native completion and
creates independent corrected reviews, without rerunning native cases or
changing pinned reports. Every new campaign remains diagnostic; setup/hold,
recovery/removal, load/slew coverage, numerical uncertainty and release
qualification stay open.

`run_prototype_BBPD_phase_screen.py` starts conventional extracted BBPD
observations at TT/27 C/1.8 V for -1000/0/+1000 ps clock phase, with stock
KLU and profile numerical controls. The native fixture prints reference,
divided clock, reset and both outputs for the complete 90 ns interval.
It records pulse counts/widths and slew without assuming a passing pulse
polarity, receiver capture, distributed-R or parent-loading qualification.
A versioned observer (`run_prototype_BBPD_phase_screen_v2.py`) additionally
checks absolute reference start/frequency; its integrity tests reject wrong
phase/frequency, missing table indices, nonfinite values and truncated runs.
The active original worker remains pinned and unchanged.

The initial BBPD interface inventories (`_DN_assembled_interface_001` and
`_UP_assembled_interface_001`) returned zero exterior loads because the
hierarchy helper's top-local internal names were compared with fully rooted
flattened names. They must not be interpreted as physical load evidence.
`prototype_capacitance_aliases.py` retains the exact flattening alias resolver;
`inventory_prototype_interface_loading_v2.py` roots internal nodes, preserves
top ports and resolves zero-R aliases before selecting capacitor/device
terminals. Controlled tests cover internal aliases and top-port names.
The corrected `_002` inventories find 365 DN / 250 UP external aggregated
capacitor pairs and 16 receiver transistor gates on each output. Coupled
other terminals remain explicit; these are not equivalent ground loads and
intrinsic nonlinear receiver capacitance is not yet evaluated.

The TT dfrtp_1 100 fF pilot completed all 21 native cases and six separated
controls. Its corrected full-waveform review
(`prototype_v3_capture_TT_dfrtp1_100fF_waveforms_001`) passes all 21 table and
control checks, preserves 100 fF/200 ps metadata and verifies measured input
slew. At the -1000 ps separated control, observed clock-to-Q is approximately
627.99 ps for data rise, 421.08 ps for data fall and 627.99 ps for asynchronous
release. These are individual native observations, not qualified timing
constraints or an uncertainty-covered load envelope.

`compare_prototype_capture_loads.py` checks identical native cell-model and
simulator hashes, matched corner/supply/temperature/input ramp, exact offset
coverage and passing separated waveform controls before comparing two loads.
The TT dfrtp_1 20/100 fF comparison finds rising clock-to-Q 271.19/627.99 ps
and falling clock-to-Q 239.67/421.08 ps at the -1000 ps control. All three
sampled transition brackets remain [-200,0] ps. Nonmonotone, unsettled or
incomplete observations cannot produce a single-transition bracket. Neither
these coarse brackets nor load interpolation are qualified constraints.

`check_prototype_gate_connectivity.py` screens all extracted primitive gate
conductors for a potential DC-support path through MOS channel terminals,
resistors/diodes, rails or declared boundary ports. The assembled screen
`prototype_v3_gate_DC_connectivity_001` passes with no unsupported gate
conductors. Capacitors do not count as DC drivers. The screen intentionally
does not establish conduction in every bias state, absence of static current,
voltage stress or complete electrical-rule qualification; those flags remain
false. Controlled tests reject a gate-only floating conductor and preserve
channel-chain/boundary-port support.

The strict SPARSE routed-RC TT coarse-1/fine-128 reference completed in
9,159.629 s native wall time. Its successor's full-waveform review covers
44,281 samples and 26 complete measurement cycles over 20–80 ns: mean
459.7206815 MHz, observed cycle-frequency interval 459.5114147–459.8380641
MHz, duty interval approximately 0.519626–0.519697. The waveform ranges from
-0.04518 to 1.87183 V; these extrema do not establish an all-device stress
qualification. The legacy two-cycle CSV reports 459.528 MHz, illustrating
why all-cycle review is required. The changed fine-8 native case has started
after the reference completed and passed its waveform review. Neither case
contains final parent/receiver loading or a qualified numerical uncertainty.

`prepare_prototype_BBPD_receiver_v2.py` selects both actual BBPD event flops
and their clock/data/asynchronous-control combinational fan-in, stopping at
other sequential outputs and primary inputs. The retained `_receiver_001`
attempt failed on escaped generated instance names. The versioned `_002`
preparation normalizes leading identifier escapes with collision checks,
and binds all 17 selected cell masters/pins/conductors to the filled-layout
LVS extraction. It then uses actual assembled cell-local capacitance models.
Four boundary inputs are the two BBPD bits, track_pipe[1] and local
fast_pipe[1]; two outputs are the actual event-toggle states. The manifest
retains 44 omitted receiver terminals and explicitly leaves intercell RC,
parent coupling and boundary-stimulus qualification false.

`run_prototype_BBPD_receiver_pilot.py` applies two clean 1 ns pulses, 40 ns
apart, separately to each receiver polarity, with the opposite polarity low
and both enabling pipeline states released after reset. It checks complete
80 ns native output tables and one rise/one fall of the active toggle with
no inactive-toggle edges. This is a receiver control, not a measured-BBPD
stimulus, minimum-pulse-width qualification or full-load correlation. Cone
integrity tests reject missing/multiple drivers and truncated waveform data.

Both actual-receiver native controls completed and passed in
`prototype_v3_BBPD_receiver_native_control_001`. DN and UP each produce one
rise at approximately 20.432970 ns and one fall at 60.431065 ns on the active
event-toggle output, with no inactive-toggle edges. The first input pulse's
50% rising center is 20 ns, giving approximately 433 ps observed latency.
The entire 80 ns tables are retained. This establishes the stated clean-pulse
control only; actual BBPD pulses, omitted loads, wire RC, minimum-pulse
constraints and native numerical uncertainty remain unqualified.

`run_prototype_BBPD_coupled_pilot.py` connects the conventionally extracted
BBPD to the physically bound 17-cell receiver, removing the isolated pilot's
explicit 20 fF output capacitors. It requires matching passing native
receiver controls, verifies boundary aliases and distinct event-toggle
outputs, and prints reference/divided clocks, reset, both detector outputs
and both event-toggle states for complete 90 ns captures. The TT pilot
covers -1000/0/+1000 ps phase. It records detector pulses and observes whether
each detector rising edge produces one correctly alternating receiver toggle,
including paired delay when correspondence holds. Missing/spurious events
remain visible; a zero-event case cannot establish active capture margin.

Both enabling pipeline boundary states follow fixture RESET in this pilot.
This is an explicit characterization assumption, not replay of actual
sequencer timing. Intercell RC, parent coupling and the 44 omitted receiver
terminals remain unbounded; native interface qualification stays false.
Integrity tests reject ambiguous boundary mappings, duplicate output roles,
missing/spurious toggle events and truncated seven-channel native tables.

`compare_prototype_DCO_native_decks.py` compares actual generated native
SPICE decks, permitting only explicit KLU selection and RELTOL/ABSTOL values
to differ. Other records, including models, supplies, clocks, transient
horizon/max-step, method and charge tolerance, must match. The retained
`prototype_v3_DCO_solver_deck_identity_001` proves this identity for the strict
SPARSE and profile-tolerance KLU coarse-1/fine-128 experiments. It does not
claim that the still-running alternative has completed or converged.

`review_prototype_DCO_solver_waveforms.py` waits for that alternative's native
owner identity and terminal receipt, checks the stock compact-device source
identity and capture regression, performs full-cycle waveform review, repeats
actual deck identity checks, and compares matched operating points/windows.
The comparison reports observed frequency/duty envelopes and mean differences.
Solver and ABSTOL change together, so their effects are not independently
separated. Observed envelopes are not universal numerical-error proofs and
cannot themselves qualify functional capture margins. Tests reject changes
to physical decks/undeclared controls, duplicate/nonfinite tolerances,
window/point mismatches and invalid/insufficient measured cycles.

`bind_prototype_BBPD_receiver_wire.py` binds all 41 functional terminals of
the 17-cell receiver to 21 nominal conventional SPEF networks, verifying
scalar pins/directions, exact logical-net membership and resistance-graph
connectivity of every named terminal. Outside terminals and all RC records
are retained. `prototype_v3_BBPD_receiver_wire_binding_001` passes this
binding. The BBPD[0]/[1] boundary networks have 23.3875/29.957 fF declared
wire capacitance; event-toggle outputs have 10.1236/7.17564 fF. PIN_CAP NONE
excludes nonlinear receiver pin capacitance. The data are not yet applied
to the native receiver and do not bound omitted pins or parent/final-fill
coupling. Tests reject missing/disconnected/shorted nets and wrong directions.

`run_prototype_BBPD_DC_probe.py` retains the coupled circuit and numerical
controls but substitutes a DC operating-point analysis for the transient.
The independent capped probe completed its single DC point in 27.167 s wall
(native analysis approximately 0.975 s, total native elapsed 21.807 s,
maximum native program size approximately 356.8 MB). Consequently the
longer ongoing coupled transient is not explained by initial bias setup.
This is resource/convergence diagnosis, not transient or interface
qualification; existing native transients continue without restart.

The coupled BBPD 9 ns probe completed 942 samples in 42.568 s wall, before
the first divided-clock transition. `reduce_prototype_BBPD_fixed_rails.py`
finds 1,620 of 1,782 primitive instances with every terminal fixed to ideal
constant rails; 162 remain. It flattens only this signal-voltage model,
retains every signal-connected signed capacitor and all retained primitive
parameters, preserves zero-R port aliases and checks exact decimal conversion.
Independent reparsing verifies the retained primitive-card multiset and signed
capacitance pairs. Only all-fixed-terminal devices and fixed-rail-only
capacitors are omitted. Power/supply current/noise/nonideal-rail behavior is
not preserved, and full native signal-waveform correlation remains required.
The full extracted models and their ongoing native holdouts remain unchanged.

`run_prototype_BBPD_short_probe_v2.py --reduced-model` completed the matching
9 ns horizon in 23.884 s, also with 942 samples.
`prototype_v3_BBPD_9ns_reduction_comparison_001` compares both complete seven
signal captures on the union of their sampled time grids using piecewise
linear interpolation. Threshold-crossing counts match; maximum observed
voltage difference is approximately 15.857 microvolts. Sample timestamps
are not identical. This reset/quiet-window comparison does not establish
active detector capture or a universal numerical-error bound.

`run_prototype_BBPD_coupled_signal_pilot.py` starts the longer TT phase screen
with the reduced signal model and the actual 17-cell receiver. The fixture
holds supply/bulk rails at ideal constant voltages and global temperature at
27 C. It remains a diagnostic model until full-versus-reduced active native
waveform comparison, omitted loading and numerical uncertainty checks finish.
Tests cover exact retained cards/negative capacitances/aliases and reject
inexact conversion of nonterminating rational values.

The isolated BBPD -1000 ps native phase case reached its explicit 1,800 s
per-case resource limit before completing 90 ns. Its retained progress log
ends near 29.2277 ns; this is a resource/numerical observation, not a hardware
functional failure. Other declared phase cases continue independently.
The full coupled holdout also shows extremely small progress near 29.2275 ns.
The reduced coupled model remains live, with observed progress near 13.098 ns
at inspection. Thus removal of fixed-terminal devices improves cost but has
not yet resolved transient stepping around active clock transitions.

Matching full/reduced 12 ns probes extend the comparison across the first
input clock transitions. The reduced probe completed 1,714 samples in
36.761 s, with reference/divided/reset transitions at 10.1/9.1/1.1 ns and no
half-supply crossings yet on detector or event-toggle outputs. The full
12 ns probe remains independently bounded and live at inspection. A short
horizon or quiet detector output is not a completed pulse-capture test.

The full 12 ns coupled probe completed in 176.093 s versus 36.761 s for the
reduced model. The matched comparison retains 1,805/1,714 native samples;
all seven signal threshold-crossing counts match and maximum observed
piecewise-linear voltage difference remains approximately 15.857 microvolts.
This still precedes an active detector output pulse and does not qualify
full-horizon event capture.

Two separate bounded experiments investigate the active-edge stepping issue.
`run_prototype_BBPD_shunt_probe.py` explicitly adds 1 aF to every voltage node
of the reduced signal circuit; native output confirms 134 added capacitors.
The stock implementation was inspected in the pinned bootstrapped source
(frontend cshunt parsing and INPpas4 insertion). Its 40 ns probe advances
quickly to approximately 29.2274 ns, then progresses very slowly. The added
capacitances are a physical perturbation, not qualified extracted capacitance;
artifacts explicitly record that distinction and leave margins unqualified.

`run_prototype_BBPD_method_probe.py` changes only the integration method to
trapezoidal for another capped 40 ns reduced-model run, retaining profile
RELTOL/ABSTOL and adding no capacitance. The existing Gear full/reduced
holdouts continue unchanged. Neither bounded experiment has qualification
status; their outcomes must determine subsequent numerical work rather than
being treated as a release pass.

The higher-load native capture campaign and independent corrected waveform
review both completed all 25 master/corner points: 525 native waveforms and
all separated controls pass, with native load/ramp metadata and measured
slew verified. Loads are 100/150/250/50/250 fF for dfrtp_1/2/4 and dfstp_1/4.
These data still do not prove receiver-pin/parent-load bounds, refined
setup/hold/recovery/removal constraints or numerical uncertainty coverage.

`observe_prototype_generated_clock.py` instruments the existing startup
regression and compiles the frozen prototype RTL inside the pinned image.
The native RTL run passes and records 1,118 ordinary generated-clock edges.
`prototype_v3_generated_clock_observation_001` observes minimum period two
PLLOUT cycles, with one-cycle high and low widths during startup; tracking
periods are 16 cycles. The routed root `$auto$ff.cc:337:slice$19039/Q` aliases
CLKDIV_RETIMED. Thus assigning a divide-by-16 clock to every startup state
would miss observed reachable transitions. This is a witnessed condition,
not an exhaustive analog pulse-width bound or timing qualification. Tests
preserve startup intervals and reject duplicate transitions/reset-epoch errors.

The 1 aF shunt and trapezoidal 40 ns probes both reached their explicit
240 s native budgets near 29.2279/29.2278 ns, respectively; neither yields
a complete waveform or qualified fix. A separate original-SPARSE probe now
checks the reduced signal circuit with no added capacitance. Its initial
controller expects a solver banner not emitted by the KLU-disabled build;
if native analysis completes, that guard cannot qualify it. The versioned
`run_prototype_BBPD_sparse_probe_v2.py` instead pins the binary build receipt,
requires its --disable-klu configuration and exact binary SHA, and rejects
unexpected KLU selection. The existing native case is not restarted; any
completed waveform requires independent assessment. These probes remain
numerical diagnosis, with all qualification flags false.

A native ngspice47 unit control identified the active BBPD numerical failure:
raw extracted diode geometry must not be passed directly to ngspice47. The
pinned source `dio/dioparam.c` and `dio/diosetup.c` do not apply the older
explicit AREA/PJ scaling convention to these level-1 parameters. Existing
`scripts/sky130_diode_translation_probe.py` also documents the ngspice42/47
geometry distinction. The earlier assumption that raw extracted diode cards
were runtime-compatible with ngspice47 was incorrect.

`prototype_v3_ng47_diode_units_control_001` measures the actual pinned PDK
wrapper at TT/27 C/0.9 V reverse bias and 1 MHz. Raw area=4.347e11 /
perim=2.64e6 produces approximately 4.08854e-4 F; effective area=.4347 /
perim=2.64 produces 5.05687e-16 F. The capacitance ratio is 8.08512e11.
This explains the severe stepping pathology around clock transitions.
The diode-free DCO and 17-cell receiver models are unaffected by this error;
MOS-only capture grids also retain their scope and evidence.

`convert_prototype_ng47_diode_geometry.py` makes versioned runtime models,
dividing raw diode area/perimeter by 1e12/1e6 while leaving all other cards
and signed capacitances untouched. Only independently reviewed HD/HS diode
geometries are accepted; double conversion and unknown geometry are rejected.
Expanded primitive reparsing proves the exact intended conversion. Separate
full and signal-only corrected BBPD models retain the original extraction.

The three still-running raw-geometry BBPD pilot controllers/native groups
were stopped after PID/birth/group checks, with immutable supersession
records and diagnostic statuses. Their earlier raw-geometry native data
cannot qualify physical signal behavior. DCO jobs continue unchanged.

`run_prototype_BBPD_ng47_geometry_pilot.py` starts both corrected full and
signal-only TT pilots. The corrected signal model completes a 90 ns case
in about 41.658 s native elapsed (26.400 s analysis), rather than timing out
near 29 ns. The original observer incorrectly rejects a negative-phase third
DIV edge in the final 85–90 ns guard interval. The versioned independent
`review_prototype_BBPD_corrected_waveforms.py` verifies all actual full-horizon
input edges, then measures the intended 5–85 ns two-cycle analysis window.
It only accepts the identified guard-observer error for re-assessment;
resource/solver failures cannot be recast as observer errors. No native
waveform is rerun or modified to correct this assessment.

The corrected signal TT review covers -1000/0/+1000 ps. DN is active at
-1000 ps; UP is active at 0/+1000 ps. The active output produces two roughly
20.06 ns pulses, each captured once by its receiver toggle with roughly
409–412 ps observed latency. Inactive outputs produce no analysis-window
events. These are corrected native observations; five-corner coverage,
full-model correlation, parent/intercell loading and uncertainty remain open.
The full corrected TT pilot and its independent guard-aware review continue.

`prototype_v3_BBPD_corrected_TT_model_comparison_001` completes matched
full/reduced correlation for all three corrected 90 ns TT captures. Actual
decks match except the declared corrected full/signal model include. All
seven signal threshold-crossing counts match. Maximum observed paired edge
difference is 0.15117 ps; maximum piecewise-linear voltage difference is
approximately 9.6044 mV. This supports the ideal-constant-rail signal reduction
at these observed conditions, without bounding omitted loads or universal
numerical error.

`run_prototype_BBPD_ng47_corner.py` uses the guard-aware observer directly
and accepts the five prototype process corners at 27 C/1.8 V.
`run_prototype_BBPD_corner_campaign.py` starts 55 corrected signal-model
cases on the declared -1000/-200/-50/-20/-5/0/+5/+20/+50/+200/+1000 ps grid,
plus 12 full-model holdouts at -1000/0/+1000 ps for FF/SS/SF/FS. TT's completed
three-case full correlation is reused as provenance. Eight small native
workers share the CPU/RAM lease system; no failed point is identically
retried. Full-model corner correlation, reset-alignment, omitted loading and
numerical-margin qualification remain separate work.

`run_prototype_KLU_four_core_probe.py` changes only num_threads from one to
four in the prior profile-tolerance 30 ns resource probe, with identical
other native deck records. It reserves four CPU slots, pins four distinct
physical cores (no SMT), limits memory to 4 GiB and keeps a 240 s native
budget. Observed native Threads=4 and CPU affinity 0–3 confirm enforcement.
The benchmark reached its budget; the partial progress log is retained and
is not a completed 80 ns measurement or qualified numerical comparison.

`run_prototype_DCO_native_point.py` starts the missing nominal-RC coarse-1
fine-8/fine-247 endpoint observations at FF/SS/SF/FS, plus TT fine-247. The
existing TT reference/fine-8 cases are explicitly rejected as duplicate
requests. Each new point uses profile controls, one CPU/4 GiB, 12 h outer
budget and full-cycle waveform assessment after successful native execution.
These are measured endpoint candidates, not assumed calibration presets;
coarse/seed selection must follow actual brackets and uncertainty margins.
The two ongoing TT reference/bracket jobs continue unchanged.

The completed profile-tolerance KLU DCO run takes 4,458.738 s native wall
for the 80 ns TT coarse-1/fine-128 case. Independent all-cycle review measures
459.686166 MHz, versus 459.720682 MHz for the stricter SPARSE reference:
34.516 kHz / 75.079 ppm observed mean difference. The combined observed
cycle-frequency envelope is 459.476585–459.838064 MHz. Solver and absolute
current tolerance change together, so this is a combined sensitivity result,
not separate attribution or a universal numerical bound.

`run_prototype_native_successor_v2.py` retains changed-point/tighter-control
checks and identity-checked successful predecessors, but uses the standard
1 CPU/4 GiB worker cap and a separate serial lock for numerical holdouts.
`prototype_v3_TT_RC_KLU_tighter_step_001` keeps the completed profile point's
physical conditions and ABSTOL=1e-9 while tightening max step to 5 ps and
RELTOL to 1e-6. It runs as a distinct numerical holdout; the old fine-8
16 GiB reference slot and all endpoint cases remain unchanged.

All five corrected signal-model corner grids have completed their 11 phase
cases without native failures; the overall campaign awaits its final full
holdout point. Sampled polarity transitions are bracketed by [-200,-50] ps
at TT/SS/FS and [-50,-20] ps at FF/SF. These are coarse observed transition
brackets, not a calibrated timing offset or qualified uncertainty bound.
The nonzero detector bias must be retained when building the correlated
loop model; zero input phase is not assumed to be a balanced decision.

`prototype_v3_BBPD_five_corner_phase_campaign_001` completed all nine declared
points with no failures: 55 corrected signal captures plus 12 new full-model
holdouts. `review_prototype_BBPD_corner_campaign.py` verifies their pinned
artifacts and incorporates the three earlier TT full holdouts. Full/reduced
crossing counts match at every corner; maximum observed paired edge difference
across the five corners is 0.35952 ps. The report preserves measured polarity
brackets, detector/reference delay, event-capture delay and pulse-width
intervals, with load and numerical uncertainty qualification still false.

`observe_prototype_BBPD_reset.py` checks late reset release against actual
clock guard edges, quiet detector/toggle levels before the first allowed
reference, correct signed output polarity, expected pulse/toggle counts and
final state. `run_prototype_BBPD_reset_point.py` uses the corrected reduced
model for these controls. The TT 15 ns release pilot passes both signed phase
cases: no event occurs before the next reference at 50.1 ns, followed by
one correctly captured event. Tests reject a pre-sample 0.4 V glitch even
when half-supply edge counts still look correct, and reject wrong reset timing.

`run_prototype_BBPD_reset_campaign.py` starts the five-corner controls at
15/25/35 ns reset start, each with -1000/+1000 ps phase, reusing the passing
TT/15 ns pilot. Thirty native cases cover the declared late-release grid.
Four small workers use the shared resource leases. This checks reset-release
behavior under the declared fixture; actual sequencer timing, intercell RC,
parent loading and interface qualification remain open.

`refine_prototype_BBPD_phase.py` adaptively queries each measured transition
interval using corrected native reduced-model captures. It seeks an observed
interval no wider than 25 ps with at most four distinct probes per corner;
this is a characterization target, not a new release precision gate. The
single-point worker caps native wall time at 300 s under a 600 s outer budget.
Only two clean active-polarity pulses, correctly captured with quiet initial
state and no opposite-polarity event, move a bracket endpoint. An ambiguous,
unresolved or uncaptured observation retains the prior enclosing bracket;
no identical probe is retried. Four small workers use shared resource leases.
Tests reject missing captures, missing pulse edges, ambiguous/absent polarity
and nonquiet pre-sample behavior as binary classification evidence.

The late-reset release campaign completed all 15 corner/release points and
30 signed-phase native controls without failures. The adaptive phase campaign
also completed: 11 additional native probes refine all five observed intervals
to 25 ps or less. Observed brackets are FF/SF [-50,-35] ps, TT/FS [-69,-50] ps
and SS [-88,-69] ps. These are measured nominal transition intervals under
the declared fixture, not universal phase/loading uncertainty bounds.

`build_prototype_BBPD_receiver_RC.py` rewires all 41 selected receiver pins to
their exact SPEF terminal nodes, retaining cell-local capacitance definitions.
The nominal receiver model contains 115 positive wire resistors and 449 wire
capacitors; internal mirrored couplings are emitted once. Every serialized
wire topology/value is independently reparsed exactly. The model exposes
196 nonzero off-network coupling terminals as explicit aggressor ports;
zero-only off-network records do not create ports. No off-network terminal
is implicitly grounded in the reusable model. Interface ports attach to their
actual input/source terminals, preserving resistance from source to cell pins.
Tests reject missing/inconsistent mirrored couplings, zero wire R and wrong
logical pin bindings, and verify that local cell C remains intact.

`run_prototype_BBPD_receiver_RC_pilot.py` connects the corrected signal BBPD
to that receiver model. The first TT fixture explicitly holds all off-network
aggressor ports at ideal 0 V; it is a quiet conditional holdout, not an
assumption that those nets are always ground. The independent guard-aware
waveform reviewer is queued. The initial launch retains the older guard
observer, whose negative-phase third input edge must be independently
re-assessed as in the corrected TT pilots. Missing external receiver pin C,
parent/final-fill coupling and nonquiet aggressor activity remain unbounded;
no interface qualification is claimed from the wire construction alone.

The quiet nominal-RC TT pilot completed all three 90 ns native captures.
Its independent guard-aware review passes: each active detector pulse is
captured exactly once, with no inactive-polarity events. Observed capture
delays are approximately 452.7–474.9 ps, compared with roughly 409–412 ps in
the cell-local-only receiver. This is a measured wire-loading effect and
must be retained in the correlated model. The quiet aggressor fixture does
not establish nonquiet crosstalk bounds, omitted receiver pin loading or
parent/final-fill coupling qualification.

The first completed DCO endpoint at SS/coarse-1/fine-247 measures
357.791109 MHz over the complete native observation window. This observed
upper endpoint is below the target; it cannot establish a 400 MHz bracket.
SS coarse-2/fine-8 and fine-247 observations have therefore started. The
remaining coarse-1 endpoints continue; calibration will use measured brackets,
not an assumed common coarse code across process corners.

`run_prototype_BBPD_receiver_RC_point.py` extends the bound receiver RC
fixture to declared corners and explicit off-network activity. It uses the
correct guard-aware observer directly and rejects rerunning the completed
quiet TT signal grid. TT full-model quiet correlation and two reduced-model
stress points have started. In the stress fixtures all 196 exposed coupling
ports follow one declared 400 MHz / 20 ps full-ramp clock, with offsets 325
and 1575 ps (opposite phases near the nominal detector output transition).
These are explicit conditional stress scenarios, not a proof that every
real aggressor can switch together or that all startup frequencies/activity
patterns are covered. Parent/final-fill coupling and omitted receiver pin
loads remain unbounded; interface and release qualification remain false.

Both reduced-model TT switching-aggressor scenarios completed all three phase
captures with matching expected detector/toggle event counts. However, the
DN event-toggle output reaches approximately 0.45265 V during its low-state
quiet interval (UP toggle approximately 0.21308 V). The DN value exceeds the
existing 0.36 V diagnostic quiet screen, so these conditions must not be
reported as passing electrical/interface qualification merely because
half-supply crossing counts match. This is a deliberately common-activity
stress fixture; actual aggressor ownership/activity and receiving-flop
capture/noise immunity must be assessed before interpreting its release
impact. The original quiet-screen results are retained without relaxation.

### Receiver conductor ownership and conditional capture replay

`map_prototype_receiver_aggressors.py` resolves all 196 exposed coupling
terminals to 145 distinct conductors in the complete nominal routed SPEF.
Each terminal has a unique conductor, logical bit, actual routed driver and
primary/sequential source cone. Vector primary ports and escaped instance
names are resolved explicitly; ambiguous ownership, merged logical nets and
unbound terminals fail. The retained result is
`prototype_v3_BBPD_receiver_aggressor_ownership_004/aggressors.json`.
The largest individual DN-event-wire couplings include 2.46682 fF from a
PLLOUT-domain state path, 2.36597 fF from CONFIG_READY logic and 0.93867 fF
from another PLLOUT-domain state path. Thus the original common-clock
fixture is a conditional stress observation; its activity cannot be assumed
to represent the actual routed logic.

`run_prototype_receiver_glitch_replay.py` replays the measured 5–8 ns DN-wire
quiet-window waveform from the TT/325 ps stress case into the extracted
`sky130_fd_sc_hs__dfrtp_1` used by the actual first receiving synchronizer.
Five receiving-cell corners, thirteen clock phases separated by 250 ps and
both the observed low-state glitch and its complemented high-state version
produce 130 conditional cases. The output load is 2 fF and the complete
output waveform is checked for wrong-state excursions and transient captures,
including captures that subsequently recover. These jobs are running;
`review_prototype_receiver_glitch_replay.py` independently checks finite,
complete, ordered native tables, every declared case, and the routed receiving
cell/PLLOUT clock binding before reporting their results. The source waveform
is TT, the high waveform is a complement rather than a measured high-state
response, and a finite phase grid is not a continuum proof. Actual pin loading
of the original source waveform remains open. These cases cannot alone
qualify the interface or replace the retained failed quiet-screen result.

The ngspice47 explicit diode-unit conversion has also been applied to the
complete assembled conventional capacitance model. Exact expanded-card
comparison verifies all 51,829 primitive instances, including all 280 diodes;
MOS, resistor and capacitance cards remain unchanged. The result is
`prototype_v3_assembly_ng47_geometry_001`. This is a compatibility preparation,
not a whole-PLL native simulation or electrical-rule qualification.

The completed SF coarse-1 endpoints measure 382.012899 and 468.878839 MHz
at fine codes 8 and 247. Their observed cycle intervals straddle the target;
model and numerical uncertainty have not yet been added. An interior native
fine-64 point is running. SS coarse-1 endpoints measure 296.674084 and
357.791109 MHz and do not bracket 400 MHz; the coarse-2 endpoint jobs remain
active. No calibration or release gate is promoted from these observations.
The prototype regression suite currently contains 90 passing tests.

The TT full/reduced detector correlation with receiver wire RC has completed
(`prototype_v3_BBPD_receiver_RC_full_signal_comparison_001`): all threshold
crossing counts match across the three complete 90 ns captures, with a maximum
paired edge difference of 0.194349 ps and maximum interpolated voltage
difference of 5.41017 mV. Omitted loads and numerical uncertainty remain open.

`run_prototype_BBPD_numerical_holdout.py` now replays four pinned phase points
per corner (-1000, -50, 0 and +1000 ps) with relative tolerance tightened from
1e-5 to 1e-6, absolute current tolerance from 1e-9 to 1e-10, and maximum step
from 10 to 5 ps. The physical deck remains identical. All five corner jobs
are running. Their observed changes must later enter the functional uncertainty
budget; agreement is not a universal numerical-error proof.

`summarize_prototype_DCO_points.py` verifies the completed all-cycle receipts
and reports measured target brackets without combining different corners or
coarse codes. It also reports pending controller liveness, avoiding an
interpretation of the legacy `native_point_complete_review_pending` status
as missing all-cycle data. The first summary contains seven completed points.
The completed FS coarse-1/fine-8 point is 408.5883 MHz, above target; FS
coarse-0/fine-8 and fine-247 jobs have started. The regression suite now has
94 passing tests. The current five-gate audit remains false for release
readiness; the frozen source and physical candidate identities still match.

### Native pulse, numerical-sensitivity and receiver-load follow-up

The independent review of the original glitch replay completed all 130
cases with their full output states retained. The additional peak-targeted
TT-source replay completed 90 cases across the five receiving-cell corners,
also with all states retained. Its clock phases include the measured glitch
peak and offsets of +/-10, +/-25, +/-50 and +/-75 ps, excluding previously
sampled grid points. Both results remain conditional: the high-state waveform
is a complement, input pin loading of the original source waveform was
omitted, and finite phase samples are not a continuum proof.

The 20 native detector numerical holdouts completed across all five corners.
Every signal crossing count matches its baseline; the largest observed paired
edge differences are TT 2.4280 ps, FF 1.9552 ps, SS 2.6453 ps, SF 2.0359 ps and
FS 3.0727 ps. These empirical differences still need propagation into model
and functional margin budgets. The holdouts do not establish a universal
error bound or qualify the omitted loading scope.

`run_prototype_clock_pulse_grid.py` and its campaign completed 250 native
high/low pulse fixtures across all five used flip-flop masters and corners.
Each master uses the existing higher-load characterization fixture, with
200 ps full clock ramps and pulse widths 250/400/600/1000/1600 ps. The
independent `review_prototype_clock_pulse_campaign.py` checks the preloaded
state at 5.0–5.3 ns, after slow loaded outputs settle and before the low-fixture
D transition starts at 5.4 ns. It retains the original 4.5–5.0 ns observer
results. All pretest states are verified with the later window. All high-pulse
samples pass; low-pulse 250 ps samples fail for all five SS masters and SF
`dfstp_1`/`dfstp_4`, while their 400 ps and larger samples pass. These are real
retained pulse-capture limits, not grounds to require every design clock to
work at 250 ps. Actual design clock widths, slew/load envelopes and numerical
uncertainty must be compared with conservative derived constraints before
the digital gate can pass.

The explicit common-activity receiver stress fixture has now completed at
TT/FF/SS/SF/FS. DN quiet-window peaks are respectively 0.452645, 0.412923,
0.496323, 0.404982 and 0.510877 V; UP peaks are lower. The original 0.36 V
quiet-screen failures remain retained. Source/receiving-cell matched corner
peak replays are running, reusing the completed TT point and measuring each
other corner's own waveform. Native receiving-cell capture behavior and
bounded electrical/functional margins must support interface acceptance;
the diagnostic quiet screen must not be silently relaxed or treated as a
substitute for actual receiver immunity.

`extend_prototype_receiver_synchronizers.py` adds the two actual first
synchronizer cells to the bound receiver model. Their D inputs attach to
exactly the existing named SPEF wire terminals, preserving original wire R/C
and all extracted cell definitions. Cell identities are also bound to the
filled-layout CDC mapping. The extended model is
`prototype_v3_BBPD_receiver_with_sync_001`. Its first native TT pilot includes
both D loads and explicit 400 MHz sampling clocks, sampling at 345 ps to
align with the observed aggressor-induced peak; output loads are explicitly
20 fF fixtures. Clock/reset tree RC and final Q fanout envelopes remain open.
This pilot measures the physical loading and captures together rather than
assuming that an omitted input capacitance has no effect.

`run_prototype_DCO_tuning_step.py` has started a conventional-RC TT/coarse-1
fine-128 to fine-129 transition at 40 ns with a 200 ps control ramp, retaining
the original 80 ns horizon and reset schedule. A separate static fine-129
observation is running for later lookup/phase-transient correlation. Additional
coarse-0 TT and FF endpoints are running as calibration candidates. They do
not select a final coarse code in advance of measured target/headroom
brackets. The prototype regression suite currently has 104 passing tests;
all release qualification flags remain false.

The first completed extended-receiver TT/-1000 ps capture measures a DN
wire quiet-window peak of 0.425173 V with the actual first synchronizer input
attached (the previous omitted-input model was 0.452645 V). The sampled first
synchronizer outputs stay near the low rail in that window, with maxima about
0.000230 V, including the peak-aligned sampling clock. This is one completed
fixture, not interface qualification. The remaining TT phases and corresponding
FF/SS/SF/FS extended-receiver fixtures are running. The build helper is tested
against changed wire resistance, wrong physical master and ambiguous omitted
loads. The prototype regression suite now has 104 passing tests.

### Loaded detector fit and first closed-loop diagnostics

The extended detector/receiver/first-synchronizer review completed 15 native
cases across all five corners. All quiet first-synchronizer outputs remain
near the low rail and every source event has its corresponding delayed
capture. The subsequent wide-phase review covers 20 points: five corners at
0/10/20/30 ns, reusing the completed zero-phase captures. Its native event
captures match throughout. At TT with a 20 or 30 ns initial phase offset,
the first reference sample produces UP and the next DN. The initial input
history therefore belongs in the model; a steady-phase-only truth table is
insufficient.

The loaded near-zero phase review has completed 18 additional native cases.
Its observed DN-to-UP intervals are TT/FS [-75,-50] ps, FF/SF [-50,-25] ps,
and SS [-100,-75] ps. A legacy observer rejects the -100 ps fixture because
its third input half-supply crossing is exactly at the 90 ns capture endpoint.
`prototype_BBPD_guard_v2.py` verifies the native endpoint voltage and positive
slope without inventing a sampled edge or extending the capture. The original
failed assessments remain archived; the corrected review is
`prototype_v3_BBPD_loaded_bias_five_corner_review_002`.

`fit_prototype_detector_model.py` fits a delayed feedback-level sampler and
polarity-specific rise/fall latency intervals to these data. The initial
models in `prototype_v3_detector_fit_002` replay all 38 fitting points in
Icarus with matching event counts and edge differences inside the observed
fit band plus time quantization. This is fit consistency, not independent
validation. The models explicitly remain synthetic/unqualified for gate
purposes. The first replay launcher failure is retained; its successor
restricts Go/OMP/BLAS threads and uses a 4 GiB subprocess budget. The image's
`/usr/bin/python3` includes NumPy; its minimal Nix Python environment does not.

The off-grid sequential capture campaign completed 600 cases across the five
used masters and five corners, with valid pretest states throughout. It adds
-350/-250/-150/-75/+75/+150/+250/+350 ps data/control offsets to the existing
525 higher-load observations. The TT pilot brackets data and asynchronous
release capture between -150 and -75 ps. These observations still need full
constraint construction, numerical/load/slew envelopes and routed timing
checks; no setup/hold/recovery/removal gate is promoted.

A separate divided-input 1500 ps / reference-input 200 ps full-ramp campaign
completed 25 native cases with the same bound receiver and synchronizer loads.
It tests sensitivity to the slow divided-clock edge: the current routed
`dfrtp_1` divided-clock driver has 65.3672 fF of wire capacitance before its
two `clkbuf_16` inputs and analog boundary load are counted. Under this
conditional mixed-slew fixture, SS and FS transitions bracket between -500
and -250 ps, demonstrating that the 200 ps-input detector fit alone does not
bound slew sensitivity. The actual pin-load/slew envelope and resulting
functional phase margins remain open; this is not a relaxation of the
existing phase limits.

`prepare_prototype_loop_diagnostic.py` builds an explicitly unqualified SF
model from measured coarse-1 endpoint frequencies using interpolation in
period, with no extrapolation outside fine codes 8..247. The source/model
identities and compiled detector replay are pinned. The full 12-case SF run
at KI=4/KP=0 completes but fails the functional limits. KI=1 with KP=0/1/2/4/8
also completes without a full trace pass; KP=2/4 approaches the target
frequency but still violates the phase-span limit. The declared 25-pair gain
grid is running, with additional intermediate KP=3/5 diagnostic probes.
These runs cannot qualify the closed-loop gate or establish a common gain
across five corners. Other corners still need measured target/headroom
brackets and model uncertainty before their qualifying matrix is eligible.

Completed all-cycle measurements now include TT coarse-1/fine-8 at
419.773202 MHz and FF coarse-1/fine-8 at 538.88875 MHz, both above target.
SS coarse-2/fine-247 is 318.13329 MHz, below its coarse-1 value of
357.791109 MHz; the two decks differ only in the second coarse thermometer
control (apart from comments). This reverses the earlier provisional coarse
search direction. New endpoint observations test SS coarse 0, TT/FS coarse 2
and FF coarse 5. They are experimental calibration candidates, not selected
settings; coarse/fine interactions and tuning polarity must be measured.
The earlier candidate observations remain retained. The latest point summary
contains 11 completed generic points and 16 pending points, with the completed
strict TT lower endpoint reviewed separately. The prototype regression suite
currently has 120 passing tests. All five release gates remain unqualified.

The standalone `check_portable_prototype_inventory.py PACKAGE
--receipt-sha256 TRUSTED_DIGEST` verifies a relocated staged package without
opening its original source paths. Keep the trusted staging-receipt digest
outside the package. The checker rejects missing, changed or extra files,
links, mismatched profile/candidate identity and inconsistent inventory.
Three focused tests pass, and `_portable_inventory_native_control_019`
runs a relocated synthetic fixture in the isolated image with the source
workspace unavailable. This is a checker control; complete candidate
native replay and the integration contract remain unqualified.

`_selected_oscillator_farthest_schur_019` reuses the driver reduction only
after verifying the entire farthest source capacitor operator under a
bijective voltage-node map, identical floating and retained subspaces,
and unchanged target device/wire cards. The row-error certificate transfers
through the boundary permutation; independent target passivity passes.
No extraction or linear solve was repeated. Three focused rebinding tests
cover signed parallel capacitors, invalid mappings and missing endpoints.

The reduced UIC startup was archived before reset release because its
zero-charge settling remained slow. `_selected_schur_DC_native_launch_019`
evaluates normal reset-held DC initialization on the same reduced model,
with the same 80 ns duration and original deadline. Removing the floating
capacitor-only nodes changes the applicability of DC initialization; its
success remains a native measurement, not an assumed result.

Normal DC initialization now succeeds on the reduced driver model: native
ngspice reports an initial transient solution with reset held low, without
singular-node or failed-stepping diagnostics. The transient remains in
progress. The farthest case is queued only after successful independent
driver cycle and power reviews. A second dependency waits for both points
before reporting observed placement sensitivity; it explicitly leaves
physical uncertainty bounds and release qualification false. The two
focused comparison tests pass.

`_selected_oscillator_{driver,farthest}_exterior_C_bind_019` binds all 2,834
signal capacitor boundaries to retained nodes of the corresponding reduced
model. Every shared exterior conductor maps consistently. These are the
explicit capacitance-placement maps, not claims of exact physical wire
locations. Missing, conflicting and eliminated endpoints are rejected by
two focused controls. No exterior capacitor is stamped by this step.

`_selected_exterior_C_operator_launch_019` composes the complete stock
exterior capacitor network, with only the DCO body removed, with the
mapped-fill reduced DCO. It retains every exterior capacitor and remote
dynamic endpoint, including signed compensation pairs. Only explicitly
fixed supplies are projected to their AC reference. The driver operator
has 913,152 dynamic pairs. It is quarantined: exact principal screens
find seven negative dynamic diagonals and 23 negative two-node minors.
A replay produces byte-identical operator pairs and the same negative
energy result. The source interior absolute reduction certificate carries into
the enlarged operator; no combined relative-error bound is claimed.
Exterior transistor/wire models, dynamic stimuli, FOM coverage and loaded
native validation remain open. Two focused composition tests pass.

The mixed geometric operator is rejected by its exact negative-energy
witnesses. The earlier seven-node diagnostic matched exported cell counters
by name; the subsequent native placement comparison finds 1,120 of 2,070
standard-cell counters refer to different geometry across those extractions.
That name-only binding cannot establish physical conductor identity.
`_selected_context_physical_diagonal_review_019` now uses the proved
primitive-conductor bijection for the same seven physical conductors; all
current diagonals are nonnegative. The old failure cannot be attributed
solely to context differences on the basis of the old counter comparison.
The current reference uses one complete native context and is unaffected
by that archived binding. The mixed operator remains quarantined.

`_selected_parent_context_fill_view_v2_019` retains the complete parent
hierarchy and drawing geometry while mapping the same 63,873 selected
poly/LI/metal fill polygons around the DCO. Only selected purpose-99
polygons are removed after mapping them to purpose 20; unselected fill and
opaque FOM remain. This avoids the retained-99 overlay behavior measured
by the earlier native paint control. Full geometry and MOS-gate comparisons
pass; the manufacturing GDS is unchanged. `_selected_parent_context_fill_capacitance_019`
is the new native extraction under the original checkpoint deadline. FOM,
neighborhood convergence, loaded models and release qualification remain
open. The earlier overlaid view is archived and was never extracted.

The context extraction has two dependent reviews queued. The full-operator
review independently aggregates the complete native hierarchy, projects
only fixed supplies, applies the exact geometric passivity certificate and
re-resolves the seven affected conductors through the new exported ports.
No isolated interior is substituted. Two focused diagonal controls pass.
The device review applies the existing exact ngspice47 diode conversion,
compares every expanded primitive card against the same manufacturing
candidate's stock extraction and binds the existing native unit control
only if the simulator/image identities match. It does not repeat that
native control or infer loaded electrical qualification.

The context-matched extraction is complete. It expands to 62,450 primitive
instances and 2,615,221 capacitors, aggregating to 1,047,745 pairs before
fixed-supply projection. All seven previously affected diagonals are now
nonnegative. The original local-path certificate was inconclusive, rather
than a negative-energy result. `_selected_context_parallel_C_certificate_019`
subsequently covers all 750 negative pairs with parallel positive paths;
independent rational replay verifies every allocation. No coefficient is
modified by the certificate.

The first lexical device comparison differs because native instance counters
and conductor representatives changed. `_selected_context_device_reuse_v2_019`
pairs all 62,450 primitives by retained-cell master and exact native placement,
requires identical local cards across all 55 primitive masters, and proves
a bijection of all terminal conductors with named top ports fixed. All
checks pass. The independent native diode-unit control is reused only with
the matching simulator/image; its loaded electrical qualification remains
open. Two physical-graph controls reject changed connectivity, placement
or primitive parameters while accepting extraction naming changes.

The full-context reference preserves actual supply incidence and independently
reparses every emitted primitive and capacitor. Exactly 63,873 capacitor-only
nodes form two components; no incident capacitor is negative. The completed
context reduction has 3,089 retained boundary nodes and reports a maximum
normalized coefficient row error of 8.044e-7 against a 1e-6 budget. Its final
certificate reporting hit Python's large-integer string limit. The numerical
products are preserved; `_selected_context_reduction_review_launch_019`
replays the inverse bound and export and runs a bounded-diagnostic certificate
without repeating the floating-charge solve. New capacity sums use downward
dyadic enclosures and exact per-path replay. Two focused controls cover the
integer-reporting regression and reject overstated capacity witnesses.
The review must pass before this reduced reference is adopted. Domain
partitioning, wire R, stimuli, FOM, neighborhood convergence and loaded
native validation remain open; all release flags stay false.

`_selected_context_guarded_reduction_019` refines the existing numerical
export and adds explicit positive diagonal guards sized from its rigorous
symmetric row-error bounds. A PSD source has a PSD exact Schur complement;
adding a diagonal that dominates the symmetric export-error row sums
preserves PSD. Both decimal and native binary guard coefficients are
checked, and their capacitance is included in the total error budget.
The final bound is 1.81e-7, below 1e-6. The source inverse certificate and
export have been replayed; no floating-charge solve is repeated. Exact
small-matrix controls cover the PSD argument, insufficient guards, total
budget rejection and decimal/binary enclosure. The earlier local-path
certificate remains inconclusive and archived. This new certificate
establishes the reduced geometric operator property; native domain behavior
remains unqualified.

The full software regression `_selected_context_regression_011.log` passes
757 tests across all 18 commands, with five optional host-tool skips. This
covers software controls, not loaded native model qualification.
A 20 um neighborhood view and native extraction are running under the same
original deadline to assess sensitivity to the 10 um fill selection. Both
views preserve the checked manufacturing GDS. The neighborhood comparison
must use proved physical conductor correspondence rather than exported
instance counters; neighborhood convergence remains open.

`_selected_context_domains_019` inventories every primitive and dynamic
capacitor endpoint in the guarded reference. Physical roles contain 4,210
oscillator, 6,636 parent, 1,782 detector and 49,822 digital primitives. Two
layers of complete parent cells around the oscillator select 10,254
primitives, with 304 conductive cuts and 7,463 remote capacitor terminals.
No remote voltage is assigned or grounded, and no domain deck is emitted.
The focused cone control verifies complete-cell selection and prevents
supply rails from pulling unrelated logic into the cone. Subsequent
partitioning must preserve receiver loading and validate interface stimuli.

The margin-20 extraction has dependent native-source aggregation, diode-unit
conversion, physical-primitive correspondence and passivity reviews queued.
Its aggregation omits the obsolete counter-based seven-node diagnostic.
Cross-neighborhood comparisons must use the physical conductor bijections.
The 757-test full regression predates this new domain-inventory helper;
the helper's focused whole-cell-cone test passes separately.


Implementation checkpoint, 2026-11-02: the expanded domain's twelve parent
and oscillator wire-R variants are complete. The physical 10/20 um
comparison still differs by 2.91% on the worst private row, PLLOUT; the
oscillator-only maximum is 4.78e-6. These are sensitivity measurements,
not qualified waveform bounds. Native decoded parent and digital PLLOUT
wire corridors now extend fill selection beyond the retained-cell windows.
Both new extraction views preserve the manufacturing GDS and all 1,948
selected physical cells. Both native extractions are complete;
`_selected_context_clock_wire_models_launch_019` is reviewing and reducing
them before pruning, wire-R assembly and physical neighborhood comparison.
All dependent controllers retain the original checkpoint deadline.

The software regression `_selected_context_regression_launch_013` passes
779 tests across 18 commands with five optional host skips. Eight subsequent
focused controls pass for native wire envelopes, disjoint routed corridors
and DC netlist/operating-point parsing. This is software evidence only.

`_selected_assembled_DC_control_019` prepares the assembled 62,450 primitive,
6,054 wire-resistor model for a reset-held operating-point check. Its
1,038,547 explicit constant capacitor cards are opened for DC only;
no transient equivalence is inferred. The DC controller waits for the
existing isolated TT transient. Two older idle isolated comparison
controllers were superseded before launching native cases; the live
transient remains unchanged. The first independent parse-only control
exhausted its 60-second local budget without a completed parser result.
`_selected_assembled_parse_control_v2_019` separates preprocessing cost from
DC solution with a 600-second local cap, bounded by the same original
checkpoint deadline. This control runs no native analysis. Neither parser
nor DC preparation qualifies a loaded model or changes native transient
concurrency. All five release gates remain open and all release flags false.

The idle 120-second DC controller was subsequently superseded before native
launch: the separate parser had already exceeded that budget.
`_selected_assembled_DC_control_v2_019` reuses the exact prepared deck,
requires the completed parse-only receipt, and caps the complete native
load plus operating-point check at 1,200 seconds. It still waits for the
live reference transient and retains the original overall deadline and
single-large-transient policy. Neither DC controller has executed a native
analysis at this checkpoint.

`_selected_context_clock_wire_private_row_review_019` waits for the physical
10/20 um operator comparison, then reports retained private nodes, conductive
boundary cuts, oscillator-only rows and private parent/shared rows separately.
It verifies the physical mapping and rejects missing private or boundary
rows. These measurements diagnose spatial sensitivity; they do not by
themselves establish waveform convergence or a release tolerance.

The wrapped parser also exhausted its 600-second local budget. No completed
native parser receipt or operating point exists. The separate
`_selected_assembled_root_parse_control_019` keeps the same 600-second cap
and tests a structural loading change: remove only the parameterless,
identity-connected outer subcircuit and preserve every primitive/resistor
card. `prototype_identity_wrapper.py` rejects reordered ports, parameters,
scoped directives, duplicate element names and non-PDK child calls; two
focused controls pass. The prepared DC deck remains unchanged. Its queued
v2 controller requires the unsuccessful wrapped-parser receipt and therefore
cannot launch DC analysis unless that prerequisite is satisfied; no receipt
is fabricated or diagnostic result promoted. The root-level parser is a
separate diagnostic, and all release gates remain open.

After confirming the failed wrapped-parser prerequisite, the idle v2 DC
controller was stopped before native launch (its exact PID/birth and absence
of children were checked). DC validation now awaits a successful structural
parser control; the existing TT transient is unaffected.

The root-level parser also reached its 600-second cap without a completed
receipt. `_selected_assembled_literal_template_parse_control_019` tests a
different representation under the same cap: 417 shared parameterless
literal PDK-call templates for all 62,450 primitives. Expansion of the
actual emitted file recovers every original primitive terminal, model,
literal parameter, resistor and outer interface exactly. No PDK device
model is replaced or evaluated by the Python transformation.
`prototype_native_literal_templates.py` rejects nonliteral/scoped values
and duplicate/reserved names; independent expansion review detects changed
terminals, parameters or resistors. Three focused controls pass. This is
an experimental native-loading control, with no analysis or qualification
claim. The original overall deadline and live TT reference are unchanged.
All six margin-10 clock-corridor wire variants are now complete; margin-20
floating-charge reduction is running.

`build/tools/ngspice47_parser_trace_001` is a separate diagnostic binary
built from a copy of the completed KLU build. Only stderr phase markers
were inserted in two frontend files; stripping those markers recovers the
original source modulo whitespace, and all 1,212 device C/header files
remain byte identical. No install step or replacement of the pinned
simulator occurred. `_parser_trace_native_control_019` compares a native
PDK inverter operating point with the stock binary: all captured variables
match exactly and the diagnostic markers are observed. This limited control
does not qualify the assembled model or replace the stock simulator.
`_selected_assembled_parser_phase_trace_019` waits for the current literal
parser to finish. If that parser succeeds, tracing is skipped; otherwise
it captures preprocessing phases from the unchanged wrapped DC deck under
a 120-second local cap, running no analysis. A timeout is recorded explicitly
and never represented as a completed parser. All jobs retain the original
checkpoint deadline; the live TT reference remains unchanged.

The stock-native literal-template parser completed within its 600-second
cap, with no analysis executed. Its completed receipt pins the actual deck,
417 templates and exact primitive-expansion review. The optional phase-trace
controller encountered the brief interval between native process exit and
receipt creation; its failed observation is preserved, and no trace was
launched. Tracing is now unnecessary because the completed parser receipt
has been verified.
`_selected_assembled_literal_DC_control_019` now waits for the live isolated
TT reference, then runs the assembled reset-held operating point using the
stock simulator and the successfully parsed template representation. It
replays template expansion, preserves every external bias card and wire
resistor, checks all captured native values and root output observations,
and keeps a 1,200-second local cap under the original overall deadline.
Opening explicit constant C is valid only for this DC control. DC completion,
loaded transient correlation and release qualification remain pending.

`_literal_templates_five_corner_native_control_v2_019` compares the actual
417 assembled literal parameter sets at all five process corners and
27 C/1.8 V. Each set has two independently biased instances; three gate
biases produce 15 original/transformed operating-point comparisons and
12,510 individual primitive current observations. All captured values
match exactly. The first control preserved three completed TT points but
rejected duplicate plot-scale vectors; v2 corrects only the explicit raw
capture list and retains the strict unique-variable reader. This validates
the representation transformation on the fixture, not loaded PLL behavior.

`prototype_native_literal_templates_v2.py` extends the transformation to
explicit constant capacitors. Signed values, terminals and original card
order survive independent expansion review; two focused controls pass.
`_selected_context_clock_wire_full_C_parse_control_019` waits for the native
five-corner control and completed margin-20 nominal/driver joint-wire model,
then parses the complete capacitor-preserving template representation with
the stock simulator. It checks that every source literal parameter set was
covered by the native fixture and that source wire/contraction/passivity
reviews pass. Its native cap is 1,200 seconds, under the unchanged original
checkpoint deadline; it runs no analysis. Both margin-10 and margin-20
clock-corridor guarded reductions have completed, and their physical
neighborhood comparison is running. Loaded model and release gates remain
open.

The clock-corridor physical neighborhood comparison is complete. Across
3,171 retained private nodes, the worst relative C-matrix row difference
is 6.26046e-4 at PLLOUT, versus 2.90741e-2 before adding the routed corridors.
Oscillator-only rows remain at 4.77494e-6 maximum. Conductive boundary cuts
still differ by up to 0.304623, and the full dynamic basis by 0.400505.
These distinct scopes are retained in the comparison and private-row
receipts; no waveform-convergence or model-qualification flag is promoted.

`inventory_prototype_loaded_domain_halo.py` inventories one complete-cell
conductive layer around the whole-parent/oscillator/PLLOUT-receiver domain.
It includes every physical primitive of incident cells and excludes fixed
rails from expansion. Two focused controls cover whole-cell driver/receiver
selection, fixed-rail exclusion and rejection of incomplete physical
inventories. `_selected_context_clock_wire_loaded_halo_launch_019` runs it
on the margin-20 physical reference. The inventory supplies no boundary
voltages, grounds no capacitive endpoint and exports no simulation model;
remaining interface direction and stimulus obligations stay explicit.
The complete margin-20 nominal/driver model has reached stock-native
capacitor-preserving parsing, without running an analysis.

The loaded halo inventory is complete: 344 incident physical cells add
4,713 primitives to the 10,887-primitive base. The resulting 15,600-device
selection contains 6,636 parent, 4,210 oscillator, 4,725 digital and 29
detector primitives. It has 4,212 private nodes and 560 remaining conductive
cuts. This is a measured inventory for subsequent interface characterization,
not a simulation model or validated boundary-waveform set.

The complete current margin-20 nominal/driver model passed stock-native
parsing within its 1,200-second cap: 62,450 primitives, 417 shared literal
templates, 6,054 wire resistors and 1,269,218 explicit capacitor cards.
No analysis was executed. All twelve clock-corridor wire variants are
complete. `_selected_context_clock_wire_DC_control_019` now prepares and
queues the reset-held operating point from this exact successfully parsed
model, opening only explicit C for DC. The older idle domain-model DC
controller was superseded before native launch after checking its exact
PID/birth and absence of children. The live TT transient remains unchanged.

`resolve_prototype_loaded_halo_interfaces.py` resolves the 560 halo cuts
using the same-extraction local primitive terminals, exact zero-R aliases,
physical LEF directions and root-port directions queried from the certified
frame ODB. The corrected v2 launch uses the exact HS LEF pinned by the frame
receipt, in the private PDK; the earlier missing canonical HS-path failure
is preserved. All 560 driver origins resolve, with 2,023 physical pin
endpoints, 544 external-driver obligations and 235 receiver-loading
obligations (overlapping categories). Three focused controls pass.
`_selected_context_clock_wire_halo_interface_coverage_019` independently
checks every incident cell/conductor pair, its inside/outside membership
and outside-primitive incidence. Boundary-waveform validation remains open.

A new full software regression, `_selected_context_regression_launch_014`,
is running after these material helper additions; the last completed full
regression remains 779 tests. Subsequent focused controls total 20. No
release gate or loaded-native qualification flag is promoted by parser,
representation or interface-inventory results.

The full software regression `_selected_context_regression_launch_014`
passes 799 tests across all 18 commands, with five optional host-tool skips
and source hashes verified. The independent halo interface review covers
all 2,023 expected incident cell/conductor pairs, with no missing or extra
bindings.

`_selected_context_clock_wire_conditional_plan_019` inventories the halo
against the actual current joint-wire model, retaining every wire resistor
and excluding primary inputs from private unknowns. It finds 10,231 private
unknowns, 620 conductive boundaries and 8,383 non-supply voltage obligations.
Of 7,732 capacitive-only boundaries, 4,922 are internal nodes rather than
physical cell pins. The 1,269,218 source capacitor cards partition into
714,168 contributing to private KCL and 555,050 boundary-current cards.
No deck or voltage trajectories are exported. Internal aggressor voltages
must not be replaced by arbitrary quiet values.

`_frozen_programmed_reset_reference_019` compiles the campaign's frozen
fixed-divider RTL, rather than the different working-tree core. All 29
digital root reset bits are defined. With first reference rise at 20 ns,
40 ns reference period and external reset release at 5 ns, oscillator reset
releases at 180 ns with coarse 20/fine 111, even while PLL_ENABLE is low.
PLLOUT is held constant in this controller-only reference; actual analog
startup and the complete ready handshake are not simulated. An 80 ns
full-macro cold-start pilot under these inputs would stop before oscillator
release. This controller observation does not change the isolated DCO pilot.
`prototype_reset_observation.py` adds a diagnostic midrail comparison of
frozen reset bits to captured native DC values, rejecting missing, wrong or
indeterminate bits. Three focused controls pass after the 799-test regression.
`_selected_context_clock_wire_reset_comparison_019` waits for the current
native DC result before performing that comparison. It neither assumes the
analog PLLOUT reset voltage nor qualifies noise margins or transient behavior.

`_frozen_programmed_pre_release_reference_019` extends the frozen-controller
reference to the 175 ns pre-release state and checks both constant PLLOUT
levels. They agree on every observed bit and the 180 ns oscillator-reset
release (first ideal reference rise at 20 ns, reset release at 5 ns).
`prototype_native_transient_snapshot.py` streams one complete real ASCII
transient plot, checks all samples, indices, finite values and interval
coverage, and records final values plus observed trailing-window spans.
Three focused controls pass. `_transient_snapshot_native_control_019`
validates the reader on an actual stock-ngspice RC waveform; a separate
named-node control checks explicit root-bus and hierarchical node saves.
These controls do not qualify waveform convergence or checkpoint reuse.

`_selected_context_clock_wire_programming_pilot_019` is prepared and queued
behind the successful current-model DC/reset comparison. It preserves the
complete current model and changes only the external REFCLK and RESET_N
sources: reference ramps start at 20 ns with 100 ps rise/fall and 40 ns
period; reset ramps from 5 to 5.1 ns. Other programming inputs remain static,
with PLL_ENABLE low. The experiment ends at 175 ns and requests all 25,734
non-ground source-graph node voltages. Its 1 ns maximum step is diagnostic,
not the profile's frequency-measurement step. It checks the pre-release
logic vector and captured DCO reset samples, records all physical node
voltages, and uses no internal voltage clamps or invented aggressor values.
Snapshot reuse has not been validated. Oscillation,
hazards, convergence and the complete ready handshake remain unqualified.
The case has a three-hour local cap and a 900-second assessment reserve,
within the original checkpoint deadline and single-large-transient policy.

`_FOM_native_scope_control_019` generated four small GDS extraction fixtures
with identical metal/pin geometry: empty, alternate FOM (65/99), canonical
FOM (23/28), and a drawing-poly positive control. All native extractions
completed; initial postprocessing rejected Magic's inline `$ **FLOATING`
comment on the positive-control capacitor. `_FOM_native_scope_review_019`
reuses those outputs with correct inline-comment parsing and independently
checks the fixture geometry. Both FOM purposes import as `fomfill` and give
identical operators. Each metal-to-SUB capacitor changes from 0.7103 fF to
0.59429 fF; inter-metal coupling remains 0.2816 fF. FOM creates a zero-self-C
node in the native .ext file, without an added SPICE primitive. The poly
positive control introduces explicit floating-node coupling. These are
measured native extractor behaviors, not a bound on real physical FOM error.

`_selected_context_clock_wire_FOM_geometry_review_019` independently verifies
that all manufacturing FOM geometry, for both recognized purpose codes,
survives exactly in the margin-10 and margin-20 views. Their completed native
extractions bind those actual view files and the same pinned technology and
`ngspice()` style used by the controls. Thus FOM is not wholly absent from
native extraction: the native model includes its geometry-dependent effect.
No remapping, model change or physical-accuracy qualification is performed.
The physical FOM coverage/accuracy flags remain false, and synthetic controls
are not promoted to release evidence.

The isolated `_selected_oscillator_schur_TT_driver_DC_019` reference completed
its full 80 ns native run with ordinary DC initialization. Its independently
recorded all-cycle assessment covers 21 complete cycles between 20 and 80 ns:
average 369.1642199 MHz, observed cycle frequencies 369.0484995–369.2308071 MHz
at TT, 1.8 V, 27 C, coarse 20/fine 111. The two fixed supply rails average
4.026024 mW over that observation interval. This is an isolated driver-anchor
diagnostic with incomplete final parent loading; numerical convergence,
all-corner code coverage and macro power remain unqualified. The result does
not establish 400 MHz operation or justify a new startup code. The existing
current clock-corridor assembled DC controller started after this native
process exited, retaining its original deadline and pinned inputs. All
release flags remain false.

`_native_affinity_enforcement_019` records a runtime resource-control repair.
The current native DC process and its three validation controllers allowed
CPUs 0–63; `OMP_NUM_THREADS=1` alone does not cap ngspice's runtime thread
request because its setup code defaults to two threads. All existing tasks
of these verified processes were restricted to CPU 0. New worker children
of the queued controllers inherit that affinity. This enforces their
one-CPU leases within the allowed 0–31 subset without restarting analyses,
changing pinned files or extending deadlines. It is a scheduling constraint,
not a multithread consistency or performance qualification.

The current clock-corridor assembled DC check completed with 210,617 finite
native variables and the prescribed supplies recovered. Native initialization
reported a singular node and successfully completed its automatic dynamic
gmin stepping; no deck gmin/shunt modification was introduced. The strict
frozen-RTL comparison matches all 29 defined digital reset bits, with minimum
distance 0.89999785 V from the diagnostic 0.9 V midpoint. This is a reset-state
check, not noise-margin or transient qualification. The prepared full-model
175 ns programming pilot then started under its existing local and original
whole-check deadlines. Its native child inherited CPU-0 affinity. All
release and loaded-model qualification flags remain false.

`_explicit_thread_consistency_control_019` reuses the preserved 834-device
literal-parameter fixtures with explicit runtime `num_threads` values 1 and
4, matching OpenMP thread limits, and the unchanged stock native binary.
All captured native values match exactly at 15 paired operating points
(five corners, three input biases), including 12,510 individual primitive
current observations. The small fixtures run sequentially under a four-CPU
lease on CPUs 1–4 while the large programming pilot remains on CPU 0. This
control establishes only these fixture operating-point comparisons; no
representative transient speedup or multithreaded loaded-model qualification
is claimed, and no running or queued large-case setting is changed.

The one-thread programming pilot reached 60.1264 ns before its planned
9,900-second native budget expired (10,800-second case cap less the
900-second assessment reserve). Its worker traceback reports TimeoutError;
no complete 175 ns raw waveform or successful programming assessment exists.
`_selected_context_clock_wire_programming_threads4_019/prior_stop_review.json`
records the terminal process and preserved outputs. This is a runtime-limit
result, not a demonstrated circuit failure or a validated partial snapshot.

The explicit four-thread successor uses the same stock binary, full model,
stimuli, save vectors, 175 ns endpoint and 1 ns diagnostic maximum step.
Its deck is checked identical to the previous deck after normalizing output
paths; only runtime thread selection and output paths change. It starts
after the previous native process has exited, uses a four-CPU/48 GiB lease
on CPUs 0–3, and retains the original whole-check deadline, local case cap
and assessment reserve. The five-corner operating-point thread control is
a prerequisite, but transient thread consistency and representative speedup
remain unproven. This is a single diagnostic follow-up, with no automatic
identical retry and no change to the release criteria or qualification flags.

The explicit four-thread programming pilot also exhausted its planned
9,900-second native budget, reaching a last reported 60.3823 ns of 175 ns.
Its native process exited and the worker reports the budget TimeoutError.
`_selected_context_clock_wire_programming_threads4_019/stop_review.json`
binds the preserved terminal logs and preparation receipts. No completed
waveform assessment exists, and this runtime-limit result establishes
neither circuit failure nor programming, transient-consistency or model
qualification. No identical retry is launched, the original deadline remains
unchanged, and all five release gates remain open.

The selected 019 timing reports now have independent path classifications:
`_selected_402p1_path_classification_019` retains all 299 reported samples,
including ten decision-data hold violations and five first-stage reset
synchronizer aperture violations. All ten decision-data paths terminate at
`core.gen_registered_decision.decision_q`; their source is the two-bit
`core.bbpd_decision` state. The already completed proof-bound enabled-phase
screens have a separate replay in `_selected_402p1_phase_path_classification_019`:
all 299 reported samples are retained and its only negative samples are five
first-stage apertures. These reports are sampled, not exhaustive endpoint
inventories. The conditional phase experiment does not qualify startup,
capture disable/reset, metastability resolution, actual oscillator frequency
coverage or the digital gate, and no timing exceptions or physical ECOs are
generated from these classifications.

### Stock Xyce backend trial (2026-11-03)

`prototype_v3_Xyce_compatibility_020/assessment.json` records a completed
trial of the existing stock Xyce 7.10 MPI installation in the pinned modern
container, separate from the older experimental solver binaries. The complete
834-device fixture fails on four pinned level-3 diode instances. A clearly
scoped 830-device subset retains 826 MOS and four poly-resistor instances
while omitting those diodes. At five corners and three input biases, one
and four MPI ranks give exactly equal subset outputs. The maximum MOS
current difference normalized with a 1 nA denominator floor is 2.3782296e-08;
the resistor difference reaches 12.905600%. Stock Xyce reports ignored
DW, TC1R and TC2R resistor parameters, and substitutes BSIM4 4.6.1 for the
PDK-requested 4.5. It also reports a sidewall-potential clamp.

Five paired native 4 ns MOS-inverter transients use identical drawn device
geometries, 10 fF external load, 1 ps maximum step and nominal 27 C/1.8 V.
All four output crossings are retained per corner; the largest paired edge
difference is 0.818481 ps. These are small compatibility controls,
not loaded oscillator or whole-circuit qualification. The fixture runtimes
are dominated by parsing and startup and establish no representative
full-circuit speedup. A larger performance trial requires first addressing
the diode and resistor compatibility defects and checking the affected
dynamic behavior. No PDK model, manufacturing artifact, release criterion
or existing deadline is changed, and Xyce is not adopted as a release backend.

### XDM translation trial (2026-11-03)

`prototype_v3_XDM_translation_trial_021/assessment.json` records actual XDM
2.7.0 HSPICE and T-Spice translation probes, including automatic include
translation and inline model controls. XDM has no ngspice input mode. The
input resistor statement and diode model are copied from the pinned PDK;
the self-contained probes use explicitly diagnostic parameter contexts.
The inline resistor control normalizes only the HSA expression quoting.
All translation processes return zero, but the translated HSPICE resistor
loses TC1R, TC2R and DW; its native current differs from the matching ngspice
probe by 9.362818% at 0.9 V. T-Spice loses additional geometry/model fields.
Both translated inline diode decks fail in stock Xyce after the diode model
is omitted or commented out. Translation exit status is therefore not an
electrical compatibility certificate.

The isolated XDM build is pinned in `build/tools/XDM_001/manifest.json` with
source commit and downloaded dependency hashes. Only a modern-compiler
portability patch (sstream include and std::isnan qualification) is applied
to XDM; conversion rules, the PDK and Xyce are unchanged. No system packages
are installed. The trials do not establish full-model compatibility or a
PLL performance improvement, and all release flags remain false.

### Explicit Xyce device adapters

`prototype_xyce_resistor_translation.py` preserves the pinned ngspice poly
resistor geometry equation using explicit resistance, avoiding Xyce's
different NARROW semantics. TC1R/TC2R become supported TC1/TC2 parameters
with TNOM=30 C. Its native 022 comparison covers both actual geometries at
five corners and three input biases; the largest relative current difference
is 3.97e-16. The geometry-limited diode adapter reuses the existing fixed-27-C
translation and preserves corner capacitance multipliers. Five adapter
controls pass. The 023 native fixture now retains all 834 primitives; one
and four MPI ranks give identical outputs at all five corners. Diode DC
current differences are at most 4.30e-6 relative in the sampled fixture.

Dynamic qualification remains failed. The 024 diode test reaches a timestep
collapse at the first ramp with overly tight transient tolerances. The
separate 025 successor changes only transient tolerances to the earlier
comparison settings and reuses DC/AC outputs and saved ngspice transients.
Subsequent endpoint review finds both stock simulators incomplete. It
advances through the reverse-bias ramps but fails during the forward-bias
ramp near 1.712 ns, before the required 3 ns endpoint. Both failures and
partial outputs are retained. Neither tolerance relaxation nor passing DC
comparisons qualify the diode dynamics or permit full-PLL backend adoption.
No simulator or PDK source has been changed by these adapters.

### Shared diode sidewall charge discontinuity and isolated correction

The 027 source/waveform review identifies a defect shared by the pinned
ngspice-47 and stock Xyce-7.10 diode implementations: the forward sidewall
charge branch uses the bottom junction's charge offset. Their different
potentials and grading coefficients imply a 0.318754 V offset mismatch per
unit sidewall capacitance at the 0.1 V junction transition, or 3.03e-17 C
for perimeter 2.64 um with unit corner multiplier. All 20 saved stock native
terminal waveforms stop near that transition; inferred junction voltages
are within 1.39e-6 V using terminal current and series resistance. This is
not a claim that the final failed internal state is converged. Stock
ngspice reports a transient abort despite process exit zero, so its saved
forward transient is not a completed golden reference.

The isolated Xyce correction changes the normal and analytic-sensitivity
sidewall charge offsets to their own potential/grading/transition integral.
The rebuilt library differs in exactly N_DEV_Diode.C.o. A separately built
ngspice reference applies the same physical continuity requirement, with
only dioload.o changed. Stock executables and the PDK remain untouched.
Three independent mathematical controls check charge continuity, charge
derivative versus capacitance on both sides, and rejection of the original
shared-offset defect; with the adapter tests, eight focused controls pass.

`prototype_v3_diode_charge_fix_controls_026/completed_review.json` independently
reviews all ten corrected native geometry/corner cases after the producer
misidentified Xyce AC output filenames. No simulations are repeated for
that reader fix. Both corrected simulators reach 3 ns in every case. All
existing sampled comparison limits pass: maximum DC relative error with
1 pA denominator floor is 5.400e-4, AC complex-current relative error
4.863e-10, and integrated transient-current relative error 1.535e-4. This
fixed-27-C comparison includes forward and reverse transitions but is not
noise, statistical, universal model or full-PLL qualification.

The separate 028 assembled DC benchmark retains all 62,450 physical
primitives and 6,054 wire resistors, opening only the 1,269,218 constant
capacitors for DC as in the preserved ngspice baseline. It uses explicit
resistor/diode adapters and the isolated corrected MPI Xyce binary, with
one large case at a time, a four-CPU/48-GiB lease, and a 600-second cap per
MPI configuration (one and four ranks). This new diagnostic trial does not
modify the original checkpoint deadline or establish transient speedup.
All release and backend-adoption flags remain false.

The assembled 028 DC benchmark is complete: one MPI rank takes 152.799 s
and four ranks take 67.691 s, a measured 2.257x elapsed-time improvement
for this paired DC test. Both cases match all 29 defined frozen-RTL reset
bits against the preserved ngspice DC observations. This does not measure
full-capacitance transient performance or qualify all internal analog states.

`prototype_v3_Xyce_snapshot_format_control_029` verifies root bus and physical
internal-node capture through Xyce ASCII RAW output and the unchanged strict
streaming snapshot reader. The tested configuration uses an explicit PRINT
FILE, FORMAT=RAW and no -o override. Although the deck requests PRECISION=17,
Xyce 7.10's TimeRawAscii writer hardcodes eight digits after the decimal in
scientific notation. The passing reader control does not prove that the
requested precision is honored. Comparisons below concern the saved values;
the strict reader must still reject rounded duplicate times.

The separate 030 full-C programming diagnostic retains all 62,450 physical
primitives, 6,054 wire resistors and exactly the original 1,269,218 capacitor
statements, including signed values and order (capacitor-card SHA256
a6bbe3664b99994702b26d99e857316f2f71a27305387aa998c62ff67001135c).
It preserves the previous REFCLK/RESET_N waveforms and all static inputs,
uses the checked device adapters and isolated diode-charge correction, and
captures all 25,734 physical voltage vectors. Ordinary native DC startup,
the 175 ns endpoint and the diagnostic 1 ns maximum step remain. The single
large case uses four MPI ranks under a four-CPU/48-GiB lease, with a new
3,600-second diagnostic cap including a 300-second assessment reserve. It
does not restart the old checkpoint or change its deadline. Completed
waveform, frozen-RTL sequence, reset-held-low and strict endpoint checks
remain required; no warm restart, frequency, loaded-model or release
qualification is inferred from launch or DC performance.

The 030 full-C Xyce run is terminal: its 3,300-second native budget expired
after DC initialization and entry into transient analysis. Last logged
progress is 10.8859%, approximately 19.05 ns of 175 ns; this is a rounded
progress-log observation. The 128,434,572-byte partial RAW file and all
inputs/logs are retained and hashed in `stop_review.json`. The MPI controller
and all four known workers are gone. No completed snapshot or programming
assessment exists, no full-C transient speedup is established, and no
automatic identical retry is launched. The passing isolated device controls
and assembled DC benchmark retain their narrower scopes.

### 2026-11-03 — UMFPACK simulation backend; full programming validation pending

The original 030 progress log understated its final simulation time: direct
inspection finds partial RAW point starts through approximately 20.38 ns,
past the first reference edge. This remains an incomplete waveform, not a
completed programming assessment.

The unchanged full-C, four-rank KLU prefix in
`prototype_v3_Xyce_full_C_timing_profile_033` spends 86% of transient wall time
in linear solving. A captured first-transient matrix has 211,431 unknowns and
3,634,364 stored entries. Offline UMFPACK is 2.75 times faster than KLU on that
matrix and passes original-equation residual and native-solution checks.
Four- and sixteen-thread Basker are slower than KLU on the same matrix;
increasing thread count alone does not solve this workload's bottleneck.

`prototype_v3_Xyce_full_C_UMFPACK_profile_051` validates the integrated MPI
adapter on the original 32-step prefix: native elapsed time decreases from
891.488 to 493.769 seconds, a 1.805 times total speedup. Transient stepping
decreases from 247.641 to 126.751 seconds, a 1.954 times speedup. All 33 saved
times match, and all 25,734 saved physical-node voltages differ by at most
1.00000002e-8 V. The circuit, signed capacitor statements, source waveforms,
tolerances and diagnostic maximum step are preserved. This establishes a
prefix improvement, not full-programming, frequency or release qualification.

The reproducible implementation is in
[tools/xyce_umfpack](../../tools/xyce_umfpack). Its builder starts from the
image's stock archive, applies the previously checked diode correction, and
adds an explicit `-linsolv umfpack` backend. Only `N_DEV_Diode.C.o` and
`N_LAS_TranSolverFactory.C.o` change; all other archive members remain identical.
The repository rebuild is byte-identical to the binary used in 051/052
(SHA256 `63651569cb97c9a994adfd685976b059056751c93c3f225d87dcc79e4549c79f`).
The checked stock simulator and PDK are not modified.

From the repository root, using fresh output directories:

```sh
apptainer exec --cleanenv --bind "$PWD:$PWD" build/apptainer/openpll-release-modern.sif \
  python3 tools/xyce_umfpack/build.py --output build/tools/xyce_umfpack_local_001 --cpus 16,17
apptainer exec --cleanenv --bind "$PWD:$PWD" build/apptainer/openpll-release-modern.sif \
  python3 tools/xyce_umfpack/check.py --binary build/tools/xyce_umfpack_local_001/Xyce \
  --output build/signoff400/xyce_umfpack_local_controls_001 --cpus 4,5,6,7
apptainer exec --cleanenv --bind "$PWD:$PWD" build/apptainer/openpll-release-modern.sif \
  python3 tools/xyce_umfpack/run.py --binary build/tools/xyce_umfpack_local_001/Xyce \
  --deck path/to/xyce-compatible.spice --log build/signoff400/my_case/native.log --ranks 4
```

The self-contained control compares KLU, serial UMFPACK and four-rank UMFPACK
through a nonlinear diode transient and connected RC ladder. It checks every
ladder voltage and the source current. The launcher preserves deck/output
directives, binds the process group to the selected CPU set, uses one BLAS
thread per rank, and retains native process identity and a time cap. A zero
native exit remains separate from waveform validation.

`prototype_v3_Xyce_full_C_UMFPACK_programming_052` ran the unchanged
175 ns full-C programming diagnostic after passing the prefix speed/accuracy
checks. It exhausted its separate 7,200-second native cap at approximately
61.475 ns (last fully delimited saved point), without qualification. The old
checkpoint deadline was not modified. A completed endpoint, finite physical-node inventory, frozen-RTL
programming bits and oscillator-reset observations remain required. The
diagnostic 1 ns maximum step does not qualify numerical convergence, loaded
oscillation, the ready handshake or any release gate. All release flags remain
false.

The experimental checked-reuse backend remains separate from the reproducible
fresh-factorization tools above. It refines reused UMFPACK factors against the
current matrix and RHS, falls back to fresh factorization on failed checks, and
disables reuse during DC initialization. The changed-matrix probe `062` passed;
native nonlinear controls `063` completed with matching waveforms and zero DC
reuse. Neither result establishes full-PLL performance or accuracy.

The queued 21 ns full-C clock-prefix trial `064` waits for the identified `052`
owner to exit. Its conditional 175 ns successor `065` waits for `064` and requires
normal prefix completion, all 25,734 physical voltage vectors over the first 300
reference samples to agree within 1 microvolt with matching saved time grids,
zero DC reuse, and a conservative speedup lower bound of at least 1.5. It then
checks the complete 175 ns waveform, programming bits and reset observations.
The full successor has a separate 7,200-second native cap. Large native circuit
cases run sequentially; waiting controllers reserve no simulation cores or RAM.
The experimental backend is not adopted for release and the speed goal remains
unproven until a representative complete run has been assessed.

The experimental backend is reproducible from repository sources with explicit
`--experimental-checked-reuse` on each of `build.py`, `check.py` and `run.py`.
For example, inside the same pinned CAD image:

```sh
python3 tools/xyce_umfpack/build.py --experimental-checked-reuse --output build/tools/my_checked_reuse --cpus 16,17
python3 tools/xyce_umfpack/check.py --experimental-checked-reuse --binary build/tools/my_checked_reuse/Xyce --output build/signoff400/my_checked_reuse_controls --cpus 16,17,18,19
```

The stock-image rebuild in `xyce_umfpack_checked_reuse_reproducible_001` is byte
identical to the candidate used by `063` and queued trials `064`/`065`. The
reproducible controls `066` compare KLU, fresh UMFPACK and checked reuse, including
one- and four-rank reuse runs. They require actual reuse hits and zero DC reuse.
Launcher control `067` independently verifies the complete saved waveform against
KLU. These remain small backend controls; they do not prove full-PLL speed.
Without the explicit option all three commands retain fresh-factorization mode.

Trial `052` has stopped; `064` started after its identified controller exited.
The stop review confirms zero surviving `052` native workers and four `064`
workers. The full successor `065` continues to wait for a passing `064` result.

`tools/xyce_umfpack/compare_prefix.py` compares a specified number of fully read
saved samples from ASCII RAW files, including interrupted or live waveforms.
It checks ordered matching variable inventories, finite values, consecutive
indices and strictly increasing times from zero. It compares saved grids without
interpolation and reports no value agreement when grids exceed the time tolerance.
It rejects an incomplete requested prefix and never claims simulation completion.
For the PLL, all compared vectors are voltages; the default value tolerance is
1 microvolt. Mixed vector types require an appropriate explicit tolerance.
The 300-point KLU/fresh-UMFPACK comparison reproduced the existing 10 nV bound;
requesting a 34th point from the complete 33-point profile was correctly rejected.

The separate six-correction policy experiment `068` retains the same residual,
correction and contraction checks but removes the 5% row-change prefilter and
allows up to six corrections before fresh fallback. All seven manufactured
changed-matrix cases passed. At a 0.005 branch-stamp perturbation, it accepted
reuse in 0.243 s versus 1.019 s fresh; the three-correction policy had fallen back.
This remains a manufactured sequence, not a captured Newton sequence.

Private build `Xyce_MPI_UMFPACK_checked_reuse_002` adds periodic counters so a
bounded native run retains reuse observations even when interrupted by its cap.
Nonlinear controls `069` passed with zero DC reuse, up to 4.4e-15 V difference,
and 2,784 reuse hits in the four-rank run. Fallback prefix `070` waits for the
identified full-trial `065` owner. It launches only if that predecessor stops
without qualification; a completed predecessor suppresses the extra native run.
It uses the same 21 ns waveform/speed screening as `064`. The running `064`,
queued `065`, and public experimental build policy remain unchanged.

Full fallback controller `071` waits for `070` and requires its complete passing
accuracy/speed screen before launching the unchanged 175 ns diagnostic with the
six-correction backend. It checks reuse was exercised, every reported DC reuse
count is zero, all programming bits and reset observations, and an additional
1,500-sample saved-grid/voltage comparison against the stopped fresh-backend
`052` waveform. Its bounded queue covers the predecessor's existing whole cap;
its own native cap remains 7,200 seconds. No predecessor deadline is extended.

Trial `064` was deliberately stopped by the agent after 1,704 seconds: even an
immediate completion could no longer satisfy its predeclared conservative
`2450 / elapsed >= 1.5` speed screen. This is a screen result, not a measured
upper bound on actual speedup against an unfinished baseline. The first 300
samples still agreed with fresh UMFPACK within 10 nV on identical saved times.
`requested_stop.json` records this decision; the resulting `KeyboardInterrupt`
was not a user cancellation. Its conditional full run `065` did not launch.
The stop review verifies zero surviving `064` workers and four revised-policy
`070` workers. Trial `070` is now live; `071` remains conditional and queued.

Runtime analysis now records cumulative `umfpack_progress_snapshots`, the latest
snapshot, and separate terminal adapter-instance counters. It never sums
cumulative snapshots or infers full transient completion from a log. Trial `070`
reported only 12 accepted cached solves in its first 400 calls, with 1,498
refinement corrections: stationary refinement still falls back frequently.

The next private candidate uses weighted, left-preconditioned GMRES with at most
12 basis vectors, retaining old UMFPACK factors only as a preconditioner. Every
operator application uses the current matrix. Independent current-equation
residual and correction checks decide acceptance; failure uses fresh UMFPACK.
Probe `072` passed all seven changed-matrix comparisons, including numerical
fallback at the largest change; the 0.2 branch perturbation took 0.466 s versus
1.078 s fresh. Native controls `073` agreed electrically, but the original
post-solve contraction rule rejected many already-small corrections.

Candidate `Xyce_MPI_UMFPACK_checked_reuse_004` therefore requires two successive
post-GMRES current-equation corrections below 0.01 of the original correction
threshold, with componentwise backward error <=1e-13. The correction threshold
is 1e-12 absolute plus 1e-10 relative; this replaces a contraction ratio at
roundoff with two corrections 100 times below that threshold. It is not a
universal forward-error bound for ill-conditioned matrices. Probe `074` passed
all seven cases with large-change fallback. Native controls `075` passed all
2,881 saved samples: four-rank reuse needed 65 fresh factorizations out of 2,907
solves, with zero DC reuse and maximum voltage difference 2.8e-15 V from KLU.

Krylov prefix `076` waits for the identified `071` owner, skips the extra native
case if that full predecessor completed, and otherwise applies the same 21 ns
accuracy/speed screen. Its full successor `077` waits for a passing prefix and
uses the same 175 ns endpoint, programming/reset checks and 1,500-sample fresh
backend comparison as `071`. Only one full native circuit runs at a time.
Neither Krylov candidate is adopted; extracted-PLL speed remains unproven.

The tested Krylov candidate is now reproducible with the public builder:

```sh
python3 tools/xyce_umfpack/build.py --experimental-checked-reuse --reuse-policy krylov --output build/tools/my_krylov --cpus 16,17
python3 tools/xyce_umfpack/check.py --experimental-checked-reuse --binary build/tools/my_krylov/Xyce --output build/signoff400/my_krylov_controls --cpus 16,17,18,19
```

Run these inside the pinned CAD image, with fresh output directories. The
existing launcher's `--experimental-checked-reuse` selects the reuse backend in
that binary. `xyce_umfpack_Krylov_reproducible_001` is byte identical to the
candidate tested by `075` and queued in `076`/`077` (SHA256
`19bfa2d1863508c18d3e452a261e31d82015b3704a9201fe395839c2b9017175`).
The builder's default remains fresh UMFPACK; the conservative experimental
policy remains selectable independently. No release qualification is granted.

Stationary trial `070` was deliberately stopped at 1,648 seconds when its
predeclared conservative speed screen became unreachable. Its first 200 samples
passed within 10 nV on identical saved times, but the last counter snapshot had
661 fresh factorizations out of 700 calls. Its conditional full successor `071`
did not launch. `requested_stop.json` records the agent's performance decision;
the resulting interrupt was not a user cancellation. The stop review confirms
zero surviving stationary workers and four live Krylov `076` workers. Trial `076`
is now running; full successor `077` remains conditional and queued.

Krylov trial `076` passed its first 33 samples within 10 pV, but only 12 of the
first 300 calls reused factors. The agent deliberately stopped it at 799 seconds
to prioritize diagnosis, rather than finishing another slow prefix. This was
not a completed speed-screen result or user cancellation. Its full successor
`077` did not launch. The stop review verifies all old workers exited before the
four-worker diagnostic `078` began.

Diagnostic `078` uses an isolated instrumented copy of candidate `004`. It saves
one actual rejected transient system after call 180: shared CSC graph, previous
factor matrix values, current values, native RHS, rejected proposal and the fresh
solution. It still returns the same fresh solution on rejection. The 32-step
native diagnostic has a separate 900-second cap and requires a complete waveform
comparison. The capture is intended to distinguish slow iterative convergence
from acceptance criteria that fresh native solutions cannot meet. No numerical
or electrical tolerance has been changed, and full-goal completion remains false.

Offline review `079` waits for completed capture `078`, verifies its digest and
binary dimensions, and checks the native fresh and rejected solutions against
the exact captured current equations using long-double accumulation. It reports
proposal differences under native and cached correction scales for all MNA
unknowns. These are Newton-correction diagnostics, not physical voltage waveform
qualification. The offline review uses one spare CPU and no additional native
circuit case.

Capture `078` and review `079` completed. In the actual 211,431-row Newton system,
the rejected proposal differed from the native fresh solution by at most
7.04e-20, and its maximum absolute equation residual was 3.98e-23. It nonetheless
failed the purely relative 1e-13 componentwise residual check in 44 rows (maximum
relative error 2.79e-12). The fresh result passed that check. This identifies
oversolving of tiny Newton corrections in this captured case, rather than a
large proposal error; it does not characterize every rejected solve.

The mixed check tested by `080` is:

```
abs(b - A*x) <= 1e-13*(abs(b) + abs(A)*abs(x)) + 1e-16*row_sum(abs(A))
```

It retains the relative term and adds an absolute correction floor, mapped to
equation units by each current matrix row. It keeps two independent post-GMRES
correction checks. Replay `081` of the actual captured system reused factors in
0.399 s versus 1.146 s fresh, with maximum difference 7.62e-17 from the captured
native fresh result. This is an offline linear-solve timing, not full-circuit
speed. All seven changed-matrix cases in `082`, including large-change fallback,
and the native nonlinear controls `083` passed.

Private mixed-residual build `Xyce_MPI_UMFPACK_mixed_residual_006` is now running
21 ns full-circuit prefix `084`, preserving device models, capacitances, stimuli
and nonlinear/integration tolerances. Full successor `085` requires its passing
waveform/speed screen and adds the complete 175 ns waveform, programming/reset
checks and 1,500-sample baseline comparison. Its fresh measurement cap is 10,800
seconds; this does not extend any predecessor deadline or establish a practical
runtime claim. The completed runtime and accuracy evidence remain required.

The mixed-residual candidate is reproducible through the same public builder:

```sh
python3 tools/xyce_umfpack/build.py --experimental-checked-reuse --reuse-policy krylov-mixed --output build/tools/my_mixed_backend --cpus 16,17
```

The repository rebuild `xyce_umfpack_mixed_reproducible_001` is byte identical to
live candidate `006` (SHA256
`db782505ff6f1ec1914b52acc5e9053ce2df641e46df4f267c76471ebcfb1b88`).
Use the existing `--experimental-checked-reuse` options for control checks and
launching. Native controls `083` used 46 fresh factorizations in 2,907 calls,
with zero DC reuse and maximum voltage difference 1.03e-12 V from KLU.
Full extracted-PLL performance and waveform checks remain pending.

The live mixed-residual trial `084` has accepted 138 cached solves in its first
300 calls (previous strict-relative Krylov trial: 12). Its first 100 complete
samples agree with fresh UMFPACK within 10 nV on identical saved times, including
all 25,734 physical voltage vectors. These observations support the correction
of the residual gate; the 21 ns speed screen and full 175 ns run remain pending.

The public control runner supports `--extra-ranks 8|16|32` with that many CPU IDs.
It retains the serial/four-rank controls and adds the requested fresh/reuse MPI
cases. Sixteen-rank control `086` passed with zero DC reuse, voltage difference
<=1.03e-12 V, and saved time difference <=2.2e-21 s. This validates compatibility,
not extracted-PLL scaling.

Scaling prefix `087` waits for the identified four-rank full-run `085` owner.
It suppresses the extra native case if that full run completes within the
provisional two-hour practical target. Otherwise it runs the same 21 ns screen
on sixteen cores with a 64 GiB reservation. Where `084` has a completed timing,
it additionally requires at least 1.1x speedup over that four-rank prefix before
full successor `088` can launch. The successor retains endpoint, programming,
reset and 1,500-sample baseline checks, with a separate 10,800-second native cap.
Only one full native circuit runs at a time.

Mixed trial `084` has passed its first 300 complete saved samples through
20.3721959 ns: all 25,734 physical voltages agree within 10 nV on identical saved
times. Its first 800 calls include 596 reuse hits. Full prefix timing and the
complete 175 ns result remain unproven.

Four-rank prefix `084` completed normally through 21.0029618 ns in 1,928.79 s.
It reused 1,057 of 1,140 transient solves and reported zero DC reuse. The
conservative speedup lower bound against the fresh-UMFPACK run is 1.2702, below
its 1.5 screen, so full `085` did not launch. Independent comparison of all 494
saved samples against the stopped fresh reference passed within 10 nV, with
identical times across all 25,734 physical voltages.

The completed transient profile reports 991.03 s linear solution time (63.9%),
381.86 s residual loading and 136.15 s Jacobian loading (33.4% combined), out of
1,551.94 s transient stepping. This supports measuring additional MPI ranks.
Trial `087` is now live on sixteen cores. Its handoff review verifies zero old
four-rank workers and sixteen new workers; full successor `088` remains queued.
The complete 175 ns result and practical full-run speed remain unproven.

The first 200 sixteen-rank samples from `087` agree with the four-rank waveform
within 10 nV on identical saved times. Resource review confirms sixteen workers
on CPUs 0–15 within the 64 GiB reservation. Scaling remains unproven.

Captured-system kernel profile `089` motivated testing row-oriented storage.
Its residual counter includes one post-timing diagnostic evaluation, so that
field must not be summed as an exact solve-time breakdown. CSR replay `090`
measures matrix refresh plus solving: three runs were 1.46–1.54x faster than the
column-oriented baseline, with bit-identical solutions. Each row retains its
original ascending-column summation order; UMFPACK still receives the same CSC
matrix. Seven changed-matrix cases `093` passed, including fresh fallback.
Threaded prototype `091` also retained bit-identical solutions, but did not show
a reliable improvement over serial CSR and was not selected. Equal-row work
blocks are imbalanced in this graph (maximum nonzero fractions 44%, 40%, 39%
for 4, 8, 16 blocks respectively).

`rank_exec.py` pins each single-host OpenMPI rank to its selected CPU before
executing the simulator. Both public `run.py` and `check.py` now accept
`--pin-ranks`. Probe `092` verifies affinity survives MPI initialization. It also
confirms the pinned MPI library supports `OMPI_MPI_THREAD_LEVEL=1`; no application
threads are enabled in the selected CSR backend. Pinned native controls `094`
passed through sixteen ranks with <=1.03e-12 V voltage difference and zero DC
reuse. Prefix `095` and full successor `096` are queued behind the current
scaling attempt; they use serial CSR kernels and individually pinned ranks.

The CSR binary is reproducible inside the pinned image with:

```sh
python3 tools/xyce_umfpack/build.py --experimental-checked-reuse --reuse-policy krylov-csr --output build/tools/my_csr --cpus 16,17
```

`xyce_umfpack_CSR_reproducible_001` is byte identical to tested candidate `007`
(SHA256 `1b9b4c4b2f5281a6c0c68c18d88d77a41f4f8747b250159b9e7e93548ff18989`).
No extracted-PLL CSR speedup or complete 175 ns result is established yet.

Unbound sixteen-rank prefix `087` completed in 1,970.03 s versus four-rank
1,928.79 s (0.9791x scaling). Its accuracy screen passed, but neither the speed
nor scaling gate passed, so full `088` did not launch. Transient residual loading
was 409.70 s (four ranks: 381.86), Jacobian loading 103.77 s (136.15), and linear
solution 1,044.75 s (991.03). Additional MPI ranks alone did not help this case.

CSR/pinned prefix `095` is now live. Its handoff audit verifies zero old workers
and each of sixteen new ranks confined to its assigned CPU 0–15. Full successor
`096` remains conditional on complete prefix accuracy/speed checks. Full 175 ns
completion and practical runtime are still unproven.

Full-duration measurement fallback `098` distinguishes the experiment-entry gate
from goal completion. The previous 1.5x screen uses only a conservative lower
bound from an unfinished fresh baseline. If strict full controller `096` exits
without ever launching a native worker, `098` can launch the first full 175 ns
measurement after a complete passing electrical prefix and measured >=1.1x
improvement over the completed four-rank mixed prefix. It also pins that completed
baseline assessment and the prefix assessment used for authorization.

It skips an already completed full predecessor and refuses to retry if any
native full attempt was started. All full endpoint, finite-node inventory,
programming/reset, 1,500-sample waveform comparison, device/parasitic inputs and
nonlinear/integration tolerance requirements remain. Its new native cap is
10,800 seconds. This entry rule is not a practical-runtime acceptance rule or a
claim that the speed goal has been achieved. No predecessor deadline is extended.

Distribution review `100` identifies an important default-layout concern. The
pinned Xyce default distributor fills contiguous flat-device-count blocks,
starting with processor 1. This model lists 62,450 physical primitive wrappers
before the first of 1,269,218 literal capacitors. The conservative per-rank block
size at sixteen ranks is 83,607, so the leading MOS-heavy physical block fits
one rank. This is a source/deck-order inference, not an observed per-rank device
count. The source hashes are retained with the review.

Xyce's built-in `.options DIST STRATEGY=2` instead balances counts separately by
device type. Hierarchical MOS/diode/RC controls `099` passed through sixteen
pinned ranks with maximum voltage difference 3.8e-15 V from KLU. The public
control runner exposes `--distribution-strategy 2 --hierarchical-mos`; the actual
simulation launcher preserves its supplied deck, so include the DIST option in
that deck explicitly.

The agent stopped unbalanced CSR prefix `095` after preserving 300 complete
samples, all bit-identical to the preceding sixteen-rank waveform. Its idle full
controllers `096` and `098` were deferred before any native full run. Balanced
prefix `101` is now live with the same CSR binary, sixteen individually pinned
ranks and the DIST option. Its handoff audit confirms zero old workers.

Full successor `102` includes the same DIST option and retains the complete
175 ns, finite-node inventory, programming/reset and 1,500-sample reference
checks. Its entry gate is complete prefix accuracy plus measured >=1.1x gain over
the completed four-rank mixed prefix; its native measurement cap is 10,800 s.
These are experiment-entry conditions, not proof of practical full-run speed.
The speed goal and all release qualifications remain unproven.

Balanced trial `101` has entered transient stepping. Its first 33 complete
samples agree with the unbalanced sixteen-rank reference within 10 nV, with
identical saved times and all 25,734 physical voltages covered. This validates the
early electrical result after redistribution; full prefix timing and complete
175 ns performance remain pending.

The live full-duration run `102` has passed its first 300 complete saved samples
against fresh UMFPACK: all 25,734 physical voltages agree within 10 nV on
identical saved times through 20.3721959 ns. This is an early full-run check,
not a completed 175 ns assessment; its native endpoint, programming/reset and
extended reference checks remain pending.


### Simulation speed evidence — 2026-11-04

Completed full-duration trial `112` took 10,650.309 s on sixteen pinned MPI
ranks. Cached matrix conversion trial `127` completed the same 175 ns diagnostic
in 8,996.251 s (149.94 minutes, 1.18386x speedup). Both retain the original full
physical circuit and electrical tolerances. All 5,800 saved samples of all
25,734 physical voltages and their timestamps match exactly between these runs;
see `build/signoff400/cached_conversion_full_all5800_waveform_20261104.json`.
This agreement is against the preceding backend, rather than an independent
full-duration accuracy or convergence qualification. Programming bits and reset
checks passed, but startup, frequency and lock qualification remain pending.
The provisional two-hour runtime target is not met.

Values-only MPI gather trial `129` is the next bounded 21 ns experiment, using
sixteen individually pinned ranks and the experimental `value-gather` policy.
It caches the fixed matrix layout, checks local graph structure on updates and
transfers changing values. Small native controls `128` passed through four MPI
ranks. At the first 200 large-circuit solves, cumulative gathering fell from
29.9849 s in cached-conversion prefix `126` to 3.65359 s; this is a phase counter,
not a completed runtime speedup. Full-circuit prefix waveform agreement and
completed timing remain pending. No release qualification follows from this
experiment.


Values-only gather prefix `129` subsequently completed normally in 783.386 s,
versus 977.069 s for cached-conversion prefix `126` (1.24724x speedup; 19.82%
less runtime). All 494 saved samples, their timestamps and all 25,734 physical
voltages match `112` exactly. See
`build/signoff400/prototype_v3_value_gather_prefix_129/assessment.json` and
`build/signoff400/value_gather_complete21ns_waveform_20261104.json`.
There were zero failed transient linear solves and zero DC factor-reuse hits.
Full-duration successor `130` is now running on sixteen individually pinned
ranks with unchanged electrical inputs. Its launch audit verifies all sixteen
rank affinities and pinned input hashes. It requires the original completion,
programming/reset and fresh-backend overlap checks, plus an exact comparison of
all 5,800 saved samples against completed cached-conversion trial `127`.
The prefix gain is not yet a measured full-duration gain; the two-hour full-run
target and release qualification remain unproven.


### Validated simulation configuration — 2026-11-04

Values-only gather full trial `130` completed the original full-C 175 ns
programming diagnostic in **6,776.384 s (112.94 minutes)** on sixteen pinned
MPI ranks, one solver/BLAS thread per rank. This meets the provisional two-hour
native-runtime target. It is 1.32759x faster than cached-conversion full trial
`127` (24.68% less runtime) and 1.57168x faster than double-CSR trial `112`.

The completed comparison covers all **5,800 saved samples and 25,734 physical
voltages**, with exact timestamp and value agreement against `127`. The first
1,500 samples also pass against fresh factorization, with about 10 nV maximum
voltage difference on identical times. All expected programming bits match,
oscillator reset stays low, transient failed linear solves are zero and DC
factor reuse stays disabled. All pinned input and artifact hashes were
independently rechecked after completion.

Evidence is in `build/signoff400/prototype_v3_value_gather_full_130/`:
`assessment.json`, `complete_prior_backend_comparison.json`,
`programming_observations.json`, `timing.json` and
`speed_validation_audit.json`. The run is complete; no native worker remains.

The selected build policy is `value-gather` in `tools/xyce_umfpack/build.py`:

```sh
apptainer exec build/apptainer/openpll-release-modern.sif \
  python3 tools/xyce_umfpack/build.py \
  --experimental-checked-reuse --reuse-policy value-gather \
  --cpus 24,25 --output build/tools/xyce_value_gather_new
```

Use a fresh build output directory. The validated run uses
`.options DIST STRATEGY=2`, sixteen MPI ranks individually pinned to CPUs 0–15
through `tools/xyce_umfpack/rank_exec.py`, `-linsolv umfpack_reuse`,
`OMP_NUM_THREADS=1`, `OMP_THREAD_LIMIT=1`, `OPENBLAS_NUM_THREADS=1`, and a 64 GiB
reservation. Preserve original models, parasitics, stimuli and tolerances.
Each new circuit trial needs its own deck and output directory; archived trial
`130` is evidence and should not be rerun in place.

This is runtime validation of the pre-release programming diagnostic. The
175 ns endpoint precedes oscillator-reset release at 180 ns. Startup, frequency,
lock, numerical convergence and release/tapeout qualification remain unproven.


### Selected-circuit mixed-signal development — 2026-11-05

Full native startup trial `131` completed 260 ns with 45,760 finite saved
samples and zero failed transient linear solves. The oscillator starts after
reset release; its measured 200–260 ns average is 392.3103 MHz at coarse 20,
fine 111. The deck holds PLL_ENABLE low. Its lack of tracking is therefore
expected and is not a failed lock result. Native-input RTL replay `135` matches
the final programming/status outputs. A separate synthetic clock continuation
`146` predicts configuration-ready at 900.05 ns; it does not qualify native
startup timing beyond the observed interval.

`run_selected_mixed_signal.py` provides explicit scenario, phase, preset,
polarity and gain inputs. It requires full observation segments and the terminal
completion marker, applies the existing functional acceptance limits, and keeps
physical/release qualification false. The measured-only flow requests missing
native data rather than extrapolating tuning. The current missing point is
coarse 20/fine 112, under native calibration `134`, with assessment watcher `138`.
`selected_model_registry.py` keeps analog/interface identity distinct from the
controller version and verifies pinned data. The current registry is diagnostic;
its detector fit has not been qualified for the selected layout.

All 8,383 boundary voltages of the proposed conditional partition are uniquely
available in the native waveform (`140`). Export `142` retains 15,600 primitive
instances, 6,054 wire resistors and 714,168 private-incident capacitors. Omitting
555,050 boundary-only capacitors is specific to a prescribed-voltage private-KCL
solve and does not qualify exterior currents. Replay files `144` preserve every
saved knot. Loading that complete replay in control `145` failed with SIGSEGV
before DC initialization after high memory use near the address-space cap;
memory pressure is suspected, not a proven root cause. No identical retry is
scheduled and no circuit/partition failure is inferred from it.

Separate variant `148` removes only redundant constant-plateau interior knots,
without voltage approximation. Bounded prefix `149` retains the right guard knot
for the 1 fs control interval; control `150` tests initial-state correctness
without loading irrelevant future data. Neither a prefix/DC pass nor a
conditional waveform match establishes a reusable tuning model. Full transient
correlation, independent code/loading holdouts, extraction/FOM uncertainty,
five-corner tuning coverage, the 60-case closed-loop matrix, final timing/CDC,
and the five-gate release audit remain open.

The bounded initial-state control `150` completed in 90.48 seconds and matched
all six monitored initial output voltages exactly. This covers six DC values,
not internal state or transient behavior. Exact 21 ns replay preparation `152`
is complete; transient control `153` is running. The full fine-112 native
calibration `134` and its assessment watcher remain active.

`run_selected_matrix.py` now orchestrates the five-corner, three-scenario,
four-phase diagnostic matrix using one common KI/KP pair. Supply five
`--registry` arguments and a fresh `--output`, starting with `--ki 4 --kp 0`.
Each registry interface must name its `detector_rtl` and pin that file in
`input_sha256`; recompute the interface identity when adding this explicit
path. Missing corners or measured startup points produce exit 3 before
simulation. An unsupported tuning code stops the matrix and records a native
measurement request. Exit 0 means all 60 functional diagnostic traces passed;
physical qualification and release readiness remain false. The existing
`loop_v3.py` qualified-model route and five-gate audit remain the release gates.

Preflight `156` checked the real TT measurement registry and requested the four
missing corner registries without launching simulations. Synthetic benchmark
`155` completed twelve engine cases in an observed upper bound of 116.63 seconds;
its deliberately untunable model passed zero functional cases. This establishes
engine throughput and failure handling, not target-PLL lock. The streaming-DAC
review `154` identified different time-zero initialization behavior, so that
alternative is not adopted without a native equivalence control.

Native DAC/PWL controls `161` now quantify the alternative memory-bounded replay
route (`tools/xyce_streaming`). The four controls completed 2 ns each. Loading a
whole waveform at time zero produced a 1 V error for both fixtures. Streaming
after an explicit 1 ps bootstrap matched a plateau fixture within 6.67e-16 V,
but produced a 2 mV maximum error for a ramp starting at zero. The provisional
API requires an ADC readback device; direct solution readback is used because
normal deck waveform printing is not emitted along this stepping path. DC
readback can expose the initial trial point, so only positive accepted transient
intervals are included in these metrics. No DC-equivalence claim follows.

Initial-segment analysis `162` verified all 8,383 prefix PWL artifact hashes and
examined their first saved segment/right guard. Of these, 1,027 are not exactly
flat; the worst held-voltage error over a 1 ps bootstrap is approximately
1.0e-16 V. This is a recorded source-voltage bound only. It does not bound
private charge/state error, extend the prefix bench's declared interval, or
qualify a selected-circuit streaming model. Streaming is not adopted in the
release path pending a native circuit equivalence control.

To reproduce the small API controls, run inside the pinned tool container:

```sh
python3 tools/xyce_streaming/build_probe.py \
  --manifest build/tools/xyce_umfpack_value_gather_001/manifest.json \
  --output build/tools/xyce_streaming_new
python3 tools/xyce_streaming/run_controls.py \
  --probe build/tools/xyce_streaming_new/probe \
  --output build/signoff400/streaming_controls_new
```

Use fresh output directories. The builder links the existing isolated Xyce
archive without simulator patches. The control runner uses CPU 24, an 8 GiB
address-space limit, and a 60 second timeout per small fixture.

Exact compaction `148` is complete: 383,606,080 recorded knots became
295,665,644 by removing only redundant constant-plateau interior knots across
all 8,383 files. No voltage approximation was introduced. This receipt verifies
file equivalence, not native memory fit or circuit behavior.

`boundary_replay.cpp` generalizes the API control to the selected recorded
boundary inventory. It keeps a source's current right guard in memory, enforces
future-knot spacing above the DAC filter threshold, caps bootstrap at 1 ps,
and uses the isolated ADC needed by the API. Native smoke `163` completed 2 ns;
its source and PWL reference differed by at most 5.56e-16 V. Reference readback
also matched the analytic PWL at the accepted timestamps within 5.56e-16 V.
Selected control `164` is running through 21 ns on CPU 24, with comparison
watcher `165`. It uses the same private devices, R and C as the PWL control.
The watcher compares only positive accepted samples and never claims DC or
physical-model qualification. These controls still precede oscillator startup.

Partial snapshot `166` covers 5.121 ns of the running selected streaming
control. The largest of 31 output voltage differences is 7.27 uV on PLLOUT;
neither trace has oscillator rising edges in that interval. The 1 uV diagnostic
flag is false. Preserve this discrepancy; it is neither a lock failure nor a
qualified analog-model error bound.

Queued controller `167` will start a separate 260 ns streaming diagnostic `168`
once short comparison `165` completes, then write assessment `169`. The longer
run has a 12 hour native cap, CPU 24 and a 48 GiB address-space cap; it does not
retry automatically. Its prerequisite requires a complete, pinned, 31-channel
21 ns comparison against the same reference. The strict diagnostic voltage
flag may be false: this extension investigates whether voltage discrepancies
change oscillator startup/frequency/edge timing, and never grants qualification.
The extended comparator reports measured frequencies from edges at/after 200 ns
when at least three are available. Missing or failed short observations stop
the queue. Full recorded-knot replay, rather than the 21 ns prefix, supplies the
extended run. Its shared saved grid has no intervals at/below the DAC's 1 fs
filter threshold (minimum recorded interval 63 fs).

The extended scripts and `boundary_replay_v2.cpp` are separate variants so the
running short-control sources remain immutable. The C++ variant accepts a
260 ns endpoint with a small floating-point comparison guard. Both controls
remain recorded-boundary diagnostics; native tuning holdouts and physical
correlation are still required before model-based release evidence is valid.

Partial cross-check `170` snapshots the two live controls and compares their
common 1.55 ps–3.7318 ns interval at the PWL control's saved times. Across 1,672
samples and 31 outputs, PWL versus full-native error is at most 1.09e-13 V;
streaming versus PWL/full-native error is at most 2.41e-9 V. These observations
precede the reset transition at 5 ns. They support baseline partition/API
consistency, but do not explain or qualify the later 7.27 uV discrepancy.
Snapshots do not establish either control's completion.

The primary [SKY130 mask documentation](https://skywater-pdk.readthedocs.io/en/main/rules/masks.html)
identifies FOM as Field Oxide, and the [layer reference](https://skywater-pdk.readthedocs.io/en/main/rules/layers.html)
identifies FOM dummy/waffle geometry. These descriptions do not supply a physical
capacitance error bound for the selected fill. In the existing native scope
controls, “canonical 23/28” means the pinned Magic technology's FOMFILL export
purpose; it is not a claim that this purpose is the documentation's 23:0 mask
layer. The installed technology explicitly imports both tested purpose codes
as `fomfill`. Physical FOM coverage/accuracy remains an open evidence item;
its diffusion display style alone establishes neither implant physics nor
an electrical model.

Selected streaming control `164` completed 21 ns normally in 1,417.41 seconds
(23.62 minutes), with 4,942 linear solves, zero UMFPACK failures and no DC reuse.
Comparison `165` completed all 2,693 positive accepted samples and 31 outputs.
Its maximum voltage difference against the full-native trace is 33.30 uV on
CLKDIV_RETIMED, so the strict 1 uV diagnostic flag is false. Neither trace has
oscillator rising edges in this interval; frequency/startup correlation is
still unproven. The PWL control remains live and is not a completed runtime
baseline. Queue `167` has advanced to preparation of the separate full 260 ns
control `168`; its result will be assessed in `169`. No release gate is changed.

Transition cross-check `171` extends the PWL/full/streaming comparison through
5.237 ns, including reset. The PWL conditional control differs from full-native
by up to 6.21 uV; streaming differs by up to 7.27 uV, and the two conditional
methods differ by up to 3.81 uV. Thus streaming initialization is not the sole
source of the observed deviation. This remains a partial common-window check,
not a convergence study.

`assess_selected_interface_observations.py` separately quantifies saved-sample
logic agreement using the existing 0.9 V readback convention. Assessment `172`
verifies the completed comparison's input hashes and inventory, then checks
all 2,693 samples/31 outputs: zero sampled logic mismatches, with the nearest
native output sample 0.89004 V from the threshold. Every channel's minimum
sample distance exceeds its observed maximum voltage difference. This is not
a noise-margin specification, unsaved-hazard assessment, or timing/model gate.

`advance_selected_calibration.py` is now waiting in `173` for completed native
assessment `138`. It verifies the original native/model identities, provenance,
artifact hashes and RAW digest; compares the two decks while permitting only
the eight binary fine biases and RAW output destination to change; checks the
measured fine code against the requested stimulus; and creates a fresh measured
registry with unchanged analog/interface keys. It writes a next-native-point
request using `select_calibration_point.py`. It does not extrapolate a simulation
table, launch another full native circuit, or promote diagnostic models.

`capture_selected_native_runtime.py` addresses a provenance gap in the older
native manifests: those pin the extracted model/deck, but not the PDK's nested
include closure directly. Captures `174` and `175` read the live controller
mount namespaces twice and hash a conservative superset of all statically
referenced PDK files, including inactive library sections. Comparison `176`
confirms identical contents for 319 files and checks that each native child
shares its captured controller mount namespace. The declared image digest
matches the previously recorded release-tool image. These are live-namespace
observations, not proof of a historical run's image binding or corner selection;
`historical_reference_runtime_attested` and physical qualification remain false.

The diagnostic matrix now accepts `--presets FILE` for explicit startup
programming by corner. The JSON object must contain exactly `tt`, `ff`, `ss`,
`sf`, and `fs`; each value must contain integer `coarse`, `seed`, and `polarity`
fields within the existing programming limits. Each startup code must already
have a measured point in its corner registry. The file is pinned and each case
records its actual preset. KI/KP remain common across all 60 cases. Without this
option, the scalar startup arguments remain common defaults. No measured
all-corner presets have been invented or supplied; preflight `177` still
requests the four absent process-corner registries and launches no simulations.

PWL conditional control `153` reached its one-hour native budget and stopped
without qualification. Watcher `157` also stopped explicitly; neither job is
restarted. Review `178` preserves the final partial RAW and verifies 4,550
complete finite ordered samples through 9.0947 ns, short of the required 21 ns.
This is a runtime-budget result, not a circuit-failure or completed waveform
comparison result. The completed streaming control remains the bounded replay
path under investigation; it does not yet qualify tuning or oscillator behavior.

Selected detector inventory `181` verifies every native primitive's terminal
mapping against the same physical sidecar and original wire model. The detector
contains 1,782 primitives, 66 signal nodes, 1,414 incident capacitors (1,113 with
an external endpoint), 619 remote RC nodes, and five crossing wire resistors.
Its hierarchical view has 59 formal ports; nine logical signal/supply roles are
resolved, including formal `SUB` connected to parent `VGND`. The remaining 50
hierarchical ports are not assumed to be independent voltage inputs. There are
29 detector primitives shared with the current DCO partition.

`bind_selected_detector_ports.py` uses the wire-contraction sidecar to resolve
the five physical terminals (`182`). Old output names alone do not work after
R insertion. REF maps to `__parent_R_node_3003`, CLKDIVR to
`__parent_R_node_2885`, detector RESET_N to `__parent_R_node_3059`, and the two
outputs to `__parent_R_node_3055`/`3057`. The parent drives detector RESET_N from
TRACKING. These bindings prepare a correctly bounded interface bench; receiver
loading and active phase response remain unqualified.

Pin capture `183` collected all five detector-terminal traces from completed
full-native run `131`, without rerunning its circuit. Four verified boundary
PWL files were reused; the missing CLKDIVR trace was extracted by the existing
compiled finite/ordered RAW reader. The RAW digest was checked before and
after extraction. Every trace contains 45,760 samples through 260 ns.
Measured complete 10–90% rising slews are 79.820–79.822 ps on REF (six edges)
and 477.028–477.033 ps on CLKDIVR (two edges). These are observed TT/disabled-loop
values, not a qualified all-corner active-mode slew envelope.

The actual detector reset pin ranges from -12.77 mV to +11.40 mV and never
crosses 0.9 V; neither detector output has a rising logic edge. This confirms
that run `131` does not calibrate active phase response. The selected-layout
interface probe must cover the observed input-slew asymmetry, actual receiver
loading and relevant holdouts before the historical detector fit can contribute
to release evidence. The existing closed-loop bench already drives its detector
reset from the actual RTL BBPD_RESET_N output, which is assigned TRACKING.

Receiver inventory `186` follows actual LEF pin directions through clock and
data fanout, rather than assuming a direct detector-to-flop connection. It
identifies 14 parent cells/484 primitives: ten HS clkbuf_16 cells, two HS dfrtp_1
cells and two HS xnor2_1 cells. Each detector output reaches one event clock
and the other receiver's D input, matching cross-channel inhibition. Backward
D-input closure finds no unresolved input-driver components or external state
inputs. Each Q output additionally drives a downstream HS dfrtp_1; that loading
and other coupled boundary behavior still need bounds before phase-bench use.
No receiver substitute load or active phase-response qualification is emitted.
The LEF snapshots in `185` match the selected candidate's existing proof hashes.

Clock-path observation `187` measures nearest-preceding-edge phase offsets in
the 200–260 ns native window. Rounded transport values are 704/582 ps for rising/
falling divided-output transitions after PLLOUT rising edges, 5 ps for the
feedback wire and 2 ps for the reference wire. These are sparse TT observations,
not proven unwrapped causal latencies or an all-corner timing model. The packet
explicitly remains diagnostic and unqualified.

`Prototype400ClockTiming.v` and the separate timed closed-loop bench apply those
explicit delays before the detector and record DIV at the physical divided-output
boundary. The actual controller RTL and the existing phase acceptance limits are
unchanged. `run_selected_mixed_signal_v2.py` requires a clock timing packet;
`run_selected_matrix_v2.py` additionally requires one pinned by each corner's
interface registry. Timed registry `190`/preflight `191` still request the four
missing corner datasets. Smoke `189` compiled and exercised the actual RTL,
then exited 3 requesting native coarse 20/fine 112 without extrapolation.

The qualified-model route in `loop_v3.py` now requires clock timing covered by
the qualified interface receipt, matching the operating point and physical
model. Diagnostic phase observations cannot qualify that path. Synthetic engine
controls can still exercise zero-delay timing explicitly as diagnostics. Compile
commands now execute independently of Python assertions.

Synthetic timed control `193` completed all 12 scenario/phase cases; zero
functional passes are expected for its untunable 400 MHz/no-detector fixture.
Cross-check `194` pairs its cold-start edges with the prior zero-delay engine
control: all 5,503 DIV edges move by 704 ps, while 5,505 REF edges and 88,000 OUT
edges remain unchanged. This verifies timing-boundary implementation, not PLL
lock or native interface qualification. All 72 selected-flow tests pass in the
release container, including the Icarus timing adapter checks.

Selected-layout diagnostic detector fit `254` uses seven conditional native
waveforms and eight separate holdouts, including two budget-stopped native
clock-shape prefixes with complete first-event windows. All sampled decisions
and replayed event counts agree; output edges lie within the observed fit band
plus 1 ps quantization. The nominal lookback is 111.9828 ps. This remains a TT
rising-edge-neighborhood diagnostic: receiver latency, other phase regions,
exterior switching, numerical convergence and other corners are unqualified.
`fit_selected_detector_diagnostic.py` requires one physical native model across
fitting and holdout data and replays the emitted Verilog in Icarus.

`bind_selected_detector_registry.py` creates a new interface identity while
preserving the measured analog cache. Binding `255` retains coarse20/fine111.
Actual RTL probe `256` takes 4.73 s and requests measured fine112, without tuning
extrapolation. Follow-up `257` observes registry advancement `173`, then binds
the selected detector and reruns the same actual RTL case once; it does not
launch another native calibration or promote diagnostic results to release.

Bounded native clock-source controls `259`/`260` completed all 80 ns in
1550.81/1399.66 s. `bounded_clock_sources.py` certifies at most 1 uV uniform
voltage error by checking the union of the two PWL knot sets and preserves
all 0.18/0.9/1.62 V crossing times. Audit `263` verifies identical devices,
passives, exterior biases and solver controls before comparing responses.
Comparison `275` agrees with the exact-source prefixes in sampled signs and
actual receiver captures; the largest edge shift is 0.03449 ps and capture
latency shift 0.00644 ps. This is diagnostic agreement, not a charge-response
or all-condition interface-equivalence proof.

RAW output still rounds time despite the print precision setting. Each complete
control contains 74 repeated printed timestamps. The V3 assessor and V2 response
characterizer retain every complete sample, require the declared point count
and endpoint, and reject nonfinite data. Separate observation receipts `268`/
`270` and responses `269`/`271` recover the normally completed native runs;
no circuit retry was needed. The comparison command accepts explicit recovered
`--assessment` and `--response` paths for this situation.

Feedback-driver inventory `264` resolves CLK/D/RESET_B/Q on the actual 39-
primitive HS DFRTP4. Capture `265` extracts all five driver/reference channels
from the existing full native RAW, preserving its 45,760 saved samples and
checking the prior complete RAW fingerprint. The cropped reset input is still
asserted at initialization. No storage state or driver Q is forced.

Loaded partition `267` moves the feedback cut from Q to the three real input
pins, includes both actual CLKBUF16 loads on Q, and keeps 2,514 primitives/
36,726 passives. Q's explicit wire-R component has no exterior voltage clamp.
The recorded clock/data/reset curves receive one common time translation; the
original Q curve supplies an anchor only. V7 native diagnostic `273` runs on
CPU25 with a two-hour/12 GiB cap. Live runtime capture `274` matches the same
319-file PDK include superset and executable as the full calibration. Exterior
switching, remaining loads, other corners and active interface qualification
remain open; this bench does not issue a qualified model.

The diagnostic synchronizer stimulus is already a nominal 400 MHz pulse
(`pulse(-10,100,2.5)`), not 25 MHz. It is not the recorded physical clock
waveform. Inventory `276` and capture `278` additionally request the actual
synchronizer-clock and reset-pin curves from the existing native reference,
so its phase/slew relationship can be tested without changing running `273`.
The inactive native event/detector reset traces are evidence only; they cannot
replace the explicit active-reset protocol used by detector tests.

Capture `278` completed nine channels with every one of the 45,760 native
samples retained. Clock-path observation `279` pairs all 30 startup carrier
edges in order: physical synchronizer transport is 249.583–249.635 ps and
feedback-FF clock transport 261.656–261.699 ps. All four observed driver-Q
changes follow the first eligible clock edge after data/reset changes, with
about 441 ps rising and 319 ps falling CLK-to-Q delays. These refer to the
physical driver Q, not a substitute observation port. The packet remains
diagnostic; it neither replaces `187` nor qualifies an uncertainty/corner
envelope or a complete unwrapped causal timing model.

Receiver probes compare nominal publication and sampling cycles locally. An
intentionally near-aperture asynchronous input can reveal setup/hold or
metastability-related capture uncertainty. The prototype criterion is to
characterize that uncertainty and demonstrate controller operation under it;
it does not require the asynchronous first stage always to select the ideal
first eligible edge. Unexplained behavior remains unqualified. This preserves
the required crossing review, interstage timing and uncertainty holdouts,
while the profile separately defers the production 1 FIT target.

`run_selected_mixed_signal_v5.py` is an experimental bounded-interpolation
diagnostic, separate from the version-4 measured-only path. `--interpolation`
selects linear period or linear frequency between native knots. Estimated
rows are never inserted into the native measurement registry, and unsupported
codes outside each bank span still request native data. Interpolation itself
is not a validated uncertainty bound or release-qualified model.

Native comparison guard checks corner and 27 C temperature; matching geometry alone cannot admit FF data against a TT reference. Supply and library identity require the separate runtime/input audits. Evidence: `build/signoff400/selected_native_corner_comparison_guard_395.json`.

Two-stage TT receiver replay matches both observed UP transitions in count, value and sampling cycle. DN remains inactive. DLF is disabled: this is local receiver evidence, not full-controller or setup/hold qualification. V6 resolves the continuation geometry through its verified boundary inventory; the original failed observer is retained. Evidence: `build/signoff400/selected_two_stage_receiver_replay_398/assessment.json`.

Receiver replay V7 uses the exact selected-layout RTL binding, with its MMD configuration parameters. Physical replay `399` matches both active UP transitions at both stages using the independent publication model. DN is inactive, and DLF remains disabled; aperture and complete controller timing qualification remain open. The prior legacy-source replay is retained separately.

Active-DN two-stage control `400` uses phase -5 ns with the same device cards, observed nodes and TT operating point as UP control `346` (identity audit `402`). Collector `401` uses V7 layout-pinned RTL and the independent frozen publication model `372`. Native execution is capped at three hours with 12 GiB on CPU26; completion and active-DN coverage must be verified from its results.

Clock-frame audit `405` pairs recorded PLLOUT edges with both bounded receiver clocks under their original common time translation. First-stage clock transport is 249.583–249.635 ps; second-stage transport is 252.244–252.296 ps. Both active UP transfers use the next root cycle, with 365.1–365.7 ps first-Q to second-D transport and approximately 2.00 ns data lead. This sampled mapping prevents confusing local publication delay with root-domain delay; it does not qualify a uniform uncertainty envelope, setup/hold or complete controller timing. Run the audit inside the pinned simulator image to verify its Icarus executable pins.

Root-frame receiver replay `406` uses recorded PLLOUT, subtracts the median measured first-clock transport from independent publication delays, and compiles selected-layout RTL. Observed UP capture cycles match native at first-stage indices 5/21 and second-stage indices 6/22; DN remains inactive. This tests the timing-frame conversion needed by the whole-loop bench without fitting publication timing to the validation events. It does not qualify full-controller timing or uniform uncertainty and is not yet applied to the main loop model.

Diagnostic composition `407` adds measured event-publication delay to detector fit `254`, after subtracting sampled local-clock transport to use the PLLOUT frame. UP effective delays are 216.606/205.195 ps and DN delays 224.233/207.335 ps for alternating event-Q rise/fall. Adapter check `409` verifies both channels, pulse-width preservation and pending-event cancellation across reset. Selected-layout whole-loop diagnostic `408` reaches unsupported coarse20/fine113 in 4.68 s and requests native data; it neither extrapolates nor proves lock. Main release models remain unchanged while DN native validation, other timing paths and uncertainty remain open.

Collector `410` waits for the original target calibration `316`, then runs the publication-aware selected-layout controller with measured-only points and separately with bounded period/frequency interpolation. It pins the original analog registry and diagnostic interface separately, uses KI4/KP0, never starts native work, and preserves missing-code requests and diagnostic failures. Interpolation results do not qualify an error bound or replace independent native holdouts.

Numerical control `414` requests CPU27/16 GiB through the shared lease gate, with a three-hour cap. Preflight `413` proves the same retained devices and source cards as TT baseline `362`; only timestep (10 to 5 ps) and reltol/abstol (1e-5/1e-9 to 1e-6/1e-10) change. Collector `415` uses comparator V2, whose physical reset role is DCO_reset, and requires normal 60 ns completion. Negative tests reject changed device cards, source voltages and corner selection. This measures combined numerical sensitivity of the reduced circuit, not a full-model convergence bound.

Coherent-clock fine112 control `388` and full-reference comparison `389` completed normally. Matched oscillator-age 10–40 ns increment `416` is 0.281224 MHz reduced versus 0.357858 MHz full, a -21.415% slope error; early/late errors are -21.433%/-21.725%. Residual absolute errors are +1063.129 ppm at fine111 and +866.952 ppm at fine112. Input audit `417` proves identical device cards/solver settings and only DCO_THERM[111] driver-input voltage changes. The reduced model remains unqualified; a constant frequency offset cannot repair this tuning slope. Independent FF holdout `369` matches first-stage counts, values and cycles for one UP and one DN transition; second-stage, falling-direction, aperture and whole-controller coverage remain open. Numerical control `414` is now admitted and live, with all 319 PDK dependencies and executable matching (`418`).

Residual load inventory `419` finds 287 omitted incident primitives belonging to 77 complete physical cells (49 flip-flops in total), requiring 2,038 primitives to retain whole cells. Plan `420` selects 7,818 primitives, including all of prior control `284` plus another 1,249. Control `423` runs on CPU16/16 GiB with a three-hour cap; collector `424` compares its full111 reference. Preflight `422` preserves all original cards and common source voltages, internalizes 625 old cuts and exposes 702 new exterior cuts without clamping any original private node. Those new cuts use the same recorded TT final-bias procedure; stateful exterior histories remain unqualified. Runtime `425` matches all 319 PDK dependencies and executable. This is a load-sensitivity experiment, not a qualified full-equivalence model.

Completed conditional SS probe `394` measures 241.935 MHz at C20/F111. Historical macro-only sweep SS C47/F120 (403.538 MHz) is used solely to choose the next native probe, not as current-candidate calibration data. New SS guide `426` measures C47/F120 using the same physical reduced circuit and TT-derived exterior biases, CPU23/16 GiB/three-hour cap; collector `427` records frequency and clock-edge guidance. Audit `428` admits only the expected 36 programming input changes, with identical devices/common exterior biases/solver settings, and runtime `429` matches all 319 PDK dependencies and executable. Full-corner exterior and tuning qualification remain open.

Unseeded load control `423` terminated with a DC operating-point failure, before any transient result. Distinct control `433` adds 896 recorded final-bias NODESET guesses on newly internalized load nodes only. Audit `432` preserves devices, sources and transient settings, excludes original DCO nodes, and rejects UIC/NOOP. Per the [Xyce reference guide, section 2.1.22](https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.8.pdf), NODESET first solves with specified values and then solves without those constraints; it is not a held transient state. State selection remains conditional. Collector `434` waits for normal completion; runtime `435` matches all 319 dependencies and executable. The original failure is retained.

Recorded REFCLK forcing control `378` completed normally; comparison `380` measures +19.072 ppm relative to the held-reference baseline over oscillator age 10–40 ns (early +12.108 ppm, late +23.453 ppm). Twelve aligned output edges differ by -0.652 to -0.118 ps. Thus, these two REFCLK cuts do not explain most of the previously observed +1063.129 ppm reduced/full fine111 mismatch. This conditional forcing trajectory does not establish a general frequency or phase uncertainty bound.

Load-node guess control `433` also terminated with a DC operating-point failure and no transient result. Reset/set inventory `437` resolves all 49 added state cells and confirms all reset/set pins are private circuit unknowns, with no held exterior voltage source on their actual model R components. Thus a direct reset/set clamp is not the established explanation. Both unseeded and node-guess failures remain evidence; this inventory does not identify the nonlinear DC failure cause.

Near-aperture FF holdout `383` completed normally. Frozen-model replay `438` preserves both UP counts/values but misses the falling event capture cycle: at 19.992 ps native data lead, native first-stage capture is cycle17 and ideal RTL predicts cycle16. The earlier well-separated transition matches. This is observed one-cycle capture uncertainty, not a qualified aperture limit or a requirement for asynchronous first-edge certainty. Probe `439` (phase9.8515) targets approximately 100 ps lead between the 20 ps late capture and earlier 248 ps first-edge capture; actual timing must be measured. Collector `440` retains the same training cases, and runtime `441` matches all 319 PDK dependencies and executable. Controller robustness under such capture variation still needs to be demonstrated.

`replay_selected_receiver_uncertainty.py` adds explicit nominal/late-window diagnostic capture policies using layout-pinned RTL. A provisional 100 ps window defers near-edge delivery until just after that clock and preserves pulse width; it is chosen after observing the 20 ps case and is not an independently validated aperture model. Stress replay `442` reproduces native FF capture cycle17 while keeping the native first-eligible-edge mismatch visible. Well-separated independent UP/DN case `443` remains unchanged and matches. Two unit checks cover nominal identity, width preservation, distant events and rejected reordered/invalid inputs. Whole-controller robustness under capture variation remains open.

Conditional FF/SS guide collection `397` completed: at C20/F111, FF is 595.049 MHz and SS 241.935 MHz. First-sync clock relative delays average 180.896 ps FF and 345.942 ps SS, with other retained clocks observed too. These run at different carrier frequencies with TT-derived exterior biases and are not interchangeable with the recorded-TT-clock publication experiments.

Target guides `444`/`445`/`446` measure FF C9/F184, SF C26/F88 and FS C20/F136 on CPUs22/18/19, each 16 GiB/three hours. Historical macro-only sweeps choose these controls but supply no calibration frequencies. Collector `447` waits for original jobs. Audit `448` permits only expected programming-driver values and explicit corner changes; devices, common exterior bias, observations and solver settings match. Runtime `449` verifies all 319 PDK dependencies and executable for each live native process. Full-corner calibration remains open.

Whole-loop diagnostic receiver stress `450` adds an explicit 100 ps to each of the four root-frame publication direction delays; other generated Verilog is byte-identical to nominal composition `407`. This is an extra-latency stress assumption motivated by the FF capture deferral, not a measured TT aperture or uniform uncertainty bound. Adapter checks `451` pass direction alternation, pulse widths and reset cancellation. Selected-layout loop `452` requests native C20/F113 after 4.65 s. Collector `453` waits for the same original target calibration as nominal collector `410` and will run matching measured-only/period/frequency diagnostic variants, without launching native work. Full-controller robustness remains unproven until supported complete traces and a qualified uncertainty envelope exist.

Initialization inventory `454` proves complete-cell coverage of all 5,780 retained baseline primitives. It counts 557 HD einvp and 110 HD einvn tri-state inverter cells, plus four retained HS dfrtp state cells (two _1, one _2, one _4). This precludes assuming the diagnostic is merely a combinational NAND chain with an established unique reset DC state. The inventory does not prove any node floats, identify enabled banks, or establish the cause of operating-point failures. Further initialization changes must preserve physical state/history obligations rather than replace them with guessed logic values.

Reset-domain audit `455` traces all four original retained state-cell RESET_B pins to the DCO reset wire-R component, driven by the real HS clkbuf_4 at input __context_node_15147. The prescribed input is PULSE(0 1.8 5n 50p 50p 80n 160n); the buffer output is not voltage-clamped. Completed baseline `362` measures initial DCO reset at 2.491e-7 V. Thus the original state cells already receive the active-low reset protocol; a deasserted held-final reset boundary is not established as the DC failure cause. This connectivity/initial-voltage audit does not prove failed-load state voltages or unique equilibrium.

FF DN falling-event holdout `384` completed normally. Combined nominal collection `385` preserves all counts/values and still reports the known near-aperture UP cycle mismatch; its publication parameters are byte-identical to `382`. Layout-pinned replay `456` matches both independent DN rise/fall captures, with no late-window deferral applied (data leads 298.673/1094.424 ps). This does not close aperture or controller-wide timing qualification.

SS publication training `457`/`458` uses phases10/-5 on CPUs21/24, each 12 GiB/three-hour native cap. SS devices use the solved SS initial vector from `306/ss`, with recorded TT upstream waveforms remaining conditional. UP is admitted and runtime `460` matches all 319 dependencies and executable; DN initially waits for shared memory admission. Collector `459` fits only completed original training cases and explicitly reports independent holdout validation as false. Missing directions remain explicit.

Upper-range queue `463` waits for the original target registry `316`, then requests at most one native point 32 codes above the closest measured target code (clipped to fine247). The selector inserts no predicted frequency and treats existing coverage or the bank limit explicitly; three unit controls pass. The original full runner, unchanged physics/solver settings, 16 ranks on CPUs0–15, 64 GiB shared lease and 172500 s native cap are retained. A queue lock plus observation of existing full workers keeps this workflow to one full native case at a time. Child observation failures do not restart or terminate independently bounded work. Nominal/stressed collectors `464`/`465` will consume the enlarged registry for measured-only and bounded interpolation diagnostics. Upper coverage and interpolation uncertainty remain unqualified until measured and validated.

SS target guide `426` completed normally at C47/F120: 395.848654 MHz. Clock guide `427` measures first-sync relative rise delay 345.658–345.694 ps over 16 paired edges. This is a conditional lower-side point, not yet a 400 MHz bracket. Probe `467` measures C47/F160 through the shared lease queue; audit `469` permits only its expected programming inputs, and collector `468` retains both results. Serial runtime collector `470` waits for the original PID/birth and actual pinned Xyce executable before recording dependencies; it never launches native work and rejects MPI cases. SS DN training `458` has now been admitted and runtime `466` matches all 319 dependencies and executable.

Initial-state load control `475` is a distinct attempt after the unseeded and final-time/new-node guess DC failures. It uses the recorded full TT initial DC vector at time0 for all 6,884 retained private voltage nodes. Preflight `476` checks every guess exactly, preserves all device/source cards and solver/transient settings, and rejects UIC/NOOP. The run requests CPU16/16 GiB/three hours through shared admission; frequency collector `477` and live runtime collector `478` wait for original work. Converged state and frequency remain unqualified. Individual target-guide collectors `471`/`472`/`473` make completed FS/SF/FF measurements available separately; combined collection `447` remains a cross-check.

FS target guide `446` completed at C20/F136: 392.433673 MHz; individual clock guide `471` is retained. Upper-side probe `479` measures C20/F216, with input audit `481` preserving devices, common exterior biases and solver settings. Its live runtime capture `482` matches all 319 dependencies and executable. Collector `480` waits for both points; there is no measured 400 MHz bracket yet and the exterior bias remains TT-derived.

Tighter numerical control `414` completed normally. Same-circuit comparison `415` measures +37.819 ppm over oscillator age10–40 ns (early +38.449 ppm, late +35.245 ppm): 392.655140 MHz tightened versus 392.640291 MHz baseline. This local sensitivity is much smaller than the prior approximately +1063 ppm reduced/full mismatch at fine111. It does not qualify full-model convergence, other codes/corners or a uniform uncertainty envelope.

Full initial-DC guess attempt `475` also failed before transient simulation. Live runtime `478` matched dependencies. Tiny native controls `483` confirm NODESET behavior in the pinned executable: opposite guesses select opposite level1-MOS latch states, while a divider guessed at 1.8 V relaxes to its unconstrained 0.9 V solution. These are solver controls, not PDK/PLL validation.

Output boundary audit `484` finds four held voltage cuts on the wire-R component of the retained HS dfrtp_4 feedback output __parent_R_node_2886 (cuts2887/2889/2890/2891, approximately 3.45 uV). Forty-nine retained state outputs were checked. A private Q node alone does not make its resistor network free of prescribed voltages. The next load-model correction must address that output frontier before additional state-guess attempts; the audit does not establish it as the DC failure cause.

Protected-output load plan `485` retains every original primitive/passive card, removes exactly four voltage sources on retained output resistor networks, and adds 15 original physical wire resistors (no capacitors). Export audits `487`/`492` preserve all 303 programming/reset inputs and the solver protocol; independent state-output check `491` finds no prescribed resistor component among 49 state outputs. Three protected-cut unit controls pass. Native control `488` nevertheless fails DC initialization with zero successful transient steps; runtime `490` matches the reference dependencies. Thus the output clamp is corrected but is not the sole DC failure cause. No additional node guesses were introduced. Held REFCLK cuts3003/3004 are near zero, ruling out the suspected mid-transition reference bias in this case. See `verification/prototype400/selected_unclamped_output_load_result.json` for hashed evidence.

Independent TT DN two-stage native probe `400` completed; layout-pinned replay `401` matches both observed DN transitions at the first and second receive stages with frozen TT publication model372. DLF remains disabled. Independent FF probe `439`/replay `440` matches first-stage captures, including the falling transition at measured 99.984 ps data lead (native/logical cycle16). The earlier 19.992 ps case captured on cycle17. These observations do not establish a uniform aperture bound; the provisional 100 ps late-window policy remains a stress assumption, not a calibrated capture rule. Hashed evidence is retained in `verification/prototype400/selected_receiver_additional_holdouts.json`. Full-controller timing qualification remains open.

SF conditional target guide `445` completed normally at C26/F88: 392.770425 MHz, with individual clock collection `472`. Upper-side probe `493` measures C26/F168 on CPU18 under the shared 16 GiB/three-hour lease. Input audit `495` permits only the 80 expected programming changes, preserving the physical cards, common exterior bias, solver and observations; runtime `496` matches the reference dependencies and executable. Collector `494` waits for the original lower/upper pair. No predicted frequency is assigned, and a measured 400 MHz bracket remains pending. The exterior bias is still TT-derived, so this remains conditional guidance.

Time-zero exterior control `497` isolates a remaining startup inconsistency: reset/programming start at time zero while earlier quiet exterior cuts were held at their full-native 260 ns values. It uses the verified original full-native time-zero voltages on all 6,315 non-programming/reset exterior nodes, with protected output plan485. Audit `498` verifies every source against the recorded vector and keeps devices, source boundaries, 303 programming/reset inputs, supplies, solver, print and transient protocol unchanged; no NODESET/IC/UIC is added. Runtime `499` matches all 319 dependencies and executable. Collector `500` awaits normal completion for an oscillator-age comparison. This tests one conditional boundary-state explanation; startup consistency, omitted exterior switching and frequency correlation remain unqualified.
