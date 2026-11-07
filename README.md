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

A [native loaded programming-path screen](verification/prototype400/selected_loaded_programming_screen.json) now retains the physical AOI4, INV8, INV2, six-device DCO enable-inverter load, four antenna-diode cells and 20,161 incident passive elements. A guard rejects direct or resistive output clamps. The first SF A1 case at a 1 ns input slew measures AOI output slew of 857 ps rising / 350 ps falling, and DCO inverter input slew of 55 ps / 85 ps. All 24 TT/SF cases and four receiver phase states completed: the worst AOI output slew is 879.9 ps at SF and 618.0 ps at TT. Repeating the worst SF case with 1 ps maximum step and tenfold tighter tolerances changes any observed slew by at most 0.034 ps. Static exterior coupling, sampled slew and partial library coverage keep this diagnostic.

A [saved-state DCO diagnostic](verification/prototype400/selected_saved_state_DCO_control.json) tests skipping the costly programming interval by importing all 5,980 private voltages from the actual full-native 175.001 ns knot. A native RC control verifies Xyce `.IC`/`UIC` voltage initialization, analytic decay and charge balance. The separate 85 ns run shifts all 303 prescribed histories and retains the original circuit and quiet exterior biases, with one CPU, 8 GiB and a three-hour cap. That `UIC` run failed near 10 ps and is rejected. A [separate constrained-DC diagnostic](verification/prototype400/selected_saved_state_DC_DCO_control.json) preserves the saved circuit voltages during DC while solving unspecified variables, then releases the constraints for transient. Its oscillator-age comparisons are pending; nonlinear restart and exterior charge-state equivalence remain unqualified.

The [full-native TT fine133 result](verification/prototype400/selected_TT_fine133_native_result.json) completed normally: coarse20/fine133 measures 397.235 MHz over 200–260 ns, about 6,912 ppm below 400 MHz. This extends the measured tuning curve but does not qualify a target preset. The registry suggests fine146 only as a measurement hint; the already queued upper-bracket campaign has advanced to its next native run.

A [controlled reset-source sparsity experiment](verification/prototype400/selected_saved_state_reset_sparsity.json) reduces the checkpoint run’s reset PWL from 7,713 to 121 knots. An independent audit proves that the physical network, imported voltages, solver, other sources, reset endpoints and 10/50/90% threshold times are unchanged. The measured added voltage error is below 0.972 mV, with a conservative 1.001 mV bound relative to the original full-native reset trace. Both the tighter baseline and sparse experiment continue; charge, oscillator-response and runtime equivalence remain unqualified.

The [independent fine112 saved-voltage diagnostic](verification/prototype400/selected_saved_state_fine112_control.json) now runs alongside fine111. Its actual saved voltage bits verify coarse20/fine112, and all 5,980 private nodes map to that native state. Guards reject missing, duplicate, unsettled and nonfinite programming bits. [Frozen common-window snapshots](verification/prototype400/selected_checkpoint_common_windows.json) now measure −0.52 ppm at fine111 and +1.80 ppm at fine112 against full native, with +0.255% tuning-increment error over oscillator ages 10–40 ns. The original jobs continue; normal full-horizon completion and uniform model-family qualification remain pending.

An [affine fixed-boundary control](verification/prototype400/selected_fixed_boundary_fold_control.json) removes 6,003 redundant fixed-voltage sources and aggregates 578,149 linear capacitor cards to 417,263 while preserving nonlinear cards, all dynamic sources and 5,980 private voltage initializations. Retained-node current equations are exact before coefficient serialization, whose relative error is bounded by 1e-15. Both the original and serialized free-C operators pass exact parallel-path energy certificates with independent rational replay, including the signed native branches. Fixed-source currents and absolute capacitor charges are outside this voltage-response experiment. Native response and runtime comparisons remain pending.

The [original sparse-history budget review](verification/prototype400/selected_sparse_history_budget_result.json) records its three-hour terminal stop at 188.31 ns, with reset release and two oscillator rises. Only 4.23 ns of oscillator age exists, so the required 10–40 ns frequency comparison is unavailable. The waiting two-code observer was stopped; other native jobs were left running. A [new FF bank study](verification/prototype400/selected_FF_center_bank_study.json) measures coarse10/fine128 and coarse11/fine128 under the prior conditional FF bias convention, aiming to improve on coarse9/fine229’s 18-code upper headroom. Both measurements and any replacement preset remain pending.

The [selected gain-scaling regression](verification/prototype400/selected_gain_scaling.json) checks 112 integral updates and three proportional responses in the frozen DLF with the selected wrapper’s two fractional bits. KI=4 accumulates 0.25 fine code per update; KP=4 contributes one fine code. Integer-boundary quantization differs by direction. The 18-code FF headroom is therefore a closed-loop measurement question, with no headroom pass or failure inferred from the gain number alone.

[Immutable folded-network snapshots](verification/prototype400/selected_fixed_boundary_prefix_response.json) now measure +0.12 ppm against full native over oscillator ages 10–40 ns. Relative to the original checkpoint circuit, the common-window frequency differs by +0.65 ppm and the first output rise by +0.003 ps in simulation. These are one-code TT voltage-response measurements; both original full-horizon jobs and their terminal comparison continue. No speedup, power or whole-family qualification is claimed.

A [matching-corner exterior-bias sensitivity control](verification/prototype400/selected_FF_corner_bias_control.json) repeats FF coarse9/fine229 with quiet boundary voltages from the completed full-circuit FF reset-state solve. The physical devices, solver, programming, reset and rails match the prior FF control; only held quiet voltages change. Guards reject mismatched corners/models and incomplete or nonfinite vectors. This measures a combined exterior corner/state effect relative to the prior TT final-state biases, with a terminal native comparison queued. It does not qualify dynamic exterior behavior or full FF startup.

The [external supply-contract consistency check](verification/prototype400/selected_supply_contract_consistency.json) binds the draft v4 integration contract through the 61,616-MOS bulk-connectivity and alias-LVS receipts to the selected GDS. VPWR and VPB require external connection to the same nominal 1.8 V supply; VGND and VNB require external connection to ground. The four extracted rails remain distinct internally. The checked native fixture drives every rail accordingly. This closes the declaration/fixture consistency question, while tap spacing, latchup, supply tolerance and power integrity remain unqualified.

The [fine111 checkpoint diagnostic has now completed normally](verification/prototype400/selected_checkpoint_fine111_completion.json) through the original 260 ns endpoint, covering the full 84.999 ns restart horizon. Its common-age error remains −0.52 ppm against full native. Xyce reports 8,931.09 s elapsed (about 2 h 29 min). This is one completed TT response measurement, with no whole-family uncertainty or controlled speedup qualification.

An [independent fine133 checkpoint holdout](verification/prototype400/selected_fine133_checkpoint_holdout.json) now imports the actual full-native 175.001 ns coarse20/fine133 state and its own 303-channel programming/reset history. All 5,980 private voltages bind, and saved logic bits plus source-manifest identity reject another code’s state or history. Its baseline was prepared without executing the programming interval. The new 85 ns diagnostic runs on a spare physical core with the same three-hour/8 GiB budget and an independent full-native comparison queued. This extends the tested tuning range beyond fine111/112; no response result or target-preset qualification is claimed yet.

[Both fine111 and fine112 checkpoint runs have completed normally](verification/prototype400/selected_checkpoint_pair_completion.json), with backend elapsed times of 8,931.09 s and 8,914.13 s. An independent pair audit checks identical physical cards, solver decks and quiet boundary voltages while retaining each code’s own saved state and programming/reset history. The common-window tuning-increment error remains +0.255%. This is measured two-code correlation, with broader tuning, code-step and uncertainty qualification still open.

The [selected-RTL scenario/phase matrix](verification/prototype400/selected_scenario_phase_matrix.json) now executes all three declared scenarios and four reference phases with both interpolation models: 24 TT diagnostic runs. With the currently measured fine133 startup point, all stop for missing native tuning coverage: phase20 requests fine110 in every scenario, while the other phases request fine134. No functional pass is claimed. Two further matrices are queued behind the existing fine165 native calibration, covering nominal and receiver-stress publication timing. This tests whether the updated measured range and startup choice resolve the gaps, without extrapolation or automatic native launches.

