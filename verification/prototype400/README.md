# Programmed 400 MHz prototype

The active profile is [`requirements_v3.json`](../signoff400/requirements_v3.json),
as selected by [`active_release.json`](../active_release.json): 25 MHz reference,
400 MHz output, 1.8 V, 27°C, TT/FF/SS/SF/FS. The deliverable is a verified macro
handoff. Other frequencies, temperature qualification, automatic acquisition,
precision jitter qualification and chip/shuttle submission are deferred.
Historical four-mode requirements remain unchanged; their former active pointer
is preserved in `verification/active_release_four_mode_400mhz.json`.

## Current release blockers (2026-11-08)

The 400 MHz prototype is not release ready. All five gates remain open; the
historical implementation notes below do not override the active v3 profile.

| Gate | Evidence still required |
| --- | --- |
| Physical integrity | Resolve extracted RC/ground-capacitance concerns and bind final checks to the selected candidate. Running ground audits are not passing receipts. |
| Analog models and tuning | Establish a measured full-layout 400 MHz bracket in every corner, then qualify tuning/detector models and numerical uncertainty. |
| Digital timing and CDC | Complete routed reset pulse/recovery/removal coverage and physical interface constraints. Unreported checks and structural classifications are not passes or waivers. |
| Closed-loop operation | Pass all 60 active-profile cases with actual RTL and qualified analog models, including acquisition, sustained frequency/phase, no slips and code limits. |
| Reproducible handoff | Pin and independently verify the final selected views, models, calibration, constraints and completed gate receipts. Development snapshots alone do not qualify a handoff. |

The [corrected full-layout TT collection](selected_keeper_corrected_BSIM_TT_collection_1351_completed.json)
measures 365.579–379.312 MHz at coarse20 and does not bracket400 MHz.
The [fast coarse23/fine149 pilot](static_coarse23_DCO_1541/assessment.json)
measures404.097 MHz in19.2 minutes, but remains an unqualified subsystem point.
At coarse20, the [reset-aligned comparison](static_reset_aligned_1540/assessment.json)
shows roughly+1,531 ppm discrepancy. The
[0/32 fF receiver-load comparison](static_load_pair_1538/assessment.json)
changes frequency by only0.0031 ppm and does not explain that discrepancy.
The [omitted-aggressor ranking](omitted_capacitive_drives_1543/assessment.json)
identifies dynamic exterior coupling, including REFCLK, that the static model
grounds. These diagnostics do not supply a transferable correction or error bound.

The [completed analytic REFCLK case](static_REFCLK_DCO_1544/assessment.json)
changes frequency by only+1.019906 ppm versus the grounded-REFCLK pilot.
The [current source-binding audit](mixed_signal_RTL_binding_1547/assessment.json)
verifies all nine portable mixed-signal RTL files against the selected route's
exact bytes. Five source/geometry/cache rejection tests pass. The digital
controller is actual selected RTL; analog frequency, detector and clock-timing
models remain separate unqualified diagnostic inputs.

The [completed coarse23/fine8 point](static_coarse23_fine8_DCO_1545/assessment.json)
measures376.003 MHz; together with fine149 at404.097 MHz it brackets400 MHz
inside the unqualified fast subsystem. This is not a full-layout bracket.
The current numerical work replays measured programming-input ripple and
continues the existing full-layout references and boundary replay. Their results
must be completed and hash-verified before selecting a calibration or correcting
a model. The full-reference and reduced-model routes are both retained; the
faster route is not substituted for release evidence.

## Programming and integration

`IntegerPLL_400MHz_PrototypeTop` combines the programmed digital core with the
existing DCO and BBPD. Build physical views with `USE_POWER_PINS`. Compile the
explicit digital sources in `rtl/prototype400/sources.json`, plus
`IntegerPLL_ProgrammedStartup.v` and `IntegerPLL_ProgrammedCore.v`; do not compile
the duplicate historical modules from `rtl/` into the same design.

Supply STARTUP_COARSE (0–47), STARTUP_FINE (8–247), STARTUP_INCREASING (the measured
frequency/code direction), nonzero KI, and KP (zero is allowed). Keep all programming inputs and
gains stable from before reset release until the next reset. REFCLK must run
during startup. Hardware captures the configuration, holds the oscillator reset
for two reference periods after capture, then uses a separately decoded seed to
bootstrap the stopped clock. Both destination-domain handshakes must load the
seed before CONFIG_READY asserts. During tracking the existing registered
thermometer controls drive the DCO; startup does not introduce a combinational
decoder into the tracking tuning path.

With PLL_ENABLE=0 the oscillator runs at the preset for bench frequency
measurement. Enabling starts the fine loop. Disabling withdraws tracking and
restores the preset; enabling again reloads the seed before tracking resumes.
Reset is mandatory before changing programming inputs. An invalid or changed
configuration, or 512 unsuccessful reference cycles waiting for tuning, produces
a sticky FAILED condition and stops the oscillator until reset.

TRACKING means the fine loop is enabled, not that frequency/phase lock has been
verified. Consumers must treat the clock as invalid during reset, programming,
disable transitions and acquisition. External measurement selects a startup band
and seed for each device; no automatic process-corner identification is assumed.
The integrator must honor the final characterized clock load, supply, reset and
input timing limits. These remain unqualified until final-assembly checks pass.

## Verification entry points

Run these inside `build/apptainer/openpll-release-modern.sif`, binding `/home`
and `/tmp` to themselves, and the workspace to `/work/OpenPLL` for historical
characterization receipts, with the existing numeric Python interpreter:

```sh
build/timing400/numeric_tools_002/bin/python -m unittest discover -s verification/prototype400 -p 'test_*.py' -v
build/timing400/numeric_tools_002/bin/python verification/prototype400/run_digital_v3.py --output FRESH_DIRECTORY --synthesize
```

`run_digital.py` creates the independent full-cell mapping; `run_digital_v3.py`
creates the restricted mapping with physical tie cells. `check_mapping.py`
compares their complete paired-state data, clock, asynchronous-control and output
functions, including a corruption control. `build_placement.py` and
`build_route_v3.py` build a fresh digital layout. `continue_physical.py` waits for
that route and runs routed equivalence, streamed-GDS DRC/LVS, antenna and power
connectivity checks. The placement constraints deliberately serve only as a
supplied-TT25, 500 MHz capacity screen; they cannot qualify five-corner timing,
reset recovery/removal or cross-domain payload bounds.

`run_loop.py --models MANIFEST --output FRESH_DIRECTORY --ki KI --kp KP` runs one
corner's three startup/recovery scenarios at four reference phases. Every segment
must satisfy the unchanged 200 µs acquisition, 1000 ppm frequency and sustained
phase/cycle-slip criteria. Across five corners this is 60 inexpensive model-based
scenarios, not 60 extracted full-circuit SPICE runs. Unknown frequency-table
lookups stop the clock driver. Trace passes alone cannot qualify a handoff.

The model manifest pins the profile, current source identities, final physical
candidate identities, frequency table, detector-model RTL, and their respective
qualification receipts. A physical receipt must match the candidate and corner,
pin its inputs and artifacts, and cover the actual model artifact. The detector
model implements `Prototype400DetectorModel(REFCLK, FEEDBACKCLK, RESET_N, BBPD)`.
Synthetic manifests require `--diagnostic`, and cannot produce a qualification
pass. `--phase-zero-only` is also diagnostic-only.

## Remaining qualification

The new digital layout must be assembled with the DCO and BBPD before extracting
final parent loading and physical interface behavior. The historical 80 ns KLU
result remains diagnostic evidence for its original candidate, not a qualified
model for this assembly. No long native run should be launched using the old
hard-coded deck merely to fill the queue.

For each corner, find a measured 400 MHz bracket, resolve the local seed and
adjacent codes, and perform independent timestep/tolerance checks. Extend the
80 ns baseline only when settling requires it; model uncertainty must resolve
100 ppm and a quarter of the measured local LSB. Measure additional codes when
required by a qualifying trajectory. Retain all signed extracted capacitances
and the KLU full-equation residual limit of 1e-12. Each expensive native check
has 48 hours total, including preparation and assessment, one large case at a
time, with no automatic identical retry. A timeout is inconclusive.

Qualify the five corners' actual timing, reset/CDC/interface bounds and loop
models; select one KI/KP pair passing every case. Begin with KI=4/KP=0 and then
search KI={1,2,4,8,16}, KP={0,1,2,4,8}, selecting the lowest passing KI then KP.
Finally close assembled DRC/LVS/antenna/density/power integrity and package
matching GDS, LEF, netlists, extraction, constraints, model evidence and bench
instructions. `prototype_handoff_qualified` stays false until all these gates
have direct, matching evidence. Broader release qualification stays false.

## Parent assembly continuation

`build_assembly_frame.py` audits all 686 original macro-pin connections.
`build_parent_power.py` connects existing GDS power-port shapes through external
trunks and checks their metal clearance. `protect_parent_antennas_v2.py` adds
four diodes and one local tap per measured failing parent net.
`route_parent_v6.py` includes lower-metal blockages around the digital macro;
its binding check includes every protection-cell pin. `check_parent_layout.py`
streams all three exact source GDS files, verifies duplicate definitions and
preserved macro geometry, then runs full Magic DRC and transistor-level LVS.

`check_parent_geometry.py` measures three raw parent-wire RC views, conservative
antenna formation stages, the native PDK antenna method, and stock density.
These are separate checks: a zero native density exit status does not imply
passing density limits. `localize_parent_antennas.py` maps actual failing
formation-stage components back to macro ports. `add_targeted_parent_banks.py`
adds protection on existing power rails and freezes unaffected signal routes.
The first targeted candidate retained 359 background routes while repairing ten
nets. Full LVS localized one coarse/fine short; `repair_targeted_short.py`
releases that additional coarse route and retains the other 358 routes.
`audit_targeted_route.py` independently checks the retained geometry and accepts
only the explicit PG SPECIAL tags added by full DEF import. Earlier nonpassing
candidates and logs remain retained.

`continue_targeted_parent_v2.py` runs the next physical checks without retrying a
failed candidate. Shared status updates use `status_store.py` with a file lock;
a four-process regression verifies that concurrent reporters retain all fields.
`fill_parent_v5.py` requires DRC/LVS and both antenna methods
to pass before generating fill. It preserves all original drawing geometry and
labels, and adds only the eight PDK fill purposes; metal5 gets a separate
clearance and density-window preflight. `continue_filled_parent_v2.py` then checks
the actual filled GDS, including independent macro-port topology and arithmetic
recomputation of the PDK density report. `check_parent_layout_v2.py` audits any
supplied fill-only GDS against the unfilled route before checking it.

`extract_filled_loading_v4.py` is preparation after passing filled geometry: it
preserves floating nodes and signed capacitances in a separate flat extraction
view with explicit metal/poly fill. It does **not** establish complete finite-R
or FOM/substrate coverage. Its output cannot satisfy `run_native.py`'s final
physical-domain prerequisite by itself. The matching complete domain, native
variable-map and solver-control receipts must be constructed and checked before
any long qualification transient is started. Five-corner timing, physical lock,
power integrity, and final reproducible handoff remain mandatory open gates.

`trace_filled_domain_v2.py` follows the checked fill-aware loading extraction with
retained native wire-resistance/device-domain tracing. It saves both the
pre-resistance capacitance export and the native RC export, plus creation,
segment, binding and device records. It uses exclusive native admission,
40 GiB available-memory admission, a 48 GiB address-space cap, and one total
12h CAD budget including waiting. It does not assert a complete physical domain:
signed-C attachment, substrate/FOM coverage and native numerical controls still
need matching reconciliation before qualification transients are eligible.

The current passing physical receipt is `filled_closure_005/assessment.json`
under the prototype build root: full DRC0, unique LVS, both antenna methods0,
175 density checks and 744 macro-port probes. `finish_filled_geometry.py`
reuses completed native checks and finishes the independent audits.
`extract_filled_loading_v4.py` verifies all 65 external boundary points and
labels supplies/inputs at their physical parent ports before finite-R tracing.
`index_filled_domain_v2.py` resolves captured node lifetimes;
`trace_filled_capacitance_v2.py` compares traced/untraced native C and device
cards before compiling owned signed charge operators. These model workers keep
their original 12h deadlines when a prerequisite is corrected; waiting and
assessment do not start a new budget. No physical lock case has passed yet.

The serial owned-C compilation in `filled_capacitance_004` exhausted its budget
after 292,020,000 kernels. Its native extraction and all partial outputs remain
retained. `compile_capacitance_parallel.py` reuses that completed extraction
with the changed four-process compiler (`compile_local_C_operators_v6.py`).
It starts a separate, explicit 12h whole-check budget for this changed algorithm,
including input verification, indexing, compilation, merging and hashing.
`parallel_C_trace_ranges.py` aligns four byte ranges across kernel, owner,
surface and native-contribution streams, retaining original kernel/event IDs.
Workers have separate outputs/status/receipts and a shared deadline; the
controller terminates workers on failure or budget exhaustion. Aggregate worker
RSS is limited to 40 GiB and available host RAM must remain at least 4 GiB.

The result is `operators_manifest.json`, an ordered set of operator shards
with explicit local-to-global field maps. Consumers must apply those maps;
plain concatenation of local field IDs is invalid. The merged ledger is in
global field numbering; tiny floating-point differences from serial summation
are expected. `test_parallel_capacitance.py` compares actual four-process output
against v5 for all supported kernel kinds, omitted self pairs, multiple events,
global record IDs and ledger values, and rejects corrupt event alignment.
Successful compilation still does not qualify global passivity, FOM/substrate
coverage, R-domain attachment, physical lock, timing, power or release readiness.


The retained `filled_domain_index_005` receipt exposes a record-conservation
failure: 639,629 native TILE snapshots became 496,441 indexed domains and
914,860 CONTACT snapshots became 557,474 indexed contacts. Its v3 implementation
keyed snapshots by conductor name, overwriting earlier groups with that name.
It must not be used as complete full-assembly coverage. The v4 indexer preserves
native group IDs on every row, retains repeated conductor names in separate
private-node namespaces, and requires exact GROUP/TILE/CONTACT/BIND/SINGLE
record conservation. This changed algorithm has a fresh explicit 12-hour budget;
it does not relabel old results. Regression controls exercise repeated names,
reused native pointers and an unclosed snapshot. Preserving all groups still
leaves physical overlap, contact impedance and C attachment to qualify.


The v4 output is a complete **raw snapshot index**, not a declaration that all
native groups coexist in the final electrical topology. A direct retained-trace
scan confirms 18,414 groups with 18,043 conductor labels (371 repeated labels).
Repeated extraction lifetimes may overlap physically. Their final-export
membership and tile/contact consistency must be reconciled before attachment;
blind inclusion could double-count loading. `verification/signoff400/audit_native_groups.py`
compares exact printed-node/incident-edge fingerprints independently of native
pointers and group IDs. Equal fingerprints qualify only that diagnostic and
never waive domain reconciliation or select a group automatically.


The later compiled native-export reconciliation refines the raw-count finding:
`build/signoff400/native_r_export_001` and
`native_r_last_group_check_001.json` show that all 18,043 last groups reproduce
the printed node name/coordinate and resistor cards in the final `.res.ext`,
with 999,187 selected nodes. Thus raw snapshot attrition alone is not evidence
that final printed electrical nodes were omitted. The v4 index preserves full
history for explicit selection/coverage audits; raw snapshots must not all be
included as simultaneous physical domains. Of 371 repeated conductor labels,
71 have multiple matching printed snapshots. Matching printed cards does not
qualify capacitance, device bindings, contact impedance or tile-voltage coverage.
The original v3 index and the complete v4 raw index both remain unqualified as
runtime models until those physical-domain checks pass.

Keeper stream-out diagnosis (1100): the 1096 RenameCell export retained empty HS inverter cells. Replaying only stream-out with OverwriteCell restores source geometry on every source GDS layer; the eight LI polygons below 0.056 square micrometres disappear after merging with the restored cell. This does not qualify DRC, LVS, power connectivity, or analog behavior. See `selected_keeper_streamout_diagnosis.json` and `../signoff400/diagnose_selected_keeper_streamout.py`. The separate 1097 wider-grid route still reports disconnected power rails; neither candidate is selected.

Keeper PDN-only replay (1101): restoring met4 width/spacing to 1.6/1.7 micrometres eliminates all missing-via warnings. PSM reports only eight unconnected instance pins: VGND and VNB on each of the four HS inverter macros. The prior 0.48 micrometre met4 width cannot enclose via4 (0.8 cut plus 0.19 enclosure on each side). Local macro ground access remains to be implemented and verified. No physical qualification is claimed. See `selected_keeper_pdn_baseline_probe.json`.

Keeper local ground access (1102–1104): extend each HS inverter met1 ground rail to x=4.5 micrometres and reserve a 4.8 micrometre-wide macro. The added metal area is 1.4994 square micrometres per cell; the first helper incorrectly reported zero due to a live KLayout region and is superseded by v2. Independent layer comparison confirms that the corrected geometry matches the PDN-tested geometry on all 22 layers. The 1102 PDN check reports no missing vias, disconnected shapes, or disconnected instance pins. Full route 1104 uses the corrected helper, original legal 1.6/1.7 micrometre met4 width/spacing, and OverwriteCell stream-out. DRC/LVS, well/tap coverage, new parasitics, timing corners, and analog behavior remain unqualified. See `selected_keeper_ground_access_PDN.json`.

HS macro well/tap check (1105/1106): standalone Magic `drc(full)` confirms that the inverter with ground extension but no tap violates nwell.4, LU.3, and LU.2. Adding the matching HS tapvpwrvgnd_1 cell at (1.44, 0) micrometres, within the existing 4.8 micrometre reservation, removes all standalone Magic full DRC errors. The v3 generator includes the tap geometry and extends the power abstract over its rail. This is a local macro check; full routed DRC/LVS, HD cut-row tap coverage, connectivity, parasitics, and analog validation remain pending. See `selected_keeper_tapped_macro_check.json`.

Tapped keeper integration preflight (1107): matching HS taps and HD tap-cell row endcaps pass PDN connectivity with no missing vias, disconnected shapes, or disconnected instance pins. The v8 preflight manifest inherited an incorrect only-met1-change flag; the pinned geometry receipt records the HS tap and v9 corrects that metadata. Full route 1108 is queued behind 1104 and requires the verified passing 1107 receipt before running. Physical DRC/LVS and analog qualification remain pending. See `selected_keeper_tapped_PDN.json`.

Tapped macro electrical topology check (1110): Magic extraction and Netgen against the HS inverter CDL match uniquely with the routed VNB=VGND and VPB=VPWR bindings. The checker verifies these ties on all four 1107 powered-netlist instances before constructing the reference wrapper; CDL device names are normalized to the PDK primitive names without changing dimensions or multiplicity. This is standalone supply-tied macro LVS, not full routed LVS or parasitic qualification. See `selected_keeper_tapped_macro_LVS.json` and `../signoff400/check_selected_keeper_macro_lvs.py`.

Keeper physical audit (1111): the completed untapped 1104 route is correctly rejected for extraction. Its power-grid, detailed routing, KLayout DRC, antenna metrics, and exported macro geometry pass; Magic reports 50 errors and native LVS fails. Detailed LVS shows four isolated HS body nets and one HD well fragment, consistent with the tap changes in the running 1108 candidate. The auditor requires terminal ownership, unchanged pinned inputs, explicit zero metrics, a unique LVS match without record discrepancies, and matching nonempty macro geometry before setting extraction_allowed. Candidate timing corners, full-parent integration, and analog behavior remain separate unqualified work. See `selected_keeper_physical_audit_negative.json`.

Keeper extraction handoff (1112/1113): the guarded extraction runner rejects the known failed 1104 audit before creating output or launching Magic. A 24-hour bounded follow-up waits for the original 1108 route owner to exit, audits terminal results, and allows one stock hierarchical capacitance extraction only after all physical checks pass. Extraction retains its 12-hour child bound and 1-core/16-GiB lease. Failure leaves the original route and receipts intact, with no identical retry. Capacitance completion alone will not qualify distributed resistance, parent loading, extracted transient behavior, or release readiness. See `selected_keeper_extraction_followup.json`.

Tapped route 1108 has zero Magic/KLayout DRC, power-grid, routing, and antenna violations, but native LVS still fails. Follow-up 1113 correctly stops before capacitance extraction. Diagnosis 1114 replays only extraction/LVS from the same completed GDS, expanding HS transistors and explicitly loading normalized HS CDL. This restores the six-pin HS interface; its extracted definition contains R0 VPB VPWR 0 and R1 VNB VGND 0. Parent-level propagation of these exact aliases remains unresolved in LVS, including two residual body nodes after flattening. No waiver, geometry change, or extraction approval is inferred from this diagnosis. See `selected_keeper_GDS_LVS_replay.json`.

Keeper exact-alias LVS (1115–1118): the first replay omitted Netgen setup environment and is invalid. Corrected v2 pins and restores the original environment and rejects setup/runtime errors. The GDS-extracted R0 VPB–VPWR=0 and R1 VNB–VGND=0 connections justify parent alias propagation and expansion of exactly four HS instances into their unchanged 16 MOS cards. The normalized LVS matches uniquely with all records free of connectivity/property discrepancies. Controls reject nonzero resistance and a missing ground alias. Consolidated audit 1117 verifies the same GDS hash and all other physical checks, preserves the failed original LVS diagnostics, and permits extraction. One bounded capacitance extraction (1118) is now launched; no selected design change or analog qualification is implied. See `selected_keeper_body_alias_LVS.json` and `selected_keeper_physical_with_normalized_LVS.json`.

Keeper capacitance extraction (1118) completed normally and passed native receipt/artifact verification inside the pinned image. Expanded inventory has 4096 MOS devices plus two poly resistors, including eight LVT NFET and eight PFET devices from the four HS inverters. The network has 20,266 nonzero capacitor pairs, including 26 signed negative entries; network passivity still needs qualification, so these entries are not independently interpreted as a pass/fail result. New-route wire resistance, parent loading, and native analog behavior remain incomplete. See `selected_keeper_capacitance.json`.

Keeper passive-capacitance and wire-RC preparation (1119/1120): the unchanged signed capacitor network passes exact passivity certification after restricting all exposed supply/body rails to ideal constant voltages. This projected network has 17,472 positive pairs and no negative pairs. The full unrestricted network remains uncertified. Completed RCX views from the same audited route were collected without rerunning extraction: nominal/min/max each have 364 nets and 1,826 terminals, with 2,532/2,525/2,821 positive wire resistors. All SPEFs exclude cell pin capacitance. Physical instance/pin binding and combination with the full capacitor network remain pending; SPEF capacitors must not simply be added to the full Magic C network. See `selected_keeper_capacitance_passivity.json` and `selected_keeper_wire_RC.json`.

Keeper physical binding/model assembly (1121/1122): independently measured 0.005 micrometre Magic grid matches all 2,130 routed/extracted cell placements. Nominal/min/max SPEF binding covers all 364 networks and 1,826 terminals without failures. Six full-C/wire-R diagnostic variants (three RC corners times driver/farthest C attachment) retain 4,098 primitives and all 20,266 capacitor pairs, rewire 1,522 cell pins, and verify exact device topology and capacitor operator recovery after zeroing wire R. SPEF capacitance is not added. Each emitted network passes ideal-supply passivity certification. Spatial C placement, attachment uncertainty, parent loading, cell-internal wire resistance, and native transient qualification remain open. See `selected_keeper_wire_binding.json` and `selected_keeper_RC_models.json`.

Keeper native attachment comparison (1123): launched two serial Xyce reset-start diagnostics for nominal driver/farthest full-C wire-R models at TT/27 C/1.8 V, coarse 20/fine 112, inverted thermometer, normal DC initialization, reset release 5 ns, horizon 80 ns, maximum step 10 ps. The runner pins its complete static PDK include superset inside the container, preserves every capacitor card, shares literal primitive calls through independently reviewed templates, and applies the existing scoped poly-resistor adapter. Each native case has a 3-hour cap, one CPU, and a 12-GiB lease; no identical retry is authorized. Frequencies are assessed only after normal full-horizon completion. Parent loading and model-family qualification remain incomplete. See `selected_keeper_native_attachment_pair.json`.

Keeper parent integration candidate (1124–1126): macro size, origin, all 308 pins, every signal-pin PORT shape, and all original power-pin PORT shapes are preserved. Four input antenna-area annotations increase and additional power accesses are exposed, so exact LEF equality does not hold. Isolated assembly 1125 replaces only the DCO definition at its original parent placement, preserves 86 other original cell definitions through GDS serialization, and verifies the new DCO recursive polygon geometry against its source. The modified HS inverter receives a private cell name to preserve the stock HS inverter used elsewhere in the parent. A fresh full flattened Magic DRC check (1126) is launched. Parent LVS, antenna, density, power connectivity, extraction, timing, and analog behavior remain unqualified. See `selected_keeper_macro_interface.json` and `selected_keeper_parent_assembly.json`.

Keeper parent fill diagnosis (1126–1130): the first assembled parent has 50,193 flattened Magic DRC rectangles, concentrated inside the newly routed DCO. Its retained global density fill was generated around the old DCO; the fill includes diffusion/poly/LI/metal datatype-99 patterns over the parent area. A separate candidate removes exactly the old global density-fill and metal5-fill instances while retaining all macro definitions and all other parent instances. Fresh flattened DRC 1130 is running to test the collision hypothesis. This unfilled diagnostic requires regenerated density fill and all parent checks; it is not a release candidate. Initial LVS preparation 1127 stopped before native extraction because the original recipe uses a relative feedback path. See `selected_keeper_parent_DRC_with_old_fill.json` and `selected_keeper_parent_fill_diagnosis.json`.

Keeper parent-route reuse rejected (1130–1133): removal of stale fill reduces flattened Magic DRC from 50,193 to zero rectangles. Regenerated fill 1132 preserves active geometry and is only a diagnostic candidate. Fresh parent extraction and LVS show all three macros individually match; propagating the extracted digital R0 TRACKING–BBPD_RESET_N=0 connection resolves the familiar alias mismatch. The remaining parent comparison exposes shorts between DCO_THERM[91]/[97] and [93]/[96]. Thus unchanged pin shapes and clean DRC do not justify parent route reuse after changing DCO internal routing. A fresh parent route with the new macro obstruction/power geometry is required before repeating filled parent checks or parent model qualification. The failed LVS and generated fill remain retained without promotion.

Keeper fresh parent route (1135/1136): native parent contacts, buffered logical composition, macro positions, and existing power contacts are retained, while 15,062 conservative global obstructions cover all keeper DCO conductor/cut geometry absent from the original abstract. Both main-rail database checks pass. A namespace-safe DCO subtree is exported for subsequent parent streaming. The original buffered-parent router is now rerunning global/detail routing from this updated protected database; no old signal route is reused. Fresh assembled DRC/LVS and subsequent fill/antenna/density/power/model checks remain mandatory. The native abstract retains its original gate-area annotations, so this routing preparation does not qualify updated input loading or timing. See `selected_keeper_parent_routing_geometry.json`.

Fresh keeper parent validation (1136–1143): the new parent route completes with zero router DRC and connected main rails. Stream 1137 verifies all three source macro geometries/labels and placements. Fresh flattened Magic DRC 1140 reports zero rectangles. Expanded parent LVS 1142 matches uniquely after the existing proven digital zero-ohm alias propagation; all records are free of connectivity/property discrepancies, and the previous DCO control-net shorts are absent. Initial host-side checks 1138/1139 stopped before native work on container-only tool paths; v4 performs verification and native work in the pinned image. Fresh fill 1143 is launched only after this same-GDS DRC/LVS pair passes; filled-layout checks, antenna, density, power, updated timing/loading, and parent analog models remain unqualified. The public routing-preparation receipt now retains hashes/counts for the large buffered pin lists; its complete native receipt remains pinned.

First completed keeper attachment transient (1123 driver): native Xyce reaches the full 80 ns horizon normally in 1,861.44 seconds with all pinned inputs and waveform/log artifacts verified inside the image. Measured frequency is 389.364320 MHz (20–40 ns), 389.435364 MHz (40–55 ns), and 389.481103 MHz (60–79 ns) at TT/27 C/1.8 V, coarse 20/fine 112. The farthest-attachment case remains running. These are isolated reset-start measurements with incomplete parent loading, not a 400 MHz or lock qualification. See `selected_keeper_native_attachment_pair.json`.

Filled keeper parent checks (1143–1148): regenerated fill retains the fresh-route geometry and labels. Flattened Magic DRC 1144 reports zero rectangles; normalized expanded LVS 1146 matches uniquely with all three macros expanded and no connectivity/property discrepancies. A provenance resolver binds the fill to exactly one checked fresh stream and rejects non-fill geometry changes or a different source GDS. Receipt 1147 binds these actual results to an identical copied GDS for downstream checks; its frame is used only for die/positions, and current macro views come from stream 1137. Stock density checking 1148 is running. Antenna, density, power, updated loading/timing, parent extraction and analog qualification remain open. See `selected_keeper_checked_filled_parent.json`.

Filled keeper density review (1148/1149): the stock wrapper stops explicitly because the 650 by 500 micrometre die is smaller than its 700 micrometre window; native Magic nevertheless completes normally and reports all 80 raw tiles. The existing small-layout reviewer independently weights the clipped edge tiles and finds all seven constrained global layer densities within unchanged stock thresholds: FOM 37.31%, LI1 48.06%, MET1 41.51%, MET2 38.41%, MET3 40.42%, MET4 43.54%, MET5 60.70%. POLY is measured without an invented threshold. The wrapper remains nonpassing/inapplicable, and stepped-window or chip-integration density qualification is not claimed. See `selected_keeper_parent_density_review.json`.

