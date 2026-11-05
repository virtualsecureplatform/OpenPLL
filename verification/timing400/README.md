# 400 MHz first-release qualification

The active requirements are `verification/release_requirements_400mhz.json`;
`verification/active_release.json` identifies the active plan and unqualified
divider presets. Supported modes are100/250/300/400MHz at1.8V, five process
corners and three temperatures:60 mode/PVT cases.450MHz is deferred.

`run_dco_qualification.py` checks the160-load candidate first and144 second.
It independently remeasures completed TT traces and verifies their provenance,
then searches the remaining TT mode ranges. Only a complete TT pass permits
the rest of the PVT range matrix. SS125, FF-40 and FS125 are prioritized.
Only a complete60-bracket pass permits measured fine-code searches and
adjacent-code baseline/half-step/tighter-tolerance/longer-duration comparisons.
Missing brackets or failed convergence stop expansion; they do not prove
global unreachability or qualify a frequency model.

Every engine owns one native check, capped at43200s. A shared four-slot
admission controller counts external workspace Xyce jobs and reserves slots
while new engines prepare decks. The queue lock prevents duplicate400MHz
controllers. Timeouts are inconclusive; identical automatic retries and
overwriting an existing output directory are prohibited.

`prepare_functional_matrix.py` compiles the frozen physical candidate RTL,
tests its disabled/reset boundary and actual divider configuration at all four
ratios, and prepares60 blocked cases with all12 directed mode transitions per
PVT. It does not execute acquisition or lock qualification. Unknown/unvalidated
DCO model lookups must stop future qualification execution. Historical root RTL
and preset tables are not substitutes for the frozen candidate and its models.

Run controls with `python3 verification/timing400/test_release400.py -v`.
Native jobs and the HDL smoke require the existing release Apptainer image,
bound at both `/work/OpenPLL` and the host workspace path. Launch scripts using
the host absolute workspace path, as recorded in
`build/timing400/release_001/launch.json`. Always use a fresh output directory.

Current evidence lives in `build/timing400/release_001/`: `dco/status.json`,
`functional_matrix/assessment.json`, and `retired_450_scheduler.json`.
No local convergence result can adopt a model or qualify a release. Model
coverage, dynamic interfaces, nominal15PVT timing,60 whole-PLL cases, applicable
electrical/physical signoff, and final matching frozen artifacts remain gates.

## Phase-continuous clock bridge

`phase_clock_vpi.cpp` provides the Icarus verification task
`$pll400_phase_clock(PLLOUT, COARSE_CODE, DCO_CODE, RESET_N)` with widths1/6/8/1.
It integrates oscillator phase exactly in integer units, carries the sub-tick
residual between edges and tuning changes, and observes edges on a1ps grid.
Coarse/fine changes alter the phase derivative without restarting a half-cycle.
Reset holds PLLOUT high, matching the NAND-gated macro topology; simulation
benches must deliver an explicit reset assertion when the clock is stopped.

The task reads `+phase400_table=PATH`, a machine table with one exact
`coarse fine frequency_millihz` integer triple per line, and writes
`+phase400_trace=PATH`. There is no implicit interpolation or extrapolation.
Missing lookups, X/Z controls, malformed/duplicate points, incompatible widths
or time precision stop simulation with a nonzero exit status.

`check_phase_bridge.py --output FRESH_DIRECTORY` compiles the bridge, compares
saved edge times with an independent Fraction oracle and checks reset/disabled
integration with the exact frozen candidate RTL. `audit_phase_bridge.py`
independently checks saved artifacts and Decimal phase conservation. Run both
inside the existing release container with the host absolute script path and
both workspace bindings. Completed evidence is in
`phase_bridge_validation_003/assessment.json` and
`phase_bridge_independent_001.json` under the current release build directory.

These checks use explicitly synthetic frequency tables, including a full grid
only for the disabled/reset integration fixture. They contribute zero passing
whole-PLL qualification cases. The bridge currently represents an ideal50%
duty, deterministic oscillator; physical startup, duty, settling, tuning
transients, noise/jitter, supply effects and the dynamic BBPD/interface model
remain unqualified. A qualification runner must gate its use on matching
independently qualified models and reject every uncovered lookup.

## Functional trace acceptance

`functional_acceptance.py` evaluates the existing `event,time_ns,code,bbpd`
clock CSV plus the complete phase-bridge control CSV. It requires an explicit
`--observation-stop-ns`; a truncated channel cannot move the final windows
earlier. Capture actual reference edges through at least that horizon so phase
interpolation uses measured stimulus edges. Every tuning change and the command
active at each window boundary are checked against inclusive fine codes8..247.

The checker retains the existing frequency, phase span/mean/drift, cycle-slip,
sustained-window and conservative acquisition-confirmation deadline criteria.
It exits nonzero on a functional criteria failure. A trace-only pass is never
a whole-PLL qualification pass: terminal capture identity, qualified physical
models, a validated closed-loop driver and the remaining release gates are
separate requirements. The frozen historical checker is not modified.

Controls are in `test_functional_acceptance.py`; completed synthetic validation
is `functional_checker_validation_001/assessment.json` in the current release
build directory. Cases cover all four modes, valid code boundaries, invalid
codes7/248, invalid excursions between clock samples, truncated tails, missing
reference/control data, phase/frequency failures, cycle slips and deadlines.

## Compact digital mapping feasibility

`check_compact_mapping.py --output NEW_DIRECTORY` maps the frozen candidate
with full and restricted HS cell sets, proves paired-state transition/output
equivalence, checks a corrupted-data negative control, and compares unrouted
supplied-TT timing. Completed evidence: `compact_mapping_004/assessment.json`.
The compact mapping has12 synthesized cell types versus72 in its control;
all863 matched state elements and external outputs pass the relation check.

`check_compact_placement.py --mapping MAPPING_DIRECTORY --output NEW_DIRECTORY`
verifies that receipt, then runs a separate placement estimate with resizer
masters restricted to the allowed set. Both tools preserve the current design.
These are capacity diagnostics: cross-clock exceptions, unqualified supplied
views and missing physical effects prevent release timing claims. In
particular, the unrouted recovery path is still negative in both mappings.
New physical implementations require fresh logical, routed timing and signoff
evidence before adoption.

Physical continuation uses fresh output directories and retains failed evidence:

1. `complete_compact_ties.py --placement PLACEMENT --output TIED` connects
   actual tie cells before logical checking. The pre-tie export leaves constants
   undriven and fails the SAT check; it is never promoted.
2. `check_compact_physical_equivalence.py --gold-json MAPPING/compact/mapped.json
   --physical-verilog TIED/placed.v --output EQUIVALENCE` checks the complete
   paired-state transition/output relation and rejects an inverted reset control.
   Exact escaped-name aliases and structurally verified functional FF models
   account for physical naming and drive-strength changes.
3. `check_compact_clock_tree.py --mapping MAPPING --placement TIED
   --equivalence EQUIVALENCE --output CTS` requires matching receipts and checks
   the restricted inventory. Repeat the equivalence check on `CTS/cts.v`.
4. `route_compact_candidate.py --cts CTS --equivalence CTS_EQ --output ROUTE`
   adds taps/fill/PDN, audits power pins, routes and extracts nominal signal RC.
5. `check_compact_layout.py --route ROUTE` runs the existing independent layout
   audit with a retained runner adapted only for the fresh build root. It keeps
   historical source files untouched, refuses existing signoff output, and
   enforces the12h budget across the audit process group.

CTS evidence is `compact_cts_001/assessment.json`, with34 functional-library
cell types including tie cells. The863-state transition/output proof passes in
`compact_cts_equivalence_001/assessment.json`. Supplied-TT propagated-clock
placement estimates remain positive, but routed RC, complete qualified
nominal15PVT timing and the other release gates are still required.

`check_compact_routed_timing.py --route ROUTE --cts CTS --output NEW_DIRECTORY`
adds min/max wire-RC extraction and four-mode supplied-TT25 diagnostics across
all three wire-RC sets. It retains parasitic annotation reports, rejects known
SPEF name mismatches, applies uncertainty to event clocks, and preserves the
explicit cross-domain exceptions. It cannot qualify nominal15PVT timing or
physical interface assumptions. A missing/negative margin or uncovered net
remains evidence to resolve, not a reason to relax the release criteria.

`check_compact_routed_equivalence.py --route ROUTE --gold-json MAPPED_JSON
--output NEW_DIRECTORY` audits PG-only cell/port projection before the routed
logic relation proof. It requires every removed cell to have no signal
connections, and every projected logical supply port to be unused by logic.
Powered-GDS LVS remains independent. `audit_compact_parasitics.py --route ROUTE
--timing TIMING --output NEW_DIRECTORY` resolves unannotated outputs in OpenDB
and checks the reset SPEF network's endpoint connectivity without claiming
RC extraction fidelity.

The first compact route passes router/Magic DRC and binary logic equivalence,
but fails reference-input hold, electrical slew/load, antenna and aliased-output
pin export. `repair_compact_route.py --route ROUTE --timing TIMING --cts CTS
--output NEW_DIRECTORY` preserves that evidence and attempts isolated output
separation, restricted electrical/hold repair and antenna jumpers. Every
changed route needs fresh equivalence, timing and independent physical checks.

`check_compact_routed_equivalence_v2.py` accepts exports with or without unused
logical VDD/VSS ports; any projected supply must still have no logic connection.
The original checker and reports remain pinned. The first repair clears unique
layout LVS and sampled hold but still fails electrical/antenna checks.
`repair_compact_route_clustered.py` adds `--diagnosis ELECTRICAL_LOG` to the
repair CLI and applies the explicit `cluster_electrical_nets.tcl` topology to
all actual violating nets. Spatial buffering is an implementation heuristic;
new routed/electrical and physical checks must establish its result.

`characterize_compact_propagation.py --route ROUTE --corner fs
--temperature-c 125 --output NEW_DIRECTORY --run` prepares and runs one native
batch after conservative shared-budget admission. Without `--run` it only
prepares. It checks static truth tables, exact extracted-model ports and hashes,
and includes all sensitizing side-input states, three slews and three loads.
The current891-fixture/40-type batch is at one nominal-supply PVT point only.
It contributes raw propagation data, not a qualified timing view; sequential
constraints, output slew, numerical/interpolation and full nominal15PVT coverage
remain open. Do not edit its pinned source or deck while it is running.

`repair_compact_route_clustered_v2.py` adds `--cluster-prefix NEW_PREFIX` for
successive isolated repairs. A tightened-limit diagnostic may guide extra
implementation margin, but the new physical route must be assessed against
the original limits. Prior routes/checkers remain immutable.

`repair_compact_export_names.py --route ROUTE --cts CTS --output NEW_DIRECTORY`
fixes the three observed internal-net/output-port identifier collisions and
checks DEF equality except the NETS names. It preserves all physical geometry
and all public ports. The initial failed guard attempts are retained; completed
export evidence is `compact_export_names_003`. Fresh LVS must validate exports:
a binary relation proof cannot establish the isolation of ideal buffers.

`repair_compact_route_drive_reset.py` takes the repair CLI plus `--diagnosis
ELECTRICAL_LOG`, explicitly upsizes the actual failing drivers within the allowed
set, and inserts six private external-reset leaves. The new reset path requires
fresh physical interface characterization. Existing scripts and receipts remain
unchanged; neither templates nor positive diagnostic setup values qualify it.

`repair_compact_route_drive_reset_v2.py` reuses the six reset leaves and clears
protection during global PG connection, then restores it and asserts full PG
connection before routing. This fixes the retained24-pin failure in the first
reset repair. The guarded route passes12supplied-TT25 mode/RC setup, hold,
slew/capacitance and pulse screens, plus Boolean equivalence, Magic DRC and
unique LVS. Antenna and full nominal15PVT/reset-interface qualification remain
open; this diagnostic result is not a release timing pass.

`prepare_compact_sequential_propagation.py --corner fs --temperature-c 125
--output NEW_DIRECTORY` prepares108clock-toggle/reset-assertion fixtures for
the6FF variants. It launches no native job and does not characterize sequential
constraints. The3native jobs already running remain within the shared limit.
Existing diode model comparisons are revalidated in
`diode_reuse_qualification_001.json`; this does not qualify the whole PLL.

Antenna diode integration uses `prepare_antenna_diode_load.py` and
`repair_compact_antennas.py --route ROUTE --cts CTS --equivalence EQ
--diode-model LOAD_DIRECTORY --output NEW_DIRECTORY`. The auxiliary Liberty
view supplies the explicitly conditional diode input capacitance. It does not
qualify a full load/noise envelope. Check changed routes independently with
`check_compact_layout.py`, `check_compact_routed_equivalence_v3.py` and
`check_compact_routed_timing_with_diodes_v2.py --route ROUTE --cts CTS
--diode-model LOAD_DIRECTORY --output NEW_DIRECTORY`. The logic proof audits
input-only passive diode projection; actual load effects belong to timing.
The timing receipt records reported electrical violations as well as path
slacks. The v2 size-only antenna trial was cancelled: dfstp_1 and dfstp_4
have identical D gate area in the LEF. `repair_compact_antennas_v3.py` uses
three short buf_8-to-D branches and strengthens the measured weak driver.
It is specific to the retained failing route and requires fresh checks.

`run_compact_sequential_propagation.py --plan PLAN_JSON --after
COMBINATIONAL_ASSESSMENT --output NEW_DIRECTORY` claims a prepared deck once,
waits for terminal passing combinational evidence and conservative shared
native capacity, then makes one native attempt. Its total 12-hour limit
includes waiting and assessment. A prerequisite nonpass prevents launch;
there is no identical automatic retry. These raw measurements do not cover
setup/hold, recovery/removal, minimum pulse or MTBF.

`repair_compact_postroute_v3.py --route ROUTE --cts CTS --equivalence EQ
--timing TIMING --diode-model LOAD_DIRECTORY --output NEW_DIRECTORY` performs
an isolated place165 clkbuf_8-to-16 upgrade and one actual detailed-route
antenna repair iteration. It preserves other routed wires and clears both
preset-driver nets after antenna checking so temporary guide wires are not
imported as legal detailed routes. Earlier retained trials fail DRT-1231.
Fresh equivalence, independent layout audit and diode-aware loaded timing are
mandatory before considering adoption; this helper does not qualify a release.

`check_compact_routed_timing_with_diodes_v3.py` reports every violating
slew/capacitance/pulse pin with `-violators -no_line_splits -digits 6`.
Earlier reports showed only the worst row per check type. Zero worst-row
violations still prove those reported limits passed, but complete diagnosis
avoids repairing one displayed pin at a time.

`diagnose_compact_timing_headroom.py` creates a private copy of the supplied
TT library with transition/capacitance limits multiplied by0.9. It checks
actual routed RC at400MHz and selects implementation repairs only. It must
never replace original-limit verification. The incremental electrical v3
helper selects the next larger allowed size, isolating strongest complex
outputs where needed, and adds no diodes. Completed diagnostic closure is
`compact_incremental_headroom_001`; the final original-limit twelve-screen
assessment is `compact_incremental_headroom_timing_001`. Full nominal15PVT
and physical timing/load qualification remain open.

`refine_compact_slew_cases.py --batch BASELINE_DIRECTORY --slew
SLEW_AUDIT_DIRECTORY --output NEW_DIRECTORY` makes one focused numerical
refinement for up to six measured ambiguous zero-load XOR/XNOR fixtures.
It waits for conservative shared capacity within a total12h budget, halves
the maximum step and tightens tolerances by10, preserves all raw threshold
crossings, and reports50%delay changes. Runtime status is excluded from the
immutable final artifact manifest. This is not a numerical-domain enclosure
or a timing-library qualification, and no identical retry is automatic.

`audit_compact_sequential_completion.py --run TERMINAL_RUN --output
NEW_DIRECTORY` checks terminal producers and every original input/raw hash,
preserves the original measurements, and replaces its known mutable-status
manifest reference with a frozen final snapshot. It does not remeasure the
waveform or qualify setup/hold/MTBF. Prefer the audited receipt for reuse.

`benchmark_dco_linear_solver.py --reference-result COMPLETED_RESULT_JSON
--solver KLU2|BASKER --threads 1..4 --output NEW_DIRECTORY` runs one10ns prefix
with the original circuit/tolerances/step limit, reports solver costs and raw
output/edge differences, and enforces a total12h budget with shared admission.
Requested OpenMP thread count is recorded, not assumed to be achieved. No
backend is adopted from this short benchmark; full-duration fidelity and
numerical-domain validation remain necessary.

The v2 solver benchmark also permits `--solver KLU` to control for thread
policy: the completed baseline used default BLAS threading, while probes set
OPENBLAS_NUM_THREADS=1 and MKL_NUM_THREADS=1. Compare this control before
attributing performance changes to the backend alone. Original native jobs
and their pinned inputs remain unchanged.

## Capture and asynchronous-release boundary observations

`prepare_compact_capture_boundaries.py --corner fs --temperature-c 125
--output NEW_DIRECTORY` prepares198 fixtures over all six used FF types:
data rising/falling and asynchronous release at eleven offsets from the
clock's50%crossing. The initial scan uses200ps full ramps and5fF load.
Thirty-six separated +/-1ns controls have asserted expected captures;
near-boundary states, ambiguous levels and extra output crossings are retained.
This sparse scan does not establish setup/hold/recovery/removal tables,
interpolation, numerical accuracy, metastability or a timing envelope.

`run_compact_capture_boundaries.py --plan PLAN --output NEW_DIRECTORY` runs
one batch with shared admission, a total12h budget, no automatic identical
retry and raw terminal-waveform checks. Invoke it through the canonical host
absolute script path with both workspace binds. It is prepared but not queued
behind the current combinational jobs. `check_capture_boundary_observer.py`
validates bookkeeping against an independent ideal edge-triggered oracle and
five faults; its synthetic results contribute zero native timing passes.

The combinational v2 runner requires `--canonical-workspace HOST_ROOT` and
accepts `--total-budget-s` in(0,43200]. It rejects an alternate container-root
launch before creating output. This fixes an unlaunched SS125 queue wrapper
whose relative script path resolved ROOT to `/work/OpenPLL` while running
native outputs used the canonical host prefix. The original wrapper and
receipts are retained; its replacement preserves the original budget start,
so the handoff does not reset the12h limit. No native case was retried.

## Frozen-candidate closed-loop driver bring-up

`diagnose_frozen_closed_loop_v2.py --ki 1 --kp 4 --output NEW_DIRECTORY`
compiles the exact frozen candidate and phase-continuous VPI driver, then runs
reset acquisition for all four modes. Run inside the release container using
the host absolute script path. All48x256DCO frequencies and the deterministic
phase detector's pulse timing are explicitly synthetic. This complete grid is
for driver bring-up only and contributes no physical calibration evidence.

The saved edge and complete tuning traces can be evaluated with
`functional_acceptance.py` at enabled_ns100 and observation_stop_ns220000.
`audit_closed_loop_driver.py --diagnostic DIRECTORY --output NEW_DIRECTORY`
independently verifies Decimal phase conservation under the actual RTL tuning
sequence and exact identity of delivered oscillator rising edges. It verifies
source/artifact hashes before auditing. The audit does not validate detector
physics. Missing-edge, wrong-level and wrong-frequency faults are rejected.

Retained diagnostics show why tracking cannot stand in for lock: KI4/KP0
reaches tracking in all modes but fails sustained trace criteria. KI1/KP8
passes100/250MHz while300/400MHz exceed the phase-span limit. KI1/KP4 passes
all four synthetic trace cases, including the existing acquisition deadline
and final sustained windows. These are diagnostic configurations, not selected
release gains. Physical model/coverage/interface gates and all60qualification
cases remain open, as do directed mode-change and assembled signoff coverage.

## Independent DCO duration comparison

`prepare_dco_duration_probe.py --code 128 --stop-ns 160 --output NEW_DIRECTORY`
prepares a longer run of the completed160-load/coarse1TT27C1.8V waveform.
Fine247 and200ns are also supported. Source waveform, extracted circuit,
PDK/tool provenance and deck hashes are verified. Removing instrumentation
measurements and changing the transient stop argument are the only netlist
changes; every remaining circuit/initialization statement is preserved.

`run_dco_duration_probe_v2.py --canonical-workspace HOST_ROOT --plan PLAN
--output NEW_DIRECTORY --after-launch PRECEDING_RUN/launch.json` waits for the
preceding external runner to finish admission before competing for a native
slot. Dependency wait, native execution and assessment share one total12h
budget. It retains all predeclared windows, independently checks frequency
and half-window drift with Decimal arithmetic, and compares the first80ns
with the completed reference. KLU and explicit single-thread BLAS are used.
No favorable window or calibration model is adopted from this observation.

The160ns fine128 probe is now waiting for the SS125 launch. Fine247 is prepared
but not queued. The historical80ns fine128 run took3.201h; its linear160ns
projection is6.403h, not a runtime guarantee. Validation checks exact statement
preservation, three actual waveform windows, eight synthetic measurement
windows and three malformed-input controls. Full localLSB/numerical/model
coverage and combined calibration uncertainty remain separate requirements.

## Directed mode-change driver diagnostic

`diagnose_frozen_mode_changes.py --output NEW_DIRECTORY` runs all12 ordered
changes between100/250/300/400MHz using the exact frozen RTL and the previously
checked synthetic KI1/KP4 model. Each case first runs220us after enabling,
changes the divider without external reset at220100ns, and then runs another
220us. It applies the unchanged trace checker separately before and after the
change, with explicit horizons220000ns and440000ns. All12cases pass both
synthetic trace phases in `frozen_mode_changes_diagnostic_001`.

`audit_frozen_mode_changes.py --diagnostic DIRECTORY --output NEW_DIRECTORY`
checks complete ordered-pair coverage, pinned sources/artifacts, the actual
divider transition in the state trace, tracking release/reacquisition, both
trace verdicts and the absence of any oscillator reset after time0. Per-case
Decimal phase integration and output-edge identity cover2893462clock edges
and1446728delivered rising edges. These are synthetic driver diagnostics,
not the required12directed physical mode changes at each of15PVT points;
qualified whole-PLL cases remain0 and release gains remain unselected.

## Routed wire-load observations

`audit_compact_characterization_loads_v2.py --route ROUTE --timing TIMING
--plan COMBINATIONAL_PLAN --output NEW_DIRECTORY` compares the actual OpenDB
output/net inventory with the three normalized extracted SPEF views. It decodes
one quoting layer in both namespaces, preserves case/literal backslashes and
rejects canonical-name collisions. The initial raw-name inventory is retained;
its101unresolved used-output names perRC are quoting mismatches, all resolved
by the collision-checked decoder in `compact_characterization_load_audit_002`.

All40combinational types have resolved used-output wire totals in all3RC sets.
No reported wire-only total exceeds that cell's maximum prepared fixture load.
For the three cell types with unloaded nonmonotone waveform cases, minRC
minimum reported totals are1.9928fF(xnor2_4),6.60931fF(xor2_2) and83.8038fF
(xor2_4). These PIN_CAP NONE totals exclude sink/diode capacitance and do not
establish effective-load floors or bounds under coupling. No waveform case is
excluded and the three ambiguous zero-load slew cases remain unresolved.
The audit does not check input slew or qualify full nominal15PVT load coverage.
A parser control preserves case and rejects wrong units, negative/nonfinite
capacitance, duplicate nets and unknown name-map entries.

## Independent simulator observation of the envelope counterexample

`crosscheck_hs_ngspice.py --controller-pid PID --output NEW_DIRECTORY` runs the
retained FS125C1.8V NAND2_2 A-to-Y case with the existing ngspice47 binary.
`crosscheck_hs_ngspice_refined.py` repeats that distinct observation at1ps
instead of2ps and10x tighter tolerances. Geometry, extractedRC, stimuli and
load stay pinned; temperature/tolerance/control syntax is translated for
ngspice and geometry scaling is explicit at1u. These probes do not patch PDK
models or replace any original native result.

Each small reference is capped at60s. The script temporarily stops only the
verified dispatch process to reserve a fourth slot, leaves native children
running, and resumes dispatch in a finally block. The two observed dispatch
pauses are16.78s and17.11s. Both probes complete; combined native count never
exceeds four and dispatch/native identities are reverified afterward.

Ngspice's rising-output delays are37.0310604ps and37.0298080ps versus Xyce's
36.5481853ps. `audit_hs_ngspice_crosscheck.py --output NEW_DIRECTORY` checks all
source/raw hashes and independently remeasures four delays with Decimal
arithmetic. The refined rising delay remains0.7906711ps below the sampled fast
bound37.8204791ps. The tested FF/SS envelope therefore remains rejected.
This single case neither resolves the cross-simulator/model-version difference
nor qualifies a numerical/physical timing domain or any release gate.

## Retained nominal detector scope and static-bias sensitivity

`review_bbpd_nominal_scope.py --output NEW_DIRECTORY` checks the retained
nominal-only detector summaries and point receipts:30isolated phase-transfer
curves across15PVT points and two input slews, plus60coupled receiver checks
at+/-200ps. The isolated transition brackets are25ps wide and their farthest
nominal endpoint is100ps from zero. Raw historical waveforms are not reaudited
by this receipt, and old receiver/load/rail assumptions are preserved.

`diagnose_frozen_static_bias.py --ki 1 --kp 4 --threshold-ps -100 --output
NEW_DIRECTORY` (also+100) exercises all four modes at those static threshold
extremes, using the synthetic DCO and ideal detector pulse timing. Both
four-mode groups pass the existing trace criteria and independent clock audits.
At400MHz the final phase means are approximately-99.93ps/+100.02ps and spans
149ps, within the stated250ps mean/span limits for these diagnostics.
A constant offset affects phase mean; these runs do not enclose dynamic
aperture, near-coincident capture, metastability, load or noise behavior.

The new compact receiver requires a matching detector macro and port/reset
convention, current receiver/RC/pin-load enclosure, valid clock/reset/rail
assumptions and independent dynamic holdouts before physical reuse. Release
models/gains and all60physical whole-PLL cases remain unqualified.

## Guarded admission and completed TT27 characterization

The TT27C1.8V combinational batch completes891/891raw propagation fixtures.
Its888/891strict output-slew observations retain the same ambiguous cases
774/837/873 as FS125. `compact_propagation_tt27_domain_review_001` records all
voltage extrema and the largest repeated-opportunity delay difference10.7498ps.
All594positive-load cases stay within the conditional diode bias range;
60of297zero-external-load cases leave it. These observations do not establish
routed voltage/effective-load bounds or adopt a timing model.

`guarded_native_admission.py` serializes external launches and stops only the
verified dispatch process while checking reservations and launching Xyce.
Dispatch resumes once the new native is visible, so its existing accounting
sees the occupied slot before scheduling more work. Native children continue.
The guard accepts one available slot, rejects pending/preparing DCO engines,
and holds a separate external-admission flock. Other external admission owners
must already have launched or use this guard. The actual fifth-launch negative
control rejects before Popen and verifies dispatch resumes with the same four
native identities (`guarded_native_admission_validation_001`).

The unlaunched duration wrapper is retired after verifying it is childless and
has no launch/log. Its old native_run.json remains immutable. The v3 runner
uses native_run_v3.json and the same output/plan, with a handoff receipt and an
absolute boot-time deadline equal to the original process start plus12h.
It launches the160ns check in the fourth slot with a51.84ms dispatch stop;
no native work or budget restarts. Use the v3 claim/status for current ownership.
SS125 is running. `run_compact_capture_boundaries_v2.py` is now queued with the
same guard and its own total12h deadline; it does not pause dispatch while the
workspace is already full. Observer semantics match the validated first version.

## Numeric-to-physical DCO control compatibility

`check_dco_control_encoding.py --output NEW_DIRECTORY` compiles the exact
frozen DigitalCore with the AcquiringCore's actual parameter block and drives
its normal DLF_Clear seed-load path. All48coarse x256fine values are sampled
after the registered control pipeline. The resulting12288code/thermometer
pairs match304SPICE fixture bases (256fine and48coarse) emitted by the actual
native DCO generator, anchored to a completed native input deck. A DUT with
wrong fine polarity is rejected. This adds no SPICE simulations.

`audit_dco_control_binding.py --output NEW_DIRECTORY` verifies all source/raw
hashes and305ordered instance bindings (304bases plus the retained native deck)
against the actual308-port extracted macro. Fine control has255pins and is
active low; coarse control has47pins and is active high. The latest routed
Boolean-equivalence receipt and exported port widths also match the interface.

Evidence is `dco_control_encoding_001/assessment.json` and
`dco_control_binding_audit_001/assessment.json`. This verifies settled encoding,
including reset/rail codes, not analog startup, code-step glitches, phase
response, physical frequency models or a final assembled connection. Tracking
still requires fine8..247; outside-range values used here are encoding tests.


## Current compact event receiver fixtures (2026-10-19)

`extract_compact_event_receiver.py` traces the current routed candidate's
event-toggle cone from the equivalence projection and maps its exact SPEF
endpoints. The fixture contains two capture flip-flops, two XNOR gates and ten
clock buffers, with all17signal nets and four outside flip-flop input loads.
Nominal/min/max wire RC is retained, internal coupling is counted once and
omitted aggressors are static. Outside pin capacitances use the supplied TT25
scalar/range maximum; this is a conditional diagnostic load, not a qualified
PVT/Miller/noise bound. The ideal event-reset cut excludes reset generation.

`audit_compact_event_receiver.py` checks all102functional cell-pin bindings
across the three views against actual model port order, supply connections,
primitive inventories and pinned input/artifact hashes. Nine in-memory faults
(wrong supply, missing wire, missing leaf load in each view) are rejected.
Evidence: `compact_event_receiver_001/assessment.json` and
`compact_event_receiver_audit_001/assessment.json` under the active400MHz build
root. No new native simulation was launched and no physical gate was promoted.
The TT250 DCO endpoint pair, SS125 combinational batch and160ns DCO duration
probe continue; the sequential capture-boundary scan remains budgeted in queue.


The current receiver capture pilot is prepared in
`current_receiver_capture_tt27_002` and queued by
`check_current_receiver_capture.py`. It checks TT27C/1.8V/maxRC at both signed
200ps phase offsets and20/200ps input edges (four cases). It reuses the retained
fixed-rail sampled BBPD, verifies the historical model digest across its
container/canonical path alias, and binds the current14-cell receiver.
It waits for the earlier sequential-boundary scan to launch before competing
for guarded native capacity. One12h total deadline includes that dependency
wait, admission and all four cases; no identical retry is scheduled.
The prior empty preparation directory is retained with a failure explanation;
it launched no simulator. This pilot does not qualify generated reset,
metastability, PVT timing, dynamic pin loads, power or noise.


