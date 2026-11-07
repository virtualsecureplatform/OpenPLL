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