Keeper antenna evidence pipeline (1150/1151): a fresh flattened full-GDS measurement uses the conservative contact engine with its unchanged 26 matched rule controls. The original selected-GDS profile is not transferred to the keeper candidate. A bounded 24-hour follow-up verifies source/native masks and gate area, proves actual contact-mask containment in exported paint, and runs all seven guarded process prefixes in pairs only after zero main feedback and passing geometry/paint checks. The new process auditor binds the exact native parent receipt and its MOS inventory, replacing the original selected-GDS path/count constants without weakening geometric/component guards. All candidate/profile qualification flags remain false pending completed evidence and a candidate-specific profile. See `selected_keeper_antenna_queue.json`.

Initial keeper antenna measurements (1150/1151): the controlled conservative engine completes with zero feedback. Independent comparison preserves all 16 source masks and matches extracted MOS gate area to the source poly/diff intersection; all six actual contact masks lie within exported paint. Native MOS count is 61,504: original 61,616 plus 40 keeper/inverter MOS minus 152 MOS from replacing 76 two-MOS HD decap_3 row endcaps with well taps. This physical inventory change is accounted for; supply decoupling/power behavior is not inherited from the original layout. Seven process-prefix checks remain running, and candidate-specific antenna qualification is still false. See `selected_keeper_conservative_antenna.json`, `selected_keeper_antenna_geometry.json`, and `selected_keeper_contact_paint.json`.

Full keeper parent capacitance extraction (1152): started one stock hierarchical extraction from the exact DRC/LVS-checked filled GDS 1147, with the input receipt and matched LVS binding verified inside the pinned image. The job has a 24-hour cap, one CPU (23), and a 16-GiB lease; its native child is independently bounded and is not automatically retried. Full parent/interface coupling is being collected; isolation/binding, signed-capacitance review, passivity, new-route wire resistance, and native model correlation are still required. See `selected_keeper_full_parent_capacitance_queue.json`.

Fresh keeper parent wire extraction (1153): min/nom/max RCX completes from the exact rerouted database behind checked filled parent 1147. Inside-image verification confirms all pinned inputs and artifacts. Each view covers 973 signal nets and 2,547 resistively connected terminals; positive wire resistor counts are 3,326/3,557/3,766. PIN_CAP NONE excludes cell pin capacitance. Native macro-port binding and combination with full parent capacitance remain pending. SPEF capacitance must not be added again to the full Magic capacitor network. See `selected_keeper_parent_wire_RC.json`.

Keeper parent wire binding (1154): all 2,097 routed instances match independent extracted placement, including all three macros. All 973 wire networks bind and connect without failures in each RC corner. The hierarchy is the exact filled-GDS native extraction with body aliases and the independently proved digital TRACKING/BBPD_RESET_N zero-resistance alias; all three macros passed expanded LVS. Full parent capacitance remains separately extracting, and model combination/parent loading is not qualified. See `selected_keeper_parent_wire_binding.json`.

Completed keeper attachment diagnostic (1123): both cases reach 80 ns normally, with both native input/artifact receipts verified inside the pinned image. Driver/farthest final 60–79 ns frequencies are 389.481103/486.478274 MHz (96.997171 MHz difference); elapsed native times are 1,861.44/2,454.43 seconds. This large sensitivity prevents calibration/model-family qualification. These two artificial C attachment choices do not establish a physical uncertainty bound; physically justified capacitance placement and cell/internal wire treatment must be resolved before using this model for release correlation. Parent loading is still incomplete. See `selected_keeper_native_attachment_pair.json`.

Keeper C locality audit (1155): all source, wire, binding, model, and lift receipts are verified before analysis. Of 1,522 child-cell pin capacitance endpoints, conductor-wide driver attachment relocates 1,461 and farthest attachment relocates 1,159 away from their actual rewired cell terminal. Incident capacitance is counted per pin, not as a network total. Exact zero-wire-R recovery therefore does not establish correct finite-R dynamics. A replacement must expand child capacitance using actual rewired pin bindings before aggregation, while resolving root/interconnect capacitance separately without adding duplicate SPEF capacitance. Neither existing attachment variant is qualified. See `selected_keeper_C_locality.json`.

Local-cell capacitance reconstruction (1156/1157): v6 expands child capacitors at actual rewired terminals before aggregation, retaining driver/farthest diagnostics only for root interconnect contributions. All six models recover exact original device topology and C operator under zero wire R, and no SPEF C is added. All six fail the current sufficient ideal-supply passivity certificate; this is not proof that the real networks are nonpassive. Their signed hierarchical compensation requires stronger certification or a spatial extraction that preserves the physical compensation structure. First runner 1156 stopped at its certificate guard; v2 1157 preserves all model/lift/proof artifacts for diagnosis and allows no native simulation. Two regression controls verify receiver-local capacitance and a fixture where separating compensation produces negative energy. These models remain unqualified. See `selected_keeper_local_C_models.json`.

Exact local-C principal energy audit (1158): independently rebuilds the fixed-rail projected operator from each emitted model and checks one- and two-node voltage candidates using exact rational arithmetic. No negative witness is found for any of the six models. This rules out these particular small-support counterexamples only; neither passivity nor indefiniteness is proved. Four controls cover a negative diagonal, an indefinite two-node block with positive diagonals, a passive example, and an explicitly inconclusive result. Broader coupled-node analysis remains necessary before native simulation. See `selected_keeper_local_C_energy.json`.

Exact sparse local-C elimination (1159/1160): five controls pass, including a negative-energy three-node mode with positive two-node principal blocks. Initial 120-second audit reaches its computation bound but loses serialization to the decimal integer digit limit; its terminal status records no certificate. Version 2 serializes elimination rows as exact hexadecimal numerator/denominator pairs and retains a bounded nominal-driver elimination receipt. The 15-second run remains inconclusive; partial positive pivots do not certify the remaining matrix. No model is changed or enabled for native simulation. Full source/operator dependencies and retained elimination history are hashed. See `selected_keeper_exact_C.json`.

Exact GMP local-C certificate (1161/1163): nominal-driver exact rational sparse LDL eliminates all 4,346 dynamic nodes with nonnegative pivots and zero residual rows, certifying positive semidefiniteness under the explicit ideal constant supply assumption. Five native controls pass, including singular PSD, higher-order indefiniteness, zero-diagonal coupling, exact fractional coefficients, and bounded inconclusive behavior. This stronger certificate resolves the inconclusive sufficient path test for this operator only; physical C placement, parent loading and model-family correlation remain open. The remaining five variants are running serially with 120-second computation bounds and 1-core/8-GiB leases; the completed nominal-driver case is not rerun. See `selected_keeper_GMP_C.json`.

Completed full keeper parent C (1152/1162): extraction and receipt/artifact hashes verify inside the pinned image. Exact hierarchy expansion retains 62,338 primitive calls, 985,673 capacitor cards and nine zero-resistance aliases; aggregation has 344,029 nonzero pairs, including 3,306 signed negative pairs. Negative entries alone are not a passivity failure. The full parent operator still requires alias/interface binding, supply projection/passivity qualification, and combination with the new route R without duplicate C. See `selected_keeper_full_parent_capacitance.json` and `selected_keeper_parent_C_inventory.json`.

Completed keeper antenna process audit (1151): native follow-up and all referenced stage artifacts verify inside the pinned image. Every one of seven process prefixes has 61,504 MOS devices and zero conservative feedback; independent stage component guards, source/native masks and gate area, and actual-contact paint containment pass. This is completed exact-candidate evidence, not yet a registered candidate-specific antenna profile/component qualification. The original selected-GDS profile remains unchanged. See `selected_keeper_antenna_complete.json`.

Full-parent C/wire binding (1164): all 973 networks in each min/nom/max route-R view bind directly to the completed full-parent capacitance hierarchy with no failures. Source receipts require the same checked filled layout and LVS proof, and the independent placement join is retained. This establishes terminal/conductor identity only; no C is relocated, no wire R is inserted, and parent-loaded analog model/passivity qualification is still pending. See `selected_keeper_parent_C_wire_binding.json`.

Keeper antenna component qualification (1165/1166): a separate keeper profile binds filled GDS de16c76e… and the measured 61,504 MOS inventory; the original selected profile is unchanged. The qualifier retains all seven tool/rule/diode/geometry/contact/process guards, validates the same DRC/LVS-checked layout, and limits qualification to antenna for these exact bytes. Antenna geometry does not require a claim of full RTL equivalence; RTL binding, selection, other physical components and complete release remain explicitly unqualified. Four negative controls reject the original GDS hash, wrong MOS inventory, nonzero native feedback, and a missing process-component guard. See `selected_keeper_antenna_component.json` and `tools/magic_antenna/keeper_profile_v1.json`.

Completed exact local-C family certification (1163/1168/1169): all remaining five GMP congruence checks complete with zero residual nodes; together with 1161 all six unchanged model operators are PSD under fixed supplies. The acceptance wrapper independently matches each certificate to one exact model and retains the failed path-certificate history. It permits isolated native diagnostics only, not physical/model-family qualification. A fresh serial native pair 1169 is launched with the same pinned reset/TT/coarse20/fine112 conditions as 1123, now preserving child-cell C locality. Each case retains the existing 3-hour, 1-core/12-GiB bound and no retry; parent loading remains absent. See `selected_keeper_exact_C_models.json`.

Full-parent fixed-rail projection (1167/1170/1171): the isolated-cell helper rejected the valid mixed parent because digital body pins use VGND/VPWR while analog macros expose VNB/VPB. Canonicalizing aliases alone does not merge these distinct external rails and must not be described as a physical short. The final parent-specific projector checks every body/supply conductor belongs to its explicit ideal-voltage rail group, rejects any positive-to-ground alias or undeclared supply conductor, and requires all four top rails exposed. It independently reparses the original full C network and applies an exact fixed-voltage congruence without changing signed entries. The projected parent operator has 329,261 pairs, including 743 signed negative pairs; passivity and nonideal supplies remain unqualified. See `selected_keeper_parent_fixed_C.json`.

Full-parent C energy checks (1172–1174): bounded sufficient positive-path certification completes but does not certify the projected parent; this is not an indefiniteness proof. Exact small-support analysis finds no one/two-node negative witness. The unchanged parent operator is now submitted to the controlled exact GMP congruence engine with a 20-minute computation bound, 1-core/8-GiB lease, bounded native child and no identical retry. A time or resource limit leaves the result inconclusive. Both native model diagnostics and the original full TT case remain independently running. See `selected_keeper_parent_C_paths.json` and `selected_keeper_parent_C_energy.json`.

Parent wire model assembly (1175/1176): the first diagnostic builder correctly stops because two distinct routed nets join through a child zero-resistance alias; globally collapsing that child alias before parent R insertion loses the physical connection location. The v7 helper preserves root conductor identity while retaining child aliases at their actual rewired terminals. Exact zero-wire-R contraction still recovers all original device cards and the complete capacitor operator. A dedicated two-branch child-short control and both existing cell-local C controls pass. Revised bounded 1176 assembly is running for nominal driver/farthest root-C diagnostics, with no SPEF C addition; macro-internal R, physical C location, emitted passivity and native eligibility remain unqualified. The failed 1175 receipt is preserved.

Coalesced parent conductor diagnosis (1176/1177): v7 correctly stops at the same guard because the complete parent C hierarchy already uses TRACKING for both TRACKING and bbpd_reset_n routed networks. No root-level zero-R card distinguishes them. V8 allows a diagnostic representative for such an already coalesced root conductor only when actual zero-R child terminal aliases connect every associated wire graph after rewiring. It rejects a synthetic example with the same root name but no child short. Both driver/farthest positive controls retain exact zero-R device/C recovery and keep physical C placement unqualified. Bounded revised 1177 assembly is running; both earlier stopped runs remain unqualified and retained.

Completed parent-wire diagnostics (1177): both emitted models and all pinned sources verify inside the pinned image. Each retains 62,338 primitives, inserts 3,557 nominal parent wire resistors and rewires 2,484 cell pins. Driver/farthest have 352,298/364,614 nonzero C pairs after local expansion; exact zero-R contraction recovers the original complete 344,029-pair operator and every primitive card. No SPEF C is added. The only coalesced root conductor is TRACKING/bbpd_reset_n, and actual rewired child zero-R connection is proved. Root interconnect C attachment remains diagnostic, macro-internal distributed R is absent, emitted operator passivity is not yet checked, and native simulation/model-family eligibility remains false. All five focused controls pass with v8. See `selected_keeper_parent_wire_models.json`.

Emitted parent C certificates (1178/1179): both nominal driver/farthest emitted parent-wire operators are submitted independently to exact GMP congruence, each with a 20-minute bound and 1-core/8-GiB lease on separate spare cores. Source/artifact checks require complete original parent C, parent wire R, no added SPEF C, and exact zero-R device/C recovery. These checks certify operator energy only if completed; even a pass does not qualify spatial C placement or missing macro-internal R. Original parent operator audit 1174 and native DCO diagnostic 1169 continue independently.

DCO internal-wire binding inside parent (1180): all 2,130 same-route DCO placements join the macro extracted in the full parent using an independently measured 0.005 micrometre grid. Only four exact recorded private HS master names are normalized for matching; actual extracted instance identities and geometry remain unchanged. All 364 networks in each min/nom/max view bind with zero failures to the complete parent DCO hierarchy. This permits subsequent nested wire insertion without substituting the isolated C network or losing parent coupling. No R has yet been inserted at this level, and parent model/loading qualification remains open. See `selected_keeper_parent_DCO_wire_binding.json`.

Exported coupling interface preservation (v9): parent extraction exports 2,854 DCO ports versus 308 in isolation, with 2,547 additional names and the original VGND represented as SUB (explicitly mapped to parent VGND). Flattening can disconnect an exported conductor when its C moves to a routed wire node. V9 retains literal declared ports through explicit zero-R interface bindings and includes them in exact contraction verification; these are diagnostic attachment points, not spatial reconstruction. The exported-TAP control and all five locality/child-alias controls pass. Original v8 parent-wire models and their operator audits remain unchanged and unqualified for native use.

Parent-extracted DCO internal-R diagnostics (1181): both variants retain all 2,854 original macro ports in exact order, including SUB mapped to parent VGND. Each has 4,098 primitive calls, all original 20,266 aggregated C pairs before lifting, 2,532 nominal wire resistors, and 61 explicit zero-R exported-interface bindings. Exact contraction recovers original macro device/C topology; native inputs and emitted artifacts verify inside the pinned image. Parent coupling outside the macro is not substituted by isolated extraction. Full parent composition, emitted passivity, physical C placement and native eligibility remain unqualified. See `selected_keeper_parent_DCO_R_models.json`.

Nested parent/DCO wire composition (1182): v10 explicitly collects positive resistors already present in child models, retains them during parent wire insertion, and verifies their exact values and topology after contracting only the new parent wire R. Negative existing R is rejected. All eight locality, exported-interface, child-alias and nested-resistor controls pass. Bounded composition 1182 substitutes only the 1181 DCO block into the unchanged full-parent hierarchy, verifies every other subcircuit byte-for-byte, requires all 2,532 DCO wire resistors survive, and inserts nominal parent R without adding SPEF C. Global zero-all-inserted-R recovery follows the checked macro interface/C contraction and parent-stage device/C/existing-R contraction. Physical C placement, other macro-internal R, emitted passivity and native eligibility remain open.

Completed nested parent/DCO wire models (1182): both emitted variants and all source/model artifacts verify inside the pinned image. Each retains 62,338 primitive calls, 3,557 parent resistors and all 2,532 DCO internal resistors (6,089 total positive wire resistors). Existing DCO resistor topology and values survive the parent-stage exact contraction; all original parent coupling is retained through the unchanged full interface. Non-DCO subcircuits remain byte-identical during substitution. Per-stage exact device/C contraction and interface preservation establish recovery of the original parent when all inserted wire R is zeroed. BBPD/digital internal R, physical C placement, emitted operator passivity and native correlation remain incomplete; native eligibility stays false. The BBPD source route is the checked `build/timing400/release_001/bbpd_internal_antenna_001/route.odb` whose signoff GDS is pinned by current parent stream 1137. See `selected_keeper_nested_wire_models.json`.

Bounded original parent-C congruence (1174): exact GMP computation stops at its declared 20-minute bound after 17,147 of 19,692 nodes, leaving 2,545. The result is inconclusive: no PSD certificate and no indefiniteness proof. No coefficients change, no native model eligibility follows, and the same run is not retried unchanged. Separate emitted parent-operator audits remain active. See `selected_keeper_parent_GMP_C.json`.

BBPD internal wire extraction (1183–1185): exact route database is bound through its zero-DRC/unique-LVS stream to the BBPD GDS pinned by current parent 1137. Initial strict wire guard 1183 stops on unwired one-terminal nets. V2 explicitly inventories VNB/VPB body BTerms and the unused single-terminal logic0 output; these keep their full extracted capacitance and require no inserted route-wire R. Unwired multi-terminal signals remain rejected. Min/nom/max each has 16 wired nets, 40 connected terminals and 29/30/30 positive wire resistors, with PIN_CAP NONE. A native in-memory fixture joins VPB to VNB and proves the multi-terminal guard rejects it; all original sources/artifacts reverify unchanged. Physical binding and model insertion remain pending. See `selected_keeper_BBPD_wire_RC.json` and `selected_keeper_BBPD_unwired_control.json`.

Parent-extracted BBPD internal R (1186/1187): independent grid/placement join covers all 1,116 BBPD instances. All 16 networks in every RC corner bind without failures to the actual full-parent macro. Both nominal attachment variants preserve the exact 59-port parent interface and SUB-to-parent-VGND binding, retain 1,782 primitive calls, insert 30 positive wire resistors and preserve 11 exported-interface zero-R connections. Exact zero-R device/C recovery and all native input/artifact hashes verify. Parent composition, spatial C, passivity and native eligibility remain open. The unchanged digital macro also has a checked route and existing nominal RC extraction; its internal R remains a separate pending scope. See `selected_keeper_parent_BBPD_wire_binding.json` and `selected_keeper_parent_BBPD_R_models.json`.

Digital internal wire RC (1188–1190): original route preflight detects changed historical resources.py/compiled_charge_v2.py bytes; their exact old source hashes are not present in retained Git history. No archive is claimed. The corrected collector explicitly quarantines only those recorded runtime-helper mismatches, verifies every other historical input and artifact, verifies all unchanged independent signoff hashes including the exact route database/GDS, and binds that GDS to parent stream 1137. It extracts all three corners afresh without reusing the old nominal RC file. Min/nom/max cover 4,071 wired nets and 13,066 connected terminals, with 14,303/14,651/15,336 positive wire resistors and PIN_CAP NONE. Historical runtime provenance remains explicitly incomplete; current physical source identity is independently checked. Binding/model insertion remain open. See `selected_keeper_digital_wire_RC.json`.

Bounded emitted parent-C audits (1178/1179): both exact GMP jobs terminate at their declared 20-minute computation bound. Driver eliminates 18,595 nodes with 2,641 remaining; farthest eliminates 18,362 with 2,872 remaining. Neither passivity nor indefiniteness is proved. All source/model/report hashes verify inside the pinned image. These certificates concern the original parent-wire diagnostic operators, not later nested macro-R models, and confer no native eligibility. No identical repeat is launched. See `selected_keeper_parent_driver_GMP_C.json` and `selected_keeper_parent_farthest_GMP_C.json`.

Completed local-C native driver diagnostic (1169): normal full 80 ns completion in 1,912.68 seconds, with PDK/source and native waveform/log hashes verified inside the image. TT/27 C/1.8 V, coarse20/fine112 final 60–79 ns frequency is 395.941180 MHz, versus 389.481103 MHz for the earlier conductor-wide C driver attachment; earlier windows are 395.816785/395.891043 MHz. The slow drift remains characterized rather than declared settled. Farthest attachment is running, and no new spread or physical uncertainty bound is inferred from its partial RAW. Parent loading and calibration/lock qualification remain open. See `selected_keeper_local_C_native_driver.json`.

Digital internal-wire binding (1191): independent dimension/grid and placement join covers all 11,671 digital macro instances in the parent extraction. Every one of 4,071 wire networks per min/nom/max corner binds with zero failures. The source RC receipt binds the independently checked current GDS/database while retaining the historical runtime-helper provenance limitation from 1190. The extracted macro uses 15,528 ordered ports, with VSS/VDD explicitly bound to parent VGND/VPWR; no analog SUB naming assumption is transferred. Nominal internal-R construction 1192 is running with all exported ports retained. See `selected_keeper_parent_digital_wire_binding.json`.

Completed parent-extracted digital wire models (1192): both variants retain all 15,528 ports and exact VSS/VDD bindings, 49,822 primitive calls, 14,651 positive nominal wire resistors and 3,705 explicit zero-R interface connections. Exact contraction recovers original digital device/C topology; native source and artifact hashes verify inside the image. These are diagnostic conductor-C attachments with spatial placement and passivity unqualified. All three macro internal-R models now exist for subsequent full-parent composition; historical route runtime provenance remains explicitly limited as recorded by 1190. See `selected_keeper_parent_digital_R_models.json`.

All-macro nominal wire composition (1193): v11 accepts a coalesced root conductor only when associated routed networks join through actual child zero-R aliases or retained positive child wire-R paths; MOS conduction or an unrelated resistor is not a conductor join. Zero-only and finite-R witnesses are distinguished in metrics. All ten focused controls pass. Bounded composition replaces exactly the DCO, BBPD and digital subcircuits with their parent-extracted RC variants, checks all port orders and every other subcircuit byte-for-byte, and requires all 17,213 macro wire resistors survive parent R insertion. The nominal driver/farthest models are assembling; standard-cell internal R, spatial C, emitted passivity and native qualification remain unclaimed. Historical digital route runtime-helper provenance remains limited as recorded by 1190.

Completed all-macro wire composition (1193): both variants retain 62,338 primitive calls, 17,213 macro wire resistors and 3,557 parent wire resistors (20,770 total). Every source/model artifact verifies inside the pinned image. The coalesced TRACKING/bbpd_reset_n root conductor now joins through a verified finite digital-wire path, not a claimed zero-R alias. All macro port orders, unchanged other subcircuits and staged exact zero-R device/C/resistor recovery pass. Spatial C, standard-cell internal wire R, emitted passivity and native/model qualification remain false. See `selected_keeper_all_macro_wire_models.json`.

Sparse C energy search: a bounded, diagonally scaled floating shifted-power search proposes integer voltage vectors only. The verifier stamps all unchanged projected source capacitor values with exact fractions; numerical eigen/energy values never constitute a certificate. Four native controls pass: higher-order negative mode with independent exact negative energy, signed PSD case, ground-only degeneracy, and an inconclusive time bound. The all-macro wrapper first checks exact small-support witnesses before invoking search. No nonnegative candidate proves PSD, and intrinsic transistor capacitance is outside this constant-C audit.

Exact all-macro C counterexamples (1194/1195): both constructed constant-C operators are indefinite even under ideal fixed supplies. The exact principal audit finds witnesses before numerical search is needed. Driver sets only __flat_15357 to 1 V and obtains twice-energy -9659/50000000000000000000 J (diagonal -0.19318 fF); nested node maps trace it through DCO __flat_2299 / __wire_409 to coarse_inv_35:Z on disable_drive[35]. Farthest sets only COARSE_CODE[0] to 1 V and obtains -1679639/100000000000000000000 J (-16.79639 fF). All omitted voltages are zero. These exact counterexamples concern the reconstructed extrinsic C operators, not intrinsic BSIM C or a proof of total transistor-circuit instability. They prevent claiming a passive extracted interconnect model; spatial/compensation attachment needs resolution before qualification. Neither model is promoted to native correlation. See `selected_keeper_all_macro_driver_energy.json` and `selected_keeper_all_macro_farthest_energy.json`.

Exact hierarchy compensation trace (1196/1197): independently reconstructs every emitted capacitor pair as child-local C plus lifted parent interaction C, requires exact complete-operator equality, then reproduces the exact witness energy. At the driver witness the 1-V diagonal contribution is +0.91318 fF child-local and -1.10636 fF parent interaction, totaling -0.19318 fF. At the farthest COARSE_CODE[0] witness child-local contribution is zero and parent interaction is -16.79639 fF. All incident signed terms and original/emitted endpoint names are retained and verified. No coefficients are clipped or altered. This localizes the constructed negative energy to signed interaction attachment; it does not establish the physical interpretation of individual extraction correction terms or total transistor-circuit instability. Extraction/de-embedding semantics and compensation placement remain to be resolved. See `selected_keeper_driver_C_compensation.json` and `selected_keeper_farthest_C_compensation.json`.

Native signed flat-export semantics (1198–1200): pinned 8.3.623 source extHierAdjustments subtracts child overlap capacitance; spccapHierVisit compares absolute C to threshold, while flat spccapVisit compares signed C. Magic documents this adjustment and recommends flattened treatment for distributed RC: https://opencircuitdesign.com/magic/commandref/extract.html and https://opencircuitdesign.com/magic/howto.html . Native replay reads existing EXT files through a read-only mount and performs no geometry extraction. Both exports finish; initial reviewer stops only on the documented FLOATING annotation. The corrected reviewer strips that annotation, reuses completed outputs and verifies all original inputs. Default-threshold export has 340,967 positive and no negative cards; signed-threshold export has exactly the same positive operator part and two negative substrate cards (-11.25665 fF at sky130_fd_sc_hs__inv_8_134/A and -4.92586 fF at sky130_fd_sc_hs__inv_8_205/A, both to VGND). Zero-valued printed cards are counted separately. Default export therefore hides signed corrections and is not a qualification fix. Equivalence to the custom hierarchical reconstruction, passivity and native eligibility remain unproved. See `selected_keeper_C_export_semantics.json` and `selected_keeper_native_flat_C_review.json`.

Completed local-C attachment pair (1169): both native cases reach the full 80 ns horizon normally, and waveform/log/source receipts verify inside the image. Driver/farthest final 60–79 ns frequencies are 395.941180/433.902625 MHz, a 37.961445 MHz diagnostic spread; elapsed native times are 1,912.68/2,131.61 seconds. Correct cell-local C placement reduces the former conductor-wide attachment discrepancy but does not resolve root interconnect placement. Two choices are not a proven physical uncertainty bound. Parent loading, settled calibration, PVT family and lock remain unqualified. See `selected_keeper_local_C_native_pair.json`.

Primary-port C comparison (1201): three mathematical restriction controls pass. Both source representations have the same 65 ordered primary ports and 61 non-supply alias groups, but 333 constrained C matrix entries differ after resolving explicit zero-R aliases and holding all other conductor voltages fixed. COARSE_CODE[0] diagonal is 66.47949 fF in the hierarchical reconstruction versus 85.33119 fF in the signed native flat export; RESET_N differs by 28.45707 fF. All difference coefficients are exact rationals and retained. The source naming audit finds no case collisions or duplicate formal ports. This is a constrained operator comparison without intrinsic device C, not a physical error bound or floating-node terminal reduction. The original hierarchy and native flat export must not be substituted as equivalent. See `selected_keeper_primary_C_comparison.json`.

Independent flat-geometry C reference (1202): one bounded extraction starts from the same expanded-DRC/LVS-checked filled GDS, physically flattens its geometry, and extracts capacitance/coupling without wire R. It retains signed output through the diagnostic negative threshold and writes a flat GDS for independent mask verification. The 24-hour, 1-core/16-GiB native child has no automatic retry. Completion alone will not verify source mask preservation, primitive inventory, operator equivalence, passivity or native eligibility; those flags remain false. The existing PLL native run continues independently.

Flat-reference geometry validation (1203–1204): all 16 conductor masks, every primitive model count, all MOS dimensions and total gate area match the checked hierarchical source. The flat geometry has 61,504 MOS and 62,338 primitives; channel area is exactly 11,651.539 square micrometers. Five complete selector masks differ after Magic regeneration, and that raw failure is retained. Differences are absent in the technology-defined checked active domains, including taps, gate/diode variants and marked high-resistance poly; the active diode marker also matches. Four selector-domain controls pass, and both audit source/artifact closures verify inside the image. This supports electrical reference investigation only: the flat GDS is not a fabrication replacement, and device connectivity, capacitance equivalence and model qualification remain separate checks. See `selected_keeper_flat_geometry_audit.json` and `selected_keeper_flat_active_selectors.json`.

Flat-reference device connectivity (1205): the capacitance file remains unchanged; only explicit constant C cards are removed in a separate topology-only copy. The checked powered schematic and native Netgen setup are replayed with the flat extracted top. All comparison records are free of connectivity/property discrepancies and the final circuits match uniquely. Source and artifact closure verify inside the image. This qualifies the device-connectivity comparison only, not capacitance equivalence, distributed-RC placement or native simulation eligibility. See `selected_keeper_flat_C_device_LVS.json`.

Physical flat primary-C comparison (1206): all 65 ordered primary ports and 61 non-supply zero-R alias groups agree. Exact constrained matrices differ in 382 entries between hierarchy reconstruction and physical flat extraction, and 165 between native hierarchical export and physical flat extraction; the prior 333-entry hierarchy/native difference reproduces. Physical flat output contains 341,067 positive, zero negative and 1,023,188 printed-zero C cards. COARSE_CODE[0] diagonal is 95.02577 fF physically flat, 85.33119 fF native hierarchy export and 66.47949 fF hierarchical reconstruction. Four focused controls pass; all source/artifact hashes verify inside the image. This compares extrinsic constant C with every other conductor fixed to zero; it is not a floating-node terminal reduction, device-intrinsic C comparison or physical error bound. Earlier representations cannot be assumed equivalent. No model or release gate is promoted. See `selected_keeper_geometry_primary_C.json`.

Flat native model preparation (1207–1208): the initial literal-template adapter stops on four k-suffixed diffusion geometry values in two MOS calls; its failure is retained. V2 expands those numeric literals and passes five controls, including signed-C rejection, case-collision rejection and nonzero-wire-R rejection. The completed reference preserves all 62,338 primitive calls and all 341,067 nonzero C endpoints/literal coefficients under a reversible conductor-name map. It omits only 1,023,188 exact-zero C cards, shares 433 parameterless literal primitive templates and uses the pinned poly-resistor backend adapter. The constant-C network is positive semidefinite by nonnegative branch energy; this says nothing about transistor stability or distributed-wire-R accuracy. Source/artifact closure verifies. Native execution/correlation remains pending, distributed wire R is absent, and model/release qualification remains false. See `selected_keeper_flat_native_model.json`.

