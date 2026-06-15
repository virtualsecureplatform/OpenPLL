# OpenPLL

OpenPLL is an integer-N bang-bang digital PLL implementation targeting Sky130.
The current high-frequency source/integration path is
`IntegerPLL_HardMacroTop_EINVP`, which combines the digital core RTL, filled
BBPD macro, physical `IntegerPLL_DCO_EINVP_COARSE` oscillator macro source, and
hard-top hardening flow. The current release promotes the all-HD coarse-DCO
source and 25 MHz configured RTL/behavioral path. Existing
hard-top/configured-wrapper routed artifacts must be regenerated after the
5-bit `DLF_KP` interface update before they are treated as current post-layout
signoff evidence. The DCO is one macro and one oscillator loop: HD
NAND/NAND2B turn/pass mirror delay provides coarse band selection, while 255 HD
NAND2 load cells provide local fine tuning. It does not use parallel DCO
macros, a mux-selected feedback tap, or a NOT-chain ring.

The ring-facing output buffer intentionally stays
`sky130_fd_sc_hd__buf_1` to limit oscillator-node loading. The fine-load
digital enable is NAND2 pin `B`, the pin whose series NMOS is directly
connected to `VGND` in the Sky130 HD `nand2_1` SPICE view.
If more oscillator speed margin is needed, adjust the ring/mirror gate drive,
effective loop length, or fine-load topology; do not upsize the ring-facing
output buffer as a speed fix because that directly increases oscillator load.

Older `IntegerPLL_DCO_EINVP` and `IntegerPLL_DCO_EINVP_SPARSE72` artifacts are
retained as low-frequency and 200 MHz diagnostic history, not as the current
100/250/300/400/500 MHz hardtop target history.

## What to Read

- `PLL_ARCHITECTURE.md` describes the PLL architecture and block-level control
  conventions.
- `SKY130_IMPLEMENTATION.md` summarizes the Sky130 implementation, physical
  status, signoff evidence, and local build commands.
- `SPICE_VALIDATION.md` records the transistor-level validation boundary,
  promoted evidence, and non-promoted diagnostic history.

## Current Status

The current fast coarse-DCO source/behavioral gates are:

```sh
make -C OpenPLL check-sky130-macros
make -C OpenPLL check-pll-25mhz-divider-config
make -C OpenPLL check-pll-25mhz-divider-controller
make -C OpenPLL check-pll-25mhz-configured-wrapper
make -C OpenPLL check-pll-25mhz-configured-behavioral
```

`rtl/IntegerPLL_25MHzModeConfig.v` is the reusable preset table for a 25 MHz
reference. It exposes the restored /4, /10, /12, /16, and /20 settings:

| Feedback divider | Target | Coarse | Fine seed | KI | KP |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 100 MHz | C24 | 139 | 4 | 2 |
| 10 | 250 MHz | C07 | 8 | 4 | 2 |
| 12 | 300 MHz | C06 | 242 | 4 | 2 |
| 16 | 400 MHz | C03 | 45 | 4 | 2 |
| 20 | 500 MHz | C02 | 149 | 4 | 2 |

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
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured`. Its existing routed/signoff
artifact predates the current 5-bit `DLF_KP` interface and must be regenerated
before it is treated as current physical release evidence.
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

| Target | Coarse | Seed | Interpolated seed frequency |
| ---: | ---: | ---: | ---: |
| 100 MHz | C24 | 139 | 100.069 MHz |
| 250 MHz | C07 | 8 | 249.851 MHz |
| 300 MHz | C06 | 242 | 299.854 MHz |
| 400 MHz | C03 | 45 | 399.904 MHz |
| 500 MHz | C02 | 149 | 500.154 MHz |

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

The heavier `make -C OpenPLL check-sky130-pll-25mhz-release` target still checks
post-layout hard-macro artifact freshness. After changing the physical
`DLF_KP` interface to 5 bits, the existing routed/signoff artifacts are stale
and must be regenerated before using that target as a post-layout release gate.

An optional slow direct-RCX integration smoke for the hardest divider target is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-500m-hold-smoke
```

It runs the extracted coarse DCO and extracted BBPD in Xyce at C02/code149 with
the digital divider/filter in the mixed-signal driver. Its short ADC-sampled
frequency estimate is intentionally loose; regenerated standalone RCX DCO rows
must remain the precise frequency evidence.

An even slower all-mode direct-RCX near-seed code-update diagnostic is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
```

The last completed all-mode direct-RCX run checked +/-4 fine-code starts for all
five divider targets on the previous HS-load/drive4 DCO family. That evidence
remains a historical direct-RCX integration diagnostic; regenerated standalone
RCX DCO rows remain the precise frequency evidence.

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
