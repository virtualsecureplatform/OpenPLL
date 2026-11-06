# OpenPLL

The active target is a **programmed 400 MHz hard macro**, using a 25 MHz
reference and nominal 1.80 V, across TT/FF/SS/SF/FS at 27°C.
The [active release manifest](verification/active_release.json) points to the
[prototype signoff flow](verification/signoff400/README.md) and its
`requirements_v3.json` profile. The active prototype requires five operating
points and 60 closed-loop startup/recovery/phase scenarios per common gain pair.
Temperature qualification belongs to the retained earlier plan.

**The macro is not tapeout ready.** The selected filled GDS has a
[qualified antenna component](verification/prototype400/selected_antenna_component_qualification.json)
under a pinned tool profile, with independent process-view geometry/connectivity
checks. Remaining physical checks, analog model/tuning qualification, complete
digital timing/CDC, closed-loop operation and clean handoff are still open.
Release requires direct evidence closing all five prototype gates for this
same candidate.

The verification hot loop now has a C++20 streaming charge compiler, bounded
multicore scheduling and Python-reference comparison controls. Start with
`make signoff400-test`; see the signoff workflow for benchmarks and continuation.

Startup settings remain externally programmed and stable until reset. Jitter,
power and supported output loading will be characterized and published. Other
frequencies, automatic band acquisition, supply variation and chip/shuttle
submission are outside the active deliverable. The historical prototype and
four-mode release evidence retain their original scope.

## What to Read

- `PLL_ARCHITECTURE.md` describes the PLL architecture and block-level control
  conventions.
- `SKY130_IMPLEMENTATION.md` summarizes the Sky130 implementation, physical
  status, signoff evidence, and local build commands.
- `SPICE_VALIDATION.md` records the transistor-level validation boundary,
  promoted evidence, and non-promoted diagnostic history.
- `REPRODUCIBILITY.md` describes the Apptainer/SingularityCE flow for
  reproducing the latest release gate.

## Historical configured flow

The current fast coarse-DCO source/behavioral gates are:

```sh
make -C OpenPLL check-sky130-macros
make -C OpenPLL check-pll-25mhz-divider-config
make -C OpenPLL check-pll-25mhz-divider-controller
make -C OpenPLL check-pll-25mhz-configured-wrapper
make -C OpenPLL check-pll-25mhz-configured-behavioral
```

The latest-release result can also be audited or rebuilt inside Apptainer:

```sh
make -C OpenPLL apptainer-build
make -C OpenPLL apptainer-physical-audit
make -C OpenPLL apptainer-audit-release
make -C OpenPLL apptainer-rebuild-release
```