Flat-reference native smoke (1209–1210): the initial runner omits the existing diode backend adapter and reports fatal missing diode model errors; it is explicitly terminated after those errors and its failure receipt is retained. Corrected V2 applies the existing exact ngspice47 geometry conversion and fixed-27-C Xyce diode translation, verifies the pinned foundry model hash and preserves every constant-C card exactly. Existing diode translation and unit-conversion suites pass four tests; an adapter/bias control also passes. One reset-asserted TT 1.8-V operating point is running with a 30-minute cap on CPU 20/16 GiB and no identical retry. This is a parse/DC smoke check only, with no frequency, transient, wire-R or model qualification claim. See `selected_keeper_flat_native_smoke_launch.json`.

Flat-C size audit (1211–1212): all 341,067 nonzero C cards have distinct unordered endpoint pairs, so exact parallel aggregation offers no reduction. The C graph contains 19,696 nodes and every node is already a primitive terminal or primary port; there are zero capacitor-only nodes and zero peelable capacitor-only leaves. Thus floating-capacitor elimination is inapplicable. Native Xyce parse reports 61,504 MOS, 814 diodes, 20 resistors, 35 voltage sources and 205,057 unknowns; parsing succeeds through initialization, while the bounded operating-point check remains running. Graph source closure verifies. This rules out two proposed exact C-only speedups and changes no circuit model. See `selected_keeper_flat_C_graph.json`.

Completed flat native DC smoke (1210): Xyce exits normally after 250.449 seconds with one finite reset-asserted DC point. VPWR/VPB are 1.8 V; VGND/VNB/RESET_N are 0 V. PLLOUT and CONFIG_BUSY are high; CONFIG_READY, TRACKING and FAILED are low. The keeper NAND reset gate followed by two inverting ring stages permits high oscillator output under asserted local reset; this DC observation is not an oscillation or startup check. All source/artifact hashes verify inside the image. No wire-R accuracy, transient behavior, frequency, analog correlation or release qualification is inferred. See `selected_keeper_flat_native_smoke.json`.

Queued flat native programming transient (1213): two deck-conversion controls pass, preserving model inclusion, programming biases and held-low PLL_ENABLE while changing only reset/reference stimuli, transient command and observations. One 260-ns TT case requests coarse 20/fine 112, with a 10-ps maximum step and a 200–260-ns assessment window. Frequency is reported only after complete waveform verification and a stable requested output code without ambiguous bit voltages. The queue respects the existing full-native slot, allows 48 hours waiting and caps one 1-core/16-GiB native case at 24 hours; there is no identical retry. Its source closure verifies inside the image and the live controller is waiting. Distributed wire R is absent, and no selected-design promotion or mixed-signal correlation is claimed. See `selected_keeper_flat_native_transient_launch.json`.

Completed original selected TT upper guard (977): native Xyce reaches 260 ns normally in 41,870.485 seconds. The completed extractor verifies all 45,770 samples and 25,735 vectors finite. Coarse 20/fine 181 remain stationary in 200–260 ns and PLLOUT measures 405.802379 MHz; CONFIG_BUSY remains high, CONFIG_READY and TRACKING remain low. This is calibration, not lock. Waveform SHA, source/artifact closures and selected-interface registry validate inside the image. The original analog/interface identities remain unchanged and now contain six measured points, extending upper lookup coverage; interpolation uncertainty and safe capture remain unqualified. These original-layout results do not transfer to the keeper candidate. See `selected_TT181_native_measurement.json` and `selected_TT181_registry_attachment.json`.

Expanded TT history sensitivity reruns (1214–1215): the completed original TT fine-181 calibration extends the same model-domain range beyond the prior missing code 166. The same KI=1/KP=2, seed-nearest-400-MHz exact-RTL V8 sensitivity matrices are running for nominal and receiver-stress detector compositions on CPUs 23/24, each covering 96 stress/interpolation/scenario/phase combinations. Existing compiled RTL caches are verified and reused; no native cases are launched by either matrix. Source closures verify at launch. The first completed nominal cases pass, but complete results, finite uncertainty applicability, common gain selection and physical correlation remain pending. See `selected_TT181_history_matrices_launch.json`.

Diagnostic matrix image guard (1216): V4 retains a full image SHA check at matrix entry and successful completion, checks inode/device/size/mtime/ctime between cases and rehashes after any metadata change. Every non-image pin is still fully hashed each check; final case artifact and exact 96-case coverage checks are unchanged. This detects ordinary local filesystem changes and does not claim hostile-write isolation. Six controls pass, including a same-size edit with restored mtime, non-image changes, replacement inode, changed expected digest and mandatory final full check. A read-only benchmark on the current 3.2-GB image measures 3.3797 seconds for an ordinary full pin check versus 0.00089–0.00092 seconds for guarded unchanged-image checks; initial/final full checks remain 2.51/2.54 seconds. These are validation timings, not native or end-to-end simulation speedups. Running V3 matrices are unchanged; V4 is retained for subsequent diagnostic campaigns. See `selected_matrix_image_guard_benchmark.json`.

Completed gain-stress failure witnesses (1217): with expanded measured original TT range, KI=1/KP=2 cold-start phase 10 ns under linear-period interpolation completes normally in both detector views with no missing tuning point and correct phase initialization. Neither case confirms acquisition or sustained final acceptance. The final four windows span 4.716–8.459 ns in phase (requirement 0.250 ns); frequency error ranges 880.20–1,660.90 ppm, and fine codes remain inside 153–168. Full case input and artifact hashes verify inside the image. Thus this failure is no longer an unresolved code-166 lookup; it is a completed functional failure under the existing affine gain stress (0.7862884 multiplier). Wide-code physical applicability of that stress is still unqualified, and no actual silicon failure, robust gain choice or complete matrix result is claimed. See `selected_TT181_gain_stress_failure.json`.

Covered KI1/KP4 gain-stress phase20 check (1218): the same four targeted cases that previously requested fine 166 now complete and pass with expanded TT calibration. Both detector views and both period/frequency interpolations confirm acquisition at 163.781 microseconds; final phase spans are 110–125 ps, below the 250-ps requirement. All case inputs and source/artifact closures verify inside the image. This supports a wider KI1/KP4 sensitivity sweep, not a selected robust gain or full-matrix/physical qualification; affine wide-code stress applicability remains open. See `selected_TT181_KI1_KP4_gain_phase20.json`.

Queued KI1/KP4 full sensitivity follow-up (1219–1220): the passing four-case gain-stress recovery motivates the same 96-case nominal and receiver matrices at KI1/KP4. Each waits for its corresponding KI1/KP2 matrix to complete and verifies all predecessor inputs/artifacts before starting one V4 matrix on the freed CPU 23/24. Queue wait is bounded at two hours; the child retains its own finite case/matrix limits and is not restarted on an observer failure. No native cases launch. Both live queue controllers and pinned source closures verify; no running job or selected RTL is changed. Guarded image checks apply only to the future V4 matrices, with mandatory full initial/final image checks. Full-matrix results, physical stress applicability and robust/minimum gain selection remain pending. See `selected_TT181_KI1_KP4_history_queued.json`.

Completed covered KI1/KP2 history matrices (1214–1215, review 1221): both exact 96-case matrices finish with 51 passes and 45 functional failures, and zero missing tuning points. Per detector view, nominal stress passes 24/24, gain passes 6/24, offset passes 21/24 and combined gain/offset passes 0/24. All case inputs/artifacts and exact scenario/interpolation/phase coverage verify inside the image, including prior 1088/1089 comparisons. Every previously completed case retains its old outcome. Former missing cases resolve to six passes plus 18 failures nominal, and six passes plus 15 failures receiver. Therefore added calibration removes lookup ambiguity but does not make KI1/KP2 robust to the declared diagnostic stress. Physical wide-code stress applicability and common five-corner gain qualification remain open. Guarded KI1/KP4 follow-ups have started independently. See `selected_TT181_KI1_KP2_history_results.json`.

Completed expanded-range TT diagnostic gain search (990): eight 24-case matrices verify against all recorded source/artifact hashes. The required first pair KI4/KP0 remains indeterminate at unmeasured codes 110/182. Lower ordered pairs KI1/KP0 and KI1/KP1 each fail functionally over the two detector views without missing lookups; KI1/KP2 passes all 48 corresponding cases. Thus the search resolves KI1/KP2 as the lowest passing pair in this nominal-frequency TT diagnostic scope, with no unresolved lower ordered pair. This does not supersede the separate 96-case-per-view history stress failures, select a robust/common five-corner gain, or qualify physical models. See `selected_guarded_exact_gain_search_result.json`.

Flat device-location regions (1222): the checked filled GDS has exactly one instance of each original macro master, with the same R0 origin on its 1-nm grid as the pinned frame. Independently measured EXT device coordinates use a 1/200-micrometer grid. Assigning each native device location to those non-overlapping frames recovers all primitive model counts and every MOS L/W multiset: digital 49,822, DCO 4,098, detector 1,782 and parent 6,636. Both GDS/stream/frame provenance and source/artifact closures verify. This identifies a potential smaller DCO reference without discarding its physical origin. No circuit has been cut: emitted SPICE device correspondence, all boundary loads and correlation remain unverified. See `selected_keeper_flat_device_regions.json`.

Completed KI1/KP4 history matrices and read-only trace review (1219–1220, 1223–1224): both 96-case matrices finish with 78 passes and 18 functional failures and no missing tuning points. Nominal, gain-only and offset-only groups pass all 24 cases each; combined gain/offset passes six and fails 18. Recomputing every segment from saved edge/control traces and every phase initialization reproduces all metrics exactly, and every case file is hashed before/after. Per view, 30 failing segments comprise 20 late acquisitions (209.760 microseconds elapsed, above 200) and ten without sustained final acceptance. Four reviewer controls pass after correcting a synthetic fixture to include its required reference guard edge; acceptance rules are unchanged. Each V4 matrix records two full image hashes plus 96 guarded intermediate checks. KI1/KP4 improves the prior 51/96 result but is not robust over this diagnostic stress set. Physical stress applicability and common five-corner gain remain open. See `selected_TT181_KI1_KP4_history_results.json`.

Combined-stress gain screen and strict witness review (1225–1226): after the verified KI1/KP0,1,2,4 rejections, the finite phase20 combined-stress screen tries KI1/KP8 first. All four detector-view/interpolation cases pass without missing tuning points. Independent read-only trace recomputation reproduces their metrics, and strict execution/completion/phase checks all pass. During review, V1 screening is found to lack an explicit incomplete-execution guard before gain rejection; no such incomplete case occurs in this four-pass run. Preferred V2 requires the strict classifier for rejection witnesses and new cases, with six controls ensuring incomplete execution or wrong phase cannot reject a gain and missing coverage stays indeterminate. The KI1/KP8 result is a one-witness screen only: the earlier offset-only phase10 late-acquisition challenge still needs checking with the expanded range before any full sweep or robust/minimum gain claim. See `selected_TT181_KI1_KP8_combined_witness.json`.

KI1/KP8 offset challenge and multi-witness continuation (1227–1228): the earlier offset-only cold-start phase10 failure persists with expanded calibration. Both detector views under period interpolation confirm only at 220 microseconds elapsed, past 200; frequency interpolation lacks sustained final acceptance. All four cases have normal completion, correct phase, no missing tuning point and exactly recomputed traces, and all source/artifact hashes verify. This rejects a full KI1/KP8 sweep despite its combined-stress phase20 success. The next finite screen reuses this verified rejection plus the other KI1 failures, starts at KI2/KP0 and tests combined-stress phase20, offset-only phase10 and nominal phase10, each in both views/interpolations. A covered failure prunes a pair; missing lookup stays indeterminate. Passing all 12 cases only nominates a full-sweep candidate. The run is bounded at two hours/240 fast cases with no native launch or identical retry. Its first KI2/KP0,1,2 cases fail functionally without missing points. See `selected_TT181_KI1_KP8_offset_witness.json` and `selected_TT181_multi_witness_gain_screen_launch.json`.

### Flat device region correspondence (1229)

The checked flat EXT and emitted SPICE agree on all 61,504 MOS devices across 37,502 terminal/model/dimension equivalence classes. Transitive native node aliases and unordered source/drain terminals give zero count mismatches and zero cross-region ambiguous classes. Region totals are digital 49,590, oscillator 4,096, detector 1,778 and parent 6,040. This establishes region ownership, not an individual bijection between identical parallel devices or a diffusion-area/perimeter correspondence. The two oscillator poly resistors, boundary coupling and exterior loading still need a checked partition and correlation before a smaller native DCO reference is qualified. No circuit was cut and no release gate was closed. Three focused alias/signature tests pass. See `selected_keeper_flat_MOS_region_join.json`.

### Flat DCO partition boundary audit (1230)

All 20 native poly resistors have unambiguous terminal/model/dimension region correspondence. The oscillator contains 4,096 MOS devices and two poly resistors, with 2,887 primitive nodes: 306 shared with exterior primitives or top ports and 2,581 private. Among 341,067 nonzero capacitor cards, 21,466 have both endpoints on DCO primitive nodes, 40,099 have one, and 279,502 have neither. An independent check of the saved boundary list found zero private-DCO-to-exterior-only capacitors; all crossing cards attach through shared nodes (including supplies). These are topology counts, not a loading equivalence proof. No exterior node was clamped and no circuit was reduced. The shared-node exterior loads/activity still need preservation and native correlation. See `selected_keeper_DCO_partition_boundary.json`.

### DCO shared-node terminal roles (1231)

Native exterior-device terminal inspection resolves all 306 shared DCO nodes: two supply nodes, 302 exterior inverter outputs, the reset net, and PLLOUT. Each of the 302 control drivers has a single gate-input node and only supply/output diffusion connections, checked directly from native cards rather than inferred from node names. Their 1,208 MOS cards must be retained if preserving control-driver impedance. The reset and oscillator-output connections also carry exterior gate/diode loading. The exact cards and terminal roles are saved in the build receipt; they do not yet form a closed reduced circuit. Upstream driver inputs, reset logic, receiver state and capacitor boundary loading remain to be resolved before native correlation. No release gate was closed. See `selected_keeper_DCO_boundary_roles.json`.

### Completed multi-witness gain screen (1228)

The finite screen terminated normally after checking the 20 remaining declared gain pairs. Three covered combined gain/offset phase-20 cases failed (KI=2, KP=0/1/2); their saved traces were independently recomputed. The other 17 pairs stopped at missing native lookups (fine 110 or 182), so they remain indeterminate rather than rejected. Every recorded source/artifact hash and trial input closure was verified inside the pinned image, and the strict disposition classifier agreed with every record. There is no provisional full-sweep candidate. The five previously covered KI=1 rejections remain recorded separately. This does not prove that no fixed gain can pass, and does not qualify physical applicability of the diagnostic stress packets. See `selected_TT181_multi_witness_gain_screen_result.json`.

### Four-rank flat native DC benchmark launch (1232)

A single bounded four-MPI-rank run repeats the completed 1210 reset operating-point deck with only its output filename changed. It uses CPU cores 24–27, a 64 GiB reservation and a 900 s native cap, with no automatic retry. The controller compares all finite output columns against the existing single-process point to an absolute 1e-8 tolerance and records separate elapsed times. Four live native children were confirmed at launch. This measures startup/DC scaling only; it cannot establish transient speedup or qualify the model. The active full transient is unchanged. The pinned image Kokkos configuration has OpenMP and Threads disabled, and the inspected DeviceMgr source contains no OpenMP loop directive; increasing OMP_NUM_THREADS is not a demonstrated acceleration path for this build. See `selected_keeper_flat_MPI_DC_launch.json`.

### Actual digital-to-DCO control chain trace (1233)

All 302 shared control nodes trace through exactly two complementary inverter stages to 302 distinct actual digital macro thermometer ports (47 coarse and 255 fine). Native alias equivalence, every source/drain/body rail connection and the common gate input are checked, with no inferred cell-name mapping. All chains preserve polarity and together require 6,040 parent MOS cards; 1,208 is only the final-stage subset. Their exact native cards are saved in `chains.json` in the build directory. The EXT source hash also independently matches the prior checked partition source. This establishes a concrete RTL-to-analog control interface but does not yet preserve all capacitor, reset or receiver loading. See `selected_keeper_DCO_control_drivers.json`.

### Capacitor closure of DCO plus control drivers (1234)

The 10,138-device DCO-plus-full-driver candidate has 3,491 canonical primitive nodes. Exact native-alias and capacitance-unit parsing identifies 33,023 non-supply capacitor crossings to 7,304 exterior nodes: 32,122 attach at actual RTL control ports, but 901 attach elsewhere. The earlier plain-name exploratory count included uncanonicalized supply aliases and is superseded by this result. Every one of the 341,067 nonzero C cards is classified, including 52,901 with both endpoints on selected non-supply nodes. No capacitor was dropped and no exterior node was clamped. Thus the proposed cut is not an exact closed analog reference: external waveforms/loading still require preservation or a separately validated approximation. Three focused literal-unit tests pass, including p/f suffixes, zero, scientific notation and rejected unknown suffixes. See `selected_keeper_DCO_driver_C_cut.json`.

### Completed four-rank native DC benchmark (1232)

The four-rank reset operating-point run completed normally. All ten observed voltages agree with the single-process reference to at most 1.4212e-16 V. Native Xyce elapsed time is 240.605 s for four ranks versus 241.744 s for one; solver time increases to 149.975 s from 143.647 s. Controller elapsed values (248.594/250.449 s) also include surrounding overhead and are not identical timing scopes, so the native timers are preferred. This single comparison demonstrates no useful DC speedup and does not measure transient scaling. No long transient was restarted. All source/artifact hashes for both completed operating points were independently verified inside the pinned image. See `selected_keeper_flat_MPI_DC_result.json`.

### Residual capacitor crossing locations (1235)

All 901 non-control-port crossing cards resolve to 36 retained nodes and 818 exterior nodes. Reset has 404 cards totalling exactly 37.79962 fF; PLLOUT has 463 totalling 30.20924 fF. The remaining 34 cards attach one per other retained control-driver node. Exact rational sums and original native labels are retained in `selected_keeper_DCO_residual_C.json`. The illustrative C×1.8 V charge sums assume that excursion and are explicitly not frequency/phase error bounds. None of these couplings was omitted. Future necessary full native references should save internal voltages so external-waveform replay and a defensible reduced-model comparison are possible; the running 1213 deck remains unchanged.

### Fine-149 full native reference with internal voltages (1238)

The V2 runner requests all native node voltages via V(*) and programs an explicit fine code while retaining the checked coarse-20 protocol, reset, 260 ns duration, 10 ps maximum step, one-core solver and 24 h native cap. Fine 149 is queued behind the active full-native slot, with a 48 h queue cap and no automatic retry. Completed code stability and all saved finite voltages remain required before frequency measurement. This is a new tuning point on the keeper flat-C model, not transferable to the original selected registry or release qualification. Three deck checks pass. A 686-sample native RC probe verifies V(*) capture and the completed selected-signal reader. The initial 1236 probe failed during BLAS initialization because its harness omitted thread limits; 1237 sets all three one-thread limits, as the queued runner already does. See `selected_keeper_flat_fine149_allV_launch.json` and `selected_keeper_capture_syntax.json`.

### Port-complete conditional DCO export (1240)

The DCO plus complete control-driver chains is now exported as a conditional SPICE subcircuit with 10,138 unchanged native primitive cards and 93,496 unchanged nonzero C cards. All capacitor branches touching selected non-supply nodes, and supply-only branches, are retained. All omitted-device terminals and external capacitor endpoints are exposed as 7,612 boundary ports; 3,185 nodes remain interior. Original top-level formal ports are preserved when represented. No omitted primitive or capacitor touches an interior node. No default voltage source or exterior clamp is added, and supply-current equivalence is not claimed. The subcircuit requires a validated external environment and is not standalone executable or model-qualified. The earlier exploratory 1239 build is superseded by the original-formal-port preserving 1240 build. Three focused export tests pass. See `selected_keeper_conditional_DCO_export.json`; the generated circuit and complete interface are in the pinned build artifacts.

### Conditional reference with free oscillator output (1241)

A boundary-replay frequency comparison must not force PLLOUT to its recorded waveform. The V2 conditional exporter therefore adds every original exterior primitive incident on PLLOUT (eight receiver MOS devices and one diode) and verifies that no omitted primitive touches it. Its original formal output remains exposed for observation, explicitly excluded from externally driven ports. The resulting subcircuit retains 10,147 native primitive cards and 93,531 C cards unchanged, with 7,616 externally driven ports plus the observation-only output. No sources are generated. This supersedes 1240 for free-output replay; 1240 remains only a conditional internal-equation export. Three tests cover omitted receiver rejection, observation-only output preservation and retained coupling to an exterior port without forcing the output. External receiver drain/body waveforms still need validated binding, and no frequency, speedup or release qualification follows from this export. See `selected_keeper_conditional_free_output.json`.

### Native preparation of free-output conditional circuit (1242)

The 1241 circuit is translated into a 10,147-device Xyce model with reversible safe boundary names, literal primitive templates and the same pinned fixed-27 C diode/poly-resistor adapters as the completed full native reset reference. All 93,531 nonzero capacitor endpoint/value pairs are independently restored through the inverse node mapping and compared exactly with the original conditional cards. PLLOUT remains observation-only; 7,616 other ports require a validated external environment. No default sources are added. Three tests verify unusual-name mapping, forced-output rejection and namespace-collision rejection. No native execution, frequency, runtime advantage or model qualification is claimed. See `selected_keeper_conditional_native.json`.

### Exact full-native replay port mapping (1243/1244)

All 7,616 driven conditional ports plus the observation-only PLLOUT map through physical node names to the identical full native model used to prepare the backend. Full-model formal ports map at the top level; internal nodes map under XDUT. A completed 686-sample native RC hierarchy probe verifies actual V(XDUT:INTERNAL)/V(PLLOUT) RAW names and the selected-signal reader. Five tests cover hierarchy/top-level binding, missing physical nodes, missing saved voltages, forced-output rejection and duplicate case-folded variables. The real full-reference header and completed boundary waveforms remain unavailable; the mapper does not consume partial running RAW data or claim replay validation. See `selected_keeper_conditional_replay_plan.json` and `selected_keeper_hierarchical_capture.json`.

### Bounded-memory completed waveform extraction (1245)

The replay extractor requires a normally completed, all-voltage, stationary-code full reference and verified input/artifact hashes before opening its RAW. It validates all saved voltages, sample ordering/count and final time, then writes selected physical ports to a sample-major float64 NPY memory map, retaining only one full native sample in working memory. PLLOUT is observation-only. Seven tests cover complete extraction, truncated data, nonfinite unselected voltages, wrong final time, incomplete-reference rejection, malformed voltage and extra sample rejection. On the completed 1244 native hierarchy probe, all 686 extracted samples match the established reader exactly. This is parser/storage evidence only; actual full-PLL boundary waveforms and replay remain pending. See `selected_keeper_replay_extractor_probe.json`.

### Sample-preserving PWL boundary source writer (1246)

The replay source writer emits sources only for explicitly driven safe ports, never PLLOUT. Every nonconstant recorded sample is written with round-trip float precision; exactly constant traces use two endpoints, with no lossy compression. It rejects role, name, time and finite-value inconsistencies. Five focused tests pass. A completed native RC reference/replay exercise verifies the generated PWL syntax and free-output plumbing; maximum interpolated output difference is 0.950755 mV, measured between differing adaptive sample grids. This small-circuit diagnostic is not an exact equivalence proof, a PLL accuracy limit or a release gate. Actual full-PLL sampled-boundary replay and speed comparison remain pending the all-node native reference. See `selected_keeper_PWL_source_probe.json`.

### Conditional replay pipeline queued (1247)

The replay controller waits for a normally completed all-voltage, stationary-code 1238 reference; it checks controller PID/birth while waiting and never restarts a missing or failed native reference. It verifies that the plan belongs to exactly the supplied conditional model, extracts disk-backed boundary data and emits sample-preserving sources. Preparation reserves one CPU/8 GiB; native replay reserves one CPU/64 GiB with a 24 h cap, following a 48 h reference-observation cap. There is one native case and no automatic retry. PLLOUT remains unforced. Three deck checks pass. Frequency and elapsed-time differences are diagnostic: capture scopes differ and receiver/exterior waveforms depend on the recorded reference, so replay cannot by itself establish an independently predictive DCO model, runtime advantage or release qualification. See `selected_keeper_conditional_replay_launch.json`.

### Combined capture/replay software checks (1248)

All 38 focused tests across ten suites pass together in the pinned release image, with zero failures/errors/skips. Coverage includes physical alias/device-region signatures, exact capacitance units, conditional branch/export boundaries, free-output loading, reversible native port names, full-model/RAW port binding, selected fine-code all-node capture, completed-only disk extraction, sampled PWL sources and replay deck interfaces. This is software plumbing evidence, not an executed full PLL replay, predictive analog-model qualification, refreshed parent timing or release-gate completion. The single-process full reference remains active, followed by queued fine-149 capture and conditional replay. See `selected_keeper_replay_integration.json`.

### Legacy resistance-driver coverage preflight (1249)

The checked flat model has 19,696 capacitor-connected canonical conductor nodes, agreeing with the earlier capacitance-graph count. Of these, 19,643 have at least one MOS source/drain terminal; 53 do not. The exceptions are 33 top formal ports (31 gate-input nets and VNB/VPB, which have no primitive terminal) and 20 internal poly-resistor nets (11 also have MOS gates). The exact labels and terminal-role counts are saved in `without_MOS_diffusion.json` in the build directory. This electrical anchor inventory does not predict the exact Magic skip set: native driver locations and resistor/device handling still require coverage auditing. No extraction was launched or qualified. See `selected_keeper_resistance_driver_coverage.json`.

### Native EXT anchors for diffusion exceptions (1250)

All 53 preflight exception nodes have structural anchors in the actual checked EXT: 33 explicit port-location records and 20 positive-width poly-resistor source/drain anchors. None is structurally unanchored. All 65 native port records are on distinct canonical conductors. Reviewed legacy ResReadPort marks ports FORCE/DRIVELOC/PORTNODE, and generic ResReadDevice records the last two poly terminal triples as source/drain, consistent with these anchors. This corrects any inference that absence of MOS diffusion alone implies a skip. Actual native extraction coverage, device lookup/drive-location behavior and emitted R/C topology remain unverified; no wire-R qualification follows. See `selected_keeper_EXT_driver_anchors.json`.

### Bounded native PLLOUT resistance pilot launched (1251)

After the explicit driver-anchor preflight, one stock-Magic pilot extracts the checked flat GDS with an include filter requesting only PLLOUT. It keeps local/coupling capacitance, requests resistance, disables resistor simplification and exports signed C with threshold -1e100. It uses one CPU/16 GiB, a 1,200 s cap and no automatic retry. Native Magic child PID/birth was confirmed live. All work is in a fresh output directory; checked layout, full native decks and original C source remain unchanged. A completed process alone will not prove a one-network result, device/C contraction or RC qualification; those require independent emitted-artifact audit. See `selected_keeper_PLLOUT_resistance_pilot_launch.json`.

### Completed PLLOUT resistance pilot and contraction audit (1251/1252)

The pilot completed normally. Both native passes report one requested/extracted/output net. It emits 78 positive wire-R cards in one connected component, whose endpoints are exclusively PLLOUT and PLLOUT.*. Exact contraction preserves all 62,338 primitive devices, every checked numeric parameter, source/drain-oriented diffusion parameters and all ordered formal ports. No candidate C card is negative. However, 8,188 of the 341,067 aggregated C pairs differ from the original flat-C reference, so exact device-and-C recovery is false and native simulation remains disallowed. The differences extend beyond PLLOUT; fresh extraction/export must be separated from resistor augmentation before drawing a cause. Five contraction tests pass, including changed-property/C controls and unintended-original-net short rejection. See `selected_keeper_PLLOUT_resistance_pilot_result.json` and `selected_keeper_PLLOUT_R_contraction.json`.

### Separation of fresh extraction and resistor augmentation (1253/1254)

Two fresh Magic processes export original and pilot EXT files with extresist off, without redoing geometry extraction. Re-exporting the original EXT reproduces every aggregated C pair. The pilot EXT alone differs from the original on 8,188 pairs (maximum 11.7 fF). Contracting the augmented pilot against its own C-only export leaves exactly one C difference: PLLOUT-to-ground increases by 65.9447 fF. Its C-only PLLOUT ground term is 23.0686 fF and its 677 other nonzero PLLOUT couplings sum to 65.86412 fF; coupling-to-ground conversion is a specific source-code hypothesis to check, not an accepted correction. Fresh-process exports also change device geometry parameters relative to the loaded-layout export context, so their primitive comparisons fail and no device/model equivalence is inferred. These controls isolate C effects only; their context needs correction before any new model is accepted. All release/simulation qualification flags remain false. See `selected_keeper_pilot_C_controls.json`.

### Validated grid-aligned EXT export controls (1256/1257)

Explicitly matching the 500,000 EXT linear scale to the pinned ngspice technology base of 1,000,000 with `scalegrid 1 2` restores every checked primitive parameter in all three controls (62,338 devices each). Re-exporting the original EXT then reproduces every C pair exactly. Simply loading a tiny GDS with copied UNITS metadata did not restore this context; that exploratory approach is superseded. With device context validated, the pilot C-only extraction still differs on 8,188 pairs (maximum 11.7 fF), while R augmentation alone changes exactly one contracted pair: PLLOUT-to-ground, by +65.9447 fF. The two effects are therefore independent of the earlier parameter-scaling artifact. No model is accepted; a smaller coupling-specific native control is the next investigation. See `selected_keeper_aligned_C_controls.json`.