An [adaptive full-native target refinement](verification/prototype400/selected_native_target_refinement_queue.json) is queued after fine165. It skips extra nominal target measurement when an actual point already meets ±1000 ppm; otherwise it requests one new native point nearest a measured-bracket secant target, rather than repeatedly bisecting the whole interval. Unbracketed hints also require new native execution. Exact acceptance-boundary and invalid-curve controls pass. At most one new full job can run under the shared slot lock; estimated frequencies never enter the registry. Nominal and receiver-stress scenario matrices are queued after the resulting measurement or explicit skip decision. Startup/headroom and model uncertainty remain separate open gates.

The [FF coarse10 target-bracket study](verification/prototype400/selected_FF_C10_target_bracket.json) now has a normally completed fine128 point at 394.806976 MHz, below target. A fine160 companion runs on the freed core. A direct input audit verifies identical circuit cards, solver, reset, rails and quiet biases, with exactly 32 physical fine-programming driver inputs changed. This provides a same-bank increment and potential target bracket; no second-point frequency, replacement preset or full-corner startup qualification is assumed.

The [reset-source response convergence study](verification/prototype400/selected_reset_response_convergence.json) records the tight-reset control’s three-hour stop at 23.54 ns of oscillator age. A separately labeled 10–20 ns diagnostic measures −3.61 ppm sparse-versus-tight frequency difference and a +0.041 ps first-rise shift; the required full 10–40 ns comparison remains unmet. A distinct 100 µV control now uses 689 reset knots, with an independently recomputed maximum source difference below 99.865 µV and all other physics unchanged. Its full-window response comparison is pending.

The [fixed-boundary reduction comparison has completed normally](verification/prototype400/selected_fixed_boundary_completion.json) for both original restart horizons. Folded-versus-original frequency differs by +0.65 ppm over common oscillator ages 10–40 ns (maximum subwindow difference 1.45 ppm); the folded case is +0.12 ppm against full native. Reported solver times are 8,898.22 s original and 8,203.99 s folded, a ratio of 1.085. Different concurrent workloads prevent a controlled throughput claim. This validates one sampled voltage response; fixed-source power and whole-family equivalence remain outside the result.

The [selected bundle-storage provenance audit](verification/prototype400/selected_bundle_storage_provenance.json) proves all 38 omitted bits from the two logical 34-bit handoffs are unused in mapped hardware: 22 integer aliases touch no cell or module port, and 16 optimized unknown aliases have no active unknown consumers anywhere. All 30 retained capture Q outputs bind to the declared routed flops. The receipt chain reaches the routed database, streamed digital GDS and selected filled parent. Four mutation regression tests reject reintroduced consumers, active unknowns, wrong capture drivers and duplicate mappings. Payload timing, initial programming setup and the 420-candidate crossing review remain open.

The [selected mixed-signal build cache](verification/prototype400/selected_mixed_signal_build_cache.json) reuses the exact RTL/VPI build while checking source, detector, artifact, tool and runtime-library identity. All 168 trace-file pairs across the 24-case measured-data matrix are byte identical to uncached runs. Two separate synthetic fixtures also preserve complete disable/re-enable and tracking-reset traces; they never enter a calibration registry. Three cache-mutation controls reject changed artifacts, detector identity and image state. Paired runtime fell from 35.4 s to 23.9 s under the current host load, excluding cache creation. The cached diagnostic matrix took 102 s. Verified cached callbacks replace the two still-waiting post-refinement callbacks; no native job was restarted or terminated.

A [larger clock-load checkpoint holdout at fine133](verification/prototype400/selected_fine133_coherent_checkpoint.json) now runs alongside the original cut. Its audit preserves every original physical card and saved voltage, adds 170 nonlinear and 4,646 passive cards, and replaces eight prescribed nodes with initialized private voltages. All shared programming/reset histories and quiet voltages remain identical; 249 new exterior nodes are held at the documented quiet biases. Three mutation tests pass. The free geometric-C operator passes exact energy certification and independent rational replay with no coefficient changes. Frequency/phase partition sensitivity remains pending.

The [FF bank study](verification/prototype400/selected_FF_center_bank_study.json) now has normally completed midpoints: coarse10/fine128 at 394.806976 MHz and coarse11/fine128 at 419.961394 MHz. In coarse10, the completed fine160 point is 401.837303 MHz, forming a [measured target bracket](verification/prototype400/selected_FF_C10_target_bracket.json). The existing conditional selector requests fine152, which now runs natively with a three-hour/8 GiB budget. Estimated frequencies are not inserted into any registry; matching full-corner startup and a replacement preset remain unqualified.

The [queued target refinement](verification/prototype400/selected_native_target_refinement_queue.json) now launches native, assessment and registry child stages explicitly inside the pinned CAD image. A real child probe confirms the required PDK library checksum and workspace before any full job is launched; two argument/namespace tests pass. The former refinement controller lacked the PDK mount, so only that waiting controller and its two waiting callbacks were replaced. Active native jobs remain unchanged. Cached callbacks now follow the corrected pipeline.

The [full-device-corner calibration runner](verification/prototype400/selected_full_corner_preparation.json) now supports declared TT/FF/SS/SF/FS device models at 1.8 V and 27 C with the selected nominal geometric R/C. A prepared TT coarse20/fine133 deck exactly reproduces the completed native input except for its output path; an FF coarse10/fine152 deck is prepared without native execution. Six tests cover preset/deck generation and rejection of incorrect corner, rails, changing observed codes, incomplete waveforms and invalid frequencies. The observer requires normal native completion and verifies the measured preset before accepting a calibration point. Execution requires the pinned CAD image and shared full-job slot. Full-corner startup and model qualification remain pending.

The [matching-corner FF exterior-bias control](verification/prototype400/selected_FF_corner_bias_control.json) has completed normally. Replacing TT final-state quiet biases with matching FF reset-state biases changes common-age frequency by +0.091 ppm over 10–40 ns, with a maximum early/late difference of 0.184 ppm and a first-output-rise shift of −0.0037 ps. This is one measured combined corner/state sensitivity at coarse9/fine229; dynamic exterior behavior and a uniform model-family uncertainty bound remain open.

A [single full-circuit FF target holdout](verification/prototype400/selected_FF_full_target_queue.json) is queued after the current TT refinement and the conditional FF coarse10/fine152 measurement. It launches only after normal completion and a measured conditional frequency within ±1000 ppm, using the pinned CAD container and shared full-job lock. Native execution retains its 16-core, 64 GiB, 48-hour bound; no identical retry or frequency prediction is allowed. Three request-validation tests pass. The resulting FF waveform remains separate from the TT registry, and full-corner model-family qualification remains open.

The [selected-top handoff reset contract](verification/prototype400/selected_handoff_reset_contract.json) now has an unbounded PDR proof for seven assertions, with a reset-polarity mutation rejected by a counterexample. The exact selected RTL supplies the paired reset assertion assumed by the existing 34-bit, three-consumer-cycle handoff proof; reset releases and clock stalls remain independent. Only the external reset is assumed initially asserted. This closes that discrete RTL composition obligation. Physical reset recovery/removal, bundled-data timing and the remaining CDC review remain open.

A [saved-state fine-code pulse diagnostic](verification/prototype400/selected_checkpoint_code_step.json) now tests 111→112→111 at TT coarse20 through one retained physical HS_INV2 programming input. It preserves the completed fine111 checkpoint circuit, all private voltage initializations, solver and every other prescribed source. Independent deck/source checks and two waveform tests pass. Engineered 1 ns ramps at 30–31 and 60–61 ns exercise both directions; they do not represent extracted decoder timing. The native run uses one spare core, 8 GiB and the existing three-hour cap, with input/output driver voltages observed. Response and full-circuit dynamic equivalence remain pending.

The [selected-route CDC component review](verification/prototype400/selected_CDC_component_review.json) now binds all 13 synchronizers through the routed database: 26 stage registers, 49 intermediate buffers, and continuous nets with unique expected drivers. Five selected-route native timing queries check both enabled decision bits for setup and hold under the existing integrated phase proof. Across 20 paths, minimum conditional setup slack is 0.331 ns and minimum hold slack is 2.005 ns at the 402.1 MHz capacity screen. Three actual-log mutations reject negative slack, missing coverage and duplicate paths. This is enabled-path component evidence under supplied timing/load views; synchronizer input apertures, reset/recovery, disabled/startup masking, actual frequency-range coverage and the full crossing review remain open.

