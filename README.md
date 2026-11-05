# OpenPLL

The active target is a **programmed 400 MHz hard macro**, using a 25 MHz
reference and nominal 1.80 V, across TT/FF/SS/SF/FS at 27°C.
The [active release manifest](verification/active_release.json) points to the
[prototype signoff flow](verification/signoff400/README.md) and its
`requirements_v3.json` profile. The active prototype requires five operating
points and 60 closed-loop startup/recovery/phase scenarios per common gain pair.
Temperature qualification belongs to the retained earlier plan.

**The macro is not tapeout ready.** The current unfilled parent with 302 control
buffer pairs passes assembled DRC/LVS, bulk connectivity and both antenna
checks. An earlier filled template passes DRC/LVS and all seven global density
limits; chip-level window checks remain separate. Digital timing closure over
wire RC variation, final fill, loaded analog models, timing/CDC, closed-loop
qualification and clean handoff remain open. The audit keeps qualification
false until evidence for one final candidate closes all five prototype gates.

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
