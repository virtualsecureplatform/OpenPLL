# Programmed 400 MHz prototype

The active profile is `verification/prototype_400mhz.json`: 25 MHz reference,
400 MHz output, 1.8 V, 27°C, TT/FF/SS/SF/FS. The deliverable is a verified macro
handoff. Other frequencies, temperature qualification, automatic acquisition,
precision jitter qualification and chip/shuttle submission are deferred.
Historical four-mode requirements remain unchanged; their former active pointer
is preserved in `verification/active_release_four_mode_400mhz.json`.

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