The [FF coarse10/fine152 target probe](verification/prototype400/selected_FF_C10_target_bracket.json) has completed normally at 400.059248 MHz over 20–60 ns, +148.12 ppm from target. Its actual measured receipt passes the queued full-FF runner’s ±1000 ppm request screen. Code152 has a numerical distance of 95 codes to the upper allowed limit; startup/capture headroom is not inferred from that distance. The full-circuit FF startup holdout remains queued behind TT refinement. Held TT exterior biases, model uncertainty and closed-loop qualification remain open.

The [exhaustive selected interstage timing queries](verification/prototype400/selected_CDC_interstage_timing.json) check all 13 synchronizer first-Q to second-D paths for both setup and hold at TT/FF/SS/SF/FS: 130 explicit checks, all passing under the supplied native views and nominal routed R/C. Minimum setup slack is 0.988 ns and minimum hold slack is 0.046 ns. No timing exceptions were added. Actual-report controls retain negative slack as failure and reject missing endpoints or wrong path types. Actual startup frequency coverage, first-stage resolution, reset recovery/removal and the remaining crossing review stay open.

The [fine133 checkpoint holdout](verification/prototype400/selected_fine133_checkpoint_holdout.json) has completed normally through the full original 260 ns endpoint. The common 10–40 ns oscillator-age frequency error is −1.15 ppm against full native; the maximum early/late-window error is 1.94 ppm. Xyce reports 9,361.23 s elapsed (about 2 h 36 min). This supplies a third measured TT code with its own actual saved state and history. It does not establish arbitrary-state restart, dynamic code-change equivalence or a uniform model-family uncertainty bound.

A [cross-code checkpoint challenge](verification/prototype400/selected_checkpoint_retarget_challenge.json) reuses the actual fine111 private voltages and history for a requested fine133 measurement. Twenty-two physical programming inputs ramp at 0.5–1.5 ns while reset remains asserted; no target-code saved state is imported. Independent input/deck checks preserve all physical cards, initial voltages, solver and other sources, and bind all 88 changing-driver MOS primitives. Two waveform tests pass. The one-core, 8 GiB native run retains its three-hour cap; its observer will compare common oscillator-age windows against both full fine133 native and the completed fine133 own-state checkpoint. Cross-code response and model qualification remain pending.

The [selected-RTL TT gain search](verification/prototype400/selected_TT_gain_search.json) is queued after TT refinement and reuses its nominal/receiver-stress KI=4/KP=0 matrices. It then tests lower KI/KP pairs in the declared order, using verified cached builds and both interpolation variants across all scenarios/phases. A real 48-case current-data control stops for missing fine110/fine134 coverage without expanding gains or launching native jobs; three policy tests pass. Execution failures also stop expansion. Search execution has a 12-hour bound on one spare core. A passing TT diagnostic pair cannot qualify the required common five-corner gain or the analog models.

[Full-native supply characterization](verification/prototype400/selected_full_native_supply_characterization.json) is added to the queued FF startup run through a separate four-rail voltage/current CSV. An actual native resistor control measures the expected 3.564 mW and energy with correct current signs; extra CSV printing preserves every voltage sample exactly. The prepared FF deck differs only by output destinations and that observation statement. Three analysis tests cover clipped integration and invalid data. Only the waiting FF controller was replaced; active native workers were untouched. The observer will report 200–260 ns static-preset startup supply draw, with no invented power limit or locked-loop power qualification.

A [corner-bound FF raw-detector fit](verification/prototype400/selected_FF_raw_detector_fit.json) is now queued after one new 0.1 ns recorded-phase probe. Existing FF data has publication timing and broad UP/DN responses, but no negative-phase UP observation to bracket the raw decision boundary. The new decision is not presumed. Four fitting cases and two disjoint holdouts will be replayed against the generated model. Actual deck corner/temperature, supply/body rails, initial-state corner and TT excitation identity are checked; a real FF case passes its binding and is rejected for an SS fit. The native probe uses one spare core, 12 GiB and a three-hour cap. Recorded TT upstream excitation, full phase coverage and model-family uncertainty remain unqualified.

The [100 µV reset-convergence control](verification/prototype400/selected_reset_response_convergence.json) completed normally in 10,522.9 s (about 2 h 55 min), covering the required full 10–40 ns oscillator-age window. Its frequency differs from full native by +0.32 ppm (maximum early/late error 1.23 ppm). Direct sparse-versus-100 µV comparison measures −0.84 ppm, maximum subwindow difference 1.71 ppm, with all physical cards, private voltages, solver and other sources independently matched. The full-window comparator accepts both completed controls and rejects the earlier capped dense-reset run. That earlier run remains partial; this one-code TT result does not establish a uniform reset-response bound.

[Native clock-quality characterization](verification/prototype400/selected_native_clock_quality.json) now reports finite-window period, cycle-to-cycle and detrended edge-timing variation for completed TT fine111/112/133 waveforms. Fine133 at 397.235 MHz has 23 complete periods over 200–260 ns, with 0.398 ps sampled period RMS deviation and 0.086 ps after removing linear period drift. Three arithmetic/input-guard tests pass. These are noiseless simulation observations that include startup drift and numerical variation; they neither characterize thermal/flicker phase noise nor qualify precision jitter or a 400 MHz preset. No jitter limit is invented.

The [remaining full-corner startup sequence](verification/prototype400/selected_remaining_full_corner_queue.json) now waits behind the FF holdout, then measures SS47/fine145, SF26/fine115 and FS20/fine180 in order. Each request comes from a normally completed conditional native target measurement with its actual library selector and supply/body rails checked. Three request-validation tests pass. The sequence launches at most three new full jobs, one at a time through the shared lock, with the existing 16-core/64 GiB/48-hour per-case policy and supply-current CSV observations. It stops on a failed stage and performs no identical retry. These new points remain separate from the TT registry; full-corner startup and model-family qualification are still pending.

A [conditional affine follow-up for the larger fine133 holdout](verification/prototype400/selected_conditional_coherent_affine_fold.json) is prepared with unchanged nonlinear cards and all 5,988 private initial voltages. It removes 6,244 redundant fixed-voltage sources and reduces 582,795 capacitors to 417,408; source and serialized free-C energy witnesses replay independently. Three decision tests pass. The controller skips if the original finishes normally, and launches at most one distinct folded case only after an explicit original budget stop, on the freed core with the same three-hour/8 GiB cap. The original run is untouched. Retained-voltage equations are exact before 1e-15-bounded coefficient serialization; source currents and absolute stored charges are outside this experiment.

The [selected DLF arbitrary-state clear proof](verification/prototype400/selected_DLF_clear_recovery.json) establishes five assertions with no environment constraints or assumed initial DLF/reset state. One valid clear clock loads the requested seed and clears acquisition history regardless of prior stored bits; the output mask bypasses that prior state. Native PDR rejects both a removed clear load and a removed output mask. Selected filter parameters and RTL bind to the physical candidate. This is a discrete logical recovery property, not a metastability-resolution bound, physical reset recovery/removal waiver or proof of timely clear arrival in the complete macro.

The [larger fine133 clock-load holdout](verification/prototype400/selected_fine133_coherent_checkpoint.json) reached its original three-hour cap at original time 254.824 ns, with 70.77 ns of oscillator age. Its terminal trace covers the full required 10–40 ns comparison: +5.79 ppm against full native and +6.94 ppm against the original partition (maximum subwindow partition difference 7.31 ppm). It did not complete the 260 ns horizon. The [distinct certified affine variant](verification/prototype400/selected_conditional_coherent_affine_fold.json) has started on the freed core with the original voltages and dynamic sources, its own three-hour/8 GiB cap and captured PDK namespace. Neither terminal-prefix data nor the affine variant qualifies a uniform model-family bound.

The complete-core and control-overapproximation clear-before-unmask proof attempts both returned UNDECIDED at their 600-second limits; neither establishes a hardware failure or a proof. A [decomposed proof runner](verification/signoff400/prove_selected_clear_before_unmask_v3.py) now checks the clear-clock witness and all ten seed-bit equalities separately under the same initial-reset/static-programming contract and the same two unconstrained feedback outputs. Every component must prove before the conjunction is accepted, and a removed-witness monitor must produce a counterexample. The run is pending; physical clear arrival, metastability and reset recovery/removal remain unqualified.