### Minimal coupling-augmentation reproduction (1258/1259)

Two parallel metal1 wires reproduce the native augmentation effect independently of the PLL. With coupling enabled, the explicit A–B capacitor stays at 3.91111 fF while A-to-substrate rises from 2.84130 to 6.75241 fF: the increase equals the retained coupling exactly. With coupling disabled, before/after C operators match exactly. The simple geometry emits no explicit wire R; the effect occurs in the extresist augmentation path even in that case, while the full PLLOUT pilot separately demonstrates impact with 78 positive resistors. A portable Tcl testcase, expected exports and fresh native positive/negative controls were merged to main as `312eb62`. No correction is applied to any PLL model, and no release gate closes. See `selected_magic_coupling_R_probe.json`.

### Same-GDS C-only extraction-mode control launched (1263)

All 8,188 fresh/pilot C differences are incident on VGND. Inspected native node records retain identical resistance-class geometry statistics while their substrate C fields change. The reviewed Magic command table maps `extract do resistance` to full RC extraction (`extresist`), and that mode changes default-substrate handling in ExtBasic.c. To test mode versus geometry reload, a bounded C-only extraction now reads exactly the pilot flat GDS with full RC mode disabled. It uses one CPU/16 GiB and a 1,200 s cap, no retry, a fresh directory and no fabrication/source mutation. Native process PID/birth was confirmed live. The source observation is a hypothesis until the completed device/C comparison; no equivalence or release qualification is claimed. See `selected_keeper_reloaded_flat_C_launch.json`.

### Exact flat-GDS C-only round-trip control completed (1263/1264)

The completed same-flat-GDS C-only extraction exactly reproduces all 62,338 primitive-device signatures/parameters, the ordered formal interface and all 341,067 nonzero aggregated C pairs of the original reference. There are zero C differences. Thus the 8,188 substrate differences observed in the RC pilot do not come from flat-GDS serialization/reload; they arise in the full-RC extraction path, consistent with its different default-substrate handling. This preserves the original C-only reference provenance and separates mode-dependent substrate modeling from the independently reproduced coupling duplication. It does not qualify distributed wire R, coupled-C placement, corners, loop operation or release readiness. See `selected_keeper_reloaded_flat_C_result.json` and `selected_keeper_reloaded_C_equivalence.json`.

### Physical thermometer-control assessment queued (1265)

A read-only observer binds all 302 actual controls at both ends of their verified two-inverter chains: 604 unique physical voltage roles in the same full native model. Expected states follow the route-pinned RTL: coarse thermometer bits are normal, while the startup fine thermometer is inverted under PLL_ENABLE=0. It waits for a normally completed all-voltage reference, verifies its hashes and code stability, and then checks every final-window sample at both macro and DCO endpoints (existing 0.36/1.44 V logic margins). Five tests cover polarity/bank boundaries, both correct endpoints, a correct macro hiding a wrong DCO endpoint, ambiguous voltage and incomplete-window rejection. No voltage source is added and no completed assessment is available yet. This check is diagnostic and grants no analog or release qualification. See `selected_keeper_physical_tuning_launch.json`.

### Independent native captures scheduled concurrently (1266–1269)

The global legacy full-native slot unnecessarily serialized the independent one-core flat-C cases. Fine 149 now runs on CPU 21 alongside the untouched fine-112 run on CPU 20, using the existing global CPU/RAM leases (combined 2 CPUs/32 GiB), a 24 h native cap and no retry. Both native process identities and CPU affinities were confirmed live. Its electrical deck is exactly the old queued deck after substituting only the output-directory path; the shared deck generator also passes an equality test at four fine codes. Only the never-started old fine-149 waiting controller was withdrawn after PID/birth, waiting state and absence of a native process receipt were checked. No running native simulation was stopped. Old replay/physical observers terminate on that explicit superseded reference; live replacements 1267/1268 use the new capture. Historical FF/remaining-corner requests are retained. This removes queue delay, not a measured per-case speedup or qualification. See `selected_keeper_parallel_capture_handoff.json`.

### Parallel keeper TT characterization family launched (1270)

Five additional independent native cases now characterize coarse 20 at fine 8/110/133/182/247, alongside existing fine 112 and 149. Fit points are 8/110/149/182/247; fine 133 is reserved as an independent interpolation holdout. Every new case uses the same flat-C backend model, TT/27 C/1.8 V, programming protocol and all-node capture, one dedicated CPU/16 GiB, a 24 h cap and no retry. Both native PID/birth/affinity and each read-only physical-control observer were verified live. The combined native reservation is 7 CPUs/112 GiB within the existing global budget. Full completion, finite stationary codes and actual thermometer voltages remain prerequisites for using each point. No curve, holdout accuracy, other corner, wire-R or release qualification is claimed. See `selected_keeper_TT_characterization_launch.json`.

### Completed-point TT collector queued (1271)

A read-only collector waits for all six fit/holdout captures and their physical-control assessments. It requires normal finite native completion, stationary codes, matching backend/domain hashes and all 604 endpoint voltages before reporting the measured 400 MHz bracket and independent fine-133 errors for linear-frequency and linear-period interpolation. The holdout is excluded from fitting. Six tests cover the bracket, holdout leakage, extrapolation, nonmonotonic curves, nonfinite frequencies and an out-of-range target. Its 48 h observation cap does not restart or stop native children. No automatic accuracy acceptance, model promotion or release qualification is granted.

Collector workflow validation: three additional synthetic-fixture tests exercise completed six-point collection without model promotion, rejection of a physical assessment belonging to another native receipt, and rejection of an incomplete capture. All nine collector tests pass. These fixtures are test data only and provide no PLL characterization evidence; the running collector source and all native inputs are unchanged.

### Keeper timing prerequisite audit (1272)

All five historical 402.1 MHz timing screens pin the routed internal digital macro database 019; keeper route 1136 is the surrounding parent database. Their different hashes do not alone establish a change to the digital macro. Completed audit1439 verifies identical recursive digital-macro geometry and labels; changed parent loading and conditional timing models remain unqualified. Their reported minimum slacks are TT -0.44 ns, FF -0.48 ns, SS -0.35 ns, SF -0.38 ns and FS -0.46 ns; these are historical results, not measured keeper violations. The new min/nom/max parent wire views pin the current route. Later binding 1154 supersedes the wire export’s initial pending-binding flag: all 973 networks per view are bound and connected. Combining those wires with current macro capacitance and qualifying propagated clock/receiver response remain incomplete. Keeper timing must bind the internal digital macro and current parent wire views through qualified macro loads and clock/receiver response, then resolve actual setup/hold failures and rerun CDC/reset/enable and closed-loop checks. This artifact-identity audit does not requalify the historical dependency closures. See `selected_keeper_timing_prerequisites.json`.

### Explicit resistance extraction after C-only substrate extraction (1273)

One bounded PLLOUT pilot now leaves `extract no resistance` in effect during `extract all`, then calls `extresist all` explicitly. The source makes default-substrate selection depend on the full-RC extraction option, while explicit resistance extraction consumes the emitted EXT. This tests whether the original C-only substrate operator can be preserved independently of the already reproduced coupling augmentation. It uses the same flat GDS, stock Magic/PDK, one CPU/16 GiB, a 20-minute cap and no retry. Native process identity was verified live. No correction or RC qualification is claimed; exact device/C contraction is required after completion. See `selected_keeper_PLLOUT_R_after_C_launch.json`.

### Explicit resistance-after-C pilot completed (1273/1274)

Stock Magic completes the C-only extraction followed by explicit PLLOUT resistance extraction normally. All 62,338 primitive signatures/parameters and ordered ports match the original reference; 78 positive resistors form one component without joining distinct original nodes. Exact contraction now differs on only one of 341,067 C pairs: PLLOUT-to-ground increases by 65.9448 fF. Thus the 8,187 off-PLLOUT differences of the earlier full-RC-mode pilot are eliminated by extraction order, independently of the remaining coupling augmentation defect. There are zero negative candidate C cards. The exact C invariant still fails, so this is not a usable or qualified RC model and no native PLL run is launched from it. See `selected_keeper_PLLOUT_R_after_C_result.json` and `selected_keeper_PLLOUT_R_after_C_contraction.json`.

### Remaining ground-capacitance increase traced to coupling (1276)

Resolving native EXT aliases gives 1,030 raw coupling records incident on PLLOUT, totaling 65.944796012611 fF. The 79 resistance-node ground-capacitance records sum to 65.944820109 fF; their difference is 0.000024096389 fF. The final exported ground increase is 65.9448 fF. These quantities agree within native floating-point/export precision, not exact rational equality. This quantitatively supports the inspected `ResReadCapacitor` signal-mode path that adds coupling to node capacitance, followed by distribution to resistance nodes, while the explicit coupling is retained. No rounding adjustment, capacitor subtraction or model correction is applied. Spatial capacitance placement and the RC model remain unqualified. See `selected_keeper_resistance_coupling_charge.json`.

### Native EXT node-retention controls (1277)

Five hand-authored EXT/resistance-file fixtures were exported by stock Magic; these are file-format controls, not geometry extraction. The reference has A–B 3 fF, A-ground 2 fF and B-ground 1 fF. Retaining A while adding a 3 fF resistance-node capacitor preserves A–B and raises A-ground to 5 fF. Removing that addition restores the reference after prescribed resistor contraction. Killing A instead removes its explicit coupling and original 2 fF substrate capacitance; adding the 3 fF resistance-node capacitor only substitutes a ground branch. Removing that addition as well loses both original capacitances. Thus a general correction must preserve/remap original capacitive connections for replaced nodes, not just stop adding coupling to ground. All five native exports completed. No extractor patch, physical placement or model qualification is claimed. See `selected_magic_coupling_node_lifecycle.json`.

### Full native maximum-timestep control launched (1278/1279)

One full keeper fine-149 case now changes only the maximum timestep from 10 ps to 50 ps; the initial suggested step remains 10 ps. Its actual deck matches the live 10 ps reference exactly after replacing the output path and that single transient argument. A deck test checks this invariant at four fine codes, preserving model, stimuli and numerical tolerances. The new case uses CPU 25/16 GiB, all-node capture, a 24 h cap and no retry; native PID/birth/affinity and its physical-control observer were verified live. Comparison requires normally completed captures and correct physical controls, with frequency and edge timing considered together. No accuracy qualification or speedup is claimed; finer-step convergence remains necessary before qualification. Original characterization/replay inputs remain unchanged. See `selected_keeper_step50_launch.json`.

### Completed native timestep comparison queued (1280)

A read-only comparison waits for normal completion and physical tuning validation of both fine-149 captures. It verifies source/artifact hashes and deck equality except the output path and maximum timestep before reading either RAW. It extracts output waveforms while checking every saved voltage, reports final-window frequency error and rising/falling ordinal edge differences, and refuses phase pairing when post-reset edge counts differ. Equal counts alone are explicitly not a cycle-slip proof. Capture elapsed times include validation/output work and are not labeled isolated solver timings. Five tests cover equal-frequency phase shifts, frequency/count changes, truncated/nonfinite waveforms and stationary output. The observer is live with a 48 h cap, no native changes/retries and no automatic numerical/model qualification. Finer-step convergence remains unavailable.

### Finer-step full native control launched (1281/1283/1284)

A single fine-149 5 ps maximum-step capture now refines the unchanged 10 ps reference, alongside the 50 ps speed control. Actual decks differ only in output path and maximum timestep; a four-code deck equality test passes. The native PID/birth/CPU 26 affinity, physical observer and completed-result comparison were verified live. Each native case retains its 24 h cap and no retry; all nine reserve 9 CPUs/144 GiB within the global budget. The first observer-only submission raced the creation of inputs.json and exited before creating its output; replacement 1283 was initialized after the manifest existed, without rerunning or interrupting native work. Comparison V2 reuses the tested waveform metrics and explicitly checks the declared 5 ps candidate; no convergence/model qualification is inferred until results are available and assessed. See `selected_keeper_step5_launch.json`.

### Non-TT flat-model reset DC checks launched (1285)

The fixed-27 C backend retains dynamic corner expressions for diode junction multipliers and poly sheet resistance/dimensions; it is not numerically frozen to TT in those expressions. Four reset-DC checks select FF/SS/SF/FS library sections sequentially on CPU 27/16 GiB, with an unchanged backend and external biases. The first actual FF deck differs from the completed TT reset deck only in library selection and output path; two tests enforce that invariant and reject other domains. The FF native PID/birth/affinity were verified live. The family cap is two hours, each native case has a 30-minute cap, and no identical retry is allowed. Completed checks will establish only native acceptance and finite saved reset values, not complete internal states, corner I/V/C-V or transient correlation, tuning, or release readiness. See `selected_keeper_non_TT_reset_DC_launch.json`.

### Current backend diode controls revalidated (1286)

All 50 fresh native analyses complete using the current value-gather/reuse Xyce backend: DC, three AC biases and a completed 3 ns transient for both keeper diode geometries at all five corners, 27 C. Their model/wrapper fragment exactly matches the current flat backend; the unchanged corrected-ngspice reference outputs and prior review hashes were verified. The 814 current diodes comprise 812 of area 0.6417 um²/perimeter 3.24 um and two of area 0.4347 um²/perimeter 2.64 um. All existing limits pass without adjustment: maximum DC relative error 0.000539961 (1 pA denominator floor), AC complex-current error 4.86221e-10 and integrated transient terminal-current error 0.000153447. This revalidates sampled diode component controls for the current executable, not noise, arbitrary bias/geometry, full macro/corner transient correlation, or PLL release readiness. See `selected_keeper_current_backend_diode_controls.json`.

### All current MOS/poly literal geometries checked at DC (1287)

The current backend has 429 unique MOS parameter sets and two poly-resistor geometries. Semantic literal comparison finds 399 current MOS sets in the historical fixture and 30 absent, so its DC evidence could not cover the keeper unchanged. Fresh native ngspice/current-Xyce controls now compare all current sets at five corners/27 C, three gate biases and two drain/probe biases: 12,870 MOS-current and 60 resistor-current observations. All ten native analyses complete. Maximum MOS relative difference is 3.85807e-8 with a 1 nA denominator floor; maximum poly difference is 2.18529e-16 with a 1 pA floor, passing the unchanged 1e-10 poly DC screen. The resistor gate-bias rows repeat the same two-terminal conditions; these counts are observations, not 60 independent resistor bias states. No new MOS acceptance limit or analog gate is inferred. Capacitance, transient, noise and full PLL correlation remain unqualified. See `selected_keeper_current_primitive_DC.json`.

### Current MOS small-signal mismatch measured (1288–1290)

All 429 current MOS literal geometries were compared natively across five corners at gate/drain DC 0.9 V, separate unit gate/drain AC excitations, and 25/400 MHz: 17,160 terminal-current observations. Gate-excitation maximum relative difference is 1.46715e-6; drain-excitation maximum is 0.1105932. Maximum reactive-current difference divided by angular frequency and unit excitation is 0.05670768 fF. This is a measured primitive small-signal discrepancy, not an inferred PLL frequency/phase error or an accepted model bound. Several worst relative cases are long-channel NFET drain responses; DC agreement does not qualify their capacitance behavior. Root cause remains open.

The first attempt stopped because this pinned ngspice returned one row for `ac lin 2 25e6 400e6`. A separate one-resistor native control reproduces that behavior; `lin 3` returns both endpoints plus 212.5 MHz, and a one-frequency control returns 400 MHz correctly. V2 compares the verified endpoint rows of the three-point reference grid. It reuses the already completed, byte-identical TT gate-excitation Xyce case and runs 19 new native analyses; no completed candidate case is rerun. Both attempted sources and outputs are retained, and all source/artifact hashes verify. No bias-range, capacitance, transient or full PLL qualification is granted. See `selected_keeper_current_primitive_AC.json`.

### BSIM drain gate-sidewall default isolated and patched (1291–1293)

The inspected Xyce BSIM4 4.6.1/4.7.0/4.8.2 paths default omitted PBSWGD to the ordinary drain-sidewall potential, while pinned ngspice defaults it to the source gate-sidewall potential. SKY130 NFET models distinguish those potentials. A PDK-free one-MOS native fixture confirms a -0.0791960172 fF difference per 1 um gate width, matching the two junction-potential formulas. Explicit PBSWGD equal to PBSWGS removes that discrepancy; equal potentials and an explicit asymmetric value are controls. Eight original native analyses complete.

An isolated executable corrects that single omitted-value assignment in each version path. Relinking the cached base archive first reproduces the current executable byte-for-byte. Exactly three BSIM objects then change; all other archive members, including diode/solver objects, remain identical. Two source-shape tests pass. All 24 corrected native controls across requested versions 4.6.1/4.7.0/4.8.2 agree with ngspice to at most 1.40661e-11 fF. This is a minimal-defaulting regression result, not a full MOS/PLL qualification. The full current-geometry AC matrix and any accepted new-backend calibration still need rerunning. Stock sources, current binaries and all running job inputs remain unchanged. See `selected_bsim_drain_gate_potential.json`, the native probe scripts under `../signoff400/`, and `../../tools/xyce_umfpack/bsim_PBSWGD_default.patch`.

### Corrected backend rechecked on all current MOS AC controls (1294)

Ten new Xyce analyses reuse the exact completed ngspice reference outputs and byte-identical electrical decks from 1290. All 429 current MOS parameter sets, five corners and separate gate/drain excitation controls complete: 17,160 observations. Correcting the omitted PBSWGD default reduces the worst relative complex-current difference from 0.1105932 to 1.68365e-6. The maximum reactive-current equivalent difference is 2.28595e-8 fF (maximum drain-excitation value 1.11956e-9 fF). This confirms that the defaulting correction removes the large measured keeper-geometry discrepancy at the sampled bias/frequencies. Full-bias, transient and full PLL qualification remain open. Old-backend calibration cannot be silently attached to the new executable. See `selected_keeper_corrected_BSIM_AC.json`.

### Corrected-backend full native capture launched (1295/1296)

One fresh TT/27 C/1.8 V coarse-20/fine-149 all-node capture uses the separately built and component-checked PBSWGD-corrected executable. Its build and complete keeper AC control receipts are verified and pinned; active executable path/hash and the correction flag are explicit in inputs and completed-result metadata. The actual electrical deck is byte-identical to the old-backend fine-149 deck after output-path substitution, and /proc executable identity confirms the new binary. Native/controller/physical-observer PID births and CPU 16 affinity were verified live. The case has a 24 h cap, one CPU/16 GiB and no retry. The ten capture reservations total 160 GiB; the ongoing one-core corner DC check brings reservations to 176 GiB, within budget. Existing jobs stay unchanged, and their old-backend tuning points are not promoted to the corrected executable. No corrected full-circuit frequency, numerical convergence or release qualification is available yet. See `selected_keeper_corrected_BSIM_capture_launch.json`.

### Non-TT reset DC checks completed (1285)

All four FF/SS/SF/FS cases complete normally with exactly one finite saved reset point; elapsed times are 976.39/315.17/1166.38/265.26 seconds. Saved supply/body/reset rails match their requested values, PLLOUT/BUSY are high, and READY/TRACKING/FAILED are low at the existing logic margins in every corner. These are the original value-gather executable’s reset diagnostics, explicitly not new PBSWGD-corrected-backend results. No full internal state, corner transient response, tuning or model qualification is inferred. See `selected_keeper_non_TT_reset_DC_result.json`.

The simulator-only PBSWGD patch, portable builder and PDK-free positive/negative native controls were independently validated in a clean integration worktree and pushed to main as `88abedd`. Its fresh binary is byte-identical to the locally validated corrected backend; unpatched controls fail and all 24 patched controls pass. The in-progress PLL design remains on the development branch.

### Corrected-backend free-output replay queued (1297)

The new replay explicitly verifies the active executable hash in both the capture manifest and completed receipt, including the correction flag and matching input pin. Four guard tests accept a matching identity and reject old active binaries despite unrelated corrected pins, missing metadata, wrong hashes and false correction flags. It also pins the matching physical observation plan and waits for all 604 control voltages to pass on that same completed capture before generating sources. The existing checked free-output deck generator is reused unchanged. Replay uses the corrected executable on CPU 28 with a 64 GiB global lease and 24 h cap, after a 48 h observation cap; no retry or change to native children is allowed. The observer identity is live, waiting for capture 1295. PLLOUT stays unforced. This remains a sampled-boundary consistency/speed check, not an independently predictive DCO model or qualification for controller changes. See `selected_keeper_corrected_BSIM_replay_launch.json`.

### Logging-only coupling geometry controls (1301–1303)

An isolated Magic build records native overlap, sidewall and fringe search support without changing capacitance arithmetic or introducing early node naming. All six trace-off/on native controls complete with identical primitive and capacitance inventories. Their traces reconstruct each exported coupling pair at native six-digit precision, including two checked sidewall spans. The legacy overlap path is not exercised. A bounded full checked-flat-GDS trace is running on CPU 27 with a 16 GiB lease and 1800 s cap; its process birth and affinity were verified. Full-layout circuit equivalence and trace reconstruction remain pending. Search support does not resolve shielding masks, ground-capacitance placement or distributed RC conservation. No simulation model or release gate is promoted. See `selected_magic_coupling_geometry_controls.json`.

The full-layout coupling auditor preserves double-precision event order per native pointer pair, applies native six-significant-digit rounding before combining printed aliases, and sums duplicate exported records exactly. Three regression tests cover alias rounding, visible unmapped events, and rejection of repeated extraction epochs. It reproduces all three completed native control traces. Substrate relocation and original ground capacitance remain outside this coupling-only audit; a matched exported table cannot qualify their spatial placement. The full-layout result remains pending.

### Ground-capacitance trace coverage review

The pinned extraction sources contain 18 direct `nreg_cap` mutation sites across ExtBasic, ExtCouple and ExtRegion. Area/perimeter additions, shielding subtractions, substrate relocation, property/option suppression, near-zero clamps and the final negative export clamp must be accounted for before spatial redistribution. The existing coupling-only trace omits these ground updates. Its search boxes also do not resolve shielding masks. The reviewed inventory records source hashes and required coverage; it is not an alias-aware whole-program proof or an implemented ground ledger. See `selected_magic_ground_capacitance_source_review.json`.

### Full-layout trace circuit neutrality (1303/1305)

The coupling-only traced extraction completes normally on the unchanged checked flat GDS. Exact comparison with 1202 matches all 62,338 primitive calls, their parameters and endpoints, ordered formal ports, and all 341,067 nonzero capacitor pairs with zero differences or negative capacitor cards. The 21 GB coupling trace reconstruction audit is still running. This proves circuit neutrality for this extraction, not pointwise placement or a distributed RC model. See `selected_keeper_trace_circuit_equivalence.json`.

A separate isolated tracing build instruments all 18 direct ground-capacitance mutations and observes native node output using one shared extraction epoch. Its numerical ledger validator checks state continuity, native scaling/clamps and exported node records; four tests pass, alongside the three coupling auditor tests. Compilation completes and installation is in progress. Native circuit-neutrality and ground-ledger controls remain pending; spatial shielding/ground placement remains unimplemented. The coupling auditor accepts explicit ground events for separate validation.

### Ground lifecycle native controls completed (1307)

All six native trace-off/on controls finish normally. Each circuit remains exact, including all exported ground and coupling capacitor values. The numerical ground ledgers reconstruct 12/11/11 ordered updates and three node outputs per parallel/overlap/fringe fixture. Area/perimeter additions and sampled overlap/fringe shielding paths are exercised; the other instrumented sites are not thereby runtime-qualified. The combined checked-flat-layout trace 1308 is now running on CPU 27 with 16 GiB and an 1800 s cap; native birth and affinity match. Its numerical ground audit, circuit equivalence and coupling reconstruction remain pending. A separate v2 ground auditor adds the bounded-job CLI while leaving the control-pinned original unchanged; it reproduces all three completed native fixture ledgers. No spatial placement or distributed RC qualification is inferred. See `selected_magic_ground_lifecycle_controls.json`.

### Native shielding support control (1309)

A three-conductor fixture places coincident m1/m3 rectangles with an m2 shield over half their overlap. Both native trace-off/on runs complete with exact circuits, and both numerical ledgers reconstruct all exported records. The A–B overlap event retains a search rectangle of area 400,000 database units squared but reports only 200,000 unshielded units squared. Thus the current rectangle cannot be uniformly distributed as surviving A–B capacitance. The next spatial implementation must retain the shielding subtraction geometry (including recursive plane traversal), along with signed ground contributions, before mapping endpoints into wire-R components. See `selected_magic_shielded_overlap_trace.json`.

### Overlap shielding geometry implementation in validation

A new isolated build records an overlap begin/end pair and each terminal shielding-removal rectangle, including removals reached by recursive plane traversal. Native arithmetic and the original tracing engines remain unchanged. The geometric auditor subtracts disjoint rectangles, checks scalar native areas against the surviving support, rejects overlapping/outside removals or incomplete event pairs, and withholds rectangular reconstruction for split-tile cases. Five targeted tests pass. A two-case native runner covers half shielding and two intervening planes; compilation and these four native off/on controls are pending. Fringe shielding, split-tile support and ground spatial assignment remain open.

### Full-layout coupling ledger reconstructed (1306)

All 58,017,745 logged contributions reconstruct the 564,002 exported native coupling-name pairs exactly at native precision, with zero differences. The audit checks 4,276,668 sidewall spans. Of 583,156 native pointer pairs, 19,151 pairs comprising 11,923,030 events lack an exported coupling-name mapping; they remain explicitly unresolved, not discarded as qualified ground capacitance. The combined ground trace is needed to identify their lifecycle. Together with 1305, this proves circuit neutrality and exported coupling reconstruction, not shielding-resolved placement, distributed wire-R validity or release readiness. See `selected_keeper_trace_coupling_reconstruction.json`.

### Native overlap shielding reconstruction passed (1311)

All four native trace-off/on controls complete with identical circuits and matching numerical ground/coupling ledgers. The geometric audit reconstructs three overlaps/one shielding leaf in the half-shield case and five overlaps/two leaves in the recursive case. A–B support is exactly `[2000,0,4000,100]` for half shielding and `[2000,0,3000,100]` for two intervening planes, matching native remaining areas of 200,000 and 100,000 database units squared. This validates these rectilinear overlap cases, not split tiles, fringe weighting, ground placement or distributed wire R. See `selected_magic_overlap_support_controls.json`.

The pending full-layout relocation audit uses the observed substrate identity and paired native coupling-writer events, not names alone, to distinguish exported, zero-sum, relocated and unresolved pointer pairs. Every relocated pair must match exactly one native ground update using the original rounded `before + cap == after` operation. Three regression tests pass, including missing-update rejection and prevention of names-only export claims. All four completed numerical native fixtures classify correctly; they do not exercise substrate relocation. The bounded-job CLI pins the matching engine receipt and its inspected relocation-site inventory. Full-layout relocation proof remains pending.

The rectilinear fringe integration helper implements the pinned extractor’s distance kernel with its native 0.6366 constant. Four tests pass: rectangle partition conservation, mirrored directions, weaker weight at greater distance for equal areas, and agreement with independent density quadrature. This establishes the helper’s mathematical behavior, not correlation to logged native fringe rules or a qualified spatial model. Native per-rule multipliers and shielding fractions still need tracing.

### Combined ground trace preserves full circuit (1308/1312)

The combined ground/coupling trace completes normally. Its exact circuit comparison again matches all 62,338 primitives, ordered formal ports and 341,067 nonzero capacitor pairs, with no differences or negative capacitor cards. Numerical ground continuity, coupling reconstruction and substrate relocation audits are running; they remain separate from circuit neutrality. See `selected_keeper_ground_trace_circuit_equivalence.json`.

A further isolated diagnostic build logs native per-rule fringe multipliers, base fractions, shielding fractions and support rectangles, including terminal callbacks reached by recursive shielding. Strict source-shape insertion and Python compilation checks pass; native compilation and correlation remain pending. The original arithmetic and previously pinned sources stay unchanged.

The per-rule fringe support auditor integrates surviving rectangles separately with the native coupling and substrate multipliers, verifies each logged shielding-fraction update, and checks both remaining weighted totals. Split-tile placement stays unqualified. Four regression tests pass for half-edge location/weight, erroneous native fractions, incomplete traces and split exclusion. The new native runner covers single-plane shielding, recursive shielding and an offset receiver partially covered by an intervening layer. Native compilation/correlation remains pending; the comparison tolerances (5e-13 relative, 1e-13 absolute in diagnostic integral units) are numerical diagnostic limits, not PLL accuracy or release criteria.

### Native fringe support correlation completed (1317/1318)

The initial six controls and expanded eight-control set all complete normally with exact trace-off/on circuits and reconstructed numerical ledgers. Single-plane fringe shielding exercises one leaf; a dedicated offset m4 receiver with m2/m3 shields exercises eight rules and two recursive shielding leaves. Weighted surviving rectangles match native coupling/substrate fractions with a maximum diagnostic comparison difference of 5.68435e-14 in integral units (zero in the other cases). This is native correlation of these rectilinear fixtures, not a global placement or RC qualification. Split tiles, spatial ground updates and resistance-node endpoint mapping remain open. See `selected_magic_fringe_support_controls.json` and `selected_magic_recursive_fringe_controls.json`.

### Full-layout ground accounting and relocation verified (1313/1315)

The ground audit verifies 63,740,896 ordered updates and 800,253 resets/output records, matching every exported ground node with no missing or extra records. It observes 29 native negative export clamps. The relocation audit classifies all 583,156 pointer pairs: 564,002 exported coupling pairs, 19,151 substrate-relocated pairs and three zero-sum pairs. Every relocated pair matches its observed VGND substrate identity and an exact native rounded ground addition; no nonexported pair remains unresolved. This proves numerical lifecycle accounting, not spatial ground assignment, local clamp treatment, resistance-node mapping or distributed wire-R qualification. The additional coupling reconstruction pass 1314 is running after the ground pass. See `selected_keeper_ground_trace_numerical.json` and `selected_keeper_ground_trace_relocation.json`.

