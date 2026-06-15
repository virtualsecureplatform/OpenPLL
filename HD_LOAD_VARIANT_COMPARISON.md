# HD Load Variant Comparison

This note records the HD-load experiment against the tagged `v6` 25 MHz
configured PLL release. The goal was to check whether HD load cells improve DCO
precision and deterministic BBPD jitter enough to promote a new release.

## Variants Checked

| Variant | Ring cells | Load cells | Physical status | Result |
| --- | --- | --- | --- | --- |
| v6 release | HS NAND/NAND2B | 90 HS NAND2 loads | Existing v6 release | Baseline |
| HS ring + HD loads | HS NAND/NAND2B | 144/152/160/180 HD NAND2 loads | Not promoted | Mixed HS/HD rows do not fit one macro cleanly because the HS and HD sites have different row heights. |
| all-HD 255-load candidate | HD NAND/NAND2B | 255 HD NAND2 loads | DCO macro signoff-clean | Promoted for the current source/behavioral release because it preserves one-macro implementation and improves peak-to-peak period jitter across the configured targets. |

The all-HD source uses `sky130_fd_sc_hd__nand2_8` for the oscillator/reset and
mirror merge path, `sky130_fd_sc_hd__nand2b_4` for turn/pass delay, and one
physical `sky130_fd_sc_hd__nand2_1` load per DCO thermometer bit.

## Frequency Coverage

The all-HD 255-load candidate covers all configured 25 MHz reference targets in
pre-layout Xyce waveform checks:

| Target | Coarse | Bracketing codes | Measured bracket |
| ---: | ---: | ---: | ---: |
| 100 MHz | C24 | 0..147 | 98.224916..100.056414 MHz |
| 250 MHz | C07 | 8..11 | 249.850624..250.146396 MHz |
| 300 MHz | C06 | 242..245 | 299.853581..300.361094 MHz |
| 400 MHz | C03 | 45..255 | 399.903986..448.308082 MHz |
| 500 MHz | C02 | 145..149 | 498.516140..500.154405 MHz |

The generated target summary is
`build/xyce_dco_mirror48_allhd_load255_target_check/dco_coarse_target_summary.csv`.

## Matched Jitter Screen

The deterministic jitter comparison uses the sampled ideal-BBPD model with
`ref=25 MHz`, `DLF_FRAC_WIDTH=2`, `cycles=80000`, `discard=10000`,
`phase_start_ps=-100,0,100`, and a 40 ps BBPD deadband. Values below are the
worst fitted-TIE RMS across those phase starts.

| Target | v6 release gain | v6 TIE RMS | all-HD best gain | all-HD TIE RMS | Decision |
| ---: | ---: | ---: | ---: | ---: | --- |
| 100 MHz | 16:8 | 30.347 ps | 4:2 | 25.413 ps | Improved |
| 250 MHz | 16:8 | 27.523 ps | 2:1 | 30.293 ps | Regressed |
| 300 MHz | 16:2 | 660601 ps | 4:2 | 32.118 ps | Improved |
| 400 MHz | 1:4 | 18.514 ps | 4:2 | 33.882 ps | Regressed |
| 500 MHz | 16:5 | 92.885 ps | 1:1 | 34.606 ps | Improved |

The matched v6 artifacts are under `build/jitter_compare_25mhz_v6_matched/`.
The all-HD artifacts are under `build/pll_jitter_25mhz_allhd255/`.

Peak-to-peak period jitter is the metric that moved the release decision. The
same matched screen shows lower worst-case period peak-to-peak jitter at every
configured target:

| Target | v6 period p-p | all-HD period p-p | Result |
| ---: | ---: | ---: | --- |
| 100 MHz | 10.423 ps | 2.653 ps | Improved |
| 250 MHz | 4.114 ps | 1.577 ps | Improved |
| 300 MHz | 70.083 ps | 3.759 ps | Improved |
| 400 MHz | 4.090 ps | 1.440 ps | Improved |
| 500 MHz | 9.402 ps | 1.183 ps | Improved |

## Signoff Checks

The all-HD DCO macro itself passes the local DCO signoff artifact checker:

```sh
make check-dco-einvp-coarse-librelane-signoff
```

The source-level configured PLL checks also pass:

```sh
make check-pll-25mhz-divider-config \
     check-pll-25mhz-divider-controller \
     check-pll-25mhz-configured-wrapper \
     check-pll-25mhz-configured-behavioral \
     check-sky130-macros
```

## Release Decision

Promote the all-HD 255-load candidate as the next source/behavioral release. It
is physically viable as a single DCO macro, supports the configured
100/250/300/400/500 MHz targets from a 25 MHz reference, and improves the
period peak-to-peak jitter screen that motivated the HD load experiment.

This is not a final extracted hard-top PLL signoff claim. The fitted-TIE RMS
screen still regresses at 250 MHz and 400 MHz, and the hard-top/configured
wrapper physical artifacts must be regenerated after the all-HD DCO and 5-bit
`DLF_KP` interface changes. The next useful jitter direction is a TDC-style
detector or another fine-load topology if integrated phase error becomes the
primary metric.
