# OpenPLL

OpenPLL is an integer-N bang-bang digital PLL implementation targeting Sky130.
The promoted implementation path is `IntegerPLL_HardMacroTop_EINVP`, which
combines a signed-off digital core, filled BBPD macro, filled
`IntegerPLL_DCO_EINVP` oscillator macro, and hard-top routing/SPEF.

## What to Read

- `PLL_ARCHITECTURE.md` describes the PLL architecture and block-level control
  conventions.
- `SKY130_IMPLEMENTATION.md` summarizes the Sky130 implementation, physical
  status, signoff evidence, and local build commands.
- `SPICE_VALIDATION.md` records the transistor-level validation boundary,
  promoted evidence, and non-promoted diagnostic history.

## Current Status

The current validation gate is the fast artifact audit:

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

## Environment

The Makefile defaults assume Sky130 is installed through Volare at
`$HOME/.volare`. Override these variables for another local setup:

```sh
export PDK_ROOT=$HOME/.volare
export PDK=sky130A
export STD_CELL_LIBRARY=sky130_fd_sc_hd
export LIBRELANE_ROOT=$HOME/src/librelane
export XYCE_MPI_ROOT=$HOME/.local/xyce-mpi
```

`LIBRELANE_ROOT` is auto-detected from nearby checkout locations when possible.
`XYCE` defaults to the first `Xyce` on `PATH`; MPI/KLU diagnostics use
`$XYCE_MPI_ROOT/bin/Xyce` when that binary exists.

## Validation Boundary

The strongest promoted post-layout convergence evidence is the
hard-top-loaded extracted-DCO lock-window set. The Xyce C-interface
mixed-signal flow is promoted as BBPD polarity and gain evidence, especially
for keeping nonzero proportional gain, but it is not the final post-layout PLL
lock signoff path.

Diagnostic targets that are slow, host-sensitive, or known not to pass from
both rails are deliberately excluded from the promoted artifact gate and are
documented as diagnostic history in `SPICE_VALIDATION.md`.