### Raw resistance-area provenance diagnostics (1319–1322)

An isolated engine observes all ten raw tile-area assignments without changing native arithmetic. Four horizontal/vertical native trace-off/on controls complete with exactly matching R/C/device/port exports and matching raw support areas. They exercise the left/right contribution sites, not the single-breakpoint branch with the source-level sign asymmetry. A dangling T-shaped case completes native export but its controller stops during spatial postprocessing on reversed support bounds. A separate auditor classifies the existing artifacts without rerunning natives: off/on exports match exactly; the tee logs two negative native additions, two reversed supports and four ordered supports extending outside their tile. These raw signed terms may participate in later merges and are not by themselves proof of a simulator defect. They prevent using raw areas as physical capacitor placement without merge provenance. The corrected postprocessing receipt is explicitly artifact analysis, preserving the original stopped receipt. No final-node area continuity, placement or wire-R qualification is inferred. See `selected_magic_resistance_area_controls.json` and `selected_magic_dangling_area_postprocess.json`.

The completed dangling-tee trace-off and trace-on exports both contain an explicit A-to-SUB capacitor of -0.9887 fF. The resistance EXT has two negative rnode contributions. Thus the raw signed anomaly reaches exported capacitance; it is not only a transient area observation. The single-breakpoint sign-asymmetry branch remains unexercised and is not assigned as the cause. Network passivity is not inferred from the sign of one card. A new isolated build observes node initialization/merging, native float area-to-capacitance scaling and existing rnode naming/output to determine the unsimplified lifecycle. Compilation and lineage validation remain pending. See `selected_magic_dangling_negative_export.json`.

### Combined trace coupling closure and localized port control

The final combined-trace coupling pass 1314 reconstructs all 564,002 exported pairs exactly, complementing the completed ground and relocation audits. Numerical accounting is now complete for 1308; spatial assignment remains open. See `selected_keeper_ground_trace_coupling.json`.

Six localized-label controls 1327 preserve conductor geometry while narrowing A/B port rectangles. All off/on exports match exactly. The localized tee no longer exports a negative capacitor, but exercises the separate horizontal single-breakpoint branch: it adds negative area for a positive tile. Thus broad port attachment and the single-breakpoint sign asymmetry are distinct effects. This is a fixture diagnostic, not authorization to relocate PLL ports or a source fix. The first lineage observer 1325 passes simple wires but correctly rejects the tee at a state-continuity gap caused by unobserved topological area transfers. A new isolated version observes 13 additional transfers; its extended auditor passes seven regression tests. Native lineage closure remains pending. See `selected_magic_localized_port_area_controls.json`.

### Native resistance-node numerical lineage closed on controls (1328/1329)

Both six-run off/on suites complete with exact circuits and exact resistance-node export reconstruction. Initialization, pointer reuse, raw float additions, node merges, series area transfers and float normalization all match observed states. The broad-port tee exercises eight initializations, three merges and two series transfers; two negative raw additions survive as two negative final node values. The localized tee exercises four initializations, one merge and three area transfers; its single-breakpoint negative addition survives accounting but final exported node capacitance is positive. Unexported nonzero states from eliminated nodes remain explicit and geometric merge-basis attribution is not yet qualified. These results separate the two effects without asserting a physical endpoint mapping or valid full RC model. See `selected_magic_extended_lineage_controls.json` and `selected_magic_localized_lineage_controls.json`.

### Isolated single-breakpoint area-sign candidate in validation

A candidate changes only the horizontal single-breakpoint width from LEFT-minus-RIGHT to RIGHT-minus-LEFT, along with the corresponding diagnostic value copy. Compared with the checked lineage observer, every other transformed file remains byte-identical. A pure one-expression source patch is retained. The candidate build explicitly marks capacitance arithmetic modified and the sign correction present; its native runner requires those flags. The baseline localized tee normalizes 119,999.9921875 area units despite a 500,000-unit conductor union. Native verification of corrected area accounting, unchanged cases and R exports remains pending. The broad-port attachment anomaly and coupling duplication remain separate unresolved issues; no candidate is promoted to the PLL model or release tool.

### Single-breakpoint sign correction passes scoped native regression (1331–1333)

Eight candidate native off/on runs complete with exact circuits and reconstructed lineages. The comparison pins matching baseline/candidate engines and byte-identical electrical Tcl protocols after output-path substitution. The localized tee changes exactly one raw contribution’s sign and normalizes 499,999.96875 area units instead of 119,999.9921875, against a geometric union of 500,000 (one float32 rounding unit difference). All raw candidate contributions are nonnegative. Both simple-wire controls remain exact, and the broad-port tee retains its three-resistor network and identical exports. Native total capacitance inputs are unchanged. The fixture-only roundoff allowance is derived from float32 area ULP and observed update count; it is not a PLL error budget. The separate broad-port anomaly and coupling duplication are explicitly not fixed. This validates the one-expression correction on these controls, not global spatial attribution or the PLL RC model. See `selected_magic_area_signfix_local_controls.json`, `selected_magic_area_signfix_broad_controls.json` and `selected_magic_area_signfix_comparison.json`.

### Rectangular port projection passes scoped native controls (1335–1337)

Eight native off/on runs complete with exact circuits and reconstructed node lineages. Only the NEWPORT-containing header differs from the area-sign-only engine. All localized cases remain electrically identical. The broad-port tee has no reversed/outside support, negative raw additions or negative C cards; the ideal broad port eliminates its three internal resistor cards. Original C-only EXT inventories and electrical Tcl protocols remain identical. Separate exact contraction against a device-free C-only fixture reference still shows excess A-to-SUB capacitance of 3.91111 fF, equal to retained A–B coupling: projection does not resolve coupling duplication or qualify an RC model. Split tiles remain explicitly outside this candidate. See `selected_magic_port_projection_local_controls.json`, `selected_magic_port_projection_broad_controls.json` and `selected_magic_port_projection_comparison.json`.

### Checked PLL resistance geometry pilot launched (1339)

The checked flat keeper GDS is undergoing one PLLOUT-only resistance pilot with the separately validated area-sign/rectangular-port corrections. Structural anchor, engine and native-comparison receipts are verified and pinned. The actual native executable matches the installed artifact closure; PID birth and CPU 27 affinity match. It uses one CPU, 16 GiB, a 1800 s cap, C-only extraction before explicit extresist, no resistor simplification and no native retry. It records node-area lineage. Exact primitive/C contraction, raw support and conservation audits remain pending; simulation/model qualification stays false. Attempt 1338 stopped during receipt-schema preflight before any native process; v2 handles the artifact-free comparison receipt explicitly and uses a fresh output directory. See `selected_keeper_PLLOUT_corrected_geometry_launch.json`.

### Bounded PLLOUT trace selection launched (1340)

An offline worker selects PLLOUT ground/coupling events from the completed 34 GB combined trace, requiring matching completed ground, coupling and relocation audit receipts. It verifies the source hash closure once, backtracks to a provably complete output-name suffix, byte-filters the forward scan, and independently reconstructs selected exported coupling and ground continuity. Source stat identity must remain unchanged through selection. The packet retains source line numbers and resolved endpoint names. Four tests cover suffix backtracking, conflicting names, wrong exported coupling and missing ground updates. The CPU-29 worker has an 8 GiB lease and 2 h cap; PID birth and affinity are verified. Selection remains pending and will not qualify unresolved shielding or ground geometry. See `selected_keeper_PLLOUT_trace_packet_launch.json`.

### Corrected-backend numerical control and additional tuning captures (1341–1347)

A fresh corrected-backend fine-149 50 ps maximum-step capture runs on CPU 30; its actual electrical deck differs from the corrected 10 ps reference only in output path and maximum step (initial step remains 10 ps). A corrected fine-110 10 ps capture runs on CPU 31, while corrected fine-182/CPU 27 waits for the global RAM budget. Each keeps the TT/27 C/1.8 V coarse-20, 260 ns protocol, 16 GiB/24 h cap and no retry. Active native executable paths/hashes, PID births and affinities are verified where started; queued controller identity is verified. Each has a live observer for all 604 physical tuning endpoints. The new timestep comparison checks corrected active-backend identities in input and completed receipts before waveform comparison, and waits for matching completed physical controls. No accuracy or corrected tuning-curve promotion is inferred. The old-backend timestep result cannot qualify the new backend. See `selected_keeper_corrected_BSIM_additional_captures_launch.json`.

### Corrected real-layout R pilot and PLLOUT packet audited (1339/1340/1348)

The real PLL pilot completes with one requested/extracted/exported net and 74 R cards. Exact ideal-R contraction preserves all 62,338 primitive calls, parameters and formal ports without shorting distinct reference nodes. Its observed node lineage verifies 228 initializations, 145 pointer reuses, 551 raw updates, 30 merges, 231 topological transfers and all 77 exported rnode values. No negative raw/final contributions or out-of-tile support remain; six half-area integer-rounding differences remain explicit. Capacitance conservation still fails only on PLLOUT–VGND, by +65.94475 fF. Native simulation/model promotion remains forbidden.

The offline PLLOUT packet completes with 179,345 selected events in about 62 MB. It reconstructs all 1,030 exported coupling pairs (65.944796012611 fF), identifies one substrate-relocated pair (6.750194631348116 fF), and verifies the selected ground-state history. Unrounded native final ground is 23.007617025460238 fF; native export rounding remains separate. Overlap shielding masks and ground geometry are still unresolved in this older trace. The packet and corrected R model provide numerical evidence for the next conservation/spatial work, not a qualified RC network. See `selected_keeper_PLLOUT_trace_packet.json`, `selected_keeper_PLLOUT_corrected_geometry_result.json` and `selected_keeper_corrected_R_geometry_audit.json`.

### Charge-conserving accounting control (1349)

The completed offline control retains all 1,364,255 original C-only capacitor cards literally, including their endpoints, and all native corrected-pilot resistor, device and port records. Exact ideal-R contraction preserves all 62,338 primitive calls and all 341,067 nonzero capacitance pairs with no negative capacitors. Three tests cover literal preservation, detection of native excess capacitance and rejection of nested subcircuits. This isolates export accounting for later comparisons; it does not repair native export or place capacitor terminals along the resistor network. Physical mapping, distributed-R qualification, simulation authorization and release readiness remain false. See `selected_keeper_retained_C_R_control.json`.

### Corrected-backend tuning collector prepared

A separate collector requires explicit corrected active-executable identities in both input and completed receipts, a hash-pinned protocol, unique predeclared fit/holdout roles, matching electrical domains and matching 604-endpoint physical assessments. It accepts only 10 ps points and checks a strictly interior independent holdout. Eight tests pass, including old-active-backend and completed-receipt rejection. No corrected curve has yet been collected; captures remain pending, and tuning-range, interpolation acceptance, model and release qualification remain false.

### Corrected tuning interpolation collection queued (1350/1351)

The live CPU-29 collector pins a three-point protocol before any corrected capture completes: fine 110/182 fit, fine 149 independent holdout. All three native controllers and physical observers are initialized; fine 182 has now acquired its lease and its actual corrected executable, PID birth and CPU-27 affinity are verified. The collector waits for completed native and physical receipts without modifying those jobs. This narrow interval cannot qualify the full tuning range or replace endpoint/corner measurements. See `selected_keeper_corrected_BSIM_TT_collection_launch.json`.

### Resolved overlap/fringe full-layout trace queued (1352)

A live CPU-28 controller verifies the unchanged checked GDS, isolated logging engine and eight native controls, then waits for a 16 GiB lease (24 h queue cap). One native extraction has a separate 1800 s cap and no retry. Unlike trace 1308, this engine records resolved overlap shielding and fringe support. Full-layout circuit/ledger/spatial audits remain pending; split geometries and ground placement are not promoted. See `selected_keeper_resolved_fringe_trace_launch.json`.

### Completed-trace support audit observer initialized (1353)

A live CPU-29 observer waits for the completed 1352 receipt and checks owner birth while waiting. Under an 8 GiB analysis lease, it verifies the full artifact closure, exact C-only circuit preservation, overlap shielding subtraction and fringe support integrals, then rechecks hashes. It does not read partial native traces. Nine existing overlap/fringe auditor tests pass. Split cases remain explicit and ground placement, distributed R, simulation authorization and release qualification remain false. See `selected_keeper_resolved_fringe_audit_launch.json`.

### Ground area/perimeter observer build started (1354)

An isolated source transformation preserves the original numerical ledger and adds support records immediately before its six ExtBasic area/perimeter additions. Records include tile/neighbor bounds, clipping rectangle, plane/residue, direction, split flags, native measure and coefficient. This supplies missing geometry rather than inferring it from the numerical ground delta. A source check finds all six expected original statements and inserts six observations. The live CPU-29/4-GiB builder verifies the pinned source before compilation; native neutrality and support reconstruction remain unverified. Existing source trees, PDK, GDS and running traces are untouched. See `selected_magic_ground_support_build_launch.json`.

### Ground-support reconstruction prepared

The new auditor independently reconstructs clipped rectangular area and neighboring edge length, checks split-area integer division while withholding rectangular qualification, and requires each support record to be immediately followed by its matching native ground update with exact double arithmetic. Five tests pass, including wrong geometry, bad arithmetic and truncation rejection. A four-fixture/eight-run native off/on runner is prepared; compilation and actual native validation remain pending. Area/perimeter support does not qualify shielding-subtraction geometry or full physical placement.

### Ground area/perimeter observer passes native controls (1354/1355)

The isolated build completes. Eight native off/on runs preserve each fixture circuit exactly and all prior coupling, ground, overlap and fringe ledgers reconstruct. The new support audit verifies 70 events across four fixtures (14 tile-area additions and 56 neighboring-edge additions), including immediate matching native numerical updates. No unsupported split support occurs in these controls. Clipped/split geometry has only unit coverage; native clipped/split controls, shielding-subtraction support and full-layout ground placement remain unqualified. See `selected_magic_ground_support_controls.json`.

### Ground overlap-shielding provenance prepared (1356)

The next isolated observer links the native area shielding subtraction at ExtCouple.c:522 to its completed resolved overlap mask by epoch, overlap ID, node and area. The auditor requires the immediately following native ground update to match the exact subtraction. Three tests pass for matching support/arithmetic and rejection of wrong support, wrong arithmetic and truncation. A fresh 4-GiB/CPU-29 build has launched; native validation is pending. Three separate fringe subtraction sites (halo truncation, resolved halo shielding, legacy side overlap) remain outside this area-specific proof. No spatial placement or RC model is promoted.

### Ground overlap-shielding links pass native controls (1356/1357)

Eight native off/on runs preserve fixture circuits exactly. The area/perimeter support, numerical ground/coupling, overlap-mask and fringe-integral audits all pass, as do 11 native ground-area shielding subtraction links to resolved masks and adjacent exact updates. Twelve ground-auditor tests pass. This qualifies the observed fixture bookkeeping, not spatial placement: native clipped/split coverage and three fringe-ground subtraction paths remain open, and full PLL/model/release qualification stays false. See `selected_magic_ground_overlap_controls.json`.

### Resolved halo ground subtraction observer started (1358)

A fresh isolated source transformation records callback begin/end around the native halo rule accumulator and observes its substrate subtraction immediately before the unchanged numerical ground update. Records bind node pair, clipped support, boundary, native substrate multiplier/fraction, accumulated shielding, coefficient and subcap. Pinned-source checks locate the exact callback and one subtraction. A CPU-29/4-GiB build has launched; compilation, callback reconstruction and native neutrality remain pending. Halo-tail truncation and legacy fringe paths are separate unresolved work. No native arithmetic or release tool is changed.

### Resolved halo ground bookkeeping passes native controls (1358/1359)

The isolated build and eight native off/on runs complete with exact fixture circuits. All prior numerical/support ledgers pass. The new audit verifies 19 halo callbacks and 8 ground subtractions: geometric initial fractions, native per-rule shielding accumulation, the original coefficient/fraction/length formula and immediately adjacent exact ground updates. Seventeen ground-auditor tests pass. The scalar accumulator proof complements the separately checked per-rule geometric supports; it does not qualify a final spatial redistribution. Halo-tail truncation, legacy paths, native clipped/split coverage and full-layout qualification remain open. See `selected_magic_ground_halo_controls.json`.

### Native halo-tail clipping controls complete (1360–1362)

The isolated observer records the exact native float multiplier, clipped search boundary, distance, fraction and ground subtraction. Four new tests pass (21 total ground-auditor tests). The original 1361 fixture completes its first native pair but stops postprocessing because it contains no tail events; it remains unqualified. A distinct 1362 fixture adds a nearby same-plane conductor and completes all eight native off/on runs with exact circuits and all prior ledgers/support checks. Its 8 actual tail events reconstruct geometry, native float precision, fraction, formula and adjacent ground updates. This is native clipping coverage for these rectangular fixtures, not full-layout qualification or a final spatial redistribution. Legacy fringe paths and split/native diagonal support remain open. See `selected_magic_ground_tail_parallel_controls.json`.

### Full checked-layout ground-support trace queued (1363)

A live CPU-24 controller pins engine 1360 and its eight native controls 1362, preserving the checked flat GDS. It waits for a 16 GiB global lease (24 h queue cap), then permits one native extraction with a separate 1800 s cap and no retry. The trace requests resolved overlap/fringe support plus native ground area/perimeter, overlap-shielding, halo-rule and halo-tail provenance. Existing queued trace 1352 and captures remain unchanged. Full-layout circuit, numerical and geometric audits are still pending; legacy paths, split geometry and final spatial redistribution remain unqualified. See `selected_keeper_ground_support_trace_launch.json`.

### Full ground-support audit observer initialized (1364)

A live CPU-29 observer waits for completed 1363 artifacts and verifies source owner birth while waiting. Its single ordered partition rejects unknown events and enforces source adjacency before writing reduced per-auditor streams. Three partition tests pass. All eight downstream audits (overlap, fringe, ground support, ground overlap, ground halo, ground tail, exported coupling and numerical ground) pass on each of the four completed 1362 native fixture traces. The full-layout worker additionally requires exact C-only circuit preservation and rechecks hashes. It records legacy-fringe event counts explicitly and never qualifies final placement or simulation. The actual full-layout audit remains pending. See `selected_keeper_ground_support_audit_launch.json`.

### Native ground-support coverage cross-check prepared

A new cross-check compares each of the six native area/perimeter mutation-site counts and each of the three supported subtraction-site counts against the geometry records. It rejects unknown native mutation sites, missing records and compensating per-site count errors; three tests pass. All nine counts match individually on all four completed 1362 fixture traces. The complete 18-site inventory also reports resets, substrate relocation updates and unsupported legacy subtraction explicitly. Full-layout coverage remains pending and no spatial placement qualification is inferred. See `selected_magic_ground_support_coverage.json`.

### Bounded conditional replay memory benchmark initialized (1365)

The live CPU-29 controller uses completed old-backend 50 ps capture 1278 and matching 604-endpoint physical pass 1279. It verifies exact old-backend pins and prepares captured boundary sources under an 8 GiB analysis lease. One conditional replay uses the same old binary and 50 ps maximum step, an 8 GiB address-space limit, a 1800 s native cap and GNU time peak-RSS logging; no identical retry. PLLOUT remains free. Two backend guards pass. This tests whether the reduced native workload can run with a smaller reservation; neither the original 64 GiB queues nor any capture is changed, and no corrected-backend memory, timestep, predictive-model or release qualification is inferred. Launch is verifying completed inputs; native execution remains pending. See `selected_keeper_replay_memory_benchmark_launch.json`.

### Reduced replay native benchmark started (1365)

Boundary preparation completes with 6,454 samples and 7,616 driven ports: 33 constant sources and 7,583 nonconstant sources produce 48,940,748 PWL points without lossy compression. Native Xyce is live parsing the sources. Its actual executable hash, PID birth, CPU-29 affinity and inherited 8 GiB address-space limit are verified independently of the GNU time wrapper. Completion, final peak RSS and replay comparisons remain pending; an interim RSS is not a memory qualification. See `selected_keeper_replay_memory_native_launch.json`.

### 8 GiB replay benchmark stops during netlist parsing (1365)

The completed source set contains 48,940,748 PWL points. Xyce terminates by signal 11 while parsing, after 148.75 s and 8,177,664 KiB peak RSS under the verified 8 GiB address-space cap. The controller records exit 139 and no completed replay. GNU time's trailing exit-status line is not used to override its signal-termination report. This is consistent with allocation exhaustion near the cap, but no fault stack proves the cause. An 8 GiB reservation is not supported; original 64 GiB jobs remain unchanged. No frequency, accuracy, memory reduction or speedup result is inferred. The failed run is retained and not identically retried. See `selected_keeper_replay_memory_benchmark_failure.json`.

### Native PWL parser storage diagnosed (1366)

Source inspection of the pinned Xyce build shows that PWL FILE input still adds generic T/V instance parameters for each pair; Util::Param copies clone the value object. A compiled sizeof probe using the actual build flags measures Device::Param at 56 bytes and ParamData<double> at 24 bytes. For the 48,940,748-point replay, two parameters plus value objects nominally occupy 7,830,519,680 bytes (about 7.29 GiB), before allocator metadata, vector capacity, parser tokens or other simulator storage. This accounting explains why an 8 GiB cap has little headroom; it is not a completed peak-memory measurement or proof of the crash cause. FILE syntax alone is not a demonstrated fix. No simulator source is modified. See `selected_xyce_PWL_parameter_storage.json` and `tools/xyce_umfpack/pwl_parameter_sizes.cpp`.

### TABLEFILE boundary-source controls pass (1367/1368)

The existing expression TABLEFILE constructor reads numeric arrays directly instead of generic PWL T/V instance parameters, uses linear interpolation and retains time-knot breakpoints by default. Twelve native controls (old and corrected binaries; constant, irregular ramps and plateau cases; PWL and TABLEFILE encodings) complete. Every source matches its literal piecewise-linear samples within the 1e-12 V fixture tolerance, contains every sample-knot breakpoint within 1e-21 s and holds the final value after the file ends. No downsampling argument or FASTTABLEFILE is used. Attempt 1367 stops postprocessing on an overly strict exact endpoint equality; v2 uses the same fixture time tolerance for endpoint validation and the original result remains stopped. Full PLL memory/runtime and replay accuracy are not yet measured. See `selected_xyce_TABLEFILE_boundary_controls.json`.

### Full sampled-boundary TABLEFILE benchmark initialized (1369)

The literal generator writes each nonconstant sample with 17 significant digits into a separate TABLEFILE input, retaining the existing exact-constant endpoint reduction and excluding PLLOUT. Two tests verify numeric round-trip and role/finite-data rejection. The live CPU-29 benchmark reuses the completed 1365 boundary array after checking capture/plan identity, pins the twelve native source controls, and hashes every external data file before and after execution. One old-backend 50 ps replay has the same 8 GiB native limit and 1800 s cap as the failed inline-PWL benchmark. This changes source representation, not the simulator binary or captured values. Native peak RSS, completion, accuracy and speed remain unmeasured; original capture/replay queues remain unchanged. See `selected_keeper_TABLEFILE_replay_memory_launch.json`.

### Local boundary staging prepared after small-file I/O control (1370)

An alternating local/shared control writes and verifies 16 files of 256 KiB per round without fsync. Shared write/close takes 1.17–1.32 s versus 0.0057–0.0095 s locally under current load; this is a small I/O control, not a full source-generation speedup. A prepared staging wrapper generates TABLEFILE data under local scratch and retains a deterministic, hash-verified archive on shared storage. Two tests verify exact archive contents, stable metadata and rejection of changed/uninventoried files. The local source path is recorded and retained; automatic relocation is not performed. No second full preparation is launched while benchmark 1369 uses the remaining lease. Full staging/runtime measurements remain pending. See `selected_boundary_file_IO_control.json`.

### Explicit PLLOUT interconnect scale screened (1371)

The charge-conserving accounting control contains 74 positive wire R cards on 59 connected PLLOUT nodes. The largest shortest series-resistance path is 948.61147 ohm (not an effective-resistance diameter); resistor-card sum is 6182.6630133 ohm. The same literal SPICE control has 678 incident positive explicit C cards totaling 88.87172 fF, with no intra-component C cards. Their series-diameter product is 84.3047 ps. This is an explicit interconnect screening scale, not an active delay/phase bound: intrinsic device capacitances, placement and driver/load response are unqualified. Two tests cover parallel resistors, capacitance scope and invalid networks. This result does not requalify upstream dependency closures or promote the anchored control to simulation. See `selected_keeper_PLLOUT_RC_scale.json`.

### PLLOUT EXT-to-SPICE quantization reconciled (1372/1373)

All 1,030 PLLOUT coupling endpoint pairs map one-to-one between checked EXT and literal SPICE. Of these, 352 positive sub-attofarad values print as zero, totaling 0.080732972611 fF (largest 0.966448 aF); 677 positive printed values contribute a net +0.00005696 fF rounding delta. One native negative residual of -1.2595e-36 F also prints zero and is retained in the exact signed identity. Thus EXT coupling 65.944796012611 fF becomes 65.86412 fF in SPICE, with printed ground 23.0076 fF separately accounted. Source inspection finds esSIvalue leaves values below 1e-18 F unscaled before five-decimal fixed formatting. Initial strict nonnegative-native analysis stops before output creation; the signed-residual audit passes three tests and exactly reconciles the discrepancy. This records finite export precision, not a dynamic frequency/phase bound, passivity defect or model promotion. Current captures and stock tools remain unchanged. See `selected_keeper_PLLOUT_C_export_quantization.json`.

### Full TABLEFILE native replay started (1369)

All 7,616 source files and their receipt complete verification, and the bounded native replay launches. The actual old-backend executable hash, PID birth, CPU-29 affinity and inherited 8 GiB address-space limit are verified independently of the GNU time wrapper. Native parsing has progressed to device/model setup. An interim RSS is not a completed peak measurement; normal replay completion, waveform comparison and final memory/runtime remain pending. This benchmark retains the known old backend solely for comparison with its completed reference; corrected-backend qualification remains separate. See `selected_keeper_TABLEFILE_native_launch.json`.

### Completed TABLEFILE replay comparison observer initialized (1374)

A live CPU-29 observer waits for normal completion of 1369, verifies waveform/model identity and artifact closures, and then compares its free PLLOUT with the identical completed captured reference. It reports final-window frequency and rising/falling edge differences with the existing equal-count/ordinal-pairing limitations. Five waveform helper tests pass. The actual replay is still simulating; partial RAW is not analyzed. Sampled-boundary consistency, numerical convergence and an independently predictive changed-controller model remain distinct unqualified work. See `selected_keeper_TABLEFILE_replay_comparison_launch.json`.

### Shared boundary breakpoint controls queued (1375)

TABLEFILE replay 1369 is live in transient simulation with bounded memory but slow early progress. Source inspection shows each table can request the same captured time knots. A distinct twelve-control campaign compares PWL against FASTTABLEFILE plus one independent zero-valued PWL carrier requesting every original knot; its resistor closes the carrier branch without driving a physical port. This intends to preserve the global time-knot set while avoiding per-table duplicate breakpoint requests. The live CPU-29 controller waits for a 2 GiB lease (2 h queue cap); its 600 s native campaign deadline begins only after acquisition. No native results or PLL performance are available yet, and no existing run changes. See `selected_xyce_shared_TABLEFILE_controls_launch.json`.

### Keeper declared RTL linked to completed divider induction (1376)

The current route database and all nine declared RTL source hashes verify. The declared divider RTL is byte-identical to the completed divide-by-16 induction proof; the proof/negative-control input and artifact closures and native success/failure logs verify inside the pinned image. Pinned-format declaration checks bind ratio 16, width 5, register-config 0, countdown 1 and configuration-pipeline 0 through the current wrapper/core source. Three guard tests reject ratio, pipeline and parameter-forwarding changes. This is explicit source-level property reuse, not a fresh elaboration/formal run or routed-netlist equivalence. Propagated clocks, CDC/reset timing and the digital timing gate remain unqualified. See `selected_keeper_divider_RTL_binding.json`.

### Shared-knot source generator prepared with native-control guard

The prepared generator retains every literal TABLEFILE sample, switches the table expressions to FASTTABLEFILE and adds one independent zero-valued PWL carrier containing the complete original time column. It rejects an auxiliary-node/physical-port collision and leaves PLLOUT unforced. Full generation requires the completed twelve-run 1375 native control receipt before proceeding. Local staging now accepts `--shared-knots` and records/pins the selected generator. All six source-generation/archive tests pass. The native controls are still queued and no full shared-knot replay or performance result is claimed. Existing active source banks and benchmark 1369 remain unchanged.

### Tracking-property model reconstruction queued (1377)

Archived campaign 002 has a completed baseline PDR proof but no final assessment because its inverted-assertion PDR control times out. The separate completed BMC control demonstrates reachability at frame 64 and pins both model/source variants. A live CPU-28/2-GiB job verifies that receipt, compares current ProgrammedCore instrumentation with the recorded positive/negative cuts, checks all nine current source inputs, and rebuilds both AIGs from the original source paths with only export destinations changed. Both hashes must exactly match the recorded models before property reuse is published. The job has a 2 h queue cap and a separate 600 s export cap, and does not rerun induction or alter RTL. Source/model binding is pending; initial seed loading, full-core behavior, routed equivalence and physical CDC/reset timing remain unqualified. See `selected_keeper_tracking_RTL_binding_launch.json`.

### Current tracking formal models exactly reconstruct (1377)

Both current-source Yosys exports exactly match the recorded baseline and inverted-stability AIG hashes. This binds the completed baseline PDR induction and bounded reachability result to the current keeper route's declared RTL under the retained conservative free-core/free-feedback-clock cut. Sampled tracking configuration stability and ready/running fine-payload agreement with static presets are proved under the recorded reset/static-preset assumptions. No induction is rerun. Initial seed loading, full-core behavior, routed-netlist equivalence and physical CDC/reset timing remain unqualified. See `selected_keeper_tracking_RTL_binding.json`.