The [selected conditional reset-check summary](verification/prototype400/selected_conditional_reset_checks.json) records fifteen passing worst enabled recovery/removal/clock-pulse checks across the existing five-corner 402.1 MHz capacity views. Minimum reported margins are 0.714 ns recovery (SS), 0.0105 ns removal (FF), and 0.579 ns clock pulse width (FS). Actual-report controls retain negative slack as failure and reject missing, duplicate or wrong-type checks. These are worst enabled checks, not an exhaustive reset endpoint inventory: existing external-reset and asynchronous-group exceptions remain, and startup transitions, external reset pulse width and physical reset qualification remain open.

The [FF raw-detector fit](verification/prototype400/selected_FF_raw_detector_fit.json) now uses four normally completed native training cases and passes two independent holdouts for sampled signs, event counts and timing. Its measured opposite-decision bracket is -111.10 to -13.03 ps; maximum replay edge error is 0.988 ps under the observed fit band plus 1 ps quantization. The upstream excitation remains recorded TT data, so this does not qualify FF sender waveforms or a uniform uncertainty bound. A new midpoint holdout runs separately and is not added to training. The [exact reset-load Liberty parser check](verification/prototype400/selected_observed_reset_liberty_parser.json) also verifies all ten five-corner early/late cell inventories and FF pins without warnings; constraint semantics and physical timing remain open.

The [physical one-code pulse](verification/prototype400/selected_checkpoint_code_step.json) completed normally. Initial and returned fine111 windows match their static reference within 0.52 ppm, but the fine112 plateau is 194.9 ppm below the separately initialized static112 reference. Equal-age comparisons show a switched tuning increment 21.21–21.37% smaller than the static111/112 increment across four post-step windows, despite verified settled real driver input/output states. This is a material unresolved dynamic-response discrepancy. The experiment does not separate saved-state dependence, held-exterior approximation and transient effects, and has no full-native switched reference; no universal slope correction or uncertainty bound is inferred. Static checkpoint agreement alone cannot qualify closed-loop tuning dynamics.

The [clear-before-unmask subproperty review](verification/prototype400/selected_clear_before_unmask_proof.json) now retains an unbounded sampled clear-clock witness proof, a byte-identical independent baseline AIG re-export and a removed-witness monitor counterexample at frame 63. Selected reset/startup/handshake logic is preserved; only feedback-clock and fine-code outputs are unconstrained. Initial reset and static programming are explicit assumptions. The first variable seed equality remained UNDECIDED after 600 seconds, so the complete clear/seed conjunction is still unproved. Physical clear arrival, metastability and reset recovery/removal are separate open requirements.

The [111-to-133 checkpoint challenge](verification/prototype400/selected_checkpoint_retarget_challenge.json) completed normally but differs from the independent full-native133 reference by -2,077.65 ppm over oscillator ages 10–40 ns (-2,076.50 ppm against the target-own-state checkpoint). The original 111 voltages/history were retained and 22 real programming inputs changed under reset; no target state was imported. This does not validate cross-code checkpoint reuse. An observer lineage bug was fixed by resolving and verifying pinned parent manifests to the same full physical model; a forged-parent-digest control is rejected. The initial-state-only112 control remains active to separate state from boundary-history sensitivity.

The [seed-equality proof](verification/prototype400/selected_clear_before_unmask_proof.json) now has a proven first variable seed bit using four sound command-comparison overapproximations, reducing its state space from about 344 to 172 elements. Each comparison retains the selected seed, run and coarse bits and gives omitted-field equality an independent input; every original trace is reproduced by the actual omitted-field comparison. Sixteen symbolic witness identities cover equality and inequality for all eight seed projections. The remaining seven variable seed proofs are running. No physical timing assumptions or narrowed seed values were added, and the complete seed conjunction remains open.

The [selected discrete clear/seed recovery review](verification/prototype400/selected_clear_before_unmask_proof.json) now passes the complete eight-variable-bit proof set, constant low-bit hookup, reproduced clear-clock witness and arbitrary-prior-state DLF clear theorem. It verifies exact selected source/export recipes, replays each command-comparison abstraction, checks fresh wire identifiers and original environment constraints, and binds the actual proven AIGs. Missing-proof and wrong-RTL-digest controls are rejected. Under initial external reset and static programming between resets, a valid sampled clear clock carries the current seed before every unmask. Physical clear arrival, analog metastability, reset recovery/removal and the rest of CDC qualification remain open.

The [enable clocking review](verification/prototype400/selected_enable_clocking_review.json) identifies raw PLL_ENABLE in 76 reference-domain destination cones, including all three startup-state bits, with no intervening sequential capture. Another 277 destination cones are in the fine-clock domains. Existing capacity screens assign the input REFCLK timing, while the integration contract leaves input timing unspecified. The release interface must resolve synchronous REFCLK setup/hold requirements versus an asynchronous-enable synchronization ECO. The completed discrete DLF recovery proof does not discharge reference-state-machine input capture. Current selected RTL and native runs are unchanged pending that interface decision.

The [selected handoff payload review](verification/prototype400/selected_handoff_payload_timing.json) covers all 30 implemented capture registers with 300 explicit min/max paths across five device corners. Maximum measured source-clock-to-capture-D delay is 1.341 ns (SS), using the existing conditional native load views and routed min/max R/C. A separate unbounded selected-leaf proof establishes two prior destination rising edges of payload stability before capture under the coasserted-reset contract; bypassing capture qualification gives a frame-5 counterexample. Three actual-report mutations are rejected. Artificial related-clock slacks are excluded from asynchronous acceptance. Request aperture, actual startup clock range, physical reset and payload setup/hold qualification remain open.

A [separate asynchronous-enable RTL proposal](rtl/candidate400_async_enable_v1/sources.json) now adds two REFCLK-domain capture stages before the startup-controller enable input, preserving existing raw-input withdrawal equations. Exactly one of the nine copied source files changes. All eighteen synthetic-clock phase/restart regressions pass, including 200 ns stable tracking observations, short/long disables, stopped-oscillator restart and reset during tracking; elaborated wiring confirms startup consumes the second stage. Candidate-specific clear/seed proofs are running. This is a layout-unbound proposal while the release interface choice is pending; the selected layout and its native/model qualification inputs retain their original source identities.

The [frozen FF raw-detector midpoint holdout](verification/prototype400/selected_FF_raw_detector_fit.json) completed normally and fails nominal validation: at -61.10 ps measured physical phase, native reports DN and the unchanged midpoint model predicts UP. This lies inside the previously recorded -111.10 to -13.03 ps transition bracket. All three observed conditional edge classes fit their prior latency intervals plus the existing 1.01 ps model quantization allowance; the fourth class is unobserved. Unmatched event counts invalidate global zip-paired edge errors as latency measurements. The new case remains excluded from fitting, the earlier two holdouts still pass, and uniform uncertainty/full-interface qualification remain open. Subsequent loop stress cases need explicit phase ambiguity rather than a single assumed midpoint threshold.

The [asynchronous-enable proposal](verification/prototype400/selected_enable_clocking_review.json) now passes candidate-specific clear-clock/all-eight-seed proofs and the sampled handoff reset contract. Its reviewer checks the actual candidate source, export recipes, replayed overapproximations and proven AIGs; the unchanged DLF theorem is joined by source identity. A startup tap on the first capture stage is rejected by the phase regression, and the reset-polarity hardware mutation is rejected formally. All eighteen concrete logic regressions remain passing. The proposal is still layout-unbound; selected-layout timing/model receipts are not transferred, and physical CDC, reset timing and closed-loop qualification remain open.

The [certified coherent affine holdout](verification/prototype400/selected_conditional_coherent_affine_fold.json) completed its full horizon normally in 9,385.55 seconds. Independent deck checks preserve nonlinear cards, surviving sources, initial conditions, solver and observations. Over oscillator ages 10–40 ns it differs from the original terminal prefix by +0.0113 ppm (subwindows +0.756 and -0.232 ppm), and from full native by +5.805 ppm. The original hit its three-hour cap; this is not a controlled throughput benchmark. Source currents, absolute capacitor charge, power and a uniform tuning-family error bound remain outside this voltage-response result.