## Provisional current-candidate top connectivity

`prepare_candidate_top_v2.py` links the actual current routed AcquiringCore
netlist, the160-load DCO candidate and the sampled detector using explicit
macro declarations. The detector reset uses BBPD_RESET_N, its reference uses
REFCLK and its feedback uses CLKDIV_RETIMED. DCO reset uses RESET_N. The302
thermometer controls and two detector feedback bits remain internal. Gains
and the feedback divider remain explicit configuration inputs.

`candidate_top_004` contains the wrapper, declarations, Yosys hierarchy/driver
check and structural audit. All317scalar analog-macro LEF pins match expected
port sets; swapped detector reset and reversed fine-bit controls are rejected.
All functional standard cells use the existing library. Tap/filler/antenna
instances are preserved as physical-only declarations; no instances or wires
are deleted to pass linking. The routed digital netlist has implicit power,
so physical assembly must connect it using its existing PG geometry.

The earlier attempts are retained:001/002failed on missing physical-only
declarations;003links but exposes internal control buses as diagnostic ports.
004is the corrected structural integration candidate. This is not an assembled
layout: intermacro wire RC, macro interfaces, PG/noise, DRC/LVS and all other
release gates remain open. No native simulation was added or interrupted.


## Current physical assembly inputs and provisional macro floorplan

`prepare_digital_macro_abstract.py` exports the current routed digital database
with occupied routing layers blocked. The357macro pins preserve all406source
pin rectangles, directions and signal uses exactly. The GDS/database identities
match the current digital signoff receipt. Physical digital power pins are
VDD/VSS, which internally connect the standard-cell VPWR/VPB and VGND/VNB
respectively; this differs from the separate analog-macro body pins.
Evidence: `digital_macro_abstract_001/assessment.json`.

`candidate_floorplan_002` places the current454.615um-square digital macro at
(20,20), the125um-square160-load DCO at(515,20), and the120um-square sampled
detector at(515,185), within a660x500um provisional die. The nearest digital/DCO
channel is40.385um. These dimensions are initial assembly choices, not a
congestion/RC/noise-qualified floorplan. The first attempt is retained; it
stopped before placement because OpenROAD required a standard-cell site.

`audit_candidate_floorplan.py` checks674actual macro ITerm connections, all
three bounding boxes and lack of overlap. It verifies the two explicit digital
power connections, macro reset/clock wiring and thermometer bit identities.
Wrong detector reset, reversed fine-code binding and wrong digital power are
rejected. The physical top differs from the checked structural top only by
adding digital VDD->VPWR and VSS->VGND. Analog body rails stay separate.

The database and DEF are preparation for intermacro routing. Top pin placement,
power grid, route/RC extraction, assembled DRC/LVS/antenna/density/integrity and
physical timing/noise remain open. Missing macro Liberty warnings retain the
known unqualified timing scope. No timing or release gate is promoted. Four
native analog simulations and the existing budgeted receiver queues continue.


## Intermacro routing-capacity screen

The first355-net global route (`candidate_global_route_001`) overflows21130
resources. Digital thermometer pins are split152on the top edge and150on the
bottom edge, so the original narrow perimeter channels do not suffice. A
1000x850um provisional floorplan (`candidate_floorplan_003`) places digital at
(150,150), oscillator at(750,150), detector at(750,400). The unchanged674macro
connections, bounding boxes and non-overlap pass `audit_candidate_floorplan_v2.py`.
This larger placement with met2-met4 and two-grid macro extension still has
2457overflow (`candidate_global_route_002`).

Allowing signal routing on met1-met4 and using actual macro obstructions without
an additional halo gives zero global overflow (`candidate_global_route_003`).
It preserves355guide-covered signal nets,674macro bindings and55top pin shapes,
independently audited by `audit_candidate_global_route.py`. Reported signal
wirelength is251359um. All earlier congested results remain preserved and marked
nonpassing. The layer and spacing changes have not passed detailed DRC; zero
global overflow does not establish pin accessibility or detailed-route success.

Metal5is reserved in this screen. A power grid must be constructed and routing
capacity rechecked with its actual obstructions before final signal routing.
The standalone DCO calibration decks include extracted internal loading but no
assembled external PLLOUT receiver/interconnect load. Their measurements remain
unqualified for the assembly; final wire/pin loading and its effect on DCO and
BBPD behavior must be enclosed in the physical models. No native check is
restarted, no frequency model is adopted and no release gate is promoted.


## Main power grid and routing with its obstructions

The analog macro LEFs expose VPB/VNB as small met3 SIGNAL pins. These retain
separate top-level body-bias connections and are included in ordinary routing;
they are not silently tied to the main rails. The main VPWR/VGND grid uses
met4/met5 rings and stripes. The first generated core and macro grids were
disconnected. Explicit70met5bridges close the gaps, each outside all macro
bounding boxes with3um clearance and1.6um clearance from opposite-net met5
shapes. The two main rails pass `check_power_grid -floorplanning`.

`candidate_power_grid_audit_001` independently compares source/output database
geometry, checks that the only70added rectangles match the bridge manifest,
preserves existing shapes/vias and all674macro connections, and rechecks bridge
clearances. This is a connectivity screen, not full DRC, EM/IR or noise signoff.
The current grid is `candidate_power_grid_013`; failed attempts remain retained.

An isolated special-router attempt crashed before saving a database. Exact
OpenROAD dcf36133source is pinned in `pdn_source_audit_001` with matching Git
blob identities. Its ring selector finds21VPWR/19VGNDcandidate shapes in this
mesh while its group array is fixed at four. That path was abandoned; the final
bridges do not use temporary aliases, change pin names or modify OpenROAD.
Official command context: https://openroad.readthedocs.io/en/latest/main/src/pdn/README.html

`candidate_global_route_004` routes all357signal nets including both body-bias
nets with zero global overflow and rechecks both main rail connections after
pin placement/routing. The independent v2guide audit preserves674macro
bindings and55placed scalar top pins. Reported wirelength is252777um.

Detailed routing is running in `candidate_detailed_route_002`, with current
owner and input manifest in that directory. The first attempt stopped before
routing because the advertised bottom/top layer flags are deprecated. The
corrected invocation uses set_routing_layers and retains the first attempt's
absolute12hdeadline, including startup/correction time. No identical retry is
scheduled. Detailed DRC/route connectivity, antenna, extracted RC, assembled
LVS/density/integrity/noise and physical model/load closure remain open.


## Detailed top routing completed

`candidate_detailed_route_002` finishes detailed routing with zero reported
router DRC violations, an empty route.drc and both main rail connectivity checks
passing. It finishes within the original first-attempt12hdeadline.
`candidate_detailed_route_audit_001` independently verifies all357signal nets
have detailed wires (including VPB/VNB), preserves all674macro connections and
compares every power special-wire rectangle/via bounding shape against the
audited source grid: no power geometry changed during signal routing.

This closes the provisional top's routing-feasibility step, not assembled
physical signoff. Full streamed-layout DRC/LVS, antenna/density, extracted
intermacro RC and EM/IR/noise remain open. In particular the exported digital
macro LEF has no ANTENNAGATEAREA/ANTENNADIFFAREA annotations. A top-level antenna
pass that ignores internal macro gate/diffusion/metal geometry would not prove
the requirement; derive qualified hierarchical antenna models or perform an
applicable flattened geometry check before promoting that gate. Existing
standalone macro antenna receipts retain their original limited context.

The four native analog simulations and the two existing receiver queues
continue. No frequency/interface model, loop gain or final release candidate
is selected or qualified by the routing result.


## Completed SS125 observations and assembled-layout repair

The SS125/1.8V batch completes891/891propagation observations and888/891strict
slew observations. Cases774/837/873 retain the same ambiguous output crossings
as TT27/FS125. `review_completed_propagation.py` verifies terminal source hashes
and independently recomputes their crossings with40-digit Decimal arithmetic
from19354raw rows. All594positive-load outputs stay inside the conditional
diode bias range;64of297zero-load outputs leave it (overall-.437827..2.39953V).
The largest repeated-opportunity delay difference is14.6694ps, case839input
rise. These observations neither exclude zero-load cases nor qualify a library.
The FS125capture-boundary scan starts after the batch frees its native slot.

The first assembled GDS retains all source macro geometry and labels, but full
Magic DRC finds256rectangles and LVS detects a VPWR/VGNDshort in the added top
power geometry. All three underlying macro comparisons pass. Generic PGstraps
and vias inside the macros are replaced with connections to their existing
met5power ports; source macro GDS and all ordinary signal DEF routes remain
unchanged. No physical failure is waived.

The repair preserves separate external legacy VPB/VNB connections. The actual
DCO/BBPDpowered netlists leave those top ports unreferenced and connect all cell
well pins to VPWR/VGND; these ports do not provide independent body-bias control.
This corrects the earlier body-bias description.

Port-based power repair then passes LVS. Remaining met5width errors are addressed
by legal1.6um via wire pads and pruning unprotected external tails. A completed
iteration (`candidate_layout_checks_003`/`candidate_lvs_003`) has Magic DRC0and
a unique complete LVS match, but two cleanup-marker coordinates were off the
5nmmanufacturing grid. `repair_assembly_macro_power_v4.py` snaps removal masks
outward onto that grid and asserts every generated met5coordinate is on grid.

The current corrected design is `candidate_macro_power_repair_007`, streamed
and audited in `candidate_stream_006`: all three macro geometries/labels and
nine shared definitions match their sources. Current checks are
`candidate_layout_checks_004` and `candidate_lvs_004`, sharing the original
layout-check12hdeadline. Initial/native failures and all earlier candidates
remain preserved. Antenna/density, PI/noise, routed load/RC models, complete
nominal15PVT timing/calibration and the60physical wholePLL cases remain open.


## Exact assembled GDS DRC/LVS evidence

`candidate_assembled_layout_audit_001/assessment.json` binds full-style Magic
DRC0and complete unique LVS to the exact `candidate_stream_006/assembly.gds`
and `candidate_macro_power_repair_007/route.odb`. All55top pins match; all three
macro circuits are expanded in LVS. There is no Magic input-grid snapping.
All generated met5coordinates lie on the5nmgrid, the source macro geometries
and labels are preserved, and ordinary signal routes match the original
detailed route. The audit also retains the real256-DRC/shorted-power negative
case, which is rejected. These are DRC/LVS passes, not complete physical signoff.

The FS125capture-boundary batch completes198/198observation-integrity checks
and36/36separated controls. Its outcome review preserves all near-boundary
results; none has multiple post-test50% edges. Constraint/MTBF/model enclosure
qualification remains open. The current max-RC receiver pilot also completes
4/4signed two-event captures at TT27C/1.8V, with both200psphase directions and
20/200psinput edges. It still excludes parent intermacro wire RC, generated
reset, fullPVT/load/noise bounds and near-coincident/metastability holdouts.

A fixed20..60nslive DCO prefix screen measures244.8786/255.4641MHz at TT/coarse4/
fine8/247, provisionally surrounding250MHz. Only frozen prefix copies are
hashed; the ongoing native checks and growing waveforms are untouched. This
does not claim native completion, settled frequency or a qualified range.

After the receiver owner terminates, `run_dco_duration_probe_fresh.py` admits
the prepared coarse1/fine247160nsprobe through the shared guard. Admission
moves the workspace from three to four native analog processes, with only
~52msdispatch pause and no paused native children. It retains all eight
predeclared windows and independent Decimal comparisons; one total12hbudget
includes verification/admission/assessment. The fine128duration comparison
and TT250range endpoints continue. No numerical window or frequency model is
adopted before convergence evidence is complete.

Antenna/density, measured power/jitter and PI/noise, actual routed-interface
load/RC bounds, full nominal15PVT timing/calibration and the60physical wholePLL
cases remain open. The goal and all release-qualification flags remain active
and unqualified; no release tag or candidate selection is made.

The exact repaired assembly now has three parent-wire RC views in
`candidate_interconnect_001`. `candidate_interconnect_audit_002` matches all
357 net endpoint sets (721 boundary endpoints per view) to the current routed
database, proves every wire graph connected, reconciles wire capacitance totals,
and exports coupled parent-wire SPICE with each reciprocal coupling once.
The six legacy INOUT endpoints are explicitly reconciled with OpenRCX's I
encoding; their database directions remain preserved. The initial conservative
direction-check rejection is retained in `candidate_interconnect_audit_001`.
`candidate_interconnect_validation_001` reads the exported SPICE back and checks
every resistor/capacitor edge and value against raw SPEF; all12 injected endpoint,
direction, connectivity and coupling faults are rejected across the three views.

PLLOUT wire-only totals are0.185289/0.421899/0.464795pF in nominal/min/max RC
views, excluding receiver/pad loads. These are coupled circuit quantities, not
fixed effective capacitances or demonstrated delay/frequency bounds. Macro pin
and interior RC, cross-boundary coupling accuracy and external integration loads
still require matching models. Earlier unloaded DCO checks remain intrinsic
checks and do not establish assembled oscillation or frequency coverage.

`check_assembled_receiver_capture.py` prepares four TT27C/1.8V diagnostics with
the full357-net max-RC parent network and current max-RC14-cell receiver. REF,
CLKDIV and reset boundary sources drive their actual macro/port locations;
detector outputs travel through parent wires before reaching the digital
receiver. Other parent-net drivers are explicitly static. The guarded runner
waits for native capacity with one total12hdeadline including admission wait;
it does not add a fifth native job or retry an identical run. Generated reset,
dynamic omitted loads/aggressors, external pad loads, fullPVT/near-coincident
noise/metastability qualification and loaded-DCO closure remain open.

The first assembled-RC capture case starts native transient analysis at22:51UTC
after the TT/coarse4/fine24780nsendpoint completes. Guarded admission records
three native jobs before and four after, ~40msdispatch pause, and no paused
native children. `qualification_progress_022.json` records the actual launch;
no capture result or loaded-DCO qualification is claimed yet.


### 2026-10-19: assembled density repair and antenna localization