### Shared-knot controls pass; local full replay started (1375/1379–1381)

All twelve shared-knot native source controls pass on both binaries, preserving literal values (maximum error 2.22e-16 V), every tested knot and final-value hold. Earlier per-table replay 1369 reaches its 1800 s native cap with last reported progress 27.0657%; parsing and DC finish, but no completed waveform or final peak-RSS receipt exists and its comparison correctly stops. Its partial RAW is not analyzed. Distinct source staging 1379 generates the complete shared-knot bank locally in 139.84 s and archives/verifies it in 39.62 s. A CPU-24/8-GiB replay now runs from that verified bank, retaining all samples and free PLLOUT, with a finite four-hour native cap and no identical retry. Its completed-waveform observer is live. Native source encoding, staging and budget differ from 1369; full replay accuracy and native speedup remain pending. See `selected_xyce_shared_TABLEFILE_controls.json`, `selected_keeper_TABLEFILE_replay_timeout.json`, `selected_keeper_local_shared_source_staging.json` and `selected_keeper_local_shared_replay_launch.json`.

### Explicit coarse-band capture preparation

A new corrected-backend capture runner accepts explicit coarse code 0–47 and maximum step 10 or diagnostic 50 ps, preserving fine headroom 8–247. It rewrites and validates all six startup coarse voltage sources and checks the observed final-window coarse/fine word against the requested values. Three tests cover 24 code/step combinations, incomplete/invalid interfaces and byte-identical default behavior. The actual checked smoke deck remains byte-identical to the prior coarse-20/10-ps generator at fine 8/149/247. No new coarse-band case is launched or selected without measured tuning evidence; all active captures remain unchanged.

### Conditional capacitor-only boundary inventory (1382)

The exact conditional native model has 7,616 driven ports: 306 are used by primitive/device or other noncapacitor cards, while 7,310 appear only in linear positive capacitors. Of the latter couplings, 32,924 connect prescribed boundary voltages only; 795 connect to 188 internal targets (maximum 464 distinct exterior neighbors per target). For unchanged ideal boundary histories and interior-voltage observables, capacitor superposition projects 306 direct plus 188 weighted forcing waveforms (494 total), and 60,000 explicit capacitors instead of 93,531. Eliminated boundary-source currents and power would not be retained. Two inventory tests pass. No model is transformed, and native equivalence, aggregation roundoff, changed-controller prediction and speedup remain unqualified. See `selected_keeper_capacitor_boundary_inventory.json`.

### Symbolic capacitor-boundary reduction and native controls queued (1383/1384)

The new offline transformation preserves primitive/wrapper records and exact retained-node charge coefficients while replacing capacitor-only prescribed boundary couplings with capacitance-weighted virtual voltage ports. It separates synthetic forcing nodes from physical-node bindings, retains device-connected boundary ports, and emits exact rational coefficient certificates. Three tests pass, including independent rational-voltage charge comparisons and unsafe-card rejection. Native simulation is explicitly disabled in the output pending qualification.

A separate bounded 24-run native campaign compares original and weighted RC networks on both Xyce binaries, three waveform cases and two reciprocal resistance/capacitance scales. Every completed waveform must match an independent closed-form first-order response and retain each source knot. Three closed-form helper tests pass. Both controllers are live and queued for 2 GiB leases; native results, actual PLL aggregation roundoff, replay equivalence and speedup remain pending. Existing captures are unchanged. See `selected_keeper_capacitor_boundary_reduction_launch.json` and `selected_capacitor_boundary_superposition_controls_launch.json`.

### Weighted forcing waveform helper with exact roundoff audit

The prepared helper copies direct forcing and observed PLLOUT samples unchanged, retains every time knot, and generates each virtual voltage from certified positive capacitance weights. It independently computes the exact rational weighted sum of the captured binary floating-point voltages at every sample and records the maximum absolute rounding error as an exact fraction. For common-grid PWL interpolation, the endpoint-error maximum also bounds source-voltage error between knots. Three tests cover exact samples, nonbinary-weight rounding, malformed coefficients and attempted observation forcing. This is a source-error audit, not a bound on nonlinear PLL phase/frequency error. No full waveform generation or reduced native replay has run; native simulation permission and all model/dynamic qualification flags remain false.

### Completed-input weighted waveform generation runner prepared

`generate_keeper_aggregate_waveforms.py` requires completed hash-verified full-reference boundary arrays, the symbolic reduction certificate and all 24 closed-form native RC controls before acquiring a 2 GiB lease. It writes reduced arrays, port roles and exact sample-roundoff receipts, rechecks input hashes and leaves native simulation/dynamic/model qualification disabled. The runner passes syntax compilation but is not launched because its native control prerequisite remains queued. Full generation and reduced replay are still pending.

### Audited waveform follow-up controller live (1385)

The generation runner now has an explicit 24 h completed-prerequisite observer, checking each producer's PID/birth identity and terminal status. A live CPU-29 controller waits for symbolic reduction 1383 and all native RC controls 1384 before requesting its own 2 GiB lease. It consumes no analysis lease while waiting, limits numerical-library threads to one, does not retry failed prerequisites and never launches native PLL simulation. Generation and all replay/dynamic qualification remain pending. See `selected_keeper_aggregate_waveforms_launch.json`.

### Full-core initial-seed proof binding queued (1386)

The completed full-core baseline induction in `prototype_v3_tracking_configuration_proof_002` and legal-clock reachability witness 002 declare the same nine RTL hashes as keeper route 1136. A new live controller verifies their completed evidence and reconstructs both AIGs from current declared source paths before accepting reuse. The deterministic witness constraints are extracted literally from the hash-pinned witness producer and apply only to the negative control. A 2 GiB lease, 2 h resource queue cap and separate 600 s export cap bound the reconstruction. No new induction is requested. Binding is pending; physical CDC/reset timing, routed equivalence and full-core behavior qualification remain open. See `selected_keeper_seed_RTL_binding_launch.json`.

### Reduced-boundary native replay benchmark prepared

The prepared diagnostic runner binds the symbolic reduction, exact sample-roundoff receipt, original completed reference, physical tuning checks and locally archived shared-knot source bank before one bounded old-backend replay. It retains the existing 8 GiB/one-core/four-hour native limits, free PLLOUT and 50 ps diagnostic step, and records runtime, peak RSS and completed-reference frequency difference. Aggregate samples are explicitly distinguished from the original physical samples; numerical/dynamic/reduced-model qualification remains false. One integration test passes through reduction, audited array generation, source bank generation and complete free-output deck construction. Syntax compilation passes. No native reduced benchmark is launched because completed reduction/control/waveform/staging inputs remain pending.

### Full-layout ground update coverage follow-up queued (1387)

A live CPU-29 observer waits for completed full-layout support audit 1364, verifies its input/artifact closure and the exact engine mutation inventory, then requests 2 GiB to compare all six area/perimeter and three shielding-subtraction event counts with the native numerical ledger. Resets, substrate relocation and any legacy-ground events remain explicitly classified. Three coverage tests pass. Observation is bounded to 48 h; memory admission to 6 h. No active native extraction changes. Full-layout counts are pending and spatial placement/distributed-R qualification remain false. See `selected_keeper_ground_support_coverage_launch.json`.

### Completed reduced/unreduced replay comparison prepared

The new comparator requires normally completed finite unforced replays with matching executable, maximum step, shared-knot representation, original conditional model and full-reference identities. It compares the observed output edge/frequency diagnostics and reports peak RSS plus single-run runtime ratio. Runtime is read from each native GNU time receipt, excluding controller resource-admission delays. Three tests cover compatible conditions, rejection of changed/incomplete cases and elapsed-time parsing. No dynamic error tolerance is invented; reduction error, changed-controller prediction and release qualification remain false. Actual comparison is pending a completed reduced replay.

### One-shot reduced replay pipeline live (1388–1391)

A live observer waits for completed audited aggregate waveforms 1385, then stages and archive-verifies their shared-knot source bank (1389), requests one bounded 8 GiB diagnostic native replay on CPU 25 (1390), and compares completed reduced/unreduced captures (1391). CPU 25 avoids sharing the current original replay's CPU 24. The pipeline pins its producers, refuses existing output directories and performs no automatic retry. Observation is bounded to 24 h; staging, native execution and comparison retain their individual resource/deadline controls. No model promotion or release tolerance is implied; all actual native reduction and speedup results remain pending. See `selected_keeper_aggregate_pipeline_launch.json`.

### Corrected capture, exact seed-proof binding and symbolic reduction complete

Corrected-backend 50 ps capture 1341 completes normally in 15,657.25 s with finite saved values, stationary coarse 20/fine 149 and a 372.921866 MHz final-window diagnostic. Physical tuning observer 1342 is still processing; timestep convergence and the 400 MHz bracket remain unqualified. The result does not transfer the old backend's frequency.

Seed binding 1386 exactly reconstructs baseline AIG `de8da1101863be806d9f36c157bb67e614a91fb588b5e93861824161149b7501` and legal-clock witness AIG `8184fdafdd960c12115c797b548f42db3d53673b0dbd49a18162c9d08d3f0cc5`. This reuses the completed full-core initial sampled tracking-code/seed and stable-configuration proof under its reset/static-preset/discrete-clock assumptions; no fresh induction is run. Physical CDC/reset timing and routed equivalence remain open.

Symbolic reduction 1383 preserves all 10,147 primitive calls and produces 494 forcing ports and 60,000 explicit capacitors, matching the inventory projection. Native equivalence remains unqualified. RC controls 1384 stop at the first opposed-ramp slope corner with time step too small, zero nonlinear convergence failures and zero failed linear solves; their waveform/pipeline dependents stop without qualification as intended. Distinct controls 1392 use Gear integration (confirmed supported in the pinned Xyce source) with unchanged waveforms, accuracy acceptance and budgets. The new controller is live and waiting for 2 GiB; no identical failed campaign is retried. See `selected_keeper_corrected_BSIM_step50_capture.json`, `selected_keeper_seed_RTL_binding.json`, `selected_keeper_capacitor_boundary_reduction.json` and `selected_capacitor_boundary_superposition_Gear_launch.json`.

### Gear-control follow-ups connected (1393–1397)

New live waveform observer 1393 requires completed Gear controls 1392 and the already completed symbolic reduction. A new versioned pipeline observer 1397 waits for those audited samples, then uses new source-staging/replay/comparison outputs 1394/1395/1396. Both observers hold no analysis lease while waiting. Prior failed control and stopped follow-up outputs remain untouched, no native replay starts before completed prerequisites, and the old-backend diagnostic scope and existing resource limits remain unchanged. See `selected_keeper_aggregate_Gear_followups_launch.json`.

### Local resolved-trace staging prepared

The live resolved-support trace writes tens of gigabytes directly to shared storage; native replay and filesystem observers show I/O waits while disk capacity remains ample. A distinct prepared runner keeps the same engine, checked GDS, equations and native/resource caps, redirects only the hot trace stream to local scratch, and requires at least 256 GiB free before native execution. After normal completion, a new retention helper copies the closed trace in 8 MiB blocks, checks source identity/size/timestamps, independently verifies source and destination SHA-256, and publishes the checked shared copy by rename. Local originals remain retained. Two tests pass for exact binary retention and refusal of incomplete/existing outputs; syntax compilation passes. No replacement extraction is launched while the original process remains live, including I/O wait beyond its nominal cap. Native performance and full-layout audit remain pending.

### Corrected physical controls pass; bounded recovery campaigns queued

Physical observer 1342 completes with all 302 tuning bits and 604 macro/DCO endpoints matching coarse 20/fine 149, zero mismatches and 6,463 captured samples. This binds the completed corrected 50 ps diagnostic to the actual physical tuning controls; timestep accuracy, the 400 MHz bracket and other corners remain open.

Resolved trace 1352 exhausts its 1,800 s native budget; its SIGTERM remains pending during uninterruptible filesystem I/O before the process finally exits. The partial trace is not audited. Distinct local-staging extractor 1400 and completed-only audit observer 1401 are now queued with the same checked engine/GDS and native cap; the original process was confirmed absent before launch.

Gear RC controls 1392 also stop at the first PWL slope corner with time step too small and zero nonlinear/linear convergence failures. Pinned Xyce source confirms ERROPTION=1 bypasses predictor/corrector LTE rejection while retaining nonlinear success checks. Distinct controls 1398 use that mode, a 100 fs maximum step and 1 fs initial step, with the unchanged 1e-7 V closed-form acceptance limit and all source-knot checks. They remain queued; no success or general simulator fix is claimed. The failed Gear follow-ups remain stopped, and further replay follow-ups await passing controls. See `selected_keeper_corrected_BSIM_step50_physical.json` and `selected_keeper_bounded_recovery_launch.json`.

### Runtime CPU collision removed (1406)

Live `/proc` affinity checks show ground-trace native PID 2209460 and replay PID 2187464 both initially bound to CPU 24. After verifying PID/birth identities and the previous CPU-28 extraction's exit, the ground trace's single thread moves to CPU 28; replay remains on CPU 24. The queued local-trace controller 1400 moves from initial CPU 28 to free CPU 30 so its native child inherits a separate core. These are explicit runtime overrides of initial affinity declarations; frozen input files, core counts, memory limits, equations and deadlines are unchanged. Consecutive observations show each active native job accumulating approximately 60 CPU seconds during 60 elapsed seconds after separation. This is a scheduling observation, not a measured end-to-end speedup. Single-run benchmark timing includes this intervention and other concurrent workload effects. See `selected_ground_trace_CPU_rebalance.json`.

### Completed-capture early-settling analysis queued (1407)

A live CPU-25/2-GiB job verifies completed corrected capture 1341 and physical controls 1342, then compares early-window frequency/period/amplitude diagnostics with the final 200–260 ns window. It checks all 604 physical endpoints at every saved sample and reports the last mismatch and first sample after which every saved control remains correct. Early windows lacking enough edges are retained as unavailable evidence. Four tests cover stable windows, late control failure, absent early oscillation and truncated/misaligned data. The analysis does not shorten any live run or qualify another code/corner/timestep; it may inform a later shorter-capture experiment only after measured results. See `selected_keeper_early_settling_launch.json`.

### Local native outputs prepared for reduced replay

A versioned reduced-replay runner keeps native RAW, stdout/stderr and GNU time output on local scratch with an initial 1 GiB free-space check. It pins the chosen output paths, runs the same guarded model/source/backend case, then retains all three closed outputs through the independently tested hash-verifying retention helper before waveform analysis. Local originals and retention receipts remain available. Existing live replay and frozen producer versions are unchanged. Syntax compilation passes; native end-to-end performance/accuracy remains unmeasured and this runner is not launched before passing RC controls and completed audited sources.

### Completed RC controls, unreduced replay and aggregate forcing (1380/1381/1398/1399/1407)

All 24 fine-step original/weighted RC controls complete on both binaries and both capacitance/resistance scales. Their largest closed-form voltage error is 2.61258e-11 V, below the unchanged 1e-7 V fixture limit, with every source knot checked. This fixture result does not qualify the PLL reduction or its dynamic error.

The completed old-backend shared-knot replay peaks at 5,013,188 KiB RSS under its 8 GiB limit and reports 374.262578 MHz versus its identical 373.860225 MHz full reference: +1,076.21 ppm. Ordinal final-window rising-edge differences reach 85.36 ps with a 63.26 ps span; falling-edge differences reach 82.75 ps. Equal edge counts do not prove absence of slips. These are measured errors, not a correlation/accuracy acceptance or corrected-backend result. Its approximately 2 h 57 min native interval includes shared-I/O and recorded scheduling effects and differs in output scope from the full capture.

Completed corrected-capture early-settling analysis finds no adequate oscillation edges in windows through 160 ns. Physical controls match at every saved sample only from 109.083776 ns; the 140–200 ns frequency differs from the final window by -738.11 ppm. This evidence does not support simply shortening reference captures.

Aggregate forcing generation 1399 completes exact per-sample roundoff auditing; the largest source-voltage discrepancy is `35207/124979393259158634496` V (about 2.82e-16 V). New pipeline 1405 stages sources 1402, runs local-output native replay 1403 and will compare completed reduced/unreduced outputs in 1404. The actual Xyce PID/birth, old executable path, CPU 25 affinity and 8 GiB address-space limit are verified live in observation 1408. Native reduction equivalence, speedup and release qualification remain pending. New pipeline sources and completed/launch receipts are retained alongside these results.

### Voltage-LTE current masking controls pass; controlled PLL comparison live (1409–1411)

Pinned Xyce `TIAParams` and `DataStore` source confirms MASKIVARS=1 assigns machine-large LTE weights to current-type variables while preserving voltage-variable weights and nonlinear convergence checks. All 24 original/weighted RC controls pass at the original 50 ps maximum step with voltage LTE retained. Their worst closed-form voltage error is 6.87530e-8 V under the unchanged 1e-7 V fixture limit. This tests a more targeted setting than ERROPTION=1; it does not qualify PLL phase/frequency accuracy.

A distinct one-case old-backend reduced replay 1410 uses the same model and staged forcing as default replay 1403, changes only MASKIVARS, and keeps local outputs, the 50 ps cap and 8 GiB limit. Its actual native child is verified on CPU 24, separate from default replay CPU 25. Observer 1411 waits for both normal completions, verifies identical model/reference/source identities, and requires deck equality except that single directive and output destination before reporting waveform/runtime/RSS differences. Four tests reject mismatched backends/steps, missing voltage control, two masked cases, and other deck changes. Both accuracy acceptance and general speedup remain unqualified. See completed controls 1409 and `selected_keeper_MASKIVARS_replay_launch.json`.

### Corrected adjacent coarse-band probe live (1412–1414)

Original old-backend fine-112 capture 1213 completes normally at stationary coarse 20/fine 112 with a 10 ps maximum step and a 366.742137 MHz final-window diagnostic. It saves selected top signals, so it does not supply the later all-604-endpoint physical check. Its frequency must not be combined with the 50 ps or corrected-backend points as a qualified gain fit.

Completed corrected coarse-20/fine-149 capture 1341 and its all-604-endpoint check are below 400 MHz. A new explicitly exploratory corrected coarse-19/fine-149 capture 1412 uses the same checked physical model, 50 ps diagnostic maximum step, 16 GiB limit and one core (free CPU 20). Its existing parameterized capture producer validates all six startup coarse sources. Observer 1413 waits for normal completion and checks all 302 tuning bits at both endpoints. The prior fit/holdout jobs remain unchanged. This single adjacent-band experiment does not prove coarse-20 unreachability or select/qualify coarse 19. See `selected_keeper_coarse19_probe_plan_1414.json` and `selected_keeper_coarse19_probe_launch.json`.

The retention checkout now uses an independent Git clone on local scratch to avoid the observed NFS object-write stalls. Simulation workers and frozen input/artifact paths remain in the original workspace. The local clone passes the existing 19 helper tests before synchronization; the four current-mask comparison tests are checked separately after synchronization.

### Completed aggregate replay and prescribed receiver boundary (2026-11-08)

The completed old-backend TT coarse20/fine149 replay1403 and comparison1404
retain all shared source knots and use the exact capacitor reduction1383.
Native GNU-time elapsed is6109s versus10612s unreduced (one-run ratio1.737),
peak RSS1448788 versus5013188KiB. Frequency differs by-0.604690ppm; maximum
absolute final-window rising/falling edge differences are1.274891/1.271350ps.
Output sampling grids differ; this does not establish timestep convergence,
a dynamic aggregation error bound, corrected-backend qualification, or release readiness.
The original full-reference discrepancy remains approximately1076ppm.

Static causality audit1415 binds the reduced model and completed physical1279
plan:302 macro programming endpoints, one reset, two supplies,188 aggregate
capacitor forcing inputs, and one other prescribed node `a_61378_74686#`.
Eight four-terminal MOS wrapper calls have PLLOUT on the gate and that
prescribed node on a source/drain terminal. The literal wrappers preserve
p0/p1/p2/p3 ordering into the PDK MOS calls. Thus the replay also prescribes
a receiver output; freeing PLLOUT alone does not make the environment causal
under changed controller histories. An independent plant must resolve or
bound this receiver/downstream loading and replace or qualify sampled
capacitor forcing before controller-change predictions can be accepted.
The audit reports terminal positions and hashes, without claiming a dynamic
error bound. Three tests cover receiver detection, supply exclusion and
missing physical controls. All model/release qualification flags remain false.

### Unclamped first receiver output (2026-11-08)

`expand_keeper_receiver_boundary.py` produces experiment1416 from the same
flat source and conditional1241: all32 previously omitted MOS devices
incident to `a_61378_74686#` are retained. That node is now internal and
unforced, all previous internal unknowns remain internal, and every retained
primitive/capacitor card is unchanged. The expanded circuit has10179
primitives,93813 nonzero capacitors,7680 boundary ports and3186 internal
nodes. New capacitor boundaries are explicitly listed in the receipt.
Its remaining non-control/non-reset/non-supply transistor boundary is
`IntegerPLL_ProgrammedCore_0.sky130_fd_sc_hs__clkbuf_16_123.A` (32 terminal
uses). This shifts the receiver cut downstream; it does not establish an
autonomous clock tree or eliminate the prescribed environment. No native
run or controller prediction is claimed. Three tests verify the downstream
frontier and literal capacitor preservation, reject a formally exposed
receiver that cannot become internal, and reject an empty expansion.

### Isolated coupling-import export control (2026-11-08)

Source review of stock Magic8.3.623 identifies `ResReadCapacitor` in
`resis/ResReadExt.c`: when `ResOpt_Signal` is set, it adds each explicit
coupling value to both endpoint substrate capacitances. `ResRex.c` sets
that option for resistance extraction and passes `node->capacitance` into
`rg_nodecap`; `ResSimple.c` distributes that value into the resistor network.
The existing native fixture shows explicit coupling remains exported.

Experiment1417 builds an isolated stock-source variant that removes only
this signal-mode grounding block, retaining the existing `cap_couple`
accounting. It does not replace the release executable, mutate PDK/layout,
or include earlier geometry fixes. Experiment1418 waits for the checked
build, then repeats the original coupling-on/off fixture on both stock and
modified executables, requiring stock-on to reproduce the difference and
the other three cases to produce byte-identical before/after exports.
The build uses one CPU28 and4GiB; each native fixture has a300s cap. Two
transformation tests pass. Build/control completion is not yet claimed in
the launch receipt. This is an export diagnostic, not a general coupling
placement or delay/simplification fix: the small fixture does not exercise
a qualified distributed-R network, and changed lumped-C heuristics need
separate validation. No PLL model or release qualification follows.

### Native translated expanded receiver, exact reduction (2026-11-08)

Experiment1419 translates receiver expansion1416 with the same checked
physical source/backend translation provenance as1242. The translation
checks every nonzero capacitor endpoint and value and reversible physical
node mapping. Experiment1420 reduces only capacitor-only prescribed ports:
10179 primitive calls remain unchanged,93813 capacitor cards become60009,
7373 ports are eliminated, and189 aggregate forcing inputs plus306 direct
inputs remain. The exact charge-coefficient certificate is retained in
build output; no native equivalence is claimed for this new circuit.

Causality audit1421 finds zero PLLOUT-gated MOS calls whose source/drain is
prescribed, versus eight before expansion. Its one other direct prescribed
boundary remains the downstream clock-buffer node documented for1416.
Sampled capacitor forcing also remains. The portable audit summary pins
the full static report and records that downstream boundary; all dynamic,
changed-controller prediction and release flags stay false. No new
transient or independent causal model is claimed by these static steps.

### Completed isolated coupling import controls; receiver replay queued

Build1417 and all four native controls1418 completed normally. Stock Magic
reproduces the extra3.91111fF substrate term with coupling on; coupling-off
is unchanged. Both modified cases have byte-identical before/after SPICE.
The `.res.ext` rnode term is3911.11 for stock-on and0 for modified-on;
explicit A-B coupling remains3.91111fF. This fixture has no distributed R
network, so it confirms this import path without qualifying R segmentation,
coupling attachment, simplification or the full PLL model. A nonzero-R
control is required before extending the conclusion.

Pipeline1424 binds expanded receiver1419 to the completed full50ps
capture1278 (plan1422), extracts its complete boundary histories1423,
uses reduction1420 and native RC controls1398 to audit weighted forcing1425,
stages shared-knot sources1426 and permits exactly one4h/8GiB old-backend
receiver replay1427 on CPU25. It preserves the reference260ns duration,
50ps maximum step, all knots and physical programming code; no retry is
automatic. The purpose is a controlled loading-sensitivity comparison
against the first-clamped replay1403, not changed-controller prediction.
Its launch receipt does not claim completed native simulation.

### Failed two-port R controls and live receiver replay (2026-11-08)

Native1428/1429 use separate A/AFAR port labels on one conductor and
threshold0. Both modified and stock Magic terminate with SIGSEGV after
the shorted-port warning and extraction start. Distinct stock1430 changes
threshold to1 and also crashes. All three native input sets were verified
inside the tool container. These are retained failures, not passing R
controls; neither crash cause nor coupling-change responsibility is known.
No completed resistor export exists. A supported nonzero-R control, such
as the completed PLLOUT74-R pilot, is still required with geometry and
coupling changes controlled separately.

Receiver replay1427 is running after complete waveform preparation, on
verified actual CPU25 with the pinned old backend and8GiB cap. No partial
waveform analysis or completed loading conclusion is reported.

### Combined geometry and explicit-coupling PLLOUT control queued

Build1431 composes the exact source transforms from geometry engine1334
with the explicit-coupling import diagnostic1417, in a new isolated source
tree and installation. Pipeline1434 runs four native stock/combined
coupling-on/off controls1432, then permits one PLLOUT extraction1433 from
the unchanged flat1202 GDS with the1250 structural-anchor preflight. The
pilot requires the five geometry-source hashes and trace-header hash to
match the completed1334 baseline exactly; only `ResReadExt.c` adds the
coupling import change. Full extraction uses CPU28,16GiB and1800s cap,
simplification off, same PLLOUT selection and signed-C threshold as1339.
The follow-up audit must verify primitive recovery, R network and explicit
C charge after ideal-R contraction against1202/1339. No cap conservation,
placement or dynamic qualification is asserted at launch; no release tool,
PDK or layout is modified. Build and observer actual PID/birth are pinned
in the launch receipt.

### MASKIVARS completed comparison: no observed PLL speed benefit

Replay1410 and completed comparison1411 use the same old backend, exact
shared source bank, reduction, model and50ps/260ns settings as1403. The
only numerical directive difference is `maskivars=1` (plus output paths),
checked by the comparator. Native GNU-time wall is6134s versus6109s
default: masked is about0.41% slower in these single concurrent runs,
so no PLL runtime improvement is established. Peak RSS1448580 versus
1448788KiB is essentially unchanged. Final frequency difference is
-0.080961ppm; maximum absolute rising/falling edge differences are
0.281880/0.209839ps. The masked run has30130 samples versus30154.
The option resolved the small RC-fixture LTE failure, but that does not
justify adopting it for the PLL. Keep the default reduced solver for
subsequent comparisons; MASKIVARS accuracy and corrected-backend behavior
remain unqualified. This negative benchmark closes this speed experiment
without further identical runs, and does not change release gate status.

### Completed-only PLLOUT coupling-export audit queued

Observer1435 follows live pipeline1434 for at most24h without holding a
resource lease while waiting. It requires normal completed1433 export
and source/receipt/artifact hashes matching the same flat1202 extraction
and completed1339 baseline. The audit uses CPU29 and16GiB to compare exact
primitive/C contraction against the original C circuit, plus the literal
named R network before/after the import change. Total absolute contracted
C error is reported with exact fractions; residual errors are retained,
not rounded into a passing result. Geometry, coupling placement, RC
simplification, dynamic accuracy and model/release qualification stay
false regardless of static results. Three tests cover removing duplicate
grounding, detecting changed R despite identical ideal-R contraction,
and retaining a small exact residual C mismatch.

### Combined controls complete and receiver comparison queued

Build1431 and all four native controls1432 completed. The combined engine
preserves before/after capacitance export in both coupling modes; stock-on
reproduces the extra ground term. The source-composition guard matches all
five geometry source hashes and header against1334. Full-layout PLLOUT
pilot1433 has started, with actual Magic PID/birth and CPU28 verified.
The completed-only static observer1435 remains waiting for its result.

Receiver comparison1436 waits for normal replay1427 completion and checks
the same full reference1278, physical604-endpoint validation1279, backend,
maximum timestep and exact declared reductions against1403. It reports
final-window edge/frequency differences and completed GNU-time/RSS data.
It does not claim pure receiver-isolation error, because moving the cut
also changes the prescribed capacitor environment and adaptive grid.
Downstream loading remains prescribed; no error tolerance or model
qualification is inferred. Three tests reject incomplete/forced records
and mismatched backend/timestep, while accepting matching checked settings.

### Lossless compressed retention and local ground-support trace queued

The active1400 uncompressed retention is unchanged. New helper
`retain_completed_native_gzip.py` requires normal native completion,
preserves the original regular source, writes a fresh gzip-level1 archive,
checks source inode/size/mtime/ctime and independent SHA, decompresses the
archive to verify exact byte count/SHA and gzip integrity, then publishes
with an exclusive hard link so concurrent destinations cannot be replaced.
An archive receipt records both compressed and uncompressed hashes. Four
tests cover binary recovery, incomplete input/existing destinations,
preexisting partial files and concurrent publication. No measured speedup
is claimed before a completed full trace archive.

New1437 uses the unchanged flat1202 GDS, logging-only ground-tail engine1360
and eight checked controls1362. Hot trace output is local; native extraction
gets CPU24,16GiB and3600s, with a24h resource queue and no automatic retry.
It requires512GiB free local scratch at preparation and native start. After
normal completion, gzip retention uses a separate2GiB lease; only after
round-trip verification is `coupling.jsonl` linked to the preserved local
trace for existing audits. Both raw local bytes and compressed archive
are pinned. Observer1438 waits for completed producer evidence before
partitioning/auditing the trace. The portable archive allows recovery of
the exact raw bytes; the local raw trace must remain until all audits
finish. Ground placement, legacy support and all release flags remain
false. This distinct local-I/O run follows failed shared-storage1363;
it does not reuse or audit that partial trace.