The [initial-state-only control](verification/prototype400/selected_checkpoint_IC_swap.json) now has a pinned observer waiting for normal completion. It compares the measured IC111/static112 response, own-state static111/112 references and completed code pulse across four identical simulation-age windows. It reports the IC-only frequency shift and pulse-minus-control residual separately; their sum is the measured pulse/static difference. Different boundary histories and switching times prevent treating that descriptive decomposition as causal identification or a universal gain correction. No native simulation is restarted by the observer.

The [asynchronous-enable proposal](verification/prototype400/selected_enable_clocking_review.json) now has frozen full/compact HS mappings with 483 paired registers. All paired next-state, clock/reset and external-output functions are equivalent, and the corrupted-data control is rejected. Both mappings preserve two positive-edge asynchronous-clear REFCLK capture cells, their exact data/reset chain and ASYNC_REG attribute. Four actual-mapping tests pass, including rejected bypass, wrong-clock and missing-attribute mutations. Placement, routing, physical CDC and layout selection remain open.

The [SS raw-detector bracket followup](verification/prototype400/selected_SS_raw_detector_bracketing.json) waits for both distinct probes to complete normally. It derives the bracket only from the three predeclared training cases and fits only if measured DN/UP decisions establish an ordered negative-phase bracket. The two holdouts remain disjoint and excluded from parameter selection. Four guard regressions reject missing polarities, reversed/contradictory decisions and brackets crossing zero. The followup launches no native cases or retries; sender-corner correlation and uniform model qualification remain open.

The [asynchronous-enable proposal placement](verification/prototype400/selected_enable_clocking_review.json) completed as a separate supplied-TT capacity screen. Both mapped capture stages and their D/Q/clock/reset connections remain present; the asynchronous input and reset are explicit diagnostic exceptions, and the REFCLK interstage path stays timed. Routing/extraction is running on four reserved cores with new outputs. This does not replace the selected macro or transfer its physical/native qualification. The initial placement attempt stopped because protecting the capture cells blocked required reset buffering; the retained version allows buffering and records the actual placed capture cells.

A [routed-equivalence followup](verification/prototype400/selected_enable_clocking_review.json) is pinned to the separate enable candidate route and compact mapping. It waits on the actual original route worker, verifies normally completed route artifacts and identical candidate-source identities, then checks every routed state transition/output relation and a corrupted-reset control after audited physical-only cell projection. A route observation timeout does not restart the route. Boolean equivalence cannot qualify diode loading, layout connectivity, timing or CDC.

The [separate asynchronous-enable candidate](verification/prototype400/selected_enable_clocking_review.json) now completes digital routing and nominal RC extraction with an empty final router DRC report. Routed Boolean equivalence covers all 483 state primitives and rejects reset corruption. An independent actual-netlist audit traces both capture clocks/resets through buffers, verifies that the first stage feeds only the second-stage D pin, and records 12.48 um Manhattan separation between capture-cell origins. Nominal supplied-TT interstage setup/hold reports are present; four actual-route controls reject bypass, extra functional first-stage fanout and wrong-clock mutations. This is a routed digital proposal, not assembled GDS signoff, physical CDC qualification or promotion of the selected layout.

The [frozen FF detector fit](verification/prototype400/selected_FF_raw_detector_fit.json) now has 32 executable diagnostic endpoint variants: both prior measured phase thresholds crossed with independent endpoints of four prior latency intervals. All 224 compiled native-case replays completed. Each of the seven cases has at least one fixed variant matching its signs and event counts; the midpoint holdout matches sixteen variants while the original nominal failure remains recorded. No new holdout determines parameters, and the old midpoint-specific edge-error criterion is excluded from endpoint timing validation. These finite stress choices do not establish jointly realizable extrema, adaptive cycle-to-cycle ambiguity, a uniform uncertainty envelope or closed-loop robustness.

The [initial-state-only112 control](verification/prototype400/selected_checkpoint_IC_swap.json) completed normally with all target physical cards, boundary sources, reset and solver unchanged. Importing only private saved voltages from111 shifts frequency by -260.11 ppm at 40–55 ns and -257.56 ppm at 70–84 ns relative to own-state112. Across four matched pulse windows the IC-only frequency shift is -0.1021 to -0.1023 MHz, while pulse-minus-control is +0.0251 to +0.0262 MHz. At 40–55 ns these are -28.40% and +7.12% of the static tuning increment, summing to the observed -21.28% switched/static discrepancy. This establishes initial-state sensitivity in the conditional partition; differing switching times and exterior histories prevent causal attribution of that sum, and hybrid physical reachability remains unproved. Static code-only calibration still cannot qualify the switched response.

The [initial-state sensitivity experiment](verification/prototype400/selected_checkpoint_IC_swap.json) now has two distinct bounded complementary controls running: import only the twelve context-node voltages differing by more than100mV, or import every remaining private-node voltage. Each uses the unchanged112 circuit, boundary waveforms, reset and solver, on its own core with8GiB/three-hour limits. The groups are selected from initial-voltage differences, not frequency outcomes. An independent observer verifies all5980 complementary assignments and exact deck substitutions before waiting for normal completions. Combined with the completed own-state and all-donor cases, this four-case experiment measures group effects and their interaction. Actual Xyce children and319-file PDK include supersets are captured; no physical reachability, floating-node diagnosis or uniform model qualification is inferred.

The [routed enable proposal](verification/prototype400/selected_enable_clocking_review.json) is now undergoing independent streamed digital-component GDS checks: Magic DRC, layout LVS, native antenna reporting and power-pin connectivity. A bounded wrapper binds the actual completed route/equivalence proof, reserves four cores/eightGiB, refuses existing signoff-output overwrites and retains all component outcomes, including failures. These checks do not select the candidate or transfer assembled-parent, timing, CDC, density or power-integrity qualification.

The [enable candidate digital GDS audit](verification/prototype400/selected_enable_clocking_review.json) completed with zero Magic DRC rectangles, unique LVS match and48,428/48,428 power pins connected, but failed antenna checks on ten nets/twelve pins. A distinct repair inserts twelve local diodes by partitioning existing filler footprints at the measured sinks, with incremental rerouting and nominal RC re-extraction. Three filler-partition regressions pass, and a fresh routed Boolean/reset-corruption proof waits on the repair. Historical diode-load evidence is verified under its recorded /work/OpenPLL alias through a bind of the same workspace; input digest checks remain enabled. Repaired GDS checks, timing/loading, physical CDC and assembled-parent qualification remain open.

The [repaired enable-candidate digital component](verification/prototype400/selected_enable_clocking_review.json) now passes repeated independent streamed-GDS checks: zero Magic DRC rectangles, unique LVS match, zero antenna net/pin violations and48,444/48,444 power pins connected. Twelve local diodes are present, final router DRC is clean and nominal RC is re-extracted. The repaired netlist again proves all483 state/clock/reset/output relations with reset-corruption rejection. A fresh actual-netlist audit preserves the sole first-stage-to-second-stage data fanout and12.48um capture-origin separation; its nominal path query explicitly includes the verified conditional diode-load view. These are digital-component results; assembled-parent, timing/CDC, density and power-integrity qualification remain open.

The [separate enable-candidate assembly](verification/prototype400/selected_enable_clocking_review.json) now has an exact-GDS digital obstruction LEF and a passing three-macro frame with686 audited macro-pin connections. Parent power construction passes actual macro-GDS metal5 port/clearance checks and main-rail database continuity, preserving child geometry. A new parent route is running against these views. The assembly retains the existing DCO/BBPD physical sources and the new digital source identity; this frame/power evidence does not transfer old native-model, assembled DRC/LVS, power-integrity or timing qualification and does not select the proposal.

The [enable proposal parent route](verification/prototype400/selected_enable_clocking_review.json) now completes with zero router DRC violations, exact macro bindings and connected VPWR/VGND geometry while preserving every original PG pin rectangle. The first route failed because a historical router moved power contacts to x500um although this power frame uses x200um. A fresh router snapshots/restores actual source rectangles and verifies their equality instead of assuming coordinates; the failed route and stopped checker remain retained. The revised assembled GDS is streamed and undergoing independent DRC/LVS checks. No assembled signoff or native-model qualification is inferred from database connectivity.