The container includes NumPy, Sky130 PDK archives, LibreLane, and upstream
Xyce. It selects a newer PDK with native LibreLane setup for physical rebuilds;
see [REPRODUCIBILITY.md](REPRODUCIBILITY.md#pdk-compatibility) for the
historical v8 pin distinction and the current audit result.
The physical audit passes on the newer PDK; the historical v8 release audit
does not pass because its fixed physical and frequency baselines belong to
the older PDK.

`rtl/IntegerPLL_25MHzModeConfig.v` is the reusable preset table for a 25 MHz
reference. It exposes the restored /4, /10, /12, /16, and /20 settings:

| Feedback divider | Target | Coarse | Fine seed | KI | KP |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 100 MHz | C20 | 93 | 16 | 4 |
| 10 | 250 MHz | C06 | 234 | 16 | 4 |
| 12 | 300 MHz | C04 | 90 | 16 | 4 |
| 16 | 400 MHz | C02 | 76 | 16 | 4 |
| 20 | 500 MHz | C01 | 121 | 16 | 4 |

The table also emits a 10-bit `DLF_Ext_Data` seed equal to
`target_code << 2` and `CONFIG_VALID`. Unsupported divider values are passed to
the lower divider bus for observability but hold `CONFIG_VALID=0` and do not
enter tracking.

`rtl/IntegerPLL_25MHzModeController.v` and
`rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured.v` are the intended
configured RTL entry point for the 25 MHz reference path. The external control
is the feedback-loop divider value, `FEEDBACK_DIVIDER[4:0]`, plus `PLL_ENABLE`;
the controller latches the divider, applies the matching characterized
coarse/fine/gain seed when `CONFIG_VALID=1`, asserts `DLF_Clear` for the preset
seed, and then enables closed-loop tracking. The shipped hard-macro path uses
the divider-clocked DLF macro; the
generic digital core and `IntegerPLL_Top` still support
`DLF_UPDATE_ON_PLLOUT=1` as a diagnostic build option if the digital-core macro
is rebuilt for that variant. `make -C OpenPLL
check-pll-25mhz-configured-wrapper` runs the wrapper-level divider sequencing test
and checks that those preset controls reach the hard-macro instance. The
configured wrapper also has a hardening flow as
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured`. The regenerated wrapper
artifact passes Magic/KLayout DRC, LVS, setup/hold, max slew/cap, and the
configured hard-top release checker.
The lower-level `IntegerPLL_HardMacroTop_EINVP` pins remain available for
characterization and custom bring-up.

Next-version BBPLL work should focus on the broader control extension needed
for robust acquisition from arbitrary phase and code, rather than on packaging
the configured interface.

`make -C OpenPLL check-pll-25mhz-configured-behavioral` runs reset-to-tracking
behavioral PLL regressions for all restored 25 MHz divider values. It uses the
real controller, digital core, divider, and BBPD with a behavioral DCO table
fitted to the all-HD 255-load coarse-DCO measurements, and checks
measured output frequency plus non-rail DCO control after the preset load.

The current configured-mode 25 MHz-reference PLL target gate is:

```sh
make -C OpenPLL xyce-pll-mixed-signal-25mhz-targets
```

The current all-HD DCO target table is:

| Target | Coarse | Seed | Target-code evidence |
| ---: | ---: | ---: | --- |
| 100 MHz | C20 | 93 | Interpolated code estimate 93.429 |
| 250 MHz | C06 | 234 | Measured target code |
| 300 MHz | C04 | 90 | Interpolated code estimate 89.631 |
| 400 MHz | C02 | 76 | Interpolated code estimate 76.037 |
| 500 MHz | C01 | 121 | Interpolated code estimate 120.677 |

Fast deterministic BBPLL jitter sweeps are under
`build/pll_jitter_25mhz_allhd255/` with matched v6 rows under
`build/jitter_compare_25mhz_v6_matched/`. They use an ideal BBPD/control model
and exclude device noise, supply noise, and extracted interconnect noise. The
all-HD DCO improves the worst-case peak-to-peak period jitter screen at all five
configured targets versus v6. Fitted TIE RMS is mixed, improving at 100, 300,
and 500 MHz while regressing at 250 and 400 MHz, so this remains a deterministic
model screen rather than final jitter signoff.

The current fast source/behavioral check for that 25 MHz coarse-DCO path is:

```sh
make -C OpenPLL check-pll-25mhz-divider-config check-pll-25mhz-divider-controller check-pll-25mhz-configured-wrapper check-pll-25mhz-configured-behavioral check-sky130-macros
```

It checks the coarse-DCO RTL shape, including the `buf_1` output-buffer
constraint, the restored 25 MHz divider presets, the divider
controller/wrapper, and the configured behavioral PLL reset-to-tracking
regression.

The heavier `make -C OpenPLL check-sky130-pll-25mhz-release` target checks the
current post-layout hard-macro artifacts, configured-wrapper artifacts,
target-code rows, and direct-RCX integration summaries.

An optional slow direct-RCX integration smoke for the hardest divider target is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-500m-hold-smoke
```

It runs the extracted coarse DCO and extracted BBPD in Xyce at C01/code121 with
the digital divider/filter in the mixed-signal driver. Its short ADC-sampled
frequency estimate is intentionally loose; regenerated standalone RCX DCO rows
must remain the precise frequency evidence.

An even slower all-mode direct-RCX near-seed code-update diagnostic is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
```

The current all-mode direct-RCX run checks +/-4 fine-code starts for all five
divider targets with `KI=16`, `KP=4`, and `FRAC=2`. That evidence remains a
near-seed direct-RCX integration diagnostic; standalone target-code rows remain
the precise frequency evidence.

The legacy low-frequency v1 artifact audit remains available:

```sh
make -C OpenPLL validate-sky130-pll-artifacts
```

It checks the older Sky130 signoff, SPICE, RTL, mixed-signal, and extracted-loop
artifacts and writes consolidated summaries under
`OpenPLL/build/sky130_pll_validation/`. The heavier
`make -C OpenPLL validate-sky130-pll` target regenerates those legacy promoted
artifacts before running the same audit.

An optional pre-layout mirror-delay diagnostic is:

```sh
make -C OpenPLL check-dco-einvp-coarse-mirror-targets
```

It uses the same small `output-buffer-drives 1` assumption. The legacy target is
still useful for topology experiments, but the current release DCO source uses
an all-HD ring and all 255 thermometer load controls.

## Environment

The Makefile first looks for the newer Ciel/Volare Sky130 tree at
`$HOME/.volare/ciel/sky130`, using the newest `versions/*` entry when there is
no direct `sky130A` symlink. It falls back to `$HOME/.volare`. Override these
variables for another local setup:

```sh
export CIEL_SKY130_ROOT=$HOME/.volare/ciel/sky130
export PDK_ROOT=$HOME/.volare/ciel/sky130
export PDK=sky130A
export STD_CELL_LIBRARY=sky130_fd_sc_hd
export LIBRELANE_ROOT=$HOME/src/librelane
export XYCE_MPI_ROOT=$HOME/.local/xyce-mpi
```

Use `make -C OpenPLL check-pdk-stdcell` to print and validate the selected
PDK. If the shell exports either the legacy default `PDK_ROOT=$HOME/.volare` or
the Ciel registry root `PDK_ROOT=$HOME/.volare/ciel/sky130`, the Makefile and
direct script defaults resolve it to the usable Ciel PDK root; pass
`PDK_ROOT=...` on the `make` command line or export a non-default root to select
something else. The local Ciel install used for this tree includes
`sky130_fd_sc_hd` and `sky130_fd_sc_hs` reference views. The current coarse
high-frequency DCO macro explicitly uses HD cells.

`LIBRELANE_ROOT` is auto-detected from nearby checkout locations when possible.
`XYCE` defaults to the first `Xyce` on `PATH`; MPI/KLU diagnostics use
`$XYCE_MPI_ROOT/bin/Xyce` when that binary exists.

## Validation Boundary

The strongest current high-frequency evidence is the post-layout coarse-DCO
target map plus clean physical hardtop/SPICE interface checks. The
25 MHz-reference mixed-signal flow is configured-mode polarity and gain evidence
around measured target settings; it is not final post-layout PLL lock signoff.

For the 25 MHz reference / 200 MHz fast path, run
`xyce-pll-postlayout-calibrated-dco-mixed-fast200-sparse72-lock` after the
sparse72 DCO signoff/RCX/probe targets. That mixed target uses the filled BBPD
RCX in Xyce and a DCO phase model calibrated from the sparse72 post-layout RCX
frequency points; the current bounded run converges from code 0 to code 192
at 202.314 MHz and from code 255 to code 191 at 196.767 MHz, both within the
configured 4 MHz tolerance around the 200 MHz target.
The full extracted-DCO C-interface path is retained as a slow diagnostic. The
bounded direct-RCX companion is
`xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion`: it keeps both
the filled BBPD and sparse72 DCO RCX decks in Xyce, uses Xyce's mixed-step API
for post-decision DCO-code updates, and drives REF as a 25 MHz pulse source for
robust BBPD edge capture. The current sparse72 diagnostic run measures fixed
code 196 at 199.734 MHz, pulls a low-side start from code 184 to 197 with
measured PLLOUT at 200.000 MHz, and pulls a high-side start from code 220 to 194
with measured PLLOUT at 200.000 MHz. This is direct-RCX near-lock evidence, not
a full rail-to-rail extracted-DCO regression.
Running the current C-interface executables under `mpirun` is not a practical
speedup path: the probed `mpirun -np 2` smoke reached Xyce completion but left
both driver ranks stuck instead of exiting cleanly.

For the 100 MHz-order fast path, `xyce-pll-mixed-signal-fast100-coarse4-smoke`
is a bounded C-interface check with the filled BBPD RCX in Xyce and a
behavioral fast DCO table plus independent coarse offset in the compiled
driver. It is useful local polarity/range evidence, not physical fast-DCO
signoff.
`xyce-pll-analog-dco-mixed-fast100-coarse4-acq` is the stricter mixed-signal
fast-path check: Xyce owns the filled BBPD RCX, behavioral analog DCO phase,
reference, and divider, while the compiled driver owns only the DLF code
update. The current tuned bounded run reaches fine code 34 from 0 and code 30
from 64 around the 126.88745 MHz target, with measured `PLLOUT` frequencies of
127.389 MHz and 126.316 MHz respectively.

Diagnostic targets that are slow, host-sensitive, or known not to pass from
both rails are deliberately excluded from the promoted artifact gate and are
documented as diagnostic history in `SPICE_VALIDATION.md`.

The 400 MHz spatial circuit interface now has an exact native-name binding for
all 371 top-level ports, with unique existing resistance-node IDs before and
after the exact zero-resistance transform. The source-hashed receipt is
`build/signoff400/startup_timing_external_port_binding_001/assessment.json`.
This binding still requires reconciliation with the final spatial projection
receipt and does not qualify the complete circuit or physical models.

The unresolved diode sheet-end audit scanned all 206,708 native device
terminal bindings and all 371 external ports: none directly uses the 560
unassigned end states. A source-pinned follow-up waits for the exact live
zero-resistance-constrained capacitance build and will scan every matrix
entry for those states. See `startup_timing_symbolic_end_connections_001`
and `startup_timing_symbolic_end_capacitance_followup_001` under
`build/signoff400`. No state elimination or physical qualification is claimed.

The native capacitance unit audit compiles and exercises the actual Magic
formatter: one raw EXT/trace unit is `1e-18 F`, and positive capacitances
below 1 aF serialize as zero. The receipt is
`build/signoff400/startup_timing_SPICE_cap_serialization_001/assessment.json`.
The successful full printed-EXT comparison therefore does not establish
SPICE matrix equivalence. Complete serialization accounting and spatial
assignment remain required before physical RC qualification.

An eight-thread compiled scan of every retained native SPICE capacitor found
40,122,611 records: 20,452,615 printed zeros, 19,651,958 positive values, and
18,038 negative values. Parser controls cover 1/4/8 threads, signed values,
SI suffixes, and malformed records. The source-hashed receipt is
`build/signoff400/startup_timing_SPICE_cap_token_inventory_003/assessment.json`.
These counts do not prove matrix equivalence or passivity; the signed native
values are retained for full matrix qualification.

The independent negative-capacitor audit binds every one of the 18,038
negative retained SPICE records to exact native R nodes. All connect to VGND
from 5,614 other original conductors, none collapses within one original
conductor, and their exact printed sum is `-1.4597212e-13 F`. See
`build/signoff400/startup_timing_negative_SPICE_caps_001/assessment.json`.
These terms remain present; no passivity or full SPICE equivalence is claimed.

The complete eight-thread native SPICE capacitor endpoint audit registers
2,944,855 exact names from original conductors and final native R nodes.
All endpoints of all 40,122,611 capacitor records resolve, including all
19,669,996 nonzero records; no guessed aliases or zero-only namespace
extensions were needed. See
`build/signoff400/startup_timing_SPICE_cap_endpoint_coverage_001/assessment.json`.
This establishes name coverage for native matrix assembly, not full matrix
equivalence or physical RC qualification.

The complete serialized native SPICE C matrix is assembled in the controlled
ideal original-conductor basis: 20,735,077 upper entries and 1,893,230 states.
Exact signed small-matrix/SI/fold controls pass at 1/4/8 threads. Full native
row and 2x2-minor checks pass (scaled charge residual `5.8789e-20`), without
a full PSD claim. Receipts are `startup_timing_native_SPICE_C_matrix_001`
and `startup_timing_native_SPICE_C_audit_001` under `build/signoff400`.
The diagnostic comparison against the ideal EXT trace finds 42,380,308
entries beyond its strict numerical screen, with a largest difference of
123,908,438.46108106 raw units (123.90843846108106 pF), on the reference
diagonal. Serialization and native RC capacitance allocation still need
reconciliation; no full SPICE equivalence or physical RC qualification passes.

The complete pre-resistance native SPICE matrix isolates the large native
RC discrepancy: its reference diagonal differs from the EXT trace by
102,994.66891894542 raw units (0.10299466891894542 pF), whereas resistance
extraction changes that diagonal by 124,011,433.13 raw units (124.01143313 pF)
and changes 913,300 conductor-coupling entries. The source-hashed three-way
diagnostic is `build/signoff400/startup_timing_pre_R_SPICE_C_comparison_001/assessment.json`.
The RC-stage capacitance redistribution must be reconciled separately from
SPICE serialization; no equivalence gate has been waived.

An eight-thread audit of all 18,207 selected native R groups, all 1,051,995
final R nodes, and all 40,470,849 original coupling records finds exported
R-node capacitance totals of 130.79903470533779 pF versus 130.80795001149893 pF
of incident coupling and 18.577457352878138 pF of original node-ground C.
Pinned native source imports coupling into the R-node capacitance accumulator
and does not read node-ground C in `ResReadNode`; its area-based redistribution
then exports that accumulator. The receipt is
`build/signoff400/startup_timing_R_cap_redistribution_002/assessment.json`.
Per-group differences remain diagnostic (37 groups exceed a relative `1e-5`
screen), and this result does not completely account for the matrix delta
or qualify native RC capacitance allocation.

The native R capacitance import was replayed over all 40,470,849 coupling
records in source order using the actual compiled `MagAtof` function and
float32 additions. Order-sensitive controls pass. The summed absolute
per-group prediction error decreases from 9,072.930634195078 to
1,322.155442778849 raw units; 18,206 of 18,207 groups fall within the same
diagnostic relative `1e-5` screen. VPWR remains outside it: exported
17,618,149.77758 versus imported 17,619,436 raw units (1.28622242 fF difference).
See `build/signoff400/startup_timing_native_R_cap_float32_replay_001/assessment.json`.
The remaining area-normalization/export arithmetic is not yet qualified,
and no physical capacitance or matrix-equivalence gate is promoted.

The repaired digital timing-characterization audit reconciles all 12,334
instances across 49 masters with the OpenDB inventory. Retained terminal
raw propagation grids cover 40 of its 41 logic masters at all 15 required
1.8 V PVT points. The sole missing master is `mux2_4` (four instances).
The retained LVS-checked extracted model is now being measured with 54
sensitization/load/slew fixtures per PVT point and up to eight single-thread
Xyce workers under shared CPU/RAM leases. Evidence is in
`build/signoff400/startup_timing_characterization_coverage_001/assessment.json`
and the live `build/signoff400/startup_timing_mux2_4_15PVT_raw_001` campaign.
These are raw observations; qualified timing views, numerical/interpolation
bounds, sequential constraints, and final boundary/fill loading remain open.

The whole known G offdiagonal sign audit finds 9,431,097 strictly negative
entries and no positive entries across 18,577,590 records. The unresolved
diode unit family also has 560 nonnegative edge weights. This certifies
the exact mathematical graph defined by those edge weights with implicit
exact incident-sum diagonals, including nonnegative family multipliers.
Receipts are `startup_timing_known_G_signs_001` and
`startup_timing_nominal_G_edge_graph_certificate_001` under `build/signoff400`.
The stored matrix has separately rounded diagonal entries: its exact PSD
and a rigorous diagonal-perturbation enclosure are not proved. The graph
is not yet implemented in the native solver, material values remain
unselected, and physical RC qualification remains false.

The complete positive-family conductance topology is independently checked
against every original and zero-R-constrained voltage-map slot: 9,431,657
edges on 9,147,054 states form exactly 1,893,231 original conductor components.
No edge crosses an original conductor and no original conductor is fragmented.
Alias, cross-conductor, and fragmentation controls pass. The verified map
and receipt are under `build/signoff400/startup_timing_G_components_001`.
For the exact edge graph, with strictly positive symbolic-family multipliers,
the kernel is precisely the original-conductor constant subspace. Stored
rounded-diagonal nullspaces, native charge-constraint implementation, final
projection-map reconciliation, and physical qualification remain open.

The new mux2_4 campaign is complete: all 810 fixtures (54 per PVT point)
pass propagation and strict output-slew checks at all 15 required points.
`build/signoff400/startup_timing_characterization_coverage_002/assessment.json`
reconciles the terminal receipt and fixture sets: all 41 logic masters in
the repaired candidate now have raw 15-PVT propagation observations.
The new campaign receipt is
`build/signoff400/startup_timing_mux2_4_15PVT_raw_001/assessment.json`.
This completes raw cell-type coverage; numerical/interpolation bounds,
sequential constraints, final loading, and qualified timing views remain open.

A compiled streaming propagation assessor matches every retained Python
record across 1,701 fixtures (810 new mux2_4 plus 891 legacy TT), including
three failing slew records and their raw threshold crossings. Missing
terminal markers are rejected. The binary runs inside the simulator image,
and a future-run adapter exactly reproduces the retained 54-fixture TT
assessment without rerunning a simulation. Receipts are
`compiled_propagation_assessor_controls_002` and
`compiled_propagation_assessor_adapter_controls_001` under `build/signoff400`.
The parser retains event lists rather than full waveform arrays. Reported
parser timings are nonisolated; no benchmark speedup or physical timing
qualification is claimed. Existing native workers and completed artifacts
are preserved.

A separate mux2_4 timestep-only campaign is registered at
`build/signoff400/startup_timing_mux2_4_step_control_001`: all 15 PVT decks
retain their original stimuli and solver settings while changing only the
maximum step from 2 ps to 1 ps. Each deck has a one-line patch. Up to eight
single-thread native workers use shared leases and the validated compiled
streaming assessor. Signed matched metric differences, changed outcomes,
and unmatched measurements are retained; no numerical uncertainty threshold
or qualification is inferred from these controls.

The full G component attachment audit joins all 51,829 native devices,
206,708 terminal bindings, 371 ports, and all 7,500,317 floating-basis
voltage states. Exactly 18,207 components have native device/port attachment,
and exactly 1,875,023 are unextracted physical floating conductors. No other
native R component is unattached. The binary role inventory and receipt are
under `build/signoff400/startup_timing_G_component_roles_001`. Initial
floating charges and native charge constraints are not assigned or
implemented; final producer-map reconciliation and physical qualification
remain required.

A compiled rectangular charge-row transformation now computes
`P_unattached^T C`, preserving every constrained voltage column. Independent
full symmetric controls pass at 1/4/8 threads with two voltage permutations,
signed coefficients, forced accumulator flushes, internal-capacitance
cancellation, and zero operators retaining all declared rows. The format
rejects wrong-magic, truncated, and trailing-data inputs. Controls are in
`build/signoff400/floating_charge_row_controls_001`. A source-pinned
`startup_timing_floating_charge_rows_followup_001` waits for the exact final
zero-R-constrained C and producer-map reconciliation before processing all
floating conductors. Initial charges and native solver charge constraints
remain unassigned and unimplemented; physical RC qualification stays false.

Separate relative- and absolute-tolerance mux2_4 controls are registered
for all 15 PVT points under `startup_timing_mux2_4_reltol_control_001` and
`startup_timing_mux2_4_abstol_control_001` in `build/signoff400`. Relative
tolerance changes only `1e-5` to `1e-6`; absolute tolerance changes only
`1e-10` to `1e-11`. Both retain the baseline 2 ps maximum step and all
stimuli. Compiled streaming assessment is enabled. Shared admission limits
projection and numerical jobs together to 32 CPU slots and 200 GiB of
reserved job memory, retaining the host memory reserve. No uncertainty
acceptance threshold or physical qualification is selected.

An exact GMP dyadic audit encloses every stored G diagonal difference
from the positive-edge graph. The known matrix maximum row-scaled
perturbation is exactly `182439 / 2522116326380437066561369`
(about `7.233568019514133e-20`), and every row meets the existing `1e-12`
gauge screen with exact integer comparisons. Symbolic unit matrices are
audited separately; the bound extends to their exact nonnegative linear
combinations. However, the rounded known matrix has 7,713 negative original
conductor constant-mode energies, so its exact PSD is disproved; the first
witness and exact dyadic energy are retained. This is a numerical
representation result, not a claim of physical instability or a qualified
model. Receipt: `build/signoff400/startup_timing_G_dyadic_rounding_001/assessment.json`.
Additional numeric scaling/assembly and native graph residual integration
remain open; physical qualification is false.

A compiled conductance evaluator now computes incidence-form edge currents
`g*(Vi-Vj)` from the certified positive-edge graph. Small exact dyadic
controls include the stored matrix negative-energy example. On every
9,147,054-state known/unit graph, conductor-constant inputs yield exactly
zero currents; every output row also matches an independent streamed edge
scatter for a nonconstant vertex test pattern. Single-thread controls are
`build/signoff400/startup_timing_G_edge_operator_controls_001/assessment.json`.
This validates an operator component; full native MNA/GMRES integration,
material selection, and physical qualification remain open.
The independent 1 ps timestep campaign has also completed at all 15 PVT
points: all 810 fixture outcomes match baseline, no metrics are unmatched,
and the largest observed matched metric change is 0.046272988694896766 ps.
The receipt is `build/signoff400/startup_timing_mux2_4_step_control_001/assessment.json`;
these finite controls do not establish a numerical-domain enclosure.

The complete diagnostic native device provenance join now checks both
exports for all 51,829 devices and 206,708 terminal bindings: pre-R node
names match original conductors, post-R names/private IDs match the
independent native geometry audit, and original/constrained voltage and
conductor IDs are retained. Both complete parameter token sets are stored
without unit conversion or selecting physics. Exactly the retained X14/X52
source-area/perimeter discrepancies remain unresolved. The receipt and full
ledger are under `build/signoff400/startup_timing_native_device_provenance_001`.
The strict parameter-equivalence gate remains false, as do finite-R bulk
assignment, physical device binding, runtime eligibility, and RC qualification.

Current PDK model inventory for the two unresolved X14/X52 device types
checks 1,890 bins across all five process corners: distributed body
resistance is enabled, all five model body-resistance parameters are 50,
and the standard MOS instances do not override them. This explains why
external D/S/B aliasing is insufficient to establish an internal junction
short; it is an inference from model topology, not a causal-isolation
simulation or recovery of the failed probe model hashes. The strict failure
and both parameter exports remain preserved. Receipt:
`build/signoff400/startup_timing_native_body_resistance_inventory_001/assessment.json`.
The completed timestep/reltol/abstol controls are independently reconciled
for all 15 PVT points: 2,430 fixture comparisons, no changed outcomes, no
unmatched metrics. Observed maximum metric changes are 0.046272988694896766,
0.052785076030834044, and 0.015440920805173675 ps respectively. Full signed
observations are under `build/signoff400/startup_timing_mux2_4_numerical_review_001`.
No uncertainty threshold, domain enclosure, interpolation qualification,
or physical timing qualification is inferred.

The compiled conductance edge evaluator now has validated OpenMP execution at
1, 4, and 8 threads: every one of the 9,147,054 output rows is bit-identical
across thread counts for both tested vectors on the known and symbolic-unit
graphs, and matches the independent streamed edge scatter. See
`build/signoff400/startup_timing_G_edge_operator_controls_002/assessment.json`.
Nonisolated known-graph apply times were 0.990/0.524/0.384 seconds for the
conductor-constant vector and 1.048/0.552/0.587 seconds for the vertex pattern
at 1/4/8 threads. These measurements exclude graph loading and do not establish
end-to-end solver speedup. Native MNA integration and physical RC qualification
remain incomplete.

A bounded compiled stored-symmetric matrix operator preserves diagonal and
signed off-diagonal coefficients and evaluates rows with OpenMP. Exact dense
dyadic controls (including negative diagonals, positive off-diagonals, empty
rows and an empty matrix) and invalid dimension/memory/thread/vector controls
pass. On the retained native SPICE capacitance matrix, all 1,893,230 rows of
both constant and nonconstant vectors match an independent streamed symmetric
scatter and are identical at 1/4/8 threads, covering 20,735,077 stored upper
records. The nonconstant apply times were 1.300/0.542/0.329 seconds, measured
without isolation and excluding matrix loading. Receipt:
`build/signoff400/startup_timing_symmetric_operator_controls_001/assessment.json`.
Coefficients remain in raw EXT capacitance units (1e-18 F); MNA integration
must explicitly apply SI scaling. This control does not qualify the physical
capacitance model, full spatial C operator, or native transient solver.

The exact GMP diagonal-dominance audit fixes the ideal reference voltage
to zero and checks every remaining original-conductor row in parallel
independent matrix jobs. Strict/weak sufficient-certificate controls, an SPD
matrix that fails DD, an indefinite matrix, an alternate reference and a
negative margin of exactly 2^-64 pass:
`build/signoff400/startup_timing_grounded_C_diagonal_dominance_001/assessment.json`.
The physical-integral principal matrix has 450,341 negative DD margins and
98,494 positive grounded off-diagonal records. Its maximum negative-margin
to absolute row-sum ratio is exactly 96674408926928490417 /
3704110520084526980785 (approximately 0.0260992). The retained native SPICE
principal matrix has 329,491 negative margins but a maximum ratio of only
459 / 9700681539762010455499 (approximately 4.73163e-20), with no positive
grounded off-diagonals. Neither matrix receives a DD passivity certificate;
failure of this sufficient condition is not proof of indefiniteness. No
coefficients were changed. Full spatial passivity and physical qualification
remain open; the physical-integral result requires a stronger certificate.

A stronger exact weighted certificate now proves strict positive definiteness
of the ideal original-conductor physical-integral principal capacitance matrix
after fixing reference ID 0. An eight-core compiled Jacobi comparison-matrix
search found positive weights in 11 iterations; the separate GMP verifier
checked every stored coefficient and all 1,893,229 grounded rows using exact
dyadic arithmetic. Every weighted margin is strictly positive, including in
the presence of 98,494 positive off-diagonal records. Receipt and pinned
positive vector:
`build/signoff400/startup_timing_weighted_C_diagonal_dominance_001/assessment.json`.
For positive diagonal D=diag(z), the checked inequalities
A_ii*z_i > sum(j!=i)|A_ij|*z_j make D*A*D symmetric strictly diagonally
dominant with positive diagonal, proving SPD by congruence. The candidate
search itself is not a proof. Controls include a known SPD matrix failing
ordinary DD, a matrix receiving no sufficient certificate, and rejection of
zero/negative weights or a nonzero reference weight. No matrix coefficients
were changed. This certificate resolves the coarse grounded physical-integral
passivity check; it does not prove full spatial C passivity, the rounded
unfixed reference nullspace, finite-resistance substrate assignment, or
physical RC qualification.

Compiled reassessment of all 15 retained legacy combinational waveforms
checks 13,365 fixture/PVT observations and preserves every previously reported
record field. All propagation checks pass; 32 strict slew failures occur only
on unused xnor2_4, xor2_2 and xor2_4 masters at zero external load and a 20 ps
input ramp. Receipt:
`build/signoff400/startup_timing_raw_strict_slew_audit_001/assessment.json`.
Joining every strict result and the separate mux2_4 raw campaign to the exact
current master inventory gives 12,285 passing propagation/strict-slew
observations across all 36 current combinational masters at all 15 PVT
points. Receipt:
`build/signoff400/startup_timing_current_raw_slew_coverage_002/assessment.json`.
The failed first summary attempt is retained in `_001`; `_002` correctly
binds mux point plans through their native per-point receipts. The unused
master failures are retained without waivers. Raw-grid coverage does not
qualify extracted loads, interpolation, sequential constraints or physical
timing.

An independent mux2_4 startup-settling campaign is running at
`build/signoff400/startup_timing_mux2_4_settling_control_001`: input delay
2 ns to 12 ns, stop time 34 ns to 44 ns, with pulse shapes, models, loads,
maximum step and tolerances preserved. Eight native single-thread workers
use shared CPU/RAM admission and the controlled compiled assessor. The
exact-producer watcher in
`build/signoff400/startup_timing_mux2_4_settling_review_followup_001` will
reconcile all four numerical controls into
`build/signoff400/startup_timing_mux2_4_numerical_review_002` after the
settling grid completes, without automatic identical retries. Completion
and numerical-domain qualification remain unproven pending those receipts.

The compiled streaming sequential assessor matches every retained full-array
Python record at all 15 PVT points: 1,620 clock-to-Q/asynchronous-assertion
fixtures, including output rail extrema and direction-specific slew arrays.
A deliberately failing initial-state control remains failed; missing or
duplicate terminal markers, nonmonotone time and wrong columns are rejected.
Receipt: `build/signoff400/compiled_sequential_assessor_controls_001/assessment.json`.
The future adapter is exercised inside the pinned native image and matches
all 108 retained TT records:
`build/signoff400/compiled_sequential_assessor_adapter_controls_003/assessment.json`.
Failed adapter controls `_001` (historical mutable release-manifest hash)
and `_002` (leftover combinational status field) retain their sources and
failures. `_003` verifies the retained waveform/plan/receipt and controlled
parser; it does not claim to revalidate the historical mutable manifest.

`build/signoff400/startup_timing_sequential_step_control_001` is running
new native one-parameter max-step controls (2 ps to 1 ps) over 108 fixtures
at each of 15 PVT points. Up to 16 single-thread native cases share CPU/RAM
admission with existing work, each bounded to 4 GiB. All other deck tokens
are identical. Each new worker checks historical model/engine hashes plus
explicit current control inputs; it does not inherit a stale mutable release
manifest as a simulation input. New assessments use the controlled compiled
sequential adapter. Numerical results remain pending, and these propagation
controls do not qualify setup/hold, recovery/removal, pulse width, load
interpolation or physical timing.

The mux2_4 settling campaign and independent four-control review are complete:
`build/signoff400/startup_timing_mux2_4_numerical_review_002/assessment.json`
reconciles 3,240 fixture/control comparisons across all 15 PVT points. Every
propagation and strict-slew outcome is unchanged and every metric matches
inventory. The extra 10 ns settling variant has a maximum observed metric
change of 0.00537932 ps; the largest across all four variants remains
0.0527851 ps. These are measured perturbations, not certified numerical
error bounds or physical timing qualification.

The derivative `tools/sheet_charge/stream_project_charge_v2.cpp` supports
disjoint byte-range tasks and shares each immutable field map across tasks.
It validates complete gap-free partitions per canonical source file and
rejects conflicting field maps. `bounded_jsonl_range.hpp` owns each record
by its first byte and requires newline termination. Initial controls pass
209 exhaustive ownership trials and three invalid-input checks. A 17-range,
97-actual-operator projection preserves both node maps and all sparse
contribution counts, with normalized matrix difference 1.822e-22 from the
sealed oracle. Those mathematical results are retained in
`build/signoff400/startup_timing_chunked_projection_controls_001`. Its geometry
loader requests 8/7 threads despite the 2-core projection reservation; the
resource-accounting correction is recorded in `resource_admission_note.json`.
The corrected controller in
`build/signoff400/startup_timing_chunked_projection_controls_002` sets
OMP_THREAD_LIMIT=2 for the whole process and separately checks that an
eight-thread OpenMP request obeys that cap. That corrected validation is
pending its terminal receipt. The active full projection and all its frozen
inputs remain unchanged; no duplicate full projection has been started.

Current diode compatibility support is now bound to the actual 400 MHz
candidate: all 280 diode devices match the 280 symbolic ndiode tiles
one-to-one, joining all 560 unresolved end stubs. Of these devices, 278
have the independently checked HS geometry and two have the checked HD
geometry. All native instance names and terminal order are preserved on
explicit `_v<zero-R-constrained-voltage-id>` nodes. Fifteen fixed-temperature
corner fragments exactly reproduce the density model cards from completed
native diode comparisons. Existing HD/HS electrical/noise evidence and
foundry-model hashes were rechecked, with no new simulations:
`build/signoff400/startup_timing_current_checked_diodes_001/assessment.json`.
The companion `zero_R_lineage_check.json` confirms the device and known-G
proofs use the same exact zero-R map. The fragments require matching global
Xyce temperature. Device compatibility does not select an ndiode sheet law:
internal series resistance is not reused as sheet resistance, and the 560
end-stub conductances remain symbolic. Full PLL integration, final producer
node-map reconciliation and physical model qualification remain incomplete.

A fresh same-circuit TT/27 C diagnostic compares X14/X52 native and retained
junction parameters using original body-network models and private copies
with only the body selector disabled. All 378 relevant TT model bins are
covered. Wrapper/model identifiers are private; all other model text is
reversibly preserved, and original/derived model hashes are checked before
and after DC and AC simulation. The native models still fail the original
strict comparison; disabling the body network makes the two parameter
variants produce identical printed DC/AC responses, with split-terminal
sensitivity controls retained. Receipt:
`build/signoff400/startup_timing_junction_body_network_cause_003/assessment.json`.
Independent named-column complex-current review:
`build/signoff400/startup_timing_junction_body_network_cause_review_001/assessment.json`.
This establishes observed body-network involvement only at TT27; physical
effects versus numerical conditioning are not separated. It does not
recover missing pre-run hashes for the old failed probe, waive that failure,
select either junction allocation or adopt modified models. Failed preparation
`_001` (numeric selector format) and native `_002` (auxiliary wrapper name
collision) retain their sources and diagnostics.

Model preparation now has validated linear edit ledgers and directive-only
dependency tokenization. Both actual model copies reconstruct byte-for-byte,
synthetic line-ending/no-final-newline/UTF-8 cases pass, and five malformed
edit ledgers are rejected. The fast and original scanners return exactly
the same 319 dependency files, with observed nonisolated times 0.804 s and
22.285 s respectively. The two actual edit-ledger/reconstruction checks took
0.161/0.122 s. Receipt:
`build/signoff400/startup_timing_fast_model_preparation_controls_002/assessment.json`.
These controls add no native simulations or model adoption.

Current generic-poly devices now have direct PDK DC/AC cross-simulator
evidence. The 24 instances use two native geometries: twenty w=0.51/l=0.045
and four w=0.48/l=0.5, in micrometers. All native parameter tokens, source/drain
order and exact constrained terminal IDs are retained. Direct ngspice47
versus Xyce comparison at all 15 PVT points found mismatches at every point,
with maximum scaled current difference 0.191325:
`build/signoff400/startup_timing_current_generic_poly_models_003/assessment.json`.
At TT/-40 C, reference values are 53.5273/4.49912 ohms while the direct native
wrapper gives 50.2083/4.25294 ohms. The native response omits the observed
width/temperature effects; it is not accepted as an equivalent primitive.
Failed `_001` (reference provenance lookup) and `_002` (missing 400 MHz
reference AC endpoint) are retained; `_003` requires exact 1/400 MHz samples
with 400 MHz interior to the reference sweep.

The corrected views explicitly evaluate the foundry law
rp1*l/(w-1e6*(-tol_poly-poly_dw)) *
(1+tc1rsgpu*(T-30)+tc2rsgpu*(T-30)^2). Corner parameters come from the pinned
PDK; MC_MM_SWITCH must be zero, and effective widths/resistances must be
positive. The geometry expression also matches the foundry scalar-wrapper
formula. Fifteen fixed-PVT definitions reproduce all reference DC and AC
responses with maximum scaled difference 2.77502e-16:
`build/signoff400/startup_timing_checked_poly_translation_001/assessment.json`.
An independent review verifies all 24 actual device assignments and all
30 PVT/geometry scalar values, with maximum decimal-to-emitted relative
difference 1.541e-16:
`build/signoff400/startup_timing_checked_poly_translation_review_001/assessment.json`.
These are numerical compatibility controls, not a silicon error enclosure.
The selected definitions require matching corner/global temperature, and
noise equivalence, Monte Carlo, ordinary sheet-G PVT laws and full PLL
integration remain unqualified. MOS compatibility is also still open: current
native sequential logs report BSIM4 4.5 fallback to 4.6.1 and a junction-
potential clamp. Raw propagation coverage does not qualify those semantics.

The exact current MOS inventory contains 51,525 devices in five model
families, 33 model/W/L pairs and 476 complete parameter profiles. Both pre-R
and post-R parameter alternatives for X14/X52 are preserved without selecting
a physical allocation:
`build/signoff400/startup_timing_MOS_backend_profiles_001/assessment.json`.
A bounded first TT27 batch covers 16 profiles, all five families, and both
unresolved alternatives: 96 DC fixtures and 864 AC bias/excitation fixtures
produce 9,600 four-terminal response comparisons. The worst absolute AC
difference is 3.059e-7 A, or 4.638% for that sample, on an unresolved junction
profile at 400 MHz with bulk excitation. This is evidence of a backend
response gap, not a qualified physical error bound:
`build/signoff400/startup_timing_MOS_backend_batch_control_001/assessment.json`.

The compact worker preserves every generated circuit and observation vector
for all 476 profiles (60 DC/AC generation batches). Equivalent first-batch
AC JSON metadata drops from 44,981,460 to 219,348 bytes by removing repeated
instance-population lists from each bias fixture:
`build/signoff400/startup_timing_MOS_backend_worker_upgrade_001/assessment.json`.
`build/signoff400/startup_timing_MOS_backend_grid_001` is running the full
450-batch, 15-PVT finite grid, targeting 7,140 profile/PVT observations and
4,284,000 terminal-response comparisons. The sealed initial benchmark is
reused without resimulation. One new case validates caller-owned CPU/RAM
lease handoff before broad launch. Up to 14 single-thread native workers,
each bounded to 4 GiB, leave two slots for projection controls alongside
the live 16-core projection reservation. All cases retain both simulator
outputs and exact model/binary input hashes. Numeric screens remain
diagnostic: full response enclosures, physical junction allocation and
MOS backend compatibility are not qualified by this grid.

The selected 400 MHz DCO control with 302 physical programming drivers completed
60 ns normally in 5,903 s. Its matched-startup-age frequency remains about
1,099 ppm above the full native circuit. The recorded physical programming
inputs start at coarse 0/fine 128 and finish at coarse 20/fine 111; 16 fine
inputs have logic excursions despite equal endpoints. This is an observed
history mismatch, not proof of floating-charge causality. Separate controls
now test MPI consistency, an expanded physical receiver load layer, and
recorded programming/reset history. See
`verification/prototype400/selected_dco_backend_screen.json` and
`verification/prototype400/selected_dco_programming_history.json`.

The physical feedback flip-flop and its real output loads completed the
conditional detector control with one captured event per DN/UP pulse.
New probes retain the recorded fast synchronizer clock and test a falling
feedback aperture against the first reference edge. Their results must be
checked for pre-reference activity before interpreting detector state.
These controls do not qualify the detector model or satisfy release gates;
see `verification/prototype400/selected_detector_physical_driver_controls.json`.

The complete 260 ns recorded-boundary control now has a formal comparison:
`verification/prototype400/selected_streaming_full_window.json`. Its PLLOUT
frequency differs by -0.2003 ppm and its largest matched rising-edge difference
is 0.0367 ps, while peak saved-time voltage error is 1.894 mV and fails the
original 1 uV diagnostic screen. Recorded exterior histories are prescribed;
this is not standalone tuning-model or closed-loop qualification. The frozen
TT detector fit also matches both observed real-feedback-driver reference
windows and every available output edge within its existing fit band plus
1 ps quantization, without refitting. The new reference-level checker retains
no/both decisions and pre-reference detector activity explicitly.

The prototype auditor now recomputes closed-loop functional limits from each
case's pinned edges, control changes, segments and completion log. A receipt's
`passed` flags cannot replace the raw measurements. The auditor also checks
phase coordinates against the raw REF/DIV edges and restricts the common gain
pair to the declared search. Regression controls include a passing 400 MHz
trace, a falsely marked 500 MHz trace, missing control provenance and altered
phase coordinates. This strengthens evidence checking without changing the
prototype acceptance limits or qualifying any current diagnostic model.

A serial full-circuit reset-state queue is waiting for the original TT fine-112
calibration assessment. It will capture FF, SS, SF and FS initial voltages in
1 ps native runs, retaining every saved voltage and the same candidate circuit.
Each case uses the pinned release container, 16 ranks, a 64 GiB reservation and
a one-hour cap. The queue observes other full-native workers and does not run
alongside one. These snapshots establish corner-specific initialization only;
programming histories, target tuning and interface qualification remain open.
See `verification/prototype400/selected_corner_initial_states.json`.

The completed 5610-device DCO MPI control measures 1.1207x wall speedup from
one rank to four (5903.15 s versus 5267.53 s). The same circuit's measured
frequency differs by -0.092 ppm and its maximum oscillator edge difference is
0.0211 ps. This is one timing trial, not numerical convergence qualification.
Independent reduced-control batches retain the serial default; four ranks can
reduce latency when cores are otherwise spare. The matched four-rank receiver
load comparison isolates a -40.82 ppm shift with a strict circuit superset and
identical common boundary voltages. Remaining exterior loads are not bounded,
and the full-circuit frequency discrepancy remains unresolved.

The physical-driver detector control with the recorded synchronizer clock
completed normally and passes the frozen TT detector fit without refitting.
Both observed reference-window decisions and all available output-edge counts
match; maximum edge error against the fit is 0.460 ps. A circuit/source audit
isolates the synchronizer-clock substitution: native detector output edges
move by at most 0.0143 ps, while first-synchronizer output edges move by up to
490.33 ps. Decision agreement does not qualify receiver or clock-domain timing.
The exact comparison is retained in
`verification/prototype400/selected_detector_physical_driver_controls.json`.

The recorded-clock native pulses now replay through the frozen RTL event
receiver with the candidate divider/filter parameters. The bench adapts reset
to the observed internal receiver boundary; it never forces DUT storage.
Both event counts match, but the UP first receive stage samples one clock
cycle earlier in zero-delay RTL at that same physical clock boundary. The
native event Q changes at 63.132 ns, after the 62.752 ns receiver edge; native
first-stage capture therefore uses the next edge. The zero-delay event Q is
already visible before 62.752 ns. DN captures on the same cycle in both runs.
See `verification/prototype400/selected_receiver_cycle_replay.json`.

This identifies a missing timing effect at the receiver boundary. It does not
establish a full-loop decision-cycle error: root-clock distribution, later
receive stages, and guarded decision timing must be correlated together.
Receiver and complete-controller timing remain unqualified. No timing offset
has been patched into the detector fit, and the candidate RTL is unchanged.

A separate receiver publication adapter now uses event-flop delays measured in
native control 273 and validates against independent recorded-clock control
280. Both first-stage sampling cycles match after this adjustment, including
the UP event that previously landed on the wrong sampling clock. The adapter's functional
BBPD delivery input represents event publication to the zero-delay RTL flop;
it is not the physical BBPD output voltage. Scope is limited to TT first
post-reset positive event publications at the local physical receiver clock.
The main PLL model remains unchanged. Opposite event transitions, later receive
stages, root-clock distribution and full-controller timing remain unqualified.

The full coarse20/fine112 TT calibration completed 260 ns normally, with all
saved values finite. Its 200--260 ns output frequency is 392.670114 MHz,
compared with 392.310318 MHz at fine111. Native stimulus replay through the
actual startup RTL matches all six observed endpoint fields; PLL_ENABLE and
TRACKING remain low, so this is not enabled-handshake or lock proof.

The reduced fine112 control remains +863.6 ppm above its full reference at
matched oscillator ages. Its two-code frequency difference is about 21.3%
smaller than the full model's, so a constant frequency-offset correction is
not qualified. The secant selector requests native fine133 near 400 MHz. One
full-native calibration is queued after the corner-initialization queue, then
its measured point will attach and the actual RTL diagnostic will use the
closest measured seed. No predicted frequency enters the tuning table.

The first-reference falling-aperture probe completed normally. At a measured
feedback falling offset of -116.16 ps, native decides UP and captures one event.
There are no detector edges before the first reference at 60 ns. The frozen
rising-neighborhood detector model matches the observed decision and output
edges within its existing fit-band-plus-quantization allowance, without refit.
One opposite-side companion and one repeated-DN publication control are live;
these add validation points rather than assuming a full aperture bound.

The receiver publication adapter also passes independent native phase20,
phase30 and first-reference falling-aperture controls without refitting. The
five active event publications in these three controls all land on the native
first-stage clock cycles, alongside the two earlier recorded-clock holdout
events. An inactive role is checked for zero events rather than fabricated
activity. These are local receiver-boundary checks; later stages, opposite
event transitions and all-corner full-controller timing remain open.

Full FF and SS reset-state initializations completed with all saved voltages
finite. A new corner-aware conditional probe path binds only a matching solved
corner snapshot and rejects mismatched corners or nonfinite vectors. Its TT
prepare-only control reproduces the existing native TT circuit, every voltage
source, and solver/observation settings exactly. Two FF detector/publication
probes are running with the solved FF exterior biases and unchanged geometry.
Their upstream clock/data excitation is still the recorded TT packet; these
are controlled FF response measurements, not full FF sender or PLL correlation.
See `verification/prototype400/selected_detector_corner_controls.json`.

The TT publication adapter now selects separate observed delays for event-Q
rising and falling transitions. An independent actual-RTL receiver replay
matches native first-stage sampling cycles. Missing directions are rejected;
DN falling coverage and complete-controller timing remain open. The four
recorded phase detector holdouts also pass the frozen fit without refitting.
See `verification/prototype400/selected_publication_direction_model.json`.

A separate DCO performance control eliminates 5,963 unobserved constant-voltage
cut nodes connected only through linear capacitors, reducing solver unknowns
from 35,410 to 23,484. Retained differential equations are unchanged; absolute
charge, energy and removed-source currents require reconstruction. The native
accuracy/speed comparison is running; this reduction is not yet qualified.
See `verification/prototype400/selected_constant_cut_control.json`.

The physical receiver continuation contains five CLKBUF2 cells per role before
the next synchronizer, whose clock is a different tree node. A new native
control retains those paths and both next-stage flops, driven by the recorded
next-stage clock. The prepared deck retains all original device lines; its
only changed shared boundary source activates that previously held clock.
Native measurement and automatic two-stage RTL comparison are pending.
See `verification/prototype400/selected_second_stage_controls.json`.

Full FF, SS, SF and FS reset-state initializations now all completed normally
with every saved voltage finite. These are reset-only snapshots, without
tuning or tracking qualification. The exclusive full-circuit queue has moved
to the requested TT coarse20/fine133 measurement. Three new small controls
also match the pinned live executable and all 319 PDK include-file bytes.
See `verification/prototype400/selected_complete_corner_initializations.json`.

Source binding correction: the selected filled layout was built with a
negative-edge decision register and static divider configuration. Earlier
mixed-signal runners compiled a different RTL revision with a positive-edge
decision register and registered divider configuration. New version-4 mixed
signal runners use exact source bytes pinned by the physical layout receipt,
retained under `rtl/selected400`, and reject changed RTL or unrelated GDS.
The matching-source startup replay agrees with all six native endpoint fields;
the loop still requests unmeasured fine113. Legacy full-controller results
cannot qualify this physical candidate. Local receiver-only observations keep
their existing scope. A matching-source replay of the active calibration is
queued without changing its native job or old receipts. See
`verification/prototype400/selected_physical_RTL_binding.json`.

The independent unprimed falling-edge companion completed normally. Its
measured feedback offset of -96.16 ps produces DN, opposite to UP at -116.16 ps
in the earlier sample. The frozen detector fit predicts both decisions, event
counts and observed output edges without refitting. This brackets the sampled
falling transition for the retained waveform and initialization; it does not
establish a uniform aperture or uncertainty bound. See
`verification/prototype400/selected_falling_aperture_pair.json`.

The retained full TT fine111 waveform exposes dynamic forcing omitted by the
reduced DCO constant cuts. Of 6,303 nonrail held boundaries, 5,961 connect by
literal capacitors to retained voltage unknowns; 1,784 of those vary by more
than 0.1 V over 200–260 ns. The strongest ranked omitted forcing includes
clock-tree and feedback nodes. Connections between prescribed voltages are
excluded from the unknown-equation ranking. This demonstrates a boundary
approximation, not its frequency-error contribution or a qualified uncertainty
bound. See `verification/prototype400/selected_DCO_boundary_variation.json`.

A new reduced-DCO control retains five complete physical clock-buffer cells
(170 primitives), making seven of the eight strongest ranked dynamic boundary
voltages native unknowns driven by the retained circuit. The remaining ranked
feedback-state frontier is explicit. Preflight preserves every original
device/passive line, shared boundary value, corner, solver setting and horizon.
The native control is running; full boundary coverage and frequency correlation
remain unqualified. See
`verification/prototype400/selected_DCO_coherent_clock_control.json`.

The retained full fine111 CSV has now been independently re-extracted from
the immutable native RAW and reproduced byte-for-byte; its original assessment
also reproduces exactly. An automatic follower will compare the clock-buffer
control with both the original reduced baseline and this checked full reference
after normal native completion. See
`verification/prototype400/selected_fine111_reference_provenance.json`.

A resistor-connectivity guard confirms that all seven resolved clock nodes
and every added clock-buffer/inverter output have no prescribed voltage cut
on their resistive components. A separate surviving-boundary audit finds 40
nonrail, nonprogramming resistor-connected constant cuts. Two switch by about
1.8 V in the full native trace and both belong to REFCLK. Their reference-input
forcing remains a separate unqualified approximation; the five-buffer control
does not claim to close it. See
`verification/prototype400/selected_DCO_resistive_boundaries.json`.

The repeated-DN native test completed normally, measuring DN event-Q fall
publication at 456.96 ps versus 473.86 ps for rise. The new TT packet now has
measurements for all four UP/DN Q directions; its independent DN-fall holdout
is still running. The first FF repeated-UP control also completed, with rise
and fall publication at 348.79 ps and 343.30 ps. FF uses solved FF initial
biases under the same recorded TT excitation; FF sender correlation remains
open. Mixed TT/FF training is rejected without writing parameters. A separate
phase-zero FF holdout is running and its comparison is queued. These remain
local receiver diagnostics, without uniform timing uncertainty qualification.
See `verification/prototype400/selected_publication_corner_measurements.json`.

An isolated REFCLK sensitivity control now replaces only the two resistor-
connected reference boundary DC values with recorded full-native voltages.
The 200–260 ns source window is cropped and translated to 0–60 ns, without
time warping or extrapolation; simplification stays within 1 uV of the recorded
piecewise-linear curves. Preflight confirms identical device/passive bytes,
source inventory, programming, solver and observation protocol. The native
control and comparison follower are running. Their effect is conditional on
the tested histories, not a universal exterior or frequency/phase uncertainty
bound. See `verification/prototype400/selected_reference_forcing_control.json`.

The FF repeated-DN control completed normally. The FF publication packet now
measures all four directions: UP rise/fall 348.79/343.30 ps and DN rise/fall
354.57/345.46 ps. Independent FF holdouts are running for phase zero, repeated
DN, and repeated UP with falling data deliberately near the first-stage clock.
The near-aperture stimulus is chosen from training observations; its actual
sampling outcome is not presumed. Model uncertainty must explain any capture
cycle variation before full-controller validation. All remain conditional on
recorded TT upstream excitation, not full FF sender correlation. See
`verification/prototype400/selected_FF_direction_holdouts.json`.

A separate version-5 mixed-signal diagnostic can interpolate frequency or
period between native tuning knots, strictly within each measured coarse-bank
span. Every estimated row is marked as interpolation; native registry points
are unchanged and extrapolation remains forbidden. The adjacent 111/112
control produces the identical native table and still requests fine113. Three
unit controls pass. Independent model holdouts and a frequency-error bound
remain unqualified. See
`verification/prototype400/selected_bounded_frequency_interpolation.json`.

The five-buffer native control completed normally through 60 ns with every
saved value finite. At matched oscillator ages 10–40 ns it shifts frequency
by -36.25 ppm relative to the original reduced baseline, leaving +1,063 ppm
against the full native reference. It therefore does not close the reduced-
model gap. The original comparison calculation succeeded, but its wrapper
tried to hash an output directory. A separate recovery re-computes the saved
comparison identically and fixes the wrapper path for future controls, without
a native retry. See `verification/prototype400/selected_DCO_coherent_clock_result.json`.

The independent repeated-DN control completed normally. The TT direction-
aware packet now passes independent native first-stage cycle/count checks
for UP rising/falling and DN rising/falling publications, without fitting
validation timing. Its parameters reproduce the retained packet372 exactly.
This validates the sampled local receiver behavior; a uniform aperture bound
and full-controller timing remain open. See
`verification/prototype400/selected_TT_direction_holdout_result.json`.

The constant-cut benchmark completed normally. Frequency differs by +1.37 ppm
and oscillator edges by at most 1.47 ps from the original serial reference.
Wall time is 6,072.59 s versus 5,903.15 s (0.972x speedup), so this trial does
not justify adopting it for speed. Numerical convergence remains unqualified.
A separate fine112 five-buffer control is now running, with comparison to the
matching completed full fine112 reference queued to assess tuning slope. See
`verification/prototype400/selected_constant_cut_benchmark_result.json` and
`verification/prototype400/selected_DCO_clock_code_holdout.json`.

Conditional reduced-DCO FF and SS probes are running at coarse20/fine111.
They retain the same device/passive/source files as the TT clock-buffer
baseline; only the PDK corner and five additional clock observations change.
Retained devices use the requested corner, while prescribed exterior voltages
come from the TT final trace. Fresh local DC initialization is explicit; these
are preset/clock-edge guides, not full-corner calibration. Live simulator and
all 319 PDK dependency bytes match the pinned reference. See
`verification/prototype400/selected_conditional_corner_DCO_guides.json`.

The selected-layout antenna controls expose a coverage gap in the pinned Magic
flow: oversized poly and all six contact-array controls produce no feedback,
while LI1 and metal conductor controls are detected. An independent geometry
check passes conservative poly and LICON bounds for the actual selected GDS,
with oversized positive controls correctly rejected and all MOS channel area
preserved. Later contacts and diode protection remain unqualified; this does
not close the physical-integrity gate. See
`verification/prototype400/selected_antenna_coverage_and_early_bounds.json`.

The FS refinement at coarse20/fine180 completed normally at 400.062190 MHz
(+155.47 ppm), passing the conditional nominal-frequency check. The FF bracket
now requests a native coarse9/fine229 probe; its frequency is not assigned from
interpolation. These retained-device measurements still use TT-derived held
exterior biases and do not qualify full-corner calibration. See
`verification/prototype400/selected_FS_refined_result_and_FF_target.json`.

The independent SS phase-zero holdout matches the frozen publication model
for native first-stage sampling cycles and counts, with both nominal and
provisional 100 ps late-window replay. SF training now measures all four
publication directions; each has one observation, which does not establish
an uncertainty bound. Separate SF repeated-UP and repeated-DN holdouts are
running. See
`verification/prototype400/selected_SS_independent_result_SF_complete_training.json`.

An isolated logging build reproduces the missed contact feedback with unchanged
MOS geometry/connectivity. The 14-by-14 MCON fixture is counted as only 2-by-2
cuts. Contact areas are nonzero; a database/CIF unit mismatch is now under
controlled test. The release tool and PDK rules remain unchanged. See
`verification/prototype400/selected_magic_contact_area_diagnostic.json`.

The repaired-load fine111 control reached its original wall-time limit. Its
finite saved prefix covers the full matched oscillator-age window 10–40 ns:
392.656955 MHz versus 392.223307 MHz full native (+1105.61 ppm). Repairing all
missing input drives enables DC convergence but does not close the frequency
gap. This is a budget-stopped prefix result, not normal 60 ns completion or
model qualification. See
`verification/prototype400/selected_driven_load_budget_prefix_result.json`.

Converting database tile dimensions to CIF units in an isolated Magic control
restores feedback for oversized MCON and all four via arrays, while every
matched normal contact control remains clean. LICON remains missed. This
controlled result confirms a consequential unit mismatch; exact cut accounting,
early-plane coverage, diode protection, and parent qualification remain open.
See `verification/prototype400/selected_magic_contact_unit_control_result.json`.

Both repaired-load controls stopped at their original time limits with finite
prefixes covering matched oscillator ages 10–40 ns. Their measured 111-to-112
step is 0.281301 MHz versus 0.357858 MHz full native (-21.39%). Physical cards,
solver, and observations match; only the expected fine driver input changes.
The reduced tuning model remains unqualified and no offset correction is
applied. See
`verification/prototype400/selected_repaired_load_tuning_slope_result.json`.

The isolated Magic contact-unit and gate-plane control passes all 26 matched
fixtures: all 13 oversized conductor/contact negatives produce feedback, and
all 13 normal controls remain clean. MOS geometry/connectivity is unchanged;
the complete installed experimental tool is hash-pinned. A selected-parent
run is underway with this executable. Exact cut accounting, diode protection,
and parent antenna qualification remain open. See
`verification/prototype400/selected_magic_complete_engine_controls.json`.

Publication-delay training now covers all 20 direction/corner combinations
(TT/FF/SS/SF/FS, UP/DN, rising/falling). A verified frozen-model set requires
each corner and direction and forbids fallback. These local retained-circuit
measurements do not establish a uniform uncertainty bound or full-controller
timing. See `verification/prototype400/selected_five_corner_publication_models.json`.
The experimental selected-parent antenna run and its exact controlled-engine
inputs are retained in
`verification/prototype400/selected_experimental_parent_antenna_queue.json`.

The controlled experimental antenna engine completed on the selected parent
with zero feedback and 61,616 extracted MOS devices. Independent source/flat
comparison preserves all 16 checked masks after controlled M5 fill normalization;
source, flat, and extracted MOS gate area agree exactly at 11710.4958 um².
Exact contact cut accounting and diode-protection validation remain open, so
this does not yet qualify the parent antenna gate. See
`verification/prototype400/selected_experimental_parent_antenna_result.json`.

The experimental antenna build with generator-matched contact pitch arithmetic
passes all 26 matched rule controls. An actual HS diode control also passes:
an isolated diode leaves 17 oversized-M3 feedback entries; connecting the
diode to the gate net removes feedback. Native extraction verifies that
connection. The selected parent is being replayed with this exact executable;
whole-parent qualification remains open. See
`verification/prototype400/selected_magic_pitch_and_diode_controls.json`.

The SF coarse26/fine118 probe completed at 400.673698 MHz (+1684.25 ppm),
missing the conditional nominal-frequency limit. The measured bracket selects
fine115 for a new native probe, with no interpolated frequency assigned.
The refinement retains the same physical cards, solver, and TT-derived held
exterior biases; its input audit passes. See
`verification/prototype400/selected_SF_measured_target_refinement.json`.

The pitch-corrected experimental engine also completes on the selected parent
with zero antenna feedback. Its 26 matched rule controls and local diode
control pass, and independent comparison again preserves all 16 checked masks
and exact MOS gate area. General contact-area validation and portable release
tool integration remain open. See
`verification/prototype400/selected_pitch_corrected_parent_antenna_result.json`.

A standalone Magic 8.3.623 patch and explicit container toolchain recipe now
build from the SHA256/NAR-verified source archive without diagnostic logging.
The recipe-built executable passes all 26 matched rule fixtures and the actual
diode control. Its selected-parent replay is running. Use
`verification/signoff400/build_selected_magic_patch_v2.py` with the archive,
`tools/magic_antenna/antenna-8.3.623.patch`, and
`tools/magic_antenna/toolchain_sif_v1.json`; each build requires a new output
directory. Receipts and limits are in
`verification/prototype400/selected_reproducible_magic_patch.json`.

The source-verified recipe build completes the selected-parent replay with
zero antenna feedback. Independent comparison preserves all 16 checked masks
and matches source, flat, and extracted MOS gate area exactly. General contact
area bounding remains under validation. See
`verification/prototype400/selected_reproducible_magic_parent_result.json`.

The original 260 ns history-control run now has a duration-aware, read-only
comparison observer. The new comparator reproduces the completed 60 ns
frequency/startup regression exactly and explicitly checks either 60 or 260 ns
on normal completion. Budget-stopped prefixes remain marked as such. See
`verification/prototype400/selected_history_duration_followup.json`.

The duration follow-up uses a fresh V4 comparator, preserving native-deck
device-condition matching. The original V3 source is restored byte-for-byte.
V4 reproduces the 60 ns regression exactly with TT/27 C conditions verified;
its replacement observer waits for the original 260 ns history run. Earlier
regression654/observer655 are superseded and must not be used as evidence.
See `verification/prototype400/selected_history_duration_followup.json`.

A separate conservative antenna variant charges the larger of reconstructed
cut area and full painted-contact rectangle area. All 26 matched rule fixtures
and the local actual-diode control pass. Its selected-parent diagnostic is
running; general area-bound qualification remains open. See
`verification/prototype400/selected_conservative_contact_antenna_controls.json`.

The conservative contact-area engine completes the selected-parent diagnostic
with zero feedback. All 16 checked source/flat masks and exact MOS gate area
match again; matched rule and local diode controls pass. The general contact
area bound still needs an explicit qualification argument. See
`verification/prototype400/selected_conservative_contact_parent_result.json`.

The independent SS repeated-UP holdout completes normally and matches frozen
selected-RTL first-stage sampling cycles and counts for both UP transitions,
under nominal and provisional 100 ps replay. Publication predictions differ
from native by at most 0.176 ps without refitting. This local two-transition
result is not a uniform uncertainty bound or full-controller timing closure.
See `verification/prototype400/selected_SS_UP_independent_receiver_result.json`.

An independent output-only paint export proves that all six actual selected
contact masks lie inside the contact paint used by the conservative bound,
with zero outside area. LICON/MCON painted areas equal actual cut area; via
painted areas are larger. The original PDK file and selected GDS are unchanged.
Per-net accounting remains open. See
`verification/prototype400/selected_contact_paint_containment.json`.

The FS phase-zero holdout completes normally and passes independent frozen
selected-RTL first-stage sampling-cycle/count comparisons, under both nominal
and provisional 100 ps replay, without refitting. Repeated-UP/DN holdouts are
still running; uniform uncertainty and full-controller timing remain open.
See `verification/prototype400/selected_FS_independent_receiver_result.json`.

The independent SF repeated-UP holdout completes normally and matches frozen
selected-RTL first-stage sampling cycles/counts for both UP transitions, under
nominal and provisional 100 ps replay without refitting. Other SF/FS direction
holdouts and full-controller timing remain open. See
`verification/prototype400/selected_SF_UP_independent_receiver_result.json`.

The SS repeated-DN holdout completes and passes both replay policies. Together
with the independent repeated-UP holdout, all four SS publication directions
now have local independent first-stage sampling-cycle/count validation, without
refitting. Uniform uncertainty, second-stage corner coverage, and complete
controller timing remain open. See
`verification/prototype400/selected_SS_complete_local_receiver_validation.json`.

The SF phase-zero independent holdout also completes normally and matches
frozen selected-RTL first-stage cycles/counts under nominal and provisional
100 ps replay, without refitting. See
`verification/prototype400/selected_SF_phase_zero_receiver_result.json`.

The original history-driven DCO run stopped at its wall limit with a finite
prefix covering matched oscillator ages 10–40 ns. It measures 392.225160 MHz
versus 392.223307 MHz full native (+4.72 ppm); early/late differences are
+3.78/+5.60 ppm. This supports investigating history-consistent initialization,
but does not qualify other codes, tuning slope, or the later expanded circuit.
See `verification/prototype400/selected_history_consistent_DCO_result.json`.

A separate sparse-history diagnostic is running on the same retained physical
circuit. Its 303 source certificates preserve initial/final values and threshold
transition times: programming has a 1 mV bound, reset retains 1 uV. The original
strict clock helper is unchanged. Bounded knots drop from 201,024 to 13,352.
An actual Xyce probe verifies 1 ns quiet-window steps and 10 ps transition/
oscillation steps. The input audit passes; runtime speedup and response/charge
equivalence remain unqualified. The new native budget is 3 h/8 GiB. See
`verification/prototype400/selected_sparse_history_control.json`.

FF coarse9/fine229 completes normally at 400.038180 MHz (+95.45 ppm),
passing the conditional nominal-frequency check. The selector retains this
measured point. TT-derived held exterior biases remain explicit; this is not
full-corner calibration. See
`verification/prototype400/selected_FF_measured_target_result.json`.

SF and FS repeated-DN holdouts complete and pass both replay policies.
Together with repeated-UP results, each corner now has independent local
first-stage cycle/count validation for all four publication directions, without
refitting. Near-edge uncertainty, second-stage corner coverage, and complete
controller timing remain open. See
`verification/prototype400/selected_SF_FS_complete_local_receiver_validation.json`.

Seven guarded process views of the selected layout now pass an independent
audit: retained masks/MOS channels match, labels and future conductors/contacts
are excluded, and local contact stubs cannot join distinct current conductor
components. All current-layer views have zero conservative antenna feedback.
This is selected-layout evidence; release-tool integration and other physical
checks remain open. See
`verification/prototype400/selected_antenna_process_view_audit.json`.

The SF refinement at coarse26/fine115 completes at 399.911203 MHz (-221.99
ppm), passing the conditional nominal-frequency check. FF, SS, SF, and FS
now each have a measured conditional target within 1000 ppm. These fresh-local-DC
probes retain TT-derived exterior biases and do not qualify full-corner startup
or calibration. See
`verification/prototype400/selected_four_corner_conditional_targets.json`.

The selected antenna component now passes its reproducible qualification
command with frozen GDS/RTL/profile identity, the installed tool closure, all
26 rule controls, the actual diode control, independent geometry/paint bounds,
and all seven guarded process views. Three negative metadata controls reject
a missing stage, a mixed tool build, and a wrong GDS profile. This closes the
selected antenna component; the complete physical gate remains open. See
`verification/prototype400/selected_antenna_component_qualification.json`.

A [same-network DCO history audit](verification/prototype400/selected_same_network_history_pair.json) now verifies identical device cards, quiet boundary sources, solver settings and observation nodes for the static and recorded-history controls. At TT coarse20/fine111, the common 10–40 ns oscillator-age frequency error changes from +1099.42 ppm to +4.72 ppm when the 302 programming inputs and reset use their recorded histories. This diagnoses the combined history effect for one code; independent-code correlation, code-step response and numerical uncertainty remain required.

The [independent fine112 history holdout](verification/prototype400/selected_fine112_history_holdout.json) uses all 303 input histories extracted from the completed full-native fine112 run, with its RAW checksum reverified. Its endpoints are coarse0/fine128 and coarse20/fine112; 14 channels show intermediate logic excursions. The reduced native experiment uses 13,248 bounded knots, one CPU, 8 GiB and a three-hour cap; its actual simulator and 319 PDK dependencies match the retained runtime reference. The terminal frequency comparison is pending, so this remains diagnostic evidence.

An [explicit five-corner electrical margin screen](verification/prototype400/selected_explicit_electrical_margins.json) now reports the worst constrained pins instead of relying only on absence of violations. All five supplied-capacitance-envelope views pass at 402.1 MHz, but SF has only 0.299 ps of slew margin at the `sky130_fd_sc_hs__a21oi_4` driver of `DCO_THERM[226]`. The minimum capacitance margin is 27.0 fF. These are conditional screens; native model uncertainty, unconstrained-pin coverage and the startup frequency range remain open.

The [physical programming-driver inventory](verification/prototype400/selected_programming_upstream_drivers.json) traces all 302 DCO input paths through extracted resistor connectivity and physical hierarchy. Each DCO HS INV2 input is driven by an HS INV8 output buffer. For the narrow SF `DCO_THERM[226]` path, that buffer is driven by the identified AOI4 output. A native loaded-path check must retain this chain and its extracted wires; the digital timing screen’s 5 fF output load does not establish the complete parent load.

A [native loaded programming-path screen](verification/prototype400/selected_loaded_programming_screen.json) now retains the physical AOI4, INV8, INV2, six-device DCO enable-inverter load, four antenna-diode cells and 20,161 incident passive elements. A guard rejects direct or resistive output clamps. The first SF A1 case at a 1 ns input slew measures AOI output slew of 857 ps rising / 350 ps falling, and DCO inverter input slew of 55 ps / 85 ps. The remaining TT/SF arcs and four receiver phase states are running; static exterior coupling and sampled slew keep this diagnostic until further correlation and coverage checks.

A [saved-state DCO diagnostic](verification/prototype400/selected_saved_state_DCO_control.json) tests skipping the costly programming interval by importing all 5,980 private voltages from the actual full-native 175.001 ns knot. A native RC control verifies Xyce `.IC`/`UIC` voltage initialization, analytic decay and charge balance. The separate 85 ns run shifts all 303 prescribed histories and retains the original circuit and quiet exterior biases, with one CPU, 8 GiB and a three-hour cap. That `UIC` run failed near 10 ps and is rejected. A [separate constrained-DC diagnostic](verification/prototype400/selected_saved_state_DC_DCO_control.json) preserves the saved circuit voltages during DC while solving unspecified variables, then releases the constraints for transient. Its oscillator-age comparisons are pending; nonlinear restart and exterior charge-state equivalence remain unqualified.

The [full-native TT fine133 result](verification/prototype400/selected_TT_fine133_native_result.json) completed normally: coarse20/fine133 measures 397.235 MHz over 200–260 ns, about 6,912 ppm below 400 MHz. This extends the measured tuning curve but does not qualify a target preset. The registry suggests fine146 only as a measurement hint; the already queued upper-bracket campaign has advanced to its next native run.