### Internal digital timing provenance and completed PLLOUT R control

The historical STA route019 is the internal `IntegerPLL_ProgrammedCore`
database, not the parent1136. Its signoff receipt pins both that database
and digital GDS; selected keeper parent geometry1135 references the same
digital GDS. Different parent/internal database hashes therefore do not
alone establish that internal digital timing geometry changed. Audit1439
will compare every recursive polygon layer and transformed text in the
current filled1147 digital cell against the019 GDS, and bind all five
historical STA database hashes through the signoff record. It uses the
retained pinned Python3.13/KLayout interpreter and2GiB on CPU29. Three
fixture tests pass for identical geometry, changed polygons/layers and
changed pin labels. The default Python lacks these bindings; the pinned
layout interpreter is required. No completed geometry result is claimed
at launch. Even identical geometry does not qualify old cell models or
changed parent loading/clocks, and no STA slacks are remeasured here.

PLLOUT1433 completed normally with exactly one network extracted/output
and74 emitted R cards, as in1339. Its exact C/R/primitive comparison1435
is queued for memory. Ground1437 has started on CPU24. None of these
producer results establishes C conservation or dynamic qualification.

### Predeclared coarse19 safe-range endpoint measurements

Protocol1440 waits for normal finite corrected-backend coarse19/fine149
50ps capture1412 and its604-endpoint physical check1413. A missing central
frequency or physical mismatch stops the protocol. Before any endpoint
result is available, fine8 and247 are declared as the two safe-range
endpoint captures1441/1443 with physical checks1442/1444. They run strictly
sequentially on the released central CPU20, each using the unchanged
coarse-band capture helper's16GiB/24h ceilings,260ns duration and50ps
maximum step. No other active capture is cancelled or reconfigured.
Physical-helper v2 changes only configurable affinity/CPU metadata; its
604-endpoint bindings and voltage checks are unchanged. Each physical
check runs after its native capture on the same CPU20. Four guard tests
cover backend/band/timestep identity, physical mismatch and absent frequency.

The purpose is to establish or reject a completed same-band diagnostic
400MHz bracket across the safe fine range. The existing149 point informed
band exploration, so it is explicitly not called a blind holdout. Neither
50ps numerical accuracy nor interpolation, startup capture margin, band
selection or predictive controller behavior is qualified by this protocol.
The original corrected coarse20 10ps fit/holdout family continues unchanged.
No additional native endpoint case begins before central completion.

### Ground mutation-site coverage follow-up1445

The existing completed-only coverage helper is now attached to local trace
support audit1438 and the same pinned ground-tail engine1360. Observer1445
waits for a completed audited trace, then checks direct-ground mutation
inventory/counts against reconstructed numerical lifecycle and spatial
support packets. It holds no lease while waiting and uses2GiB/CPU29 only
for the completed check. This replaces the dependency path of stopped
shared-trace coverage1387; neither source trace nor audit is reused from
that failed run. No native extraction is added. Legacy/split/placement
qualification remains governed by the actual coverage report, not observer
launch or producer completion.

### Completed nonzero-R coupling export control: exact C recovery

Audit1435 compares normally completed1339/1433 with the same flat1202 C
source. Both retain62338 primitive records,74 positive R cards in one
component, original ordered ports and no false shorts. The previous export
had only the PLLOUT-VGND excess65.94475fF; the modified export now has exact
aggregated C equality for all341067 nonzero pairs after ideal-R contraction
and zero negative capacitor cards. This establishes static charge recovery
for this actual nonzero-R PLLOUT control, not just the two-wire fixture.

Literal named R comparison is false because16 `.t` labels are permuted.
Audit1446 derives a bijection from identical primitive IDs, model/parameter
records and every non-R terminal; all62338 primitive records match. No
primitive has multiple distinct R-network nodes in this proof. Applying
that terminal mapping makes the full74-edge weighted R multigraph exactly
identical, including parallel edges and exact resistance values. This is
not a comparison based only on total R or an unconstrained graph relabeling.
Three tests cover valid terminal renaming, changed R values and changed
non-R primitive attachment.

The import change therefore removes the extra grounded coupling charge
without changing the tested resistor network modulo native terminal
numbering. Coupling/ground attachment geometry, simplification heuristics,
transient accuracy and full PLL model/release qualification remain false.
No RC simulator run is enabled by these static results.

### Completed digital macro identity audit1439

The current filled1147 `IntegerPLL_ProgrammedCore` has exactly the same
recursive polygon regions on every layer/datatype and transformed text
multisets as routed digital019 signoff GDS, on the same1nm grid. All five
historical STA receipts pin the019 database hash recorded alongside that
GDS in its signoff record. Thus the digital macro geometry is reused;
the earlier parent-versus-internal database hash difference was not proof
of changed digital geometry. The historical conditional STA screens remain
relevant diagnostics of this macro, including their reported negative
hold slacks. They are not new measurements and do not establish timing
closure with current parent loads or qualified native cell/receiver models.
The timing gate must combine the retained internal macro with current
parent interconnect and actual load/clock envelopes, rather than require
a different internal database solely because the parent was rerouted.
Physical timing, reset/CDC and release qualification remain false.

### Paired internal critical-path timing measurements1447

Thirty fresh OpenROAD checks query setup and hold of the three retained
critical path pairs at all five corners, using the unchanged internal019
database, min/max wire views, native early/late models and402.1MHz clock
constraints. No exceptions or load assumptions are added. These are
conditional internal diagnostics, not qualified current-parent400MHz STA.
The two `bbpd_decision` to `decision_q` bit paths are ordinary/interface
paths. The third ends at `gen_feedback_tracking.release_pipe[0]`, classified
as the first synchronizer aperture. Its protocol/interstage obligations
remain separate; it is not silently waived or treated as an ordinary
data-path ECO. The historical report is sampled, not exhaustive.

Exact printed-slack screen1448 asks only whether a corner-independent
nonnegative added data delay could repair each pair: lower bound is the
maximum negative hold slack, upper bound the minimum setup slack. Bit0
requires378.369123ps but permits331.331849ps, an empty window by47.037274ps.
Bit1 has482.129335..607.153654ps (no physical margin is assigned).
The aperture pair has396.646738..612.187207ps under this mathematical
screen, without selecting a fix. Real cell delays vary by corner; feasible
constant-delay windows do not select a physical implementation. In
particular, blanket delay insertion cannot resolve bit0 under these views.
Next timing work must qualify/tighten actual cell/load/clock bounds and
then evaluate clock/data restructuring or a measured ECO with both setup
and hold preserved, rather than accept an ordinary-path waiver.

### Full clock expansion of critical path diagnostics1449

Thirty full-clock reports reproduce every slack from1447 exactly. Focused
FF-min/SS-min/SS-max reports for decision bit0 are retained in the portable
clock-detail packet, with full source log hashes. In the SS hold report,
the capture path after divider Q contains `clkbuf_regs_0_FINECLK`,
`clkbuf_0_core.feedback_divider.CLKDIV_RETIMED_regs`,
`clkbuf_3_7__f_core.feedback_divider.CLKDIV_RETIMED_regs`,
`clkbuf_leaf_53_core.feedback_divider.CLKDIV_RETIMED_regs` (all clkbuf16),
then the decision clock inverter. Their SS late increments are roughly
253/309/357/231/106ps, after the567ps divider clock-to-Q. The decision
data paths already include many clkbuf2 hold stages.

This identifies a concrete candidate direction: evaluate an earlier,
logically equivalent FINECLK clock branch for the two decision registers
while selectively reducing existing data hold stages. A clock advance
alone trades hold improvement for setup loss, so both paths and all
corners must be measured after rerouting; no nominal algebra proves a
physical repair. The current macro/RTL/layout remain unchanged. Current
model/load/clock qualification and actual-frequency-range checks remain
open. Broad supplied-load envelopes and finite interpolation margins in
the retained libraries also require qualification; they cannot simply
be deleted to obtain positive slack.

### Isolated clock/data repair candidate1452 queued

The predeclared candidate feeds both existing decision-clock inverters
from divider Q and bypasses six non-inverting clkbuf2 data stages: bit0
hold133/145/148/155 and bit1 hold141/182. Twenty unchanged-arc delta
estimates across five corners/min-max are positive, with a worst estimate
of120.542366ps. Changed loading, slew and interconnect are excluded from
that estimate, so it is only a candidate-selection screen. The candidate
script forks019 route.odb, verifies expected masters/connections, preserves
RTL and clock polarity, reroutes changed nets, exports a new database/
Verilog/LEF and freshly extracts min/nom/max wire views. No timing numbers
are accepted from stale SPEF. Formal equivalence, DRC/LVS/antenna, current
parent reintegration and fresh full timing remain mandatory before selection.

Preflight1450 stopped on the assumption of one shared inverter; reports
actually show separate73752/76477 inverters. No native tool ran. Queued1451
was deliberately interrupted before native launch to correct RC extraction:
each retained rule file has one density corner, so1452 uses separate
read-only extraction invocations for min/max after nominal routing/export.
No existing PLL capture was cancelled. Corrected1452 separates a24h
resource queue from its1h native route/export cap, uses8GiB and two CPUs,
permits one route case and has no automatic identical retry.

A recorded queued-controller affinity override changes28/29 to28/30,
retaining two CPUs and all electrical/resource caps. CPU29 is occupied by
trace audit1401; the original CPU30 retention producer is confirmed gone.
The native child inherits this override. The candidate is unselected and
currently awaiting resources; existing layout and analog references remain
unchanged.

### Retained enabled-phase proof bound to current RTL1453

Scope review found the existing integrated decision-phase proof001 and
five selected402.1MHz enabled-phase screens. Their full retained input/
artifact hashes verify, and all nine current parent1136 RTL source hashes
match the integrated proof. It proves enabled decision stability at the
sampled falling edge, high-phase-only enabled decision changes and
high-phase loop-enable assertion in the actual integrated parent, retaining
both handoffs and the filter. It assumes initial external reset, stable
presets/gains between resets and ideal sampled RTL clocks. No new induction
is performed by1453.

The retained conditional screens shift only the two decision source hold
checks by one actual source period, retain physical launch latency and
all setup checks, and leave no reported ordinary/interface violating
samples; five first-stage aperture samples remain. This is a proved-phase
conditional diagnostic, not an arbitrary waiver, but the report is sampled
and does not qualify disabled-state masking, startup/reset/capture-disable
or full physical mode transitions. The unconditional delta screen1448
therefore does not establish that an ECO is required. Candidate1452 is
optional stronger-timing exploration, not the accepted fix or a reason
to replace the existing macro/reference captures. Earlier language that
physical clock/data repair was necessarily required is superseded by
this scope distinction. Full lifecycle timing and model qualification
remain release blockers; the existing phase proof must be used within
its actual assumptions.

### Completed expanded-receiver loading comparison1427/1436

The expanded old-backend50ps/260ns receiver replay completes normally
with all saved values finite and matching physical programming controls.
Native GNU-time elapsed6229s versus6109s first-clamped; peak RSS1452684
versus1448788KiB. Final frequency374.261240702MHz versus374.262351923MHz
changes by-2.969097ppm. Maximum absolute final rising/falling differences
are1.671104/1.465435ps. Both have29 post-reset rising and falling edges,
which alone does not establish absence of slips. The adaptive grids
differ (30170 versus30154 samples).

The expanded replay remains1072.635935ppm above full50ps reference1278,
so removing the first receiver clamp does not account for most of that
discrepancy in this same-code experiment. Full10ps references and numerical
convergence checks remain required; no attribution to timestep alone is
proved. The next receiver output and sampled capacitor environment remain
prescribed. This is neither changed-controller prediction nor corrected-
backend model qualification. No additional same-code receiver expansion
is automatically queued from this completed comparison.


The isolated clock-branch candidate 1452 completed route and fresh min/nom/max
wire-RC export with an empty router DRC report. Diagnostics 1454 use the same
five conditional cell-view corners and 402.1 MHz constraints, without new timing
exceptions: all twenty ordinary decision setup/hold checks are positive (minimum
hold 81.594124 ps, setup 98.300926 ps). The remaining reported negative paths are
five first-synchronizer data apertures. RESET_N still lacks an input delay;
startup/recovery and the actual operating frequency range remain unqualified.
Export 1455 physically binds all 95 unannotated outputs to zero external sinks
and zero top ports. Proof 1456 matches all 481 state primitives and all binary
transition/output functions; its corrupted-reset control fails as required.
Completed receipt inputs and artifacts were rehashed before retention in 1458.
These are separate diagnostic results, not selection or release qualification.
The original candidate and all analog reference captures remain unchanged.

Fresh layout check 1459 uses a separate artifact bundle and the retained native
stream/Magic DRC/LVS/antenna/PG checker. It binds the Boolean proof through the
functional export to the exact ECO database. It reserves one CPU (28), 8 GiB,
queues at most 24 hours and caps native checks at one hour. No assembled parent,
cell model, frequency range, physical CDC, density or EM/IR qualification is
claimed from these component checks; the route remains optional and unselected.


Layout check 1459 completed normally: the streamed ECO component has zero Magic
DRC rectangles, a unique layout/netlist LVS match, zero antenna net/pin violations,
and all 43,736 power pins connected. Native PG checks report all VDD/VSS shapes
connected. Its input/artifact hashes and native result hashes were reverified
before retention. This removes a component-level physical objection to the
optional ECO; it does not select it or replace the current parent GDS, whose
analog captures still refer to the original macro. Parent integration, custom
cell model bounds, startup/reset timing and the operating frequency range remain
open, as do the full release gates.


Corrected-BSIM pipeline 1466 waits for normal full-reference completion (1295)
and the exact capture's 604 endpoint-voltage checks (1296), then extracts completed
boundaries for receiver model 1419, exact reduction 1420 and replay plan 1422.
Fresh outputs 1467/1468/1469/1470 retain all source knots, verify the aggregate
roundoff certificate and local source archive, then run at the reference's 10 ps
maximum timestep on corrected backend 84ba37cb. One CPU (25), 8 GiB and a 24-hour
native ceiling are predeclared; resource queue time is separate from native
runtime. The original full captures and 64 GiB replay remain unchanged.
The controller was observed live waiting for the full reference. No runtime,
memory or accuracy success is claimed before its completed native receipt.

First preflight attempt 1460 stopped before native execution: the new guard
incorrectly rejected the old executable hash retained as historical provenance
in the corrected capture's inputs. Version 2 binds the explicitly named active
corrected executable, its hash and its corrected flag, while allowing historical
pins. Four container-run identity regressions pass, including old-active-backend
rejection, missing/mismatched identity, and legitimate historical provenance.
This validation replay still prescribes downstream waveforms and cannot alone
qualify a model for changed-controller or closed-loop prediction. It measures the
remaining correlation error after moving the proven source-reduction technique
to the corrected simulator and the finer reference timestep.


Parent integration 1471 replaces only the digital macro definition in a fresh
copy of filled baseline 1147. All 93 other original cell definitions and the
parent reference are preserved; the ECO's recursive polygon geometry and labels
match its checked component GDS, and the LEF prefix containing the outline and
all pins is byte-identical to the original. The original parent is not changed.
Component checks do not imply a parent pass: this copied filled parent has 2,592
Magic DRC rectangles. Expanded LVS 1472 independently reproduces one top-level
net discrepancy, while the three macro-level comparisons have no discrepancies.
These are completed negative results, retained with rule counts and the actual
bad-net record in 1474. No candidate selection or parent qualification follows.


Controlled fill removal 1473 changes only the two parent fill instances, preserves
all macro definitions and all other parent shapes/instances, and drops the full
flattened Magic DRC count from 2,592 to zero. Fresh expanded LVS 1475 of this
unfilled candidate matches uniquely, with no discrepant records and all three
macros expanded. Both exact-zero body and parent-port alias witnesses are obtained
from the new extraction itself; the new ECO powered digital reference is used.
Thus old parent fill causes both observed integration failures in these controls.
Removing fill is an intermediate repair, not a density or final physical pass.

Fill regeneration 1476 runs the retained eight-purpose stock fill process plus
the same M5 clearance/window preflight against the new, DRC/LVS-clean geometry.
The new helper checks the exact ECO-to-original-parent frame lineage rather than
pretending the old frame contains the new digital geometry. It reserves one CPU
(28), 12 GiB and a one-hour native limit after resource admission, with no identical
retry. The original parent and analog references remain untouched. A live launch
receipt is retained; the regenerated filled candidate still requires fresh DRC,
expanded LVS, density and fill-aware parasitics before any selection. Frequency,
cell-model, startup and full closed-loop release gates remain open.


ECO fill 1476 completed with the original unfilled geometry and labels preserved,
only allowed fill purposes added, and the declared 650 x 500 um frame retained.
Fresh full-parent Magic DRC 1477 has zero rectangles. Expanded LVS 1478 matches
uniquely, with all three macros expanded and every record free of discrepancies.
These results check the regenerated fill rather than inheriting unfilled passes.
The first DRC invocation stopped at import time under the minimal interpreter,
before any output or native check; the pinned KLayout interpreter ran the fresh
check successfully. No failed native run was silently retried or overwritten.

Density 1479 records 80 complete native tiles and independently applies the
retained stock thresholds and clipped-edge weighting. All seven constrained global
checks pass (FOM, LI1 and M1-M5; POLY has no threshold). The stock wrapper exits 1
at its explicit small-macro applicability stop because the nominal window is
700 um; its failure is retained, and no stepped-window or chip-integration pass
is claimed. Fill-aware parasitics, input loading, antenna/power integration,
startup timing and actual-frequency-range qualification remain open. The new
filled GDS is an unselected alternative; no existing analog reference is rebound.


Frequency-capacity measurement 1480 checks the same ECO database and fresh
min/max wire RC at 400 and 420 MHz across five conditional cell-view corners.
All five 400 MHz max-path checks are positive; the minimum is SS +111.357369 ps.
At 420 MHz SS is -7.690293 ps, while the other four corners remain positive.
Do not call the candidate 420 MHz capable across corners or infer an arbitrary
startup/tracking frequency range. Min-path reports retain the previously
identified first-synchronizer aperture negatives. These are capacity constraints:
the original RESET_N false path and asynchronous clock exceptions are explicitly
retained, with no new exceptions added. They are not a startup/reset or physical
cell-model qualification. The filled parent is not yet represented in those
internal-macro wire RC measurements. Summary 1481 links the completed physical
checks and this measured limit without selecting the ECO or closing a release gate.


Fill-aware ECO extraction 1482 completed from regenerated GDS 1476, bound to its
fresh parent DRC 1477 and expanded LVS 1478. It flattens actual geometry, extracts
stock constant capacitances with a signed export threshold, and extracts no wire
resistance. Flat device LVS 1484 matches the independent powered hierarchy
uniquely with no discrepancy records; only explicit constant-C cards are removed
for that topology-only comparison, and the original export remains unchanged.
Mask audit 1486 confirms every checked conductor, all electrically active
selectors, diode markers on active diffusion, and the poly/diff channel region.
The same positively/negatively controlled M5 alias normalization is reused. Full
selector masks outside their electrically active domains are regenerated rather
than bit-identical; the flat diagnostic GDS is not a fabrication replacement.

Two validation guard corrections are recorded in 1488. First LVS attempt 1483
stopped before native comparison because the retained reference recipe is pinned
as an input, not an output artifact. Version 2 verifies the actual completed pin
binding. Mask audit 1485 used KLayout Region representation equality for channels;
version 2 uses an empty polygon XOR, which confirms geometric equality. Neither
correction changes source GDS or extracted capacitance. The earlier observations
remain preserved. Capacitance coefficient/spatial and dynamic qualification are
separate from the passing device-connectivity and mask checks.


Literal native reference 1487 is prepared only after the same export passes flat
device LVS and electrical-mask checks. It preserves 62,302 actual primitives in
433 literal templates, two checked poly adapters, and all 340,888 nonzero constant
capacitances with exact endpoint/value checks. Only 1,022,914 zero-valued C cards
are omitted. It requires nonnegative constant branches, so that constant-C part
has nonnegative branch energy. It does not force the old 62,338-device inventory
onto the physically changed candidate. These are static preparation properties,
not native corrected-backend correlation, fill-aware wire-R timing, or predictive
closed-loop qualification. No new full analog capture is launched, no spatial
endpoint approximation is applied, and the model remains unselected with native
simulation allowance and release flags false.


Endpoint schedule 1490 preserves the two coarse19/fine8 and fine247 captures and
all 604 endpoint-voltage checks predeclared by 1440, but assigns native workers
to separate physical CPUs 20 and 21. Each retains the original 16 GiB reservation,
24-hour per-case ceiling and one-shot/no-identical-retry policy. Global leases
still enforce 32 CPUs, 200 GiB and the host reserve, so simultaneous execution
requires budget admission. Neither operating points nor timestep are changed.
Four existing endpoint validation controls pass. Actual speedup is not measured.

Handoff 1489 verifies that 1440 was still waiting, had no child process, and had
created none of the four endpoint output directories. It intentionally sends
SIGINT to that waiting coordinator, then confirms its PID/birth is gone and the
endpoint paths remain absent. The central native capture 1412 remains live and
unchanged. The replacement coordinator validates this exclusive handoff and is
observed live waiting for normal central capture plus physical-control completion.
It observes both endpoint workers to termination before combining their results;
failed cases are not retried, and no band or interpolated model is auto-selected.
The old coordinator's KeyboardInterrupt status is intentional schedule replacement,
not cancellation or failure of a native simulation.


The completed old-backend 10 ps fine149 capture 1266 reports 374.076080984 MHz
for coarse20, TT/27C/1.8V over 200-260 ns. It is normally completed, finite and
stationary; physical observer 1268 validates all 302 bits and 604 endpoint
voltages with zero mismatches across 26,077 saved samples. This is not the
corrected-BSIM capture 1295, which remains a separate live reference.

Completed timestep comparison 1280 checks full 10 and 50 ps captures whose decks
differ only in output path and maximum timestep. Both pass their physical
controls. The 50 ps frequency is 373.860224790 MHz, -577.038214 ppm relative to
10 ps. Controller-through-validation elapsed is 52,934.33 s versus 14,994.94 s
(a single-run ratio of 3.5301); this includes capture/output/postprocessing rather
than isolated solver time. The comparison has no finer-step convergence result
and does not qualify numerical accuracy. The 5 ps control continues separately.
Completed inputs and artifacts were rehashed before retaining these receipts.


Comparison 1491 reuses the completed, hash-verified 10/50 ps output arrays from
1280 and the completed old-backend reduced replays; no native simulation or live
RAW analysis is added. Against full 10 ps, replay 1403 is +497.949344 ppm with
maximum final-window paired-edge differences 31.598173 ps rising/31.435749 ps
falling. Expanded-receiver replay 1427 is +494.978769 ppm, 30.678072/30.320361 ps.
The corresponding comparisons against full 50 ps and the full 50-vs-10 ratio are
recomputed, and exact multiplicative frequency-ratio accounting is checked.

The replay forcing histories still come from the 50 ps full capture, not the
10 ps reference. These ratios are not independent additive error bounds, and
equal edge counts are not a cycle-slip proof. A single old-backend operating
point below 1,000 ppm does not qualify an interpolation error bound, the corrected
backend, changed-controller prediction, or full closed-loop operation. The 5 ps
control and corrected-backend 10 ps references retain their original tasks and
criteria. This result narrows the observed discrepancy without weakening any
release acceptance gate.


The complete old-backend coarse20 TT curve 1271 has five fit points at fine codes
8, 110, 149, 182 and 247, with an independently predeclared holdout at 133. Every
native capture is normally completed/finite/stationary and each physical observer
validates 302 bits and 604 endpoint voltages with zero mismatches. The measured
fit range is 347.873211-393.221014 MHz, so it has no measured 400 MHz bracket;
extrapolation does not make this a target-ready curve. The holdout errors are
-503.737790 ppm for linear frequency and -605.609100 ppm for linear period.
Neither is accepted as a global interpolation bound. All completed receipts and
actual input/artifact hashes were rechecked before retention. These results are
old-backend C-only characterization, not corrected-BSIM or other-corner evidence.


Prospective corrected coarse19 holdout 1493 declares fine198 before the central
1412 result and before either endpoint starts. Fit codes remain 8, 149 and 247;
198 is never inserted into that fit. Linear frequency is predeclared as primary,
with linear period retained as a sensitivity comparison, before the new data.
The new case uses free CPU22, 16 GiB, the corrected backend, 50 ps and the same
260 ns capture plus all 604 endpoint-voltage checks. One additional native case
is allowed, with no identical retry and global CPU/RAM leases unchanged. The
band19 campaign has four cases including its already-running central point.

The holdout waits for normal central completion and physical validation, then
can run alongside the existing endpoint workers when admitted by the shared
budget. It subsequently collects their completed receipts and reports target
bracketing and independent interpolation residuals without extrapolating to
400 MHz. Thirteen reused characterization/endpoint guard tests pass, including
holdout leakage, extrapolation, domain and physical-receipt rejection controls.
No global interpolation bound, finer-step convergence, other-corner validity or
closed-loop qualification is accepted from this diagnostic campaign. The live
waiting launch and its prospective roles are retained.

Per-register reset/pulse coverage 1496 queries all 481 asynchronous-reset pins
and all 481 clock pins separately in each of five native corner views of the
original routed macro. All 2,405 high-pulse and 2,405 low-pulse checks are
reported and pass. Recovery and removal each report 2,135 of 2,405 queried
endpoints with no violations; 54 endpoints per corner have no reported reset
path and are explicitly unqualified. Minimum reported recovery/removal margins
are 0.713801026 ns / 0.010463519 ns. Three parser rejection/control tests pass.
The existing primary-reset and asynchronous-clock exceptions are preserved,
with no new exceptions. Periodic screening clocks, conditional cell views and
original macro RC do not qualify actual BBPD pulses, startup frequency range,
external reset pulse width, regenerated-fill loading or full lifecycle timing.
The completed receipt and compact endpoint summary are retained.

Lifecycle binding 1499 checks the actual nine RTL files from the routed
candidate, mapped/routed equivalence, retained mask/rearm proof, seed proof and
original-macro geometry reuse. Both decision registers retain the intended
falling-edge logical capture through mapped clock inversion. All 54 unreported
reset endpoints per corner are classified structurally: 48 external-RESET_N-only
endpoints, four oscillator-domain reset stages sourced from the reference
domain, and two event-capture registers reset from the fast domain. The complete
endpoint detail is retained. These classifications provide no timing waivers.
Retained sampled logic proofs are bound rather than rerun; physical reset
arrival, primary-reset pulse width, metastability resolution and full startup /
disable-reenable timing remain open. No clock-branch ECO is selected.

Corrected-BSIM coarse19/fine149 capture 1412 completed normally at 50 ps
maximum step with all saved values finite. Its final 200–260 ns window measures
362.529421912 MHz over 22 rising edges (period range 2.756672017–2.759814923 ns).
Elapsed capture/assessment time is 18,362.34 s. Physical check 1413 observes
6,374 samples and all 604 macro/DCO endpoint voltages match the requested static
coarse19/fine149 code, with no ambiguous code voltage. Input and artifact hashes
were reverified before retaining both completed receipts. This is one TT C-only
point, with corrected executable 84ba37cb; distributed wire R, convergence,
other-corner behavior, 400 MHz bracketing and closed-loop behavior remain open.
Normal completion and physical validation released the predeclared parallel
fine8/fine247 endpoint workers and independent fine198 holdout; all three native
processes are confirmed running. Their results are not yet available.

Native asynchronous-reset pulse coverage 1502 separately queries all 481
reset pins in each of the five retained corner views with OpenSTA's native
minimum-pulse-width check API. All 2,405 queries complete; zero report a check.
Zero violations is therefore not a reset pulse-width pass. This is distinct
from the complete clock-pin high/low coverage in 1496. The native-liberty writer
emits the measured pulse allowance only on CLK, while RESET_B/SET_B retain
recovery/removal tables but no pulse-width limit. Retaining this omission makes
reset pulse characterization an explicit prerequisite to physical lifecycle
qualification. No constraints, RTL, cell models or release gates were changed.
The completed source-pinned receipt and diagnostic runner are retained.

Reset-pulse grid 1504 now measures the five used extracted sequential masters
from the same fixed-divider digital extraction used by the clock-pulse campaign.
Forty independent fixtures per corner cover 100/400/1000/2000 ps active-low
pulse widths with 20 ps full ramps and 400/1000/2000 ps widths with 400 ps ramps,
plus a no-pulse control per master. Each fixture initializes asynchronously,
loads the opposite state with a clock, holds the clock low during the test pulse,
and checks retained Q after reset release. Twenty-five no-pulse controls across
the five corners must retain the opposite state. Planned total: 200 observations
at 1.8 V / 27 C using fixed ngspice, 2 ps maximum step and predeclared individual
cell output loads. Three waveform-assessment rejection/control tests pass.
The live launch is source-pinned and uses CPU17 / 4 GiB, shared leases and a
one-hour native limit per corner, with no identical retry. An earlier preflight
1503 stopped before native execution because the older assembly lacked dfstp_2.
No minimum pulse bound, actual routed slew/load envelope, recovery/removal or
physical lifecycle qualification is inferred from this diagnostic grid.

Routed reset fixture envelope 1505 queries all 481 reset inputs and all 481
corresponding Q outputs at each of five conditional native corner views of
original macro019. The largest modeled 20–80% reset slew is 0.840960860252 ns
at SF (SS: 0.816714942455 ns); every corner has samples above the initial
grid's 0.24 ns upper slew. There are no zero-slew observations and no modeled
Q-net load exceeding its declared fixture load. The smallest load margin is
52.736230195 fF, at a dfstp_1 Q output. These are conditional STA measurements,
not bounds on real reset waveforms or regenerated-fill loading. Discrete pulse
observations cannot provide a continuous envelope by themselves. The completed
receipt and runner retain the mismatch rather than qualifying the initial grid.