The exact unfilled assembled GDS fails all175 constrained checks in the PDK's
stock density workflow (195raw70umtiles,24nominal700umstepped windows with the
PDK's clipped-edge convention, plus global checks). A separate PDK-generated
fill pattern reduces failures to25, allmetal5. The stock-filled candidate passes
fullMagicDRC0 but is not selected. `repair_assembled_metal5_fill.py` replaces
only the newly addedmetal5fill; it preserves originalmacro/parent geometry,
originalmetal5fill, all labels and the other seven newfill layers. It checks
1.6umclearance/minwidth and5nmgrid, with an8umtile/10umpitch pattern.

`candidate_stream_filled_002` now passes all175PDKdensitychecks, independently
recomputed from rawtiles by `audit_assembled_density.py`. Global densities are
FOM43.2%,LI52.3%,M1 48.2%,M2 45.6%,M3 44.7%,M4 43.9%,M5 59.2%; poly11.3%
is reported without inventing a numerical limit. The currentfilledGDS is a
separate pendingcandidate. DRC/extraction and completeLVS are running in
`candidate_layout_checks_filled_002`/`candidate_lvs_filled_002`, sharing the
originalassembled-layout12hdeadline. No oldpassingGDS or database is overwritten.
PriorparentRC explicitly excludesfill; matching fill-aware electrical evidence
is required before adopting the filled candidate.

`run_assembled_antenna.py` completes the PDK's transistor-awareMagicmethod on
the unfilledexactassembly, with5053feedbackrectangles (not5053uniquenets).
The PDKdeclares itsmodelpartial and diode-diffusioncoverage remainsunqualified.
A cleanphysicalinverter has0feedback, while an injected1000umlocalinterconnect
on itsgate triggers10feedbackrectangles. `candidate_antenna_localization_002`
resolves680exactrectangularMOSgateboxmatches to137extractednets, including
131DCOthermometernets and REFCLK,CLKDIV_RETIMED,BBPD_RESET_N,KI[5],DLF_CODE[3].
This is partialdiagnosticlocalization, not proofthat allviolatingnets are found
or that a diode/routing repair is qualified. Antenna remainsopen.

The firstparent-loadedcapturecase (TT27/1.8V,phase-200ps,edge20ps) completes
and passes signedtwo-eventcapture. The remainingthree cases wait for guarded
capacity within their originaltotal12hbudget; four nativeDCOjobs remainlive.
This capture evidence applies to the unfilledparentRC and fixedrail/resetcuts,
not to finalfilledphysicalmodels. TT/coarse4/fine8/247 nativewaveforms now
complete and bracket250MHz at244.878858/255.474846MHz. Tenfixedwindow checks
with independent40digitDecimal comparisons show fine247's20..80nsdrift is
32.2676kHz, above the25kHznecessarycap. Allwindows are retained and no window,
calibration or loadedmodel is adopted. The review saved itscompleteassessment
before a console-summarykeyerror; `dco_tt250_window_review_completion_001`
independently rechecks all10results, and a v2script fixes only futureprinting.
No nativecase is repeated for that reportingerror.

`qualification_progress_023.json` and the mutableimplementationassessment bind
these receipts and liveowners. Full15PVTtiming/calibration, antenna, matching
loaded/fill-aware models, reset/CDC, PI/noise, physicaljitter/power and the60
physicalwholePLLcases remainopen. Allrelease/adoptionflags remainfalse.


At23:13UTC the repairedfilledcandidate completes fullMagicDRC0 and uniqueLVS,
with allthree macro circuits expanded and55matching top pins. The sameGDS
passes175/175installedPDKdensity checks, and its physicalbbox is independently
verified as0..1000um by0..850um. `candidate_assembled_layout_audit_filled_002`
and `qualification_progress_024.json` bind allthree results to the exactGDS.
The mutableassemblyoverview now points to this filledGDS and retains historical
unfilledstream/audit pointers. Its database still describes conductive wires
and power; floatingfill is a separateauditedGDSoverlay. ExistingparentRC and
loadedcapturemodel exclude thisfill and are explicitly not finalfilled models.
Antenna, matching fill-aware electrical/model/timing and remainingreleasegates
stayopen; the fullphysicalsignoff/release/adoptionflags remainfalse.

`antenna_localization_geometry_validation_001` additionally checks all680
localizedgateboxes against the actualGDS poly/diff polygonintersection. All
are realMOSgategeometry at the inferred5nmcoordinate scale. This strengthens
localization, while incompletefeedbackcoverage and antenna-rule qualification
remainopen. `qualification_progress_025.json` records this addedproof.


### 2026-10-19: antenna rule semantics, formation connectivity and first repair

`antenna_rule_semantics_audit_001` corrects the earlier interpretation of the
PDK's antenna settings: partial means per-layer ratio, not a declaration of
incomplete coverage. The implementation computes diffusion credit; its displayed
limit is normalized to the maximum layer limit. UpstreamMagic8.3.623source is
retained with verifiedGitblob identities alongside the publishedSkyWater rule.
The defaultngspicestyle makes the n-diffusiondiode anMSUBCKT, which also enters
Magic's sensitive-gate mask. The same1000umcable passes with one diode in that
style; with built-inngspice(orig), one and two diodes fail and three pass.
The publishedMOS-onlygate denominator independently rejects the one/two-diode
cases even using only the unambiguousstraightcable sidewall lowerbound.
No installedPDK or binary is modified. Nativeantenna work now usesorigstyle.

The currentfilledGDS is checked again with the correctedstyle and debugoutput:
151reported violations,5053feedbackrectangles,137uniquenets. Everyreportedgate
and net is localized in `candidate_antenna_localization_003`; the geometry
matches the independentlyvalidated680gateboxes. A separateKLayout formation
connectivity audit passes150full-stack gate/portbindings and150wrong-port
controls. All143DCOrecords reach their externalports at the failing layer;
the twoBBPDREF/divider metal2records cannot reach their metal3ports yet and
need internalprotection. Externalprotection remains topologically possible
for the other reportedportcases. This is not a complete antenna-area checker.
The stockMagic implementation starts from onegate per finalnet, so coverage of
all disconnected intermediate forming-subnetworks remains an explicit concern.

`repair_compact_internal_antenna.py` replacesFILLER_19_546 with oneHSdiode_2
at the identical272.160/76.590umsite andMXorientation, on electrical_root_33_out
near electrical_branch_124/A. The remaining22635componentrecords and allmacro
pinshapes/locations are unchanged;32existing regularnetrecords change during
incrementalrouting. NewregularVDD/VSSconnectionrecords are power metadata,
not newsignalnets. The isolatedcore now passes zero router and fullMagicDRC,
uniqueLVS,84904/84904powerconnections,863state/output equivalence functions
with wrong-reset rejection, and all12TT25RC/mode timing screens. Reported
400MHzmargins remain+.747114nssetup and+.022886nshold. The MOS-onlyantenna
check has0feedback. `compact_internal_antenna_closure_audit_001` binds these
results; they do not qualify the full15PVTtiming or finalassembly.

The repairedcore is retained as a separateunadoptedcandidate until integration
and remainingprotection/model checks pass. Existingfilledassembly DRC/LVS and
175densitypasses retain their exact priorGDS identity. DCOintrinsicrange and
duration jobs continue with the original oscillator; no fifthanalog process or
identicalnative retry is introduced. `qualification_progress_026.json` records
thisprogress. Release/adoption flags remainfalse and the fullgoal staysactive.


### 2026-10-20 — Detector protection and repaired-macro integration

Implemented `repair_bbpd_internal_antennas.py`: two local decap12 sites become
same-footprint decap6 + decap4 + HD diode2 groups on REF and CLKDIVR. All 13
functional cells, both flip-flops, retained placements and macro ports remain
identical. Only the REF and CLKDIVR existing routed signal records change.
The identity checker initially rejected regular POWER/GROUND endpoint metadata
added by explicit rail attachment; comparison now excludes PG pins while
requiring exact macro ports, functional signal bindings and bad-clock/diode
negative controls. No native simulation was repeated for that metadata fix.

The detector candidate passes full Magic DRC (zero), unique LVS and a zero-
feedback MOS-only antenna scan. Independent GDS topology confirms both known
metal2 gate failures now reach distinct physical diode diffusions before
higher metal forms; wrong-diode probes are rejected. The actual HD diode
geometry is 0.4347 square microns with 2.64 micron perimeter. The GDS boundary
is exactly 120 by 120 microns, resolving the Magic boundary-redefinition warning.
`bbpd_internal_antenna_closure_audit_001` binds the results. Diode input loading
and reduced decoupling still require fresh analog checks; complete coverage of
all forming-subnetwork ratios is not claimed.

`stream_candidate_assembly_v6.py` creates a separate unfilled candidate with
both the repaired core and detector, preserving each source macro's geometry
and labels. The parent route and oscillator geometry remain unchanged. Full
assembled DRC/extraction and LVS against the matching repaired netlists are
running in `candidate_layout_checks_repaired_macros_001` and
`candidate_lvs_repaired_macros_001`, under the original shared layout deadline.
The previously passing filled assembly retains its exact historical identity;
its fill, RC and qualification receipts are not transferred to the new GDS.
Four existing DCO jobs continue, without a fifth analog process or identical
retry. `qualification_progress_027.json` records this progress. Release and
adoption remain false; the 400 MHz goal remains active.


### 2026-10-20 — Full assembly passes and independent antenna coverage

The unfilled repaired-macro assembly passes full Magic DRC with zero errors,
unique Netgen LVS with all three macros expanded, and 55 matching top pins.
`candidate_assembled_layout_audit_repaired_macros_001` binds the exact GDS.
The prior filled candidate and its density receipts remain separate.

The corrected MOS-only native scan now reports 147 violations on 135 nets,
with 4,940 feedback rectangles, versus 151 records on the previous assembly.
The two BBPD metal2 failures, one BBPD metal4 failure and the internal-core
metal4-contact failure have cleared. Remaining records are 129 on metal3 and
18 on metal4. All 147 records have exact extracted MOS gate localization.

`check_forming_antenna_geometry.py` independently enumerates every drawing
MOS-gated component at 13 conductor/cut stages, conserving total gate area at
each stage and excluding pure diodes from gate area. Actual-cell LI controls
reject zero, one and two diodes and accept three. A second control confirms
that two early gated components remain separately visible even when they
merge into one final net. The original assembly gives 148 geometry violations;
its three-record difference from native Magic is retained as unresolved.
The repaired assembly gives exactly 147. A fresh spatial probe binds every
native violating MOS point one-to-one to all 147 independent violating
components, including formerly ambiguous overlapping bounding boxes.

An initial crosscheck rejected the assumption that complete drawn perimeter
always bounds native contact-edge accounting: one ratio was 536.943624 versus
537.659. The failed attempt and exact source are preserved. The corrected
crosscheck records, rather than suppresses, numerical differences, from
-0.1331% to +2.0465%; no certified ratio bound or complete process-rule
qualification is claimed. Both methods flag every matched component.

`parent_dco_antenna_placement_002` is a separate unadopted candidate with four
HS diodes and a local well tap on each of 131 failing DCO control nets: 524
diodes and 131 taps. Placement passes. The first placement candidate lacked
local taps and is retained as provisional history. The second uses alternate
R0 rows and at least 1.92 micron horizontal island clearance; worst center
distance from its DCO port is 30.715 microns. This initial sizing still needs
physical power connections, local branches connected by metal3 or lower,
full layout/antenna checks and analog loading qualification. Macro geometry
and all live oscillator inputs remain untouched. The other four failing
interface/control nets still need protection.

Four existing native oscillator jobs remain live, with no identical retry or
fifth analog worker. Broad PVT expansion must not silently adopt the already
unqualified 80ns measurement profile; scheduling handoff is an upcoming task.
`qualification_progress_028.json` records the exact evidence and next steps.
Release/adoption remain false and the full 400 MHz goal stays active.


### 2026-10-20 — Powered protection, full layout repair and duration testbench fix

The external candidate now has 524 HS diodes and 131 local well taps on 131
DCO control nets, with M1 power connections to existing M4 stripes. Preserving
old signal routes prevented collision-free power routing, so all 357 parent
signal nets were rebuilt. Power checks passed. One wrapper expected the wrong
success wording after native completion; the separate completion audit binds
its finished outputs without repeating construction. PG cleanup merged M1
rectangles and removed 456 duplicate via records, leaving 330 unique new via
records with identical physical union and unchanged signal routes/placements.

The first protected GDS passed unique LVS but full Magic DRC found 338 markers:
330 M3 minimum-area markers at 110 PG landing sites and eight M5 spacing markers.
The failed geometry and successful LVS are retained. Its independent antenna
count fell from147 to40. Adding 0.6um-square M3 PG pads and rerouting ordinary
signals on M1 through M4 produced parent_dco_antenna_route_002 and stream_002.
This candidate passes router DRC0, full Magic DRC0, complete unique LVS and55
matching top pins. parent_dco_antenna_layout_audit_002 binds the exact GDS,
three preserved macro interiors, 524 diodes and131 taps. It is unfilled and
unadopted. Independent13-stage geometry finds32 remaining antenna violations:
27 M3 and five M4. Native MOS-only checking is running in native_002.

The completed lower duration probe exposed a testbench error: .tran extended
to160ns while reset pulse width stayed80ns. Reset reasserted around85.05ns,
invalidating late windows. All eight windows and the completed waveform are
retained in dco_duration_reset_failure_windows_001. Its three early20/40/60-to-
80ns frequencies exactly match the original reference. This stopped oscillation
is not a DCO failure. The upper invalid probe was explicitly stopped. Faulty
decks, plans and partial/completed evidence are preserved, not overwritten.

run_corrected_dco_duration.py changes only reset width/period to160/320ns so
reset remains released throughout the160ns observation. Both corrected probes
are running with their original absolute cutoffs; no12h allowance was reset.
Every declared window is retained, including unmeasurable windows, and rising
edges must cover the end of each requested window. A stopped oscillator cannot
pass using only earlier edges. No measurement window or model is adopted.

scheduling_handoff_002 retired the old DCO dispatcher before broad PVT expansion
with an unqualified80ns profile. Both live TT100 endpoint jobs and their one-
case wrappers continue; completed CSV/provenance can be collected without a
new simulation. The old receiver campaign used superseded parent RC. Completed
case0 is retained, active case1 was explicitly stopped and kept as partial
superseded evidence, and unlaunched cases2/3 were canceled. These are not silicon
failures. Its original cutoff remains applicable to matching replacement checks.
An earlier retirement preflight found case1 active and changed nothing; the
executed handoff accounts for the actual live state. Old pinned dispatcher and
guard inputs were not edited. Future admission must use the retired-dispatch
mode, rather than restart obsolete controllers.

Four analog native jobs are live: two TT100 endpoints and two corrected duration
probes. Nominal-supply15-PVT requirements and every remaining physical/model/
full-PLL gate remain unchanged. qualification_progress_029.json records exact
native identities, deadlines and next actions. Release/adoption remain false.


### 2026-10-20 — Antenna routing improvements and ten targeted banks

The completed native scan of protected candidate002 reports32 violations on32
nets, with129 exact gate feedback matches. All32 debug gate records map exactly
to independently violating forming components. Two nonfatal freeMagic(NULL)
messages are retained in the native log; the scan finishes with exit0 and all
reported failures are spatially cross-checked. No qualification is inferred
from a silent or incomplete native log.

The independent checker now includes a conservative contact-area allowance.
The audited native source adds surface-contact area to metal residue totals;
check_forming_antenna_geometry_v2.py adds twice the connected adjacent-cut area
to drawn sidewall area, including upper cuts without connecting upper metal.
Cut-stage bottom areas and gate/diffusion geometry remain unchanged. Actual
zero/one/two-diode failures, three-diode success, and the separated-component
control still pass. On candidate002 the bound retains the same32 failures and
exceeds every matched native displayed ratio (minimum relative margin about
5.35e-7). General process-rule qualification is not claimed from these controls.
The former unbounded geometry comparison is retained as historical evidence.

Routing more long conductors on lower layers reduced diagnostics further:
route003 (M3 adjustment0.8) gives18 violations, ten M3 and eight M4. Route004
(M3 adjustment0.99, M4 adjustment0.9) passes router DRC0 and the corrected
conservative checker finds ten M3 failures, with no other stage failures.
Both trials preserve all macro geometry and the existing protection placement;
full-GDS physical passes are not claimed for these intermediate trials.
Exact macro-port topology localizes all ten failing components. Seven are
newly failing unprotected fine-control nets, two already protected fine nets
need more diffusion credit, and one is BBPD_RESET_N. Some earlier inference
about late diode connectivity was superseded by this precise localization.

Forty additional HS diodes and ten local taps were placed in existing power-
rail coverage. The plan proves complete M1 coverage of both cell power ports;
no new PG straps or vias are required. Existing macro and cell placements are
preserved. The first targeted routing preflight showed that incremental DEF
import updates floorplan objects without restoring the intended fixed-wire
encoding. It exited before routing, and its outputs remain retained. A fresh
technology/macro LEF and full DEF import establishes the FIXED encoding.
The revised targeted run reroutes just ten nets, reaches router DRC0, and
verifies all347 background signal route records unchanged after normalizing
the fixed/routed metadata. All old pin bindings and macro ports are unchanged.
The source audit of this OpenROAD revision confirms first-path FIXED encoding
marks the complete net fixed; partial-path pinning was not assumed.

parent_dco_antenna_targeted_006 and stream_006 contain564 parent diodes and141
taps in141 banks on139 unique parent nets. Full-chip DRC/extraction, unique LVS,
and the corrected13-stage antenna checker are running. The earlier candidate002
remains the last full-GDS DRC/LVS passing reference, with32 antenna failures.
The targeted candidate is unfilled and unadopted. No passing evidence from the
earlier GDS is transferred to this candidate.

The two TT100 endpoints and both corrected160ns probes remain live, keeping
four native analog jobs. Their existing absolute budgets and the retired-
dispatch scheduling policy remain unchanged. No native analog rerun or new
analog job was introduced in this turn. qualification_progress_030.json records
exact evidence and live check identities. Calibration, interface,15-PVT timing,
whole-PLL, final density/RC/supply/noise and release gates remain open.

### 2026-10-20 — Parent antenna repair passes independent geometry

Candidate006 failed full physical checks despite its zero antenna diagnostic:
eight M1 spacing markers and two signal short groups were confirmed by LVS
and an independent check of all 743 rectangular macro-port probes. The earlier
route004 passes that connectivity screen. Candidate006 remains failed evidence;
its antenna zero is ineligible for signoff. The first local replacement was
stopped when a temporary keepout conflicted with a fixed coarse-control route.
Adding that neighboring route to the repair produced candidate008, with full
DRC zero and unique LVS, and one remaining M3 antenna failure on DCO_THERM[53].

Candidate011 reroutes only that last net. Parent M3 wire length decreases from
532.38 to 384.54 um; all other 356 signal route records, placements, bindings,
and macro ports remain unchanged. Full-chip Magic DRC reports zero errors,
LVS matches uniquely with all three macros expanded, and the independent
conservative checker reports zero violations over all 13 forming stages.
The 743-port topology screen has no shorts, missing probes, or split nets.
Two lower-layer routing preflights failed before routing because the router
requires an access layer above the macro pins; these are retained tool-input
nonpasses, not oscillator or silicon failures.

The passing unfilled GDS contains 564 external HS diodes and 141 well taps.
Fresh density fill generation is running against that exact candidate. Fill
merge, final full physical/density/native antenna checks, and matching electrical
extraction remain required. New runners retain the original layout deadline,
including dependency waits. No analog jobs were added or restarted: both TT100
endpoints and the two corrected 160 ns duration probes continue under their
existing deadlines. qualification_progress_031.json binds the evidence and live
state. Nominal 15-PVT calibration/timing, interfaces, whole-PLL cases, supply/noise,
and final release gates remain open; release and adoption remain false.

### 2026-10-20 — Final filled geometry passes; fill capacitance correction

The final parent_dco_antenna_stream_filled_011 GDS passes full Magic DRC zero,
unique LVS with all three macros expanded and 55 matching top pins, all 175 PDK
density checks, and all 13 conservative forming-stage antenna checks. Native
MOS-only antenna checking also finishes with zero feedback after analyzing more
than 16,000 gates. The independent 743-port screen finds no shorts, missing
probes or split nets. The combined final geometry audit binds every result to
one GDS hash and its exact 1000 by 850 um extent. Native warnings, including one
freeMagic(NULL) message, remain retained; a warning-free run is not claimed.
This closes the geometry checks run here, not electrical or release signoff.

A new physical extraction control reveals that the stock Magic setup ignores
an M5 fill-purpose tile: its capacitance records equal the no-tile baseline.
The same rectangle represented as a normal conductor produces 2.22469 fF of
signal-to-floating-tile coupling. The independent two-branch calculation gives
1.5171121 fF of effective added signal capacitance; the floating node is not
grounded. A fourth control proves that simply overlaying drawing purpose on
retained fill purpose is also ineffective. The first full-design CAD diagnostic
was therefore stopped and retained as superseded partial evidence, not a device
failure. No transient analog job or manufacturing GDS was changed.

The corrected extraction-only flat view replaces LI/M1-M5 fill purposes with
conductor drawing purposes, preserving their physical footprints and all other
mask geometry. It uses 359 parent-net labels from the passing physical topology
screen and preserves MOS gate area. A diagnostic capacitance extraction is now
running on that view under the original layout deadline. Floating capacitive
nodes are retained. Resistance, FOM/poly fill coverage, extraction accuracy,
process/RC enclosure and loaded interface models remain unqualified; this raw
network is not adopted. The exact installed OpenROAD RCX sources were also
cached with all 71 Git blob hashes checked for the extraction coverage audit.

qualification_progress_032.json records the final geometry and live corrected
extraction. Both TT100 endpoints and both corrected 160 ns probes remain live,
with no new or restarted native analog jobs. All original deadlines and nominal
15-PVT requirements remain. Qualified timing, calibration, physical interfaces,
whole-PLL cases and mode changes, supply/noise, physical power/jitter and final
integration gates are still open. Release and adoption remain false.


2026-10-20: qualification_progress_033.json records completed metal-fill
capacitance extraction, digital-node correlation, the TT100 range result and
an isolated return-stage fine-range candidate. The network retains 21,007,169
positive capacitors and all floating branches; 21,579,265 exactly zero entries
were removed without changing nonzero values. All 359 parent labels and 7,468
digital targets are mapped. Device gate area is conserved. The 2,288 extraction
warnings match known decap instances by count, but full flattened feedback was
not captured. Poly/FOM fill, resistance, nonlinear device loads and RC enclosure
remain unqualified. Five combinational driver types have observed wire matrix
diagonals above their old characterization fixtures; these sums are not
qualified effective loads or timing bounds.

The completed coarse13 TT27 endpoints are 102.3183645443 and 104.1249809134 MHz,
so that band does not bracket 100 MHz. Neighboring coarse14 endpoint checks are
running. The two new 5 ps timestep checks were explicitly stopped, with partial
outputs retained, to prioritize this range gate; identical retries are not
authorized. Both corrected 160 ns duration checks continue. Four native analog
engines remain the maximum, with all original absolute deadlines preserved.

The separate IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80 source/config adds 80
existing einvp_1 input load cells on mirror_pass_n[0]. Yosys elaboration confirms
all 691 original cell connections and public ports are preserved, the new
controls avoid the existing coarse1 bank, and dummy outputs are independent.
A wrong-control negative case is rejected. No layout or analog check has begun
for this candidate; neither range nor release adoption is established. Await
neighboring-band evidence before committing physical implementation resources.
The passing filled-GDS geometry receipts apply only to the original candidate.
Nominal 15-PVT and all four target modes remain required. Qualified physical
whole-PLL passes remain zero; release, model adoption and timing closure remain
false.


2026-10-20: qualification_progress_034.json records a new extraction-only
poly+metal fill view and its live native Magic extraction. Actual poly-fill
geometry has zero overlap with active, tap, existing poly, licon or recognized
poly resistor/short markers. Gate area and every other mask region are
preserved. Poly fill is moved from fill to drawing purpose without retaining
an overlay. The manufacturing GDS remains unchanged. This CAD check shares the
original layout deadline and requests full flattened extraction feedback;
floating branches remain explicit. No analog engine was added or restarted.

lower_fill_control_node_audit_001 confirms that the automatically named P-tap
reference node is the substrate, not a floating electrode. It independently
reduces only the isolated poly control's explicitly floating branch. Neither
an ohmic FOM surrogate nor full fill/material/process enclosure is qualified.
The raw poly+metal network is still being extracted and must be assessed before
use. Four native analog engines continue with their original absolute cutoffs.
All four modes and nominal 15-PVT scope remain mandatory; release stays false.


2026-10-20: qualification_progress_035.json adds fresh min/nom/max OpenRCX
extractions of parent_dco_antenna_targeted_011/route.odb. Each corner contains
357 signal nets. All DEF terminals match, every resistance is positive, all
357 graphs are connected trees, and source-to-terminal path resistances are
ordered min <= nom <= max. A deliberately wrong terminal is rejected.
A full-GDS conductor audit locates all 10,636 exported node coordinates on
their expected logical nets across the three corners, with no unmatched
coordinates and a wrong-net negative control rejected.

This proves current parent-wire topology and coordinate correspondence only.
SPEF lacks pin capacitance, macro internals and generated GDS fill. The native
extractor grounds couplings below its default 0.1 fF threshold. Its C entries
must not be added to the full-GDS network a second time. Coordinate membership
does not yet identify a unique conductor layer or distribute the fill-aware C
onto resistance nodes. Full RC/process enclosure and physical timing remain
unqualified. The poly+metal Magic extraction and four native analog checks
remain live under original cutoffs. No additional analog engine was launched.
All release modes and nominal 15-PVT scope remain unchanged; release stays false.


2026-10-20: flat_decap_warning_gate_inventory_001 locates all 2,288 decap
channel boxes across 1,144 actual final-GDS instances. Well overlap independently
identifies the expected VPWR or VGND connection for each gate. Preliminary saved
flat feedback matches every expected box and rail; terminal MOSCAP device checks
and the complete network audit remain pending in the bounded collector. Native
Magic has finished the poly+metal extraction; the original runner is writing
its terminal receipt. No source model has been adopted.

The [SkyWater mask reference](https://skywater-pdk.readthedocs.io/en/main/rules/masks.html)
identifies FOM as the field-oxide mask, and its
[layer reference](https://skywater-pdk.readthedocs.io/en/main/rules/layers.html)
describes dummy FOM waffles. These references do not establish an electrical
resistance/capacitance model for this layout's dummy material. The installed
Magic technology and isolated controls remain the evidence for extraction
behavior; an ohmic-tap surrogate is still unqualified as a manufacturing model.


2026-10-20: qualification_progress_036.json records terminal poly+metal fill
capacitance extraction and its assessments. The source contains 49,357,430 C
records, 99,720 MOS devices, 726 diodes and 16 modeled resistors. All 359 parent
nodes participate; no negative capacitor was found. Removing only 26,845,001
exact zeros retains 22,512,429 positive capacitors, all device cards and every
floating branch. No nonzero values are changed or floating nodes grounded.

Every one of the 2,288 flat missing-terminal warnings matches an exact final-GDS
decap gate, its well-derived rail, and a native MOSCAP at the same position with
matching gate area and D=S=bulk on that rail. There are no unclassified, duplicate
or missing feedback entries. Wrong-rail and wrong-box controls are rejected.
Comparing full native device statements between metal-only and poly+metal views
finds all 100,462 statements unchanged, including geometry and connectivity; a
missing-device control is rejected. The expanded network replaces the older
view, rather than adding a second C patch to it.

The digital load inventory now uses this expanded network for all 7,468 mapped
targets. Reusing their identities is conditioned on unchanged native device
statements and original conductors, plus no new poly/contact overlap. Five
combinational driver types still exceed the old characterization fixtures by
observed wire matrix diagonal. Those sums exclude nonlinear device charge and
are not effective timing loads. PLLOUT, REFCLK and BBPD_RESET_N diagonals are
0.25536468, 0.29508430 and 0.39440007 pF respectively. FOM/bulk material coverage,
distribution of C onto wire resistance nodes, process/RC enclosure, calibrated
models and physical timing remain open. No electrical model is adopted. Four
native analog checks continue with original absolute cutoffs; all four modes,
nominal 15-PVT scope and remaining release gates are unchanged. Release and
adoption remain false, with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_037.json records 18 native CAD corner
controls and a live FOM bulk-surface sensitivity extraction. Known M1 baseline,
floating poly, P-bulk surface, N-bulk surface and floating M5 controls were each
extracted with installed ngspice(lrlc), ngspice(orig) and ngspice(hrhc) styles.
Independent reductions keep the explicitly floating electrode floating and
assume ideal bulk/supply references only in these isolated controls. All five
effective control capacitances strictly satisfy min < nom < max. The actual HS
nand2_2 GDS also preserves all eight native MOS statements after schema
normalization and all exported geometry/terminal parameters across M and X
forms. Missing-device and reversed-order controls are rejected. These checks do
not substitute for full-layout corner extraction or RC/timing enclosure.

The new FOM reference reuses the expanded poly+metal view and places diagnostic
ohmic surfaces on the remaining FOM footprints, partitioned by actual nwell.
The total footprint is 311916.8503 um2: 311869.8553 outside nwell and 46.995
inside. Added TAP/implant purposes exist only in this counterfactual view;
manufacturing GDS and all original gate/contact geometry remain unchanged.
No finite bulk impedance, actual FOM material equivalence or quantitative
upper/lower enclosure is claimed. A bounded collector waits for the running
extraction, then checks feedback, the full network, native device identity and
parent-diagonal sensitivity. Both retain the original layout deadline; no
native analog job is added. Four DCO checks and all original absolute cutoffs
remain active. Nominal 15-PVT, all four modes and all release gates remain;
release/adoption stay false with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_038.json records the completed counterfactual
FOM sensitivity extraction: 49,727,566 raw capacitor records, 26,920,418 exact
zeros, no negative capacitors, all 359 parent nodes and 2,288 individually
classified decap warnings. All 100,462 native device statements are unchanged
from the poly+metal view. Monitored parent matrix diagonals change by 0.4575%
(BBPD_RESET_N), 0.6323% (REFCLK) and 0.7360% (PLLOUT). These are sensitivity
observations, not effective timing loads or a qualified material enclosure.

Twelve additional native CAD controls preserve HD/HS tie and diode geometry,
terminal order and extracted parameter magnitudes across primitive/wrapper
forms. pj/perim names are normalized for comparison only; the documented diode
scaling is retained. Inventory of the actual full-GDS extraction finds two HD
diodes at effective area0.4347um2/perimeter2.64um and724 HS diodes at
area0.6417um2/perimeter3.24um. Parent, digital, detector and DCO DEF counts
independently agree. The existing fixed-geometry translator correctly rejects
the HS geometry; previous HD equivalence cannot qualify those724 instances.

A fresh HS comparison is prepared from pinned checked decks, changing only
geometry. All360 decks pass geometry, temperature and coverage preflight.
The bounded host runner is queued for one native analog slot, covering15
PVT electrical cases and75 noise-bias cases using ngspice47 as independent
reference and upstream Xyce as golden simulator. It holds the shared admission
lock through each simulator exit, including ngspice, so total analog concurrency
remains at most4. The single12h deadline includes preparation, queue, execution
and raw-data assessment. No translated HS model is adopted before it passes.

Full-layout min/max capacitance extractions are sequentially queued behind the
completed large FOM extraction; minimum is now live. The original empty queue
was retired before any corner worker/native launch to add15s parent cleanup
grace around the worker's existing10s native termination cleanup. The worker's
original absolute native cutoff is unchanged. Corner readers now recognize
foundry-wrapper active nodes and retain all wrappers during exact-zero cleanup;
their full-layout assessments remain pending. Four existing DCO runs continue.
All modes, nominal15PVT scope and remaining release gates remain unchanged,
with zero qualified physical whole-PLL cases and release/adoption false.


2026-10-20: qualification_progress_039.json records the corrected corner
warning assessment and a lumped floating-capacitance reduction. The first
reader stopped because wrapper export produces726 "Could not determine device
boundary" diagnostics in addition to2,288 decap terminal diagnostics. That
failed assessment is retained. Actual final-GDS diode diffusions are now located
individually; all3,014 minimum-corner messages match known devices, with native
position, area/perimeter or gate-area and connection checks. No native
extraction was rerun. The minimum network contains99,720 MOS,726 diode and16
resistor wrappers, all359 parent nodes and no negative capacitors. Exact-zero
cleanup retains21,384,654 positive entries and all100,462 wrappers unchanged.
The maximum source and its bounded collector remain live.

An isolated NumPy2.2.6/SciPy1.15.3 environment is recorded in
numerical_environment_001.json. The reduction preserves the parsed positive
network and solves zero incremental charge on2,095,561 floating nodes in174
anchored components. It assumes zero wire resistance and holds other active
terminals/supplies incrementally fixed; nonlinear device charge is excluded.
Energy/residual certificates, including floating-point allowances, give wire
capacitance intervals214.239114198..214.239114751 fF for PLLOUT,
265.956242762..265.956243306 fF for REFCLK and
331.333226191..331.333226749 fF for BBPD_RESET_N. These meet the requested
0.0001fF numerical interval width. Existing native poly and metal controls
agree with independent Decimal series reductions. Isolated unanchored test
components preserve port C; inaccurate trials retain wide intervals and
negative C is rejected. This numerical result does not qualify material,
distributed RC, nonlinear loading or physical timing.

The PLLOUT diagnostic exceeds buf_1's nominal TT25 library limit0.130015pF.
A separate unadopted RETURNFINE80_BUF8 candidate therefore changes only out_buf
from buf_1 to buf_8, whose nominal5pF library domain contains this diagnostic.
Both library logic functions are A. Elaboration preserves all771 instance
connections, all public ports/encoding, all80 return loads and the other770
cell types; wrong-input and extra-cell controls are rejected. This is a design
margin experiment, not proof of functional overload. Fresh layout, analog,
loaded-interface and15PVT/four-mode validation are required. Physical work
still awaits terminal range evidence. All original checks and deadlines
continue, HS geometry comparisons remain queued, and release/adoption stay
false with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_040.json records terminal min/nom/max
full-layout capacitance comparisons. All359 parent diagonals are ordered;
these are matrix sums, not effective timing loads. Maximum-corner assessment
classifies all3,014 diagnostics and retains23,107,833 positive capacitors after
removing26,267,595 exact zeros, preserving99,720 MOS/726 diode/16 resistor
wrappers. No source extraction was rerun.

Eight NFET model names differ between orig and each wrapper corner. The
installed technology maps0.36um scnfet devices to ordinary nfet in orig and
special_nfet_01v8 in wrapper styles; all other native fields match. The special
PDK model has a matching0.15um length/0.36um width bin. The two models remain
distinct; no electrical equivalence or full-layout nominal model is adopted.
A follow-up actual detector dfrtp_1 control, recorded in
narrow_mos_corner_exports_001/assessment.json, completes four native CAD cases.
Orig and nominal-wrapper complete wire-C matrices agree exactly; all three
wrapper styles have identical normalized native devices. This small control
does not replace full-layout nominal wrapper/model validation.

Distributed-RC controls are retained with their failures. The initial wire-only
control stopped without completion. The first driven control had conflicting
port indices; a subsequent duplicate-conductor-port case terminated with
signal11. The sequence does not independently prove the signal's cause,
despite the stronger wording in that control's frozen docstring. Corrected
single-driver-port controls complete for both floating and explicitly ported
metal tiles without port-definition errors. An independent resistor-component
collapse and Decimal branch comparison finds11 and12 changed capacitor pairs,
respectively, including lost internal-node coupling and altered substrate
capacitance. Both exports also contain four negative capacitors. These facts
do not by themselves establish whole-network nonpassivity, but the default
extresist capacitor export fails the necessary matrix preservation check and
is not approved for full-layout use. Exact unchanged matrices pass the checker;
deleting the actual tile coupling is rejected. Raw outputs and failed control
receipts are retained. The checked parent wire R and full-GDS positive C
networks remain separate until a geometry-supported distribution or timing
enclosure is qualified.

The four original DCO jobs continue under unchanged absolute deadlines and the
four-engine limit. HS diode comparisons remain queued within their original
12h check budget. No DCO candidate has been physically adopted. Release and
model-adoption status remain false, with zero qualified physical whole-PLL
cases; nominal1.8V, all100/250/300/400MHz modes and15PVT remain required.


2026-10-20: qualification_progress_041.json records the full-layout nominal
wrapper extraction and further RC controls. The four-case actual dfrtp_1
control has28 MOS and four width-selected special NFETs per cell. Orig and
nominal wrapper wire-C matrices match; nominal/min/max wrapper native device
sets match without aliases. A fresh full-layout ngspice() wrapper extraction
is live in poly_metal_full_nominal_wrapper_001. Its collector will audit all
warnings, network entries and exact-zero removal, then compare its complete
capacitor export stream with the retained orig view and its device statements
with both RC corners. The original09:44UTC CAD deadline is retained for
preparation, execution and assessment. No native analog engine is added.

Matching upstream Magic8.3.623 source is pinned at
fd12c39c37f26a0fe6e04698b1011e31b8bd3229 in
rc_extraction_source_analysis_001; binary/source equivalence is not asserted.
The manual command sets signal mode, whose capacitor reader adds each
coupling value to both node totals. Native manual-only controls still change
11/12 branch pairs and lose five internal coupling pairs. Automatic-only
controls retain those internal pairs but still change5/6 substrate branch
pairs. Both paths retain four negative C entries. Removing the duplicate
resistance stage therefore does not make this export acceptable. See the
[matching reader source](https://github.com/RTimothyEdwards/magic/blob/fd12c39c37f26a0fe6e04698b1011e31b8bd3229/resis/ResReadExt.c)
and [command source](https://github.com/RTimothyEdwards/magic/blob/fd12c39c37f26a0fe6e04698b1011e31b8bd3229/resis/ResRex.c).
Installed tools and existing physical models are unchanged.

charge_preserving_rc_controls_002 reconstructs both small controls by keeping
all31 native resistors, MOS records and public ports, discarding the altered
C export and restoring the original positive capacitors. Deleted original
nodes attach to an existing MOS terminal on the same original conductor.
There is no nearest-coordinate guess. An attempted exact original seed
mapping failed because the seed is absent from the emitted R nodes; that
attempt is retained and exact seed preservation is explicitly unproven.
After resistor-component collapse, every original capacitor branch agrees
exactly, with zero negative capacitors. Wrong-conductor attachment is rejected.
This is a lumped-placement prototype: physical distributed C placement,
transient error and full-layout RC/timing remain unqualified. It is not adopted
for release timing.

The original four DCO simulations and queued HS geometry comparison remain
live under their unchanged deadlines and four-engine admission limit. All
100/250/300/400MHz modes and nominal15PVT remain required; zero physical
whole-PLL cases are qualified. Release and model-adoption status stay false.


2026-10-20: qualification_progress_042.json changes the DCO model gate based
on an audit of the actual source used by all four live probes. Exporting the
retained native .ext without RC backannotation at the same0.01fF threshold and
collapsing explicit wire R exposes at least1,799 changed capacitor branch pairs
above a conservative print-rounding allowance, including256 removed pairs.
The source contains126 negative intermediate rnode C entries. The raw export
also changes two junction-area/perimeter records; MOS models, dimensions and
collapsed terminal identity otherwise match. The existing resistor reduction
preserves every capacitor record, so it does not repair these discrepancies.

The exact reduced-model hash is disqualified for physical range/calibration
in DCO_RC_model_invalidation_001. All four DCO diagnostics were stopped under
the shared admission lock; decks, logs and partial waveforms are retained in
unqualified_dco_RC_retirement_001. Their original deadlines were not reset and
no identical retry was started. Earlier TT frequency brackets remain results
of that model and cannot choose presets or prove physical range failure. This
supersedes the earlier plan to wait for coarse14 terminal evidence before
choosing a return-fine physical experiment. A fresh validated replacement
model must precede that decision. Retired dispatcher status files retain
historical observations; the latest progress/invalidation receipt overrides
their eligibility for physical range decisions.

The freed analog slot completed the HS diode comparison: all360 upstream-Xyce
and ngspice47 analyses,15 electrical PVT cases and75 noise-bias cases pass.
Maximum relative errors are0.0002206245 DC,0.0000054104 complex AC,
0.0000048452 imaginary AC,0.0001422093 rising charge,0.0002426655 falling
charge and0.0000187787 noise PSD, within unchanged limits. Both physical
diode geometries now have checked compatibility scope. The new
scripts/translate_sky130_checked_diode_geometries.py binds HD/HS evidence,
foundry-model hashes, native outputs and prepared decks before accepting only
HD area4.347e11/perim2.64e6 or HS area6.417e11/perim3.24e6 native wrapper
arguments. It emits explicit effective0.4347um2/2.64um or0.6417um2/3.24um
fixed-temperature level1 wrappers. The caller must use the same global
Xyce temperature. Actual726 wrapper cards (2HD+724HS) pass all15 model-template
checks against the completed native HS models and an end-to-end CLI check.
Unknown geometry, duplicate/continued cards, conflicting global scaling,
complete decks and already translated input are rejected. This prepares
compatibility fragments; no physical PLL model is integrated or released.

Independent OpenRCX DCO inter-cell R extraction completes min/nom/max. All505
routed nets match their DEF terminal sets;453 omitted nets are unrouted
singletons. All R graphs are positive and connected; path ordering has zero
inversions, with seven multiple-driver nets kept explicit. Exact GDS/DEF
transforms match1,736 instances and2,071 signal terminals on956 signal nets.
The two extra DEF singleton names are body-only VPB/VNB public ports. All
2,641 internal wire-coordinate records and5,418 terminal-coordinate records
probe the expected conductors. Another354 terminal records fall outside their
conductor, but independently equal the mean of their actual pin-rectangle
centers within1nm; every actual rectangle probe is on the expected component.
They remain virtual terminal coordinates and are not used as physical C
locations. No coordinate or connectivity waiver is applied. Cell-internal R
and spatial C-to-R assignment are still unqualified.

charge_preserving_DCO_RC_prototype_001 retains97,616 native wire R and restores
all35,051 original nonnegative C plus original parameters of8,618 MOS and two
intrinsic R wrappers, including the two changed junction records. Exact
capacitor matrix and device equality are checked after wire-R collapse;
wrong attachment/value controls are rejected. Deleted capacitor nodes attach
to a device terminal on the same original conductor. This lumped-placement
prototype excludes assembled loading/fill/supply effects and has no spatial
C or transient-error qualification; no native analog run or release adoption
is authorized by its receipt.

Full-layout nominal wrapper extraction and warning/network/zero cleanup are
terminal. All100,462 normalized device statements match min/nom/max wrapper
styles without model aliases. The49,357,430 capacitor exports have different
record order and IDs, so the initial raw-stream comparison does not prove C
matrix equivalence. An exact Decimal, endpoint/order-independent comparison
of both22,512,429-positive-record multisets is live under the original09:44UTC
CAD deadline. No extraction was retried. All four nominal1.8V modes,15PVT,
physical timing/interface bounds,60 wholePLL cases, mode changes, material/RC
and supply/noise/jitter/power/integration gates remain required. Zero physical
wholePLL cases are qualified; release/adoption stay false.


2026-10-20: qualification_progress_043.json proves exact nominal capacitor
network equivalence despite changed export ordering. Both positive views have
22,512,429 records. Exact Decimal values, unordered endpoints and removed
instance IDs are externally sorted; both complete multisets have SHA256
4d03c57417ac17d6bd81409521051958b326f562dcff020ff412ea29fa0c1c15.
Actual-record reorder/ID/endpoint controls preserve equality; deleting a record
breaks it. Together with the prior100,462-device wrapper comparison, this
establishes consistent nominal/min/max wrapper model selection without aliases
and preservation of the original nominal C matrix. Floating branches remain
explicit. This does not qualify material, spatial RC, nonlinear loading or
physical timing, and no runtime model is adopted.

An isolated unmodified Magic8.3.623 source build is prepared at the pinned
fd12c39c37f26a0fe6e04698b1011e31b8bd3229 revision. Build attempts retain their
logs: missing X11 headers first stopped compilation; a modular configuration
lacked the expected export backend; changing configuration without cleaning
left stale conditional-compilation objects. A clean fixed-configuration build
in isolated_magic_stock_build_004 completes and passes24 native baseline
checks. Four physical controls (floating metal, floating poly, HS NAND and
the actual HD narrow-device FF) have exactly matching parsed C matrices,
native devices and feedback against the installed extractor at min/nom/max.
Installed tools and the golden upstream Xyce backend are unchanged. Control
agreement does not establish full-layout binary/source equivalence.

The isolated diagnostic patch exposes the existing native node/coupling clip
arguments through an opt-in internal-coordinate rectangle. It also logs signed
ground/coupling values before the original output clamp at17 significant
digits. The first diagnostic build catches a missing stdlib declaration;
that attempt is retained. The corrected diagnostic build passes24 further
native default-mode comparisons at all3RC corners. No capacitance arithmetic
is changed in default mode; the diagnostic code is separate from installed
tools and qualified physical models.

Native window accounting in magic_cap_clip_window_controls_001 completes24
CAD runs across four nominal physical controls. Every covering window matches
the unclipped matrix after native print precision is accounted for. Quadrant
sums agree for the HS NAND and HD FF, but fail for floating metal/poly fill.
For metal fill, SIG-to-ground changes by+2.9343999344fF and SIG-to-tile coupling
by-0.8850111643fF; poly-fill changes are+3.9341178665fF and-0.8519359402fF.
These exceed the declared0.0001fF plus1e-9 relative accounting tolerance.
Negative local ground contributions on the cell controls are retained rather
than clamped before summation. All node names are preserved and omission of
a nonzero quadrant is rejected. The rectangular-clipping decomposition is
therefore rejected for DCO/full-layout capacitor placement; no broad layout
extraction or long analog sweep uses it.

The next spatial method must trace contributions from unchanged full geometry,
retain support locations plus signed shielding/clamp adjustments, and recover
the original matrix before using the resulting placement with wire/device R.
Junction-parameter location and transient-error enclosure are also open. The
previous DCO model remains disqualified; its four retired jobs are not retried.
The diode compatibility results remain valid in their checked scope. All
100/250/300/400MHz modes, nominal1.8V/15PVT and remaining physical timing,
wholePLL, mode-change, material/RC, supply/noise, power/jitter/area and integration
gates remain required. Zero physical wholePLL cases are qualified, and release
and model-adoption status remain false.


2026-10-20 checkpoint044: full-geometry DCO charge accounting and substrate context

The current immutable checkpoint is
build/timing400/release_001/qualification_progress_044.json. An isolated623
contribution tracer now uses a private exclusive file and completion marker.
The failed shared-log attempts and the corrected uninitialized fringe-support
rectangle are retained. Default mode passes24 native installed-tool comparisons;
four small physical controls pass12 traced corner comparisons. A streaming
reader agrees exactly with the original reader on12 native control logs and
rejects malformed/truncated records and omitted actual contributions.

The actual DCO passes installed-tool C/device comparisons and signed contribution
accounting at all3RC corners: nine native C-only runs and six resistance-enabled
runs. Each corner retains all8620 native devices. C-only traces contain about
7.74million events; resistance-enabled traces contain about8.30million. Their
recovered matrices agree within explicit native print/arithmetic allowances.
No full-DCO output-clamp contribution is unlocated. These are numerical/native
accounting controls, not physical capacitor-placement or transient-error proof.

A separate context audit finds1753 nominal C-pair differences, up to0.5114fF,
between a new C-only extraction and the retained pre-RC extraction. Exported X
devices and ports are identical. Re-enabling native resistance extraction
recovers the retained nominal capacitor matrix exactly. PDK technology files
are identical. Pinned upstream ExtCell.c and ExtBasic.c show that EXT_DOEXTRESIST
changes both substrate preparation and default-substrate-type membership;
ExtMain.c also runs a full resistance pass. C-only and RC contexts must not be
mixed without a direct equivalence proof.

The independent native-R coordinate survey retains89955 coordinate records and
finds coordinates for all78613 exported R/MOS/port nodes. It classifies72225
records on the expected conductor,10314 as unexported intermediate records,
7382 as MOS body terminals outside the wire-only geometry model, and34 as
unresolved VGND internal coordinates. Substrate records are included when
mapping the ground seed. Well/bulk material, finite impedance, virtual/internal
coordinates, junction distribution and spatial C/R error bounds remain open.

An opt-in C-only RC-substrate mode is prepared to preserve the native RC
substrate context while skipping the automatic full wire pass. Its direct DCO
corner equivalence controls are the next gate before any assembled-layout use.
The former DCO RC model stays disqualified and its four retired analog jobs
remain stopped. Original absolute CAD deadlines and frozen nominal1.8V/15PVT,
100/250/300/400MHz scope remain unchanged. No physical wholePLL case is qualified;
release and model-adoption status remain false.


2026-10-20 checkpoint045: common native RC substrate context validated

build/timing400/release_001/qualification_progress_045.json is the latest
immutable checkpoint. The opt-in OPENPLL_CAP_RC_SUBSTRATE mode passes24 native
default comparisons,24 installed-RC versus opt-in-C-only physical-control
comparisons, and three actual-DCO corner comparisons. All three DCO capacitor
matrices,8620 native devices and feedback match installed resistance-enabled
extraction exactly. Signed contribution accounting passes at all three corners.
No automatic full wire-R pass or .res.ext output occurs in the new C-only mode.
This proves the implemented substrate-context operation in the checked scope;
it does not qualify spatial C/junction placement, bulk impedance or timing.

Assembled-layout min/nom/max raw capacitor extractions are now attached at
poly_metal_full_RC_substrate_capacitance_001/{min,nom,max}. They share the existing
full-layout CAD memory lock, so only one native extraction runs at a time.
RC_substrate_capacitance_collection_001/{min,nom,max} waits on those exact jobs
and then audits all warning geometry, capacitor/wrapper coverage, and exact-zero
removal. Tracing is disabled on the broad views to bound output and runtime.
All jobs and assessments inherit the original deadline3136114.566309955
(about09:44UTC); preparation, queuing and assessment count against that cutoff.
Timeout remains inconclusive, and none of these jobs automatically retries.

The former C-only parent networks remain separate diagnostic evidence. No new
network is adopted as a physical runtime model. Bulk/well geometry and finite
impedance,34 VGND internal coordinate supports, physical C and junction
allocation and transient-error qualification remain open. No fresh native
frequency sweep is started with the retired model. The frozen nominal1.8V,
15PVT,100/250/300/400MHz scope and all release gates remain required. Physical
wholePLL passes remain zero; timing closure and release qualification are false.


2026-10-20 checkpoint046: native resistor material and minimum-corner full C

The latest immutable checkpoint is
build/timing400/release_001/qualification_progress_046.json. A private opt-in
R-node tracer records node origin bits and incident material types. The first
strict output comparison is retained as a failed attempt: native-generated
node names are unstable, and220 unattached internal representative coordinates
change. A coordinate/device anchored graph comparison proves a bijection for
all78613 exported nodes, checks four residual symmetry assignments, and
preserves resistor branch multiplicities, printed R intervals, MOS parameters
and exact mapped terminals. Real resistor-value, connection and MOS terminal
coordinate faults are rejected. The original pre-RC C matrix and native devices
are preserved. Backannotated C remains excluded:45 default-comparison pairs
differ beyond local print intervals, at most0.00001fF. The already-invalid old
RC model is not requalified by the R-only proof.

The native trace contains2994 output groups (automatic subset plus explicit
all-net pass). Its last2686 conductor groups recover all89955 .res.ext node
coordinate records exactly. All34 previously unresolved VGND internal points
are junctions with pwell-only incident resistors. Independent actual-GDS masks
place all34 in the default pwell domain; deep nwell is absent. All8204 internal
MOS-body records lie in the expected well material. Four additional records
are supply origins on metal4/metal5. Their actual top-level VGND/VPWR labels,
GDS conductors and cross-layer connectivity are verified independently. These
four origin coordinates are not asserted to be local physical MOS-body
locations. Bulk impedance, body connections at the origins, spatial C and
junction allocation, and transient-error enclosure remain unqualified.

Minimum-corner full-layout RC-substrate assessment completes:100462 devices
(99720MOS,726diodes,16intrinsic resistor wrappers),33669 active nodes and all359
parent nets. The raw49355117 C records contain27970463 exact zeros and21384654
positive capacitors, with no negatives. Zero removal changes no nonzero C,
floating branches or device cards. Native RC substrate preparation determines
all diode boundaries, so the old3014-warning assumption correctly fails and is
retained. Its replacement individually validates2288 decap warnings and all726
diode positions, areas, perimeters and body connections. The two obsolete
queued assessors are retired through verified pidfds after replacement
collectors are confirmed live; no native extraction or analog process is
signalled or retried.

Maximum and nominal extraction/assessment and exact old/new capacitor-context
comparisons remain under the original09:44UTC cutoff. Zero physical wholePLL
cases are qualified. The frozen nominal1.8V/15PVT,100/250/300/400MHz requirements,
remaining timing/interface and physical release gates are unchanged. Release,
model-adoption and timing-closure status remain false.


2026-10-20 checkpoints047/048: common-substrate check closed inside12h

The latest immutable state is
build/timing400/release_001/qualification_progress_048.json. All min/nom/max
native full-layout C extractions, geometry/warning audits, complete network
checks, exact-zero removal and sorted matrix comparisons finish before the
original09:44UTC cutoff. All source, assessment and comparison processes are
verified terminal; no native CAD/analog engines remain live. Historical running
observations are retained separately from the reconciled terminal job state.
The original budget is not reset and no native extraction is retried.

Each corner preserves100462 devices:99720MOS,726diodes and16intrinsic resistor
wrappers, with33669 active nodes and all359 parent nets. There are no negative
capacitors. Positive C counts are21384654(min),22512429(nom),23107833(max).
All device/continuation bytes match the corresponding older context exactly.
The new context changes12184/12188/12192 non-self C pair sums, respectively;
maximum pair changes are5.4/6.7/8.4fF and sums of absolute pair changes are
62.58900/87.34786/133.38906fF. These are matrix observations, not effective input
loads or a transient enclosure. Old C-only and RC-substrate data are separate.

For nominal, every changed edge connects fixed boundary nodes, so the old
floating-node energy certificate transfers by exact boundary-energy shifts;
no floating-node linear solve is repeated. Correct-context wire-only bounds
are PLLOUT214.299484198496..214.299484751137fF,
REFCLK266.006042761571..266.006043306299fF and
BBPD_RESET_N331.446626191197..331.446626748922fF. Other active boundaries remain
fixed incrementally, wire R is zero, nonlinear charge is excluded and the
actual FOM/distributed-RC enclosure remains unqualified.

An isolated unmodified upstream8.3.685 build is also checked after preserving
a premature-configure failure. Its actual DCO before/after full-R comparison
still loses the same two global junction area/perimeter parameter records and
changes14818 C pairs beyond local print intervals at zero export threshold.
It is not adopted, and neither installed Magic nor golden Xyce is replaced.
This does not compare failure counts directly against the older thresholded
model: the extractor version, formulas and export thresholds differ.

An isolated original-C1FINE160 buffer-only candidate is prepared at
sky130/IntegerPLL_DCO_einvp_c1fine160_buf8_sky130.v with OpenLane configuration
openlane/IntegerPLL_DCO_EINVP_C1FINE160_BUF8. It changes only out_buf fromHD buf1
toHD buf8; all691 connections, other690 cell types, original160-load fine bank,
public ports and encoding are preserved. Both library functions are A; wrong
input and extra-cell-change controls reject. No return-fine bank is added.
The new nominal library load domain contains the certified diagnostic load,
while buf1's nominal domain does not. Actual functional overload is not proven.
The candidate has no layout/native analog qualification and is not adopted.

The C/R support inventory covers8297230 native contribution events and12390661
support endpoints, with1295670 unique conductor/box pairs. Every original
conductor has a retained R representative;2030879 endpoint observations contain
one directly, while10359782 require nonzero geometric padding. The largest
representative-point gap is43835nm (for COARSETHERMAL_CODE[23]). Proximity alone
does not assign a physical capacitor location or bound transient error.
Canonical R-component/alias membership, omitted intermediate coordinates and
actual resistor-segment support must be resolved before interpreting large
gaps or constructing a runtime model. Intrinsic-resistor C, local junction
allocation, supply-origin body connections and bulk impedance remain open.

The full100/250/300/400MHz nominal1.8V/15PVT scope and all release gates remain
required. Physical wholePLL passes are zero. Fresh eligible runtime models,
range/calibration/reset reachability, timing/interfaces, mode changes and
physical release qualification are still needed; no release is declared.


Progress049 records the distributed-RC geometry work under
build/timing400/release_001/distributed_RC_model_qualification_001/owner.json.
Its12h deadline includes preparation, tool builds, extraction and assessment;
the completed common-substrate C check is not restarted. All native CAD/analog
engines are terminal at this checkpoint. Runtime and release eligibility remain
false, and physical wholePLL passes remain zero.

The retained reduced-network audit binds all78613 R/MOS/port nodes to original
conductors with no ambiguous bindings or provenance-group name differences.
The100 most remote signal C supports all touch the expected independent GDS
conductor. The source investigation finds that extresist simplify off still
allows ResDoneWithNode to combine series/parallel/triangle networks. A single
exported resistor therefore cannot inherit just its last creation rectangle.
The rejected single-segment binding and its evidence are preserved separately.

An isolated opt-in OPENPLL_R_RETAIN_MESH switch skips that reduction stage,
retains normal native output and avoids geometry mode's node alignment. Its
switch-off actual-DCO regression preserves the reference R/MOS graph and
original pre-R C/devices. The enabled extraction retains164344 positive SPICE
resistors versus97616 in the default export, with original pre-R C/devices,
exported model/geometry parameters and public ports preserved. Its independent
terminal-connectivity audit binds137004 voltage nodes and34476 MOS/intrinsic-R
terminals to original conductors with no shorts or missing bindings. These
checks do not qualify electrical impedance or repair inherited junction charge.

Creation geometry is recovered for130708 rectangular wire segments, alongside
35578 native contact branches. The native166286 resistor records exceed the
SPICE164344 branches;779 native branches have identical printed endpoint names.
Alias, repeated-name, killed-node and omission handling still require explicit
reconciliation before the mesh can become a runtime model. Pointer identity
must be preserved during that audit; conductor identity alone cannot merge
voltage nodes across a finite resistance.

For304 matched routed signal conductors,192763 unique C support boxes intersect
native resistor spans, including180920 that lacked an old retained node point.
Of15901 remaining boxes,7688 intersect full creation-tile extensions beyond
resistor breakpoints;8213 remain outside recorded creation tiles. Another
1087006 original support boxes are outside this survey's routed-signal scope.
The former43.835um maximum-gap example lies in a165nm terminal tile extension.
This establishes geometry context, not endpoint attachment, C integration
weights, an open-end resistance bound or spatial convergence.

Evidence is in DCO_retained_R_mesh_default_controls_001,
DCO_retained_R_mesh_001, DCO_retained_R_mesh_conductor_audit_001,
DCO_retained_R_mesh_geometry_001, DCO_C_R_segment_support_inventory_001 and
DCO_C_R_terminal_tile_support_001. The installed extractor and golden Xyce are
unchanged. Native-export reconciliation, unrecorded terminal regions, layer
identity, local junction/intrinsic-resistor charge, supply/body impedance and
transient convergence remain open before fresh frequency qualification. Frozen
100/250/300/400MHz nominal1.8V/15PVT scope and all release gates are unchanged.


Progress050 completes the native-to-SPICE resistor export accounting using
DCO_R_export_alias_audit_002. Original equivalence aliases explain all1942
omitted native branches:1163 join distinct native pointers with different
original alias names, and779 join distinct pointers with the same printed
name. None is a self-loop of one native pointer. Their physical voltage
equivalence is not established, so this is accounting evidence, not approval
to collapse them in a distributed model.

The remaining164344 branch multiplicities match exactly. Their values reproduce
SPICE exactly under the pinned EFread.c expression
float32(0.5 +1000*atof(native_ohms)), followed by six-significant-digit output
in ohms. The0.5 term adds0.0005ohm before float/print rounding; it remained after
resistor storage changed from integer to floating point.123102 exported printed
values differ from their native printed inputs. The first comparison, which
allowed only print intervals, rejects; its script is retained and the revised
audit models the actual source semantics rather than increasing a tolerance.

The next runtime-model step must preserve native node-pointer identities and
capture device-terminal bindings, handle public and supply boundary points
explicitly, and retain native resistance values without that reader bias.
No native CAD or analog runs are added in this accounting phase, the original
12h distributed-RC check deadline is unchanged, runtime/release qualification
remain false, and physical wholePLL passes remain zero.


Progress051 materializes lossless native resistor primitives at
build/timing400/release_001/DCO_private_R_primitives_001. All166286 positive
native resistors and148346 distinct voltage vertices are preserved. Values
come from full-precision native resistance records, without the extflat reader's
0.0005ohm addition. Every native .res.ext branch/value is independently
reproduced under its float32/six-significant-digit print semantics; parallel
branch multiplicities are retained and printed aliases never merge vertices.

Private node allocation/merge events resolve lifetimes and all34476 device
terminals without ambiguous bindings. Unique physical geometry associates all
8620 devices(4309NFET,4309PFET_HVT,2poly resistors) with original model cards.
The original and retained device-ID exports preserve their respective complete
cards and C matrices; the retained export also preserves all R records. All
original global junction records are retained as metadata. Zero-wire-R device
conductor correspondence passes, and an intentional gate/drain swap rejects.
These checks do not qualify physical local junction-charge distribution.

The new native binding run preserves the prior R/MOS graph and original pre-R
C/devices. Its separate device-ID assessment initially fails because logging
does not cover the active hierarchical writer selected by lvs defaults. The
completed native resistance data is reused. After adding that writer hook,
original and retained device-ID exports pass from saved .ext/.res.ext files;
no full R extraction is repeated for a missing diagnostic. Preparation and
failed diagnostic evidence are retained. This phase adds one full R run and
five saved-file exports, within the existing12h owner/deadline.

The trace also recovers8997 one-breakpoint conductor tiles. In the existing
304-signal-conductor survey, these explain7912 of8213 previously outstanding
C support boxes. Four boxes have multiple private-node candidates and297 remain
uncovered. Other original conductors outside that survey still require mapping.
Geometric intersections are not capacitor weights or an AC resistance bound
for a terminal region.

The wire_R_elements_unqualified.spice file contains resistor primitives for
later assembly; device_connections.json retains the geometry-linked original
cards and private terminal identities. Public signal/supply boundary attachment,
local junction/intrinsic-resistor charge, all-conductor C layer/weight mapping,
spatial convergence and transient correlation remain open. No new model or
candidate is adopted, no native CAD/analog engine remains live at checkpoint051,
and physical wholePLL passes remain zero. Frozen nominal1.8V/15PVT four-mode
100/250/300/400MHz qualification and all release gates remain required.


Progress052 checks all166286 private R branches and148346 voltage nodes:
there are exactly2686 resistor-connected components, one per original conductor,
with no split conductors or cross-conductor R links. Actual GDS pin labels,
native port rectangles, drawing coverage, origin flags and incident materials
map all308 public pins to310 physical layer interfaces and328 native origin
vertices. Eighteen signal pins have two coincident M3 origin vertices; both
remain identified as interface candidates. M4/M5 rail origins are kept on
separate physical interfaces despite their coincident xy coordinates.

The two declared VPB/VNB pins are isolated vertices with no MOS attachment and
no incident R layer. Their layer is established by the native declared port and
independent GDS M3 pin geometry. They are preserved as declared interface stubs.
The4309PFET and4309NFET bulk terminals instead bind to the VPWR and VGND mesh,
respectively. The initial incident-R-only boundary audit rejects the isolated
pin case; that failure is preserved and the separate geometry case is checked.

DCO_private_R_public_boundary_audit_002 holds the geometry/component evidence.
DCO_physical_boundary_connections_001 emits328 zero-volt point connectors under
an explicit point-boundary representation. Each connector matches the checked
map; the310 physical interface IDs keep M4/M5 supply feeds separate. This does
not qualify uniform potential over a complete pin surface, external driver or
parent-PDN feed distribution, or the final308-pin macro adaptor. No interior
R vertices are merged by a logical alias in these primitives.

No native CAD/analog run is added in this phase; all engines are terminal at
checkpoint052. The original12h distributed-RC deadline is unchanged. Capacitor
material/plane identity and all-conductor weighting, remaining297 surveyed
signal support boxes and4 multiple-node cases, local junction/intrinsic-R
charge, and external feed/body impedance qualification remain open. Runtime
eligibility, adoption and release remain false, with zero physical wholePLL
passes and the frozen four-mode nominal1.8V/15PVT release scope unchanged.


Progress053 completes capacitor surface accounting at minimum, nominal and
maximum RC using the original RC-substrate context. All8,297,231/8,297,230/
8,297,288 respective contributions have aligned plane/material metadata;
reconstructed matrices match within explicit native arithmetic/print allowances.
Native capacitance and all8620 device cards remain identical to the installed
reference. Missing-contribution and displaced-surface-serial controls reject
corruption. These are accounting checks, not spatial or transient qualification.

DCO_zero_length_junction_source_audit_001 independently maps152 zero-length
source terminals to actual poly/diffusion gates in76 decap_3 GDS instances.
Only two have nonzero pre-R exported source area/perimeter. The exporter falls
back to the entire connected node junction area/perimeter when local attributes
are absent. Consequently the prior requirement to blindly restore those two
global records is not a physically justified model repair. Local diffusion
geometry and nonlinear charge must establish the correct allocation first.
No junction area has been changed or adopted. Three diagnostic checker failures
are preserved separately; their fixes required no native CAD/analog retries.

The original12h check deadline is unchanged. Spatial weights for all conductors,
junction and intrinsic-resistor charge, external supply/driver feeds, body
impedance and the308-pin runtime adaptor remain open. No native CAD or analog
engine remains active at checkpoint053. Runtime eligibility, release and adoption
remain false; physical wholePLL passes remain zero. Frozen nominal1.8V/15PVT
100/250/300/400MHz qualification and all release gates remain required.


Progress054 resolves the static decap junction-area discrepancy. Actual GDS
diffusion polygons on both sides of each of152 decap MOS devices match the
private source/drain boundary points. Existing local drain area/perimeter values
match those independent polygons exactly. Each missing source has an equal,
separate physical region. DCO_local_decap_junction_candidate_001 adds local
source-area/perimeter candidate metadata for all152 devices and preserves all
original cards, all other device parameters and every private connection.

Native integer area/perimeter balance now holds exactly for both supply nodes:
NFET explicit(9638976,500830)+missing(434720,24624)=(10073696,525454);
PFET explicit(31593136,1211866)+missing(687648,34352)=(32280784,1246218).
Area units are25nm2 and perimeter units5nm. The original pre-R global fallback
adds the entire node inventory on top of already explicit local junctions.
Dropping those global records without recovering the missing local sources
also fails conservation. Both legacy choices are rejected. The corrected
geometry candidate is the basis for subsequent junction-charge qualification;
no new runtime model has been adopted and no capacitor matrix has been changed.

This phase adds no native CAD/analog runs and retains the existing12h deadline.
Nonlinear junction charge and spatial integration, all-conductor capacitor
weighting, intrinsic resistor/body charge, external public driver/PDN feeds and
the308-pin runtime adaptor remain open. Runtime eligibility/release/adoption
remain false and physical wholePLL passes remain zero. The frozen nominal1.8V/
15PVT100/250/300/400MHz qualification and all release gates remain required.


Progress055 recovers exact plane/material metadata for the301 unresolved signal
C support boxes. Independent GDS net probes on the recorded metal layer pass
for every box. The four multiple-single-tile cases each select one tile on the
correct layer. All297 previously uncovered boxes lie on metal1 islands with
one private mesh vertex identified by incident viali and via1 branches. This
identifies candidate locations; it does not establish uniform island voltage,
capacitor weights, resistance discretization error or transient accuracy.

DCO_unresolved_C_surface_survey_001 and DCO_unresolved_C_layer_geometry_001
preserve the ordered trace/GDS evidence. DCO_layer_qualified_C_endpoint_inventory_001
scans all8,297,230 nominal contributions and12,390,661 endpoint occurrences.
It retains1,355,315 distinct conductor/plane/material/box entries, including
active, local interconnect, every metal layer and wells. Every recorded endpoint
conductor has a corresponding native private-R conductor after explicit
@SUBSTRATE-to-VGND normalization. Logical conductor coverage does not establish
physical placement or impedance. Implicit ground endpoints and intrinsic
resistor/body charge still require their physical distributed representation.

No native CAD/analog run is added; the original12h deadline remains unchanged.
Complete all-conductor physical geometry/weights, min/max endpoint coverage,
junction/nonlinear charge and integration error, external driver/PDN feeds and
the308-pin runtime adaptor remain open. Runtime eligibility/release/adoption
remain false; physical wholePLL passes remain zero. The frozen nominal1.8V/
15PVT100/250/300/400MHz qualification and all release gates remain required.


Progress056 establishes a bijection between all2686 native conductors and2686
independent GDS connectivity clusters. All26,168 transistor/resistor-terminal and
public-pin seeds match without missing/ambiguous probes or multiple clusters.
This topology registry does not merge any private resistor voltage vertices.

DCO_all_C_endpoint_GDS_identity_001 checks all1,355,315 distinct nominal
conductor/plane/material/box entries:1,283,682 conductor-layer entries and71,633
well entries pass endpoint/midpoint sampling with1nm boundary neighbourhoods.
This checks sampled identity, not continuous box coverage or voltage weights.
Min/max support sets differ slightly from nominal: min adds5 and omits8 boxes;
max adds10 and omits6. DCO_corner_extra_C_support_geometry_001 checks all15
extra diffusion boxes against their full GDS conductor area and correct well.
Thus every corner's recorded supports are covered by nominal sampled evidence
plus explicit extra-box geometry checks. Capacitance coefficients still differ
by corner and must receive their own conservative distributed representation.

DCO_all_junction_region_audit_001 maps all17,236 source/drain terminal records
of8618 MOS devices to10,386 independent physical diffusion regions. Every local
area/perimeter share matches; there are no missing/ambiguous terminal regions,
mismatched shares or unowned regions. Exact GDS totals are NFET1,032,241,950nm2/
9,803,860nm perimeter and PFET1,553,464,600nm2/13,098,620nm perimeter. This closes
static local junction geometry after the152 decap-source repairs; nonlinear
charge, body impedance and distributed integration accuracy remain unqualified.

DCO_exact_junction_device_primitives_001 emits8620 device primitives on private
mesh vertices with34,472 exact MOS junction parameter values. It removes1138
rounded parameter values from the previous local candidate; maximum relative
print rounding was0.0000539811066127, approximately54ppm. Original cards remain
unchanged in metadata; all other parameters and every private terminal connection
are checked on readback. This is a component for model assembly, not an eligible
runtime deck. No distributed capacitor model or external feed has been adopted.

This phase adds no native CAD/analog runs. All check processes are terminal at
checkpoint056 and the original12h deadline remains unchanged. Distributed C
voltage weights, full native-matrix conservation/passivity, whole-support and
spatial integration error, implicit-ground and nonlinear/intrinsic-resistor
charge, min/max private-R values, external driver/PDN feeds and the308-pin adaptor
remain open. Runtime/release/adoption remain false, physical wholePLL passes
remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz qualification and all
release gates remain required.


Progress057 resolves creation-to-private-node orientation for all130,708 wire
branches from retained allocation/merge histories. ResSetPathRes can reverse
endpoint slots, so creation order cannot be copied blindly. All14,913 reused
allocation addresses are considered with every possible lifetime;8617 branches
require merge ancestry. Every branch has one admissible final endpoint pairing.
No closest-coordinate inference or printed-name voltage merge is used, and no
native extraction is repeated. The first CPU checker is stopped to replace a
per-branch full-node scan with direct lookups; its script/interruption receipt
is retained separately and the completed v2 is pinned.

DCO_native_tile_voltage_basis_001 builds55,663 continuous piecewise-linear tile
voltage bases from those branches. There are no axis gaps/overlaps or voltage
discontinuities between adjacent segments. Exact rational nonnegative axis
integration preserves partition of unity; nonuniform-chain affine controls,
open-end clamp integrals and a reversed-endpoint rejection control pass. Native
geometry includes140 branches whose breakpoints extend outside their creation
tile and21,200 tiles with open-end extensions. Their physical approximation
error remains unqualified; no capacitor contribution weights are emitted.

DCO_C_charge_kernel_metadata_audit_001 confirms that existing support boxes
identify candidate geometry but do not retain every local charge integration
region. The309,861 nominal tile_perimeter entries use whole tile bounds, losing
the contributing local edge interval. The3,460,669 edge_fringe entries retain
whole target tile bounds, while the native computation first clips the target
to a local fringe halo and uses a distance-dependent atan kernel with recursive
shield corrections. An actual traced target-well example rejects uniform charge
over the complete target box because it spills charge outside the native
longitudinal integration interval. Earlier matrix-accounting and sampled GDS
identity evidence remains valid; it never qualified local charge weights.

Next instrumentation must preserve local perimeter edges, overlap patches,
clipped fringe/sidewall kernels, shield exclusions and roundoff residuals aligned
with contribution/surface serials. Use a new isolated Magic source/prefix to
preserve currently pinned sources. Then integrate the kernels on the private
voltage bases and check full native matrix conservation, passivity and physical
error before runtime use. This phase adds no native CAD/analog runs; all checks
are terminal and the original12h deadline is unchanged. Runtime/release/adoption
remain false, physical wholePLL passes remain zero, and frozen nominal1.8V/15PVT
100/250/300/400MHz qualification and all release gates remain required.


Progress058 creates an isolated Magic source/prefix for local charge kernels;
previous pinned sources are unchanged. The new optional kernel stream preserves
local area/edge supports, clipped fringe rectangles, near/far distances and atan
multipliers, overlap and recursive shield patches, sidewall paired edge spans,
physical coefficient/rule values and links to every existing contribution serial.
Existing contribution and surface formats and native capacitance formulas remain
unchanged. A fresh parallel build exposes Magic's generated database-header
race; its failed logs are preserved. Build002 generates the header serially
before parallel compilation and completes without replacing the installed tool.

All12 small case/corner controls preserve native C/device/feedback output and
reconstruct local kernel integrals. Wrong kernel ID, whole-tile perimeter and
whole-target fringe substitutions are rejected in every case. The bounded-memory
reader with deadline checks reproduces all12 saved native outputs exactly and
rejects an expired deadline without repeating extraction.

Actual nominal DCO extraction passes8,297,230 contribution checks on7,421,041
local kernels, including1,626,941 candidates that emit no nonzero contribution.
There are no split rectangles. Native capacitance,8620 device cards and feedback
match the original RC-context reference; native matrix reconstruction also
passes. Accumulator/zero-clamp residuals are retained separately from physical
local integrals and do not yet constitute a qualified transient error bound.
The same controller continues minimum/maximum RC under the original12h deadline.
Its active handle is DCO_C_kernel_trace_controls_001/status.json; preserve
completed native outputs if any later assessor fails.

local_C_energy_integration.py integrates voltage products with exact rational
second moments and a positive Gram decomposition for positive uniform patches.
Controls check analytic mass matrices, zero-wire-R uniform voltage conservation,
orthogonal affine fields and refinement invariance; squaring an average voltage
is rejected by a nonuniform-field counterexample. This is a local integration
component, not a full signed DCO capacitance matrix or global passivity proof.

DCO_native_mesh_node_plane_inference_001 resolves all35,578 contact endpoint
plane pairs and8997 single-breakpoint tile planes in three propagation passes.
All148,346 private vertices have native plane associations. Multiple-plane
zero-R interfaces, including312 native locali/well vertices, remain explicit;
this topology inference is not physical contact-sheet impedance qualification.

A parallel check now tests every complete nominal C box/edge/point against its
actual GDS conductor and material/well mask, strengthening earlier samples.
It uses1nm conductor expansion and a1nm corridor around closed edges/points.
The verified live handle is DCO_complete_C_support_GDS_geometry_001/status.json.
Both follow-ups retain the existing12h deadline; no analog engine is running.
Min/max kernel assessment and complete-support geometry are pending at058.
Full C field assignment, signed global passivity, implicit-ground/nonlinear
charge and RC error, min/max R values, external feeds and the308-pin adaptor
remain open. Runtime/release/adoption remain false, physical wholePLL passes
remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz qualification and all
release gates remain required.


Progress059 completes all three actual-DCO local charge-kernel checks. Native
C matrices,8620 devices and feedback match the reference at min/nom/max; every
contribution has aligned local kernels and reconstructed physical integrals.
The complete nominal GDS box/edge/point check passes all1,355,315 entries.
Neither result by itself qualifies capacitor voltage weights or runtime timing.

A separately isolated R-domain tracer captures every pre-merge tile breakpoint
and the actual working plane of each contact copy. Native resistance/device
comparisons pass. The complete lifetime index resolves65,162 anchored domains:
55,663 multi-voltage wire domains and9499 constant domains. Of the latter,502
had multiple coincident breakpoints and were absent from the old segment/single-
breakpoint inventory. No domain or contact working plane is missing. A premature
build invocation is stopped by its missing-preparation-receipt guard before any
compiler/native launch; its failure is preserved and source preparation is
confirmed terminal before the actual build. No native extraction is retried.

DCO_complete_domain_model_primitives_001 rebuilds166,286 positive native wire
resistors,8620 devices with the exact local junction parameters, and all65,162
voltage fields in a consistent new _rdomain_ namespace. Wire endpoints are
bound by exact tile breakpoint lifetimes. Native printed R multiplicities and
values reproduce exactly; no older private node identities are mixed. All
148,346 nodes form exactly2686 R-connected components, one per original
conductor, without split or cross-conductor components.

Correction to058's unqualified plane inference: all480 well-tap contacts have
three copies on well, active and local-interconnect planes, with three distinct
voltage nodes and two finite contact resistors. There are160 psubdiffcont and
320 nsubdiffcont taps. The earlier two-plane inference is rejected for runtime
use; its312 combined locali/well annotations were inference artifacts, not
established zero-R interfaces. Direct records now give one working plane for
each private node; the two isolated public stubs use their checked port-layer
evidence. All35,578 contact edges reproduce the direct adjacent-copy topology.
DCO_direct_native_planes_and_boundaries_001 rebases328 point connectors for308
logical ports/310 layer interfaces using original source BPs and native origin
flags. M4/M5 supply interfaces remain separate; external feeds and uniform
whole-pin potential remain unqualified.

DCO_voltage_domain_coverage_002 checks every complete nominal C support against
typed anchored voltage domains using exact5nm-grid rectangle/interval unions.
Every support passes and typed domain interiors are disjoint. Its1370 independent
KLayout controls match the prior1nm expansion/corridor definition across all15
material types. All5 minimum and10 maximum corner-only supports also pass. The
slower duplicate Boolean assessor is stopped only after the equivalent full
check completes; partial results and supersession evidence are preserved. No
native result is repeated and the original12h deadline is unchanged.

All checks are terminal at059. The next stage assembles local area/perimeter/
overlap/fringe/sidewall energy matrices on the complete family, retaining signed
shield corrections and roundoff residuals. Full native zero-R C conservation,
signed global passivity, spatial/open-end/transverse error, nonlinear/implicit-
ground/intrinsic-resistor charge, min/max R values, external feeds and the308-pin
runtime adaptor remain open. Runtime/release/adoption remain false, physical
wholePLL passes remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz
qualification and all release gates remain required.


2026-10-20: qualification_progress_060.json records the first owned local C
operator compilation on the complete native resistance-domain family.
DCO_local_C_operators_nom_001 contains15,646,598 signed operators from all
8,297,230 nonzero nominal contributions and7,421,041 native kernels. Every
operator integral matches the separately recorded physical kernel total; all
9511 field entries (including the explicit substrate reference) are accounted
for. Every physical field maps to the complete typed domain atlas. Area,
perimeter, overlap, sidewall, clipped arctan fringe and signed shield corrections
remain separate. Native accumulator/clamp residuals have their own ledger.
The native convention omitting explicit intra-conductor pair coupling is kept;
this result is numerical extraction accounting, not absolute silicon accuracy.

local_C_operator_compilation_001 audits all12 saved native control cases and
pins the nominal compiler inputs to the preceding native extraction receipt.
The first small-control implementation failed on an unlocated zero-clamp
plane=-1; its partial outputs and source are retained. Version2 gives that
adjustment no spatial operator and records its arithmetic-only conductor
ledger. All12 control cases then pass. No native extraction was repeated.

local_C_field_integral_controls_001 passes exact rational area comparisons,
an exact line mass comparison,21 independent adaptive fringe-moment checks,
and8 signed fringe-field energy/charge checks spanning all four directions.
Adjacent independent domain partition controls pass; wrong inward-side and
uncovered-area controls are rejected. These checks integrate voltage products,
including their variance; they do not square an averaged field.

The nominal full sparse matrix assembler and the min/max saved-trace compilers
are live at060; process identities and observed statuses are retained in that
snapshot. The assembler uses one-sided physical edge ownership and actual
source-edge projections, with no nearest-node attachment or logical-alias
voltage collapse. The substrate reference is explicit and does not merge the
interior well voltages. check_assembled_local_C_matrix.py is prepared to check
zero-wire-R collapse and diagnose the signed global spectrum after assembly;
it has not yet qualified a DCO matrix. Full passivity, spatial/numerical error,
corner R values, external feeds, runtime integration and all frozen release
gates remain open. No runtime model is adopted; physical wholePLL passes remain
zero. The original12h owner/deadline is unchanged and release remains false.


2026-10-20: qualification_progress_061.json records the first complete nominal
C matrix and its rejection. All three retained native RC operator streams pass
accounting. DCO_domain_R_corners_002 reproduces every one of166,286 nominal
native R values exactly from float32 sheet/geometry or contact-array formulas,
and emits positive ordered min/nom/max values on the same private topology.
DCO_contact_cut_count_geometry_001 independently matches all35,578 finite
contact branches to actual GDS cuts. DCO_poly_resistor_charge_accounting_001
resolves the two generic-poly intermediate records: their native fields are
R=50,C=0, with no nonzero pair capacitors. The original two-terminal PDK model
contains one resistor and no charge element, and both exact devices remain.
This is native/PDK bookkeeping, not an absolute silicon charge claim.

signed_C_Xyce_controls_002 checks the signed-branch realization of a passive
field mass matrix against its independent analytic PWL response. Golden Xyce
accepts the negative individual capacitor required by that matrix; errors are
below1e-5V. The two configured max-step variants take identical adaptive samples,
so this proves representation compatibility, not independent time-step
convergence or actual-DCO accuracy. A CSV case-name reader failure reuses the
completed baseline; it does not repeat an identical native check.

DCO_local_C_matrix_nom_001 integrates15,646,598 operators into a148,347-vertex
matrix with9,371,163 nonzeros. Its maximum relative charge-row residual is
7.2606e-12, and DCO_local_C_matrix_nom_checks_001 passes zero-wire-R native
physical-total recovery. It FAILS signed passivity:101 diagonal entries are
negative and the minimum normalized eigenvalue is-0.3333764003. The matrix is
explicitly rejected for runtime adoption. DCO_corner_matrix_stop_after_nominal_
failure_001 preserves and stops both CPU corner assemblies at9,220,000 operators;
no DCO transient is launched with the rejected matrix.

DCO_negative_C_diagonal_diagnosis_001 reconstructs the worst private metal2
VPWR diagonal exactly:-11.74349141 native capacitance units. Ground-shield
subtractions exceed the local positive ground and coupling contributions.
DCO_negative_C_kernel_inspection_002 examines the ten largest negative events:
eight are fringe-halo and two blocked-fringe kernels; six explicitly skip pair
updates because both surfaces belong to the same ideal conductor. Those pairs
can carry different local voltages after finite wire resistance is retained.
Recovering their latent overlap/fringe/sidewall energy is a concrete candidate
repair; its sufficiency is not yet established. No eigenvalue clamp, arbitrary
capacitor relocation, or runtime adoption is performed.

qualification_progress_062.json records the isolated owner-trace followup.
magic_C_owner_source_001 reproduces the frozen tracer before adding optional
pair ownership records and otherwise skipped self-sidewall geometry/rules.
Self-sidewall diagnostics return before the native coupling hash is touched.
The isolated build and all12 native controls pass exact C/device/feedback
comparisons. DCO_C_owner_trace_001 also preserves the actual nominal DCO native
matrix, all device cards and feedback. The installed extractor and golden Xyce
are unchanged.

DCO_self_C_extension_controls_002 verifies all12 cases with contact-plane
normalization from the exact retained native SURFACE observations. It preserves
all83,838 original energy operators exactly and adds10,050 self-pair operators.
These added terms vanish when each original conductor has uniform voltage.
The decoder verifies78 actual contact normalizations, including distinct poly/
locali and locali/metal1 residues. Earlier CPU reader failures and partial
outputs are preserved; the contact decoder correction needs no native rerun.

compile_local_C_operators_v5.py is running on the full nominal owner trace in
DCO_local_C_operators_nom_self_002 at062. After it finishes,
separate_DCO_self_C_increment.py must prove exact identity of every original
operator before assemble_DCO_self_C_increment.py may reuse the original
numerical sum and add only missing terms. The corrected matrix then requires a
fresh zero-R collapse and signed passivity check before diagnostic SPICE export.
The first matrix remains rejected. Full corrected min/max, numerical/spatial
and integration qualification and all frozen nominal1.8V/15PVT four-mode
release gates remain open. Physical wholePLL passes remain zero. The original
12h owner/deadline is unchanged; release/adoption remain false.

qualification_progress_063.json records completed restored self-pair C matrices.
All three corners reproduce the zero-wire-R physical operator totals. Nominal
and minimum C pass the full numerical signed-passivity check. Maximum C fails
with two normalized negative modes (-0.00032808623 and -0.00013750135), despite
having no negative diagonal. DCO_max_C_negative_mode_diagnosis_001 preserves
both modes and confirms negative energy at max C for the same voltages that
have positive energy at min/nom C. The max matrix remains rejected; no clamp
or coefficient replacement is used. trace_DCO_max_C_mode_energy.py is tracing
the failed mode back to every owned operator under the original deadline.

All 15,646,598 original nominal operators are preserved exactly and 2,642,914
latent self-pair operators are added. Of 2,723,364 new nominal support boxes,
2,656,437 inherit previous complete GDS coverage; direct independent checks
pass for all remaining 66,927. This proves geometric support, not transient
accuracy or full RC-corner qualification.

DCO_domain_candidate_nom_001 exports the checked nominal matrix with all
166,286 finite resistors, 8,620 native devices and explicit point feeds. Its
ideal-feed wrapper is diagnostic. The initial full native point omitted an
explicit linear solver and entered the MPI default iterative/hypergraph path.
Its verified process was stopped with a configuration receipt; the changed
run explicitly selects upstream KLU with identical circuit and original 12h
owner. The KLU point is live at the063 observation, still at initial DC bias.
No oscillator frequency has yet been qualified.

split_DC_initialization_controls_001 passes all three native controls: removing
only constant capacitors preserves DC bias exactly; restoring their saved
initial charge with IC/UIC reproduces linear/BSIM waveforms within0.15uV.
The completed native outputs use STD .prn with explicit -o on this build;
assess_split_DC_initialization.py fixes the reader without repeating any native
case. run_DCO_C_free_DC.py now tests the actual DCO DC equations with all R,
nonlinear devices and feeds unchanged, preserving the active full-C baseline.
Saved-bias equivalence to the full DCO and actual startup remain unqualified.
All frozen release gates, nominal1.8V/15PVT scope, original deadline and zero
physical wholePLL passes remain unchanged; release/adoption remain false.

qualification_progress_064.json proves exact canonical support geometry identity
for all2,642,914 added self-C operators at min/nom/max. Their conductor, plane,
material, area/edge/fringe supports and directions have identical ordered SHA256
46abbb7a84b0e48e6280e7b9ecb8911974d9b8075389c77edd7163ee6a6e9d59.
The nominal prior-union/direct-GDS proof therefore covers the added supports at
all three corners. Coefficients and density multipliers were excluded only
from this geometric comparison; no electrical result transfers across corners.
Max C still has two negative-energy modes and remains rejected.

assess_DCO_domain_point_STD.py is prepared to read the completed golden native
STD output and original receipt without repeating a native case. It requires a
terminal successful simulator receipt, checks the stored waveform digest and
measures actual output edges. It does not qualify convergence, frequency models
or parent loading. At064 the full-C KLU point and C-free DC-only diagnostic are
both verified live; the owned max-C energy trace is also live. Their shared
original12h deadline is unchanged. All release gates and physical wholePLL
passes remain open/zero; release and adoption remain false.

DCO_DC_constraint_topology_001 independently unions all166,286 finite-R branches
and confirms exactly one connected component for each of2,686 original
conductors. All328 private point-constraint endpoints are unique; the ideal
constraint graph has no cycle. There is no purely resistive component lacking
both devices and ports, and no gate-only component without a conducting-device
terminal or port. This excludes those structural hypotheses for the slow DC
run; it does not establish nonlinear DC convergence or change the circuit.
The existing same-owner native runs and max-C energy trace remain active.

qualification_progress_065.json records the completed physical-R DC bias and
full max-C energy reconstruction. DCO_domain_nom_tt27_c0_f247_C_free_DC_001
passes upstream Xyce with all166,286 physical wire resistors and8,620 native
devices unchanged, only constant CFIELD capacitors open in DC. It saves all
174,508 voltage nodes. Native elapsed time is1,163.45s;53 linear solves consume
1,127.86s. No nonlinear convergence or linear-solve failure occurs. This is an
exact DC equation-preserving preparation, not dynamic-model qualification.

DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001 is a separate conditioning
comparison: original conductor components become ideal wires, all8,620 device
cards retain their models/parameters, and no dynamic result is claimed. Its DC
run passes in17.9582s with28,847 unknowns. The strong speed difference motivates
explicit initial-guess and stock-solver comparisons. Seeded physical-R DC runs
with upstream KLU and stock BASKER are live at065; the BASKER environment requests
8 OpenMP threads, but parallel speedup is not established and an intermediate
singular-pivot message is retained. No engine source is modified.

run_DCO_domain_point_v4.py verifies complete saved voltage coverage:148,346
physical nodes,25,854 BSIM internal nodes and308 public nodes. Small independent
native controls already verify full-C IC/UIC charge initialization from C-free
DC. The new80ns full-C deck preserves the actual candidate, ports, tolerances,
KLU solver and stimulus; only saved-IC/UIC initialization and output precision
change. The prior live full-C KLU DC solve is stopped only after preparation,
PID/argv/process-group verification and a reason receipt in
DCO_domain_nom_tt27_c0_f247_80ns_klu_001/stopped_for_saved_IC_initialization.json.
Its exit-15 is an intentional initialization change, not a physical test result.
DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001 is the one new full-C instance under
the same original deadline; no two large full-C instances overlap.

DCO_max_C_mode_energy_trace_001 reconstructs the negative mode from all18,290,414
unchanged owned operators: matrix energy-151.2715403562 versus reconstructed
-151.2715403126 in native capacitance times voltage-squared units. Ground terms
sum negative and pair terms only partially compensate. The largest negative
terms are retained with exact event IDs, fields and supports. Their underlying
max-C native kernels are being inspected in DCO_max_C_mode_kernel_inspection_001.
No eigenvalue clamp, coefficient replacement or max-C model adoption occurs.
All release gates, four modes, nominal1.8V/15PVT scope and original12h deadline
remain unchanged; physical wholePLL passes remain zero and release stays false.

qualification_progress_066.json records the substrate-output convention
experiment at all three RC corners. ExtBasic.c explicitly writes zero C for the
native global substrate node; the prior finite-R operator model retained its
internal G accumulator against a separate explicit reference. The experiment
omits all1,113,704 original-substrate G operators, positive and negative, while
retaining every explicit inter/intra-conductor pair operator. It does not clamp
eigenvalues or selectively remove negative coefficients.

DCO_local_C_matrix_{min,nom,max}_no_substrate_G_001 and their separate checks all
pass charge conservation, unchanged zero-R capacitance and numerical signed
passivity. The maximum corner's two former negative modes disappear; its first
three normalized eigenvalues are approximately0,0.00420188,0.00447171. Minimum
and nominal also pass. This is a candidate modeling-convention correction;
finite-R return geometry, spatial/dynamic uncertainty and actual PLL behavior
remain unqualified. The original raw-G max matrix remains rejected and all
revised model adoption/release flags remain false.

DCO_physical_C_ledger_native_output_001 independently compares each physical
operator ledger with the final native .ext capacitances, including substrate
coupling relocation. All three corners pass the retained native print and
arithmetic allowances. Independent missing-pair controls fail as expected;
there are no final output-zero-clamp events in these DCO traces. The20 largest
negative ground terms inspect as15 BLOCKED_FRINGE and5 FRINGE_HALO kernels.

The seeded physical-R KLU DC run passes in866.103s, versus1,163.45s without the
seed; their174,508 saved voltages differ by at most2uV at native SAVE precision.
The same-seed BASKER comparison is stopped after1,565.17s because it has already
exceeded completed KLU elapsed time. A PID/argv/process-stat and exact circuit/
initial-guess comparison receipt is retained; no physical failure is inferred.

DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001 runs the unchanged retained
native35051 capacitor statements and device deck as an ideal-wire diagnostic.
It reaches transient calculation and provides a reference waveform, never a
finite-R release result. The full-domain saved-IC transient also reaches
transient calculation. Both remain under the original12h owner at066; no
frequency range or calibration is yet qualified. All four release modes,
nominal1.8V/15PVT scope and remaining gates are unchanged; physical wholePLL
passes remain zero and release stays false.

qualification_progress_067.json records the corrected nominal diagnostic deck
DCO_domain_candidate_nom_substrate_output_001, exported from the checked
substrate-G output-convention matrix. It preserves all native nonlinear cards,
finite-R branches, physical ports and explicit pair capacitance, with the
native-discarded original-substrate G accumulator omitted. It remains an
unadopted candidate with finite-R return and dynamic-error qualification open.

The exact golden container build inventory confirms Release/-O3, KLU/BASKER/
KLU2 support, no SuperLU/MUMPS/ShyLU-BASKER, and no Kokkos OpenMP. The engine and
libraries are unchanged. Bounded AztecOO comparisons retain their actual failed
results: singleton filtering crashes in EpetraExt::LinearProblem_SolverMap;
factory ILUT without that filter fails in its U triangular solve; legacy
RILUK(k=1) reaches the180s performance limit without the requested1e-12 linear
residual. Inputs, decoded crash evidence and changed configurations are retained;
no numerical or physical pass is inferred and no identical native retry occurs.

DCO_fast_internal_R_node_analysis_001 measures61527 nonterminal degree1/2 R
vertices while retaining all34413 device/interface/reference vertices. Its
positive-inverse RC comparison bound peaks at4.958766ps;20481 candidate vertices
meet a1fs cutoff and51198 meet10fs. These are candidate-state comparison bounds,
not a qualified oscillator-frequency error. No state, resistor or capacitor is
removed. Any passive DC-exact condensation requires explicit dynamic-error and
native validation before adoption.

qualification_progress_068.json also records the final180s iterative comparison
using the stock MPI AMD ordering/default RILUK fill2 and a300-vector GMRES
subspace. It remains inconclusive at1e-12 tolerance; no iterative configuration
is adopted. The original full-domain saved-IC and native ideal-wire reference
transients remain verified live within the same original12h owner. Their partial
waveforms are not release frequency evidence. All four modes, nominal1.8V/15PVT
scope and six release gates remain unchanged; physical wholePLL passes remain
zero and release/adoption remain false.

qualification_progress_069.json records an isolated passive path-condensation
prototype, not a selected runtime model. passive_RC_condensation.py keeps every
device terminal and physical point port. It reconstructs only nonterminal R
paths of degree1/2 by their DC harmonic voltage, adds exact positive series
resistances, and projects the complete C energy as T-transpose*C*T. It preserves
within-field variance and accounts for every original R branch.

passive_RC_condensation_controls_002 passes independent analytic series-RC,
parallel-R/series-C and uniform distributed consistent-mass RC-line controls.
The line's DC resistance and first capacitance moment match closed-form values;
its complex port admittance respects the predicted dynamic error envelope over
61 frequencies. Opposite terminal voltages retain nonzero field energy. Device/
interface and unsupported branch-vertex elimination guards are tested. The
initial control failed on low-frequency Schur-subtraction roundoff (absolute
4.17e-20S below eps*G); its result is preserved and the reference allowance is
scaled to conductance. The implementation did not change for that correction.

DCO_passive_path_condensation_nom_1fs_001 retains127866 of148347 voltage vertices,
removing20481 internal candidates while preserving all34413 protected vertices.
Its recomputed internal RC comparison bound is0.888187fs. It has145764 positive
R branches and4895239 scalar C branches; the maximum DC Schur difference is
1.98e-13 relative, harmonic residual1.76e-16, and zero-wire-R C changes by at most
5.82e-9 native capacitance units. Separate numerical passivity and native zero-R
conservation checks pass. No nonlinear card, active native case or final design
is changed. A port-admittance bound alone does not qualify oscillator frequency,
waveform or physical return error; those checks remain required before adoption.

The original full-domain saved-IC and native ideal-wire transients remain live
under the unchanged original12h deadline. All four modes, nominal1.8V/15PVT
scope and six release gates remain unchanged; physical wholePLL passes remain
zero and all prototype release/adoption flags remain false.

### 2026-10-20 — Exact ground substitution checked independently (progress070)

Native finite-R/signed-C/BSIM controls pass replacement of unobserved external
constant-zero voltage constraints with SPICE ground. Maximum voltage difference
is5.09e-7V, supply-current difference1.50e-9A and rising-crossing difference
9.30e-18s. A separate full-testbench audit derives the zero constraints directly
from the original sources and checks all308 macro ports,296 substitutions and
174212 retained initial voltages. Removed initial voltages are exactly zero.
The physical macro source, finite resistors, capacitors, devices, private point
connectors, nonzero/dynamic sources, numerical settings and observations remain
unchanged. No physical wire node is eliminated or approximated.

After preserving a process-identity stop receipt for the original full-R run
(which had only its time-zero sample), the exact-ground case starts under the
same original12h deadline. Native Xyce reports174551 unknowns,592 fewer than the
original constrained formulation, and begins transient calculation. The native
ideal-wire reference continues separately. Full-DCO performance improvement is
not yet demonstrated; neither this transformation nor partial/ideal-wire output
qualifies oscillator frequency. All six release gates and the frozen four-mode,
nominal1.8V/15PVT scope remain unchanged and open.

### 2026-10-20 — Corrected-C full-R testbench prepared (progress071)

The corrected nominal substrate-output-convention candidate now has a pinned
exact-ground80ns diagnostic testbench prepared for later execution. Streaming
comparison of both full macro sources checks every non-capacitor statement,
including all finite resistors, device definitions, point sources and wrappers,
for exact token identity. Only the physical macro include path changes in the
testbench. Its saved DC voltages, sources, observations and numerical settings
remain unchanged; constant capacitors do not alter the DC operating equations.
The corrected source contains5492690 scalar capacitor branches. Preparation
launches no native process, grants no model adoption, and does not extend the
original12h deadline. Existing full-R and ideal-wire runs continue separately;
frequency, physical-return and convergence qualification remain open.

### 2026-10-20 — Stock symbolic fill diagnosis and serial build (progress072)

A standalone helper linked against the unchanged installed Trilinos KLU archive
analyzes passive C+R patterns, without numerical factorization or SPICE changes.
The original named-reference pattern estimates123986678 entries per factor and
5.4896e11 factorization operations. Grounding the reference estimates126130296
entries per factor and5.8085e11 operations; the corrected-C grounded pattern is
identical. Thus grounding does not reduce this passive-block ordering estimate.
The isolated20481-state path prototype estimates106565447 entries per factor
and4.5048e11 operations, about22% less than the grounded full block. These graphs
exclude nonlinear Jacobians, BSIM internal unknowns and point-source MNA rows;
their estimates do not qualify full native runtime or oscillator accuracy.

An isolated unmodified upstream serial Trilinos/Xyce build is now live under
the original campaign deadline. The current MPI build's stock Amesos adapter
does not apply Xyce's serial-only KLU_REPIVOT option; the stock serial build
allows evaluation of factor reuse without patching source. It uses a separate
prefix and eight build workers; the installed golden binary, physical decks
and two active native runs remain unchanged. Build completion, independent
equivalence controls and actual reuse performance remain pending. No serial
binary, reduction or frequency model is adopted and all six gates remain open.

`check_stock_serial_factor_reuse.py` is now waiting on the identified live
stock-serial build, with its process identity and original deadline retained in
`stock_serial_factor_reuse_controls_001/owner.json`. After successful build
completion it will run KLU_REPIVOT=1 and0 sequentially against the retained
golden finite-R/signed-C/BSIM control. It checks complete waveforms, voltages,
supply current and rising crossings, revalidates model/binary pins, and uses the
shared native admission lock. Build failure, loss of the identified build or
the original deadline ends the queued check without a retry. These controls
grant no full-DCO speed or frequency qualification and cannot replace an active
full-R case. Their live status is in the controls directory's `status.json`.

The separate `run_DCO_stock_serial_corrected_point.py` handoff is queued in
`DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_001`. It waits for those
native controls to pass, validates the prepared corrected-C deck and binary,
and prepares a complete pinned manifest before inspecting the prior full-R run.
It defers replacement if that process changed or has any positive-time sample.
Otherwise it retains a process-identity stop receipt, waits for the old full
instance to exit, then starts one corrected-C serial full-R diagnostic using
KLU_REPIVOT=0. It changes neither physical R/device cards nor the80ns duration,
10ps maximum step, reset or saved bias. Both C convention and serial solver
change, so this is not an isolated solver-performance comparison. No budget is
restarted and no frequency, model or release qualification is granted.

### 2026-10-20 — First full-R step; throughput-aware handoff (progress073)

The full-R exact-ground native run reaches its first10ps sample after about32
minutes. This is actual transient progress, not settled oscillator evidence.
The initial handoff's blanket preservation of any positive-time sample could
retain a run whose rate is far below the remaining budget. Only that waiting
handoff process was stopped, with an identity/supersession receipt; neither
native DCO simulation was interrupted.

The replacement handoff in
`DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002` records wall-clock
and simulation-time observations every30s. After native serial controls pass,
it requires at least120s of observations and preserves a prior run that has
reached its measurement window, or whose fastest recent observed rate projects
completion within twice the remaining budget. Otherwise it may replace the
slow run after retaining its waveform and process receipt. The rate projection
is a diagnostic scheduling decision, not a guaranteed runtime bound. Full
finite-R/device content, physical test duration and original deadline remain
unchanged. Stock serial Trilinos configuration, build and installation pass;
Xyce build and serial controls remain in progress. No release gate is closed.

### 2026-10-20 — Stock serial controls pass; full-R handoff running (progress074)

The unmodified stock serial Trilinos/Xyce7.10 build, installation and version
check pass in a separate prefix. Both native finite-R/signed-C/BSIM controls
(KLU_REPIVOT=1 and0) match the retained golden sampled voltages, supply current
and rising crossings exactly at printed precision. Their elapsed times are
2.01s and1.32s respectively; these small-control timings do not establish
full-DCO performance or general simulator equivalence.

The handoff records439.98s with the old full-R run remaining at10ps and no
observed time advance. It preserves the partial waveform and PID/argv stop
receipt, waits for that instance to exit, and starts the corrected-C full-R
stock serial point with KLU_REPIVOT=0. Only one large DCO native instance runs;
the separate native ideal-wire reference continues. The physical finite-R and
device model, saved bias,80ns duration,10ps maximum step and original12h deadline
are retained. Solver build and C convention both change, so an eventual speed
change cannot be attributed solely to either. Full-DCO performance, physical
return, frequency/convergence, runtime adoption and all six gates remain open.

### 2026-10-20 — General fast-node selection analyzed (progress075)

All113934 nonterminal R vertices are now analyzed using the exact native-formula
nominal R export, without restricting candidate degree to one/two. Considering
all internal nodes together gives a maximum numerical comparison time7.775ps
and only489 nodes below1fs. Retaining one slow anchor per component reaches the
64-iteration cap without meeting1fs; its inconclusive receipt is retained.

A revised bounded selection retains the worst5% of slow vertices per resistor
component per iteration. It converges in30 iterations to44252 candidate internal
nodes with maximum numerical RC comparison time0.999595fs and final relative
linear residual2.42e-14. A direct audit against actual device terminal and point
boundary files confirms all34413 protected vertices remain outside the selected
set. This selects candidates only: no projection, capacitor/resistor export or
physical state removal occurs. Projected matrix size/fill and oscillator error
remain untested. The active full-R serial and native ideal-wire runs, original
deadline and all release/adoption flags remain unchanged.

### 2026-10-20 — General mesh projection rejected for performance (progress076)

The isolated44252-state projection passes independent rational DC controls,
signed quadratic-energy controls, full native zero-wire-R capacitance comparison
and numerical passivity. All34413 protected vertices remain. DC Schur relative
error is1.69e-13 and the harmonic residual is2.79e-16. These checks do not qualify
oscillator-frequency error.

State count falls148347→104095, but equivalent R branches rise166286→229539
and C nonzeros rise11133595→22280209. Stock KLU's passive-block symbolic estimate
increases factorization work by48.87% and factor entries by29.69%. Nonlinear
Jacobians and MNA rows are excluded, so this is not a measured runtime result.
The larger projection is rejected as the performance fallback and no reduced
native case is launched. The unreduced corrected-C serial and ideal-wire runs
continue under the original deadline; all six release gates remain open.

### 2026-10-20 — Native ideal-wire reference completed (progress077)

The native ideal-wire nominal TT27/coarse0/fine247 run completes80ns with exit0,
59736 samples and98 measured periods after20ns. Its mean is1647.878744MHz.
An independent retained-waveform audit confirms completion and reports10ns
window means increasing1646.308116→1648.895827MHz, a1570.33ppm spread. The last
two windows differ about159ppm. This establishes neither a settled calibration
value nor physical finite-R range coverage. Deterministic period variation here
is not physical-noise jitter qualification.

A25ns native ideal-wire numerical diagnostic is live with maxstep0.5ps,
RELTOL1e-6 and ABSTOL1e-10, to compare its15..25ns interval against the completed
reference. It retains the same physical native capacitors/devices, code and PVT;
the shorter duration is a diagnostic, not a replacement80ns range test. Combined
numerical changes do not fulfill separate independent convergence requirements.
The original deadline is unchanged and no identical native retry is scheduled.
The unreduced corrected-C serial full-R run remains live; all six release gates
and adoption flags remain open/false.

### 2026-10-20 — Threaded stock solver prepared; configuration/grid fixes (progress078–079)

Stock source inspection distinguishes the earlier classic `BASKER` adapter from
the OpenMP `SHYLU_BASKER` adapter, which uses METIS nested dissection. A separate
unmodified-source build is prepared with four compile workers and pinned METIS
5.2.1/GKlib sources. One/eight-thread native waveform controls are queued; thread
pool observation alone will not prove factorization scaling. A literal full-order
ROM encoding is rejected before launch because its two dense input/output arrays
would require about76GiB for the proposed148346-state/34412-port dimensions.

The first threaded configure stops because Tpetra also requires the global
`Trilinos_ENABLE_OpenMP=ON` flag. The revised build reuses successful dependencies
and the failed configure tree, with that flag and `Tpetra_INST_SERIAL=ON`; original
logs and manifests are retained. Existing golden tools and native circuits remain
unchanged. The build and controls retain the original absolute deadline.

The0.5ps tighter ideal-wire diagnostic stops at reset5ns after an accepted
1.464e-22s rounding step and a failed2.928e-22s step. It produces no frequency
result. Independent ramp-driven RC controls reproduce the same tiny step and
show that0.47ps avoids it while matching the closed-form voltage within21nV.
Only the maximum-step field changes in the new25ns diagnostic deck; reset timing,
duration, tolerances and physical capacitors/devices are identical. That corrected
diagnostic is live, but DCO recovery past reset and numerical convergence remain
unproven. No tolerance is relaxed, no engine source is patched, no identical
native retry is made and no check budget is restarted. All release gates remain
open.

`compare_DCO_ideal_wire_numeric_windows.py` is now waiting on the identified
revised25ns run in `DCO_ideal_wire_numeric_window_comparison_001`. After a
successful terminal assessment it will verify retained model/deck identities and
compare15..20ns,20..25ns and15..25ns rising-edge frequencies with the completed
80ns reference. It launches no native case, preserves the original deadline and
reports failed/missing source evidence as inconclusive. Joint changes in step,
tolerances and duration remain a diagnostic; the comparison cannot qualify
separate convergence tests, finite-R calibration or settled physical frequency.

### 2026-10-20 — Revised grid crosses reset; exact-circuit handoff queued (progress080)

The revised0.47ps native ideal-wire diagnostic advances past5.05ns, including
the reset ramp where the0.5ps attempt stopped. An immutable accepted-step prefix
and live process identity are retained in `DCO_numeric_reset_grid_recovery_001`.
This proves recovery past that scheduling failure, not full completion or
frequency/numerical convergence.

`run_DCO_stock_threaded_point.py` is queued behind the one/eight-thread native
controls. It requires bounded observed throughput, a verified thread-count range
and exact physical-deck byte identity after changing only solver options. It
preserves viable prior progress; otherwise a pinned deck and process stop receipt
must precede starting one full-R ShyLU instance. The same corrected C convention,
all resistor/device cards, saved bias, reset,80ns duration,10ps step and original
deadline remain. No active solver has changed yet and no release gate is closed.

`compare_DCO_startup_prefix.py` also waits on the same revised numerical trace,
retaining an immutable prefix after six post-reset rising edges. It compares
matching cycle indices with the completed80ns reference and explicitly labels
the result as startup-only and incomplete. This preserves early diagnostic data
if the tighter run reaches the original deadline before25ns. It launches no
native instance and cannot replace the full-window comparison, settled
calibration, separate convergence checks or any release gate.

`audit_DCO_startup_comparison.py` independently checks the completed baseline's
artifact hashes and terminal duration, then the retained comparison hashes,
finite samples, strictly increasing times, rising crossings and reported
frequency differences. Before the comparison exists, it exits 2 and records no
audit pass. Once available, run it under the pinned container with `--output`
pointing to a new audit directory within the original campaign deadline. Its
result remains a startup diagnostic and cannot qualify settled calibration.

### 2026-10-20 — Stock threaded build complete; controls remain conditional (progress081)

The unmodified OpenMP/METIS/ShyLU Xyce build completed and its binary/input
hashes were verified. The original 13-unknown control passed with one thread
but exited nonzero during eight-thread initialization; its failure receipt and
logs are retained. The larger connected passive-RC/BSIM control completed with
KLU and one-thread ShyLU, while passive-wait eight-thread ShyLU reached its
120-second local limit. That result is inconclusive and its cause is unproven.

`check_stock_threaded_active_wait_control.py` changes OpenMP waiting to ACTIVE,
reuses those completed references, and retains the same circuit/tolerances.
It has a 300-second local cap within the unchanged original campaign deadline.
`run_DCO_stock_threaded_point_v2.py` waits for passing waveform/thread-count
evidence before applying the existing byte-identity and prior-throughput guards.
No threaded full DCO has started at this snapshot; all release gates remain open.

### 2026-10-20 — Active-wait controls pass; full-R handoff starts (progress082)

The eight-thread ACTIVE control completed in120.40s, with eight process threads
observed. Against the completed KLU reference, maximum sampled voltage error was
18.27nV, supply-current error15.67pA, and rising-crossing error7.61e-21s. These
controls do not establish general solver equivalence or full-DCO speedup; the
earlier tiny-control failure and PASSIVE timeout remain retained.

The guarded handoff observed no serial transient advance over121.09s at10.15625ps,
verified physical-deck byte identity after changing only the solver line, saved
the stop receipt, and started the stock threaded full-R point in
`DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_002`. It retains all R/MOS cards,
corrected physical C, saved bias,80ns duration,10ps maximum step and reset source.
OpenMP uses eight threads with ACTIVE waiting. The original deadline remains
3179534.428739453 BOOTTIME; model adoption and every release qualification remain
false. Full-R performance and frequency evidence are pending.

### 2026-10-20 — First full-R threaded positive step retained (progress083)

The full-R threaded point accepted its first10ps step. Independent comparison
with the retained stopped serial trace checks exact circuit identity after the
solver-line replacement, matching sample times, finite values and monotonicity.
The two initial samples differ by at most1.943e-11V and9.035e-13A.
`DCO_stock_threaded_first_step_comparison_001` retains immutable copies of both
prefixes and their hashes. This is an initial-step diagnostic; it establishes
neither sustained speedup, full transient completion nor frequency/calibration
qualification. All six release gates remain open and the deadline is unchanged.

### 2026-10-20 — Startup numerical comparison independently verified (progress084)

The revised ideal-wire run reached six post-reset rising edges. The retained
matching-cycle comparison reports a frequency change of-5.07510ppm between the
10ps/REL1e-5/ABS1e-9 baseline and0.47ps/REL1e-6/ABS1e-10 settings. The independent
audit verifies the original terminal baseline hashes, retained prefix hashes,
finite monotonic samples, crossing interpolation and reported metrics.
Evidence is in `DCO_ideal_wire_startup_prefix_checks_001/assessment.json`.

This compares startup only and changes multiple numerical controls jointly.
The revised25ns run remains incomplete; settled calibration, independent
one-at-a-time convergence, finite-R frequency coverage and every release gate
remain open. The original campaign deadline is unchanged.

### 2026-10-20 — Original 12-hour campaign ended inconclusive (progress085)

Both remaining native runs and their owners stopped at the original campaign
deadline; the full-window comparison helper also reports timeout/inconclusive.
The threaded full-R point retained six samples through10.33314ps, short of80ns.
The tighter ideal-wire point retained57,975 samples through8.70301ns, short of25ns.
Terminal status, immutable waveform/log hashes, process-stop checks and the
unchanged requirements/plan hashes are retained in
`campaign_deadline_001/assessment.json`. No budget was reset or identical retry
scheduled. The independently audited startup comparison remains diagnostic only.

All six release gates remain open, with zero qualified physical whole-PLL cases.
This campaign provides no settled finite-R calibration or release qualification.
The current full-R solver throughput remains a blocker to the required range
and model qualification; extending this same run is not a closure fix.

Post-campaign feasibility work does not restart either native point. The stock
nonlinear adapter audit in `stock_newton_factor_reuse_audit_001` finds that the
available Newton/NOX linear-solve path requests fresh numerical factors, while
the modified-Newton implementation is disabled behind a prerelease build flag.
Enabling that strategy alone is therefore not a demonstrated factor-reuse fix.

`passive_SuperLU_feasibility_001` tests the retained148,346-state passive RC
matrices with explicit diagnostic shunts and without transistor/MNA equations.
The offline numeric factorization reached its180-second guard without a result
and was terminated. Its explicit timeout receipt makes this inconclusive, not
a demonstrated numerical failure or a full-DCO performance comparison. No
backend build, circuit change, model adoption or release qualification follows.

The saved-bias investigation in `DCO_saved_bias_wire_KCL_audit_001` checks all
113,934 unprotected wire vertices and finds a maximum wire-only DC residual of
6.982pA; it does not evaluate MOS or protected-terminal residuals. The result
does not identify a large passive-wire startup-bias error.

`static_BSIM_UIC_startup_controls_003` completes15 native cases across three
static input biases. At the intermediate bias, the default six-significant-digit
SAVE export introduces2.8763uV output error; explicit17-digit N() export removes
that difference to roundoff. Disabling voltage limiting provides no improvement
in these controls. Initial source-current output at t=0 is excluded from the
separate positive-time current comparison. These controls do not establish the
cause of the full-DCO startup problem or a speed fix.

`xyce_precise_bias.py` generates explicit N() print requests and converts a
completed single-point STD DC table into round-trippable IC voltages, including
device-internal solution variables. The retained three DC points independently
validate all exported values in `precise_bias_export_validation_001`. V(*) omits
the six internal BSIM nodes in this control, and explicit V(internal-name) is
unsupported; both failed export-schema trials and their logs are retained.
No full-DCO run was restarted and no new model or solver setting was adopted.

### 2026-10-20 — Wire-network preconditioner feasibility

The generic smoothed-aggregation attempt in `passive_AMG_feasibility_001`
reached its180-second guard during setup. A two-level constant-per-wire basis
sets up in2.052s but its Gauss-Seidel smoother does not converge in300iterations
(scaled true residual7.237e-6). Neither result establishes a usable solver.

`wire_block_preconditioner_feasibility_001` instead factors the sparse resistor
network plus the diagonal capacitance/shunts, and adds a2686-component coarse
correction. The full148,346-state passive matrix is unchanged. Setup takes
2.714s, including0.140s block factorization; CG takes0.396s and10iterations.
Recomputed scaled/original relative residuals are7.076e-13/1.253e-14, with
known-solution relative error5.029e-9 and peak RSS905,560KiB. This workload
contains diagnostic shunts and omits transistor and voltage-source equations;
it does not demonstrate native DCO throughput or qualify a physical model.
`solver_feasibility_checks_002` independently verifies pinned inputs and the
reported convergence criteria. The first audit's incorrect log-marker check is
retained with an explicit failure receipt.

The small native matrix-export control completes and independently validates
its13-state MatrixMarket system, serial map and variable-name schema. A separate
five-minute capture-only diagnostic is prepared to export the original full-DCO
first Jacobian/RHS and stop after export, with circuit identity preserved except
for `OUTPUT_BASE_LS=1`. It does not restart the closed qualification campaign.
No solver, circuit or physical-model change is adopted by these diagnostics.

The combined export diagnostic ends inconclusive at its guard: native names
export completes with174,551 mapped variables, but the remaining matrix phase
has insufficient setup time and is stopped. `DCO_native_linear_system_capture_001`
retains the completed names and both stage exits. The staged successor reuses
that exact names export and verifies circuit/binary identity; it allows a single
ten-minute matrix-export stage without repeating the names pass. This is an
export scheduling correction, not an extension of the original12-hour campaign.

### 2026-10-20 — Native Jacobian solver feasibility passes

`DCO_native_linear_system_capture_002` reuses the completed names export and
captures the first actual native Jacobian/RHS, then stops the engine before
awaiting its factorization. The system has174,551variables,11,209,902numeric
entries and339voltage-source branch variables. All MatrixMarket files have
complete trailing newlines; the serial block map agrees with the names' GIDs.
The circuit differs from the retained serial point only by the export option.
No full transient was attempted or qualified by this capture.

`native_capacitance_preconditioner_feasibility_001` retains the native Jacobian
and RHS unchanged, removing wire-capacitance off-diagonal terms only from its
approximate Jacobian used as a preconditioner. A19,331-pair passive-only check
identifies the native capacitance multiplier as1e11/s, with2.22e-16maximum
relative coefficient error. The approximate matrix has730,204entries and
factorizes in0.657s. SciPy GMRES converges in12iterations for both a known
solution and the actual Newton RHS, taking0.860/0.909s respectively. The native
RHS scaled true relative residual is2.877e-13. This is one captured Newton
system, not evidence for successive nonlinear steps or transient completion.

`native_solver_probe_checks_001` exercises the same equations using the existing
serial Xyce SDK's Epetra/Amesos-KLU/AztecOO interfaces. Factorization takes0.238s;
the native RHS solve takes0.408s and12iterations. Independently recomputed
residuals on the original native equations are at most8.596e-16A for current
equations and0V for voltage constraints. The known-solution relative error is
2.984e-10. Solutions, input binaries, source/build/library hashes and logs are
retained. The original stock source and simulator binaries are unchanged.

An isolated experimental adapter build is prepared in
`wire_preconditioned_Xyce_001`. Its opt-in `OPENPLL_WIRE_PC` path keeps the Newton
matrix/RHS intact, factors a sparse approximate Jacobian, checks the true scaled
residual, and reuses only the approximate matrix's symbolic factorization.
The adapter retains the resistor/device coupling graph even where a particular
Newton step has zero numeric entries. The existing stock builds are preserved.
The experiment still requires native controls, variable-map identity, numerical
holdouts and completed transient evidence before any runtime/model eligibility.
All six release gates remain open; this work does not extend campaign085.

`native_wire_preconditioner_metadata_001` exports10,809,702wire-C off-diagonal
entries in native GID order. Its explicit preservation mask retains330,004
resistor/device pair slots, including graph slots that can become nonzero in
later Newton iterations. The1024pure-wire coefficient samples independently
match the captured1e11/s multiplier. The candidate's own variable-name export
must still match before this metadata can be used in a native DCO diagnostic.

### 2026-10-20 — Complete adapter tested on captured native equations

The first standalone adapter compile identifies a missing explicit
`Epetra_Comm.h` include. Its compiler log and failed probe-runner receipt are
retained; no solver executable ran in that failed probe. The initial isolated
simulator build is stopped early with an explicit interruption receipt.
`OpenPLL_WirePreconditioner_v2.h` adds the missing include without changing the
numerical method.

`native_adapter_probe_checks_002` exercises the complete adapter, including
metadata loading, coupling-mask construction, scaling, repeated numerical
factorization and symbolic reuse, on the actual174,551-state native equations.
Both captured-RHS and known-solution cases pass. Fingerprints and byte comparisons
confirm that the original Jacobian and RHS are unchanged. The native RHS solve
reports9.526e-14independently recomputed scaled relative residual and
8.596e-16A maximum current-equation residual, with zero voltage-constraint
residual. Adapter work takes0.880/0.871s for the two successive calls.
This still does not test a nonlinear trajectory.

`wire_preconditioned_Xyce_002` resumes the isolated build with the validated
header fix and cached objects. It inherits the original build deadline
conservatively rather than resetting that budget. Original adapter/header
backups, the include-only patch, stock binary/source pins and interrupted-build
receipts remain available. No installed stock source or binary is modified.

`wire_preconditioned_native_controls_002` waits on the identified builder, then
runs stock-correlated signed-C/BSIM/mesh controls with separate timestep and
tolerance holdouts. The fixture includes capacitive couplings along a resistor,
across transistor terminals and between distant mesh vertices to exercise the
preservation mask. Only after those controls pass may
`DCO_wire_preconditioner_variable_map_001` export the candidate DCO's native
variable names and compare every GID against the retained metadata reference.
These checks do not schedule a full DCO transient or qualify a release.

### 2026-10-20 — Guarded changed-solver DCO point queued

`DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_001` waits on the identified
variable-map checker. It starts no native engine unless both the adapter's
nonlinear native controls and full-DCO GID comparison pass. Its new12-hour
check budget includes all dependency waiting, preparation and native execution;
it does not extend or reset the closed campaign085. This is a changed-solver
experiment, with no automatic identical retry.

The prepared point uses the exact retained serial circuit, saved bias, TT27,
1.8V, c0/f247,80ns/20ns window and10ps maximum step. The isolated binary and
opt-in preconditioner metadata are the changed inputs. Exclusive native admission
and a48GiB address-space guard apply. The first accepted0/10ps samples must
match the retained stock prefix within1uV and100pA; a failed comparison stops
the experiment. A complete transient can establish diagnostic oscillation only.
Independent calibration convergence, parent loading, physical model qualification
and every release gate remain open.

### 2026-10-20 — Isolated build and nonlinear native controls pass

`wire_preconditioned_Xyce_002` completes its cached build, installation and
version check. The isolated binary SHA256 is
`e4a8edb15ae5261298039566e4076e7b8b30348f254000fb22c65f8006e0b200`.
The original build deadline and stock source/binary identities are preserved.

The first added-coupling fixture under default trapezoidal integration is stiff:
stock completes8ns with1,006,816samples in113.33s, while the adapter reaches
4.04152ns before its120s guard. All816,462reported adapter linear solves pass
their residual checks, but the transient is incomplete. The immutable
`wire_preconditioned_native_controls_002/timeout_assessment.json` retains both
traces and the terminal timeout evidence. This is not a full-transient pass or
a physical-model failure.

`wire_preconditioned_native_controls_004` keeps default trapezoidal integration
on the unchanged original signed-C/BSIM/mesh fixture, and uses Gear on the stiff
added-coupling fixture. Separate maximum-step and tolerance holdouts also pass.
The original default-method stock/adapter traces and names exports are reused
from completed cases, without repeating their native runs. Their earlier audit
incorrectly required exactly zero DC capacitance multiplier; native source
`N_TIA_NoTimeIntegration.C` explicitly uses1e-20. The failed expectation and its
source evidence remain retained in the003audit recovery receipt.

The completed controls cover64,956successful adapter linear solves and five
waveform comparisons, including a disabled-adapter regression. Default-method
output differences reach17.95nV; the largest sampled voltage difference across
the Gear holdouts is3.872uV. All successful linear solves meet1e-12scaled true
relative residual. `wire_preconditioned_native_controls_checks_002` independently
checks traces, input hashes, native GIDs, preservation-mask entries, recovered
case provenance and the separate numerical holdouts. Its first host-environment
attempt is retained with a receipt; the passing audit runs in the pinned SIF.
These controls do not establish DCO frequency convergence across integrators.

The initial guarded DCO point starts no engine after the failed control gate.
The002successor inherits that same12-hour deadline, including all dependency
waiting, and awaits `DCO_wire_preconditioner_variable_map_002`. Its full-DCO
circuit and default integration settings remain unchanged. It is still an
experimental diagnostic; all six release gates remain open.

The full-DCO candidate variable-map check completes with all174,551GIDs
matching the retained metadata reference. The guarded002native point then
starts under its inherited12-hour deadline (approximately2026-10-21T10:55UTC).
The physical circuit, bias, default integration method, timestep and tolerances
are unchanged. First-step comparison and full-transient completion remain
pending; no source-model, calibration or release qualification follows merely
from launching this run.

### 2026-10-20 — Full-R startup progresses with unchanged integration

The experimental point passes its first0/10ps stock comparison: maximum
reported differences are5.1393e-11V and1.0562e-12A. After initial short steps,
accepted steps recover to the configured10ps maximum. The retained independent
snapshot in `DCO_wire_preconditioned_startup_checks_002` contains152samples
through1.11216ns and321successful linear solves. Decimal arithmetic independently
checks first-step voltage/current agreement, finite monotonic samples and step
bounds; live native identity and the inherited deadline are reverified.
The first audit's exact-decimal timestamp check rejected ordinary floating-point
output rounding and is retained with an explicit receipt; no native run repeats.

The point remains under reset before5ns and outside its20..80nsmeasurement
window. This startup evidence does not establish oscillation, settled frequency,
full-transient completion or a qualified speedup. No integration-method change
or extra loader option is applied. Stock loader source already enables separate
linear loading and caches linear matrix/vector contributions during transient.
All release gates remain open; the original changed-solver check deadline holds.

### 2026-10-20 — Missing nominal PVT propagation points run independently

The existing891-fixture combinational plans have identical fixture inventories
at TT27, SS125 and FS125. Their direct source/artifact hashes revalidate in the
pinned SIF, including1664template input pins. The observations cover40cell types;
six sequential types remain outside this dataset. Completed native runs are
reused rather than repeated.

`compact_nominal_15PVT_completion_001` prepares only the12missing corner/temperature
combinations, preserving each fixture and changing only the library corner and
device temperature. Supply remains1.8V. It uses unmodified golden Xyce and the
retained KLU/single-thread policy. The first FF-40, SF-40 and SF125native cases
are launched alongside the existing DCO point through the same admission lock;
combined native count is at most four. Each cell native has a6GiB address-space
guard and admission requires8GiB available memory. Three case workers share
one12-hour campaign deadline, including preparation, queues, native runs and
assessment (approximately2026-10-21T11:36UTC). There is no identical retry.

The assessor retains the existing propagation/slew measurement semantics,
including ambiguous threshold crossings and zero-load cases. This expands raw
PVT observations only. It does not qualify interpolation, numerical-error bounds,
sequential setup/hold/recovery/removal, effective loads, noise or min/max routed
RC, and it produces no qualified timing library. The DCO point retains its
separate inherited10:55UTC deadline and is not stopped or modified by this work.
All six release gates remain open.

### 2026-10-21 — Completed stiff-fixture integration comparison retained

`completed_stiff_integration_comparison_001` compares existing unmodified-stock
traces for the identical added-coupling fixture, changing only integration method
and the explicitly identified timestep/tolerance holdouts. No native run repeats.
Trapezoidal integration uses1,006,816samples; baseline Gear uses8,756. Baseline
Gear output threshold times differ by at most1.674fs. Its tight-tolerance holdout
has maximum threshold-time difference0.0441fs. Sampled waveform differences and
time-weighted6.2..8ns supply-current means remain in the receipt; the latter
difference is approximately20.7ppm for baseline Gear and6.5ppm for the tighter
holdout. Instantaneous current differences are retained rather than interpreted
as physical noise.

This is a small-fixture observation, not DCO frequency convergence or a qualified
numerical domain. Gear is not selected for the running DCO point. Source review
also confirms the existing default NEWLTE=1 uses a global solution-magnitude
reference; the current absolute tolerance is not by itself proof that quiet-node
error weighting is the runtime bottleneck. No tolerance/mask option is changed.

### 2026-10-21 — Missing sequential propagation points share the timing deadline

The retained FS125sequential plan covers108clock-to-Q/asynchronous-assertion
fixtures across all six used FF types, the same three input-ramp and load levels,
and repeated capture opportunities. Its1596plan input hashes and audited terminal
108/108receipt revalidate in the pinned SIF. That native dataset is reused.

`compact_sequential_15PVT_completion_001` prepares the14missing nominal PVT
points by changing only the library corner and device temperature. It inherits
the combinational campaign's original11:36UTC deadline, including all new
preparation, waiting, native work and assessment; no new12-hour budget is started.
Two sequential case workers wait through the same native-admission lock. Existing
DCO/combinational engines continue, and the combined native count stays at most
four. Each new sequential native uses the same6GiB guard and golden KLU engine.

The sequential assessor retains the original event/state/threshold formulas,
uses compact double arrays, and excludes mutable status from frozen artifact
hashes. It does not qualify setup/hold/recovery/removal, pulse-width constraints,
metastability/MTBF, interpolation, physical load/noise domains or a timing library.
This work fills mandatory propagation-data gaps; all release gates remain open.

### 2026-10-21 — Live DCO edge/progress observations retained

`observe_DCO_native_progress.py` watches only the explicitly identified existing
native PID, verifies its argument identity, and incrementally parses complete
waveform rows. It neither changes inputs nor starts/retries a native process.
`DCO_wire_preconditioned_runtime_observer_001` retains30-second observations,
post-reset0.9Vedge counts, voltage extrema and provisional recent-period
frequency estimates. Runtime extrapolation is withheld until at least three
complete post-reset periods and five minutes of relevant rate observations.
Even then it remains provisional and cannot qualify settled frequency or infer
the native case verdict.

The DCO has already made a full falling transition after reset, reaching roughly
1mV; full-swing repetition and the20..80nsmeasurement window remain pending.
No integration method, numerical tolerance or physical model is changed. Source
review also confirms the stock transient loader skips repeated constant-linear
capacitor state updates after its cached linear matrices are available. No new
capacitor-state optimization is applied.

### 2026-10-21 — Completed capture samples identify refinement intervals

`analyze_completed_capture_apertures.py` consumes the already reviewed,
hash-matched FS125 terminal receipt and plan without another native run.
`completed_capture_aperture_analysis_001` retains all198 observations, signed
output-edge offsets from the test clock, and one sampled outcome-transition
bracket for each of18cell/input combinations. The brackets are50..100ps wide;
three unsimulated interior offsets per bracket identify54new refinement points.
The CSV retains all sampled outcomes and rising/falling output edges.

These are measured sample transitions at200ps full input/clock ramps and5fF
external load, not conservative setup/hold/recovery/removal limits. Interior
monotonicity, delay-degradation acceptance, other ramp/load/PVT points and
numerical convergence remain unqualified. No native job starts, no campaign
deadline changes, and no timing library or physical interface bound is adopted.

### 2026-10-21 — FS125 capture refinement batch prepared

`prepare_capture_aperture_refinement.py` prepares54previously unsimulated
interior offsets and36separated batch controls in
`capture_aperture_refinement_fs125_001`. All historical input hashes revalidate
in the pinned SIF; original/work/OpenPLL paths are explicitly mapped to their
canonical host equivalents with exact byte checks. The existing six cell
models, FS125/1.8V condition,200ps full ramps,5fF load,28ns horizon and2ps
maximum step are preserved. Only the selected changing-input offsets differ
for the54interior cases.

All90generated source sets independently parse back to their plan values;
the existing ideal oracle/observer accepts90cases including36controls. This
is synthetic stimulus/observer validation, not a native or physical timing
pass. Native execution is not started. The prepared plan inherits the existing
11:36UTC timing-campaign deadline rather than starting a new12-hour budget.
No setup/hold/recovery/removal limit or metastability bound is adopted.

### 2026-10-21 — Guarded capture refinement worker queued

`run_capture_aperture_refinement.py` now owns the90-case batch under the same
11:36UTC timing deadline. Its initial frozen-input validation completes in the
pinned SIF. Live admission observes the existing four native engines and the
two queued sequential workers, so no fifth native starts. Under the common
lock, the worker also waits whenever a live sequential worker is queued; it
checks PID argument identity rather than trusting stale status alone.

The worker preserves golden KLU, one BLAS/OpenMP thread, a6GiB address-space
guard,8GiB available-memory admission, deadline-inclusive waiting/preparation/
assessment, and no identical retry. Assessment reuses the existing capture
observer, retains ambiguous outcomes, checks all source crossings/pretest
states and separated controls, and requires terminal waveform coverage.
No constraint, numerical-domain or physical timing qualification follows from
these observations alone. The queued worker does not alter existing jobs.

### 2026-10-21 — Method-only Gear fallback prepared, not activated

`prepare_DCO_gear_fallback.py` revalidates the running point's frozen inputs
and retains the completed native control/audit and cross-method fixture
comparison receipts. `DCO_gear_method_fallback_prepared_001` differs from the
running deck only by adding METHOD=GEAR to the existing TIMEINT line. A separate
line comparison confirms this single change. All physical equations, initial
bias,80ns horizon,20ns measurement start,10ps maximum step and tolerances remain
the same. The plan inherits the original10:55UTC DCO deadline; no budget resets.

The running TRAP point is untouched. No Gear DCO process starts and no second
large DCO is allowed. Activation requires a documented runtime handoff decision.
The existing small-fixture Gear controls do not qualify DCO method/frequency
convergence or physical performance; all release gates remain open.

### 2026-10-21 — Retaining capacitance on existing sparse pairs gives no iteration gain

`benchmark_retained_C_preconditioner.py` compares two preconditioners on the
unchanged captured native Jacobian/RHS, using the metadata keep mask to retain
wire-C offdiagonals on existing resistor/device pairs in the second version.
The bounded offline comparison uses one thread and an8GiB address-space guard;
it starts no native engine and changes no model or live adapter.

Both SciPy/SuperLU variants converge in12GMRES iterations with true scaled
residuals2.872e-13 and2.837e-13. Their graphs both contain730204nonzeros; observed
factor/solve times are0.807/0.717s and0.793/0.703s respectively. One captured
linear system does not establish native runtime or nonlinear-sequence behavior,
and this small single-sample timing difference is not a demonstrated speedup.
`retained_C_preconditioner_comparison_001/decision.json` records that no native
adapter change is selected on this evidence. The running DCO remains unchanged.

### 2026-10-21 — Gear fallback runner refuses a live-prior handoff

`run_DCO_gear_fallback.py` is prepared but not launched as a native run. It
requires an explicit handoff receipt tied to the terminal prior assessment,
prior owner/native identities and original deadline. Both prior processes must
be gone before it creates a run directory. A documented guard check in
`DCO_gear_fallback_runner_guard_check_001` confirms the currently live TRAP
native/owner cause refusal before even opening the proposed handoff file.
Check-only observation confirms no native starts and no Gear case directory
exists. This tests refusal, not the unexecuted Gear transient/assessment path.

A later selected handoff revalidates control audits, GID mapping, binary,
metadata and frozen circuit inputs. Shared admission permits at most four
engines, refuses another large DCO and requires28GiB available memory; the
native48GiB address-space guard and remaining-budget CPU/wall limits apply.
The original10:55UTC deadline includes all waiting and assessment. Diagnostic
frequency from a completed point remains ineligible for release until its
numerical domain, loading and physical interfaces are independently qualified.

### 2026-10-21 — Prepared fallback can preserve admission through a handoff

`run_DCO_gear_fallback_v2.py` forks the unlaunched v1 runner to accept an
optional inherited admission-lock descriptor. This addresses the race where
queued cell workers could take the vacated large-DCO slot between stopping the
old method and admitting the replacement. A selecting controller must hold the
common lock, complete the documented stop/terminal-receipt handoff, pass its
descriptor with pass_fds, and close the parent's descriptor immediately after
spawning the replacement. The child owns the inherited descriptor until its
admission context exits, then closes it so cell admission resumes.

`DCO_gear_fallback_inherited_lock_checks_001` verifies with a temporary lock and
a real child process that inheritance does not deadlock, contenders stay
blocked after the parent closes its copy, the lock becomes available when the
child releases it, and a descriptor for another inode is rejected. Check-only
mode still refuses the currently live prior DCO. No native process is started,
no real admission lock is held during these controls, and no handoff is selected.
The existing four native engines and original deadlines remain unchanged.

### 2026-10-21 — First missing combinational PVT completes; sequential admission advances

The SF125native batch exits0after4980.66s and its terminal assessment passes
891/891propagation fixtures. Strict output-slew ordering passes889/891;
cases837and873retain their raw ambiguous threshold events. No cases are
excluded and no constraint/numerical-domain/timing-library qualification is
inferred. This increases completed raw combinational PVT observations from
three to four of the required15. The campaign retains its original11:36UTC
deadline and starts the next distinct prepared case through shared admission.

The existing queued FF-40sequential worker obtains the freed native slot
while SF125assessment runs. Its native PID185609is verified live with the
expected golden-KLU deck argument. The other DCO/two combinational engines
continue, so actual native count remains four. No live case is restarted.

### 2026-10-21 — SF125 adds measured extrema; SF-40 also completes

`compare_SF125_compact_samples.py` revalidates all raw artifacts and frozen
inputs for the retained TT27/SS125/FS125 points and the new SF125 point. It
compares3564matched propagation-delay samples, preserving both repeated edges
and all891fixtures. SF125has1357samples below the previous sampled minimum
and1332above the previous sampled maximum;1272and1298respectively extend
those sample ranges by more than1ps. The1ps threshold is reporting only, not
a numerical-error bound or acceptance criterion. Largest extensions are
152.656ps below and134.733ps above; the full records retain cell, arc, ramp,
load and repeated-event identity. These are relative to three earlier samples,
not Liberty-bound or specification violations. No timing envelope is qualified.

SF-40also exits0after5102.65s and passes891/891propagation fixtures, with
889/891strict slew observations. Completed raw combinational coverage reaches
five of15PVT points. Further distinct prepared FF27/FF125native jobs are verified
live with golden-KLU arguments; the FF-40sequential native continues and SF-40
sequential remains queued. Four native jobs remain active. The DCO has two
rising and two falling startup transitions; its first rising-edge interval is
1.138531ns, differing from the first falling-edge interval1.163618ns. This
startup behavior does not establish settled or numerically converged frequency.

FF-40terminal assessment subsequently passes891/891propagation fixtures and
890/891strict slew observations. All three first-wave points are now recorded
by the campaign, increasing completed raw combinational coverage to six of15.
All ambiguous slew events remain available; qualified timing views remain zero.

### 2026-10-21 — Selected repetition-sensitive numerical controls queued

Completed SF-40case839(xor2_2,20ps full ramp,109.99fF external load) has
17.3723psdifference between its two input-rise delay observations, exceeding
the previously reported14.6694psmaximum. SF125case839differs by15.9780ps.
These are repeated-opportunity observations, not a numerical-error estimate.
Cases874/875and the slow-ramp zero-load a21oi_2case87are also selected for
focused investigation; all other fixtures remain mandatory for full coverage.

`run_selected_compact_numerical_holdouts.py` prepares a four-fixture subset
baseline and independent1ps timestep, REL1e-6, ABS1e-11 and50ns-duration
controls in `selected_compact_numerical_holdouts_sf_m40_001`. A line comparison
confirms each control changes exactly one deck option relative to the subset
baseline. The subset baseline is needed because removing independent fixtures
can change global adaptive-solver context. The50nsrun preserves the pulse train
and measures a third opportunity; no fixed300nsrequirement is introduced.

The controller runs at most one selected case at a time through the common
four-engine admission lock and inherits the original11:36UTC deadline, including
preparation/waiting/native work/assessment. Its first worker is verified live
and queued behind four existing native engines. Original campaign workers and
executed sources remain unchanged; separate assessor/worker forks support the
variable horizon/repetition count. No identical failed check is retried.

`compact_holdout_observer_checks_001` independently validates the forked assessor
with an ideal delayed-pulse oracle: both two- and three-opportunity waveforms
recover50psdelay for all four fixtures, while a wrong-repetition negative
control fails all four. This is synthetic observer validation, not native or
physical qualification. Selected controls cannot by themselves qualify the
full slew/load/PVT domain or a conservative STA library.

### 2026-10-21 — DCO runtime handoff retained; foreground recovery reserves capacity

The TRAP point shows repeated full-swing startup activity but its best observed
30-second throughput over roughly15minutes is about0.055ns/min, versus about
0.124ns/min average needed to complete80ns before the existing10:55UTC deadline.
This is a startup-affected runtime decision, not a definitive finish ETA or
settled-frequency claim. `DCO_TRAP_to_GEAR_runtime_handoff_001` retains the
observation history, source identities, decision and stop/terminal receipts.
The identified native receives SIGTERM under the shared admission lock. Its
parent finishes normally and retains2013samples through7.688392ns,4059linear
solves with zero rejected solves, and the passing first-step comparison. The
signal exit is an explicit controlled interruption, not physical failure.
The80nscheck remains incomplete and its model remains unqualified.

The first replacement wrapper exits before any Gear native launch: its parent
container foreground exits too early, squashfuse tears down, and dependency
validation raises transport-endpoint Errno107. Gear001retains the full failure
receipt and has neither launch.json nor native.log. No Gear transient is retried.
A queued distinct cell case takes the released slot before recovery.

`run_DCO_gear_foreground_recovery.py` and the separate v3Gear runner correct the
container lifetime. The foreground controller reserves the next admission slot
under the common lock while four existing cell engines continue; it does not
preempt them or admit a fifth. It transfers the lock to Gear002when a slot frees
and waits for its child through termination, preserving the SIF mount. The
original10:55UTC DCO deadline includes this additional waiting and all assessment;
no budget restarts. At registration the recovery controller PID186879is verified
live and reserving capacity; no Gear native has yet launched. The physical
circuit, initial bias, duration, maximum step and tolerances remain unchanged.

### 2026-10-21 — Read-only monitor waits for the reserved Gear point

`watch_pending_Gear_DCO.py` runs from the host and waits for Gear002launch.json
and a matching live PID/status/deck identity before attaching the existing
incremental DCO observer. Its host-side lifetime is independent of SIF mount
lifetime; it never launches, stops or modifies a native simulator. The monitor
shares the original10:55UTC deadline and waits while foreground recovery
reserves the next slot.

After attachment it retains the first two complete Gear rows and compares them
with the retained stock first-step prefix only when time grids match. It
records voltage/current differences and the existing1uV/100pA comparison limits
without changing the native verdict. Different integration/time grids are
explicitly retained rather than forced into an equivalence claim. This is not
frequency or numerical-domain qualification. The old TRAP observer has finished
with source_native_live=false at7.688392ns; its history remains preserved.

### 2026-10-21 — Selected-control comparison waits for terminal evidence

`collect_selected_compact_holdouts.py` is a host-side read-only collector for
the five queued SF-40controls. It checks source runner identity while waiting,
then requires terminal case receipts and matching plan/receipt hashes. It
revalidates raw native artifacts before comparing both repeated edge delays
against the four-fixture subset baseline and the original891-fixture batch.
Duration results additionally retain third-versus-second opportunity drift.
Missing measurements and strict-slew counts remain explicit.

The collector produces separate signed/magnitude differences for subset
context, timestep, relative tolerance, absolute tolerance, duration and repeated
opportunities. It does not invent a numerical acceptance limit or infer a
continuous timing bound. Producer input checks are consumed as recorded; the
collector does not claim an independent full PDK/source re-audit. At
registration it waits on live source controller186172and starts no native
engine. All existing deadlines and native admission limits remain unchanged.

### 2026-10-21 — Controlled TRAP trace independently parsed and retained

`audit_retained_TRAP_handoff.py` validates the handoff-bound terminal assessment,
raw waveform/log hashes, source process termination,2013monotonic finite
accepted samples and4059sequential logged linear solves. Every reported scaled
true residual is finite and<=1e-12with status0. The audit does not recompute
Jacobian residuals independently for every Newton step; it explicitly retains
that limit. Two rising and two falling post-reset crossings are recovered.

`retained_TRAP_handoff_audit_001` preserves the two startup intervals and verifies
the prepared Gear deck changes only the integration-method option. The trace
ends before20nsand has no terminal marker, as expected after the documented
SIGTERM handoff. It remains a controlled partial startup reference, not settled
frequency, numerical-domain qualification, a completed80nscheck, or evidence
of physical oscillation failure. No native process is started by this audit.

### 2026-10-21 — FF-40 sequential passes; reserved Gear native actually launches

The FF-40sequential native exits0after3442.68s. Its terminal assessment passes
108/108clock-to-Q/asynchronous-assertion fixtures, increasing completed raw
sequential propagation coverage from one to two of15PVT points. This does not
qualify setup/hold/recovery/removal or metastability bounds.

The foreground recovery transfers the reserved admission lock to Gear v3runner
PID190337. Native PID190338is verified live with the expected isolated binary
and Gear002deck argument while three existing combinational engines continue.
The actual native count stays four. The foreground controller remains alive,
preserving the SIF mount, and the read-only observer PID190349attaches to the
identified Gear native. Initial parsing/model loading is active; no accepted
Gear waveform step or performance verdict is inferred at registration.

The DCO deadline is still the original10:55UTC (BOOTTIME3226730.312649184),
including all prior work, handoff, environment failure and reservation wait.
No Gear transient is retried, and no physical equation, initial bias,80ns
horizon,20ns measurement start,10ps maximum step or tolerance is changed.

### 2026-10-21 — Gear first accepted step matches the retained stock reference

Gear002accepts its first transient rows after native topology/matrix setup.
The read-only first-step comparison has an identical0/10psgrid, maximum voltage
difference5.139288994e-11V and current difference1.056152561e-12A, within the
existing1uV/100pA limits. The retained reference and Gear prefixes and comparison
receipt are in `pending_Gear_DCO_monitor_001`. No verdict or input is changed by
the monitor. Reported linear solves pass their<=1e-12scaled residual checks.

The initial adaptive steps remain short, so no steady throughput improvement,
settled frequency or numerical-domain qualification is inferred. Foreground
recovery and native/observer identities remain live; three combinational native
engines continue alongside Gear, preserving the four-process limit.

### 2026-10-21 — FF27 and selected subset baseline complete; Gear clears reset ramp

FF27combinational native exits0after4888.63s and its terminal assessment passes
891/891propagation fixtures with890/891strict slew observations. All ambiguous
threshold data remain retained. Raw combinational coverage reaches seven of15
PVT points; no qualified timing view is produced.

The selected four-fixture SF-40subset baseline also runs natively, exits0after
18.58s and passes4/4propagation and strict-slew observations. Independent
timestep/tolerance/duration controls remain queued and no numerical bound is
inferred from the baseline. SF-40sequential native PID192238is verified live
with the expected golden-KLU deck, alongside the other two combinational
engines and Gear. Actual native count remains four.

Gear progresses beyond the50psreset ramp to5.05048ns. At this observation no
post-reset0.9Vcrossing is recorded; oscillation, settled frequency and sustained
throughput remain pending. Both original overnight deadlines are unchanged.

### 2026-10-21 — FF125 completes and second sequential native is admitted

FF125terminal assessment passes891/891propagation fixtures; strict output
slew ordering passes888/891. All three ambiguous threshold cases remain
retained. The campaign now records five new completed points plus three reused
points, giving eight of15raw combinational PVT observations. This does not
qualify timing constraints, interpolation, numerical bounds or physical load
domains.

SF125sequential native PID192378is verified live with the expected golden-KLU
deck. SF-40sequential PID192238, FS-40combinational PID186789and Gear PID190338
continue alongside it. Actual native count remains four. The selected numerical
controller advances from its passing subset baseline to the distinct queued
timestep-only control; no existing case is stopped or retried. Gear is beyond
reset release at5.06699nsbut has no post-reset threshold crossing yet. Both
original overnight deadlines remain unchanged.

### 2026-10-21 — FS-40 passes and timestep-only selected control completes

FS-40native exits0after4727.61s. Terminal assessment passes891/891propagation
fixtures and889/891strict slew observations; ambiguous crossings remain
retained. Six new points plus three reused points give nine of15raw
combinational PVT observations. No qualified timing view is produced.

The four-fixture SF-40timestep-only control exits0after32.20s and passes
4/4propagation/strict-slew observations. Halving maximum step from2ps to1ps
changes matched sampled delays by at most0.00253701ps(case87,input rise,second
opportunity). Case839input-rise delays remain approximately1.17947977ns and
1.16210752ns, so its17psrepeated-opportunity difference persists in this control.
This is selected-fixture evidence only. Relative/absolute tolerance and duration
controls remain queued; numerical uncertainty or physical history dependence
is not yet qualified.

FS27native PID192657is verified live with golden-KLU arguments alongside the
two sequential engines and Gear. All native counts/deadlines remain unchanged.
Gear advances to5.25908nsafter reset; no post-reset output crossing is recorded
at this observation. Startup and sustained oscillation checks remain pending.

### 2026-10-21 — Gear first falling transition agrees with retained TRAP startup

The existing read-only observer records Gear's first post-reset falling edge.
Independent interpolation of the complete waveform rows finds5.562466713338ns,
versus5.562479970433ns in the retained TRAP trace: Gear-minus-TRAP is
-0.0132571ps(approximately-13.26fs). This compares one startup crossing only,
not a complete oscillation period, settled frequency or numerical-domain bound.
No native input or verdict changes. Gear, two sequential batches and FS27
combinational characterization remain live under the original deadlines.

### 2026-10-21 — Projected previous-solution initial guess passes offline algebra only

The separate warm-start header and `native_warm_start_probe` retain the original
Jacobian/RHS and use the previous physical solution as a candidate initial
direction. A scaled least-squares projection is used only when its predicted
relative residual is below0.5; GMRES and the final true scaled residual still
require1e-12. The live adapter and simulator binary are untouched.

`native_warm_start_probe_checks_001` builds the isolated SDK probe and passes
all ten independent original-equation residual checks. On this single captured
matrix, repeated native RHS takes1.071sbaseline versus0.576swarm; a synthetic
0.1percentweighted RHS perturbation takes1.030sversus0.845s. An unrelated known
RHS takes0.956sversus1.015s, showing projection overhead when unhelpful. Repeated
RHS is an optimistic case, not a measured Newton history. No full-DCO speedup
is inferred and no live backend change is selected.

An additional audit's pointwise-relative synthetic-RHS check initially fails
near cancellation: maximum absolute difference is8.674e-19and weighted relative
difference8.425e-18. The retained attempt is resolved by an independent fsum
reconstruction with an explicit floating-point summation bound, without changing
the1e-12solver criterion. All four known-solution checks have relative error
<=2.984e-10. The successful audit, initial failed attempt, raw solutions/RHS,
source/build pins and unselected-candidate decision remain retained.

Gear has meanwhile completed one falling-edge startup period:1.163714097ns
versus1.163618013ns for retained TRAP. Its first rising edge is6.168810172ns.
These startup observations do not qualify settled frequency, calibration
uncertainty or the complete numerical domain; all release gates remain open.

### 2026-10-21 — Bounded preconditioner reuse is promising in offline algebra only

The separate warm/reuse header keeps the full current operator and RHS unchanged
while allowing up to eight applications of a cached preconditioner factor when
the wire-C multiplier is unchanged. Alpha changes or the reuse ceiling force
refactorization; a cached-factor GMRES nonpass triggers one fresh-factor solve.
The1e-12true-residual condition remains unchanged. The production/live header
and executable are not modified.

`native_reuse_probe_checks_001` passes20independently recomputed equation
residual checks. Exact native RHS repetition takes1.026sbaseline versus0.295s
candidate; the synthetic0.1percentweighted RHS change takes1.071sversus0.562s.
An unrelated known RHS takes1.061sversus0.699s on this unchanged matrix. Ten
candidate calls verify a fresh factor on calls1/10and exactly eight reuses
between them. Known-solution errors remain<=2.984e-10.

Changing Jacobians/scalings and the forced refresh-after-nonpass branch are not
tested by this captured-matrix sequence. No real nonlinear DCO speedup is
claimed and no live backend change is selected. Native controls and actual
Newton-sequence performance remain prerequisites. The current Gear point and
three cell engines continue under their original deadlines.

### 2026-10-21 — SF-40 sequential propagation completes

SF-40sequential terminal assessment passes108/108clock-to-Q/asynchronous-
assertion fixtures, increasing raw sequential coverage to three of15PVT
points including the reused FS125point. Setup/hold/recovery/removal,
metastability, interpolation and full physical timing domains remain
unqualified. No identical case is restarted, and the shared11:36UTC deadline
remains unchanged. Gear and the other admitted cell checks continue.

2026-10-21: SF125 sequential native execution completed with exit 0 after
3366.18 seconds; 108/108 fixtures passed. Raw sequential coverage is now four
of fifteen PVT points, including the reused FS125 point. These observations
do not qualify setup/hold, recovery/removal or a timing library.

The selected SF-40 relative-tolerance control completed natively (exit 0,
24.05 seconds) but its original assessor rejected four equal printed times.
The separate relative_tolerance_printed_time_reassessment_001 preserves every
sample and the original failed postprocessing receipt. All equal-time segments
are checked against every consumed voltage threshold; unresolved crossings and
decreasing times are rejected. Four propagation and four strict-slew fixtures
passed reassessment. Negative controls confirm both rejection paths. No native
case was rerun, and printed-time checks do not bound integration error.
collect_selected_compact_holdouts_v2.py consumes this separate receipt under
the unchanged campaign deadline; the original collector and receipts remain.

2026-10-21: A synthetic changing-matrix probe on the captured DCO graph exposed
an unsafe-to-adopt performance/accuracy result in the original factor-reuse
prototype. One stale-factor solve needed 199 iterations instead of 10 with fresh
factors and returned a known-solution error of 1.896e-6, above the unchanged
1e-7 offline criterion, despite its reported weighted residual passing 1e-12.
The original probe failed and remains rejected; its receipts are preserved.

OpenPLL_WirePreconditioner_warm_reuse_bounded.h limits a stale-factor attempt
to 20 iterations, then uses the existing current-factor, zero-initial-guess
solve on nonpass. It retains the 300-iteration fresh-factor limit and 1e-12
true-residual requirement. native_bounded_reuse_probe_checks_001 passed sixteen
baseline/candidate checks over eight synthetic diagonal and capacitance-multiplier
changes. Independent SciPy equations, generated RHS roundoff bounds and known
solutions passed; the fallback branch and multiplier-triggered refresh were
exercised. Maximum candidate known-solution error was 1.843e-10. Small coefficient
changes were faster, while stale-factor failures cost about twice a fresh solve.
These are synthetic algebra checks, not a real DCO Newton sequence or speedup.

build_bounded_reuse_Xyce.py compiled and linked an isolated candidate. Its final
manifest check incorrectly included its own output archive as an unchanged
input. audit_bounded_reuse_build.py separately verified all pinned original
inputs, all 504 archive members and the intended single replacement object;
503 original members were unchanged. recovered_build_assessment.json records
this recovery without overwriting the failed build receipt or rerunning the
build. All live sources, archives and the running Gear binary remained intact.

check_bounded_reuse_native_controls.py is queued under the common four-engine
admission lock, 6 GiB per-case limit and inherited DCO experiment deadline.
It reuses only completed stock controls, reruns candidate controls with the
new binary, checks variable order, nonlinear waveforms, timestep/tolerance
holdouts and logged true residuals using the retained thresholds. No identical
native retry or live DCO handoff is authorized by these results alone. Native
controls and actual DCO benefit remain unproven; no candidate is selected.

2026-10-21: The bounded-reuse native control runner remains queued behind
four verified live engines. A host-side watcher now waits for its terminal
receipt under the same inherited DCO experiment deadline. It will invoke
audit_bounded_reuse_native_controls.py to independently verify original input
and waveform hashes, metadata/GID mappings, numerical holdout deck differences,
waveform comparisons, every logged residual, the eight-reuse ceiling and
capacitance-multiplier-triggered refresh. Only three completed stock cases are
reused; all candidate cases are new. The watcher never starts a native circuit,
retries a case or changes the running DCO. The audit is pending, not passed.

2026-10-21: capture_delay_degradation_fs125_001 compares the existing 198
capture observations in 18 cell/input-kind groups against each group's -1000 ps
separated control. All original reviewed input hashes and case identities are
revalidated. Samples lacking a unique expected-direction edge and changed final
value retain their outcome but receive no invented delay. The largest observed
increase is 38.61705 ps (1.14019x), for dfstp_4 asynchronous release at +100 ps
relative to the clock; its separated reference is 275.45873 ps. Correct final
logic therefore does not establish unchanged clock-to-Q timing near capture.
The queued aperture refinement must be interpreted with output-delay degradation
as well as logic outcome. No degradation acceptance threshold, safe constraint,
monotonicity, interpolation bound or numerical-domain qualification is inferred.
This read-only analysis starts no native jobs and does not change the campaign.

2026-10-21: Gear_three_period_runtime_review_001 independently parses and
retains the native waveform prefix and the read-only observer history prefix.
Four post-reset falling edges provide three complete periods. The latest
15-minute history yields 0.05110 ns/min observed progress versus 0.16529 ns/min
needed to reach 80 ns by the inherited experiment deadline. The resulting
provisional remaining runtime is 23.14 hours, beyond the unchanged deadline.
This is a startup/runtime projection, not settled frequency, numerical
convergence, native failure or authorization to extend the 12-hour budget.
The live run is retained while bounded-reuse native controls await capacity;
any handoff still requires evidence supporting the replacement method.

2026-10-21: Short bounded-reuse solver controls now reserve the next free native
slot to prevent a long characterization job taking it first. The reservation
keeper acquired the common admission lock and verified the original controller
was waiting on candidate_names, with only a reused stock receipt and no native
launch. That queued controller was terminated before any native case started;
pre_native_scheduling_handoff.json preserves the reason and original receipts.
No running native process was interrupted. The replacement control runner uses
an inherited lock descriptor, verifies its inode and retains admission through
its short sequence, with the same four-engine cap, per-case limits and original
DCO experiment deadline. The keeper remains foreground until completion to
preserve the SIF mount. Output is bounded_reuse_native_controls_002; the v2
read-only completion watcher and auditor follow that replacement. Previous
control/audit outputs are retained. This is pre-native scheduling correction,
not an identical native retry, a longer budget or selection of a new solver.

2026-10-21: Reserved solver controls completed and the automatic independent
audit passed: 64,927 logged successful linear solves, all residuals <=1e-12,
matching metadata/GIDs and waveform comparisons under default TRAP, Gear,
separate timestep and separate tolerance controls. Disabled-adapter regression
is identical to stock. Maximum default output difference is 3.615 nV; the
Gear tolerance control remains within the existing protocol (4.851 uV maximum
output difference, 5.924 nA supply-current difference, 0.1111 fs rising-edge
difference). These small-circuit controls do not establish full-DCO accuracy
or performance. FS27 combinational characterization also completed 891/891
propagation and 889/891 strict-slew fixtures; raw PVT coverage is now 10/15.

A byte-identical Gear circuit is frozen in DCO_bounded_reuse_trial_prepared_001.
The explicit solver-only handoff uses the recent runtime-budget shortfall and
passed controls to select a bounded-reuse experiment, preserving the inherited
10:55 UTC deadline. The prior Gear native was stopped with SIGTERM, exited -15,
and its terminal receipt, full partial waveform and logs were retained.
retained_Gear_before_bounded_reuse_audit_001 verifies 2,205 samples through
9.656327176 ns, four rising/four falling post-reset edges, and all 3,981 reported
residuals passing 1e-12. It does not independently recompute every Jacobian
residual, establish settled frequency or reach the configured 20 ns window.
The controlled interruption is not a physical oscillation failure or timeout.

The handoff keeper reserves admission while check_bounded_reuse_DCO_map.py
performs an actual full-circuit names export with the new binary. The prior
native and owner are terminal before that export; no second large DCO overlaps.
A replacement transient can launch only after all variable IDs match the
retained reference. The keeper remains foreground through both stages to
preserve container lifetime, transfers admission to the new runner and retains
the original four-engine/resource guards. Circuit, Gear integration, tolerances
and timestep remain unchanged; only the linear-solver implementation differs.
A read-only host monitor waits for a verified native launch and will compare
the first two samples against retained prior Gear data. No full-DCO speedup,
calibration, qualified timing view or release is claimed.

2026-10-21: The new full-DCO names export exited 0 and passed: all 174,551
variable IDs match the retained reference, with names SHA256
1ff7aa058e8526dcc09496d0be936ef26399f3ef8a5e7955746569715f510b0f.
The gate completed in 281.49 seconds including its retained assessment work.
The keeper then transferred admission and started the bounded-reuse Gear native
point (controller 206123, native 206158) under the original deadline
3226730.312649184. The prior native and controller remain terminal. There are
four actual native engines, with only one full DCO, and the foreground keeper
remains alive for container lifetime. The read-only monitor follows the new
point. No waveform first-step comparison, full-DCO speedup, settled frequency
or qualified calibration is established at launch.

2026-10-21: The bounded-reuse full-DCO trial has begun transient solving.
The host monitor retained both first-two-sample prefixes and passed comparison
against terminal prior Gear data on the identical 0/10 ps grid: maximum voltage
difference 6.18645e-11 V and supply-current difference 8.21578e-13 A, below the
existing 1 uV / 100 pA thresholds. This validates only the initial comparison,
not full-trajectory accuracy, frequency convergence or runtime improvement.
Initial logged full-DCO solves pass the 1e-12 true-residual criterion, and the
fresh-factor fallback branch has been exercised in native startup. The live
trial and inherited deadline remain unchanged.

2026-10-21: A host-side read-only cycle comparator is attached to the verified
bounded-reuse native. It waits for four post-reset edges in each direction,
then compares the first three rising and falling periods against terminal
prior Gear data. It verifies byte-identical circuit decks and retained-source
hashes, snapshots both waveform prefixes, and reports signed edge, period and
frequency differences without selecting an acceptance limit or inferring a
native verdict. Five synthetic checks passed: known phase shift, known period
change, insufficient-cycle deferral, incomplete last-record handling and time
reversal rejection. The observation inherits the DCO deadline and never starts,
stops or retries a native case. Unsettled startup agreement does not qualify
full-trajectory accuracy, timestep/tolerance/duration convergence or calibration.

2026-10-21: A separate deadline guard reserves the last five minutes of the
existing DCO experiment budget for terminal assessment. If the same identified
native is still running at deadline minus300 seconds, the guard records the
budget-stop decision, signals only that verified native process group, and lets
the existing controller retain its normal partial-data receipt before the
original deadline. Earlier native completion causes no interruption. Wrong
identity and non-leader group targets are rejected. Four dummy-process checks
passed (identity rejection, matching-group termination, no signal to a terminal
process, and non-leader rejection); no native circuit was started by the checks.
The live guard passed check-only validation and is waiting. It never extends a
budget, retries a case, infers physical failure or qualifies a partial result.
This closes the scheduling gap where a transient could consume all12h and
leave no assessment time; actual terminal receipt production remains monitored.

2026-10-21: The short duration-only numerical holdout had remained queued for
over an hour. reserve_compact_duration_holdout.py acquired common admission,
verified its original worker had no launch/log/exit record and no native child,
and replaced only that queued controller with an explicit pre-native priority
handoff. The original worker exited -15 before any native case started; its
parent campaign and incomplete collectors retain their truthful original
receipts. Running native engines were not interrupted. The new worker retains
the exact deck, plan, nominal PVT, tolerances, timestep and original shared
11:36 UTC deadline, with output duration_only/run_002. It inherits admission
and reserves the next free slot under the four-engine cap. Its assessor is the
previously checked printed-time parser that retains every safe equal-time
sample and rejects unresolved threshold crossings. This is the first native
execution of this duration control, not an identical native retry.

collect_selected_compact_holdouts_v3.py follows the priority reservation and
will combine its terminal result with the separate relative-tolerance
reassessment and other original receipts, preserving all original failures and
handoff records. It verifies receipt/deck hashes and retains subset-context,
single-control and repeated-opportunity differences. Full numerical bounds and
timing-library qualification remain open. The keeper stays foreground through
execution and assessment; no container child is orphaned.

2026-10-21: The bounded-reuse DCO produced its first post-reset falling edge.
A read-only review retains the exact candidate waveform prefix and verifies
byte-identical prior/current decks and retained-reference hashes. The 0.9 V
crossing is 5.562466713385694 ns versus prior Gear 5.562466713338016 ns; the
interpolated difference is 4.768e-20 seconds. Timestamp agreement at this one
startup edge is not a physical accuracy bound, numerical-domain convergence,
settled frequency or complete-period comparison. The collector continues toward
three complete periods in both directions; the live native is unchanged.

2026-10-21: SS-40 combinational characterization completed: 891/891 propagation
and 889/891 strict-slew fixtures, bringing raw combinational coverage to11/15
PVT points. Its freed slot was taken by the reserved duration control, which
completed its first native execution with exit0 in27.5525 seconds and passed
4/4 propagation and strict-slew fixtures. The v3 collector completed all five
selected four-fixture controls with no missing measurements; original failed
postprocessing and pre-native scheduling receipts remain preserved.

The selected SF-40 delay differences are: subset-context maximum0.001778 ps,
timestep-only0.002537 ps, relative-tolerance-only0.003244 ps and
absolute-tolerance-only0.000118 ps. Extending the same pulse train to50 ns
leaves the first two opportunities identical. The largest first-to-second
change is17.37247 ps (xor2_2 case839 rise), while the third-to-second change is
0.003565 ps. Thus the large observed initial-opportunity difference persists
under these chosen numerical controls; replacing all observations by the last
repeated value would discard a real retained waveform effect. Keep initial and
later observations in conservative timing characterization. This does not
establish its physical cause, a global numerical-error bound, unmeasured
ramp/load/PVT coverage or qualified timing views. Signed negative50% delays in
slow-input fixtures are retained rather than clamped. All release gates remain
open; no timing library is adopted.

2026-10-21: The capture-aperture refinement had been queued over four hours
behind all sequential workers. It informs the missing physical setup/hold and
reset constraints, so reserve_capture_aperture_refinement.py now reserves its
next slot. Under common admission it verified the old controller had no launch,
log or exit record and terminated only that queued controller. Original queue
records remain; pre_native_priority_handoff.json binds the replacement. The new
worker uses unchanged90-fixture deck/plan and the original11:36 UTC shared
deadline, with output run_002, 6 GiB per-native limit and four-engine cap.
Admission transfers to the worker and is released immediately after native
launch, allowing other available slots to be filled during the longer run.
The parent stays foreground for container lifetime. No native was interrupted
or retried and the budget was not restarted.

review_reserved_capture_refinement.py waits for the terminal receipt, rechecks
raw artifacts and the reviewed original198-case inputs, matches the36 repeated
control fixtures by complete stimulus/port identity, and reports output-state
and edge differences. It merges only valid new samples, retains all invalid or
ambiguous observations and every adjacent outcome transition, and reports
clock-to-Q degradation relative to the original separated controls. It does not
assume monotonicity or infer safe constraints, global numerical bounds or MTBF.
The review is pending; no physical timing gate is closed by its preparation.

2026-10-21: SF27 combinational characterization completed891/891 propagation
and889/891 strict-slew fixtures, bringing raw combinational PVT coverage to12/15.
FF125 sequential completed108/108 fixtures with native exit0 in3362.486 seconds,
bringing raw sequential coverage to5/15. These are propagation observations,
not qualified setup/hold/recovery/removal views.

The freed SF27 slot admitted the reserved90-fixture capture refinement
(controller209785, native209786). Its admission lock was released after launch;
another native characterization case (TT-40, PID209828) subsequently started
while the capture transient remained live. Actual concurrency remains four,
including one full DCO; no capacity is held idle for the longer refinement.
The same inherited shared deadline applies. Its completion review is waiting.
The DCO also produced its first rising edge at6.168810172172641 ns versus prior
Gear6.168810172298939 ns. Both first-edge comparisons remain startup observations,
not complete-period, settled-frequency or numerical-domain qualification.

2026-10-21: The bounded-reuse DCO produced a second falling edge, providing
its first complete falling-edge interval. A separately retained waveform-prefix
review compares1.163714221947781 ns with prior Gear1.163714097022448 ns: the
frequency difference is approximately-0.10735 ppm of the reference. Both are
startup periods, with no settled-frequency or physical/numerical uncertainty
bound inferred from their close agreement. The full three-period-per-direction
collector and native transient continue under the unchanged deadline.

2026-10-21: An isolated scale-aware factor-reuse prototype was checked offline.
It transforms a cached scaled inverse into current row/column coordinates,
P^-1=(C_old/C_new)*B_cached^-1*(R_old/R_new), retaining the same original
matrix/RHS, alpha/reuse ceiling, stale-iteration cap and true-residual criterion.
A three-state explicit physical matrix independently checks Apply, ApplyInverse
and NormInf under nonuniform coordinate changes. The captured full-size graph
then exercises baseline, current bounded-reuse and scale-aware variants over
eight synthetic matrix/RHS steps: all24 independently recomputed residuals
and known solutions pass the unchanged criteria (maximum known-solution error
1.843e-10). The new variant has the same fallback cases and essentially the
same aggregate single-trial time as current bounded reuse. No meaningful speedup
is demonstrated. decision.json leaves it unselected; no full simulator binary
or native transient was built/run for this variant. All running sources and
binaries remain unchanged. This does not establish a general performance bound.

2026-10-21: The reserved FS125 capture refinement completed natively with exit0
in1054.579 seconds. All90 waveform observations pass integrity checks and all36
separated controls pass. Independent completion review revalidates raw artifacts
and original receipt hashes, confirms36/36 repeated outcomes match with no
unmatched edges, and retains54 new interior samples for252 unique observations.
The maximum repeated-control edge difference is0.001029 ps. Each of the18 groups
has one observed adjacent outcome transition bracket, now12.5 or25 ps wide;
this is sampled behavior, not a proof of monotonicity between offsets.

The largest observed correct-capture delay increase is163.087 ps for dfrtp_2
with falling data at-75 ps relative to the clock: clock-to-Q407.464 ps versus
244.377 ps at the separated control. Logical outcome alone therefore cannot
justify adopting the refined outcome boundary as an unchanged-delay constraint.
No delay-degradation threshold or global physical timing envelope is selected.
Next, characterize subset-context effects and independent timestep/tolerance
holdouts at refined bracket endpoints and separated controls before using these
observations to justify conservative constraints. The original ramp/load/PVT
scope remains200 ps /5 fF /FS125; other slew/load/PVT and uncertainty coverage
remain required. No timing view, MTBF bound or release gate is qualified.

2026-10-21: Capture numerical controls are prepared and queued under the same
shared11:36 UTC deadline, including preparation, waiting and assessment. The
selected72 fixtures comprise both observed refined-bracket endpoints and the
early/late separated controls for each of18 cell/input-kind groups. Four cases
run one at a time: subset baseline (2 ps, REL1e-5, ABS1e-10), timestep-only1 ps,
relative-tolerance-only1e-6, and absolute-tolerance-only1e-11. The original200 ps
ramps,5 fF load,28 ns horizon,1.8 V supply andFS125 models/stimuli are unchanged.
Every holdout deck differs from the subset baseline in exactly one parameter.
All new cases print16-digit precision; baseline comparisons to earlier batches
explicitly include both subset-context and print-precision effects.

Independent preparation checks verified864 native PWL sources,288 copied
fixture/port identities, three isolated deck changes and72 ideal-oracle
observations including36 separated controls. This is synthetic bookkeeping,
not physical timing evidence. run_capture_numerical_holdouts.py reserves its
next available slot, transfers/relinquishes admission on native launch, waits
foreground for container lifetime, and retains the four-engine/6 GiB guards.
Only a valid72-observation/36-control subset baseline permits the other cases.
No completed native input is automatically retried and no budget is restarted.

collect_capture_numerical_holdouts.py is attached to the identified controller.
It will revalidate terminal artifacts and compare all72 outcomes, all matched
edge differences, unmatched events and invalid observations against the subset
baseline. It also retains prior-batch comparisons with their context/printing
scope. It selects no numerical acceptance threshold and adopts no constraints
or timing view. All release gates remain open while these controls are pending.

2026-10-21: A source/runtime review investigated constant-capacitor overhead
without changing the live run. Xyce already uses bulk capacitor Master loops;
it does not dispatch a virtual instance call for every constant capacitor.
The generic-external interface supports sparse stamps but indexes dense matrix
payloads, so a direct full-dimension replacement is not a selected scalable
path. Constant-capacitor charge-state writes are commented out and the Master
secondary-state update is a no-op; any compact path must still preserve all
original Q contributions, signs, coefficients and their order, and fall back
for dependent, explicit-IC or lead-current cases.

The retained native-log prefix and process uptime show reported completed
linear-solver wall time accounts for roughly56% of total elapsed time including
setup. Pending solve time and all setup/device/integration/IO work are outside
that sum; the remainder is not attributed to capacitors. Kernel perf access is
unavailable (paranoid4), no host GDB is present, and no instruction-level profile
was obtained or native interrupted. No optimization is selected. Any compact
fixed-parameter capacitor candidate requires separate benchmarking and native
original-equation/waveform controls before adoption; the live trial continues.

2026-10-21: An opt-in packed constant-capacitor source candidate is isolated in
compact_constant_cap_source_001. It retains original topology, state counts,
matrix stamps, coefficient signs, multiplicity and capacitor contribution order.
During fixed-parameter transient loading, eligible linear constants use packed
(coefficient, multiplicity, positive LID, negative LID) records; their charges
are recomputed and accumulated in the original instance order. Explicit-IC,
lead-current, solution/dependent-parameter and nonzero-temperature-coefficient
instances retain the stock path. DC/non-transient operation stays stock;
cache readiness resets across DC and decreasing simulation time. The opt-in is
OPENPLL_PACKED_CONSTANT_CAPS=1. Sensitivity/external parameter mutation and
general multi-analysis applicability are not qualified by this prototype.

The isolated copied-archive build completed. All504 archive members were audited:
only N_DEV_Capacitor.C.o differs from the current bounded-reuse archive, with503
members unchanged, including the solver object. Live sources, archive and binary
remain unchanged. The new binary requires native waveform controls, excluded-path
controls and measured performance benefit before any full-DCO consideration.
No full-DCO handoff is selected by source preparation or successful compilation.

A short original-nonlinear native control sequence is queued under the original
DCO experiment deadline and four-engine cap. It reuses six completed stock cases,
requires positive packing events on adapter cases, and checks the disabled
regression without packing. Its automatic audit will recheck metadata, waveforms,
true residuals, factor decisions and packing events. Explicit-IC/dependent/probed
path coverage and performance remain pending beyond these initial controls.
The foreground keeper preserves the SIF lifetime and never interrupts the live
native trial. No budget is restarted or extended.

2026-10-21: check_compact_cap_excluded_paths.py prepared an independent ten-cap
mixed fallback fixture and is waiting for the initial packed-cap native audit.
It compares the unchanged bounded-reuse simulator against enabled and disabled
candidate runs using KLU, with no wire preconditioner. Four constants include
negative capacitance and multiplicity; six excluded cases cover explicit IC,
solution-dependent C and Q, combined global/time-dependent C, a lead-current
probe and nonzero TC1. Eligibility counts and all printed node/current traces
must agree with the fixture contract and retained reference. No native result
or performance benefit is claimed before receipts. The inherited DCO deadline,
four-engine cap and foreground SIF lifetime apply; there is no automatic retry.
Sensitivity and external parameter mutation remain unqualified.

The completed bounded_reuse_DCO_cycle_comparison_001 retains three startup
periods in each edge direction against the prior Gear prefix. Maximum period
frequency difference is20.954456ppm and maximum absolute edge difference
is19.130825fs. No acceptance limit was selected; these unsettled startup cycles
qualify neither full-trajectory accuracy nor settled frequency. The live DCO
projection remains beyond its inherited deadline; the guard and deadline are
unchanged. SS27 combinational raw measurements completed891/891 propagation,
889 strict output-slew cases. Raw combinational PVT coverage is13/15; this is
not a qualified timing-view count. All six release gates remain open.

2026-10-21: The initial packed constant-cap native controls completed with
worker exit0. compact_constant_cap_native_controls_audit_001 independently
passed64927 successful linear solves, five waveform comparisons, original
GID/preservation masks, true original-equation residuals and separate timestep
and tolerance controls. All four adapter cases emitted positive packing events;
the disabled regression matched its stock waveform exactly. The largest
waveform difference was4.851388uV on the tightened Gear control. This does not
cover the excluded paths, general simulator equivalence or full-DCO performance.

benchmark_compact_constant_caps.py prepared a frozen150000-capacitor/64-node
fixture, with reference/enabled/disabled executions declared before launch.
It waits for mixed-fallback correctness controls before native admission.
Each case has a120s wall limit and6GiB AS guard, inherits the original DCO
deadline, and observes four-engine admission. The native metrics distinguish
transient stepping, residual load, Jacobian load and linear solve from setup.
Waveforms must also pass fixture equivalence checks. The benchmark is a
small-node-count capacitor-loop experiment; neither statistical repeatability
nor full-DCO speedup is inferred. There are no automatic failed-case retries.

Independent audit_compact_cap_benchmark_preparation.py parsed all150000 actual
cards, including8824 negative coefficients and6522 multiplicity-two instances,
and assembled their signed64x64 operator. It is symmetric positive definite,
minimum eigenvalue7.667702317e-15F, far above the1.538720262e-26F numerical
allowance. Every fixture node has a source resistor and all protocol/deck
checks pass. This proves preparation only; native performance remains pending.
TT-40 raw combinational measurements completed891/891 propagation,889 strict
slew cases, bringing raw PVT coverage to14/15. TT125 remains live. This does
not create qualified timing views; all six release gates remain open.

2026-10-21: Read-only audit_DCO_capacitance_magnitude_tail.py parsed all5492690
CFIELD branches across148215 nodes without changing coefficients or model.
Only109711 branches(1.9974%) are below1e-30F. Reaching roughly half the branches
requires a1e-19F threshold, whose conservative whole-matrix incident-row bound
is4.721464769e-16F. Thresholds are diagnostics, not selected reductions.
check_DCO_cap_tail_decimal_bounds.py independently checked all nine reported
maximizing-node witnesses against100-digit original decimal sums; all bounds
contained those sums. It does not repeat the original global maximum search.
No passivity, trajectory/frequency-error or pruning qualification is inferred.
Tiny numerical-residue counts do not establish a substantial runtime benefit.

An isolated instrumentation-only bounded-reuse header fork measured offline
solver phases on the captured graph with the original eight synthetic matrix
changes. native_bounded_reuse_stage_probe_checks_001 passed all16 original-A,
original-RHS, known-solution and true weighted-residual checks. The successful
review is native_solver_stage_profile_review_002: removing exactly the phase
clock/output additions reproduces the frozen bounded-reuse header byte-for-byte.
The first host-only collector failed on a pinned container-only libamd path;
its failure receipt remains under review_001. Only the assessment was repeated
inside the SIF; no probe/native circuit was retried.

Across the eight instrumented solves, GMRES accounted for46.66% and conditional
fallback branches23.11% of internal measured solve time, versus8.65% scaling,
7.49% matrix copy/scale,10.51% initial factor updates and small other work.
Clock/output overhead is unmeasured; initial cache setup lies outside these
internal timers. This is not an actual nonlinear RHS sequence or live-DCO
profile. The evidence directs further offline investigation toward GMRES and
fallback costs; it does not justify a simulator handoff or model reduction.

The72-fixture capture numerical subset baseline completed72/72 integrity and
36/36 separated controls. Independent timestep/relative/absolute comparisons
remain pending under the existing campaign deadline. No capture constraints,
MTBF, physical timing view or release gate is qualified by this baseline.

2026-10-21: The proactive factor-drift reuse prototype retains original matrices,
RHS, the1e-12 true residual gate and existing stale-factor fallback. A scaled
preconditioner row-relative change above1e-6 refreshes the factor before a stale
attempt. native_drift_reuse_probe_checks_001 passed48 original-equation and
known-solution checks on16 predeclared synthetic perturbations, with maximum
known solution error1.170498226e-9. Aggregate times were14.9524s fresh baseline,
20.3616s bounded reuse and12.8294s drift-aware; bounded had8 fallbacks, drift0.
These synthetic controls do not establish live Newton-sequence performance.

A separate read-only live log-prefix audit retained5320 completed solver calls:
775 fresh,4437 successful reuses and108 reuse-then-fallback cases. The latter
accounted for only5.2374% of reported completed solver wall time; successful
reuse accounted for76.3071%. Group times include whole solves, not isolated
fallback internals, and exclude pending calls. This evidence does not support
making proactive refresh the primary live-runtime fix; the candidate remains
offline and no simulator source or running job was changed.

native_matvec_probe_checks_001 tested unchanged captured174551x174551,
11209902-nonzero matrix products with Epetra and standalone one/two/four-thread
CSR row loops. Row partitions balance nonzero counts; rows retain their original
sum order and all coefficients/signs. Three input patterns per variant passed
summation-bound comparisons; observed difference from Epetra was exactly zero.
Four independent SciPy checks of saved products passed. Fifty predeclared timed
products took0.93587228s Epetra,1.12053914s custom serial,0.597101041s two-thread
and0.303631224s four-thread, approximately3.08x at four threads for this kernel.
Warmups, passive OpenMP waiting and an at-most-four-thread limit were explicit.
These are standalone matrix-product results, not an integrated solver or live
DCO speedup, and repeatability is not statistically qualified. Next consider an
isolated solver operator with original serial residual checks and independent
captured-equation/native-waveform controls. No live handoff is selected now.

2026-10-21: The isolated OpenPLL_WirePreconditioner_parallel_reuse.h uses an
Epetra operator for unchanged CSR row products inside GMRES. Its scaled matrix
is packed without changing coefficients; nonzero-balanced row partitions request
up to four OpenMP threads. Small operators below4096 rows stay serial. Original
preconditioner/factor reuse, seed logic and the final serial scaled-A true
residual gate remain. Transpose, inverse, aliased vectors, multiple RHS and
incompatible maps are unsupported/rejected. No live source or binary changed.

native_parallel_reuse_probe_checks_001 passed48 independent original-equation
and known-solution checks on16 synthetic perturbations, including the existing
fallback branch. native_parallel_rhs_probe_checks_001 passed10 additional
captured-native-RHS/repeated/perturbed/known-RHS controls. The latter is a fixed
captured matrix and first native RHS, not a complete nonlinear Newton sequence.
The independent parallel_solver_probe_comparison_audit_001 revalidated inputs,
all10 original RHS identities (with a forward summation bound for perturbation
construction), and21 paired solution files. All paired solutions were bitwise
equal. All58 original-equation residual checks retained the1e-12 limit.

Complete synthetic solve times were20.64605323s bounded and17.764794806s parallel
(13.96% less). Captured-RHS controls were3.383821341s bounded and3.069751682s
parallel(9.28% less). This supersedes any inference from the3.08x standalone
matrix-product benchmark: no full-DCO speedup was measured. Runtime team sizes
were requested by OpenMP, not separately instrumented; repeatability remains
unqualified. No native simulator build, waveform qualification or live handoff
is selected by these offline results. Per-solve matrix copy/storage preparation
is a remaining measured-source optimization candidate, requiring new controls.

compact_nominal_15PVT_completion_001/assessment.json is now terminal and reports
all15/15 raw combinational PVT points, each891 fixtures. It explicitly retains
zero qualified timing views, unqualified numerical-domain enclosure and open
sequential constraints. The capture timestep-only control is now native; the
other capture numerical profiles and capacitor fallback/performance controls
remain subject to existing admission and inherited deadlines. All six release
gates remain open; no release tag or qualification claim is made.

2026-10-22: User selected https://github.com/nindanaoto/Xyce.git and
https://github.com/nindanaoto/KLS.git for new qualification, replacing KLU as
the candidate solver. xyce_kls_toolchain.json records pinned commits, the exact
binary and adapter patch, container, solver options and provenance. Xyce commit
ff7abc4b313974c81b4ebc17f713cc912da9bf4b and KLS commit
a3be41b58833f1548a8bc48df75bf34813ca2eba plus pinned GKlib/METIS/SCOTCH/SPRAL
submodules were built in local scratch with a workspace source snapshot and
manifest. KLS is enabled with Xyce_KLS=ON; new native decks select TYPE=KLS.
Golden KLU remains a reference. No prior check was retried or budget extended.

The unmodified fork compiled but failed its own testKLSAdapter on permuted
column maps. build_001 retains its regression failure. The serial adapter used
Epetra local column IDs directly as domain-vector indices. The isolated
xyce_kls_column_map.patch translates through global IDs into domain-local IDs,
and rejects changed cached columns during numeric updates. The original clone
and KLS library remain unchanged. Copied-archive build_002 changes only
N_LAS_KLSSolver.C.o and passes the unchanged adapter regression (AUTO/SERIAL,
normal/permuted maps, numeric changes, reuse, transpose, multiple RHSs).

native_controls_002 passed nine transistor/signed-C waveform controls against
retained golden data: fork KLU and KLS at one thread across original TRAP,
Gear, timestep and tolerance profiles, plus four-thread KLS Gear baseline.
Transient settings and signed branches are unchanged. The full captured DCO
matrix(174551 rows,11209902 nonzeros) then passed two independent SciPy original
weighted-residual checks at1e-12 on native and known RHSs. KLS analysis took
11.0572s, factorization48.5430s and reported peak memory2.61095GB. These are
captured-equation results, not full transient timing or calibration.

The fresh user-selected solver campaign includes source checkout, build,
controls, queue, full-matrix probe and DCO assessment within one12h deadline,
ending2026-10-23T01:36:39.734568UTC. The old campaign remains terminal. The new
DCO TT27/c0/f24780ns Gear diagnostic waits on both waveform and full-equation
gates, checks full native variable names, then runs with KLS_THREADS=4. Its
physical deck,20..80ns measurement window,10ps maximum step, RELTOL1e-5 and
ABSTOL1e-9 remain unchanged. It reserves five minutes for assessment and never
retries an identical failed native case. No release gate is qualified by tool
selection or these preliminary checks.

The new fork/KLS native variable-map phase completed with174551 variables,
identical names and identical GID order to the retained candidate. The80ns
transient has now started using build_002/bin/Xyce with TYPE=KLS and four KLS
threads. Its launch/identity, original-tolerance deck and inherited deadline
are retained in DCO_nom_tt27_c0_f247_80ns_001. Full transient performance and
frequency convergence remain pending; all six release gates remain open.

User requested publication: the tested adapter column-map patch was committed
and pushed to nindanaoto/Xyce branch kls as 8e88b9dd18b5c5e798a035e354ae0ffcab450a7a.
The published source matches the locally tested source byte-for-byte. Remote
branch HEAD was independently verified after push; KLS itself was unchanged.
Original binary build provenance remains the prior fork commit plus this patch.

2026-10-23 terminal-state audit: no Xyce or KLS controller remained live. The
fork/KLS DCO transient stopped under the campaign budget guard(SIGTERM,-15),
with1054 samples through6.285594619830217ns, before the20ns measurement window.
Transient wall time was41645.9551s; the whole campaign retained its original
12h deadline, including checkout/build/controls/queue and assessment. The case
is incomplete/inconclusive, not an observed physical400MHz failure. Passing
adapter, nine native-control and two captured-equation checks remain valid
within their stated scope. Full DCO throughput did not improve in this trial;
profile changing-matrix factor/refactor/solve costs before another performance
experiment. No automatic identical native retry or release qualification.

2026-10-23 KLS slowdown diagnosis: graph audit found730204 entries in the prior
KLU-factored preconditioner, versus11209902 in the new directly factored KLS
matrix. The previous outer GMRES still solved the unchanged full equations;
this was a strategy change, not an equal-work KLS/KLU benchmark. Native-default
captured-matrix profiling measured123.834s factor and0.555s solve. Its first
changed refactor remained CPU-active for minutes; that synthetic diagnostic
was stopped deliberately, with a controlled-handoff receipt and no inferred
numerical failure, to allow actual native-call profiling.

A timing-only copied-archive adapter build preserves the published map fix and
passes the unchanged adapter regression. No KLS kernel or numerical policy was
changed. The bounded native prefix uses the exact prior deck and stops after
12 calls or20min, within the1h total diagnosis budget. The first four completed
calls measured initial factor125.006s, first refactor+solve504.628s, then37.519s
and33.477s for following refactor+solve calls. Matrix value checking/copying was
about0.096s per call, and the standalone solve term in the first call0.550s.
Initial L and U each had118740035 entries, changing to78596630 each after the
first update. Factor/refactor+solve dominates these sampled calls; no full-run
time fraction or accuracy certificate is inferred from this timing trace.

The prior standalone screen supplied20000 expected updates/solves; the native
deck omitted these hints, whose API defaults are0. This affects KLS's selected
factor geometry. A separately queued hinted-workload update test will measure
that effect without changing certification. No hinted speedup is assumed now.
findings_001.json retains the first-four-call snapshot and exact graph audit.
Next compare KLS as the existing sparse preconditioner backend with outer GMRES
and the original-equation residual gate retained, rather than assuming direct
full-matrix KLS beats the prior strategy. No overnight qualification rerun or
release gate closure was performed by these bounded diagnostics.

### KLS sparse preconditioner, 2026-10-23

Implemented the user-approved change in `OpenPLL_WirePreconditioner_KLS_reuse_bounded.h`: KLS factors the same 730,204-entry approximation as the previous bounded-reuse Amesos/KLU backend. The outer GMRES implementation and original-equation residual checks are byte-identical; all signed physical capacitors remain in full A. KLS default certification remains enabled, with four threads and explicit lifecycle hints of 20,000 refactorizations/solves. Column indices use ColMap → global → DomainMap translation. Unsupported maps and failed KLS calls fail the candidate without silently substituting KLU.

The 16 changing-matrix known-answer comparisons and 10 captured-RHS comparisons passed independent full-equation weighted residual checks ≤1e-12. Four native BSIM/signed-C waveform controls passed, including timestep/tolerance holdouts. Sparse-preconditioner L and U each contain 1,534,355 entries; the first captured native RHS takes 2.107 s, repeat 0.293 s. KLS is slower than KLU on this same preconditioner in these comparisons; this change addresses the full-matrix factorization cost and does not demonstrate native transient speed yet.

The isolated fork build and unmodified adapter regression passed. Evidence is in `build/timing400/release_001/KLS_preconditioner_001/implementation_assessment.json`. A new algorithm campaign includes preparation from 04:59:17 UTC and ends at 16:59:17 UTC on October 23, with five minutes reserved for assessment. The unchanged physical 80 ns DCO case is launched only after these prerequisites; no automatic identical retry. This solver candidate is not a release qualification, and no upstream push of this new experimental backend has been made.

### Updated KLS certification opt-out comparison, 2026-10-24

Rebuilt upstream KLS `7d2c909c6ab77a7201bad8559b024f4e97625840` in isolation. Compared the unchanged bounded-reuse GMRES adapter using Amesos/KLU versus KLS with componentwise certification and application-managed policy, each at one and four threads. The full-A solver and its ≤1e-12 true weighted residual gate were byte-verified unchanged. Three randomized repetitions covered five captured-RHS cases and eight synthetic matrix changes per variant; all 195 independent original-equation checks passed. Seven upstream API/accuracy tests, including the application-managed opt-out, passed. All original source archives and test inputs remain pinned.

Median total times (RHS / changing-matrix): KLU 3.078 / 8.364 s; certified KLS, one thread 4.006 / 13.967 s; certified KLS, four threads 3.952 / 12.001 s; application-managed KLS, one thread 3.542 / 12.616 s; application-managed KLS, four threads 3.573 / 10.999 s. Four-thread opt-out reduces the sum of these stage medians by 8.66% versus four-thread certification, while remaining 27.35% above KLU in the short benchmark. Most of the remaining changing-matrix gap is concentrated in startup and the first stale-factor refresh; later cases are competitive with KLU. This is not a full-transient speed measurement.

The isolated updated Xyce candidate passed its existing adapter regression and all four signed-C/BSIM native waveform controls, including timestep/tolerance holdouts. A full physical DCO variable-map check matched all 174,551 variables and GID order, followed by a deliberately bounded native prefix of 64 completed solves. Every logged full-equation residual check passed. The prefix stopped at the planned call count; no 80 ns qualification or full-DCO speed claim is made. Total preparation/build/benchmarks/native checks stayed inside a one-hour owner budget. Evidence: `build/timing400/release_001/KLS_certification_comparison_001/results.json`. No candidate was automatically promoted to release qualification or pushed upstream.

Preserved diagnostic corrections: the initial perturbed-RHS construction audit was corrected for cancellation using a floating-point forward-error bound; the original-equation 1e-12 residual threshold stayed unchanged. Runtime policy readback rejected a reversed selector in the first changing-matrix fixture; that run was excluded and the corrected fixture was forked. The isolated Xyce link was updated to include OpenMP required by the updated KLS library. Earlier receipts remain available.

### KLS update and detailed phase profile, 2026-10-25

Bumped the selected KLS library/source to upstream `56abf844fb07931370ef386ff724124dfa5d965c`. The unmodified library is built separately from diagnostic libraries; normal binaries remain free of function/allocator/CPU instrumentation. The unchanged Xyce adapter was relinked after verifying its public KLS ABI header is byte-identical, then passed its adapter regression and four signed-C/BSIM waveform controls. The selected normal toolchain uses four-thread application-managed KLS with the unchanged original-full-equation 1e-12 acceptance gate.

Three randomized uninstrumented baseline repetitions were followed by 50-scope phase/allocation diagnostics, independent instruction sampling, and a refined 60-scope cold-setup diagnostic. All 175 independent captured-equation checks passed, alongside four selected upstream tests. Recovering the diagnostic insertions reproduces the upstream source exactly. Worker elapsed time overlaps caller time and is not added to API wall time. Allocator counters are cumulative requests, not a live-memory peak. CPU samples locate hot code; fixture loading, verification and sparse-matrix work are present and the sample fractions are not production wall-time shares.

The captured eight-update workload's first refactor took 2.892 s; `maybe_promote_auto_metis` accounted for 2.778 s and requested 2.715 GiB across 382,810 allocations. The trial retained the initial AMMF/transposed ordering. Subsequent refactors averaged 41.84 ms; 129 solves averaged 11.25 ms, with 94.55% of their API wall time in KLU-derived triangular solves. Statistics queries totaled only 20.62 microseconds in that run. Certification was disabled and confirmed to cost zero; certified controls measured its separate cost.

A diagnostic exit after 64 accepted linear solves preserved the original 80 ns deck and startup time grid while flushing phase reports. Its circuit retained all 174,551 verified variable GIDs; all 64 logged full-equation checks passed. KLS API calls used 27.844 s of 94.702 s in the adapter (29.40% including statistics queries). The remaining adapter time covers scaling, full-matrix operations, GMRES and adapter bookkeeping. This startup diagnostic is not an 80 ns qualification or a steady-state speed claim. The complete update/build/profile/native assessment stayed within the one-hour owner budget. Evidence: `build/timing400/release_001/KLS_detailed_profile_001/results.json`, with caller CSV tables and CPU-sample reports alongside.

Preserved setup corrections include the upstream allocator-test target prefix, wrapper include paths, the revision's legacy certification wrapper interface, removal of an unused transpose wrapper not supplied by the upstream diagnostic, and restoration of a copied executable's mode. A shortened-endpoint diagnostic altered startup timesteps and was deliberately stopped; the original-deck boundary-exit diagnostic replaced it within the same owner deadline. No failed setup attempt was treated as an equation pass, and prior receipts remain available.

### KLU release baseline, 48-hour campaign (2026-10-25)

User authorized KLU for the required release simulations and a new 48-hour run. `build/timing400/release_001/KLU_release_48h_001/owner.json` fixes the deadline at 2026-10-27T17:16:40.691741+00:00. `run_KLU_release_48h.py` reuses the byte-identical 80 ns TT27, 1.8 V, coarse0/fine247 deck, verified KLU binary and native variable mapping. Gear tolerances and the full scaled true residual limit of 1e-12 are retained. Preparation, admission and assessment share the budget; native execution reserves the final five minutes for assessment. One large native case runs exclusively, with no automatic retry. Live progress is in `status.json`; terminal evidence will be in `assessment.json`. This baseline alone does not qualify frequency convergence, parent loading, the runtime model, or the release. KLS profiling is complete and no further profiling is scheduled.
