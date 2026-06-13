# OpenPLL

OpenPLL is an integer-N bang-bang digital PLL implementation targeting Sky130.
The promoted implementation path is `IntegerPLL_HardMacroTop_EINVP`, which
combines a signed-off digital core, filled BBPD macro, filled
`IntegerPLL_DCO_EINVP` oscillator macro, and hard-top routing/SPEF.
That promoted path is a roughly 50-72 MHz TT DCO implementation. The repo also
contains independent coarse-band DCO modeling, full 8-bit fine-code loop
control, and fast DCO candidates for 100 MHz- to 200 MHz-order output work.
The `IntegerPLL_DCO_EINVP_SPARSE72` DCO macro has Ciel-PDK post-layout
signoff/RCX and a bounded extracted-DCO probe around 200 MHz, but that fast
path has not replaced the promoted full-PLL signoff path.

## What to Read

- `PLL_ARCHITECTURE.md` describes the PLL architecture and block-level control
  conventions.
- `SKY130_IMPLEMENTATION.md` summarizes the Sky130 implementation, physical
  status, signoff evidence, and local build commands.
- `SPICE_VALIDATION.md` records the transistor-level validation boundary,
  promoted evidence, and non-promoted diagnostic history.

## Current Status

The promoted v1 validation gate is the fast artifact audit:

```sh
make -C OpenPLL validate-sky130-pll-artifacts
```

It checks the promoted Sky130 signoff, SPICE, RTL, mixed-signal, and extracted
loop artifacts and writes:

```text
OpenPLL/build/sky130_pll_validation/sky130_pll_validation_summary.csv
OpenPLL/build/sky130_pll_validation/sky130_pll_validation_summary.json
```

The heavier regeneration flow is:

```sh
make -C OpenPLL validate-sky130-pll
```

That target is intentionally expensive because it regenerates promoted
simulation and signoff artifacts before running the same audit.

This fast-path development tree changes RTL/scripts after the v1 signoff
artifacts. The audit intentionally rejects stale physical/SPICE artifacts until
the corresponding LibreLane and long Xyce evidence is regenerated.

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
`sky130_fd_sc_hd` reference views. It has `sky130_fd_sc_hs` LibreLane setup
files, but not the required `libs.ref/sky130_fd_sc_hs`
Liberty/LEF/Verilog/SPICE views, so HS is not yet a usable standard-cell
library in this checkout.

`LIBRELANE_ROOT` is auto-detected from nearby checkout locations when possible.
`XYCE` defaults to the first `Xyce` on `PATH`; MPI/KLU diagnostics use
`$XYCE_MPI_ROOT/bin/Xyce` when that binary exists.

## Validation Boundary

The strongest promoted post-layout convergence evidence is the
hard-top-loaded extracted-DCO lock-window set. The Xyce C-interface
mixed-signal flow is promoted as BBPD polarity and gain evidence, especially
for keeping nonzero proportional gain, but it is not the final post-layout PLL
lock signoff path.

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
robust BBPD edge capture. The current promoted run measures fixed code 196 at
199.734 MHz, pulls a low-side start from code 184 to 197 with measured PLLOUT
at 200.000 MHz, and pulls a high-side start from code 220 to 194 with measured
PLLOUT at 200.000 MHz. This is direct-RCX near-lock evidence, not a full
rail-to-rail extracted-DCO regression.
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