The TT native capture in 1504 completed normally, but its collector stopped
when merging duplicate negative_control fields. Recovery 1508 verifies the
specific post-native exception, original launch hashes, absent original process
identities, normal completion markers and complete finite ordered waveforms.
It reuses the closed TT capture without any native rerun. Of forty fixtures,
two fail: the 100 ps / 20 ps-ramp pulse does not set dfstp_1 or dfstp_2 despite
verified opposite prestates and released control. The other 38 pass, including
all five no-pulse controls and all sampled widths of 400 ps or more. No minimum
pulse bound follows from these finite observations. Completed receipt and all
forty observations are retained, including failures.

Collector v3 fixes the duplicate-field merge, preserves 1504, reuses its TT
capture and continues FF/SS/SF/FS in distinct campaign1506. Three assessment
controls pass. CPU17/4GiB and the one-hour native limit per corner remain in
force. This does not rerun the original TT stimulus or change cell models.

Supplemental slow-ramp campaign1507 declares 1600 ps full ramps (960 ps 20–80%)
and 1600/2000/4000 ps pulse widths for each of the five masters at five corners,
plus one no-pulse control per master/corner: 100 additional observations.
The slower ramp exceeds the largest conditional routed slew measured in1505;
this does not establish continuous or real-waveform coverage. Existing models,
loads, 2 ps maximum step and the reset-retention assessment are unchanged.
CPU affinity was moved with verified PID/birth identities for the supervisor
and its TT native child to free CPU18; later children inherit that affinity.
The explicit override record is hash-pinned in the launch, since the reusable
worker defaults to CPU17. Shared CPU/RAM leases, 4 GiB and a one-hour native
limit per corner remain unchanged. Both campaigns are live; no result from
an active native waveform is assessed.

Completed-only review1509 waits for both reset-pulse campaigns, verifies their
actual input/artifact hashes and matches every observation to the prospective
plan. It rejects missing, duplicated, unplanned or inconsistently classified
fixtures and requires identical extracted-cell sources. The common declared
2 ns pulse is checked in exactly 75 observations: five masters, five corners,
and full ramps of 20/400/1600 ps. All 300 observations and all failures remain
in the review; a passing common pulse is not a minimum-width or continuous
slew/load bound. Three guards pass, including deliberate incomplete coverage
and a failed primitive check mislabeled as passing. The review adds no native
cases and waits on process identity plus terminal receipt, never active traces.

Slow-ramp campaign1507 completed all 100 fixtures. Its original 8–9 ns
prestate window rejects eight dfrtp_1 fixtures at SS/SF, including their no-pulse
controls; these are invalid initial-state observations, not established reset
capture failures. In the verified closed no-pulse traces, SS/SF Q is respectively
1.609272/1.603998 V at 8 ns, 1.727652/1.723330 V at 9 ns, and above 1.796 V at
12 ns. The earliest tested ramp starts at 9.2 ns. Original failed observations
and completed receipt are retained unchanged. A separately recorded reassessment
will use 200–100 ps before each planned ramp leading edge, with inactive reset
and adequate sampling required. This adjusts observation timing without any
native rerun; it cannot qualify a continuous or routed reset timing bound.

Both campaigns and completed-only review1509 are now complete: the original
300 observations retain 35 failed fixtures, including premature prestate
sampling. Separate review1510 uses a stimulus-derived window 200–100 ps before
each ramp begins, requiring inactive control and at least ten samples. Three
rejection controls pass, including a state reached only after the ramp. Original
observations, failures and native waveforms remain unchanged; no native case
was rerun. All actual input/artifact hashes were verified again before retention.

Under this explicitly revised observation rule all 50 no-pulse controls pass,
and all 75 common 2 ns pulse observations pass across five masters, five corners
and 20/400/1600 ps full ramps. Thirteen capture failures remain, all 100 ps pulses
with 20 ps ramps: two TT set cells, all five masters at SS and SF, and dfstp_2 at
FS. Every remaining failed fixture has a verified opposite prestate. All other
sampled pulse widths pass. These are isolated clock-held-low observations with
fixed loads, not a universal minimum-width, arbitrary waveform, clock-high,
recovery/removal or routed reset guarantee. The complete reassessed detail and
both original completed review/campaign receipts are retained.

Clock-high campaign1511 now tests the same declared 2 ns pulses with 20/400/1600
ps full ramps while CLK remains high from its 4 ns loading edge through the
22 ns horizon. Each of five masters at five corners has three pulse cases and
one no-pulse control (100 observations). It uses the stimulus-derived prestate
window already checked in1510 and verifies retention after reset release
without any subsequent clock edge. This covers a distinct static clock state;
clock-edge proximity, recovery/removal, real reset waveform timing and routed
qualification remain open. CPU17 / 4 GiB shared leases, 2 ps step and one-hour
native limit per corner are unchanged, with no identical retry. TT native is
confirmed live, and the actual deck holds CLK at 1.8 V after 4.1 ns.

Adaptive central experiment1512 verifies the completed corrected-backend
coarse19 and coarse20 fine149 / 50 ps captures and all 604 physical controls
for each. Their decks are identical after changing only six coarse-source
values and output paths. The measured centers are 362.529421912 MHz at coarse19
and 372.921866488 MHz at coarse20: the measured direction is toward higher
frequency as coarse increases. One additional central experiment at coarse23 /
fine149 is predeclared to seek a useful region nearer 400 MHz. This is selection
of an experiment location, not extrapolated calibration, an inferred frequency,
a target bracket or a selected band. Existing band19 endpoint/holdout captures
continue unchanged and their results remain required evidence for that campaign.

The new case uses CPU18 / 16 GiB, 50 ps maximum step and 260 ns, followed by
all 604 physical endpoint checks in distinct outputs1513/1514. One native case
is allowed, no identical retry, with a 24-hour cap and unchanged global CPU/RAM
admission. The coordinator is live and has verified its prior captures; the
new capture must wait if global memory is unavailable. Three guards reject
wrong backend/code, incomplete physical checks and electrical deck changes
beyond the permitted coarse sources and output paths. No release gate closes.

Clock-high campaign1511 completed all 100 fixtures with zero failures: all 75
2 ns pulses (five masters, five corners, three full ramps) establish and retain
the async reset/set state after release, and all 25 no-pulse controls retain the
opposite state. Actual input/artifact hashes were independently rechecked before
retaining the completed receipt and full observations. Together with1510 this
covers both static clock levels in the declared isolated-cell fixtures. It does
not qualify release near active clock edges, continuous slew/load ranges,
actual routed reset pulse widths, recovery/removal or physical lifecycle timing.

Prospective coarse23 characterization1515 declares fit codes8/149/247 and
independent holdout198 before its central result exists. It waits for normal
central capture1513 and all physical checks1514 through coordinator1512. Only
a verified central frequency within the predeclared 380–420 MHz experimental
admission range starts additional captures; otherwise it records that result
and starts none. This range controls experimental spending, not qualification.
Linear frequency is primary and linear period a sensitivity check, with no
calibration extrapolation or accepted global interpolation error bound.

Three one-shot workers use CPU17/18/23 and 16 GiB each, subject to unchanged
global CPU/RAM admission. Maximum new native cases: three, total band23 cases
including the existing center: four. Each capture is 260 ns / 50 ps and followed
by all 604 physical endpoint-voltage checks. Every spawned worker is observed
to termination even if another fails. Three guards reject wrong operating
domain, incomplete physical checks, wrong/unfinished backend and missing or
nonfinite frequency. The coordinator is confirmed waiting, with no endpoint
or holdout output created. No band, numerical accuracy, other-corner model or
closed-loop prediction is qualified by this launch.

Corrected-BSIM full 10 ps reference1295 now completed normally. All saved
native values are finite and the requested coarse20/fine149 code is stationary
without ambiguous top-level code voltages. The final 200–260 ns window measures
373.148216755 MHz over 23 rising edges, with periods 2.679179275–2.680687523 ns.
Controller elapsed time through capture validation is 54,584.14 s; that includes
postprocessing and is not isolated solver time. Actual input and artifact hashes
were independently reverified before retaining the completed receipt. The
604-endpoint physical assessment1296 is now extracting from this completed
capture; it is not yet reported as passed. Corrected timestep comparison1343
and reduced replay1466 remain gated on those physical checks. No distributed-R,
transient correlation, other-corner model or closed-loop qualification follows
from this single static-code TT C-only capture.

Physical assessment1296 completed for corrected full reference1295: all 302
macro tuning bits and their 302 DCO leaf endpoints match coarse20/fine149 at
all 26,077 samples in the 200–260 ns window, with zero mismatched endpoints.
Actual input/artifact hashes were independently reverified before retention.
The completed native and physical receipts now release corrected timestep
comparison1343 and both boundary-replay preparations1297/1466. The comparison
is confirmed live in its completed-control comparison stage; both replays are
extracting from the completed capture. These passing static-code voltage checks
do not qualify wire-R, the prescribed replay environment or closed-loop behavior.

Boundary dependency audit1522 classifies all 7,679 prescribed nodes in the
receiver-expanded conditional circuit: 7,371 capacitive-only, 304 nonrail
retained-primitive terminals, and four rails. The capacitive-only boundaries
have an exact aggregate coefficient of 31.19899 fF to retained unknowns,
including observed PLLOUT; this charge coefficient is not a frequency-error
bound. The detailed table preserves each terminal role, branch counts and exact
rational coupling coefficient. No source, capacitor, primitive or boundary
condition is modified. Three guards check MOS gate/diffusion distinction,
exact capacitance accounting, partition coverage and malformed cards.

The remaining nonrail diffusion boundary is
IntegerPLL_ProgrammedCore_0.sky130_fd_sc_hs__clkbuf_16_123.A. Thus the existing
receiver expansion removes an earlier prescribed output but still prescribes
an active output farther along the clock path. Replay correlation under saved
waveforms cannot establish changed-controller prediction. A causal model must
supply or internalize this dependency as well as its gate inputs and capacitive
exterior environment. The completed source-pinned audit and full boundary table
are retained to scope that work; no independent environment or model is qualified.

Corrected-backend timestep comparison1343 is complete. The electrical decks
differ only in maximum step (10 versus50 ps) and output paths; both captures
have all 604 physical tuning checks passing. Frequency is 373.148216755 MHz at
10 ps and 372.921866488 MHz at50 ps, a -606.596138 ppm difference. Maximum
absolute paired final-window differences are 55.317709 ps rising and52.605222 ps
falling; equal post-reset edge counts alone do not prove absence of cycle slips.
Controller elapsed ratio is3.486189 (54,584.14 versus15,657.25 s), including
output validation/postprocessing rather than isolated solver time. Inputs and
artifacts were independently reverified before retaining the completed receipt.
This demonstrates a diagnostic speed/accuracy tradeoff at one static TT point;
finer-step convergence, other-code/corner numerical error bounds and release
accuracy remain unqualified. The50 ps search captures are not promoted to
converged calibration by this comparison.

Corrected-BSIM fine110 reference1344 completed at10 ps with stationary
coarse20/fine110 and all saved native values finite. Frequency in200–260 ns is
365.578566139 MHz over22 rising edges, period range2.735029203–2.735981819 ns.
Controller elapsed through validation is46,006.36 s. Physical assessment1345
passes all604 macro/DCO endpoint-voltage checks over26,075 samples, with zero
mismatches. Both completed receipts and actual input/artifact identities were
reverified before retention. Fine182 remains native-running; the prospective
corrected fit/holdout collector still needs it. This TT C-only point supplies
neither a400 MHz bracket nor other-corner, wire-R or closed-loop qualification.

Next-frontier preparation1523 internalizes the sole nonrail diffusion boundary
identified by1522, retaining32 additional physical primitives for10,211 total.
All previous interior unknowns and unchanged source cards are preserved, and
PLLOUT remains unforced. The new boundary has7,699 ports and four prescribed
nonrail diffusions: a_51394_74686#, a_56386_74454#, a_67234_77350#, and
 a_67618_73122#. This is downstream movement of the active-output dependency,
not its elimination. Three existing receiver-expansion guards pass. The new
candidate is isolated, no earlier candidate is modified, and native execution
is not authorized by its preparation receipt. The completed receipt and runner
are retained to guide causal receiver modeling rather than claim prediction.

Corrected reduced replay1470 has now started natively onCPU25 under its8 GiB
lease after completed physical checks, exact-knot aggregation and source
staging. Its actual native process and local output paths are present. All
prior large captures and the new coarse23 capture remain unchanged.

Native receiver closure cost1524 follows every retained nonrail diffusion
terminal into incident omitted primitives. From the10,211-primitive candidate,
the proposed set exceeds the20,000 preparation limit at22,590 primitives after
16 rounds; that bounded study does not claim closure. Three guards check
transitive receiver inclusion, exclusion of unrelated rail-sharing devices and
correct lower-bound reporting when a cost limit is reached.

Cost study1525 continues the same source-pinned graph to a fixed point without
exporting or simulating a circuit. It converges after59 rounds at59,004 of62,338
flat primitives (94.6517%). Thus removing these output prescriptions by explicit
native-device expansion of this cut approaches the original full-circuit cost.
The complete selected primitive list, both completed receipts and algorithms are
retained, with all input/artifact identities reverified. Formal output-port
handling and the capacitive exterior environment would still need treatment;
this graph closure does not qualify an independent model. No native case was
added. The next causal modeling step is receiver-load characterization rather
than repeated frontier expansion; replay1470 continues as a correlation control.

Extracted clkbuf_16 input-charge campaign1526 completed45 fixtures: three full
input ramps (20/400/1600 ps), three output loads (0/100/400 fF), and all five
process corners at1.8 V/27 C. Each native ngspice run includes a20 fF capacitor
reference whose20–80% charge/sign/unit checks pass within1e-4 relative error.
All input levels and noninverting output-state checks pass. Three integration
and response rejection controls pass, and actual listed inputs/artifacts were
independently reverified before retention.

Observed20–80% effective input capacitance ranges from7.490867 to10.701807 fF.
Full-window rising/falling charges and peak input currents are retained for
every case. The extracted cell has six explicit input capacitors, including
0.46664 fF to its internal a_114_74# node and0.00201 fF to output X. These must
be separated from intrinsic gate charge before stitching a load model into the
existing flat-C circuit; the current observation set does not save the internal
node voltage needed for complete de-embedding. The next measurement must add
that observable and a finer-step control. No causal load element, numerical
convergence or actual routed load envelope is qualified by this characterization.

Finer-step buffer campaign1527 completed all45 fixtures at1 ps while also
observing the internal a_114_74# input-capacitor terminal. All reference-capacitor,
input-level and output-response checks pass. Explicit capacitor charge is
computed as sum C*(V_A-V_other) from all six unchanged input-capacitor literals,
observed internal/output voltages and fixed rails, then separated from port
charge. Three controls check moving-neighbor charge, fixed-rail offsets and
rejection of missing/changed capacitor observations. De-embedded20–80% effective
intrinsic input capacitance ranges from6.319707 to8.736814 fF. Input leakage is
not subtracted. The source-pinned completed receipt, full observations, helper
and runner are retained after independent input/artifact verification.

This completes explicit capacitor accounting in the extracted-cell measurement,
not full-flat-C stitching, a causal load element or routed-load qualification.
The actual coupling topology and voltage response must still be preserved when
using these data in a receiver model.

Completed-only step review1528 matches all45 declared fixtures at2 ps and1 ps.
Maximum absolute relative differences are200.822887 ppm for20–80% effective
input capacitance and112.217086 ppm for full-window charge (0.020083% and
0.011222%). Three controls reject incomplete/duplicate grids, invalid response
and nonfinite measurements, and verify sensitivity is relative to the finer
measurement. All five actual deck pairs match after normalizing the declared
step, equivalent model include path and saved-observation command; that equality
record and its input hashes are retained. Original measurements remain unchanged.
These results quantify local integration sensitivity, not a frequency-error
bound or independent receiver-model qualification. Current model work should
address dynamic response and C stitching rather than infer accuracy from a
constant capacitance alone.

Charge-surface candidate1529 fits all45 de-embedded observations with positive
piecewise input capacitances and one positive Miller capacitance per corner.
The model is conditional on observed internal voltage; it supplies no causal
internal-state response. All five fits converge with nonnegative coefficients,
but maximum training charge error is5.6147% of the measured charge swing.
Three guards check recovery of a known positive surface, monotone input charge
and invalid/unexercised data rejection. Source-pinned coefficients, error
statistics and completed receipt are retained, with no qualification inferred.

The plan predeclares a separate400 MHz /100 ps ramp /200 fF load validation
before measuring that waveform. Exact-token parallel grouping was also inspected
as a speed option:62,338 primitive calls form54,134 groups, a13.2% call-count
reduction before backend support or equivalence validation. No multiplicity
rewrite or native optimizer was implemented on that basis.

Periodic validation1530 completed the predeclared400 MHz /100 ps /200 fF
holdout in all five process corners. All periodic20 fF reference controls and
output-level checks pass. Candidate1529 coefficients are frozen and not refit.
Maximum charge error is5.6391% of observed charge swing (0.77003 fC at SS),
consistent with its5.6147% training error. The internal voltage is measured in
this test, not predicted, so this remains a conditional charge-component test.
Completed receipts, all corner errors and the native runner are retained after
input/artifact verification. The simple surface is not integrated as a qualified
receiver; richer voltage dependence and a causal state response remain required.
No PLL release gate is closed by these measurements.

Corrected fine182 native1346 and physical1347 are complete:379.311621187 MHz
at coarse20 /10 ps, all saved values finite, stationary requested code, and
all604 physical endpoints matching over26,073 samples. Controller elapsed is
49,829.40 s. The completed native/physical receipts were independently reverified.
Corrected collection1351 now has its predeclared fit points110/182 and separate
holdout149, all at10 ps with matching physical controls. Linear-frequency
prediction at149 has -350.832349 ppm error; linear-period prediction has
-688.253260 ppm error. Neither error is accepted as a global bound. These
measured points do not bracket400 MHz, and no extrapolated target is supplied.
Other-corner, wire-R and closed-loop qualification remain open.

Static-code native DCO pilot1531 retains the native first clock buffer and
control-driver circuitry, drives the 302 macro thermometer inputs with their
static truth tables, grounds capacitive exterior boundaries, and terminates the
free receiver output with 32 fF. PLLOUT remains free; no recorded voltage history
is used. The declared TT coarse20/fine149 run is 60 ns at a maximum10 ps step,
with a20–60 ns diagnostic window. All302 native DCO control leaves are observed;
this is analog characterization, not a replacement for actual RTL loop testing.
Four boundary-mapping tests pass, covering polarity, complete role/programming
coverage, invalid codes and rejection of additional active terminals. The native
capture is running; frequency agreement, startup-window convergence, receiver
load sensitivity, other corners and wire-R uncertainty remain unqualified.

Static mapping audit1532 exhaustively checked all11,520 legal coarse/fine
settings against the selected physical port records:3,479,040 thermometer-bit
assignments match an independent threshold/polarity calculation. Conditional
input ports are unique; rails, reset, free receiver output and free PLLOUT bind
as declared. This verifies static stimulus construction only; it supplies no
analog accuracy or release qualification.

Completed-reference early-window audit1534 reverified the closed1467 extraction
and1296 physical-control artifacts. Windows20–60,60–100,100–140 and140–180 ns
have fewer than three PLLOUT rising edges, so no frequency is reported. All604
physical tuning endpoints match throughout140–180 ns and200–260 ns; earlier
windows do not. The final200–260 ns result exactly reproduces373.148216755 MHz.
Thus the static pilot's20–60 ns window cannot be treated as a simultaneous
full-reference startup correlation. Any comparison with the final reference is
only a steady-frequency diagnostic under different programming/reset histories;
startup and settling require separate qualification.

Receiver-load sensitivity pilot1536 repeats the static TT coarse20/fine149
case with zero additional receiver capacitance on CPU27. Native extracted
capacitors remain. Deck comparison confirms every other electrical statement
and observation matches1531 after normalizing the RAW output path. This is a
separate one-shot60 ns/10 ps case, not a retry. Both captures must complete
before a load-sensitivity frequency diagnostic can be reported; neither passive
termination is qualified as the full downstream environment.

Pair assessor1538 waits for normal completed1531/1536 receipts with live-owner
checks and a24 h observation cap. It verifies all source/artifact hashes and
all302 native tuning leaves, requires the electrical decks to differ only in
the declared load, and measures20–40,40–60 and20–60 ns frequencies. Missing
oscillation is recorded explicitly. No unfinished native RAW is read. Load
sensitivity and subwindow agreement remain diagnostics, without automatic model
or release qualification.

Startup timing audit1539 identifies the actual selected native DCO RESET_N:
its0.9 V rising crossing is181.310052 ns, and the first PLLOUT rising crossing
is184.239709 ns. The last sampled mismatch among604 tuning endpoints occurs
at109.065 ns. The absent early frequency is therefore consistent with the
DCO being held in reset during controller programming. The static pilot releases
its directly driven DCO reset at5 ns; oscillator settling comparisons must align
elapsed time since native reset release. Skipping controller initialization is
useful for static analog characterization, but does not verify that initialization
or the closed loop. No startup qualification is claimed.

Static pilot1531 completed normally in1,140.581 s (19.01 min), with all saved
values finite and all302 native DCO tuning endpoints matching. All input and
artifact hashes were independently reverified. Its20–60 ns frequency is
373.665911964 MHz, +1,387.371520 ppm versus the full reference's200–260 ns
373.148216755 MHz. This exceeds the release target's1,000 ppm tolerance;
no model qualification is granted. The elapsed ratio47.8564 compares a60 ns
subsystem case with a260 ns full-programming reference, not equal workloads.
It demonstrates a faster diagnostic path, without proving an equivalent-workload
speedup or calibrated400 MHz accuracy. Pair1536 and assessor1538 remain live.
Grounded capacitive exterior, receiver termination, reset-history alignment,
settling, corners and distributed wire R still require assessment.

Reset-aligned comparison1540 uses measured0.9 V reset crossings5.05 ns for
pilot1531 and181.310052 ns for the full reference. At ages20–40 ns the
frequencies are373.649282059/373.077184779 MHz (+1,533.455552 ppm); at ages
40–54 ns they are373.715922450/373.145581064 MHz (+1,528.468819 ppm).
The combined20–54 ns comparison is +1,531.465467 ppm. Aligning elapsed time
does not remove the discrepancy. Reset slews and prior histories still differ,
so this is diagnostic evidence, not an isolated attribution or a global error
bound. Passive output-load sensitivity and the prescribed-boundary replay are
still needed to separate remaining approximation effects.

Independent static point1541 prospectively tests coarse23/fine149 with the same
32 fF receiver termination,60 ns duration and10 ps maximum step as1531. It is
exploratory near-target characterization, with a single native case on CPU17.
Its inherited full_reference_frequency_MHz/frequency_difference_ppm fields refer
to the coarse20 reference1295 and therefore represent a cross-code difference,
not model error or correlation. The relevant same-code full center1513 remains
running at50 ps; even that later comparison must account for timestep mismatch.
No corrected calibration, extrapolated400 MHz bracket or qualification is
inferred from this independent static point.

Zero-load1536 completed normally in1,142.870 s, with all302 DCO tuning leaves
matching and all saved values finite. Its20–60 ns frequency373.665913129 MHz
compares with373.665911964 MHz at32 fF. Verified pair1538 measures only
-0.003119479 ppm for32 fF relative to zero added load. The two electrical decks
match except for this declared capacitance. The32 fF receiver output switches:
15 rises and15 falls over20–60 ns, with sampled range-0.021190214 to1.85960491 V.
Thus the negligible frequency difference is not explained by an inactive output.
This pair does not explain the roughly1,531 ppm reset-aligned model discrepancy;
it also does not qualify the entire downstream environment or other corners.
The zero-load native log is retained as lossless gzip; its decompressed SHA256
was checked against the original completed receipt. Raw captures remain in the
verified build artifacts.

The completed full control checks1296 show DCO_THERM[183].macro at1.57895323
to1.94688408 V in200–260 ns despite passing the logic threshold. The largest
DCO-leaf departure from its ideal rail is9.80966 mV, compared with9.71091 mV
in static pilot1531's20–60 ns window. These different-window extrema do not
establish causality, but motivate diagnostic1542: replay all302 measured macro
programming inputs in the unchanged native subsystem, retaining the grounded
capacitive exterior and32 fF receiver load. Reference samples are shifted by
176.260052307 ns so the full-reference reset crossing aligns with pilot5.05 ns.
All source sample times inside the60 ns interval are retained, with interpolated
endpoints; no lossy downsampling is applied. This explicitly uses recorded voltage
histories, leaves PLLOUT free, and cannot predict a changed controller. The
one-shot CPU27/8 GiB case tests programming-input idealization separately from
capacitive-exterior idealization; no qualification is inferred before completion.

Completed-reference coupling ranking1543 finds467 capacitive-only exterior
boundaries with retained coupling, totaling exactly31.19899 fF. In200–260 ns,
the largest coefficient-times-sampled-voltage-span scores are2.757310274 fC
for clkbuf_16_106.X,2.207556000 fC for REFCLK and1.492612453 fC for
clkbuf_2_297.A. The total score is16.230972382 fC. These actively switching
exterior nodes are grounded in the static pilot. Scores ignore phase and
cancellation, use sampled extrema, and are not bounds on charge error or
frequency error. They identify omitted dynamic excitation for targeted model
work; they do not prove that any one source causes the observed frequency bias.

Analytic REFCLK sensitivity case1544 adds the declared external25 MHz clock to
the static coarse20/fine149/32 fF native subsystem. It checks the full reference's
PULSE(0 1.8 20n 100p 100p 19.9n 40n) declaration and shifts its phase to align
with the measured DCO reset release. The resulting first edge starts at
3.739947693 ns in the accelerated60 ns run. This source is analytic, uses no
recorded voltage history, and is a capacitive-only boundary; all other capacitive
exterior nodes remain grounded. REFCLK_DRIVER is saved alongside PLLOUT and
all302 native control leaves. The single CPU31/8 GiB case tests this known
omitted excitation; other dynamic aggressors and model qualification remain open.

Independent static coarse23/fine149 point1541 completed normally in1,149.327 s
(19.16 min), at404.096788446 MHz over20–60 ns, with all302 native tuning leaves
matching and all saved voltages finite. Inputs and artifacts were independently
reverified. Its log is retained as lossless gzip with verified decompressed hash.
This establishes an exploratory fast-subsystem point above400 MHz; it does not
yet establish a qualified fine-code bracket. The matching full-layout coarse23
center1513 is still running, and no coarse20 discrepancy correction is transferred
to this point. The inherited frequency_difference_ppm is a cross-code comparison
to coarse20 reference1295, not a model error measurement.

Configurable runner run_keeper_static_DCO_point.py preserves the static native
subsystem,32 fF receiver load,60 ns duration and10 ps step while accepting
explicit coarse/fine code, CPU and exclusive output directory. It reuses the
four tested boundary-mapping controls and labels its coarse20/fine149 comparison
as a cross-code reference difference. First case1545 measures coarse23/fine8
on CPU17, prospectively pairing with completed1541 coarse23/fine149 to seek
an exploratory fast-model400 MHz bracket. This is not a full-layout bracket,
model-error correction or release calibration. Existing hashed runners remain
unchanged.

Ranked-aggressor edge audit1546 revalidates the completed reference and records
0.9 V crossing times for the20 largest charge-excursion scores in200–260 ns.
Several leading nodes, including REFCLK and clkbuf_16_106.X, have only one rise
and two falls in that interval. In contrast, dfrtp_4_3.CLK has23 rises and22 falls,
with an observed mean rising rate near373.15 MHz. Other nodes show sparse or
irregular activity. These are measured crossings, not qualified periodic-clock
models or proof of each source's frequency effect. They show that an analytic
REFCLK-only correction leaves oscillator-rate and startup-dependent exterior
activity unresolved.

Analytic REFCLK case1544 completed normally in1,125.325 s (18.76 min), with all
302 native tuning leaves matching and all saved values finite. Its20–60 ns
frequency373.666293068 MHz differs by+1.019906 ppm from grounded-REFCLK
pilot1531. Saved native REFCLK crossings are3.78994769 and43.78994770 ns
rising,23.78994770 ns falling, matching the declared stimulus phase and period.
Input/artifact hashes were independently reverified and the compressed native
log reproduces its receipt hash. The remaining difference from the full reference
is still+1,388.392841 ppm in these unaligned windows. Restoring REFCLK alone
therefore does not resolve model accuracy; other dynamic boundaries, input
idealization, reset history and numerical uncertainty remain unqualified.

Mixed-signal binding audit1547 rechecks source_pins() provenance, actual portable
and original source hashes, selected GDS binding and the route019 nine-file RTL
set. All nine names and digests match. Five tests reject changed RTL, unrelated
geometry, changed build inputs/tools, incomplete caches and changed image
fingerprints. This verifies identity guards for the existing actual-RTL harness;
it does not introduce a new functional proof or qualify analog models, timing,
closed-loop behavior or release readiness.

Coarse23/fine8 static point1545 completed normally in1,164.511 s (19.41 min),
with all302 native tuning leaves matching, all saved values finite and verified
input/artifact hashes. Its20–60 ns frequency is376.002510237 MHz. Together
with completed fine149 point1541 at404.096788446 MHz, it establishes an
exploratory fast-subsystem bracket for400 MHz at coarse23. Intermediate codes
remain unmeasured, and there is no fitted accuracy bound or qualified full-layout
bracket. This permits an interpolated target-code hypothesis followed by a new
independent native measurement, without extrapolation or transferring the
coarse20 model discrepancy as a calibration correction.
