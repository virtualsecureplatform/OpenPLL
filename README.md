# OpenPLL

OpenPLL is an integer-N bang-bang digital PLL implementation targeting Sky130.
The current high-frequency implementation path is
`IntegerPLL_HardMacroTop_EINVP`, which combines a signed-off digital core,
filled BBPD macro, physical `IntegerPLL_DCO_EINVP_COARSE` oscillator macro, and
hard-top routing/SPEF. The DCO is one macro and one oscillator loop: HS
NAND/NAND2B turn/pass mirror delay provides coarse band selection, while HS
NAND2 load cells provide local fine tuning. It does not use parallel DCO
macros, a mux-selected feedback tap, or a NOT-chain ring.

The ring-facing output buffer intentionally stays
`sky130_fd_sc_hs__buf_1` to limit oscillator-node loading. The current
post-layout RCX target map uses 90 local NAND2 fine loads split between
`osc_node` and `mirror_ret[0]`; the earlier C19/C20 deep-node slow-load banks
are not part of the shipping candidate. TT Xyce target-code probes cover 100,
250, 300, 400, and 500 MHz from a 25 MHz reference with duty and edge-rate
checks enabled. The configured-mode settings are /4 C20/code93, /10
C06/code234, /12 C04/code90, /16 C02/code76, and /20 C01/code121. Full
extracted-DCO-in-loop PLL lock evidence is still pending for that coarse-DCO
path.
If more oscillator speed margin is needed, adjust the ring/mirror gate drive,
effective loop length, or fine-load topology; do not upsize the ring-facing
output buffer as a speed fix because that directly increases oscillator load.

Older `IntegerPLL_DCO_EINVP` and `IntegerPLL_DCO_EINVP_SPARSE72` artifacts are
retained as low-frequency and 200 MHz diagnostic history, not as the current
100/250/300/400/500 MHz hardtop target.

## What to Read

- `PLL_ARCHITECTURE.md` describes the PLL architecture and block-level control
  conventions.
- `SKY130_IMPLEMENTATION.md` summarizes the Sky130 implementation, physical
  status, signoff evidence, and local build commands.
- `SPICE_VALIDATION.md` records the transistor-level validation boundary,
  promoted evidence, and non-promoted diagnostic history.

## Current Status

The current coarse-DCO structural and interface gates are:

```sh
make -C OpenPLL check-sky130-macros
make -C OpenPLL check-pll-25mhz-divider-config
make -C OpenPLL check-pll-25mhz-divider-controller
make -C OpenPLL check-pll-25mhz-configured-wrapper
make -C OpenPLL check-dco-einvp-coarse-librelane-signoff
make -C OpenPLL check-hard-macro-top-einvp
make -C OpenPLL check-hard-macro-top-einvp-spice
make -C OpenPLL check-configured-hard-macro-top-einvp-signoff
```

`rtl/IntegerPLL_25MHzModeConfig.v` is the reusable preset table for a 25 MHz
reference. It maps the 5-bit `FEEDBACK_DIVIDER` input to characterized
settings: divider /4 gives 100 MHz with C20/code93; /10 gives 250 MHz with
C06/code234; /12 gives 300 MHz with C04/code90; /16 gives 400 MHz with
C02/code76; and /20 gives 500 MHz with C01/code121. It also emits the promoted
`KI=16`, `KP=4` gains, a 10-bit
`DLF_Ext_Data` seed equal to `target_code << 2`, and `CONFIG_VALID`. Unsupported
divider values are passed to the lower divider bus for observability but hold
`CONFIG_VALID=0` and do not enter tracking.

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
configured wrapper is also hardened as
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured`, a signed-off physical macro
that embeds the signed low-level hard macro and adds the 25 MHz divider controller.
The lower-level `IntegerPLL_HardMacroTop_EINVP` pins remain available for
characterization and custom bring-up.

Next-version BBPLL work should focus on the broader control extension needed
for robust acquisition from arbitrary phase and code, rather than on packaging
the configured interface.

`make -C OpenPLL check-pll-25mhz-configured-behavioral` runs a reset-to-tracking
behavioral PLL regression for the same five divider values. It uses the real controller,
digital core, divider, and BBPD with a behavioral DCO table fitted to the
post-layout coarse-band measurements, and checks measured output frequency plus
non-rail DCO control after the preset load.

The current configured-mode 25 MHz-reference PLL target gate is:

```sh
make -C OpenPLL xyce-pll-mixed-signal-25mhz-targets
```

It aliases to the direct extracted-DCO mixed-step hold smoke after refreshing
the post-layout RCX DCO target probes. The selected coarse/fine settings are
C20/code93, C06/code234, C04/code90, C02/code76, and C01/code121. This is configured-mode
near-seed tracking evidence with `KI=16` and `KP=4`, not frequency acquisition
from arbitrary phase or code. Each row must hit the target-code neighborhood,
observe at least one BBPD decision in the expected initial direction, finish
within 2 MHz of the target, and keep the last eight modeled DCO updates inside
the same 2 MHz frequency window with no more than 16 fine-code span.

The current fast shipping artifact check for that 25 MHz coarse-DCO path is:

```sh
make -C OpenPLL check-sky130-pll-25mhz-release
```

It checks the coarse-DCO RTL shape, including the `buf_1` output-buffer
constraint, the divider preset table, the divider controller/wrapper, the five
waveform-qualified target-code rows, the configured tracking summaries, the
configured behavioral PLL reset-to-tracking regression, the fresh
`IntegerPLL_HardMacroTop_EINVP` signoff/SPICE-interface summaries, the signed
`IntegerPLL_HardMacroTop_EINVP_25MHzConfigured` wrapper summary, the five
direct-RCX hold smokes, and the ten low/high near-seed direct-RCX code-update
rows.

An optional slow direct-RCX integration smoke for the hardest divider target is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-500m-hold-smoke
```

It runs the extracted coarse DCO and extracted BBPD in Xyce at C01/code121 with
the digital divider/filter in the mixed-signal driver. Its short ADC-sampled
frequency estimate is intentionally loose; the standalone RCX DCO rows remain
the precise frequency evidence.

An even slower all-mode direct-RCX near-seed code-update diagnostic is:

```sh
make -C OpenPLL xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
```

The current TT run checks +/-4 fine-code starts for all five divider targets.
Low-side cases use REF phase offset -0.25 and divider seed 0; high-side cases
use REF phase offset 0.25 and divider seed `NDIV-1`. All ten rows pass with the
expected two BBPD decisions: 100 MHz moves 89->92 and 97->94, 250 MHz moves
230->233 and 238->235, 300 MHz moves 86->89 and 94->91, 400 MHz moves 72->75
and 80->77, and 500 MHz moves 117->120 and 125->122. This is still near-seed
configured-control evidence, not blind rail-start extracted-loop acquisition.

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

It uses the same small `output-buffer-drives 1` assumption and checks the
sampled 100/300 MHz pre-layout brackets plus waveform quality. The shipping
100/250/300/400/500 MHz claim comes from the post-layout RCX target probes and the
`xyce-pll-mixed-signal-25mhz-targets` gate above.

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
`sky130_fd_sc_hd` and `sky130_fd_sc_hs` reference views. HD remains the default
library for the promoted low-frequency macros; the coarse high-frequency DCO
macro explicitly uses HS cells.

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