The [separate enable-candidate assembled GDS](verification/prototype400/selected_enable_clocking_review.json) is Magic DRC-clean. Raw hierarchical LVS reports a split TRACKING/BBPD_RESET_N parent connection although the extracted digital child explicitly contains an exact-zero-ohm R0 between those ports. Propagating only that proven child short into a separate parent netlist copy gives unique LVS with all three macros expanded; original extraction and geometry remain unchanged, and two alias-normalization guard tests pass. A full flattened-parent antenna diagnostic is running with the previously controlled isolated Magic executable; qualification remains specific to each GDS, so old selected-layout antenna evidence is not transferred. Parent antenna, density, power integrity, timing/CDC and selection remain open.

The [enable proposal full-parent antenna diagnostic](verification/prototype400/selected_enable_clocking_review.json) completed with7,582 feedback rectangles and219 native gate/plane records. Actual GDS topology maps every record to macro ports on177 parent nets:146 fine controls,27 coarse controls and four external programming/gain inputs. The locator now considers all macro ports rather than only DCO ports and retains the distinction between gate records, feedback rectangles and unique nets. Parent antenna qualification fails; full-topology connectivity is used only for net identity, not as a substitute for process-stage connectivity. Digital-component antenna success and the old selected assembly’s qualification do not cover this new parent.

The [selected REFCLK-timed enable option](verification/prototype400/selected_enable_clocking_review.json) now has1,520 explicit min/max paths covering all76 reference-domain destinations, five corners and0.1/1.0ns input-transition samples. Largest sampled external requirements are6.346ns setup (SS,1ns input slew) and0.532ns hold (SF,1ns), with0.1ns reference transition and0.15ns clock uncertainty already included. Four report controls independently cross-check arrival/required times and reject missing, duplicate or wrong-clock paths. A0.5ns minimum input-arrival assumption would miss the SF1ns-slew hold requirement by31.6ps. These remain sampled conditional budgets: a continuous slew range, fine-domain withdrawal/reset behavior and the integration interface contract are not qualified, and selected RTL/layout remain unchanged.

The [first SS raw phase probe](verification/prototype400/selected_SS_raw_detector_bracketing.json) completed normally. Its retained measured cycle is UP at -8.420ps physical phase, rather than the requested -0.225ns excitation coordinate. The companion distinct probe is still running, and the predeclared fit continues to wait for both normal completions and an actual ordered negative DN/UP bracket. This single cycle does not establish a transition bound or full-phase validation.

The [second SS raw phase probe](verification/prototype400/selected_SS_raw_detector_bracketing.json) completed UP at -179.25ps measured phase. With no negative-phase DN in the training set, the original bracket guard stopped without fitting. Two distinct bounded probes now run at -0.5/-0.8ns excitation coordinates, preassigned to training/independent holdout respectively. A new observer waits for both normal completions while deriving any bracket solely from the four declared training cases; the fresh holdout and two prior holdouts stay excluded. Four set/leakage controls pass, and both live PDK namespaces capture319 include files. No requested coordinate or expected sign is substituted for measurement.

The [frequency-history stress harness](verification/prototype400/selected_frequency_history_stress.json) now applies explicit affine gain/offset scenarios to the fast cached selected-RTL simulation while preserving native calibration knots. Four diagnostic packets use nominal/observed low gain0.786288 and zero/observed retarget offset-2077.65ppm, tied to TT coarse20 and the exact physical model. Unstressed and nominal controls have seven byte-identical artifacts;20,576 actual oscillator edges and20,478 constant-code half-periods deliver the explicit model frequencies within0.983ps quantization error, including gain away from the measured anchor. Six guards pass. These delivery controls stop at missing native code coverage rather than extrapolate; they are not complete lock tests, a qualified wide-code envelope or a claim that independent stress extrema coexist physically.

Two [TT frequency-stress matrices](verification/prototype400/selected_frequency_history_stress.json) now wait on the original target-calibration registry, using the nominal and receiver-delay compositions separately. Each runs96 fixedKI4/KP0 cases: four frequency stresses, two native-knot interpolation choices, three restart scenarios and four reference phases. A checked diagnostic registry composition preserves native point/analog identities and refuses a different process corner; both controls pass. The workers reuse compiled RTL, launch no native cases and retain missing-code requests. These192 TT diagnostic cases neither select common five-corner gains nor replace the required60-case qualified matrix.

Full-native sender capture now accepts a normally completed 260 ns full-run assessment directly, without requiring a prior detector probe. The new `capture_selected_full_native_snapshot.py` verified the complete RAW checksum and captured 25,735 initial values from full TT fine-133 run 316 (receipt 958); six rejection tests pass. Native clock-waveform export 959 is running against that snapshot. This validates the capture path, not non-TT sender correlation or release readiness. See `verification/prototype400/selected_full_native_snapshot_capture.json`.

Sender export 959 completed (45,408 saved samples, nine driver traces). The separate V12 detector runner and V3 case wrapper require the initial vector and sender packet to bind the identical full-native manifest, RAW identity and requested process corner. Six additional source-mismatch tests pass. Prepare-only case 960 generated a deck from full TT fine-133 sources, with physical feedback Q unclamped and no native execution. Non-TT correlation and conditional interface qualification remain open.

Full TT upper run 463 completed normally in 42,007.27 s: coarse 20/fine 165 measured 402.860225 MHz over 200–260 ns, with stationary measured codes. Together with fine 133 at 397.235125 MHz, the measured points bracket 400 MHz. The existing refinement queue 799 automatically requested and launched full native fine 149; no predicted frequency was entered into the registry. Its live namespace capture 962 records 319 PDK include files. Sender-capture follower 961 waits for the existing FF/SS/SF/FS assessments, then captures same-corner initial vectors and driver traces without launching simulations. Bracket, startup/capture, corner detector qualification and closed-loop release gates remain open.

Fast measured-bracket startup diagnostics 963/964 completed 40 cold-enable/phase-0 cases: all five declared KI values at KP=0, measured seeds 133/165, two publication views and both interpolation laws. Thirty-six cases request unmeasured fine 166; four KI1/seed133 cases complete 220 us but fail frequency and phase limits (no functional passes). These results preserve missing coverage separately from functional failure, launch no native simulations and do not select a release gain. See `verification/prototype400/selected_bracket_seed_gain_challenge.json`.

The remaining nonzero-KP grid is queued in diagnostics 965/966: 160 cold/phase-0 cases across KI 1/2/4/8/16, KP 1/2/4/8, measured seeds 133/165, two publication views and both interpolation laws. Two leased serial workers use spare CPUs 23/24 and cached builds; no native simulations are launched. These probes preserve unresolved model coverage and do not select a common release gain.

KI1/KP8 now passes all 48 diagnostic TT cases in matrices 969/970: three scenarios, four physical divided-output phase offsets, two interpolation laws and nominal/100 ps receiver-delay views, using measured coarse20/fine133 startup. Across 80 scenario segments, worst acquisition confirmation is 102.24 us, final-four-window frequency error <=38.497 ppm and phase span <=221 ps. KI1/KP4 passes 36/48; phase20 misses the acquisition deadline. Completed proportional scouts 965/966 retain all 160 outcomes (22 functional passes), without converting missing coverage into a hardware failure. Frequency-history stress matrices 975/976 test KI1/KP8; matching full-fine133 detector holdout 971 and frozen-fit observer 972 are live, with runtime capture 973 covering 319 PDK includes. See `verification/prototype400/selected_TT_KI1_KP8_candidate.json`; no five-corner common gain or release qualification is claimed.

History-stress runs 975/976 reproduce all 48 unchanged-frequency KI1/KP8 passes. Early reduced-gain cases require unmeasured fine166, so their capture results remain incomplete. Queue 977 waits for refinement 799, then requests at most one upper-coverage native point using the existing +32-code guard above the nearest measured target. It runs inside the pinned CAD namespace and shares the single full-native slot with the existing corner jobs. No predicted frequency is published; wide-code history-stress applicability remains unqualified.

Exact-statistics assessment V4 removes floating interpolation errors at inclusive limits for proven 1 ps traces, without epsilon, off-grid rounding or changed acceptance limits. Twenty-seven controls pass, including exact 250 ps acceptance and 250.001/251 ps rejection. Runtime control 979 has byte-identical clocks/controls/logs to its V7 source. Reassessment 978 corrects its final-window span result but retains the genuine 214.88 us acquisition failure after a 253 ps window; nominal control 980 still passes. Release auditor V4 recomputes exact statistics and still rejects all five unfilled gates (981). Historical scripts and receipts stay frozen. See `verification/prototype400/selected_exact_statistics_assessment.json`.

