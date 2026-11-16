# PLL and RC export state — 2026-11-16

The physical RC export repair and full native reset DC checks pass. The 400 MHz
PLL is **not release ready**: repaired full-RC transient correlation, enabled
startup/lock validation, and integration into the release qualification flow
remain incomplete. Approved limits remain 300 ppm settling and ±3,000 ppm
release lock; the reset assertion contract is at least 80 ns.

## Verified RC repair

- Full physical audit 1766 passes all 13 export integrity checks, preserving
  device connectivity, wire resistances, signed capacitance and all 65 ports.
- The reversible zero-capacitance adapter preserves literal zero-C cards as
  comments, removing 785,307 empty equations without removing finite C or R.
- Native matrix 1814 has 923,123 unknowns and no empty rows or columns.
- Full reset DC 1825 completes normally with 619 numeric factorizations and
  **12 recovered linear failures**. Only the printed ports were independently
  checked for finite values; this is not full internal-state qualification.

## Simulation acceleration

The original full-RC transient 1827 stopped at its 24-hour cap after 9,413
numeric factorizations. It reached approximately 43.495 ns.

Thread benchmark 1828, on one captured full-RC DC matrix:

| Threads | Numeric factorization time |
| --- | ---: |
| 1 | 8.18 s |
| 2 | 7.38 s |
| 4 | 6.84 s |
| 8 | 7.33 s |

Four threads give approximately 1.20× numeric-factorization speedup in this
single-matrix experiment. Basker and KLU2 (1829) pass divider controls; both
full-RC DC diagnostics hit their ten-minute caps. These timeouts do not establish
relative solver speed or completed DC accuracy.

The step-tracing build had dropped the nonlinear solver hook that sets transient
context, preventing checked factor reuse. Isolated build 1830 restores that hook
using the current adapter headers. DC exclusion and analytical RC controls 1831
pass. Nonlinear diode control 1832 reduces fresh factorizations from 2,032 to 15,
with maximum reference waveform difference 2.22e-16 V. Residual checks and fresh
factorization fallback remain unchanged.

Full-RC reuse trial 1833 stops at three hours, reaching 13.29 ns. Frozen partial
comparison 1834 finds identical decks apart from output paths and maximum
65-port waveform difference approximately 20 pV over that shared interval.
Over matching simulated time 3.4–10.22 ns, throughput improves from 3.91 to
11.80 ns/hour: **3.02× combined speedup from reuse plus four threads**. This does
not isolate reuse speedup and covers reset-only behavior.

## Extended full-RC result

Run 1835 stops at its 24-hour cap, reaching **103.885 ns**, including 23.785 ns
after the reset ramp ends. At the last 25,500-call progress record: 871 fresh
factorizations and 24,629 accepted reuse solves, with zero DC reuse hits.
Post-reset throughput is approximately 4.12 ns/hour.

Frozen analysis 1836 checks all printed values as finite. Reset releases
correctly. PLL_ENABLE stays low by construction. PLLOUT remains high,
CONFIG_BUSY remains high, and CONFIG_READY/TRACKING/FAILED remain low. There
is no final solver summary, so complete failure totals and independent residual
acceptance are not verified. This partial diagnostic neither proves enabled
operation nor diagnoses a startup failure.

## Mixed-signal startup result

Diagnostic 1838 uses the actual layout-bound selected400 controller RTL with
six older static-subsystem DCO tuning knots, interpolation, and unqualified
clock/detector models. Coarse 23/fine 128, KI=1/KP=2, phase 0 passes:

- Cold start.
- Disable and re-enable.
- Asynchronous reset and recovery.

Each case runs in approximately seven seconds. Initial milestones are oscillator
release at **260 ns**, first output rising edge at **262.503 ns**, configuration
ready at **1.10 µs**, and tracking asserted at **1.3912 µs**. These are modeled
functional results, not physical lock qualification. The native diagnostic uses
coarse 20/fine 112 and held-low enable, so these are not matched correlation
cases. The 103.885 ns native endpoint precedes modeled startup milestones.

## Recommended next work

1. Match preset, reference phase, reset and enable sequence between the
   mixed-signal and native correlation cases.
2. Validate repaired-export analog behavior at the relevant oscillator,
   programming and clock boundaries; older DCO knots do not qualify new RC.
3. Use mixed-signal diagnostics for controller iteration and targeted full-RC
   experiments for physical correlation, rather than another identical long
   held-disabled macro run.
4. Establish completed enabled startup, frequency and lock evidence before
   release qualification. A tracking bit alone is not frequency qualification.

## Retained implementation and evidence

Solver and analysis scripts are in `verification/signoff400/` (1828–1838), with
`tools/xyce_umfpack/build_reuse_context_1830.py` and the startup trace bench
`tb/tb_programmed400_startup_diagnostic_1837.v`. Compact receipts and losslessly
compressed logs are retained in `verification/prototype400/rc_acceleration_1838/`.
Large netlists, matrices and waveform captures remain hash-pinned build
artifacts. Retained absolute input paths describe the originating workspace;
binary reconstruction requires the pinned CAD image and original dependencies.