Initial-state factorial controls 918/919 completed normally and comparison 921 independently verified the complementary assignments. At 40–55 ns, the context12-only intervention shifts the conditional TT112 frequency by -95.345 kHz, complement5968 by -26.564 kHz, and their interaction by +19.772 kHz; the all-donor shift is -102.136 kHz. The context-only/full-shift ratio is 93.35%. This localizes conditional-model state dependence without establishing hybrid-state physical reachability or a full-native switched-code discrepancy cause.

Both KI1/KP8 history-stress campaigns completed all 192 cases. Original assessments retain 72 functional passes, 48 fine166 coverage stops, and 72 functional failures. Exact-statistics replay 982 reassessed the complete 48-case offset subset from unchanged traces: 24 original passes become 30, with six boundary-arithmetic corrections and 18 remaining failures; no simulations were rerun and no limits changed. The gain-only coverage gap and combined-history stress failures remain open, and the wide-code stress is still an engineering diagnostic rather than a qualified physical uncertainty bound.

SS raw probes 938/939 completed normally. The fitting probe measured -279.247 ps DN then +510.623 ps UP; the independent holdout measured -579.246 ps DN then +203.553 ps UP. Fit 942 now brackets the transition at [-279.247,-179.247] ps with four training cases and three preassigned holdouts; all sampled signs, event counts and fit-band edge checks pass. Independent midpoint probe 983 at recorded coordinate -0.45 ns is live, with replay 984 retaining the same four training cases and runtime capture 985 covering 319 PDK includes. TT sender excitation remains explicit; no native-interface qualification is claimed.

Exact-assessor matrices 986/987 tested KI2/KP4 across all 48 TT scenario/phase/interpolation/publication cases at measured seed133: 21 pass, 24 stop at missing fine166, and three nominal-receiver/period-interpolation phase20 cases require 209.76 us acquisition confirmation. The controller is not promoted. Matrix worker V3 uses runtime V8 and exact statistics, while retaining complete-case, phase-coverage and diagnostic-scope checks. See `verification/prototype400/selected_KI2_KP4_diagnostic.json`.

Guarded exact-statistics gain search 990 waits for upper-coverage pipeline 977 and baseline matrices 988/989. Its V2 search preserves the declared first pair and ordered gain grid, explores other pairs when a trial reaches missing native coverage, and stops on incomplete execution. A passing candidate cannot claim resolved minimum order while any lower-ranked pair is unassessed or coverage-limited; five selection controls pass. This search launches no native simulations and cannot qualify a common five-corner gain. See `verification/prototype400/selected_guarded_exact_gain_search.json`.

Native pin inventory 996 covers 12,794 linked digital cell pins and 369 top-level ports in each of five process corners, including verified inside-terminal connections for REFCLK/PLLOUT/RESET_N/PLL_ENABLE. All library pins and propagated cell-pin slew values are present; the eight remaining constraint flags are loaded constant-tie outputs with no declared max-capacitance. Ninety-five unconnected outputs are explicitly identified, without inventing tie-cell limits. The worst SF slew margin remains about 0.299 ps. Ten parser/coverage controls pass. Conditional load/timing models, external-port assumptions and startup frequency coverage still prevent electrical or physical gate qualification. See `verification/prototype400/selected_digital_pin_electrical_coverage.json`.

Matched full-fine133 TT sender holdout 971 completed normally. Frozen-model checker 972 matches both UP decisions, all event counts and all observed timing edges without refitting; maximum replay edge error is 0.9851 ps. Measured feedback phases are +4.896 and +293.135 ps. This validates one additional source operating point and initial state under the conditional cut; DN timing, full phase coverage and native-interface qualification remain open.

SF/FS raw-bracket protocol 1005 predeclares two new training probes and one new holdout per corner (997–1002), using phase-translation estimates from prior training traces only. Each corner combines the new points with two prior training cases and three prior independent holdouts. Followers 1003/1004 wait for all three new cases, then select a negative opposite-decision bracket from training only; four separation controls pass. All six native probes use distinct spare CPUs 19–24, 12 GiB/3 h limits and observed 319-file PDK closures, bringing projected full-plus-serial reservations to 148 GiB within the 200 GiB ceiling. Recorded TT sender excitation and conditional boundary qualification gaps remain explicit. See `verification/prototype400/selected_SF_FS_raw_detector_bracketing.json`.

Frozen matching-sender replay now supports TT/FF/SS/SF/FS with actual device, initialization, physical-driver and same-full-native-source checks. The unchanged TT fine133 fit replay passes (maximum edge error 0.985004 ps); pairing that TT observation with the SS fit is rejected before output creation. Nine provenance/corner guard tests pass. Non-TT matching-sender replay awaits the queued native runs; no release gate is promoted. See `verification/prototype400/selected_matching_sender_holdout_checker.json`.

The independent SS midpoint holdout completed normally: measured phase -229.246629 ps gives DN while the frozen nominal model predicts UP. The four-case training set, parameters and Verilog are byte unchanged. The observation lies inside the prior [-279.246673, -179.247236] ps bracket, and all three observed conditional latency classes remain within prior timing bands. This is a nominal holdout miss, not a qualification pass; the bracket has not been narrowed using the holdout. See `verification/prototype400/selected_SS_raw_detector_bracketing.json`.

SS prior-endpoint diagnostics completed: 32 fixed threshold/latency choices replayed against eight native cases (256 replays), without using the midpoint holdout to select parameters. Every case has at least one sign/count matching choice (16 for the midpoint), but no single endpoint model matches all eight. This is case-by-case admission only; endpoint timing, adaptive decision uncertainty and closed-loop robustness remain unqualified. Corner-matched receiver clock-frame binding is still needed for SS loop composition. See `verification/prototype400/selected_SS_raw_detector_bracketing.json`.

SS interior-threshold follow-up resolves an endpoint-only ambiguity: three fixed fractions (1/4, 1/2, 3/4) of the original training bracket were replayed with unchanged prior nominal latencies. The 3/4 threshold (-204.247095 ps) matches signs and event counts for all eight cases; the original midpoint remains unchanged. Thus the endpoint-only result does not establish a need for adaptive decision behavior. Selecting this diagnostic variant from replay outcomes still requires fresh independent validation and timing checks before acceptance; it is not promoted. See `verification/prototype400/selected_SS_raw_detector_bracketing.json`.

The SS 3/4-bracket diagnostic candidate passes existing sign, count and timing-band checks in all eight native cases (maximum edge error 1.489322 ps). Those observations already informed candidate comparison, so this is not fresh independent validation. A new -0.4375 ns recorded-phase SS holdout is running on CPU18 with the candidate, predictions and failure handling frozen in `selected_SS_interior_validation_protocol_1013/protocol.json` before launch. It retains recorded TT excitation and cannot establish matching-corner sender qualification.

The fresh SS candidate holdout now has a live automatic follower (`selected_SS_frozen_candidate_fresh_replay_1015`). It waits for normal native completion, checks the prelaunch protocol and frozen parameter/model hashes, excludes previously compared observations, and replays once without launching or retrying native cases. Three chronology/role controls pass. An initial observer attempt rejected shell-wrapper chronology; the corrected observer uses the native process birth, and the original native run was untouched.

First-stage receiver clock-frame extraction now binds PLLOUT CSV and receiver PWL to the identical completed full-native RAW, snapshot and corner. TT fine133 gives 24 paired rising edges at 200–260 ns, with transport 249.595083–249.633025 ps (median 249.622769 ps). Wrong-full-RAW and wrong-corner controls reject before output creation. The generator accepts all five declared corners, but non-TT measurements await their full-native packets. Second-stage timing and interface qualification remain open. See `verification/prototype400/selected_full_sender_clock_frames.json`.

Replacing the earlier TT receiver frame with the same-source fine133 frame changes transport by only 0.000377427 ps. The generated composition differs only in four publication-delay literals. An actual Icarus replay at the existing 1 ps precision resolves both old and new literals to the same 205/207/217/224 ps delays. No new loop matrix was run or claimed; the comparison establishes that this frame substitution does not change those modeled delays. See `verification/prototype400/selected_full_sender_clock_frames.json`.

Constant-pin electrical review verified the original PDK HI=1/LO=0 functions and absence of a source max-capacitance constraint; no limit was lost in rendering or invented for acceptance. The selected routed database has eight loaded tie outputs, each connected to exactly one D pin (modeled load 3.207749–8.955638 fF). All 24 late-zero slews in each of five views are precisely those eight D pins plus sixteen constant outputs. This closes their STA topology explanation only; early-zero sources, physical power-up/constant drive and parent analog-macro electrical qualification remain open. See `verification/prototype400/selected_digital_pin_electrical_coverage.json`.

Zero-slew topology review is complete for the linked digital-pin inventory. Besides the 24 constant-topology late-zero pins per corner, all early-only zero pins (TT70/FF82/SS12/SF64/FS69) are actual unconnected outputs in the selected routed database, and every affected output has zero entries in its early transition tables. The database has 95 unconnected outputs, matching the original inventory. These are conditional model lower bounds, not measured instantaneous physical edges. Timing/load qualification and parent analog-macro electrical checks remain open. See `verification/prototype400/selected_digital_pin_electrical_coverage.json`.

Same-source receiver-frame measurements are now queued behind the existing FF/SS/SF/FS sender-packet observer. The live follower `selected_matching_corner_receiver_frames_1022` checks actual packet corner/provenance and measures each first-stage clock frame as its original full-native run completes. It launches no simulations, preserves all existing jobs, and retains the completed TT reference. No non-TT frame or timing qualification is claimed before observation. See `verification/prototype400/selected_full_sender_clock_frames.json`.

A separate same-corner diagnostic composition builder now supports TT/FF/SS/SF/FS while checking raw-fit and publication model hashes, matching operating points and physical model, and a source-bound receiver frame. Its TT output is byte-identical to the existing fine133-frame composition. Wrong-corner and unbound-frame controls reject before output creation. Non-TT compositions await their frames; frame binding does not qualify the raw fit's excitation or validate the interface. See `verification/prototype400/selected_full_sender_clock_frames.json`.

The predeclared independent FS -0.1 ns recorded-phase holdout completed normally over 80 ns. It reports DN at measured -152.275600 ps, then UP at +639.367614 ps, with one captured event toggle per detector rise. The holdout remains excluded from fitting; FS training probes and bracket assessment are still pending. Recorded TT excitation and conditional exterior remain unqualified. See `verification/prototype400/selected_SF_FS_raw_detector_bracketing.json`.

The six predeclared SF/FS probes completed normally. FS now has a training-only bracket [-252.274642, -28.254153] ps: all four training cases and four independent holdouts match signs, counts and timing-band checks (maximum edge error 0.593184 ps). SF correctly stopped without fitting: measured training DN points -61.446994/-261.446613 ps still lack a negative-phase UP point. One additional SF training probe at recorded -0.15 ns is live, selected only from training data; its five-training/four-holdout follower is waiting. Its runtime capture binds 319 static PDK include files. Holdouts remain excluded from bracket selection, and matching-corner sender/closed-loop qualification remains open. See `verification/prototype400/selected_SF_FS_raw_detector_bracketing.json`.

FF interior-threshold diagnostics now identify a common fixed decision model, without changing the original failed nominal fit. Three predeclared fractions of the prior training bracket were replayed; the 3/4 threshold (-37.543857 ps) matches all seven existing cases, including timing-band checks (maximum edge error 0.987784 ps), with original nominal latencies unchanged. Those cases informed comparison, so a fresh +0.0625 ns recorded-phase FF holdout is running on CPU20 with prelaunch-frozen candidate bytes and a live automatic replay follower. Its live runtime namespace capture records 319 static PDK include files, not a historical image-launch attestation. Matching-corner sender, independent outcome and loop qualification remain pending. See `verification/prototype400/selected_FF_raw_detector_fit.json`.

The fresh SS interior-candidate holdout completed normally: measured -216.746473 ps gives DN as predicted; event counts and prior timing-band checks pass (maximum fresh edge error 1.247635 ps). The second observed native phase +573.912582 ps gives UP. A bound diagnostic candidate now copies the exact prelaunch-frozen parameters/Verilog, retaining eight comparison cases and one new independent holdout without refitting. Wrong-corner prior, failed fresh replay and unbound-protocol controls all reject before output creation. This remains recorded-TT-excitation evidence; full phase, matching-corner sender and interface/loop qualification remain open. See `verification/prototype400/selected_SS_raw_detector_bracketing.json`.

Whole-native MOS voltage measurement now covers all 61,616 external MOS devices (53,812 unique cards / 21,722 terminal nodes) over all 45,408 saved samples of completed TT fine133. Ten mapping/parser controls pass; seven extrema witnesses were independently recovered by RAW byte offsets and Python arithmetic, matching exactly. Standard-NMOS VDS reaches 2.234742 V at 181.889935 ns; the largest absolute device-terminal difference is 2.320552 V. Retained node/wire maps locate the reviewed extrema in DCO e-inverter cells 335/342. The documented standard-NMOS SPICE model-valid VDS range ends at 1.95 V ([PDK device details](https://skywater-pdk.readthedocs.io/en/main/rules/device-details.html)); this motivates electrical/model review, not a reliability verdict. Saved-sample values do not prove inter-sample bounds, intrinsic-device stress, convergence or other-corner behavior. No SPICE simulations were launched. See `verification/prototype400/selected_native_MOS_voltage_extents.json`.

The voltage excursions persist in the final 200–260 ns window (18,446 samples): standard-NMOS maximum VDS is 1.997328 V, low-VT NMOS maximum VDS is 2.130301 V, and largest absolute terminal difference is 2.274389 V. Nine window/parser controls and seven independent extrema-witness checks pass. PDK functional truth confirms TE=0 disables the e-inverter output (four cases). At six late witness times, cells 335/342 have TE within 0.14 mV of ground, complementary enable near 1.8 V, and Z up to 2.274389 V. Their six-MOS topology has no external primitive/resistor connection to Z but retains 209/338 coupling-capacitor cards. This is consistent with disabled-load capacitive boosting; causality, timestep convergence, independent-simulator agreement and reliability remain open. No layout ECO or new SPICE run was performed. See `verification/prototype400/selected_native_MOS_voltage_extents.json`.

The SF extended raw-detector fit (1028) completed with five training and four independent holdout cases, all sign/count/timing checks passing (maximum edge error 1.033091 ps). The measured training bracket is [-61.446994, -15.261710] ps. This remains a TT-sender-driven corner diagnostic. The FF frozen interior candidate failed its predeclared fresh holdout (1035): measured -48.663851 ps selected UP while the candidate predicted DN; event counts and timing failed. The candidate was not refitted or bound for downstream qualification. Input/artifact pins for both completed results were verified inside the retained simulation image. All release gates remain open.

A bounded conditional replay now reproduces the two DCO e-inverter voltage witnesses with the original 12 MOS devices and all 1,686 incident capacitors (8 solved internal nodes, 377 recorded boundaries). The 200–210 ns replay completes in 42.4 s at 0.5 ps maximum step and 59.8 s at 0.25 ps. After the first cycle, maximum internal-voltage error against the full-native trace is 23.797 µV and maximum timestep difference is 1.3195 µV. Output peaks remain about 2.27 V. Eight extraction/assessment controls pass. The preparation, runner, comparison and failed initialization/filename attempts are retained in `verification/prototype400/selected_einvp_conditional_replay.json`. This is a reproducible conditional diagnostic; it does not establish independent-simulator agreement, causality, reliability or release electrical-rule qualification. The successful base trace was reused with verified hashes after correcting the wrapper completion marker, without rerunning or overwriting it.

Three predeclared conditional drive controls (1056) completed normally. With capacitor-boundary voltages held at their recorded initial values, output peaks remain 2.248 V and peak-to-peak swings remain 0.504/0.511 V. Holding only the external MOS gate drives constant reduces the swings to 0.0653/0.0698 V; holding both categories constant leaves 0.000387/0.000363 V. Thus external gate excitation is the larger contributor to the dynamic swing in this cut, through mechanisms including intrinsic MOS capacitance; contributions are not additive. The inherited output charge remains about 2.09 V in the quiet-both control, so these interventions do not establish the historical origin of that initial above-rail voltage. Four transformation controls pass; source and artifact hashes were verified in the retained image. See `verification/prototype400/selected_einvp_drive_factorial.json`. No layout, physical model geometry, release criterion or qualification flag changed.
