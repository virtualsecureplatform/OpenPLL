# OpenPLL completion implementation

The approved highest mode is 450 MHz. In corrected short-window standalone
screens, the C1LOAD64 core's physical coarse-0 endpoints lie above 450 MHz at
the mixed SF and FS corners: they are 597.880--772.424 MHz at SF and
570.327--727.937 MHz at FS; its next band reaches only 341.543--376.225 MHz
and 336.533--366.465 MHz, respectively. These endpoint measurements do not
prove that all interior fine codes exclude 450 MHz. The separate OSC8 fast core's
physical coarse-1 band brackets 450 MHz at both corners (444.292--488.916 MHz
at SF, 438.468--477.658 MHz at FS). A flat two-core candidate maps logical
coarse code zero to that fast band, and its synthesized wiring check passes.
The first routed alias candidate has zero DRC, LVS, and antenna violations,
but 27 slew violations and one capacitance violation at the slow library
corner, all attributable to the new remap gate's output. The stronger `or2b_2`
variant passes the independent physical check with zero slew, capacitance,
DRC, LVS, and antenna violations, and its synthesized remap check passes
(`pvt_probe_flatdual_osc8_c1load64_remap_fastc1alias_x2`). Magic all-net RCX
of that GDS completed with 3,793 of 3,799 reported nets and 192,017
resistors. Exact resistor-node elimination leaves 161,664 resistors without
approximating capacitance. Magic reports 232 missing-terminal warnings in the
extraction feedback. They occur at the left and right core edges, coincident
with the physical `decap_3` edge-cell columns in the final DEF. This is an
inference from coordinates: the DEF has 116 `decap_3` edge cells, and the
feedback has 116 `VPWR` plus 116 `VGND` terminal warnings. The PDK SPICE view
of each `decap_3` has one PFET and one NFET with drain and source tied to the
respective power rail. This correlation explains the count but does not waive
the warnings. The extraction is therefore diagnostic. TT and mixed-corner
full-RC 450 MHz screens are recorded below. These are range and structural screens,
not a 450 MHz preset or assembled-PLL PVT qualification.
The LibreLane `final/spice` view contains empty standard-cell placeholders;
Xyce rejects a transient deck built from it because `PLLOUT` has no defined
electrical driver. It cannot substitute for the completed Magic all-net RCX.
The completed 12--25 ns full-RC flat-layout screens give 419.307/458.722 MHz
at SF and 410.352/443.974 MHz at FS for logical coarse zero, fine codes
8/247. Thus the sampled SF band starts above 400 MHz, while the FS upper
endpoint falls 6.026 MHz below 450 MHz. The corresponding half-window
differences are 5.935/1.651 MHz at SF and 5.690/2.418 MHz at FS, so these
short windows are unsettled and cannot qualify a preset. TT logical coarse
two/fine-74 measures 424.572 MHz over four periods with 4.678 MHz half-window
spread, far below its standalone 450 MHz result. The flat candidate is not
promoted; its full layout disperses each core's cells across the die.
Its TT logical coarse-two fine-8/247 endpoint screen finishes at
414.234/453.038 MHz (four/five periods) over 12--25 ns. It samples a 450 MHz
bracket, but the 4.239/3.561 MHz half-window differences are far beyond
calibration tolerance. The target-code region would need a new search even
at nominal conditions.
The adjacent selected slow logical coarse-two/fine-247 high endpoint completes
at 354.880 MHz at SF and 344.436 MHz at FS over 12--25 ns. Its half-window
differences are 5.640/6.388 MHz. Compared with the flat fast band's sampled
fine-8 lows of 419.307/410.352 MHz, these endpoints leave 64.427/65.916 MHz
gaps containing 400 MHz. The large drift prevents calibrated values, and
these adjacent tested bands do not supply a sampled 400 MHz setting.
A separate hard-macro wrapper snapshot
`pvt_probe_450_fixedgeom_diode_repair_v4_fastalias` exposes fast physical
coarse band one at logical coarse zero. Its synthesized 240-case control
check passes, and its routed layout passes the independent physical checker
with zero reported DRC, LVS, antenna, slew, and capacitance violations.
All-net Magic RC extraction completed with 8,991/8,997 final reported nets
and 806,864 resistors; exact resistor-only reduction leaves 769,289 while
retaining capacitors and other devices. Magic reports 1,040 extraction
warnings. `check_hierarchical_decap_feedback.py` matches every warning-box
center to exactly one placed boundary `decap_3` cell: 368 in the wrapper and
76 in each hard macro. Each of the 520 cells has one VPWR and one VGND
warning. The DEF/feedback hashes and result are in
`dualmacro_diode_repair_v4_fastalias_all_net_rc/feedback_boundary_association.json`.
This spatial explanation does not waive connectivity or electrical
qualification of the extraction.
The reduced netlist contains six checked-geometry antenna diodes; TT/27 C,
SF/125 C, and FS/125 C diode translations completed with provenance sidecars.
Assembled full-RC frequency measurements remain pending, so physical checks
and completed extraction do not qualify its release modes.
An isolated 24-fixed-load OSC8 macro screens at 427.913/469.250 MHz at SF
and 421.390/457.559 MHz at FS for physical coarse one, fine 8/247, using
corrected 125 C and full RC over 12--25 ns. It remains above 400 MHz at both
low endpoints. A 72-fixed-load continuation's initial physical layout is
DRC/LVS/antenna clean but has 187 slow-library slew and eight capacitance
violations on the oscillator node. Its corrected SF/1.62 V/125 C 12--25 ns
full-RC endpoint screen gives 409.659/447.888 MHz (fine 8/247). The matching
FS screen gives 403.875/437.299 MHz. Neither sampled band brackets 400 or
450 MHz. The largest half-window difference is 0.238 MHz, also above the
100 ppm calibration limit. These are diagnostic only because that layout
fails the electrical checks.
A second 72-load layout moves 12 fixed loads from that node to the feedback
node; it still fails slow-corner slew (175) and capacitance (eight) checks.
Moving another 12 loads to feedback instead overloads that node, leaving
195 slew and four capacitance violations. A balanced placement with 16 fixed
loads on `osc_node` and 56 on `mirror_ret[0]` passes the independent physical
checker with zero reported DRC, LVS, antenna, slew, and capacitance violations
(`pvt_probe_turn10_boost8_osc8_load72r56`). Its all-net Magic extraction
completed with 2,190/2,192 final reported nets and 92,097 resistors; exact
internal-node reduction leaves 80,004 resistors. Magic reported 152
missing-terminal warnings. All 152 feedback-box centers fall inside exactly
one of the 76 placed boundary `decap_3` cells, two warnings per cell. This
spatial association does not waive extraction qualification. Corrected
SF/1.62 V/125 C full-RC 12--25 ns endpoints are 400.976/437.400 MHz, and
FS endpoints are 394.240/426.029 MHz, fine 8/247. The sampled FS band
brackets 400 MHz, but the SF band starts 0.976 MHz above it. Both upper
endpoints fall below 450 MHz. The SF high endpoint has 0.226 MHz half-window
spread, exceeding the 100 ppm calibration tolerance. These are range screens,
not qualified presets or assembled-PLL PVT coverage.
An 88-fixed-load exploration adds eight loads each to the coarse-one forward
and return nodes while retaining the balanced shared-node loads. Its route
`pvt_probe_turn10_boost8_osc8_load88r56` also passes the independent physical
checker with zero reported DRC, LVS, antenna, slew, and capacitance violations.
All-net Magic extraction of that route completed with 2,254/2,256 final
reported nets and 92,667 resistors; exact reduction retains 80,399. Magic
reported 152 missing-terminal warnings, and all 152 feedback-box centers
fall within exactly one of the 76 placed boundary `decap_3` cells. Corrected SF and FS
400 MHz endpoint screens completed over 12--25 ns at corrected 1.62 V/125 C:
fine-8/247 give 385.075/419.343 MHz at SF and 378.742/408.696 MHz at FS,
four periods per endpoint. Both sampled bands bracket 400 MHz. The SF high
endpoint's half-window difference is 0.178 MHz, above the 100 ppm calibration
tolerance. The 12--25 ns SF coarse-1/fine-116 interior sample measures
400.039 MHz, within the 400 MHz frequency bound, but its 0.075 MHz
half-window difference exceeds the 0.040 MHz calibration limit. Its completed
70 ns settling rerun measures 400.202 MHz across all 22 complete periods
from 12--70 ns. The first and last 11-period halves measure 400.124 and
400.280 MHz at the calibration threshold, a 0.156 MHz difference above the
0.040 MHz calibration limit. The runner's 400.001 MHz result uses only its
first two measured cycles and is not a sustained-window result. The FS
coarse-1/fine-175 sample measures
399.280 MHz with 0.011 MHz half-window difference; it misses the 400 MHz
frequency bound. The corrected FS coarse-1/fine-181 continuation measures
400.023 MHz with 0.009 MHz half-window difference over 12--25 ns. Its
completed 12--70 ns waveform averages 399.980 MHz across 22 complete
periods. The first and last 11-period halves measure 400.006 and
399.954 MHz at the calibration threshold, a 0.052 MHz difference above the
0.040 MHz calibration limit. At
TT/1.80 V/27 C, this macro measures 492.187/536.866 MHz at coarse 1 and
339.723/360.864 MHz at coarse 2 over 12--25 ns (fine 8/247). The 131.323 MHz
gap between adjacent sampled bands contains both 400 and 450 MHz.
Numerical calibration and assembled-PLL behavior remain unqualified.
This is not a release macro.
For TT 400 MHz coverage, an exploratory C1LOAD128 variant doubles the
coarse-one fixed loads on one node. Its completed route has 132 slow-corner
slew and four capacitance violations, so it is not physically usable. A
distributed C1LOAD128R continuation keeps 64 loads on that node and splits
64 more across three other coarse-one path nodes. Its routed layout passes
the independent checker with zero reported DRC, LVS, antenna, slew, and
capacitance violations (`pvt_probe_turn10_boost8_c1load128r`). All-net Magic
RCX completed with 2,410/2,412 final reported nets and 93,401 resistors;
exact reduction retains 81,363. Its 152 missing-terminal feedback boxes
each fall inside exactly one of the 76 placed boundary `decap_3` cells.
This spatial association does not by itself qualify extraction. Corrected
TT/1.80 V/27 C coarse-1 fine-8/247 12--25 ns endpoints measure
371.476/406.070 MHz (four periods each), bracketing 400 MHz. The upper
endpoint has 0.093 MHz half-window spread, above the 0.040 MHz calibration
limit. Interior codes 204 and 211 finish at 399.406 and 400.461 MHz over
12--25 ns (four periods each). Both miss the 400 MHz 1000 ppm frequency
bound, and their 0.075/0.078 MHz half-window differences exceed the 0.040 MHz
calibration bound. The code-208 interpolation check finishes at 400.020 MHz
over 12--25 ns, within the 1000 ppm frequency bound, but its 0.077 MHz
half-window difference misses the 0.040 MHz calibration limit. Separate
The code-208 70 ns run was found stopped with no live simulator and an
incomplete waveform ending at 9.805697 ns on 2026-10-04. It has been
restarted with the same deck settings and a 14,400 s simulation limit;
code 211 has no completed 70 ns result. This is a standalone
macro range screen, not an assembled-PLL preset or PVT qualification.
The restarted code-208 70 ns deck subsequently completed with a matching
completed-deck hash. It measures 400.174361 MHz over 22 periods in
12--70 ns, within the frequency bound, but has 0.141307 MHz half-window
drift, exceeding the absolute 0.040 MHz calibration limit. Its 40--70 ns
segment measures 400.245027 MHz over eleven periods with 0.038878 MHz
drift; adjacent-code local spacing is still unmeasured over that window.
`completed_settling_measurements.json` pins the deck/waveform hashes and
both windows. A standalone default-tolerance 160 ns campaign for adjacent
codes 206/207/208, measuring 80--160 ns with a 10 ps cap and a 21,600 s
per-simulation limit, is started in
`c1load128r_true_tt27_c1_codes206207208_160ns_cap10ps` to evaluate later
settling and actual local spacing. Four-variant convergence and assembled
behavior remain required; none of these codes is a qualified preset.
All 232 missing-terminal warning locations associate with placed boundary
`sky130_fd_sc_hd__decap_3` cells (`feedback_boundary_association.json` in
the flat-layout extraction directory). Independent extraction of that cell
in `build/modern_25mhz/boundary_decap3_all_net_rc/` reproduces two warnings
and retains both expected MOS devices and 21 resistors. Its connectivity
screen confirms all eight device terminals reach their intended supplies
and both devices retain the library width/length. This explains the warning
locations but does not establish capacitance or dynamic impedance equivalence.
An isolated-cell TT/27 C AC comparison at 1.62/1.8/1.98 V completes with
upstream Xyce (`build/modern_25mhz/boundary_decap3_ac_tt27_v1/`). At 1 MHz,
the extracted cell has 8.447/8.506/8.547 fF versus 6.711/6.769/6.811 fF
for the normalized library transistor pair. The 1.73617 fF difference
matches the explicit extracted cross-supply capacitors; all 21 resistors
are retained. The 10 GHz admittance magnitude is approximately 25% higher
than the transistor-only reference. This nominal capacitance accounting
supports the isolated decap extraction, but is not a full-PVT extraction
qualification or an assembled-PLL power/jitter result.
The subsequent 45-point isolated-cell AC grid (all five corners, three
voltages, and three temperatures) completes all 90 comparison decks with
zero simulator failures in `build/modern_25mhz/boundary_decap3_ac_pvt_v1/`.
At every point, the 1 MHz capacitance difference agrees with the explicit
1.73617 fF layout capacitance within 1.04e-8 fF (screen limit 1e-4 fF).
The report pins the raw decks, spectra, extracted cell, and release image
hashes. This supports capacitance accounting for the warning-producing
boundary cell across PVT, without qualifying full-PLL extraction or jitter.

At TT, the standalone C1LOAD64 coarse-1 fine-code-74 12--70 ns waveform
averages 450.111082 MHz over 25 periods. It meets the 1000 ppm frequency
bound, but the 0.067892 MHz half-window difference exceeds the 100 ppm
calibration bound. The measured code remains provisional.

Temperature evidence correction (2026-09-30): the Xyce generators previously
emitted `.temp`, which upstream Xyce ignored. Their non-27 C measurements
below do not establish the temperatures stated in their labels and must be
rerun. Generators now use `.options device temp=...`; the PVT gate requires
that directive and a matching completed-deck hash. No historical temperature
coverage claim is accepted as release evidence.

A corrected upstream-Xyce/KLU SS/1.62 V/125 C standalone C1LOAD64
coarse-0/fine-247 rerun completed in 245.8 s with the explicit temperature
directive. Its runner measurement is 510.236 MHz. Evidence is in
`build/modern_25mhz/c1load64_true_ss125_high_v1/`; this is an upper-endpoint
range screen, and does not qualify a 450 MHz preset or the assembled PLL.
The full 12--25 ns waveform averages 510.563 MHz over six periods; the
two half-window estimates differ by 0.572 MHz, so calibration convergence
is not established by this short run (`window_screen.json`).
The corrected coarse-0/fine-8 lower endpoint completed in 366.8 s and
measures 406.125 MHz in the runner's initial measurement window
(`build/modern_25mhz/c1load64_true_ss125_low_v1/`). These endpoint samples
bracket 450 MHz at this operating point. A measured interior code and
numerical convergence checks remain necessary for calibration.
The corrected FF/1.98 V/-40 C standalone C1LOAD64 coarse-3 endpoints
completed with runner measurements 440.821/471.411 MHz for fine 8/247,
respectively (`build/modern_25mhz/c1load64_true_ffm40_c3_v1/`). These
short-run samples bracket 450 MHz at the actual requested cold temperature;
an interior-code run with a 10 ps maximum timestep is pending.
The SS/1.62 V/125 C coarse-0/fine-110 run with a 10 ps maximum timestep
completed in 1369.4 s. Its full 12--40 ns waveform averages 454.527 MHz
over twelve periods, with a 0.240 MHz half-window difference. It therefore
provides an interior tuning measurement but fails the 450 MHz frequency
and convergence bounds; it is not a qualified preset. Neighboring search
codes 100 and 101 are running under the same numerical controls.

Baseline: 25 MHz reference, upstream Xyce, five output modes (100/250/300/400/450 MHz).
An isolated wrapper snapshot with standard antenna-diode repair enabled is
running as `pvt_probe_450_fixedgeom_diode_repair_v2`. The initial smaller-die
attempt failed placement at 109.847% utilization; v2 uses the previously
routable 480 x 280 um die. Its global repair inserted eight diodes and reports
zero remaining antenna violations. Synthesized control forwarding passes
240 cases (`build/modern_25mhz/diode_repair_v2_mapping.json`). Final v2
results have zero antenna violations and zero LVS errors, but seven Magic
and one KLayout DRC errors. The spacing errors are localized near
(160.1--160.5, 189.6--190.2) um on metal3 at the fast macro's top pins.
V3 shifts the fast macro from (60,65) to (60,66) um to test a different
pin-access alignment. Extraction and functional qualification remain
pending; these intermediate results do not establish release signoff.
V3 retains zero antenna/LVS errors and removes the prior fast-top DRC site,
but leaves seven Magic/one KLayout spacing errors at the slow macro's bottom
pins near (319.55--319.84, 94.875--95.31) um. V4 uses slow placement
(245,95.34) um while retaining the fast macro at (60,66) um. The completed
`pvt_probe_450_fixedgeom_diode_repair_v4` run has zero final Magic DRC,
KLayout DRC, LVS, and antenna violations. Its final netlist contains six
antenna cells (15.0144 um2). `check_librelane_signoff.py` passes against the
snapshot source and v4 configuration with streamout/XOR checks skipped.
The v4 synthesized netlist is byte-identical to the v2 netlist checked in
240 control-forwarding cases; evidence is recorded in
`build/modern_25mhz/diode_repair_v4_mapping_identity.json`. This establishes
the same synthesized mapping, not oscillator behavior.
Full all-net resistance/capacitance extraction is running in
`build/modern_25mhz/dualmacro_diode_repair_v4_all_net_rc/`; functional and
PVT qualification of this routed geometry remain open.
Its completed raw `.ext` device records contain six antenna diodes, each
matching the independent diode-cell extraction's `a=17388`, `p=528` and
coordinate scale. `raw_diode_geometry_screen.json` pins both extraction
files. This confirms raw geometry only; the final all-net RC netlist and
assembled connectivity/behavior are still pending.
The independent `sky130_fd_sc_hd__diode_2` cell extraction in
`build/modern_25mhz/antenna_cell_fixedgeom_rcx/` confirms the qualified
primitive geometry (area=4.347e11, perim=2.64e6). Its four resistors and
body/supply coupling capacitors must be retained in assembled simulation;
primitive model equivalence does not qualify the complete cell or PLL.
Corrected SS125 fine codes 100/101 average 446.470/446.643 MHz over 12--40 ns,
with 0.188/0.189 MHz half-window differences. The extra-drive transition
controlled by `DCO_THERM[104]` prevents interpolating through this interval
to code 110. Completed 25 ns screens at codes 104/105 measure
447.446724/453.044740 MHz in the runner window
(`c1load64_true_ss125_boost104105_v1`), confirming the drive transition near
450 MHz. The coarse-1/fine-247 upper endpoint measures 262.389571 MHz
(`c1load64_true_ss125_c1_high_v1`). These short screens do not establish
continuous 450 MHz coverage or a qualified calibration band at hot SS.
An upstream-Xyce/KLU endpoint campaign for the separate OSC8 fast core's
physical coarse bands 0/1 is running at SS/1.62 V/125 C in
`build/modern_25mhz/osc8_true_ss125_c01_endpoints_25ns_cap10ps/`.
It uses legal fine codes 8/247, a 25 ns transient, and a 10 ps maximum
timestep to determine whether an alternate measured band brackets 450 MHz.
It is a range screen; it does not establish a calibrated preset.
The completed OSC8 coarse-0 endpoints at the corrected hot SS operating
point average 477.066/590.150 MHz over 12--25 ns and do not bracket
450 MHz (`coarse0_endpoint_screen.json` in that campaign directory).
The same campaign's coarse-1 endpoints completed at 313.760/341.101 MHz
(`coarse1_endpoint_screen.json`), also without bracketing 450 MHz. The
sampled gap between the coarse-1 upper and coarse-0 lower endpoints is
135.965 MHz. These results motivate testing the loaded fast variant; they
do not exclude an unmeasured nonmonotonic interior code in either band.
The existing OSC8_LOAD24 physical coarse-0 variant is being screened with
the same corrected temperature and timestep in
`build/modern_25mhz/osc8_load24_true_ss125_c0_endpoints_25ns_cap10ps/`.
Historical LOAD24 measurements labeled 125 C below used the ignored
temperature directive and do not substitute for this rerun.
The corrected OSC8_LOAD24 endpoint campaign completed at 453.984/556.486
MHz over 12--25 ns, so it also does not bracket 450 MHz at hot SS.
An isolated OSC8_LOAD32 candidate adds eight fixed active loads while
retaining the 255 fine controls and external macro ports. Its source and
copied physical configuration are pinned in the candidate's `experiment.json`;
the initial experiment `pvt_probe_load32_hot450_v1` stopped at synthesis
because the new load indices exceeded the unchanged 24-bit dummy output
bus. The bus is now 32 bits, and `pvt_probe_load32_hot450_v2` is running.
The synthesized structural screen verifies all 32 fixed loads' input,
enable, and distinct output connections, and presence of all 255 fine
controls (`build/modern_25mhz/osc8_load32_synthesis_screen.json`).
Tuning frequency and release qualification remain unverified for LOAD32.
The v2 route subsequently completed and passes `check_librelane_signoff.py`
against current source/config with streamout/XOR skipped: zero-violation
metrics, 687 standard cells, utilization 0.546053, wirelength 11,066 um,
and 2,859 vias. All-net Magic extraction is running in
`build/modern_25mhz/v5_turn10_boost8_osc8_load32_all_net_rc/`.
These physical checks do not yet establish the candidate's tuning range
or assembled-PLL release qualification.
LOAD32 all-net extraction completed with 2,030/2,032 final reported nets
and 90,489 resistors; exact resistor-node elimination retains 78,473
resistors and all extracted capacitors. The initial 308-net resistance
pass is not the final all-net result. Corrected hot-SS coarse-0 fine codes
8/9/24/40/247 are now being measured in
`build/modern_25mhz/osc8_load32_true_ss125_c0_lowcodes_25ns_cap10ps/` to
check both endpoint range and the first switched-drive transition.
This short-window campaign cannot qualify a preset by itself.
Completed LOAD32 low-code samples at hot SS average 445.052938,
451.556164, and 454.807680 MHz for codes 8/9/24 over 12--25 ns.
The first switched-drive transition therefore jumps across 450 MHz;
endpoint bracketing alone would have hidden this issue.
The remaining LOAD32 samples completed at 458.299450 MHz for code 40 and
544.339827 MHz for code 247. All five finished waveforms and half-window
drifts are recorded in `completed_window_screen.json` in that campaign.
These samples support the downward-shift experiment without claiming
coverage of every unmeasured code. An isolated
OSC8_LOAD36 candidate adds four further fixed loads and expands the dummy
bus accordingly, preserving macro ports and the 255 fine controls.
`pvt_probe_load36_hot450_v1` is running to test a downward shift of the
switched segment. Its source provenance is recorded in `experiment.json`.
LOAD36 frequency qualification remains open.
Its synthesis screen verifies all 36 fixed loads' wiring, distinct outputs,
all 255 fine controls, and unchanged external port widths
(`build/modern_25mhz/osc8_load36_synthesis_screen.json`).
The completed LOAD36 route passes `check_librelane_signoff.py` against
current source/config with streamout/XOR skipped: zero-violation metrics,
691 standard cells, utilization 0.548361, wirelength 11,012 um, and 2,927
vias. Full all-net extraction is running in
`build/modern_25mhz/v5_turn10_boost8_osc8_load36_all_net_rc/` before any
frequency or assembled-PLL qualification claim.
LOAD36 extraction completed with 2,046/2,048 final reported nets and
90,642 resistors. Exact resistor-only reduction leaves 78,561 resistors,
retaining the extracted capacitors.
All 152 extraction-feedback locations associate with the 76 placed
boundary `decap_3` cells (two per cell); the mapping and DEF/feedback hashes
are recorded in `feedback_boundary_association.json` in the LOAD36 extraction
directory. This is spatial association, not a waiver or full-circuit
extraction qualification. Corrected hot-SS coarse-0 fine codes
9/16/24/32/247 are being measured in
`build/modern_25mhz/osc8_load36_true_ss125_c0_segment_25ns_cap10ps/`.
This is a short-window tuning search; no preset is qualified by it alone.
Completed LOAD36 hot-SS codes 9/24 average 448.208883/451.455044 MHz
over five periods in 12--25 ns. Both lie within the same switched-drive
segment (the next boost transition is at code 41), so these samples
provide a useful 450 MHz bracket without interpolating through a drive
switch. Interior behavior remains unmeasured. Adjacent codes 16/17/18
are running over 40 ns with a 10 ps cap in
`build/modern_25mhz/osc8_load36_true_ss125_c0_codes161718_40ns_cap10ps/`.
Frequency accuracy, local spacing, settling, and independent numerical
convergence must pass before any preset promotion.
The completed 25 ns code-16 sample averages 449.754505 MHz with
0.016464 MHz half-window drift. It meets the mode's frequency bound but
does not establish calibrated convergence. An independent explicit
reltol=1e-4, abstol=1e-7 40 ns run of codes 16/17/18 is running in
`osc8_load36_true_ss125_c0_codes161718_40ns_tol1e4_cap10ps` alongside the
default-tolerance baseline. Step and settling comparisons remain required.
The adjacent-code default-tolerance 40 ns campaign completed all three
simulations without runner failures. Full 12--40 ns averages for codes
16/17/18 are 449.767542/449.914990/450.193827 MHz over eleven periods.
Half-window differences are 0.023901/0.027262/0.027401 MHz; all three
meet both the 1000 ppm frequency bound and their baseline settling limits
(0.036862/0.036862/0.045000 MHz). Measurements and hashes are in
`baseline_measurements.json`, with local-spacing checks in
`baseline_assessment.json`. These are baseline screens only; independent
tolerance, timestep, and longer-settling comparisons remain mandatory.
The independent default-tolerance half-timestep comparison of codes
16/17/18 is running over the same 40 ns window with a 5 ps cap in
`osc8_load36_true_ss125_c0_codes161718_40ns_cap5ps`.
The half-timestep campaign completed without runner failures. Codes
16/17/18 average 449.789111/449.937051/450.215392 MHz over eleven
periods, with half-window differences of 0.024755/0.025538/0.027938 MHz.
Their differences from baseline are 0.021569/0.022061/0.021565 MHz,
below the current baseline local-spacing limits. The complete measurements
and hashes are in that campaign's `completed_measurements.json`.
The longer-settling comparison remains required before convergence acceptance.
The reltol=1e-4, abstol=1e-7 tolerance comparison has completed all three
40 ns waveforms. Codes 16/17/18 average
449.776926/449.924963/450.203309 MHz over eleven periods, differing from
baseline by 0.009384/0.009973/0.009483 MHz. Half-window differences are
0.024618/0.025735/0.027806 MHz. Both differences remain below the
baseline local-spacing limits, but the half-timestep and longer-settling
variants are still needed for full convergence qualification. Measurements,
deck hashes, and waveform hashes are in `tolerance_measurements.json`.
The longer-settling variant is running through 80 ns with measurement
starting at 24 ns, reltol=1e-4, abstol=1e-7, and a 5 ps timestep cap
for codes 16/17/18 in
`osc8_load36_true_ss125_c0_codes161718_80ns_tol1e4_cap5ps`.
It uses one simulation at a time to limit contention with the active
comparisons and retains a 21,600 s per-simulation limit. Qualification
requires complete waveforms and agreement across all four variants.
The 80 ns campaign has completed all three decks with matching completed
provenance hashes. Full 24--80 ns measurements average
449.816541/449.965798/450.246393 MHz for codes 16/17/18 across 24
periods each, with 0.019143/0.019976/0.021343 MHz half-window differences.
All three meet the 1000 ppm frequency bound, but the four-variant
frequency spreads are 0.048999/0.050808/0.052566 MHz, exceeding
local-spacing calibration limits of 0.037314/0.037314/0.045000 MHz.
None passes numerical convergence. The complete measurements, deck and
waveform hashes, and comparison are saved in `convergence_assessment.json`
in the 80 ns campaign directory. A default-tolerance 10 ps-cap comparison
with the same 24--80 ns measurement window is started in
`osc8_load36_true_ss125_c0_codes161718_80ns_cap10ps` to distinguish
measurement-window settling from tolerance and timestep sensitivity.
Its code-16 default-tolerance deck has now completed with a matching
completed-deck hash. The 24--80 ns waveform averages 449.794591 MHz
over 24 periods, with 0.018801 MHz half-window difference. Its
0.021950 MHz difference from the tighter-tolerance, 5 ps-cap result over
the same window (449.816541 MHz) is below the current 0.037314 MHz
local-spacing limit. `completed_code16_measurement.json` pins the deck
and waveform hashes. This single matched-window comparison does not
replace the required four independent convergence variants or settle
the earlier short/long-window failure. Code 17 has also completed with a
matching completed-deck hash: 449.943934 MHz over 24 periods, with a
0.019921 MHz half-window difference. Its same-window difference from the
tighter-tolerance, 5 ps-cap result (449.965798 MHz) is 0.021864 MHz,
also below the current 0.037314 MHz local-spacing limit. Its hashes and
measurement are in `completed_code17_measurement.json`. Code 18 has now
completed at 450.224519 MHz over 24 periods, with 0.021904 MHz half-window
difference and 0.021874 MHz same-window settings difference, below its
0.045000 MHz local limit. All three completed-deck hashes match. The
complete comparison and deck/waveform hashes are in
`matched_window_settings_assessment.json` in the default-tolerance 80 ns
directory. These matched-window comparisons do not qualify convergence.
Independent tolerance-only (reltol=1e-4, abstol=1e-7, 10 ps cap), step-only
(default tolerances, 5 ps cap), and longer-settling (160 ns, 48--160 ns
measurement, default tolerances, 10 ps cap) campaigns of codes 16/17/18
are now running in the corresponding `80ns_tol1e4_cap10ps`, `80ns_cap5ps`
and `160ns_cap10ps` directories. No interpolation or full-PVT qualification
is implied by the three adjacent-code comparisons.
No standalone preset or assembled-PLL release mode is promoted.

The five-point 25 ns LOAD36 campaign has now completed without runner
failures. Codes 32/247 average 453.157010/540.003326 MHz over five/six
periods, with half-window differences of 0.036121/0.428894 MHz.
`completed_segment_screen.json` records all five full-window measurements
and their waveform/deck hashes after checking completed provenance.
The high-code drift prevents treating this range screen as a calibrated
curve; the adjacent-code 40 ns convergence experiments remain required.
A corrected hot-SS 400 MHz range screen of the existing BOOST8_LOAD24
slow macro's coarse-0 band is running at fine codes 8/128/247 in
`build/modern_25mhz/boost8_load24_true_ss125_c0_400screen_25ns_cap10ps/`.
This examines another required release mode while the 450 MHz search runs;
it does not qualify band coverage or calibration by endpoint samples alone.
Completed code-8/128 waveforms average 381.476041/429.243224 MHz over
four periods each in 12--25 ns, with half-window differences of
0.011013/0.135544 MHz. Their completed deck hashes match the provenance
sidecars; waveform hashes and measurements are saved in
`completed_endpoint_screen.json` in that campaign directory. These samples
bracket 400 MHz but do not establish an attainable intermediate code.
Codes 40/41/64 are running in
`boost8_load24_true_ss125_c0_400segment_25ns_cap10ps` to measure the
code-41 switched-drive transition and the following segment directly.
The endpoint campaign completed all three simulations without runner
failures. Code 247 averages 476.102286 MHz over five periods, with
0.372357 MHz half-window drift; its completed provenance and hashes are
included in the same range-screen artifact. This does not qualify a
400 MHz preset or the full tuning curve.
The intermediate-code 25 ns campaign completed without runner failures.
Codes 40/41/64 average 393.926106/399.779162/404.602486 MHz over five
periods each, with half-window differences of 0.053415/0.056009/0.090089
MHz. Code 41 meets the 400 MHz frequency bound, but its drift exceeds
the 0.040 MHz absolute calibration limit before considering local spacing.
Hashes and measurements are in that campaign's
`completed_segment_screen.json`. Codes 41/42/43 are now running through
70 ns with a 10 ps cap and a 24 ns measurement start in
`boost8_load24_true_ss125_c0_codes414243_70ns_cap10ps` to measure local
spacing and later settling. No 400 MHz preset is qualified.
Completed 24--70 ns code-42/43 samples average 400.145578/400.298111
MHz over eighteen periods each. Their half-window differences of
0.047095/0.047928 MHz exceed the 0.040 MHz absolute calibration limit
and their measured quarter-spacing limit of 0.038133 MHz. Frequency
accuracy alone passes, while settling remains insufficient. Code 41 is
still running. Completed measurements and hashes are recorded in
`settling_measurements.json` in the 70 ns campaign directory.
The full 70 ns campaign subsequently completed without runner failures.
Code 41 averages 399.884525 MHz over eighteen periods, with
0.044901 MHz half-window drift, also exceeding the 0.040 MHz absolute
limit. All three pass frequency accuracy and fail baseline settling.
`completed_measurements.json` records the complete set and hashes.
A same-window comparison at reltol=1e-4, abstol=1e-7 is running in
`boost8_load24_true_ss125_c0_codes414243_70ns_tol1e4_cap10ps` to check
numerical sensitivity before attributing the remaining drift to the design.
The completed corrected FF/-40 C coarse-3/fine-80 40 ns run averages
450.461799 MHz over twelve periods, with a 0.010162 MHz half-window
difference. This is numerically steadier than the hot screens, but exceeds
the 450 MHz 1000 ppm frequency bound (450.450 MHz upper limit). Adjacent
codes 77--79 were measured with the same 10 ps timestep cap before selection.
The adjacent-code campaign completed all three 40 ns waveforms with zero
runner failures. Full 12--40 ns averages for codes 77/78/79 are
450.096999/450.264705/450.326863 MHz; all meet the 1000 ppm mode bound.
Their equal-period half-window differences are 0.095499/0.019843/0.051866
MHz. Code 78's smaller adjacent spacing (0.062158 MHz) makes its quarter-LSB
limit 0.015540 MHz; even that numerically steadiest candidate fails this
baseline settling screen. No preset is promoted.
The independent cold-FF codes 77--79 experiment with reltol=1e-5 and
abstol=1e-9 terminated at its 7,200 s per-simulation limit before reaching
40 ns. All three runner rows report timeout; their partial frequencies
are diagnostic only and cannot enter numerical qualification. The
completed default-tolerance measurements therefore still lack an accepted
tolerance comparison.
A separate 40 ns comparison at reltol=1e-4, abstol=1e-7, and the same
10 ps cap is running for codes 77--79 in
`c1load64_true_ffm40_c3_codes777879_40ns_tol1e4_cap10ps`, with a
14,400 s per-simulation limit. It tests sensitivity to a moderate tolerance
change; it does not replace the required convergence acceptance criteria.
The completed tolerance code-77 waveform averages 450.629112 MHz over
twelve periods in 12--40 ns, with 0.048782 MHz half-window drift. Its
0.532113 MHz difference from the default baseline exceeds the absolute
0.045 MHz calibration limit, and its frequency exceeds the mode's
450.450 MHz upper bound. This rejects the current baseline code-77
setting for numerical qualification. Codes 78/79 remain running;
measurements and hashes are in `tolerance_measurements.json`.
The completed tolerance code-78 waveform averages 450.767928 MHz,
with 0.016724 MHz half-window drift. Its 0.503223 MHz baseline difference
also fails numerical agreement and its frequency exceeds the mode bound.
Lower adjacent codes 73/74/75 are being measured at reltol=1e-4,
abstol=1e-7 over 40 ns with a 10 ps cap in
`c1load64_true_ffm40_c3_codes737475_40ns_tol1e4_cap10ps` to locate a
setting after the observed tolerance shift. This search does not waive
the required four-variant convergence checks.
The lower-code reltol=1e-4 campaign completed all three simulations with
matching completed-deck hashes. Codes 73/74/75 measure
450.119502/450.264252/450.373373 MHz over twelve periods in 12--40 ns
at corrected FF/1.98 V/-40 C. All meet the 1000 ppm frequency bound.
Half-window differences are 0.025087/0.027916/0.031942 MHz, compared
with local-spacing limits of 0.036187/0.027280/0.027280 MHz. Only code
73 passes this single-variant settling screen. `completed_measurements.json`
and `settling_assessment.json` in that campaign pin the waveforms/decks
and record the measurements and bounds. A separate reltol=1e-5,
abstol=1e-9 comparison of codes 73/74/75 is running over the same 40 ns
window and 10 ps cap with a 21,600 s per-simulation limit in
`c1load64_true_ffm40_c3_codes737475_40ns_tol1e5_cap10ps`. No cold-FF
preset has passed all four numerical variants or been promoted.
The reltol=1e-5 code-73 deck has now completed at 450.206840 MHz over
twelve periods, with 0.029647 MHz half-window difference. Its 0.087338 MHz
difference from the same-window reltol=1e-4 result exceeds even the
0.045000 MHz absolute calibration bound. Frequency targeting still passes,
but numerical agreement fails; codes 74/75 remain queued/running.
`completed_code73_measurement.json` pins the tighter deck and waveform.

The codes 77--79 tolerance campaign has completed without runner
failures. Code 79 averages 450.873390 MHz over twelve periods, with
0.027560 MHz half-window drift and a 0.546527 MHz baseline difference.
All three tighter-tolerance frequencies exceed the 450.450 MHz upper
bound and fail baseline agreement. The lower-code search remains active;
the complete failed comparison is retained with waveform/deck hashes.
The baseline measurements and per-code pass/fail bounds are recorded in
`baseline_measurements.json` and `baseline_assessment.json` in the completed
campaign directory, with measurement/specification hashes.
An explicit reltol=1e-5,
abstol=1e-9 rerun of these codes with the same 40 ns duration and 10 ps cap
is running in `c1load64_true_ffm40_c3_codes777879_40ns_tol1e5_cap10ps`.
The approved provisional criteria are in `engineering.json`. The configured
external PLL interface is to be preserved. This document separates implemented
infrastructure from verified design outcomes; the complete PLL is not signed off.
The 500 MHz measurements and preset artifacts below are historical. The approved
highest release mode changed to 450 MHz on 2026-09-30; no measured 450 MHz preset
has been promoted, and the modern release gate must reject the stale manifest.
The current 500 MHz TT preset uses coarse 0/code 163 and cannot be relabeled
450 MHz: its measured output is 500.707 MHz. The prior coarse-0/code-0
measurement is 448.563 MHz, but code 0 is outside the approved fine-code
range 8..247. The loaded fast-core FF coarse-4/coarse-3 endpoint gap
410.392--465.146 MHz contains 450 MHz. These are search results, not an
exclusion proof for all physical bands; the 450 MHz candidate needs a new
extracted band screen and calibration before preset promotion.
The user clarified the optimization policy on 2026-09-12: no power limit;
functional performance takes priority over area. Characterize physical jitter,
area and power, report the measured tradeoff frontier among functional candidates,
then set numerical jitter/area objectives. A finite candidate search does not
establish global Pareto optimality.

Candidate comparison must report total implemented PLL area (with macro area
separately identified), physical RMS jitter with its integration bounds and
measurement method, period/cycle-to-cycle variation, output load, operating mode,
PVT and measured power. Compare candidates under the same conditions; do not rank
different jitter bandwidths as equivalent measurements. Deterministic edge
variation alone cannot supply the physical-noise result. Application-specific
clock timing limits remain deferred until these functional tradeoffs are known.

## Development priority (updated 2026-09-28)

The user requested using the pinned upstream Xyce and removed the KLS requirement
on 2026-09-28. Numerical convergence and reproducible simulator provenance remain
qualification gates. Earlier KLS investigations remain diagnostic history.
A separate singleton-metadata defect has a
deterministic regression and fix; the historical segmentation fault remains
unresolved and is not currently reproducible on demand, including with saved
unfixed executables. Continue DCO compatibility, tuning coverage and acquisition
work. See the KLS
repository’s `docs/openpll-crash-investigation.md` for the evidence.

## Earlier strength-divider physical candidate and blockers

The experimental `IntegerPLL_DCO_STRENGTH_DIV` combines selectable parallel
inverter strength, 255 independent fine loads and /1, /2, /4, /8 output division.
The `candidate-strength-2` layout completed routing, Magic and KLayout DRC and
LVS with zero reported errors. Its 120 by 120 micrometre die is 14,400 square
micrometres; this is DCO macro area, not total PLL area. Reported maximum-slew
(449) and maximum-capacitance (192) violations remain unresolved, so this is not
timing signoff.

All-net extraction reports 2,241/2,241 nets and 54,675 resistors, reduced to
39,088 while retaining device and capacitor terminals. The initial SS fastest
and FF slowest KLS screens both fail during parsing: extracted antenna-diode
wrappers report no valid model for D0. Six extracted antenna diodes require
validated PDK/Xyce compatibility before these runs can establish frequency
coverage. The isolated DC/AC probe identifies a level-3 model unsupported by
Xyce’s standard diode; the large geometry values are intentional PDK scaling.
See `DIODE_COMPATIBILITY.md` for the retained-model probe and acceptance scope. No frequency or jitter claim is made from them.

The preceding four-driver candidate reached approximately 542 MHz at its slow
corner with coarse code 0 / fine code 8, but coarse code 1 / fine code 247 was
only approximately 293 MHz. This coarse gap prevents treating its fastest-band
result as proof of complete mode coverage. KLS refactor crashes also remain
unresolved; fresh numerical factorization is a diagnostic option, not an
established solver fix or a replacement performance benchmark.

## Implemented

- Independent trace acceptance: four final 5120 ns windows, 1000 ppm frequency,
  output-period-scaled phase mean/span/drift, cycle-slip and rail rejection,
  acquisition deadline measured from the stimulus. Missing evidence fails.
- Content hashes for simulation inputs, recursive PDK contents, solver binary,
  RTL, and numerical settings. Old cache entries without matching provenance
  are rerun. Failed runs cannot become successful cache hits.
- Explicit voltage/temperature controls in extracted DCO decks and measurements.
- Continuous-phase calibrated DCO in the RTL/Xyce bridge, preserving phase on
  tuning changes. Mode/PVT model metadata is checked before simulation.
  Historical 1 ps rounding is available only as an explicit diagnostic option
  in the Python runner (the low-level binary retains its compatibility default).
- Constant-resistor Schur reduction preserving device/capacitor terminals and
  ports. Independent complex-admittance tests cover DC through 1 THz. Nonlinear
  transient equivalence at converged tolerances still needs verification.
- Resumable band-screen and numerical-convergence campaign runner. Frequency
  uses the complete measurement window; truncated waveforms cannot pass.
- Separate synthesizable frequency-acquisition engine: Gray DCO counter into
  REFCLK, all-band midpoint scan, closest-three endpoint checks, seed
  interpolation for either fine polarity, doubled measurement on ambiguity,
  mode-change restart, frequency/rail monitoring, and retry after stopped-clock
  failure. RUN_FINE means handoff readiness, not phase lock.
- Experimental `IntegerPLL_AcquiringCore` connects that engine to the real DLF
  and divider. A single-outstanding bundled-data transfer holds each seed/mode/
  gain command until acknowledged after three destination clocks. Measurement
  waits for application; a stopped-clock acknowledgement times out and retries.
  Reset release and fine-loop release are synchronized into their clock domains.
  Coarse selection remains reference-owned so it can restart a stopped DCO.
- The mixed bridge accepts `--acquisition` with a complete 48-band JSON model,
  preserving oscillator phase across coarse changes. Replay checks REFCLK and
  coarse outputs as well as the existing fine-loop boundary. `--smoke-only`
  permits short infrastructure diagnostics but forces engineering acceptance false.

## Evidence recorded in the workspace

Artifacts are under `../build/openpll-verification/` relative to this repository.

- Initial resistance-enabled DCO: 106,848 resistors; BBPD: 74,726 resistors.
  Audit found that Magic's default threshold extracted only 308 of 1,300 DCO
  nets (mostly external nets). These are not yet verified all-net RC models.
  `magic_full_rcx.py` explicitly runs `extresist all` with simplification off;
  replacement models are under `all-net-rc/DCO-v3` and `all-net-rc/BBPD-magic`.
  DCO extraction now reports 1,298/1,300 nets and 132,239 resistors (59,780 after
  exact resistor reduction); BBPD reports 56/58 nets and 75,077 resistors.
  Body-bias nets have zero lumped route resistance; the remaining-net accounting
  still needs to be included in extraction qualification.
  DCO source SHA256:
  `d16164da76ffa408a0008bff96a82472c879a0b0d9639b53c60c3dee76e132b5`.
  BBPD source SHA256:
  `c7332d9731980be69e587f386700f469cd793f14e08f63a63451a6f7b7535511`.
- Degree-eight DCO reduction: 42,613 resistors, 50,832 eliminated internal nodes.
  The 40 ns TT/1.8 V/27 C C17/code235 KLS pilot completed, reporting about
  88.3127 MHz from the existing short measurement. This is a startup screen,
  not a converged calibration. The older capacitance-only ~100 MHz preset is
  therefore not suitable for promotion based on the current evidence.
- Unreduced and degree-three reduced KLS pilots crashed. Stack traces point to
  BSIM4 Jacobian loading and KLU transpose solve called through KLS respectively.
  Root cause remains under investigation; solver memory instrumentation and an
  unreduced KLU control run are used diagnostically. KLS was the former baseline.
  The KLU control reached 40.056 ns without a crash and was deliberately stopped;
  its partial waveform is not calibration evidence.
  A KLS AddressSanitizer/UndefinedBehaviorSanitizer build completed the reduced
  40 ns deck without an error report. This does not resolve the intermittent
  optimized-build crashes. Reproduction provenance is retained in
  `crash-diagnostic/asan-provenance.json`.
- A separate 60 ns KLS run at SS/1.62 V/125 C, C0/code255 completed. Across nine
  periods after 20 ns it measured 233.14094 MHz; the two half-window estimates
  differed by 7.68 Hz. Timestep/tolerance convergence has not yet been established.
  This setting is intended to be the fastest (shortest mirror path, no enabled
  fine loads), so the 500 MHz PVT requirement is a serious DCO redesign gate.
  Do not treat this one setting as a completed all-band coverage sweep.
- Continuous-phase 2 us RTL/Xyce smoke completed; 503 boundary evaluations
  matched independent Icarus replay. It correctly fails engineering acceptance
  for insufficient observation time and uses an unqualified capacitance model.
  A second 2 us smoke loaded an explicit JSON calibration at 3 ns reference
  offset; all 483 recorded boundary evaluations matched replay.
- Nine trace/provenance, three numerical-calibration, three resistor
  reduction, and five parallel-driver validation tests pass. The C++ oscillator test passes with assertions active
  in Release builds. Existing four configured PLL regressions pass.
- Standalone acquisition simulation covers all five modes, nonmonotonic band
  ordering, reverse fine polarity, misleading closest-band rejection, invalid
  mode, mode changes, frequency/rail loss, stopped oscillator and automatic
  recovery, with oscillator offsets 0/7/10/20/30 ns. Synthetic handoff is about
  80 us normally and 111 us with a rejected candidate; this excludes subsequent
  BBPD settling and is not a lock-time result.
  Yosys process/check and Verilator lint were run on the standalone module.
- Integrated acquisition tests pass at all five offsets, with about 86 us normal
  handoff and 119 us for the rejected-candidate case. They exercise the real DLF
  seed loading, mode changes, invalid mode, disable, stopped-clock recovery and
  reset during a command transfer. These synthetic-clock results exclude BBPD
  settling. Integrated Verilator lint and Yosys process/check also pass; physical
  CDC constraints and timing are still required.
- The acquisition valid-mode check now accepts divider 18 for the approved
  450 MHz mode and rejects the retired divider 20. Standalone and integrated
  synthetic acquisition tests pass at all five phase offsets with the 450 MHz
  behavioral band and an explicit retired-divider rejection. This does not
  establish extracted-DCO acquisition or phase lock.
- A 2 us KLS/BBPD/48-band synthetic-model bridge smoke completed; all 1,763
  boundary evaluations matched independent Icarus replay. It does not reach
  tracking and correctly reports engineering acceptance false. The historical
  nine-column 503-evaluation replay still passes after the bridge extension.

## Experimental DCO redesign

`sky130/IntegerPLL_DCO_einvp_coarse_v2_sky130.v` and its matching OpenLane
configuration are experimental. They retain all external macro ports, replace
NAND fine loads with enabled-inverter loads, parallel three shortest-path
drivers, reduce the die to 140 x 140 um, and distribute controls across four
sides. Production source and preset tables have not been replaced.

V2 completed layout with zero routing/Magic/KLayout DRC and LVS errors. Its
all-net extraction has 1,812/1,814 nets and 92,801 resistors (72,035 after exact
reduction). SS/1.62 V/125 C C0/code247 completed 30 ns, with an initial two-period
estimate of 306.66 MHz. Code8 crashed in KLS mapped refactor at about 12.19 ns.

V3 (`IntegerPLL_DCO_einvp_coarse_v3_sky130.v`) uses four parallel copies of each
of the three critical drivers and 128 physical fine loads on even thermometer
bits. Paired external codes alias, so effective resolution must be characterized
explicitly; the existing adjacent-code convergence checker must not be bypassed.
V3 also has zero routing/Magic/KLayout DRC and LVS errors. Both candidates have
19,600 um^2 DCO die area; this is not total PLL area. V3 all-net extraction has
1,312/1,314 nets and 88,476 resistors (70,934 after exact reduction).
Its SS code247 SERIAL-backend run crashed at about 22.39 ns; the partial waveform
suggests approximately 603 MHz, but cannot establish tuning coverage or convergence.
SERIAL selects a different factor policy but still reaches KLS mapped refactor.
A fresh-factor diagnostic (`KLS_REFACTOR=0`, exposed by `--kls-fresh-factor`) is
being evaluated. Default refactor behavior is preserved; the defect is not fixed.
Both one-rank and four-rank adapter regressions pass with refactor on and off.
The instrumented V2/code8 rerun completed 30 ns without an ASAN/UBSAN report;
its four-period mean is 248.98485 MHz. This does not explain the optimized crash.
A separately fingerprinted `-fno-strict-aliasing` build is another compiler
diagnostic, not an adopted fix or a performance comparison.

V4 (`sky130/IntegerPLL_DCO_einvp_coarse_v4_sky130.v`) is an isolated follow-up
to V3. It retains four parallel shortest-path drivers but restores one
`einvp_1` fine load for every one of the 255 thermometer bits. The
`pvt_probe` LibreLane run on Ciel pin
`1689ac3f2dc763876eaf967227c7dfe831b031ae` completed routing and its
standalone checker reports zero DRC/LVS violations. The narrow structural
checker verified the three intentional parallel-driver groups and 255 distinct
fine-load enables. This is experimental layout evidence, not PLL signoff.

Extracted Xyce measurements at SS/1.60 V/100 C reveal a large adjacent-band
gap. They used the V4 `pvt_probe` Magic RCX netlist, a 70 ns transient and a
12 ns measurement start unless noted.

| Coarse | Fine | Frequency (MHz) |
| ---: | ---: | ---: |
| 0 | 8 | 572.666 |
| 0 | 128 | 634.122 |
| 0 | 247 | 702.659 |
| 0 | 255 | 708.745 |
| 1 | 8 | 302.345 |
| 1 | 247 | 338.334 |
| 32 | 8 | 28.941 |

The coarse 0 lower endpoint is above 500 MHz while the adjacent coarse 1
upper endpoint is below it. V4 therefore does not supply a calibrated 500 MHz
setting in these measured bands. An all-band screen is still required before
asserting that no nonmonotonic band reaches 500 MHz. V4 is not promoted into
the configured wrapper or release audit. Increasing maximum speed alone did
not close the coarse-band coverage gap.

V5 strengthens the coarse-1 path while retaining 255 independent fine controls.
Its `pvt_probe_waived` layout passed the narrow parallel-driver structural
check and the standalone LibreLane physical checker. V6 adds 128 balanced
supplemental enabled-inverter loads, with the same 255 distinct controls; its
`pvt_probe_extra128` layout also passed those checks. Extracted Xyce 70 ns
endpoint screens at SS/1.60 V/100 C, measured after 12 ns, are:

| Candidate | Coarse 0, fine 8 | Coarse 0, fine 247 | Coarse 1, fine 8 | Coarse 1, fine 247 |
| --- | ---: | ---: | ---: | ---: |
| V5 (MHz) | 557.792 | 682.037 | 363.338 | 411.515 |
| V6 (MHz) | 426.931 | 541.126 | 304.657 | 356.651 |

V5 leaves 500 MHz between the measured adjacent bands. V6 brackets 500 MHz
in coarse 0, but leaves 400 MHz between these bands. Neither is a full-band
screen or a calibrated PVT pass. These early-period estimates can differ
materially from full-window averages; several traces drift across the 70 ns
window. Source, layouts and measurement artifacts are
under `sky130/`, `openlane/` and `build/modern_25mhz/v{5,6}_pvt_ss_100c_1p6v_bandgap/`.

V7 adds 160 balanced supplemental loads. The `pvt_probe_extra160` layout
passes the structural check, but slow-corner physical reports show 217 maximum
slew and four maximum capacitance violations on the oscillator node. Every
reported violating sink shares its 1.57167 ns transition against a 1.5 ns
limit; each of the four parallel `osc_gate` outputs sees 0.628646 pF against a
0.599680 pF limit. V7 cannot be promoted. The standalone signoff checker
previously read only zero-valued aggregate metrics and falsely passed this
layout. It now checks every reported corner-specific zero-violation metric;
regression coverage verifies that a nonzero corner rejects signoff.

An extracted V6 FF/1.95 V/-40 C endpoint screen used the same RCX layout and
70 ns/12 ns measurement settings. Coarse 0/fine 247 completed at 1985.237 MHz;
coarse 1/fine 8 and 247 completed at 1046.678 and 1252.705 MHz. Coarse 0/fine
8 reached about 68 ns and its partial waveform estimated 1525.979 MHz, but
the 1800 s simulation timeout makes that row a failure. These two shortest
bands are far above 500 MHz at FF. No claim about the remaining 46 bands or
target reachability follows from this screen. Results and row statuses are in
`build/modern_25mhz/v6_pvt_ff_n40c_1p95v_bandgap/dco_postlayout_results.csv`.
The extracted 70 ns V7 endpoints measured over the full 12--70 ns window are
408.844--524.415 MHz for coarse 0 and 295.427--348.994 MHz for coarse 1
(fine 8--247). They bracket 500 MHz in coarse 0 but leave a 349--409 MHz
adjacent-band gap containing 400 MHz. The timing violations reject V7
independently of frequency. Half-window differences reach 0.804 MHz, so these
rows do not establish numerical convergence.

V8 retains V6's 128 supplemental loads and doubles the coarse-1 path from four
to eight parallel copies at each of its forward, turn, merge and return cells.
Its synthesized netlist passes the narrow structural check, but the
`pvt_probe_coarse1x8` layout has 205 slow-corner maximum-slew violations and
four maximum-capacitance violations; the oscillator node reaches 0.659 pF
against the 0.600 pF cell limit. DRC and LVS report zero errors. Adding copies
to this path worsens the oscillator-node load and does not clear physical
signoff. V8 remains an experimental failed candidate.

V9 retains V6's four coarse-1 forward drivers and increases only its turn,
merge and return groups to eight drivers. Its `pvt_probe_latepathx8` layout
passes the narrow structural check and the standalone LibreLane checker with
zero DRC, LVS, maximum-slew and maximum-capacitance violations at reported
corners. This is DCO layout evidence only. Extracted frequency screening is
required before it can address the 400 MHz gap. The extracted SS/1.60 V/100 C
coarse-1/fine-247 70 ns run gives 358.066 MHz by the early-period screen and
359.099 MHz over the 12--70 ns window (0.533 MHz half-window difference).
Strengthening those later stages therefore does not bring this adjacent band
to 400 MHz. V9 is not a qualified replacement.

The separate `IntegerPLL_DCO_EINVP_COARSE_TURN32` experiment retains V6's
oscillator and return-node loads and adds 32 fine-controlled loads on the
coarse-0 turn node. Its synthesized structure has 255 independent base fine
controls, 128 V6 supplemental loads and 32 turn-node loads. The
`pvt_probe_turn32` layout passes the standalone physical checker with zero
reported DRC, LVS, maximum-slew and maximum-capacitance violations. Extracted
SS/1.60 V/100 C coarse-0 fine-8/247 endpoints measure 354.905/460.326 MHz
over the full 12--70 ns window. TURN32 therefore brackets 400 MHz at this
corner, while its high endpoint falls below 500 MHz. The fine-247 half-window
difference is 0.781 MHz, so numerical convergence remains unproven. V6's
coarse-0 band brackets 500 MHz, but the two physical tuning ranges are not yet
selectable within one qualified DCO macro.

V10 instead adds 32 return-node supplemental fine loads while retaining V6's
oscillator-node loading. Its synthesized structure passes the narrow driver
and fine-load checker, but `pvt_probe_return160` has 227 maximum-slew and four
maximum-capacitance violations at SS/1.60 V/100 C. The return node reaches
0.626873 pF against a 0.599680 pF cell limit, with a 1.550049 ns transition
against 1.5 ns. V10 therefore fails physical signoff before frequency
screening.

`IntegerPLL_DCO_EINVP_COARSE_TURN14` reduces the turn-node additions from 32
to 14, spaced across distinct fine controls. Its `pvt_probe_turn14` layout
and narrow structural checker pass: 255 independent base fine controls, 128
V6 supplemental loads, 14 turn-node loads, and zero reported DRC, LVS, slew
and capacitance violations at the checked physical corners. Extracted
SS/1.60 V/100 C coarse-0 fine-8/247 endpoints measure 370.805/473.570 MHz
over the full 12--70 ns window. This brackets 400 MHz but misses 500 MHz;
the fine-247 half-window difference is 0.708 MHz. Full PVT and numerical
convergence remain open.

`IntegerPLL_DCO_EINVP_COARSE_TURN7_SPACED` uses seven spaced turn-node fine
loads. Its `pvt_probe_turn7` layout and narrow structural checker pass with
zero reported DRC, LVS, slew and capacitance violations at the checked
corners. Extracted SS/1.60 V/100 C coarse-0 fine-8/247 endpoints measure
394.200/502.870 MHz over the full 12--70 ns window, so this experimental
band brackets both 400 and 500 MHz there. The high endpoint's half-window
difference is 0.902 MHz; numerical convergence and target fine-code settings
remain unproved. The approved SS/1.62 V/125 C endpoint check completed with
full-window coarse-0 fine-8/247 frequencies of
409.274/522.706 MHz. Its coarse-0 lower endpoint is above 400 MHz, so this
band does not cover 400 MHz at the approved point. The fine-247 half-window
difference is 0.805 MHz. A separate ten-load turn-node candidate is being
screened to move the lower endpoint while retaining the 500 MHz upper endpoint.

The separate `IntegerPLL_DCO_EINVP_COARSE_TURN10_SPACED` candidate adds ten
spaced turn-node loads to V6. Its `pvt_probe_turn10` layout passes the narrow
structural and standalone physical checks with zero reported DRC, LVS, slew
and capacitance violations. Extracted SS/1.62 V/125 C coarse-0 fine-8/247
endpoints measure 392.688/501.063 MHz over the 12--70 ns window. This
brackets both 400 and 500 MHz at that one point, but leaves only 1.063 MHz
upper margin, with a 0.951 MHz high-endpoint half-window difference.
Numerical convergence, target code selection and the remaining PVT points
are unproved. A nine-load candidate is being screened for more margin.

`IntegerPLL_DCO_EINVP_COARSE_TURN9_SPACED` uses nine spaced turn-node loads.
Its `pvt_probe_turn9` routed layout passes the narrow structural and standalone
physical checks with zero reported DRC, LVS, slew and capacitance violations.
Extracted SS/1.62 V/125 C coarse-0 fine-8/247 endpoints measure
401.754/513.986 MHz over the 12--70 ns window. The lower endpoint misses
400 MHz by 1.754 MHz while the upper endpoint has 13.986 MHz of margin;
the high trace's half-window difference is 0.983 MHz. A separate fixed
turn-node trim load is being tested to shift this band slightly downward.

`IntegerPLL_DCO_EINVP_COARSE_TURN9_TRIM` retains TURN9's nine controlled
turn-node loads and adds one fixed enabled-inverter input load. Its
`pvt_probe_turn9trim` layout and narrow structural check pass with zero
reported DRC, LVS, slew and capacitance violations. An extracted lower
endpoint run at SS/1.62 V/125 C measured 396.934 MHz over the full 12--70 ns
window, with a 0.043 MHz half-window difference. Fine 247 measures
506.963 MHz, so this coarse-0 band brackets both 400 and 500 MHz at the
approved point. The upper endpoint has a 0.835 MHz half-window difference;
neither numerical convergence nor actual target presets are established.
Midpoint and adjacent target-code baseline runs have completed.
The midpoint measures 446.715 MHz. At the approved SS point, full-window
local codes 15/16 measure 400.126/400.295 MHz, and codes 234/235 measure
499.859/500.347 MHz. These baseline decks printed at 10 ps but did not cap
Xyce's internal timestep; their default relative tolerance was 1e-3.
Codes 15/16 have 0.168 MHz adjacent spacing, giving a 0.040 MHz convergence
limit after the 100 ppm cap. Codes 234/235 have 0.488 MHz spacing, giving a
0.050 MHz limit. Their baseline half-window differences are about
0.033/0.029 MHz and 0.500/0.672 MHz respectively. An upstream-Xyce code-235
diagnostic with 5 ps maximum internal step, relative tolerance 1e-5 and
absolute tolerance 1e-15 completed. Its full 12--70 ns window measures
500.159 MHz versus 500.347 MHz in the original run: the 0.188 MHz spread
exceeds the 0.050 MHz local limit. Its half-window difference is 0.810 MHz.
The simulator's CSV reports a different trailing-window frequency; these
calibration figures use the full window required by `dco_calibration.py`.
The matching code-15 diagnostic measures 400.138 MHz versus 400.126 MHz in
the original run (0.011 MHz spread), with a 0.033 MHz half-window difference;
those two comparisons fall within its 0.040 MHz local limit. This does not
replace independent half-step and longer-settling variants.
No numerical calibration is accepted.
These exploratory direct Xyce runs used four MPI ranks and the default solver.
Explicit-KLS reruns of codes 15 and 235 stopped before
transient simulation: the pinned `openpll-release-modern.sif` image's upstream
Xyce reports `Unknown or Unavailable Linear Solver: KLS`. This agrees with the
image definition, which states that the experimental KLS solver is absent.
The approved campaign now uses the pinned upstream Xyce without a KLS probe.
The earlier rows have acceptable simulator provenance, but still do not qualify
because numerical convergence and full calibration variants are missing.

At TT/1.80 V/27 C, additional upstream-Xyce extracted screens of TURN9_TRIM
completed over 12--70 ns. Coarse 0/fine 8 is 824.766 MHz and coarse 1/fine
247 is 776.925 MHz; neither is the nominal 500 MHz band. Coarse 2/fine
8--247 spans 448.654--504.225 MHz, bracketing 500 MHz. Coarse 3/fine
8--247 spans 369.734--406.339 MHz, bracketing 400 MHz. Their half-window
differences range from 0.045 to 0.158 MHz on these two bands; calibration
convergence remains unproved. At TT coarse 2, fine 230 gives 499.701 MHz,
within the 500 MHz 1000 ppm frequency bound, but its 0.103 MHz half-window
difference exceeds the 0.050 MHz 100 ppm calibration cap. Fine 235 gives
501.237 MHz with 0.720 MHz half-window difference. At TT coarse 3, fine
198 gives 399.346 MHz and fine 210 gives 401.565 MHz; neither is within the
400 MHz 1000 ppm bound. Coarse-2/fine-231 measures 500.281 MHz, within the
500 MHz 1000 ppm bound, but its 0.710 MHz half-window difference fails the
0.050 MHz 100 ppm cap. Coarse-3/fine-201 measures 399.258 MHz, slightly
*below* fine-198's 399.346 MHz, with 0.109 MHz half-window difference.
This short-window numerical screen cannot establish local monotonicity or a
400 MHz preset. These baseline rows cannot qualify presets.

At the approved FF/1.98 V/-40 C point, upstream-Xyce extracted TURN9_TRIM
coarse-4 fine-8/247 endpoints measure 508.901/553.145 MHz over the full
12--70 ns window; coarse 5 measures 441.583/474.831 MHz. These adjacent
measured bands leave 500 MHz in a 474.831--508.901 MHz gap. The high endpoint
of coarse 5 differs by 0.637 MHz between half-windows, so these are screening
results, not converged calibration. A separate C4X2 experiment adds two fixed
loads to the coarse-4 turn node and passes the narrow structural and
standalone physical checks with zero reported DRC, LVS, slew and capacitance
violations. Its extracted FF coarse-4 endpoints are 505.718/549.067 MHz,
so 500 MHz remains below the measured band. Its SS coarse-0 endpoints are
398.463/508.982 MHz, spanning 400 and 500 MHz, but the high endpoint has
0.811 MHz half-window drift. These short screens do not qualify presets.
A C4X7 experiment with seven fixed coarse-4 turn-node loads completed the
standalone physical flow with zero reported DRC, LVS, slew and capacitance
violations. Magic capacitance RCX completed; these screens omit routed wire
resistance. A standard resistance RCX extracted only 308/2,420 reported nets;
the explicit all-net extraction with resistor pruning disabled reports
2,418/2,420 nets and 102,719 resistors. Exact constant-resistor reduction
leaves 90,210 resistors. The extraction summary marks this model unqualified.
Magic also reports
172 `device missing 1 terminal` feedback items, each connecting the remainder
to a supply node. Their boxes align with the 86 left/right `decap_3` edge
instances in the final DEF, two warnings per instance. This localizes the
warning source; the pinned PDK's `decap_3` SPICE subcircuit contains two MOS
capacitors with source/drain tied to supply rails. LVS passes; these warnings
are localized but the model still needs electrical qualification.
The pinned upstream Xyce guide documents AztecOO as the parallel default
for systems above 10,000 unknowns and supports explicit KLU. A four-rank
default-solver all-net FF trial emitted no transient waveform in 42 minutes;
it was intentionally terminated to free resources, so its failed CSV row is
not a natural timeout. A separate one-rank upstream-KLU trial on the same
reduced RC model completed. Its all-net FF coarse-4/fine-33 trial
measures 339.177 MHz over 12--70 ns with 0.019 MHz half-window difference,
versus 499.520 MHz in the capacitance-only model. The completed all-net
SS/1.62 V/125 C coarse-0/fine-247 run measures 318.235 MHz over
12--70 ns, versus 509.767 MHz in the capacitance-only extraction; its
half-window difference is 0.403 MHz. This measured fastest setting cannot
meet 500 MHz at the approved slow point. The result does not replace an
all-band screen, but it invalidates promotion based on the capacitance-only
coarse-0 coverage result and requires a faster architecture or a validated
alternative layout.
The physically checked, lighter V5 layout was extracted with the same all-net
method: 1,838/1,840 nets and 96,285 resistors (84,322 after exact reduction).
Its existing `pvt_probe_waived` standalone LibreLane checker still reports
zero DRC, LVS, slew and capacitance violations.
An upstream-KLU SS/1.62 V/125 C coarse-0/fine-247 all-net run measures
466.705 MHz over 12--70 ns, 33.295 MHz below 500 MHz, with 0.578 MHz
half-window drift. This V5 layout is faster than C4X7 at the same point but
still misses the mode. A compact V5 placement experiment uses a 125 by 125
micrometre die and 105 by 105 micrometre core (versus 140/120 micrometres)
with the same cells and controls. Its standalone checker passes with zero
reported DRC, LVS, slew and capacitance violations; routed wirelength is
10,015 um versus 10,235 um in the original V5 run. Its all-net extraction
reports 1,838/1,840 nets and 85,932 resistors (76,686 after exact reduction),
versus 96,285 original-layout resistors. An approved SS frequency check is
complete: coarse-0/fine-247 measures 478.309 MHz over 12--70 ns, an 11.605 MHz
gain over the original V5 layout but still 21.691 MHz below 500 MHz. Its
half-window difference is 0.481 MHz, so it is not numerically qualified. The
compact synthesis also passes the narrow structural check: seven intentional
parallel-driver groups and 255 independent fine loads.
A separate V5_TURN6 candidate adds two matched coarse-0 turn drivers to the
compact layout to address the remaining slow-corner speed gap. Its standalone
physical checker reports zero DRC, LVS, slew and capacitance violations;
the narrow structural check finds six intentional turn drivers and 255
independent fine loads. Its explicit all-net extraction reports 1,842/1,844
nets and 86,269 resistors (77,148 after exact reduction). A one-rank upstream
Xyce all-net SS/1.62 V/125 C coarse-0/fine-247 trial remained CPU-active for
about 55 minutes and produced no waveform or result CSV before its process
ended with the interrupted polling session. This is no frequency measurement;
the six-driver candidate is not qualified.
`scripts/run_v5_turn6_external_diagnostic.sh` preserves a bounded upstream-Xyce
25 ns KLU screen for an environment where Apptainer and MPI sockets work. It
completed at 488.433 MHz over 12--25 ns (five periods), 10.634 MHz faster than
compact V5 over that same window. The subsequent explicit-KLU all-net
SS/1.62 V/125 C 12--70 ns run completed at 489.131 MHz with 0.455 MHz
half-window difference. It remains 10.869 MHz below the required 500 MHz
mode and is not numerically qualified. A 110 by 110 micrometre die with a
90 by 90 micrometre core was routed as a tighter placement of this circuit.
Its standalone checker passes with zero reported DRC, LVS, slew and
capacitance violations. The cell utilization rises to 0.685, while total
wirelength increases from 9,981 to 10,652 um. Explicit all-net Magic
extraction reports 1,842/1,844 nets and 77,015 resistors (70,204 after exact
reduction); the extraction summary still marks it unqualified. Its extracted
slow-corner frequency measures 484.890 MHz over 12--25 ns, 3.543 MHz below the prior 125 by 125 micrometre layout over the same window. The tighter placement is therefore not the current speed candidate. A ten-driver coarse-0 turn variant is being screened separately.
A V5_TURN10 candidate adds four more matched coarse-0 turn drivers to the
125 by 125 micrometre V5_TURN6 layout. The standalone physical checker reports
zero DRC, LVS, slew and capacitance violations; synthesis confirms ten
identical turn drivers and 255 independent fine loads. Explicit all-net Magic
extraction outputs 1,850/1,852 nets and 86,937 resistors (77,520 after exact
reduction). Upstream Xyce with KLU measures 505.873 MHz at SS/1.62 V/125 C,
coarse-0/fine-247 over 12--25 ns, 17.439 MHz faster than V5_TURN6 over the
same window. A 12--70 ns run measures 506.741 MHz with 0.820 MHz half-window
difference, so it remains numerically unqualified. Fine code 235 measures
501.817 MHz over 12--25 ns with 0.412 MHz half-window difference. Code 230
measures 499.957 MHz over the same window, within the 500 MHz 1000 ppm
frequency bound, but its 0.487 MHz half-window difference fails numerical
calibration. The 12--70 ns code-230 run measures 500.605 MHz, outside the
1000 ppm bound by 0.105 MHz, with a 0.589 MHz half-window difference. Its
40--70 ns segment still differs by 0.098 MHz between halves, above the
100 ppm numerical threshold. These endpoint screens
establish a nearby 500 MHz tuning region but do not yet
qualify the 500 MHz mode or the PVT matrix.
Code 228 measures 500.448 MHz over 12--70 ns, inside the 1000 ppm frequency
bound by only 0.052 MHz, but its half-window difference is 0.857 MHz; its
40--70 ns segment still differs by 0.155 MHz. Thus a measured full-window
frequency hit does not resolve numerical settling or calibration.
An upstream-Xyce FF/1.98 V/-40 C coarse-4/fine-32 25 ns screen of V5_TURN10
timed out after 900 s at 24.3 ns. The partial 12--24 ns waveform measures
387.962 MHz over only three periods; it is a diagnostic, not a completed
corner result. This confirms that the fast-corner target search must use
different codes and a sufficient solver budget.
A completed FF/1.98 V/-40 C coarse-0/fine-247 12--25 ns endpoint screen
measures 1,630.428 MHz (20 periods) with 1.111 MHz half-window difference.
It shows ample fast-corner maximum range but does not identify or qualify a
500 MHz coarse/fine setting at that corner.

Follow-up SS/1.62 V/125 C tests isolated the enabled-inverter fine load's
long settling. V5_TURN10 code 228 measures 499.352 MHz with 0.674 MHz
half-window difference over 12--25 ns. A separate 10 ps maximum-step,
1e-5-relative-tolerance run measures 499.459 MHz with 0.395 MHz difference
over that same window. The original-tolerance 100--180 ns continuation
measures 501.333 MHz with 0.113 MHz half-window difference; its 140--180 ns
segment measures 501.391 MHz with 0.045 MHz difference. The shorter early
window is therefore both unsettled and sensitive to numerical settings.

Three isolated, physically clean fine-load alternatives were extracted with
all-net Magic RC. V5_TURN10_NANDLOAD uses always-driven NAND2 cells; its
coarse-0/fine-228 SS result is 470.272 MHz over 12--70 ns with 0.050 MHz
half-window difference, and 470.247 MHz over 40--70 ns with less than
0.0001 MHz difference. Its fastest legal fine code 247 reaches only
473.105 MHz over 12--25 ns. Eight extra turn drivers in
V5_TURN18_NANDLOAD reduce that endpoint to 465.516 MHz, so the longer run
was stopped. V5_TURN10_MUXLOAD uses a driven mux output and reaches
439.479 MHz at code 247 over 12--25 ns. V5_TURN10_KEEPER adds complementary
weak enabled-inverter drivers to hold every disabled fine-load output low;
the 255 pairs pass a narrow structural check, but code 247 reaches only
430.430 MHz over 12--25 ns. These variants improve settling or remove
floating outputs at the cost of too much speed. None is promoted.
An isolated V5_TURN10_BOOST8 layout adds eight fine-code-controlled turn
drivers to widen the coarse-0 tuning band. Its all-net extracted
SS/1.62 V/125 C coarse-0 endpoints measure 382.975 MHz at fine code 8
and 482.547 MHz at code 247 over 12--25 ns. The band reaches the 400 MHz
region but its fastest legal code still misses 500 MHz by 17.453 MHz.
The stronger V5_TURN10_BOOST8X8 variant completed physical and extracted
endpoint evaluation. Its physical signoff reports 151 maximum-slew and
four maximum-capacitance violations at the slow timing corner, concentrated
on the oscillator node. Its all-net extracted SS/1.62 V/125 C coarse-0
endpoints are 358.815 and 473.462 MHz over 12--25 ns. Stronger switched
drivers lower both endpoints further, so neither variant is promoted.
The original V5_TURN10 all-net model at SS/1.62 V/125 C, coarse 0/fine 224,
measures 499.656 MHz over 100--180 ns and 499.713 MHz over 140--180 ns;
the latter half-window difference is 0.044 MHz. This identifies a late
500 MHz setting but does not establish the required acquisition or sustained
window evidence. An isolated V5_TURN10_DUALBAND variant maps coarse code 0
to an unboosted path and code 1 to a separately switched lower band. Its
701-cell layout passes the standalone physical checker, but two antenna
diodes on static coarse-control nets invoke the pinned PDK's unsupported
level-3 diode model in upstream Xyce. A diagnostic with exactly those two
diode instances omitted measures code-0/fine-247 at 440.811 MHz and code-1
fine-8/247 at 379.892/478.604 MHz over 12--25 ns, all at SS/1.62 V/125 C.
The diagnostic cannot qualify release evidence, and the fastest path is far
below 500 MHz. This dual-band layout is not promoted.
The follow-up V5_TURN10_DUALCORE keeps V5_TURN10 and BOOST8 as separate
oscillators, selecting the BOOST8 output only for coarse code 1 and remapping
that core's first coarse bit to zero. Its isolated 1,329-cell routed layout
passes the standalone physical checker with zero reported DRC, LVS, slew and
capacitance violations. A dedicated synthesis check confirms both independent
255-load banks, the two-core output mux and the coarse selector. The flow
allows netlist `assign` aliases at the flattened module boundaries; the
structural check verifies their endpoint wiring. Explicit all-net Magic RCX
completed with 3,455/3,459 nets and 186,584 resistors, reduced exactly to
165,213. No antenna diode instance appears in the extracted netlist. A
12--25 ns all-net SS/1.62 V/125 C endpoint screen measures the selected fast
coarse-0/fine-247 path at 459.687 MHz; the selected lower coarse-1 fine-8/247
endpoints are 360.825/443.854 MHz. Both lower-band endpoints differ by about
5.9 MHz between half-windows. The monolithic placement spreads some fine
loads more than 100 um from their core oscillator gate, adding routing RC;
this implementation cannot be promoted. A hard-macro assembly retaining the
two standalone core layouts completed routing, but failed physical signoff:
Magic reported 423 DRC errors, KLayout reported one DRC error, and LVS
reported 126 mismatches. The top-level rows create metal spacing and
nwell/tap errors around the fixed macros; inserted antenna diodes also appear
in the layout netlist. It is not a simulation or release candidate.
A revised assembly floorplan widened every macro-side placement corridor and
reduced tap spacing to 10 um. It removed the nwell/tap errors, leaving 12
Magic metal3 spacing markers at one macro edge and one corresponding KLayout
error. The flow therefore stopped before LVS. A routing variant with a macro
extension and global-routing jumper-only antenna repair still reported 22
Magic metal3 markers, four KLayout errors, and 225 inserted diodes. Setting
both global and detailed antenna repair to jumper-only, without the macro
extension, produced zero DRC markers, matching LVS, and no inserted diodes.
The independent signoff checker rejects that layout for 99 antenna-violating
nets (144 pins); 109 jumpers did not repair the remainder. A met4/met5
top-level routing variant is under evaluation. No top assembly is qualified.
The earlier C4X7 capacitance-only frequency bracket
must not be used for candidate selection: its all-net SS fastest endpoint is
about 318 MHz, far below the required 500 MHz.
A met4/met5-only top-level route and a met3/met5-only route both failed global
routing with congestion. A wrapper with one buffer per shared coarse/fine
control reduced antenna violations from 99 nets to 10, but retained 15 Magic
metal3 spacing markers and one KLayout marker at macro boundaries. Splitting
the buffer bank into separate fast/slow drivers preserved all 255 fine controls
for each macro and reduced post-route antenna violations to one net
(`fine_slow_buffered[7]`), with no inserted diodes. It still has 17 Magic
metal3 spacing markers and three KLayout markers at two macro edges. Restricting
this wrapper to met2/met5 routing failed with congestion. At 50% placement
density, the split-driver wrapper cleared Magic DRC, KLayout DRC, and LVS, but
four antenna violations remained. Four targeted guard loads cleared those
violations, while a different slow-control branch then violated the antenna
rule; a fifth targeted load changed placement and introduced DRC markers.
A uniform guard-load wrapper instead provides one retained buffer input on
each external control and each fast/slow buffered control branch. Its
2,237-cell routed layout at 50% placement density passed the independent
physical checker with zero routed antenna violations, zero Magic and KLayout
DRC markers, and matching LVS. No antenna diodes were inserted. This is a
physical candidate only. Explicit all-net Magic RCX completed with
6,477/6,481 nets and 552,915 resistors; exact resistor-only-node elimination
reduces this to 512,585 resistors without dropping capacitance. Frequency
range, closed-loop PVT behavior, jitter, and power still require qualification.
An upstream-Xyce/KLU SS/1.62 V/125 C coarse-0/fine-247 all-net trial reached
17.4 ns and measured 503.25 MHz from its partial waveform, but exceeded its
30-minute limit before the requested 25 ns endpoint window completed. A
repeat with a 70-minute limit completed 25 ns in 48 minutes. Its 12--25 ns
window measures 504.51 MHz with a 2.11 MHz half-window difference, confirming
that the high endpoint spans 500 MHz at this corner but remains unsettled.
It does not qualify a calibration point or release mode. A matching coarse-1/fine-247
trial reached 16.2 ns before the same 30-minute timeout. Three consecutive
rising-edge periods in its partial waveform imply 478.6, 479.9, and
479.3 MHz, respectively, so the upper side of the 400 MHz band is present
at this corner. Its required window also did not complete. The corresponding
coarse-1/fine-8 partial waveform has early falling- and rising-edge period
estimates of 375.4 and 381.1 MHz, respectively; the next same-direction
periods imply 387.5 and 385.5 MHz. All four estimates place the lower side
of the band below 400 MHz at this corner; a further falling-edge period gives
389.4 MHz. This low-code transient reached 15.8 ns and timed out at 30 minutes
without completing its requested 25 ns window. No two-core release evidence
is claimed.
An isolated `IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD` assembly connects
this DCO macro to the existing BBPD and digital-core macros without changing
the earlier modern release target. Its routed 8,876-cell top passes the
independent physical checker: zero post-route antenna violations, zero Magic
and KLayout DRC markers, matching LVS, clean routing DRC, and matching
Magic/KLayout GDS streamout. The final netlist contains the new DCO instance.
The routed top contains 40 inserted antenna diodes, whose pinned level-3 PDK
model is unsupported by upstream Xyce. Thus this physical pass is not yet a
simulatable signoff assembly. Mode presets, full-window
frequency, loop lock, PVT, jitter, and power still require qualification on
the candidate assembly.
An isolated `IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD`
wrapper adds the existing mode controller around that candidate macro top.
Its independent physical checker also passes with zero antenna, routing,
Magic/KLayout DRC, LVS, and streamout XOR violations. The wrapper still uses
the earlier modern mode presets and contains 22 inserted antenna diodes.
Its physical pass does not validate those presets against this DCO, resolve
diode-model compatibility, or qualify the PLL modes.
Jumper-only routing of the hard-macro top initially left 21 antenna violations.
Targeted guard loads reduced these to 11, uniform `buf_8` loads to six, and
uniform `buf_16` loads with buffered MMD inputs to one. An extra load on that
remaining control net moved the violation to a different DCO thermometer bit.
Doubling the retained `buf_16` gate loads across all 255 DCO control branches
produced a diode-free hard-macro top with zero routed antenna violations. The
independent checker passes its Magic/KLayout DRC, LVS, routing DRC, and
streamout XOR checks; the final netlist has zero diode cells and one instance
of the two-core DCO macro. This replaces the earlier diode-bearing physical
assembly as the current top candidate. At that stage the configured wrapper
still needed a matching diode-free route and recalibrated modes.
For the configured wrapper, jumper-only repair on the original floorplan
left ten antenna net violations. Reducing the repair wire limit from 300 to
100 micrometres left six. Excluding the small `buf_1` repair cell at the
100-micrometre limit left five; the remaining sinks are `clkbuf_1` cells.
Excluding more small buffer types caused OpenROAD to select delay cells and
increased the count to seven. A 900 by 1180 micrometre floorplan failed
detailed placement, while a 980 by 1270 micrometre floorplan and a
30-micrometre wire limit each left seven violations. The best result from
these wire and buffer trials had five violations. None of these trials
changed the uncalibrated mode presets.
Upstream-Xyce/KLU FF/1.98 V/-40 C coarse-3 endpoint attempts without a
transient initial-condition override did not produce waveforms after more
than 30 minutes. Diagnostic `uic` startup, with and without a finite supply
ramp, advanced less than 0.3 ns in several minutes and was stopped. These
truncated runs supply no FF frequency evidence or validated acceleration.
An isolated single-core V5_TURN10 FF/1.98 V/-40 C coarse-3 endpoint screen
completed 25 ns with upstream Xyce/KLU. Reanalysis of the full 12--25 ns
waveforms measures 455.076 MHz at fine 8 (five periods) and 487.351 MHz at
fine 247 (six periods). The half-window differences are 0.101 and 0.194 MHz.
This standalone band therefore falls below 500 MHz at both measured endpoints;
it is a search screen, not a frequency exclusion proof for all other bands or
a qualification of the assembled two-core DCO. The adjacent standalone
coarse-2 band measures 552.915 MHz at fine 8 (six periods) and 601.511 MHz
at fine 247 (seven periods) over the same full window. Its half-window
differences are 0.315 and 0.319 MHz. The measured adjacent-band gap from
coarse-3 fine 247 to coarse-2 fine 8 is 65.563 MHz, straddling the 500 MHz
target. This is a substantial FF coverage risk; neither short-window band
is numerically qualified, and all other bands still need screening.
The existing BOOST8 core at coarse 3 is slower, measuring 447.381/478.599 MHz
at fine 8/247 over 12--25 ns at the same FF point. Its additional switched
first-turn drivers are disabled outside coarse zero, so selecting this core
at coarse 3 would not close the observed gap. An isolated C3BOOST4 variant
adds four fine-controlled tri-state drivers to the actual coarse-3 turn
node. Its structural checker passes, and a 644-cell standalone layout passes
the physical checker with zero diode, antenna, DRC, and LVS violations.
Explicit all-net extraction covers 1,874/1,876 nets and 87,495 resistors;
exact resistor reduction leaves 74,781. Its FF coarse-3 fine-8/247 transient
was stopped after approximately 12.5/14.3 ns: a preliminary 6 ns-start
measurement of two/three periods gives about 442.9/444.3 MHz. The added
stage-3 input load appears to slow this routed path and collapse its fine
span; the partial waveform is not a qualified frequency measurement. The
variant was not promoted.
An additional standalone BOOST8_OSC8 FF/1.98 V/-40 C coarse-3 endpoint
screen completed 25 ns with upstream Xyce/KLU and all-net extracted RC.
Reanalysis of the full 12--25 ns waveforms measures 478.355 MHz at fine 8
(five periods) and 505.198 MHz at fine 247 (six periods). The corresponding
half-window differences are 0.349 and 0.163 MHz. Unlike the current fast
core's adjacent-band gap, this measured band spans 500 MHz at this PVT point.
Interior coarse-3 code 200 measures 500.030 MHz (six periods, 0.032 MHz
half-window difference), within the 500 MHz 1000 ppm frequency bound.
Code 220 measures 502.408 MHz (six periods, 0.220 MHz half-window difference).
Adjacent code 199 measures 499.899 MHz with 0.072 MHz half-window difference;
code 201 measures 500.149 MHz with 0.0075 MHz half-window difference.
The smaller local step around code 200 is 0.119 MHz, making its quarter-LSB
limit 0.0297 MHz. Code 200's 0.0317 MHz drift narrowly exceeds that screen;
code 201 remains within the frequency bound and has lower drift. The four-run
numerical convergence test is still missing, so neither code is a qualified
500 MHz setting or a result for the assembled two-core DCO.
An independent 70 ns standalone code-201 run measures 500.277 MHz over
20--70 ns (24 periods) with a 0.0053 MHz half-window difference. Its frequency
is about 0.128 MHz above the earlier 12--25 ns result, showing why the short
window alone cannot establish numerical convergence. The longer result is
still within the 500 MHz 1000 ppm bound, but the approved qualification uses
four solver/settling variants and a longer observation window.
At TT/1.80 V/27 C, the same standalone BOOST8_OSC8 coarse-1 endpoints measure
569.859/628.425 MHz at fine 8/247 over 12--25 ns, with 0.226/0.156 MHz
half-window differences. Its coarse-2 endpoints measure 378.551/404.071 MHz
(three/four periods, 0.0005/0.152 MHz half-window differences). These two
standalone bands leave an approximately 166 MHz measured gap straddling
500 MHz. The two-core wrapper selects BOOST8 instead of BOOST8_OSC8 for
logical coarse code one. The selected BOOST8 coarse-0 TT endpoints measure
746.185/964.794 MHz at fine 8/247 (nine/twelve periods, 0.054/0.770 MHz
half-window differences). This fixed selector does not close the observed
nominal 500 MHz gap at these sampled endpoints. Other bands, the assembled
output, and numerical convergence remain unqualified.
The BOOST8 coarse-1 TT endpoints, which the original wrapper cannot select,
measure 508.704/568.757 MHz at fine 8/247 (six periods each, 0.025/0.165 MHz
half-window differences). A remapped wrapper exposing that band is under
physical evaluation. Its standalone low endpoint remains 8.704 MHz above
500 MHz, so routing/output loading or further tuning would still have to
close the gap before this becomes a qualified nominal setting.
The isolated `DUALMACRO_OSC8_REMAP_DBUF_GUARD` wrapper exposes slow-core
bands zero and one at logical coarse codes one and two, respectively, and
shifts the fast-core coarse code down by one for higher logical bands.
Its first placement had metal3 spacing errors at the fast-macro lower edge;
moving that macro left moved the errors to the slow-macro lower edge.
Moving the slow macro right 5 um cleared them. The final routed 2,216-cell
layout passes the independent checker with zero antenna, DRC and LVS
violations, zero diode cells, and one instance of each intended macro.
The output frequency, loop behavior, PVT matrix, jitter and power remain
unqualified; the standalone TT slow-band low endpoint still misses 500 MHz.
An isolated BOOST8_LOAD48 trial adds 48 fixed active loads while retaining all
255 independent fine controls. Its final netlist contains 303 enabled
inverter loads and no diodes, but the independent physical checker rejects
175 slow-corner maximum-slew violations and four maximum-capacitance
violations. A reduced BOOST8_LOAD24 variant retains 279 total enabled
inverter loads; its 675-cell routed layout passes the independent physical
checker with zero antenna, DRC, LVS, slew and capacitance violations and no
diodes. Its all-net extraction covers 1,994/1,996 nets and 89,135 resistors;
exact resistor-only reduction leaves 76,414. At SS/1.62 V/125 C its coarse-0
fine-8/247 endpoints measure 357.449/446.306 MHz over 12--25 ns (four/five
periods, 0.107/0.412 MHz half-window differences), so this short standalone
band spans 400 MHz. Interior fine codes 120/128 measure 399.773/401.734 MHz
(five periods each, 0.161/0.130 MHz half-window differences). Code 120 is
within the 400 MHz 1000 ppm frequency bound, but it is still unsettled and
numerically unqualified. At TT/1.8 V/27 C its coarse-1 fine-8/247 endpoints
measure 488.368/543.429 MHz over 12--25 ns, so this short standalone band
spans 500 MHz. Fine codes 56/64 measure 498.471/500.384 MHz (six periods,
0.239/0.077 MHz half-window differences). Code 64 is within the 500 MHz
1000 ppm frequency bound, but numerical convergence, assembled frequency,
and power remain unqualified.
A 50 ns TT coarse-1/fine-64 follow-up using upstream Xyce/KLU reached only
38.54 ns before its 900 s wall-clock timeout. Its complete 20--38 ns slice
measures 500.390 MHz over nine periods with a 0.0078 MHz half-window
difference. This is a partial diagnostic waveform, not a completed transient
or a numerical-convergence qualification.
A separate 40 ns TT coarse-1/fine-64 upstream Xyce/KLU run completed in
947 s. Its 20--40 ns window measures 500.390 MHz over nine periods with a
0.0078 MHz half-window difference. This confirms the later-window standalone
frequency but does not establish adjacent-code spacing or convergence across
independent numerical variants.
Separate completed 25 ns TT runs at adjacent fine codes 63 and 65 measure
500.151 and 500.572 MHz over 12--25 ns, respectively. Compared with the
same-window code-64 result of 500.384 MHz, the smaller adjacent spacing is
0.188 MHz, giving a provisional quarter-LSB limit of 0.047 MHz. The 40 ns
code-64 half-window difference is below that number, but the comparison mixes
settling windows and code 63 still has a 0.106 MHz half-window difference.
Longer adjacent-code and independent numerical-variant runs are required.
A completed capacitance-only Magic RCX run of standalone LOAD24 at TT
coarse 1/fine 64 measures 744.853 MHz over 12--25 ns (nine periods). The
matching remapped assembly at logical coarse 2/fine 64 timed out at 18 ns;
its complete 13.11--17.13 ns slice measures 745.928 MHz over three periods.
The assembled and standalone capacitance-only periods agree closely. The
large speed shift from the 500.390 MHz standalone full-RC result therefore
comes primarily from omitting distributed wire resistance in this diagnostic
extraction. Neither capacitance-only run qualifies assembled full-RC
frequency.
At FS/1.62 V/125 C, the all-net extracted BOOST8_OSC8 fast macro at coarse
0/fine 247 completes a 12--25 ns screen at 823.066 MHz (ten periods,
0.127 MHz half-window difference). This confirms high-end range above 500 MHz
at that one PVT point; it does not find or qualify a 500 MHz tuning code.
At SF/1.62 V/125 C, the same full-RC maximum-code screen completes at
807.467 MHz over 12--25 ns (ten periods), with a 0.968 MHz half-window
difference. It also confirms high-end range above 500 MHz, but its drift and
lack of a nearby tuning code leave calibration unqualified. A separate SF UIC
diagnostic was roughly 11 MHz faster in an overlapping later window and was
stopped; its different startup trajectory cannot replace the normal-startup
measurement.
Additional TT standalone endpoint screens locate the remaining modes.
BOOST8_OSC8 fast-core coarse 3 spans 307.614--324.017 MHz over 12--25 ns
(three periods each), and coarse 4 spans 258.488--270.130 MHz (two periods
each). Its coarse 5 endpoints are 223.054/231.618 MHz over 5--25 ns;
the later 12--25 ns window has only one/two periods. Neither fast band
covers 300 or 250 MHz at TT. BOOST8_LOAD24 slow-core coarse 2 spans
338.945--365.641 MHz, coarse 3 spans 279.778--297.828 MHz, and coarse 4
spans 239.238--252.166 MHz over 12--25 ns. The slow coarse-4 band spans
250 MHz, but the measured slow coarse-3 high endpoint remains 2.172 MHz
below 300 MHz and the fast coarse-3 low endpoint is 7.614 MHz above it.
BOOST8_OSC8 coarse 14 measures 99.057--100.752 MHz over the short
5--40 ns diagnostic window (two periods each), suggesting 100 MHz coverage;
coarse 16 measures 88.085--89.404 MHz over 20--70 ns (four periods each).
None of these endpoint screens establishes numerical calibration, assembled
frequency, or closed-loop behavior.
An isolated BOOST8_LOAD18 trial removes six of LOAD24's fixed active loads
while retaining all 255 independent fine controls. Its routed 669-cell
layout passes the independent checker with zero antenna, DRC, LVS, slew and
capacitance violations, no diodes, and 273 enabled inverter loads. All-net
Magic RCX covers 1,970/1,972 nets and 88,671 resistors; exact resistor-only
reduction leaves 76,070. The completed SS/1.62 V/125 C coarse-0 fine-8/247
endpoint screen measures 361.742/452.513 MHz over 12--25 ns (four/five
periods), so this isolated band still spans 400 MHz. Its half-window
differences are 0.196/0.088 MHz; numerical convergence remains unqualified.
At TT/1.80 V/27 C, coarse-1 fine-8/247 measures 491.233/547.384 MHz (six
periods each), so 500 MHz remains covered by this isolated band. Coarse-3
fine-8/247 measures 279.344/297.339 MHz (two/three periods) over 12--25 ns.
Coarse-3 still misses 300 MHz by 2.661 MHz at the fastest legal fine code,
so LOAD18 does not fix nominal 300 MHz coverage. Coarse-4 fine-8/247
measures 238.966/251.928 MHz (two periods each), spanning 250 MHz in this
short endpoint screen. These results do not qualify numerical convergence
or assembled frequency. LOAD18 remains isolated from the integrated wrapper.
The existing zero-fixed-load BOOST8 macro was rescreened at TT for a
possible 300 MHz band. Its completed coarse-3 fine-8/247 endpoints measure
288.198/307.182 MHz over 12--25 ns (three periods each), so this isolated
band spans 300 MHz. The high endpoint has a 0.550 MHz half-window difference
and is not numerically qualified. Its coarse-1 fine-8/247 endpoints measure
508.704/568.757 MHz (six periods each), leaving 500 MHz below that band.
New TT/1.80 V/27 C all-net coarse-2 fine-8/247 endpoints measure
348.405/376.664 MHz over 12--25 ns and miss 400 MHz. Coarse-4 endpoints
measure 244.869/258.640 MHz and span 250 MHz. These four rows are in
`build/modern_25mhz/v5_turn10_boost8_tt_c2_c4_endpoints_25ns/dco_postlayout_results.csv`;
they are short screening results, not numerically qualified target settings.
An isolated BOOST8_C1LOAD8 variant adds eight retained inverter loads to
the active coarse-1 turn node and preserves all 255 fine controls. Its
659-cell standalone layout passes the independent checker with zero antenna,
DRC, LVS, slew, and capacitance violations. All-net Magic RCX covers
1,930/1,932 nets and has 88,153 resistors; exact resistor-only reduction
leaves 75,253. Its TT/1.80 V/27 C coarse-1 fine-8/247 endpoints measure
493.995/551.056 MHz over 12--25 ns. This shifts the band downward by about
15--18 MHz relative to BOOST8 but still misses the new 450 MHz target.
These endpoints are in
`build/modern_25mhz/v5_turn10_boost8_c1load8_tt_c1_endpoints_25ns/dco_postlayout_results.csv`;
the extraction summary remains unqualified and numerical convergence is open.
The 32-load continuation passes the same standalone physical checks with
683 cells and zero reported violations. Its all-net RCX covers 2,026/2,028
nets and has 89,344 resistors, reduced exactly to 76,726. TT coarse-1
fine-8/247 endpoints measure 466.136/516.637 MHz over 12--25 ns, still
missing 450 MHz. These screening rows are in
`build/modern_25mhz/v5_turn10_boost8_c1load32_tt_c1_endpoints_25ns/dco_postlayout_results.csv`.
The 48-load continuation also passes the standalone physical checker with
699 cells and zero reported violations. Its all-net RCX covers 2,090/2,092
nets and has 89,969 resistors, reduced exactly to 77,810. TT coarse-1
fine-8/247 endpoints measure 454.874/503.513 MHz over 12--25 ns, missing
450 MHz by 4.874 MHz at the low endpoint. The screen is in
`build/modern_25mhz/v5_turn10_boost8_c1load48_tt_c1_endpoints_25ns/dco_postlayout_results.csv`.
The 64-load continuation passes the same standalone physical checks with
715 cells and zero reported violations. All-net RCX covers 2,154/2,156
nets and has 90,769 resistors, reduced exactly to 78,652. Its TT coarse-1
fine-8/247 endpoints measure 438.407/483.393 MHz over 12--25 ns, so this
isolated band brackets the revised 450 MHz target with 11.593 MHz lower
and 33.393 MHz upper sampled margin. The two waveform rows are in
`build/modern_25mhz/v5_turn10_boost8_c1load64_tt_c1_endpoints_25ns/dco_postlayout_results.csv`.
The extraction summaries remain unqualified, and the 64-load result does not
establish numerical calibration. An interior TT screen of fine codes
64/72/80 measures 448.446/449.786/451.233 MHz over 12--25 ns. Code 72
is within the 450 MHz 1000 ppm frequency bound, but the short window and
eight-code spacing do not establish local monotonicity or convergence.
The interior rows are in
`build/modern_25mhz/v5_turn10_boost8_c1load64_tt_c1_local64_80_25ns/dco_postlayout_results.csv`.
A capped-20-ps, 40 ns TT follow-up of adjacent codes 72/73/74 measures
449.616/449.784/450.015 MHz in the transient runner's CSV over 12--40 ns.
The release calibration remeasurement of the saved waveforms reports
449.671/449.826/450.076 MHz with twelve periods each. Code 74 is within
the 1000 ppm functional frequency bound, but its 0.058 MHz half-window
difference exceeds the 0.045 MHz 100 ppm calibration bound. This run does
not include independent tolerance, half-step, and longer-settling variants;
no 450 MHz preset has been promoted. Rows are in
`build/modern_25mhz/v5_turn10_boost8_c1load64_tt_c1_local72_74_40ns/dco_postlayout_results.csv`.
The experimental two-macro wrapper pairs BOOST8_OSC8 with BOOST8_C1LOAD64
and remaps logical coarse bands so the latter serves the nominal 450 MHz
band. A source review caught and corrected an off-by-one remap: logical
bands 1/2/4/5 now select slow physical bands 0/1/3/4. The corrected
wrapper's routed run
`pvt_probe_dualmacro_osc8_c1load64_remap_dbuf_guard_corrected_slow245`
fails physical signoff with 19 Magic metal-3 spacing errors, three
KLayout metal-3 spacing errors, and three antenna violations on slow
coarse-control routes. Earlier routes of the uncorrected source at
slow-core x=240/250 um also failed physical checks. These are routing
diagnostics, not qualified assemblies. No wrapper RCX or assembled
450 MHz frequency has been promoted from these layouts.
A 12--25 ns SS/1.62 V/125 C coarse-0 endpoint screen on the standalone
BOOST8_C1LOAD64 RCX produced no frequency rows: both fine-8 and fine-247
Xyce runs hit the 1500 s per-case timeout. The failed rows are recorded in
`build/modern_25mhz/v5_turn10_boost8_c1load64_ss_c0_endpoints_25ns/dco_postlayout_results.csv`.
That capped-step attempt supplies no slow-corner range measurement.
An explicit upstream-Xyce/KLU follow-up completed both standalone endpoint
runs without the 20 ps maximum-timestep cap. At SS/1.62 V/125 C, coarse 0
fine 8/247 measures 381.190/480.094 MHz in the runner CSV, completing in
334/264 s. Full-window remeasurement gives 381.314/480.245 MHz over
12--25 ns with four/five periods and half-window differences of
0.248/0.252 MHz. This establishes a sampled band around 450 MHz at this
corner, but does not qualify calibration or a preset. Evidence is in
`build/modern_25mhz/v5_turn10_boost8_c1load64_ss_c0_code8_25ns_klu/`
and `build/modern_25mhz/v5_turn10_boost8_c1load64_ss_c0_code247_25ns_klu/`.
The standalone FF/1.98 V/-40 C coarse-3 follow-up also brackets 450 MHz.
Fine 8/247 measures 441.742/472.230 MHz in the runner CSV over 12--25 ns;
full-window remeasurement gives 441.707/472.294 MHz with five periods
each and half-window differences of 0.059/0.108 MHz. These differences
exceed the 0.045 MHz calibration bound for a 450 MHz mode. The sampled
range is useful, but it supplies no qualified preset. Evidence is in
`build/modern_25mhz/v5_turn10_boost8_c1load64_ff_c3_endpoints_25ns_klu/`.
The wrapper continuation at fast-core 65,60 um and slow-core 245,95 um
stopped at global-routing congestion (`GRT-0116`), before DRC signoff;
its run tag is
`pvt_probe_dualmacro_osc8_c1load64_remap_dbuf_guard_corrected_fast65y60_slow245y95`.
Moving the fast core to 60,65 um restored a zero-DRC routed layout, but
independent signoff found four slow fine-control antenna violations.
Targeted slow-net guard loads cleared those and shifted the residual
violations to five other nets. Uniform extra fine-control gate area reduced
the next run to two antenna violations; another targeted continuation
again had five. None of these layouts is physically qualified.
Moving coarse-band selection gates onto the external thermometer inputs
preserved the logical band choices and reduced the best routed antenna
report to one violating fine-control net, with zero Magic/KLayout DRC and
matching LVS. A targeted guard then moved the residual to two other fine
routes. Uniform additional fast fine-control gate area also left two
antenna violations. The independent checker rejects all of these runs.
The closer macro placement at (60,65)/(215,65) um failed detailed placement
before routing; macro spacing is still under evaluation.
The tag's fast-core coordinates are inaccurate; the generated DEF places
it at 60,65 um. Enlarging the die to 480 by 280 um allowed routing to
complete in `pvt_probe_dualmacro_osc8_c1load64_corrected_room480`, but
signoff still reports four Magic spacing markers, one KLayout spacing
violation, and three antenna violations on fast fine-control nets.
The synthesized mapping checker `scripts/check_450_dualmacro_mapping.py`
passes 240 coarse/fine control cases for this corrected wrapper and rejects
the prior off-by-one wiring. Its result is in
`build/modern_25mhz/dualmacro_450_mapping.json`; this check covers control
forwarding and core selection only.
Further standalone TT/1.80 V/27 C BOOST8_C1LOAD64 endpoints measure
284.573/302.974 MHz at physical coarse band 3 and 242.093/255.269 MHz
at band 4 (fine 8/247, 12--25 ns runner window). These sampled bands
bracket the wrapper's proposed 300 and 250 MHz modes at TT. The band-4
remeasurement has only two periods at each endpoint, and the half-window
differences are 0.189/0.283 MHz; neither band is calibrated. Evidence is in
`build/modern_25mhz/v5_turn10_boost8_c1load64_tt_c3_c4_endpoints_25ns_klu/dco_postlayout_results.csv`.
Small macro-placement shifts and one extra slow-output buffer stage kept
some routes DRC clean but moved antenna failures among control and output
nets; the extra stage also caused 16 Magic metal-3 spacing errors in its
tested floorplan. A mirrored fast core had eight antenna violations.
These experimental routes remain unqualified.
An experimental BOOST8_OSC8_LOAD24 fast-core variant adds 24 fixed active
loads while retaining the 255 independent fine controls. Its routed layout
passes the independent physical checker with zero signoff violations and no
diode cells. All-net Magic RCX covers 1,998/2,000 nets and contains 90,115
resistors; exact resistor-only reduction leaves 78,124. The completed
SS/1.62 V/125 C coarse-0 fine-8/247 screen measures 427.233/524.800 MHz
over 12--25 ns (four/six periods), retaining isolated 500 MHz range. The
high endpoint has a 0.461 MHz half-window difference and is not numerically
qualified. At TT/1.80 V/27 C coarse-3 fine-8/247 measures
298.917/314.691 MHz over 12--25 ns (three periods each), now spanning
300 MHz in this isolated fast macro. Its half-window differences are
0.090/0.089 MHz; convergence and interior-code interpolation remain open.
At FF/1.98 V/-40 C, coarse-3 fine-8/247 measures 465.146/490.950 MHz over
12--25 ns (five/six periods), leaving its fastest legal setting 9.050 MHz
below 500 MHz. A separate UIC fine-247 diagnostic measures 492.246 MHz
over 5--15 ns and is not qualification evidence. Adjacent FF coarse-2
fine-8/247 measures 571.302/610.768 MHz (six/seven periods) over 12--25 ns.
The 80.353 MHz sampled gap between the coarse-3 high and coarse-2 low
endpoints straddles 500 MHz. These two loaded fast-core bands therefore do
not close FF 500 MHz coverage. Other bands and numerical convergence remain
unqualified, and this variant is not integrated.
An additional upstream-Xyce/KLU FF/1.98 V/-40 C coarse-4 fine-8/247 screen
of the same extracted macro measures 392.174/410.392 MHz over 12--25 ns.
Its sampled gap to the coarse-3 low endpoint is 54.754 MHz and contains
450 MHz. Lowering the highest target to 450 MHz therefore does not establish
FF coverage in these adjacent bands. This endpoint screen is not a full-band
or numerical-convergence qualification; results are in
`build/modern_25mhz/v5_turn10_boost8_osc8_load24_ff_c4_endpoints_25ns/dco_postlayout_results.csv`.
An isolated 40 ns TT coarse-3 screen of fine codes 24--27 measures
300.112, 300.161, 300.252, and 300.195 MHz over 12--40 ns (seven periods
each). Code 24 is within the 300 MHz frequency error bound, but code 27
measures 0.057 MHz below adjacent code 26, so the local fine response is
nonmonotonic in this run. Half-window differences of 0.048, 0.144, 0.076,
and 0.045 MHz exceed a quarter of the neighboring fine-code steps. This
short run has fewer than eight measured periods and does not establish
calibration convergence or interpolation across all legal codes.
An isolated three-macro wrapper combines original BOOST8_OSC8, loaded
BOOST8_OSC8_LOAD24, and BOOST8_LOAD24. Its logical coarse remap exposes the
original fast physical coarse 3 at logical 4 for FF 500 MHz, loaded fast
physical coarse 3 at logical 5 for TT 300 MHz, and slow physical coarse 4
at logical 6 for TT 250 MHz. The first physical placement passed LVS and
electrical checks but had two KLayout and ten Magic metal3 spacing markers
at the original fast macro's lower edge. Shifting that macro right caused
global-routing congestion; shifting it left routed but produced metal3
markers at both fast and slow lower edges. Increasing halo in the original
die failed detailed placement. A taller die then failed global routing.
With a wider 700 x 320 um die and a 20% global-routing capacity reserve,
the wrapper routed but retained one metal3 spacing cluster at the loaded
macro's lower edge. Moving all three macros to a higher grid-aligned row
cleared Magic and KLayout DRC, but the independent audit found one antenna
violation. Extra input guards moved the violation to other nets and sometimes
reintroduced metal3 spacing errors. A two-stage input buffer tree reduced
the final antenna count to two in one zero-DRC trial, while targeted guards
on those buffered nets reintroduced 19 Magic metal3 spacing markers. This
three-macro wrapper remains an unqualified experimental candidate and is
excluded from the passing physical audit. No assembled frequency has been
measured.
The integrated `DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD` wrapper uses
BOOST8_OSC8 for the fast band and BOOST8_LOAD24 for the slow band, mapping
slow-core coarse codes zero and one to logical coarse codes one and two.
The routed 2,242-cell wrapper passes the independent physical checker with
zero antenna, DRC, LVS, slew and capacitance violations, no diode cells,
and one instance of each intended macro. Its all-net Magic RC extraction
covers 6,639/6,645 nets and contains 555,701 resistors. Exact resistor-only
reduction removes 40,654 resistors and retains every capacitance. A TT logical
coarse-2/fine-64 upstream Xyce four-rank UIC diagnostic on that reduced model
wrote only the time-zero sample after 241 s and was stopped. A second
four-rank UIC run forced the KLU direct solver but reached only 0.023 ns in
244 s. Neither supplies a full-RC assembled-frequency measurement.
Closed-loop behavior, jitter and power remain unqualified.
A matching hard-macro top replaces the older DCO wrapper while retaining the
same phase detector and digital core. Its routed 9,463-cell layout passes the
independent checker with zero antenna, DRC, LVS and streamout XOR violations,
zero diode cells, and exactly one instance of the new DCO wrapper. Functional
frequency and closed-loop qualification for this top remain open.
A matching configured 25 MHz top also passes the independent physical checker
with zero antenna, DRC, LVS and streamout XOR violations, no diode cells,
and one instance of the new hard-macro top. Its mode-control source still
contains the old DCO seed presets and is not functionally qualified for the
remapped LOAD24 DCO.
An isolated `DUALMACRO_OSC8_DBUF_GUARD` wrapper replaces the original fast
core with BOOST8_OSC8 and keeps the BOOST8 lower-band core. Its first routed
placement had 15 Magic and one KLayout metal3 spacing markers at the slow
macro's upper edge. Moving the slow macro down congested global routing;
moving it up cleared DRC but disconnected its power pins, failing LVS.
Keeping its original vertical position and shifting it 5 um left passed
LibreLane and the independent checker with zero antenna, DRC and LVS
violations, zero diode cells, and one instance of each intended macro.
Explicit all-net Magic RCX of this signoff GDS covers 6,529/6,533 nets and
554,706 resistors; exact resistor-only reduction leaves 513,369 resistors
without dropping capacitance. An assembled FF coarse-3/code-201 upstream
Xyce/KLU run against this reduced model remained at operating point without
writing transient samples after 40 minutes and was stopped. It supplies no
assembled frequency measurement.
A separate upstream Xyce/KLU `TRAN UIC` diagnostic on that assembled
all-net model bypassed the DC operating-point stall and wrote initial output
samples, but advanced only to 0.071 ns in 304 s. It was stopped because it
could not reach a useful frequency window at that throughput; it provides no
assembled-frequency measurement.
This is a physical candidate only. The assembled output frequency, all-mode
PVT tuning, numerical convergence, loop behavior, jitter and power remain
unqualified.
An isolated `IDLE_RESET` wrapper buffers separate reset controls and holds
the unselected oscillator off. It passed the independent physical checker
with zero antenna, DRC and LVS violations, zero diode cells, and one instance
of each intended macro. This may reduce switching power after reset release;
the initial operating-point solve starts with both oscillators reset, so no
startup speedup is expected from this change alone. Its routed frequency,
mode-transition behavior, loop reacquisition and power have not yet been
measured. Explicit
all-net RCX covers 6,540/6,544 nets and 555,293 resistors; exact
resistor-only reduction leaves 514,735 resistors without dropping
capacitance. An FF coarse-3/code-201 upstream-Xyce/KLU diagnostic against
this model remained at operating point
without transient samples after about 12 minutes and was stopped when a
fresh physical rerun changed the GDS and extracted geometry. The refreshed
layout is being re-extracted before any further electrical claim.
The five remaining wrapper violations were traced through the placed netlist
to the `CONFIG_BUSY`, `TRACKING`, and `TARGET_MHZ[1:3]` status paths. An
isolated trial with explicit `buf_16` status drivers, disabled automatic
output-port buffering, and no wire-length buffer insertion removed those
output-chain violations. Five different internal decode/status nets then
violated the antenna rule, including the `TARGET_MHZ` decode and a
`CONFIG_BUSY` driver. That trial was not promoted.
The five output-chain violations were ultimately caused by status drivers
placed near the west side of the macro, while their wrapper output pins were
ordered on the east side. Moving `CONFIG_BUSY`, `TRACKING`, `CONFIG_VALID`,
`TARGET_MHZ`, and `TARGET_DCO_CODE` pins to the west edge shortened those
routes. Jumper-only antenna repair cleared the one remaining pre-repair
clock-chain violation. The `pvt_probe_dualmacro_guard_configured_status_west`
layout passes the independent checker with zero final antenna, Magic/KLayout
DRC, LVS, routing DRC, and streamout XOR violations. Its final netlist has
zero diode cells and one instance of the diode-free hard-macro top. This is
the current configured physical candidate; its old mode presets, closed-loop
PVT behavior, jitter, and power remain unqualified.
`make check-sky130-dualmacro-physical` independently rechecks the seventeen
diode-free layouts and their hierarchical macro references; it is a physical
check, not the release gate.
An isolated BOOST8_OSC8 variant adds four matched oscillator NAND drivers to
the physically clean BOOST8 design to recover high-end tuning speed. Its
structural check confirms eight identical oscillator drivers, the original
eight switched turn drivers, and 255 independent fine loads. The 655-cell
routed layout passes the standalone physical checker with zero reported DRC,
LVS, slew, or capacitance violations. Explicit all-net Magic RCX completed
with 1,902/1,904 nets and 89,242 resistors, reduced exactly to 80,057.
At SS/1.62 V/125 C its coarse-0 fine-8/247 endpoints measure
449.988/558.252 MHz over 12--25 ns. The high endpoint now spans 500 MHz,
but this band starts above 400 MHz. Its high-end half-window difference is
0.343 MHz, so numerical convergence also remains open. Coarse-1 fine-8/247
endpoints measure 298.413/326.950 MHz over 12--25 ns. The approximately
123 MHz gap between coarse-1's high endpoint and coarse-0's low endpoint
excludes 400 MHz; BOOST8_OSC8 is not promoted. A C1BOOST4 variant keeps four
of the switched turn drivers active in coarse band one to close this gap;
its 655-cell layout passes the standalone physical checker with zero reported
DRC, LVS, slew or capacitance violations. All-net Magic RCX completed with
88,868 resistors, reduced exactly to 79,795. Its extracted coarse-1 endpoints
measure 298.577/327.399 MHz, essentially unchanged because these drivers
feed the inactive coarse-0 turn node in coarse band one. This experiment is
rejected. A C1TURN4 variant instead decodes coarse band one and attaches four
switched drivers to its active turn node. Its 664-cell routed layout passes
the standalone physical checker with zero reported DRC, LVS, slew and
capacitance violations. All-net Magic RCX completed with 1,929/1,931 nets
and 89,853 resistors, reduced exactly to 80,705. At SS/1.62 V/125 C its
coarse-1 fine-247 endpoint is 322.503 MHz over 12--25 ns; fine code 8 has
only two complete measured periods at 280.985 MHz. The 400 MHz gap remains,
so C1TURN4 is rejected. All-mode PVT qualification remains open.
The earlier C4X7 capacitance-extracted SS coarse-0 endpoints are
398.436/509.767 MHz over 12--70 ns, spanning 400 and 500 MHz; the high
endpoint has 0.892 MHz half-window drift. Its extracted FF coarse-4 endpoints
are 495.825/537.290 MHz, so the band spans 500 MHz at that approved point.
Their half-window differences are 0.091/0.317 MHz. These endpoint screens
do not establish calibration convergence or qualified target codes.
The SS coarse-0/fine-247 period falls from about 1967 ps to 1959 ps across
the 12--70 ns measurement window, indicating that settling contributes to
the failed half-window check. A 150 ns continuation measures 510.614 MHz over
80--150 ns, versus 509.767 MHz over 12--70 ns. Its half-window difference
improves from 0.892 to 0.265 MHz but still fails calibration convergence.
FF coarse-4 local codes 31/32/33 measure 499.470/499.317/499.520 MHz over
12--70 ns. Code 33 is within the 500 MHz 1000 ppm frequency bound, but the
three readings are not monotonic and their 0.050--0.176 MHz half-window
differences leave the local fine-LSB calibration unresolved.

Initial ideal-wire SS/1.62 V/125 C screens of a two-position fast-path proxy show
about 341--591 MHz with one driver copy and up to 897 MHz with two copies.
The high-code points still show settling sensitivity, so these are feasibility
screens, not qualified tuning curves. The actual 48-band layout must be
extracted and recharacterized. Files are in `drive-screen/`.

The parallel drivers intentionally trigger three Yosys multiple-driver checks.
`check_parallel_dco.py` verifies identical cell types, parameters, and complete
connections, exactly three known parallel output groups, and no additional synthesis
diagnostics. Its hashed report permits this experimental layout to continue
with a run-local `ERROR_ON_SYNTH_CHECKS=false` override after synthesis. This is
not a general synthesis-check waiver or production signoff. The tracked config
keeps the normal checker enabled. Physical DRC/LVS and extracted behavior remain
required; the candidate flow is under `physical/IntegerPLL_DCO_EINVP_COARSE_V2/`.

## Execution gates still open

The diode-repaired V4 dual-macro wrapper's full extraction completed with
8,987/8,993 final reported nets and 806,972 resistors in
`build/modern_25mhz/dualmacro_diode_repair_v4_all_net_rc/`.
The final raw SPICE contains six pw2nd diode instances, all with the
qualified fixed area/perimeter (4.347e11/2.64e6), on fast-core fine-control
nets 68/95/96/102/111/117. Its SHA256 is
`0b99276d4446f8b93ebff26a1823dbe1431826a39457c2f2260c50a7a3ecb254`.
Exact resistor-only reduction is running before PVT-specific diode
translation. Completed extraction is not an electrical release result.
The exact reduction subsequently completed: 806,972 resistors became
768,596, with 115,911 resistor-only internal nodes eliminated and all
non-resistor statements retained. Reduced SPICE SHA256 is
`34d06f8bf30c8cbb648bbfff4aae76186e99066a1331626a6b8dec6df099f342`.
The TT/27 C qualified-geometry translation completed for all six diodes
as `wrapper_tt27.translated.spice`, with its corner/temperature/content
provenance sidecar. An assembled-wrapper coarse-0 fine-8/247 screen is
running at 1.8 V through 40 ns with a 10 ps cap in
`dualmacro_diode_repair_v4_true_tt27_c0_endpoints_40ns_cap10ps`.
It tests the extracted assembly rather than assuming standalone-core
frequencies survive integration; full release qualification remains open.

The separate modern-Ciel TT near-seed audit remains a narrower check than the
approved release criteria. Its CSV measures the first two cycles after 12 ns.
Reanalysis of its saved 12--70 ns target-code waveforms gives 99.930, 249.982,
299.595, 399.527 and 500.707 MHz for the 100/250/300/400/500 MHz modes.
The 300, 400 and 500 MHz rows exceed the approved 1000 ppm frequency error;
the 100 MHz trace has only four complete measured periods. These short
waveforms cannot qualify the five modes, despite the scoped TT audit passing.
`check_sky130_modern_25mhz_release.py` reports the scoped result separately as
`scoped_near_seed_status: pass`, records
`approved_window_frequency_all_passed: false`, and fails the release command.
This diagnostic checks only frequency error and sample count; it does not
establish numerical convergence.
The release audit also requires 225 extracted-DCO qualification reports under
`build/modern_25mhz/pvt_qualification/mode_<MHz>/<corner>_<V>V_<C>C/`, covering
every approved mode and PVT point. Each report must pass coverage, numerical
convergence, exact target-code frequency and local monotonicity, interpolation
validation, and source-extraction provenance. The release audit also remeasures
every reported waveform and checks its completed provenance sidecar. The
qualifier measures the selected target code and its adjacent fine codes in every
convergence variant.
With `--validate-interpolation`, it also measures every remaining allowed fine
code and checks the sparse curve against those measurements. This full sweep
has not been run on the release candidate; the 225 reports remain missing.

1. **Reliable extracted simulation.** With the pinned upstream Xyce, compare
   reduced/full transients and converge timestep, tolerances and settling.
   Preserve binary and source hashes for every accepted result. Historical
   experimental KLS crashes are diagnostic history, not release blockers.
2. **Physical tuning coverage.** Screen all 48 bands, measure suitable bands
   across 45 PVT points, require target inside codes 8..247. Qualify numerical
   convergence against both 100 ppm and a quarter local fine LSB. Validate
   interpolation independently (the campaign currently marks it unvalidated).
   Redesign and regenerate DCO layout if any target is unreachable.
   The pinned Sky130 SPICE deck provides `sf` and `fs` model sections, but the
   HD standard-cell Liberty set used for physical timing has no `sf` or `fs`
   libraries. Its available TT/FF/SS files also have no exact 125 C,
   1.62 V or 1.98 V characterization points. The three-corner LibreLane
   report therefore cannot stand in for timing signoff across the approved
   five process corners and voltage/temperature grid.
3. **Controller integration.** Qualify the implemented handoff with measured
   oscillator curves, constrain Gray-bus skew and bundled-data paths, audit CDC
   and timing, then connect the qualified configuration to production wrappers.
   The experimental acquiring core is connected to the mixed simulator.
   Its parameter ranges must stay within the 16-bit edge/count counters.
   A 2026-10-04 unplaced Sky130 mapping screen found the combinational
   seed divider failing the 40 ns reference period: worst reference slack
   was -72.247658 ns at TT/25 C/1.80 V and -189.899048 ns at the available
   slow timing library point. The seed calculation now uses 32 restoring
   division cycles, preserving its unsigned integer quotient, polarity,
   and legal-code clamp. This adds 1.280 us at 25 MHz. The new arithmetic
   regression checks 408 ascending/descending endpoint pairs, narrow and
   full-width count spans, plus disable and mode-change cancellation.
   All five oscillator phase offsets pass both the existing acquisition
   and integrated-core regressions, including disturbance reacquisition.
   The identical mapping recipe now has reference-domain slack of
   +28.476740 ns at TT/25 C/1.80 V and +17.089413 ns at SS/100 C/1.60 V.
   Mapped cell area falls from 51,702.0864 to 41,915.2000 um2.
   The full core still fails the 450 MHz timing screen (worst slacks
   -8.52/-15.52 ns); reset fanout and fine-loop data paths remain open.
   These screens use ideal clocks, no wire RC, and exclude cross-domain
   paths, so they do not establish routing, clock, reset, or CDC signoff.
   Source/netlist/report hashes and the passing regression log are pinned
   in `build/acquiring_core_450_timing/iterative/evidence.json` alongside
   the reproducible Yosys `synth.ys` and OpenSTA `timing.tcl` recipes.
   The available slow Liberty point is not exact approved-grid PVT coverage.
   Further nominal OpenROAD placement with estimated met2 signal RC and
   fanout repair inserted 17 buffers and removed the reported reset-recovery
   failures, but left -7.165442 ns slack through the fine-loop arithmetic
   and thermometer decode. The experimental acquiring core now defaults
   to the feedback-clocked fine loop; `DLF_UPDATE_ON_PLLOUT=1` remains an
   explicit diagnostic option. Both modes still update once per feedback
   period, but event-to-update latency differs and physical loop behavior
   needs requalification. All five phase offsets pass the default core's
   mode, gain/polarity, reset, disable, stopped-clock and disturbance tests;
   the oscillator-clock option also passes its separate integration run.
   The oscillator edge counter now predicts carry at each four-bit boundary
   one clock ahead, shortening the binary/Gray increment path. A 150,000-cycle
   regression verifies exact counts, Gray encodings, single-bit transitions,
   wraparound, and reset with active carry predictions. The 408 seed cases
   and all acquisition regressions continue to pass.
   With both changes, nominal placement/fanout repair leaves -0.157257 ns
   on the worst PLLOUT path, now from the transferred divider configuration
   into the feedback counter; the long edge-counter carry chain is removed.
   Configuration transfer into feedback-clocked outputs still fails: a
   ten-iteration setup repair leaves worst slack -2.830778 ns. The reference
   domain has +28.848818 ns slack, and the worst reported reset-recovery
   path has +0.782792 ns. No failed path has been waived. These remain
   estimated-placement diagnostics with ideal clocks and cross-domain
   exclusions, not routed or CDC signoff. Recipes, current RTL/test/netlist
   hashes, the passing regression log, and failed timing evidence are in
   `build/acquiring_core_450_timing/segmented_counter/evidence.json`.
   Slow-corner closure remains open, and timing qualification must also
   cover the above-450 MHz oscillator frequencies encountered during scan.
   An optional `REGISTER_CONFIG` stage in `IntegerPLL_MMD_Retimer` now
   registers safe-ratio terminal and duty decoding before the counter.
   `IntegerPLL_DigitalCore.MMD_REGISTER_CONFIG` defaults to zero to retain
   its historical divider behavior; the experimental acquiring core enables
   the stage. It adds one oscillator clock to ratio changes. Its regression
   checks all 256 eight-bit ratios, output periods (0/1 clamp to /2), 1,000
   live ratio changes against a one-cycle-delayed legacy divider, and reset.
   All acquisition/integration phase cases and the oscillator-clock option
   pass; the historical divider configuration/controller, configured wrapper,
   and configured behavioral PLL checks also pass with the default option.
   The current nominal placement screen's worst PLLOUT path is now handoff
   acknowledge to a command register (-0.107454 ns), rather than divider
   ratio decoding. Overall timing has not improved: configuration paths into
   the feedback domain still fail at -3.652590 ns and reset recovery has
   -0.163019 ns slack in this placement. The reference domain has +27.930532
   ns slack; mapped cell area is 42,164.1888 um2. This is a diagnostic
   configuration change, not a physically qualified release candidate.
   Current source/test/netlist hashes, recipes, successful regressions and
   failed timing evidence are pinned in
   `build/acquiring_core_450_timing/registered_divider/evidence.json`.
   The tuning handoff now registers destination request qualification before
   capturing the wide payload. This adds one destination clock and separates
   acknowledge/request comparison from the payload-register mux path. The
   source still holds the bundle until acknowledgement, and acknowledgement
   still waits the full `APPLY_CYCLES` interval after actual payload capture.
   Direct tests with apply intervals one and three cover 200 bundles each,
   initial zero, atomic capture, no early acknowledgement, source changes
   while the destination is stopped, resumption, and reset mid-transfer.
   All acquisition phase cases, counter/seed/divider tests, and the separate
   oscillator-clock integration option continue to pass.
   With nominal placement and setup repair, the reported PLLOUT-domain
   paths now meet the 450 MHz period with +0.219880 ns worst slack; reported
   reset recovery has +0.569755 ns slack and REFCLK has +28.847691 ns.
   Configuration paths from oscillator-clocked command registers into the
   feedback domain still fail at -3.430068 ns. This does not establish full
   core timing or release qualification. The result retains ideal clocks,
   estimated placement RC, and the same reference-domain exclusions; routed
   timing, cross-domain bundle/skew constraints, slow corners, and scan-rate
   closure remain open. Source/test/netlist hashes and the passing regression
   and failed timing evidence are pinned in
   `build/acquiring_core_450_timing/registered_handoff/evidence.json`.
   Feedback-clocked acquisition now uses a second tuning handoff on
   `CLKDIV_RETIMED` for the fine-loop seed, polarity, gains and run metadata.
   The original fast handoff supplies divider controls; acquisition accepts
   tuning only after both consumers acknowledge. Fine reset release and
   tracking release are synchronized to the feedback clock, while withdrawal
   remains asynchronous so it still works when the oscillator stops.
   The oscillator-clock diagnostic option retains the single fast handoff.
   All acquisition and integration phase cases pass, including an added
   assertion that an acknowledged seed has reached the actual fine-clock
   consumer. Synthetic default-core disturbance handoff is at most
   141.415 us across the five tested phase offsets, below the existing
   170 us regression bound; this is not measured-PLL lock qualification.
   Nominal estimated-placement timing now reports +0.096007 ns on PLLOUT
   and +28.890821 ns on REFCLK. The worst feedback-domain path no longer
   starts at a configuration register: it is from the oscillator-clocked
   `core.bbpd_decision` register into `DLF_CODE[4]`, with -2.507432 ns slack.
   Reset recovery also has a -0.040671 ns failure in this placement.
   No timing failure is waived; BBPD decision delivery, reset recovery,
   physical bounds on both bundled transfers and Gray skew, slow/routed
   corners and above-target scan frequencies remain open. Current source,
   test, netlist and report hashes and the successful consumer-load assertion
   are pinned in `build/acquiring_core_450_timing/feedback_handoff/evidence.json`.
   The experimental feedback-clocked core now registers the BBPD decision
   before fine-loop arithmetic, adding one feedback period of decision latency.
   The generic core's new `REGISTER_BBPD_DECISION` option defaults off; the
   oscillator-clock diagnostic also retains its previous decision path.
   Integration now checks exact four-code movement for each KI=64, KP=0
   decision, rejecting both missing and duplicate updates, as well as polarity
   and restoration by the opposite event. All acquisition/integration phase
   cases and the historical configured behavioral check pass.
   A timing-recipe audit found that the previous feedback clock was defined
   at the output port. Output buffer insertion can separate that point from
   internal clock loads, leaving fine-loop register paths unchecked. Those
   historical screens do not establish full feedback-domain coverage. The
   current recipe defines FINECLK at the actual divider register's Q pin
   (`_8309_/Q` in this mapped netlist), before placement/repair, and explicitly
   reports passing as well as failing paths. The corrected nominal screen
   reports +1.445612 ns worst feedback slack, +29.380341 ns reference slack,
   -0.054299 ns PLLOUT slack and -0.010493 ns reset-recovery slack. Timing
   still fails. Clock-tree/routed and slow-corner closure, bounded bundled/Gray
   paths, event-clock coverage, above-target scan frequencies, and measured
   loop/gain requalification remain open. Corrected recipes and current
   source/test/netlist/regression/report hashes are pinned in
   `build/acquiring_core_450_timing/registered_decision/evidence.json`.
   A wider margin/coverage audit found two unclocked BBPD event-toggle
   registers and an unconstrained divided-clock output. Current diagnostic
   recipes explicitly model both BBPD inputs as asynchronous event clocks
   with 40 ns cadence and 1.111 ns high width, and constrain the divided-clock
   output with the historical 0.5 ns PLLOUT-relative external delay. These
   are declared diagnostic assumptions, not measured pulse-width or event
   CDC qualification. Clock groups still exclude asynchronous paths; physical
   bundled/Gray and event-return synchronization checks remain necessary.
   The available SS/100 C/1.60 V capacity screen failed at -2.328565 ns on
   divider terminal decoding into upper feedback-counter bits. The generic
   digital core now exposes `MMD_RATIO_WIDTH` (default eight); acquisition
   selects five, matching its five-bit divider interface and all approved
   ratios through 18. This removes unreachable upper counter bits without
   reducing the generic core's divider range. All acquisition/integration
   regressions, exact BBPD steps and the oscillator-clock option pass.
   Nominal placement/repair now reports +0.299970 ns PLLOUT slack,
   +1.446033 ns feedback slack, +29.026682 ns reference slack and
   +0.470379 ns recovery slack. All reported nominal setup/recovery checks
   pass, but these are ideal-clock estimated-placement results, not release
   signoff. At the available slow library point, PLLOUT still fails by
   0.920859 ns and recovery by 0.241382 ns; feedback/reference slack is
   +0.738615/+20.199549 ns. Both coverage reports now have no unclocked
   register pins or unconstrained endpoints. RESET_N alone lacks a data
   input delay because it is explicitly treated as asynchronous reset.
   Source/test/netlist hashes, recipes, declared event-clock assumptions,
   passed regressions and nominal/slow results are pinned in
   `build/acquiring_core_450_timing/five_bit_divider/evidence.json`.
   Acquisition now selects an optional five-bit countdown divider with
   registered wrap prediction and segmented borrow prediction. The generic
   retimer and digital core retain the original up-counter by default.
   New ratios take effect at a wrap; the duty threshold is held for that
   entire period. `tb_mmd_countdown` passes all 32 input values (0/1 clamp
   to two), period/duty checks, 4,000 live ratio changes and reset checks.
   The full acquisition regressions and historical configured behavioral
   regression also pass. The same ideal-clock placement screen now reports
   nominal PLLOUT/FINECLK/REFCLK/recovery slack of
   +0.262411/+1.446832/+29.645279/+0.111579 ns. At SS/100 C/1.60 V,
   PLLOUT improves from -0.920859 to -0.531846 ns; feedback/reference
   slack is +0.743762/+20.043589 ns, while recovery worsens to
   -0.530383 ns. The remaining slow setup paths run through the held duty
   comparison and its reload mux. This is a functional experimental
   improvement, not timing signoff: slow setup/recovery, routed clocks,
   asynchronous crossings and full PVT coverage remain open. Clock coverage
   reports have no unclocked-register or unconstrained-endpoint warnings;
   the declared reset and event-clock assumptions remain unchanged.
   Completed logs, recipes, mapped netlists and source/test hashes are in
   `build/acquiring_core_450_timing/countdown_divider/evidence.json`.
   A separate segmented high-time countdown was tested next. Its period,
   duty and integration tests passed, but SS setup worsened to -0.780959 ns,
   so it was withdrawn. Its source snapshots, mapped netlist, reports and
   rejection evidence remain in `predicted_duty/evidence.json` under the
   same timing directory.
   The acquiring core now releases fine-loop reset from two feedback-clock
   stages of the external reset, rather than the fast-domain reset release.
   The digital core's optional `SYNCHRONIZE_RESETS` parameter generates
   separate fast/fine local reset releases internally. It resets the loop
   filter, registered BBPD decision and fine control registers from the fine
   release. Public ports, generic defaults and wrapper behavior are preserved.
   Fine-bundle validity is now checked in the fine tracking-reset domain,
   eliminating its comparison from the fast reset synchronizer. The remaining
   fast coarse comparison was also removed: RUN_FINE can rise only after LOAD
   has acknowledged both complete bundles, and any mode/coarse change withdraws
   it before another transfer. A tracking-release assertion checks both coarse
   bundles for staleness. The new
   direct reset regression verifies exactly two local edges before release,
   64 releases at varying phases, immediate asynchronous assertion and 32
   stopped-oscillator reset cases. Integrated acquisition tests now also
   reset and recover a stopped oscillator. All five integration phase
   variants, the oscillator-clock option, digital-core/coarse/loop model
   compatibility, configured behavioral tracking and 48 Python verification
   tests pass. The testbench now drives an explicit initial falling reset
   edge, so the new independently reset domain is actually initialized.
   The final nominal capacity screen reports +0.151825/+1.445197/
   +29.875275/+1.223316 ns PLLOUT/feedback/reference/recovery slack.
   At SS/100 C/1.60 V, recovery now passes at +0.500388 ns and
   feedback/reference setup at +0.738107/+20.111845 ns. Oscillator setup
   still fails at -0.443677 ns through the divider duty/reload logic.
   Added minimum-delay checks report positive removal slack at nominal/SS
   (+0.009935/+0.139675 ns). Ordinary register hold checks pass, but the
   nominal BBPD event-clock input-to-opposite-event-register paths fail hold
   by 0.076358 ns under the declared coincident event-clock/uncertainty
   assumptions; those paths pass at SS (+0.030926 ns). Their physical
   event separation, mutual exclusion and pulse-width constraints are not
   measured, and this failure is retained rather than waived.
   No unclocked-register or unconstrained-endpoint warnings are reported.
   These are ideal-clock estimated-placement diagnostics, not routed,
   pulse-width, routed reset/CDC or full-PVT release qualification.
   Intermediate evidence is pinned in `feedback_reset/evidence.json`,
   `tracking_reset/evidence.json` and `internal_resets/evidence.json`.
   Final source/test hashes, complete regressions, recipes and max/min timing
   reports are in `local_reset_release/evidence.json` under the timing directory.
   Subsequent divider work stores its advance phase with reset zero, predicts
   wrap two cycles ahead, and uses a 14-bit shift register for the remaining
   floor(ratio/2)-1 high clocks after a reload. This removes the held duty
   comparison from the output path while preserving complete pulse widths
   across live ratio changes. The highest terminal bit now uses the exact
   boolean form `ratio[MSB] && |ratio[MSB-1:0]`, removing its clamp/subtractor
   carry path. An independent integer period/high-time model now checks every
   cycle of the countdown regression: all 32 values and 4,000 live changes
   pass with each of registered and direct configuration. The existing
   eight-bit regression also passes all 256 ratios and 1,000 live changes.
   All acquisition/integration variants, reset tests and configured behavioral
   compatibility pass. The final estimated-placement screen reports nominal
   PLLOUT/feedback/reference/recovery slack of +0.382183/+1.438119/
   +28.865788/+1.007201 ns, and SS slack of -0.116545/+0.728596/
   +19.724592/+0.197228 ns. Removal remains positive (+0.016039/
   +0.135787 ns); the nominal BBPD event hold failure remains -0.076358 ns.
   Synthesis against the slow liberty alone did not change the earlier mapped
   topology or close timing. A separate falling-edge predictor and a
   predecoded two-cycle flag worsened slow setup; their source snapshots and
   failed results are retained rather than selected.
   A physical follow-up placed pins, legalized cells, upsized 18 fast-domain
   muxes and repaired electrical limits. The final same-geometry nominal/SS
   characterization has +0.938531/-0.128858 ns PLLOUT setup slack. Both
   placement checks and reported slew/capacitance checks pass; nominal BBPD
   hold still fails. Nominal and slow reports read the same strengthened
   database, with identical cell/master/position/orientation fingerprints.
   Clocks remain ideal and RC is estimated from placement: this is neither
   CTS/routing nor reset/CDC/full-PVT signoff, and no physical preset is
   promoted. Final RTL, tests, recipes, completed reports and placement data
   are pinned in `terminal_decode/evidence.json` under the timing directory.
   The acquisition core now enables the optional `BBPD_EVENT_CDC` path:
   each qualified pulse toggles its source register, followed by two direct
   PLLOUT receive stages marked `ASYNC_REG`. The generic core default retains
   its prior behavior. Removing the consumed-token return guard removes its
   unsynchronized acknowledgement from the pulse-domain data path. The
   contract is one qualified event per feedback interval, with events at least
   three PLLOUT periods apart; this does not support arbitrary pulse bursts.
   A separate asynchronously withdrawn, two-clock receive guard flushes stale
   samples during disable/clear and permits direct synchronizer connections.
   The mapped JSON confirms each first-stage Q feeds only its second-stage D,
   both stages use PLLOUT, and consumed acknowledgements do not appear in the
   source-toggle D fanin. These are structural checks, not MTBF qualification.
   The new directed test passes 384 pulses across eight phases at each of
   100/450 MHz, including 50 ps RTL pulses at 25 MHz cadence, simultaneous
   inputs, pending-event withdrawal, withdrawal between oscillator edges,
   reset, and re-enable without replay. `check-frequency-acquisition`, `sim`,
   and configured behavioral compatibility all pass. The latter retains its
   historical 500 MHz behavioral case; it does not qualify a 500 MHz mode.
   Fresh independently repaired nominal/SS placement screens report PLLOUT
   setup +0.374916/-0.067511 ns, FINECLK +1.446310/+0.740707 ns,
   and REFCLK +28.450974/+19.131222 ns. Minimum recovery is
   +0.968386/+0.052689 ns (see completed reports for individual paths).
   Removal passes (+0.023815/+0.148000 ns), while the assumed coincident
   BBPD event-clock hold check remains -0.090316/+0.006138 ns. No additional
   event-clock exceptions hide this violation. The only coverage warning is
   external RESET_N input delay, already excluded explicitly. These screens
   use ideal clocks and estimated placement RC, with asynchronous domain
   crossings excluded; they neither use a common repaired geometry nor
   establish CTS/routing, CDC, pulse-width, reset, or all-PVT signoff.
   Current sources and completed evidence are pinned separately under
   `build/acquiring_core_450_timing/event_cdc/evidence.json`; historical
   `terminal_decode` results describe the earlier RTL snapshot.
   The independent hot-SS tolerance-only code-16 run completed at
   449.804438874 MHz over 24--80 ns (24 periods), with 0.018963134 MHz
   half-window difference. Its 0.009848062 MHz difference from the matched
   baseline is below the earlier 0.037314395 MHz local comparison limit;
   neighboring codes and the independent half-step/long-window variants are
   still running. Separately, TT C1LOAD128R coarse-1/code-206 completed the
   longer 80--160 ns measurement at 400.029889921 MHz (31 periods), with
   0.037717025 MHz half-window difference. That is about 74.7 ppm from
   400 MHz and below the 0.040 MHz absolute drift limit, but adjacent-code
   local-LSB and independent numerical comparisons remain outstanding.
   Completed waveform/deck hashes are recorded beside each run; neither
   result promotes a preset or completes the 45-PVT campaign.
   A follow-up on the current CDC RTL legalized pins/cells and upsized
   17 fast-domain muxes plus the handoff ratio-bit driver. Its SS PLLOUT
   setup deficit fell to -0.043400 ns; attempting additional counter-flop
   and logic sizing worsened it to -0.131670 ns and is rejected. Automatic
   nominal hold repair reported no violations despite the explicit event
   path reports still failing, so it does not establish event hold closure.
   The retained diagnostic inserts two unity buffers at each event-flop D,
   then legalizes their placement. Netlist comparison proves the only
   logic changes from `ss_sized.nl.v` are those four buffers and the two
   corresponding D-pin rewires; event clock connections are unchanged.
   Same-geometry TT/SS characterization now reports BBPD event hold
   +0.056979/+0.289287 ns, PLLOUT setup +1.004890/-0.043400 ns,
   FINECLK setup +1.441659/+0.729713 ns, and REFCLK setup
   +29.362797/+19.047766 ns. Minimum recovery is
   +0.918900/+0.026478 ns and removal +0.032477/+0.166525 ns.
   Both placement and reported slew/capacitance checks pass. Geometry
   fingerprints match exactly between corners. This closes the assumed
   coincident-event nominal hold violation in this placement diagnostic;
   actual BBPD pulse shape, skew, reset release, MTBF, CTS/routing and
   full-PVT qualification remain open, as does slow-corner fast setup.
   `event_cdc/physical_delay_assessment.json` records the topology and
   same-geometry checks, and the recipes and completed reports are hashed
   in the updated evidence ledger. The four buffers are physical candidate
   netlist changes, not a promoted release implementation.
   The acquisition counter now updates registered Gray bits directly from
   the previous Gray word and the predicted nibble carries. For bits 0--14,
   a bit flips when the binary carry reaches that bit and stops there; bit
   15 flips on carry alone. This removes the binary-increment-to-Gray XOR
   level without changing the count or observation latency. The independent
   binary/Gray scoreboard passes 150,000 cycles, multiple full wraps, and
   reset while carry predictions are active. The full acquisition regression
   passes all six integrated runs (five phase offsets and the legacy fast
   DLF option), the edge/seed/handoff/divider/reset tests, and both BBPD CDC
   pulse tests. Fresh mapped checks retain both direct synchronizer pairs.
   The revised Gray encoding is no longer a reported worst PLLOUT path.
   A physical candidate keeps the event data buffers and splits the divider
   advance control's large wrap-decoder load onto an equivalent reset flop.
   The final netlist confirms the duplicate has the same cell type and
   identical D, CLK and RESET_B connections as the original; the wrap
   decoder alone uses the duplicate Q. Both placement and reported
   slew/capacitance checks pass. Same-geometry TT/SS characterization reports
   PLLOUT setup +0.997561/-0.012053 ns, FINECLK setup
   +1.442532/+0.731277 ns, REFCLK setup +29.961411/+19.942335 ns,
   minimum recovery +1.012122/+0.193886 ns, removal
   +0.056559/+0.209439 ns, and BBPD event hold +0.056979/+0.289287 ns.
   Stronger advance and counter drivers and a smaller wrap gate all worsened
   setup and are rejected, with their failed reports retained. The selected
   prototype reduces the slow setup deficit from 43 ps to 12 ps; it does not
   close it. Ideal clocks and estimated placement RC still preclude a routed
   timing/reset/CDC/all-PVT claim. No presets are promoted. Snapshot sources,
   tests, recipes, reports, topology checks and geometry fingerprints are
   pinned in `build/acquiring_core_450_timing/gray_increment/evidence.json`.
   Earlier `event_cdc` ledgers remain tied to their earlier source snapshots.
   Follow-up wrap-gate and endpoint sizing did not improve the 12 ps
   ideal-clock deficit. Two prediction prototypes were also evaluated:
   an upper-zero flag and a reset-low upper-nonzero flag using the existing
   low-bit borrow. Both pass the complete acquisition regression, including
   all ratios and 4,000 live changes in each divider configuration; direct
   state invariants agree with the counter. Their repaired slow setup is
   -0.109021/-0.210684 ns, respectively, so neither is selected. Sources,
   tests and completed evidence are retained under `wrap_prediction` and
   `wrap_nonzero`. The original MMD and divider test have been restored and
   verified byte-for-byte against the previously passing evidence hashes.
   The retained Gray-increment physical candidate was then subjected to
   actual clock-tree synthesis, legal placement, propagated clocks, and
   setup/electrical repair. Clock roots include REFCLK, PLLOUT, the divider-Q
   generated FINECLK, and both pulse-clocked BBPD inputs. The same-geometry
   TT/SS characterization passes placement and reported electrical checks,
   but exposes substantial fast/fine crossing failures: SS PLLOUT-group
   setup -2.283974 ns, FINECLK-group hold -1.738123 ns, and recovery
   -1.096541 ns. REFCLK input hold is also negative (-0.370331 ns) with
   the diagnostic 0.5 ns min/max input delay. In the displayed SS crossing,
   fine launch clock latency is 2.884274 ns and fast capture latency about
   0.578221 ns, a difference exceeding one 450 MHz period. No clock-group
   or timing exceptions were added to conceal these related-clock paths.
   This CTS trial invalidates any inference that the earlier 12 ps
   ideal-clock deficit is the only digital release obstacle. The next
   physical/control task is to audit generated-clock latency, balancing,
   and fast/fine control/data/reset crossings against propagated clocks,
   then repair and route before making timing/CDC/reset claims. The design
   is not routed or qualified. `gray_increment/cts_assessment.json` and
   the completed recipes, reports, database and geometry fingerprints are
   pinned in `gray_increment/continuation_evidence.json` separately from
   its earlier ideal-clock evidence ledger.
   The post-CTS path audit identified two unintended fine-to-fast
   dependencies: the acquisition rail detector decoded the registered fine
   DCO word on PLLOUT, and fast BBPD capture/decision storage used the
   fine-domain tracking flag. Acquisition now optionally samples the rail
   flag on FINECLK with its local reset and transfers that single flag through
   the existing two reference-domain stages. Its generic default still
   samples on PLLOUT; the acquisition wrapper selects the fine clock only
   when DLF arithmetic uses it. Fast BBPD storage now has an optional
   independent capture enable, selected from fast-domain tracking by the
   wrapper. The fine-clock decision register clears using its own DLF
   enable/clear signals. This latter correction was required by a new test
   that exposed stale decision consumption when fast capture was withdrawn
   while fine tracking remained enabled. New optional internal ports retain
   generic defaults and the acquisition core's external ports are unchanged.
   The new rail test passes 2,048 code changes and 114 fine samples, including
   independent fine resets, proving the flag cannot update on fast edges.
   BBPD tests pass default and independent capture at both 100/450 MHz,
   including capture while fine clear is asserted, withdrawal while fine
   tracking remains enabled, and re-enable without replay. All six integrated
   acquisition runs and the full acquisition test suite pass; `sim` and the
   configured behavioral compatibility test also pass. Mapped structure
   confirms the rail flop clock is FINECLK and fast capture is driven by the
   second fast tracking stage. These checks do not establish physical CDC.
   Fresh same-geometry propagated-clock CTS screens report nominal/SS
   PLLOUT setup +0.685438/-0.042849 ns, FINECLK setup
   +2.687933/+2.996435 ns, REFCLK setup +29.740343/+19.763399 ns,
   recovery +0.988733/+0.105592 ns, and removal +0.018430/+0.139118 ns.
   The former fine-to-fast rail/control paths and negative recovery are no
   longer worst violations. Placement and reported electrical checks pass.
   Hold remains negative: FINECLK -0.979956/-1.602643 ns and REFCLK input
   hold -0.085819/-0.351611 ns. BBPD event hold is -0.012156/+0.154569 ns
   (the other event clock also fails nominal hold by 0.010997 ns). Fine hold
   endpoints include the first tracking receive stage and the two decision
   payload registers; first-stage CDC intent and payload timing must be
   resolved separately, without hiding the payload violation. A balanced
   CTS recipe using smaller root/tree buffers worsened SS setup to
   -0.252275 ns and fine hold to -1.905356 ns and is rejected. RC remains
   estimated from placement; routing, complete CDC/reset analysis and PVT
   timing remain open. Current sources, tests, recipes and completed evidence
   are pinned in `build/acquiring_core_450_timing/local_capture/evidence.json`;
   the initial stale-clear failure is retained under `prior_capture_clear`.
   Independent hot-SS code-16 tolerance, half-step and long-window variants
   have now all completed. Their four-setting frequency spread is
   0.022313252 MHz, below the conservative previous local comparison limit
   0.037314395 MHz; all half-window drift checks also pass that limit.
   The half-step result is 449.816532729 MHz over 24--80 ns (24 periods),
   and the long-window result is 449.816904065 MHz over 48--160 ns
   (49 periods). Waveform/deck/provenance hashes and all four measurements
   are in `build/modern_25mhz/hot_ss_code16_independent_settings_assessment.json`.
   This is a custom single-code convergence screen, not the canonical
   qualify protocol or anchor/interpolation/adjacent-code/45-PVT completion.
   Codes 17 and 18 and the other active settling runs still need evidence.
   Post-CTS hold repair inserts 25 delay cells at nominal conditions and
   one additional cell for slow-corner input hold, plus one further unity
   buffer at each event-flop D. All reported hold/removal groups now pass
   nominal and slow characterization. Isolating the wrap decoder onto a
   duplicate advance flop and sizing the divider output flop from drive 1
   to 2 makes internal slow setup positive; the remaining placement-only
   setup violation is the external divider-clock diagnostic limit
   (-0.003931 ns). Increasing its drive to 4 worsens setup (-0.134591 ns)
   and is rejected. Final placement-only nominal/SS PLLOUT setup is
   +0.741972/-0.003931 ns; FINECLK setup +1.493894/+0.567170 ns.
   Structural comparison with the pre-repair CTS netlist proves that 28
   added delay cells have unity Boolean functions (checked against the
   PDK library), the duplicate has identical D/CLK/RESET_B and cell type,
   and the only other cell-type change is output-flop sizing. Collapsing
   those unity cells and the equivalent duplicate Q restores every original
   cell-pin connection. This is logic-preservation evidence after common
   reset and with powered cells, not dynamic gate/pulse/MTBF validation.
   The candidate then completes global routing with zero total overflow
   and 238,553 um total wirelength. Route-based estimated RC exposes slow
   setup -0.063791 ns and electrical violations (reported slew slack
   -0.14 ns and capacitance slack -0.01 pF). Same-geometry, same-route
   nominal/SS PLLOUT setup is +0.722244/-0.063791 ns; FINECLK setup
   +1.508433/+0.590408 ns and REFCLK setup +29.062727/+18.379433 ns.
   All reported hold/removal groups remain positive, and minimum recovery
   is +0.936000/+0.001408 ns. This near-zero slow recovery margin must
   also survive repair, detailed routing and the required corners.
   Independent nominal/SS routing initially produced different guides;
   final nominal characterization imports the exact saved slow-corner
   route segments. Geometry and serialized route-segment fingerprints
   match exactly. Exporting SPEF from estimated global-route parasitics is
   unsupported by this tool: it explicitly reports no extraction data.
   That attempted export is retained separately; no extracted SPEF or
   detailed-routing/DRC/LVS/full-PVT qualification is claimed. The next
   routing task is electrical/setup repair with global-route RC, then
   detailed routing and extraction. Completed reports, recipes, topology
   checks, guide/segment/database files and the rejected sizing trial are
   pinned in `local_capture/routing_evidence.json`; summarized timing is
   in `local_capture/route_assessment.json`.
   The hot-SS tolerance-only adjacent code 17 also completes over
   24--80 ns at 449.952687975 MHz (24 periods), with 0.018470197 MHz
   half-window drift. Its record and deck/waveform/provenance hashes are
   stored beside the run. Other independent code-17 variants and code 18
   remain incomplete; no qualification or preset promotion follows.
   Electrical repair with saved global routes now clears the reported
   slew/capacitance violations and improves slow recovery to +0.388038 ns,
   while slow PLLOUT setup remains -0.063779 ns. Nominal characterization
   imports those exact repaired segments; geometry/route fingerprints match.
   Detailed routing then exposed two unmapped logical constant nets tagged
   POWER/GROUND. Inspection proves their six sinks are signal inputs. They
   are mapped to conb tie cells, their signal net types corrected, and tie
   fanout repaired. An incremental-router callback crashed during that
   conversion; mapping constants before constructing global routes and
   rerouting from scratch avoids it. Deprecated route-layer options were
   replaced with the current layer-setting API. Both failures and corrected
   recipes are retained for reproducibility.
   Signal-only detailed routing completes in 4 min 26 s with zero final
   TritonRoute violations and an empty router DRC report. Routed DEF/ODB
   and the signal netlist are retained. This is not independent full-PDK
   DRC: the router also warns about unsupported LEF enclosure rules, and
   power/filler/tap/complete LVS and full-PVT qualification remain open.
   The installed PDK provides nominal/minimum/maximum OpenRCX Magic rule
   models under `libs.tech/librelane`; actual routed geometry now produces
   all three SPEFs. Each is explicitly read into STA for both nominal and
   slow cell libraries. Extraction alone does not load those parasitics
   into timing: its initial reports are extraction-generation diagnostics
   and must not be used as extracted timing evidence. The six authoritative
   timing runs are the `*_detailed_spef*_char` recipes and completed logs.
   Extracted-RC PLLOUT setup at nominal/minimum/maximum wire corners is
   +0.615459/+0.346281/+0.304937 ns for TT and
   -0.607055/-1.333175/-1.400697 ns for SS. SS recovery is
   +0.035165/-0.569267/-0.637997 ns. TT minimum/maximum wire corners
   also have negative hold (-0.020741/-0.073640 ns minimum reported slack).
   Consequently the earlier global-route improvements do not establish
   extracted timing closure. `detailed_rcx_assessment.json` contains every
   clock-group minimum and the scope of these six runs.
   A power-pin audit identifies 20,588 power/ground instance terminals and
   zero connected terminals. The routed object is explicitly a signal-only
   candidate and cannot operate as a released physical implementation.
   The next physical task is power connectivity/grid plus filler/tap planning,
   followed by routing, extraction, electrical/timing repair and independent
   DRC/LVS. Completed repair/route/extraction/power-audit artifacts and
   current source hashes are pinned in `local_capture/detailed_evidence.json`.
   Analog characterization continues separately; no preset is promoted.
   Additional adjacent-code diagnostics completed during routing. Hot-SS
   tolerance-only code 18 measures 450.234384050 MHz over 24--80 ns,
   with 0.021418084 MHz half-window drift; half-step code 17 measures
   449.965728079 MHz with 0.019854646 MHz drift (24 periods each).
   Cold-FF tighter-tolerance code 74 measures 450.356041883 MHz over
   12--40 ns (12 periods), with 0.030584303 MHz drift. Compared with
   its earlier 1e-4 result 450.264252 MHz, the approximately 0.091790 MHz
   numerical difference remains too large for the 0.045 MHz absolute
   comparison limit. These completed records and waveform/deck/provenance
   hashes are saved beside the runs; no frequency-range, local-LSB or
   qualification gate is weakened. Four analog jobs are still live.
4. **Acquisition/relock campaign.** Load qualified multi-band/PVT models, sweep
   initial fine code and reference phase, tune gains, and test enable, reset,
   every mode change and disturbances. Confirm four passing windows by 200 us
   from each stimulus. Select representative extracted BBPD/DCO convergence
   runs; retain replay and complete provenance.
5. **Physical characterization.** Characterize device noise, mismatch, period
   jitter/phase noise, supply sensitivity, power and area. Agree application
   limits after measuring the functional candidates, following the user's
   performance-first tradeoff policy. Deterministic co-simulation is not physical jitter.
6. **Production release.** Promote only qualified presets and controller logic,
   regenerate layouts, run DRC/LVS, timing/reset/CDC and the existing
   `check-sky130-pll-25mhz-release` gate. Its old preset assertions must change
   only with corresponding replacement evidence. No release claim is justified
   by the historical acquisition diagnostics alone.

## Reproduction entry points

Run from the OpenPLL repository:

```sh
make check-pll-verification check-frequency-acquisition
cmake --build ../build/openpll-cinterface --target test_calibrated_dco
ctest --test-dir ../build/openpll-cinterface -R calibrated_dco_phase --output-on-failure
python3 scripts/dco_calibration.py --help
python3 scripts/magic_full_rcx.py --help
```

`dco_calibration.py screen` defaults to all 48 coarse bands at codes 8/128/247.
Use `--pvt-grid` for the approved 45 PVT points.
`qualify --coarse N --mode-mhz M --target-code C --validate-interpolation`
compares baseline, tighter tolerances, half timestep, and longer settling/window
on anchors and adjacent codes, then measures all remaining fine codes to
validate the sparse interpolation curve. When the selected coarse band or fine
code varies with PVT, run `qualify` separately at each point with its selected
`--corner`, `--vdd`, and `--temperature-c`, writing to the same `mode_<MHz>`
output root. Each command requires explicit `--xyce`,
`--pdk-root`, `--rcx-netlist`, and `--output`. The runner uses the selected Xyce
binary's default solver unless `--xyce-linear-solver KLU` selects upstream KLU;
both modes use provenance-checked resume. The resulting deterministic curve
does not establish physical-noise qualification.

Power-grid follow-up (2026-10-04): `build/acquiring_core_450_timing/local_capture/build_pdn.tcl` adds VPWR/VPB-to-VDD and VGND/VNB-to-VSS global connections, met1 follow-pin rails, a met4/met5 ring and straps, and power vias to the tie-mapped placement. The first physical connectivity check rejected two `sky130_fd_sc_hd__probec_p_8` repair buffers (`load_slew17`, `load_slew108`) with isolated upper-metal power pins; the failed recipe/log are retained as `build_pdn_probe_failure.*`. Replacing them with `sky130_fd_sc_hd__buf_8` preserves their A/X pin interface, unity Boolean function `(A)`, and Liberty power-down function. Legalization reports zero displacement and placement checks pass. The revised `build_pdn.log` reports all 20,588 power/ground pins connected, with all VDD and VSS shapes connected. `pdn.odb`, `pdn.def`, and `pdn_evidence.json` retain this candidate and evidence. This is OpenROAD power connectivity evidence only. Tap/endcap/filler integration, signal rerouting around power geometry, fresh RCX/timing, independent full-PDK DRC/LVS, and electrical power qualification remain open. Prior signal-only SPEF timing does not qualify the modified geometry. Four Xyce processes were confirmed live; TT code208 and long-window hot-SS code18 advanced without restarting their campaigns.

Tap/filler integration (2026-10-04): `local_capture/build_pdn_filled.tcl` uses the installed PDK welltap (`tapvpwrvgnd_1`), endcap (`decap_3`) and fill-cell family. It inserts 2,394 taps at 10 um nominal spacing, 262 endcaps and 12,077 fillers. Placement passes; legalization moves cells by 3,831.1 um total (16 um maximum), so previous geometry timing is historical only. All 74,732 power/ground pins are connected, and VDD/VSS physical connectivity checks pass. `pdn_filled.odb/.def` retain the result. `ss_pdn_filled_route.tcl` launches full global/detailed signal rerouting with the existing timing assumptions; session 11933 was confirmed live in pin access. Router completion, independent DRC/LVS, RCX/timing and power electrical qualification remain unproven.

Completed analog results measured from pinned, completed provenance: hot-SS long-window code17 is 449.967056920 MHz (49 periods, 48–160 ns, half-window drift 0.016861348 MHz); TT long-window code207 is 400.168624994 MHz (31 periods, 80–160 ns, drift 0.037201819 MHz). The latter is about 422 ppm above 400 MHz and does not meet the 100 ppm target at that code. Results are retained in the campaign `completed_code17_measurement.json` and `completed_code207_measurement.json`; no calibration qualification is promoted.

Powered-route follow-up (2026-10-04): session 11933 and OpenROAD PID1885903 were confirmed live during detailed-route repair. Initial violations were roughly 38,000; the first repair iteration ended at 926, and a later live iteration reached 368. These are intermediate counts, not a completed DRC result. No routing process was restarted. Prepared `pdn_filled_rcx_{nom,min,max}.tcl` and six `{tt,ss}_pdn_filled_spef_{nom,min,max}_char.tcl` recipes preserve the existing constraints and explicitly load the extracted SPEF for timing. `pdn_filled_route_power_audit.tcl` will recheck power connectivity on the completed route and export a power-aware netlist. `stream_pdn_filled.sh` uses LibreLane's installed KLayout stream-out with the complete standard-cell GDS libraries. The installed `sky130A.lydrc` defaults to FEOL=false; the separate `sky130A_full.lydrc` changes FEOL to true while retaining BEOL/OFFGRID checks. These recipes are prepared but extraction, final power audit, stream-out and independent DRC have not yet run because detailed routing is live. No timing or physical signoff is claimed from these preparations.

Powered detailed-route evidence (2026-10-04): session11933 completed with exit0, final router violations0 and an empty `pdn_filled_route.drc`. Post-route power audit confirms all 74,732 PG pins connected and all VDD/VSS shapes connected. Min/nom/max OpenRCX extraction and six explicit-SPEF TT/SS timing runs complete; `pdn_filled_timing_assessment.json` records clock-group minima. Timing fails: SS PLL setup minima are -0.942828/-2.096028/-2.195261 ns for nom/min/max RC. SS max-RC recovery is -0.991228 ns, Fine setup -0.611362 ns, REF setup -1.232280 ns, and Fine hold -0.194757 ns. TT max-RC PLL setup is -0.199514 ns and Fine hold -0.315725 ns. This does not support a 450 MHz release claim. KLayout stream-out needed the installed Python environment containing pya; the installed standard-cell GDS includes all used cells, without a separate ef GDS file. The successful export reports all LEF cells have matching GDS cells. `pdn_filled_route.gds` retains full powered geometry. Independent KLayout FEOL/BEOL/OFFGRID DRC started as session42561 and was confirmed live; no independent DRC pass is claimed yet. LVS, routed timing repair, complete PVT/CDC/pulse qualification and analog calibration remain open.

Extracted-parasitic repair candidate (2026-10-04): `ss_pdn_extracted_repair.tcl` reads the powered route and its max-RC SPEF, excludes probe/low-power cells, removes fillers, and attempts design/setup repair at unchanged 450 MHz constraints. It resizes 48 cells, inserts three split-load buffers, swaps 11 pins and clones three cells. Its internal provisional WNS improves to -0.958 ns, but repair reports remaining setup violations; this is not fresh routed timing. Legalization moves cells (14.6 um maximum). `build_pdn_repaired_filled.tcl` removes/rebuilds PG geometry and inserts 11,769 fillers; all 73,528 PG pins and both VDD/VSS shape connectivity checks pass. `pdn_repaired_filled.odb` retains the candidate. `ss_pdn_repaired_filled_route.tcl` explicitly removes stale signal wires while preserving special PG geometry, then starts full signal routing as session97860. Fresh RCX/timing and independent DRC/LVS remain required. The original powered-GDS independent DRC session42561 remains authoritatively live and was not restarted. The user asked whether to lower the target to400; no target change was requested, so450 remains the objective.

Repair-equivalence follow-up (2026-10-04): `repair_equivalence.ys` compares the original powered candidate with `pdn_extracted_repair.nl.v` under powered-cell Boolean/clock-event semantics. Inline preprocessing produces `repair_gold.logic.v` and `repair_gate.logic.v`, removing only physical fill/decap/tap instances and supply-port connections. Liberty functions and sequential cells are elaborated; async primitive simulation cells require `techmap -autoproc -map +/simcells.v`, followed by `clk2fflogic`. Initial unsupported-async SAT and missing-autoproc attempts are retained as separate failure logs. Session72793 is authoritatively live, with equivalence signals proving; a full equivalence pass is not yet claimed. This check does not model analog power, pulse widths, metastability or timing. Repaired routing session97860 also remains live and a current repair iteration fell below1000 violations, while original powered-layout independent DRC session42561 remains CPU-active. Prepared the repaired candidate's three RCX and six explicit-SPEF timing recipes plus `characterize_pdn_repaired_filled.sh`; those must wait for its own completed routed database. No release gate is promoted from intermediate results.

Completed repair audit (2026-10-04): repaired detailed routing completes with zero router violations. All three extraction and six explicit-SPEF characterizations finish; `pdn_repaired_filled_timing_assessment.json` records results. SS max-RC PLL setup improves from -2.195261 to -1.292363 ns, but recovery worsens from -0.991228 to -1.901307 ns; SS REF hold is -0.169436 ns and Fine hold -0.016838 ns. This remains an unqualified candidate, not a release pass. Initial equivalence left31 internal cell-pin comparisons unresolved after pin swapping. `repair_equivalence_functional.ys` excludes automatic cell-pin wire-name matching while preserving the functional signals/output comparisons; all1715 equivalence cells are proven with zero unproven cells, under powered-cell Boolean/clock-event semantics. The blacklist and initial failure log are retained. This does not prove analog power behavior, pulse/MTBF or timing.

An isolated `terminal_boolean/rtl_snapshot` candidate directly decodes max(ratio,2)-1 instead of serial clamp/subtraction. Divider tests pass both registered/direct countdown modes (32 ratios and4000 live changes each) and registered default-width configuration (256 ratios and1000 changes). It synthesizes successfully, but the controlled SS estimated-placement screen with probe/lpflow cells excluded yields -0.193186 ns versus -0.042625 ns for the current RTL under the same exclusion policy. The candidate is therefore not selected; repository RTL stays unchanged. Independent powered-GDS DRC session42561 remains CPU-active and four Xyce simulations are live. Full release qualification remains open.

SPEF annotation/reset audit (2026-10-04): the repaired max-RC SPEF has ten BBPD CTS instance NAME_MAP entries with escaped brackets while the ODB/STA instance names have literal brackets. The focused `pdn_repaired_filled_route.max.normalized.spef` changes exactly those ten names; every other line and all RC data are unchanged. `inspect_spef_names.log` proves the physical/STA object names. Broad bracket normalization was rejected because it damages escaped multidimensional RTL net names; `rejected_all_brackets.*` retains that failed experiment. The focused read reports no STA instance/net lookup warnings. `audit_spef_unannotated.tcl/log` verifies all84 remaining unannotated drivers are unused outputs with no connected sink or output port, not connected paths lacking extraction. Corresponding min/nom and other-layout SPEF name handling still needs the same audited correction before complete timing qualification.

The -1.901307 ns recovery path is from fast-reset synchronizer _8220_/Q through split123(buf1) to fast-domain asynchronous resets. An isolated `ss_reset_buffer_size_screen.tcl` sizes split123 to buf8 under unchanged max-RC wiring and improves provisional worst recovery to -0.892771 ns; the new worst branch is split121(buf4). Placement then correctly fails because the larger buffer overlaps a filler, so no legal candidate/signoff is claimed and no RTL is changed. Additional reset distribution sizing/legalization, rerouting and fresh extraction remain required. Independent DRC session42561 and four Xyce jobs were confirmed live.

Legal reset-sizing candidate (2026-10-04): `build_pdn_reset_sized.tcl` starts from the completed repaired route, removes fillers, changes split121/122/123 to buf16/8/8, legalizes, rebuilds the power grid and replaces11,764 fillers. Placement passes (54.4 um total displacement,9.1 um maximum); all73,508 PG pins and both VDD/VSS shape connectivity checks pass. This is a legal physical candidate without an updated timing pass. `ss_pdn_reset_sized_route.tcl` removes stale signal wires and starts full rerouting as session55820, confirmed live in pin access. `characterize_pdn_reset_sized.sh` prepares three RCX and six explicit-SPEF runs using the focused ten-instance BBPD name correction. Its normalization block was verified against the completed repaired max-RC SPEF; shell syntax passes. It rejects missing-instance/net annotation warnings. Timing must be judged on the freshly rerouted/extracted geometry, not the earlier sizing screen. Independent DRC session42561 remains live and CPU-active, executing the FEOL licon.12 width operation; no timeout/restart or DRC pass is inferred. Four Xyce jobs remain live.

Transistor LVS and reset-sized extraction (2026-10-04): Magic extracts the original powered `pdn_filled_route.gds` with standard-cell SPICE port ordering. Initial Netgen pin comparison fails because TRACKING and BBPD_RESET_N are intentional aliases but Magic merged the top ports. `ext2spice short resistor` preserves both ports with a zero-ohm alias; the completed re-extraction and comparison now report "Circuits match uniquely." The JSON contains132 named comparisons and no bad nets/elements. Installed PDK setup ignores fill/tap classes; transistor/device and top-level connectivity comparisons cover the original powered geometry and power-aware schematic, not later repair candidates. `lvs_original/` retains scripts, extracted SPICE, logs/JSON, feedback and the initial merged-port failure. No independent DRC pass is inferred from LVS.

Reset-sized detailed routing completes with zero router violations. All three OpenRCX extractions and six corrected-name explicit-SPEF TT/SS timing runs finish without missing-instance/net warnings. Post-route PG audit confirms all73,508 power/ground pins connected and both VDD/VSS shape connectivity checks pass. `pdn_reset_sized_timing_assessment.json` records the results: SS max-RC recovery improves from -1.901307 to -0.253892 ns; PLL setup remains -1.359469 ns; REF hold is -0.241019 ns. TT max-RC Fine hold is -0.211493 ns. This candidate still fails450 MHz timing and needs its own GDS/LVS/DRC and continued setup/hold/recovery repair. Original independent DRC session42561 and four analog Xyce jobs remain live.

Post-route hold-repair candidate (2026-10-04): `tt_reset_hold_repair.tcl` reads the completed reset-sized route with corrected max-RC SPEF and nominal Liberty at unchanged constraints, removes fillers and excludes probe/lpflow cells. It finds five hold endpoints and inserts five delay cells, moving provisional minimum hold slack from -0.211 to +0.109 ns. Legalization passes (54.6 um total displacement,8.2 um maximum); these are internal repair estimates, not a new routed signoff. `build_pdn_reset_hold_fixed.tcl` rebuilds PG and places11,763 fillers; all73,524 PG pins and VDD/VSS shape connectivity checks pass. Full routing starts as session60422, confirmed live in pin access. Corrected-name three-RC/six-characterization recipes are prepared as `characterize_pdn_reset_hold_fixed.sh`. Fresh timing remains required. The latest completed reset-sized worst PLL path is from handoff.APPLIED_COMMAND configuration flop _7996_ through the clamp/subtract decoder to terminal register _8191_; configuration pipelining should be assessed if routed setup repair remains inadequate, without changing default generic behavior or acquisition/handshake requirements. Independent DRC session42561 and four Xyce jobs remain live.

Isolated divider configuration pipeline (2026-10-04): `build/acquiring_core_450_timing/config_pipeline/rtl_snapshot` adds optional CONFIG_PIPELINE(default0) to MMD and a corresponding generic-core parameter(default0). Only the isolated acquiring-core candidate enables it. The stage captures the raw ratio before the existing clamp/terminal/duty/high-mask decode, keeping those decoded outputs aligned and adding one configuration clock of latency. `tb_pipeline.v` independently models the extra latency; the registered countdown test passes all32 ratios and4000 live changes. The full acquisition regression launched as session16014 has progressed into integrated-core tests; its completion is not yet claimed. Synthesis launched as session53300. Repository RTL is unchanged pending full regression and physical timing evidence. Existing hold-candidate route session60422 and original independent DRC session42561 remain live; four Xyce jobs are live.

Pipeline regression/CTS and hold-candidate characterization (2026-10-04): configuration-pipeline session16014 completes successfully, including all six integrated acquisition runs, CDC/reset/handshake and compatibility divider checks plus the dedicated extra-latency model. Synthesis completes. The SS estimated-placement setup screen is -0.063900 ns, with critical reload/counter logic rather than the original handoff configuration decoder. CTS initially required I/O geometry; `make_tracks` and `place_pins` now provide it. Corrected CTS completes but still has timing violations (estimated PLL maximum-path deficit includes -0.135445 ns); it is not routed/extracted qualification and the isolated candidate is not selected. `config_pipeline/` retains source, regression, synthesis, placement/CTS recipes and results.

The selected-RTL hold-repair candidate routing session60422 completes. Three RCX and six corrected-SPEF timing runs finish without lookup warnings; `pdn_reset_hold_fixed_timing_assessment.json` records all reported group minima. These authoritative extracted results must govern subsequent setup/hold/recovery repair, not provisional positive resizer slack. Independent DRC session42561 remains live; release qualification remains open.

Powered pipeline candidate and independent Magic DRC (2026-10-04): `config_pipeline/build_pdn_filled.tcl` maps signal constants to tie cells, inserts PDK taps/endcaps/fillers and builds the power grid from its completed CTS placement. Placement passes (4,058.5 um total displacement,16.3 um maximum); all75,912 PG pins and both VDD/VSS shape connectivity checks pass. Full routing starts as session62493, confirmed live in detailed-route repair. Prepared three extraction and six corrected-name explicit-SPEF timing recipes in `config_pipeline/characterize_pdn_filled.sh`; shell syntax passes. The isolated pipeline remains unselected until routed timing/physical qualification.

`local_capture/magic_drc_original/run.tcl` follows the installed PDK `run_standard_drc.py` full-style DRC sequence, with the explicit GDS top `IntegerPLL_AcquiringCore` rather than the artifact filename. Session84463 is live after GDS import and DRC style loading. The check uses drc(full), Euclidean checks and complete original powered GDS geometry, and writes micron-scaled rule rectangles. As the PDK helper states, antenna and density are separate checks, not covered by this standard full-style run. Existing independent KLayout DRC session42561 continues unchanged; no DRC pass is claimed while either run is live. Four analog Xyce jobs remain live and unchanged.

Antenna and powered pipeline evidence (2026-10-04): OpenROAD antenna checks on the completed hold-repaired layout report3 net/3 pin violations. The affected nets are FEEDBACK_DIVIDER[0] (met3,hold106/A), _1151_ (met2,_7029_/A0), and acquisition.rail_meta (met2/met3,_8062_/D); all violate side-area ratio400. `hold_candidate_antenna_assessment.json` records them. Reusing the older global segments fails pin coverage for hold134/X; the failed log is retained. Rebuilding fresh global routes from the current geometry and applying the installed PDK diode_2 repair flow inserts10 diodes and reports0 global-route antenna violations. Placement passes with zero displacement; `hold_antenna_repaired.odb/.nl.v` retains a provisional candidate needing PG/filler rebuilding, detailed routing, fresh RCX/timing and a post-route antenna recheck. Global-route results are not final physical signoff.

Pipeline detailed routing completes with zero router violations. The copied characterization shell initially retained the original local_capture directory and regenerated earlier-layout reports/SPEFs; it failed its lookup-warning guard and supplies no pipeline evidence. Correcting its root to config_pipeline produces three pipeline RCX files and six explicit corrected-SPEF characterizations without lookup warnings. The earlier-layout artifacts were regenerated and older hashes for those generated reports are historical. `config_pipeline/powered_timing_assessment.json` records the pipeline candidate's actual routed results, which still fail and do not justify selection or release. Independent Magic/KLayout DRC and four Xyce simulations remain live.

Clean PDK DRC/LVS and antenna candidate (2026-10-04): original powered-layout Magic full-style DRC first reports zero rectangles but its startup log reveals a stale default PDK path. The completed run is retained as `run_stale_pdk.log/errors_stale_pdk.rpt`; it was repeated with explicit PDK_ROOT pointing at the installed Ciel version. The clean run has no startup parse failure, selects drc(full), checks full original powered GDS geometry and reports0 DRC rectangles. This is the installed Magic full-style rule set, excluding separate antenna/density checks, not a claim that the later candidates or all release gates pass. Original-layout transistor extraction was also repeated with the clean PDK root; the fresh Netgen comparison again reports "Circuits match uniquely", with no bad nets/elements in132 named comparisons. KLayout DRC session42561 remains live and was not restarted.

The ten-diode antenna repair is integrated as `pdn_antenna_fixed.odb/.def`. Filler/PG rebuild places11,765 fillers; all73,572 PG pins and both VDD/VSS shape connectivity checks pass. Full detailed routing launches as session64611 and is confirmed live in pin access. Corrected-name three-RC/six-characterization recipes are prepared. This candidate requires final route/antenna recheck, fresh timing and its own DRC/LVS; earlier original-layout passes do not qualify it. Four Xyce jobs remain live.

Post-route antenna, density scope and analog progress (2026-10-04): independent hot-SS half-step code18 completes at450.246362522 MHz (24periods,24–80ns,half-window drift0.021271703 MHz), with completed/hash-matching provenance. `hot_ss_codes161718_independent_settings_assessment.json` pins all completed variant waveforms/decks/provenance. Code17's four independent matched-window variants pass the custom convergence screen: spread0.023122855 MHz and maximum half-window drift0.019920834 MHz are below the conservative measured quarter-LSB0.037062275 MHz. This is not canonical anchor/full-fine/45-PVT calibration qualification; long-window code18 is still live. Three Xyce processes are confirmed live.

Diode-candidate routing session64611 completes; three RCX and six corrected-SPEF timing runs finish without lookup warnings. `pdn_antenna_fixed_timing_assessment.json` retains actual clock-group results. Post-route antenna check reports2 net/pin violations, FEEDBACK_DIVIDER[0]/hold106.A onmet3 and _1151_/_7029_.A0 onmet2. The global-route zero result did not qualify the detailed geometry; `antenna_fixed_postroute_assessment.json` records remaining repairs. Installed PDK density helper required its relative-filename working directory and explicit Magic PATH/PDK_ROOT. It completes but states the layout is smaller than700um x700um and cannot run its window checks. This is a skipped density evaluation, not a pass or waiver; density requires enclosing-layout context. The generated `density_original/check_density.tcl` and log retain scope. Independent KLayout DRC session42561 remains live.

Targeted antenna repair and mapping policy (2026-10-04): physical inspection confirms neither remaining antenna-violating net FEEDBACK_DIVIDER[0] nor _1151_ has a diode. `build_pdn_antenna_targeted.tcl` starts from the completed diode-candidate route, adds one PDK diode_2 near each reported receiver (hold106/A,_7029_/A0), verifies each receiver/net identity, legalizes and rebuilds filler/PG. Placement and VDD/VSS shape connectivity pass; all73,580 PG pins are connected. Routing starts as session72821 and is confirmed live in detailed repair. Fresh post-route antenna and corrected-SPEF characterization recipes are prepared; no antenna/timing pass is inferred from insertion.

The isolated pipeline's actual worst routed PLL path (_8307_ to _8304_) includes two lpflow_isobufsrc_1 cells, with1.669601 and0.860999 ns cell delays. Installed PDK PNR exclusions list probe/lpflow families, but the prior scratch ABC mapping allowed them before resizer exclusions. `config_pipeline_pnr_cells/synth.ys` supplies explicit repeated ABC -dont_use arguments for every matching installed nominal-Liberty cell. Synthesis completes; mapped JSON audit verifies zero probe/lpflow instances. This corrected-policy pipeline mapping remains isolated and unselected pending functional equivalence and physical timing. Repository RTL and existing analog jobs remain unchanged. Independent KLayout DRC session42561 remains live.

Corrected mapping timing/equivalence follow-up (2026-10-04): PNR-cell-policy pipeline mapping completes an SS estimated-placement screen (about-0.10ns worst setup) and CTS/placement screen (reported setup deficits include-0.216736ns); these are estimated diagnostics, not routed qualification. `config_pipeline_pnr_cells/mapping_equivalence.ys` compares the previous pipeline mapping and the excluded-cell mapping using imported Liberty functions, simcell lowering and clock-event FF semantics. The blacklist avoids matching auto-numbered mapping nets and flattened cell-pin wire names between independently mapped designs, while functional RTL signals/output comparisons remain. Session58775 is confirmed live in SAT equivalence checking; no completed proof is claimed. Targeted antenna route session72821 remains live in repair; three Xyce jobs remain live. Independent KLayout DRC session42561 remains live. The corrected mapping is not selected and repository RTL is unchanged.

### Corrected mapping and targeted antenna verification (2026-10-05)

The isolated `config_pipeline_pnr_cells` mapping passed all 1,696 functional equivalence cells. Its powered CTS candidate passes placement and power-grid connectivity with 76,496/76,496 connected power pins; detailed routing is underway. This remains an unselected candidate pending extracted timing and physical verification.

The `local_capture/pdn_antenna_targeted_route.odb` completed detailed routing with zero routing violations and independently reports zero post-route antenna net/pin violations. Six explicit-SPEF TT/SS and nominal/minimum/maximum RC diagnostic timing runs completed without STA name-lookup warnings. All reported hold-group minima are positive (worst 0.103256 ns), but SS maximum-RC PLLOUT setup remains -1.314717 ns and recovery -0.174944 ns; slew/capacitance violations also remain. These results are pinned in `pdn_antenna_targeted_timing_assessment.json`. Antenna closure does not establish release readiness; this geometry still needs independent DRC/LVS and full PVT qualification.

All three pending analog sweeps completed. Final code measurements are cold-FF coarse 3/code 75: 450.4633666066818 MHz (12–40 ns); hot-SS coarse 0/code 18: 450.24976509075606 MHz (48–160 ns); nominal coarse 1/code 208: 400.348306537984 MHz (80–160 ns). These custom-window diagnostic sweeps do not replace canonical calibration qualification.

The completed hot-SS long-window code 18 result has now been incorporated into `hot_ss_codes161718_independent_settings_assessment.json`, with terminal provenance and deck hash verified. Codes 16/17/18 all pass the four independent custom-settings screen: frequency spreads 0.022313252/0.023122855/0.025246271 MHz, all below the conservative quarter-local-LSB limit 0.037062275 MHz. This is not canonical/PVT qualification. Antenna-targeted GDS stream-out completed with every LEF cell matched to GDS; its independent full-style Magic DRC is running. The corrected-mapping detailed route remains active.

The antenna-targeted GDS independent Magic full-style DRC completed successfully with `MAGIC_DRC_RECTANGLES=0`. The final routed database additionally passes power connectivity (73,580/73,580 PG pins and connected VDD/VSS shapes), and the powered netlist was emitted for independent LVS. LVS extraction is active in a clean dedicated directory with the installed PDK explicitly selected; no LVS match is claimed yet. Evidence is pinned in `antenna_gds_convergence_evidence.json`.

The antenna-targeted GDS now additionally passes independent LVS: Netgen reports “Circuits match uniquely,” and all named JSON comparisons have no bad nets or elements. The intentional TRACKING/BBPD_RESET_N port alias is retained via extraction short resistors and matches on both sides. This candidate has passing Magic full-style DRC, LVS, power connectivity, and post-route antenna checks, but still fails diagnostic SS setup/recovery and electrical slew/capacitance constraints. These physical passes do not establish full-release qualification.

The corrected `config_pipeline_pnr_cells` candidate completed detailed routing with zero final violations. All six explicit-SPEF diagnostic timing runs completed without STA lookup warnings. SS maximum-RC PLL setup is -1.709390 ns, recovery -1.722201 ns, REF setup -4.114028 ns, Fine hold -2.733343 ns and REF hold -0.919013 ns. TT maximum-RC PLL setup is -0.134796 ns and Fine hold -1.645650 ns. Thus removal of excluded LP/probe cells alone does not close timing. The SS PLL path runs from _8350_ through _3957_/Y, _3958_/Y, _3959_/Y, _3960_/Y and _3961_/Y to _8354_; clock-to-Q is 1.248947 ns. Extracted-parasitic electrical/setup repair is active on this isolated candidate. The selected repository RTL remains unchanged by this candidate work. `pdn_filled_timing_assessment.json` pins the routed geometry, timing logs, normalized SPEFs and proof recipe.

The corrected-mapping extracted-parasitic repair completed: electrical repair resized 409 instances and inserted two buffers; setup repair resized 23 instances, inserted five split-load buffers, swapped five cell pins and cloned five instances. Its provisional WNS remains -1.342 ns with setup violations, so no timing closure is claimed. The repaired geometry passes placement and rebuilt power connectivity (75,032/75,032 PG pins; VDD/VSS shapes connected). Fresh detailed routing and functional equivalence against the formally proven corrected mapping are active, with a dedicated signal-only repaired netlist and separate extracted-timing recipes. `extracted_repair_stage_evidence.json` pins the stage inputs and outputs.

Repaired corrected-mapping functional equivalence completed successfully: all 1,665 equivalence cells proven, zero unproven. Fresh routing remains active. A canonical hot-SS (SS/1.62 V/125 C) 450 MHz coarse-0/code-17 qualification campaign has been launched in `canonical_hot_ss_450_c0_code17` using default 100 ns settling/200 ns measurement, reltol 1e-5/abstol 1e-9, independent tighter tolerance, half timestep, doubled settling/window and full fine-code interpolation verification. This is one PVT point only; campaign success and remaining 45-point qualification are not claimed. Python source changes must wait until the campaign terminates to preserve provenance.

An isolated `config_pipeline_boolean` candidate combines the already tested optional configuration pipeline with direct Boolean terminal decode, retaining PNR-family exclusions during synthesis. The terminal bit-zero expression bypasses the serialized ratio clamp/subtractor identified in the corrected-mapping setup failure. Its independent divider model passes all 32 ratios and 4,000 live configuration changes. Full acquisition regression and synthesis are active; no timing improvement or candidate selection is claimed. Repository RTL is unchanged, and analog-campaign Python sources remain untouched.

The pipelined Boolean terminal-decode candidate synthesized successfully with zero excluded LP/probe-family instances. Its clock root is _8384_/Q. A same-constraint slow-library placement timing screen gives PLL setup -0.082234 ns, still negative; the worst reported path now begins at _8357_ and ends at _8381_. CTS characterization is active. Acquisition regression is still running, and neither this preliminary screen nor synthesis establishes routed timing or candidate selection.

Fresh repaired corrected-mapping routing completed with zero final violations. The first timing batch was rejected by the STA name-lookup guard because copied recipes read raw SPEFs; its logs are retained in `repaired_timing_raw_spef_rejected`. All six recipes now explicitly read narrowly normalized SPEFs, and the completed rerun has no STA-1648/1650 warnings. The resulting SS maximum-RC PLL setup is -1.344358 ns, recovery -1.236323 ns, REF setup +5.002072 ns, Fine hold -2.647421 ns and REF hold -0.916101 ns. Repair improves setup but does not qualify timing. Full results and source hashes are in `pdn_repaired_filled_timing_assessment.json`. The separate Boolean candidate passes power connectivity (76,440/76,440 PG pins) and is undergoing detailed routing and mapped functional equivalence. No proof completion is claimed for that candidate.

A two-reset-buffer upsizing screen (split98 buf6→buf16 and split93 clkbuf2→clkbuf16) improves modeled SS recovery only from -1.236323 to -1.216247 ns and fails placement after the larger-master substitution; it is unselected and produces no valid new physical candidate. Expanded propagated-clock/slew/fanout reports are being generated to distinguish clock-slew and reset-distribution delays. The initial Boolean proof was deliberately terminated after detecting incorrect automatic IQ/IQ_N state matches across numbered mapped cells; its rejected log is preserved. The revised recipe excludes these implementation-only state names while retaining RTL signal/output comparisons and is active. Neither a Boolean proof pass nor a reset fix is claimed.

### Isolated 450 MHz timing-plan implementation (2026-10-05)

`verification/timing450/` now contains a candidate RTL overlay and a pinned
HD/HS synthesis, placement, CTS, PDN, routing, extraction and verification
flow. Divider ratio/terminal pipelining and separate equivalent reload-control
FFs reduce shared loads. Balanced Gray decoding is registered on REFCLK;
measurement endpoints retain equal latency. Scan elapsed edges are captured
before a separate ranking cycle, with five settling cycles. Retimer and reset
roots are isolated physically, and stronger cells are available in a private
HS PDK overlay. The approved shared supply ceiling is 1.95 V in
`verification/engineering.json`; the target remains 450 MHz.

Functional checks pass: all 65,536 Gray values with one-cycle latency, scan
ranking/cancellation, the full acquisition/CDC/reset regression, 82 divider
formal comparisons, and 1,268 mapping comparisons for each library. Physical
proof of each port-repaired candidate passes 916 comparisons using explicit
original-FF Q correspondence and every public port. Gate-level regression at
phase offsets 7 ns and 0 ns passes all five modes, mode changes, reset/disable,
BBPD gain/polarity and disturbance recovery for both libraries. These gate
runs are functional simulations without SDF. Observed gate acquisition is
below 127 us and disturbance recovery below 146 us, within the 200 us bound.

The HD port-repaired candidate has zero router violations, zero independent
Magic full-style DRC rectangles, and a unique transistor-level Netgen LVS
match. The HS port/retimer-cluster/BBPD-data-guard candidate also has zero
router and Magic DRC violations and a unique LVS match after adapting the
pinned tie-cell SPICE primitive. The private HS Verilog views required
malformed-declaration and supply-connection repairs; missing legacy helpers
map to the supplied HS UDP tables. Source originals, revisions and installed
view hashes are retained. These adapters do not alter Liberty, LEF or GDS.

Fresh three-corner by three-RC reports cover all five modes, without SPEF
name-lookup warnings. Before the additional HS critical-cell sizing repair,
450 MHz SS/max-RC setup is -1.593968 ns for HD and -0.986203 ns for HS;
functional reset recovery is -1.343452 ns and -0.612653 ns respectively.
HS SS/max-RC FINE hold is +0.048006 ns and REF hold -0.259504 ns. These are
failing diagnostic screens. HD at 400 MHz still has -1.316190 ns setup and
-0.270239 ns FINE hold, so reducing the target does not establish closure.
The additional HS sizing route is a separate candidate pending fresh checks.

Only one of 45 required PVT points has an exact supplied HD/HS timing model;
225 mode/PVT combinations remain the release requirement. All candidate
assessments retain `selected: false` and `release_qualified: false`. Complete
PVT, interface/pulse/CDC characterization, antenna/density/EM/IR and whole-PLL
analog qualification remain required. No candidate is promoted to selected
RTL. The historical full KLayout DRC and canonical hot-SS analog calibration
remain separate live campaigns; baseline PDK contents and `scripts/*.py`
were preserved.

The HS critical-cell sizing route completed with zero router violations and
passed all 916 physical equivalence comparisons, both gate-regression phases,
Magic DRC (zero rectangles), and unique transistor LVS. Fresh SS/max-RC setup
worsened to -1.868308 ns because shared tracking-control hold delay became a
setup bottleneck; recovery was -0.840150 ns. That geometry and its evidence
are retained in `build/timing450/hs/initial_route` as the input to the next
repair, rather than treated as closure.

HS extracted repair starts from explicit min/nom/max SPEFs in all nine supplied
cell/RC combinations. It strengthens reset roots and weak reported max-path
cells, performs electrical/setup/hold repair, and reroutes without replacing
that repair with another optimization against estimated routing parasitics.
The final route has zero router violations, zero Magic DRC rectangles, a
unique Netgen transistor LVS match, and 76,824/76,824 connected PG pins with
continuous VDD/VSS shapes. Fresh physical equivalence passes 916/916; both
gate phases pass again. Every reported hold/removal/bundle minimum across the
nine 450 MHz screens exceeds the 0.05 ns margin; the worst is +0.063846 ns.

450 MHz SS/max-RC setup improves to -0.718819 ns and recovery to -0.418278 ns,
while FINE setup is +0.488707 ns and REF setup +21.987598 ns. The new worst
setup path runs from `handoff.capture_pending` (`$auto$ff.cc:337:slice$17159`)
to `handoff.remaining` (`$auto$ff.cc:337:slice$13764`), including `hold1252`; worst recovery runs from
`$auto$ff.cc:337:slice$16711` through the reset distribution and cloned branch
to `$auto$ff.cc:337:slice$17004/RESET_B`. Electrical violations and 22 antenna
net / 24 pin violations remain. Fresh reports at all five modes are complete;
400 MHz still has SS/max-RC setup -0.441041 ns and recovery -0.140500 ns.
Thus the implementation is functionally verified but timing is not closed,
and lowering to 400 MHz alone does not qualify it.

The final routed database is SHA-256
`a17edbff90064e3ab3803ed5abb0ba5b23cdc49f4cd7d3de573d200e5806d26a`.
Timing, gate, physical-proof and signoff assessment files pin their own inputs
and logs. The candidate remains unselected, with release qualification false.

### Supplied-model closure ECO implementation (2026-10-05, in progress)

The HS-only `--repair-closure` operation archives each physical input, flow
snapshot, model hash, sizing journal and output timing report under
`build/timing450/hs/closure/iteration_NNN`. Repairs evaluate all nine supplied
cell/RC combinations, preserve clock roots and exported/pulse-guard branches,
and keep the 450 MHz target and original timing assumptions. The special
0.35 ns hold target is replaced by the agreed 0.05 ns acceptance margin.

Iteration 004 routed with zero router violations. Its extracted SS/max-RC
setup is -0.965457 ns and recovery -0.367913 ns; worst nine-screen hold is
+0.070733 ns. Electrical violations remain. This route is **not closed**.
Its database SHA-256 is
`7e4f95c92fc1498c99a88887edd90adce8f751791fe375c2ec17d8f40c64728a`.
The pre-route ECO passed all 916 physical equivalence comparisons and both
functional gate phases. These ECO checks do not replace final routed proof,
gate regression or independent signoff.

Reset-buffer discovery now includes parenthesized Liberty functions, compound
buffers and clock-buffer masters used on data/reset nets. Actual clock
connectivity determines protection. Three reset sources distribute to 861
sinks through bounded local banks. Data drivers may be replicated with equal
register latency; synchronizer and reset-release FFs are excluded.

The structural audit found inherited hold buffers between synchronizer
stages. A separately archived prototype restores direct same-domain links
using corner-checked local launch-clock branches and passes 916 formal
comparisons. Cross-domain first-stage inputs are excluded from this direct-link
test. The audit also rejects incomplete timing coverage, stale hashes and
unannotated functional drivers. Twelve repair-flow unit tests pass, including
declared open dummy outputs, unused constant-driver outputs and clock-net
classification checks against the actual routed database.

An isolated HS cell sweep at 1–90 fF confirmed that maximum strength does
not always minimize delay. Sizing now considers both directions within the
same FF family and checks receive D/reset arcs together with launched output
paths. Two real OpenROAD fixtures pass using the three supplied cell models:
at 20 fF, dfrtp_4→dfrtp_2 improves local max slack by 49 ps; a setup-limited
receive case selects dfrtp_1 while preserving hold. These are repair-selection
checks, not routed candidate qualification.

The routing repair now compares pre/post-ECO connection and pin-geometry
signatures after legal placement. It clears changed nets and retains other
ordinary wires as mutable router input. Isolated OpenROAD checks retain all
6,775 wires for a no-op, clear exactly four FF-connected nets after master,
location or orientation changes, and clear exactly two nets after a connection
change. An existing-wire reroute reaches zero DRC at pass 3 with a byte-identical
netlist. These checks preserve their inputs under iteration 007's input archive;
the next actual ECO still requires fresh timing and independent signoff.
An additional buffer sweep selects buf_16 at the tested reset-bank loads and
input slews, including rising reset deassertion edges.

Iteration 005 was stopped before routing to extend data-FF replication to
overloaded two/three-load sources. Iteration 006 replays its 47 checked sizing
changes, restores 28 direct synchronizer links, removes 57 receiver-delay
buffers, and applies targeted combinational/reset-root placement changes.
Its pre-route ECO passes all 916 formal comparisons, both gate phases and the
direct-receiver structural check. Its route was stopped during pass 53 after
an extended run at five remaining violations; no output geometry was adopted.
The iteration 006 pre-route ECO stored the new local launch-clock output
nets as signals. The current flow marks them as clocks explicitly. Inspection
of the pinned OpenROAD source confirmed that global routing already recognizes
clock nets automatically and permits leaf clocks on signal routing layers;
the pre-route metadata was not evidence of a clock-layer routing violation.
Iteration 007 resumes the verified ECO with all 28 local clock branches marked
as clocks and a bounded routing run. The recovery
recipe validates both passing netlist assessments, the unchanged physical
parent and the model hashes, and records its own checkpoint hashes. It saves
a routed result after at most 32 passes for fresh timing and DRC assessment.
Iteration 007 completed routing and fresh nine-screen extraction. Its worst
450 MHz setup slack is −0.631297 ns, recovery −0.633541 ns, and hold
+0.041910 ns, with 82 router DRC violations. It is not timing closed or
physically qualified; the other four mode reports and independent physical
assessments have not been refreshed for this geometry.

The first-stage hold repair was blocked by protection that treated all
ASYNC_REG connections alike. Protection now follows original same-clock
receiver pairs, permitting repair at cross-domain first-stage inputs. An
isolated parallel clock-leaf trial on the two worst PLL launch FFs improves
their estimated local max slacks from −0.633537/−0.625138 ns to
−0.185052/−0.182939 ns without reducing global hold. Other max paths remain
open. The trial uses the original clock parent and retains the original root.
Its isolated ECO passes all 916 formal comparisons and functional gate
simulation at both 7 ns and 0 ns phases. The hash-pinned assessment is
`build/timing450/hs/closure/launch_probe/assessment.json`; it explicitly
retains routed-timing qualification as false.
Iteration 008 recorded 85 corner-checked sizing changes and was stopped
before adopting any geometry, to measure that batch rather than continue
unsuccessful sizing trials. Its journal and unchanged parent hash are pinned
in `stopped.json`. Iteration 009 replays the journal on the identical parent
and models, rechecks global max/min against the parent's margins, and combines
the other repairs with routing reuse. Failed local sizing improvements now
skip expensive global searches; accepted trials retain the same guards.
Fresh extraction and equivalence are required before any qualification claim.
The iteration 009 ECO passes all 916 formal comparisons and both gate
phases. Its second global-routing pass stopped with seven overflow units
under the 50% met2/met3 capacity reservation. Iteration 010 resumes this
verified ECO with a 20% reservation, as recommended by the router. The resume
recipe pins the parent geometry, model hashes, ECO, proof assessments and
original wire signatures. Timing constraints remain unchanged.

A separate, unselected wrap-prediction prototype is retained under
`build/timing450/hs/wrap_predictor`. It registers the counter-high predicate
and configuration predicates to remove the counter-high decode from the wrap
flag's combinational path. Formal induction compares all 56 original divider
state bits and output phase, with five supporting invariants and unrestricted
live ratio changes after initial reset. Both registered/unregistered countdown
regressions pass. Synthesis succeeds, and the mapped wrap-input cone contains
the registered high predicate rather than counter bits 2–4. This is functional
and structural evidence only; the prototype has no routed timing qualification
and has not been adopted into the active candidate or root RTL.
Root RTL, baseline PDK and canonical campaign scripts are
preserved. Missing PVT models and full release qualification remain separate
gates; no candidate is selected.

### Handoff timing overlay and routed trials (2026-10-06)

The timing-only handoff overlay registers `transfer_busy`, with the invariant
`transfer_busy == (capture_pending || remaining != 0)`. Request qualification
uses this register instead of the capture-pending/counter-zero decode. Payload
capture and acknowledgement cycles remain identical. Root RTL is preserved.
`make -f verification/timing450/Makefile handoff` checks that the source-domain
always block is byte identical and proves every original destination state bit,
output and busy invariant after reset, with unrestricted payload, request and
subsequent reset inputs. Formal induction and the handoff regression pass for
WIDTH=34 and APPLY_CYCLES=1,2,3,4. Evidence and hashes are in
`build/timing450/handoff_proof/assessment.json`.

A separate full implementation is under
`build/timing450/hs/closure/handoff_candidate`. Synthesis, placement and CTS
complete; the full PLL RTL regression passes at phases 7 ns and 0 ns, including
all five modes and disturbance recovery. This candidate is unselected and
requires fresh routed extraction, all timing screens and final physical checks.

Completed iteration-009 full reroutes are rejected: the 50% met2/met3
reservation trial has SS/max-RC setup -1.259550 ns, recovery -0.104901 ns,
worst minimum +0.080069 ns and 2,918 router violations. The 20% trial has
setup -1.467244 ns, recovery -0.064011 ns, worst minimum +0.079256 ns and
4,026 violations. The retained-wire iteration-010 run was stopped at
iteration 10 with 3,345 violations; its original root geometry was verified
unchanged and `stopped.json` records the reason and hashes.

The small ECO with unchanged cells temporarily fixed during legalization
retains 6,930 cells and clears only 18 original wires. It finishes with 46
router violations, SS/max-RC setup -0.715267 ns, recovery -0.487661 ns and
worst minimum +0.077314 ns. It is also unselected. New cells move as far as
149.7 um, so placement preservation alone does not provide timing closure.
A local-neighbor legalization experiment remains build-only. The ordinary
legalization variant finishes with 665 router violations, SS/max-RC setup
-0.731315 ns, recovery -0.257648 ns and worst minimum +0.077843 ns. It is
also rejected.

The root physical checkpoint remains iteration 007: SS/max-RC setup
-0.631297 ns, recovery -0.633541 ns, worst minimum +0.041910 ns and 82
router violations. These are failures against the agreed +0.10 ns maximum
and +0.05 ns minimum margins. Older all-mode/signoff reports do not qualify
this geometry. No timing or release qualification is claimed.


The isolated handoff candidate iteration 000 now has fresh 450 MHz nine-screen
extraction: worst PLL setup -0.440024 ns, recovery +0.093271 ns and minimum
+0.066404 ns. Router and Magic DRC are zero; unique transistor LVS, all 918
routed equivalence comparisons, gate phases 7/0 ns and all 81,294 PG pins pass.
The PG repair temporarily releases protection only for instances with missing
supply connections and verifies preservation of signal topology and protection.
Antenna remains 19 nets/20 pins. Setup/recovery/electrical failures prevent
selection; all-mode qualification remains outstanding. Iteration 001 targets
the newly measured decision logic and electrical drivers, with fresh routing
required before any acceptance. The root iteration-007 route is unchanged.


Iteration 001 adds bounded all-nine-screen cell sizing and local electrical
banks. A signal `clkinv` omitted by the candidate filter was included; clock
cells remain protected. A second sizing pass produces the accepted trial
netlist `inverter.v`. Its full reroute finishes with zero router DRC. Fresh
450 MHz extraction gives worst PLL setup -0.067084 ns, recovery +0.075227 ns
and worst minimum +0.078769 ns. The counter setup path, a state-FF output
capacitance violation and a logic-driver slew violation remain. These fail
closure; this checkpoint is diagnostic and unselected. The preceding
`route_margin` run was stopped before completion and supplies no evidence.
Iteration 002 continues from the fresh iteration-001 route; root geometry
remains unchanged.


Iteration 002 routes cleanly and its fresh 450 MHz screens give PLL setup
-0.023444 ns, reset recovery +0.201845 ns and minimum +0.082372 ns. Routed
formal equivalence and both gate phases pass. The reporting command now uses
`-violators`: the earlier reports exposed only the worst electrical row per
type. The complete SS/max report contains 4,870 violated pin rows, so this
route is still unqualified despite its improved timing and zero router DRC.
Iteration 003 trials broad electrical sizing, guarded hold repair and local
residual banks. Native placement-estimate setup sizing crashes in the pinned
router callback and is not accepted; failed/stopped trials are recorded.
The combined trial is routing and requires fresh extraction, all five modes
and physical checks before selection. Root iteration 007 remains unchanged.


The completed iteration-003 diagnostic route has zero router DRC, fresh
450 MHz PLL setup +0.048786 ns and recovery +0.160270 ns, but its minimum
+0.011068 ns misses the hold floor. Routed formal equivalence and both gate
phases pass. Complete electrical reports still fail; the route is unselected.

Iteration 004 duplicates the BBPD seen register without changing its clock,
reset, input or latency. The pre-route netlist passes all 918 equivalence
comparisons and both gate phases. The completed met1 route has zero router
DRC and all 45 mode/corner reports are fresh on that geometry: worst PLL
setup at 450 MHz is +0.048656 ns, recovery +0.152917 ns and worst minimum
+0.069207 ns. The slow max/min screens contain 70/39 electrical violation
rows. Routed formal equivalence passes all 918 comparisons. This route fails
qualification: setup is below +0.10 ns and electrical violations remain.
Independent PG checking also finds a protected clock leaf with the wrong
row orientation, despite all 75,078 supply pins having logical connections.
The met2 routing trials were stopped without accepted routed checkpoints.

The flow now corrects protected ECO clock-leaf row orientation before
invalidating changed signal wiring, and checks physical VDD/VSS connectivity
before final routing. Verification invalidates old physical/gate assessment
files before reruns, and electrical reports request every violated pin row.
A separate met1 trial combines measured paired receive-FF sizing, acquisition
gate sizing, midpoint electrical banks and endpoint hold repair. Its estimated
maximum/minimum are +0.077799/+0.083656 ns; these are not extracted results.
Fresh extraction rejects that broader ECO: setup -0.041443 ns and minimum
+0.033354 ns miss both floors. Its zero router/Magic DRC, formal/gate passes,
unique LVS and connected supplies do not override the timing failures.

A narrower repair starts from the completed met1 route, preserves placement,
aligns one clock leaf to its row and invalidates only its two clock nets. It
finishes with zero router DRC and fresh 450 MHz setup +0.048415 ns, recovery
+0.152930 ns and worst minimum +0.072265 ns. All 918 routed formal comparisons
and both functional gate phases pass; disturbance recovery is about 145.5 us.
Magic DRC is zero, unique transistor LVS passes, and all 75,078 supply pins
are connected logically and physically. Setup still misses +0.10 ns, the
slow min/max reports contain 40/73 electrical violation rows, and 13 antenna
net/pin violations remain. All-mode reports and the final audit record these
failures. The candidate stays unselected and unqualified.
Root iteration 007 remains unchanged; no closure or release claim is made.

BBPD/handoff implementation trial (2026-10-06): the timing overlay captures
pending requests while idle and acknowledges directly on the final count;
compositional formal proof and regression pass for APPLY_CYCLES 1 through 4.
The isolated physical trial factors BBPD decisions into HS AND-OR gates and
sizes the measured remaining-count/BBPD receive paths. Its final frozen route
has fresh 450 MHz setup -0.109634 ns, recovery +0.023063 ns and minimum
+0.083912 ns. All 45 supplied model/RC/mode screens complete, with 158 electrical
violation rows at 450 MHz. Router/Magic DRC, unique LVS, both functional gate
phases and all 74,974 supply connections pass; 15 antenna nets/pins remain.
The prior logic trial proves 916/918 full netlist comparisons, leaving
acknowledge/pending-request unproven; the final sizing geometry has no full
formal qualification. Selected RTL remains unchanged. Current evidence is
`build/timing450/implementation_assessment.json`; the earlier PG-only assessment
is preserved separately as `implementation_assessment_pg_only.json`.

Receiver/reset iteration 005 (2026-10-06) strengthens the measured handoff
cells, splits the event-reset fanout into four buffer banks, and separates
tracking-state data fanout from its reset path without cloning a synchronizer.
An inverted-input NAND replaces the acknowledgement decode's inverter/NAND
pair. Fresh extraction on the completed route gives 450 MHz setup
-0.221500 ns, recovery +0.214972 ns and minimum +0.083016 ns. All 45 supplied
mode/corner screens complete; the 450 MHz slow min/max screens contain 69/89
electrical violation rows. Router and Magic DRC are zero, unique transistor
LVS and both gate phases pass, and all 74,898 supply pins connect. Fifteen
antenna nets/pins still fail. The joint gate-level proof compares all six
original handoff control state bits and passes its acknowledgement-mutation
negative check. Full physical proof composition passes all 918 comparisons:
916 direct comparisons plus the two acknowledgement/pending-state comparisons
covered by the joint induction proof. The all-mode audit reports no changed
direct synchronizer links, incorrect local clock roles or unannotated
functional pins.
The candidate remains unselected and unqualified. A separate iteration 006
localizes the measured 134 um acknowledgement decode-to-mux connection and
requires its own extraction and verification before comparison.

Iteration 006 completes the acknowledgement placement repair. Fresh 450 MHz
setup improves to +0.005359 ns; recovery is +0.214074 ns and minimum is
+0.083021 ns. All 918 physical equivalence comparisons and both gate phases
pass. All 45 supplied mode/corner screens complete, with zero router/Magic
DRC, unique transistor LVS and all 74,886 supply pins connected. Setup remains
below +0.10 ns, and electrical/antenna checks still fail. Iteration 007 targets
the next measured path: the pending-request register's long feedback-mux
connection. It moves and strengthens that mux without changing register
latency or clock wiring, and requires fresh qualification.

Iteration 007 completes that feedback repair: fresh 450 MHz setup is
+0.076332 ns, recovery +0.203622 ns and minimum +0.083021 ns. All 918
physical equivalence comparisons and both gate phases pass, and all 45
supplied mode/corner screens complete. Router/Magic DRC are zero, unique LVS
passes and all 74,874 supply pins connect; 14 antenna nets/pins remain.
The audit finds no changed direct synchronizer links, incorrect local clock
roles or unannotated functional pins. The candidate still misses the setup
margin and electrical limits. Two smaller BBPD decision-gate trials regress
estimated setup to -0.038679/+0.032103 ns and are rejected by the per-endpoint
guard. A separate iteration 008 keeps the original strengths and moves only
the measured BBPD next-state gate; it needs fresh routed checks.

Iteration 008 produces no timing improvement. Legalization returns the moved
gate to its previous site; the routing journal reports zero changed signal
nets, and fresh 450 MHz extraction reproduces iteration 007's timing exactly.
It is not accepted as a repair. Iteration 007 remains the current fully
verified checkpoint in `build/timing450/implementation_assessment.json`.

Iteration 009 tests an equivalent AOI/inverter decomposition of the limiting
BBPD decision gate. The strength-2 pair passes the preliminary endpoint guard
with +0.115713 ns estimated setup, but fresh extraction rejects the routed
implementation: sampled-delay-to-decision setup is -0.146061 ns. Recovery
and minimum remain +0.203622/+0.083021 ns. Router/Magic DRC, unique LVS, gate
simulation and the six-state handoff proof pass; none overrides setup failure.
The current checkpoint remains iteration 007. Iteration 010 evaluates only
Boolean-equivalent pin assignments on its existing decision gate, preserving
the cell count and register latency.

Iteration 010 swaps the two AND input pairs on the existing BBPD decision
A22O gate. Its Boolean function is unchanged. Fresh routed 450 MHz setup is
+0.135802 ns, recovery +0.203622 ns and minimum +0.083021 ns. All 45 supplied
mode/corner margin screens meet +0.10/+0.05 ns, all 918 equivalence comparisons
and both gate phases pass, and the audit finds no changed direct synchronizer
links, incorrect local clock roles or unannotated functional pins. Router/Magic
DRC are zero, unique LVS passes and all 74,874 supply pins connect. Electrical
checks still contain 143 violated pin rows and 14 antenna nets/pins remain,
so the candidate is unselected and unqualified. Iteration 011 separately
repairs the 18 data drivers responsible for those rows: seven compatible
strength increases and eleven buffered output branches. Its preliminary
check preserves every maximum-margin floor and +0.083021 ns minimum; fresh
routing and extraction are required before accepting it.

Iteration 011 reduces electrical violations from 143 to 35 pin rows, but
fresh extraction gives setup +0.061865 ns, below the +0.10 ns floor. Recovery
is +0.168886 ns and minimum +0.078460 ns. Both gate phases, the handoff control
proof, router/Magic DRC and unique LVS pass; all 74,702 supply pins connect.
The routed database retains every original FF and named BBPD placement.
Critical BBPD data wires also retain identical encodings, while their
extracted capacitances change with surrounding routing; clock routing changes
as well. The trial is unselected, with 16 antenna nets/17 pins remaining.
Iteration 012 evaluates equivalent XOR, A21O and AND input permutations on
this electrical-repair geometry. Swapping the XOR and A21O inputs estimates
+0.141114 ns setup and preserves all endpoint floors and +0.078460 ns minimum.
It requires fresh routed checks before acceptance.

Iteration 012 improves the electrical-repair geometry's fresh routed setup
from +0.061865 to +0.083562 ns, but still misses the +0.10 ns floor. Recovery
is +0.177157 ns and minimum +0.078460 ns; 35 electrical violation rows remain.
Both gate phases, the six-state handoff proof, router/Magic DRC and unique LVS
pass; all 74,702 supply pins connect. This trial is not accepted. Full physical
equivalence and the other mode screens have not been run for this rejected
geometry. Iteration 010 remains the fully verified timing checkpoint.

Iterations 013 and 014 test alternate strengths without accepting a change.
Changing the seen-state register from strength 2 to 1 or 4 gives preliminary
setup -0.156596 or +0.058176 ns. Changing its data AND gate from strength 4
to 1 or 2 gives -0.109398 or +0.012214 ns. Each fails the endpoint guard;
none is rerouted or promoted. Iteration 015 retains the original strengths
and reroutes the four measured limiting data nets with met2 as the minimum
signal routing layer. Its routed geometry needs fresh extraction and checks.

Iteration 015 recovers the setup floor on the electrical-repair geometry.
Fresh routed 450 MHz setup is +0.115192 ns, recovery +0.177114 ns and minimum
+0.078460 ns. All 45 supplied mode/corner margin screens meet +0.10/+0.05 ns.
All 918 equivalence comparisons pass (916 direct and two composed through
the independently proven handoff control); both gate phases pass. Router and
Magic DRC are zero, unique LVS passes and all 74,702 supply pins connect.
The audit finds no changed direct synchronizer links, incorrect local clock
roles or unannotated functional pins. This is the current fully verified
checkpoint in `build/timing450/implementation_assessment.json`.

Electrical violations are reduced from 143 to 35 pin rows; 16 antenna nets
and 17 pins remain. The candidate remains unselected and unqualified. The
model inventory supplies only one exact point of the required 45-point PVT
grid, and interface characterization, independent full physical signoff and
whole-PLL qualification remain open. Iteration 016 separately reroutes the
six remaining electrical problem-driver nets with unchanged logic and
placement; it must pass fresh extraction before acceptance.

Iteration 017 prepares a separate antenna trial from the verified iteration
015 geometry. The detailed antenna report identifies 17 violated pins; the
trial adds 16 HS diode cells beside the corresponding data gates. It skips
`fine_signal_output_out`, whose actual database role is CLOCK despite its
violated sink being a data pin. Clock connections and register latency are
unchanged. Diode placement, routing, extracted timing, transistor LVS and
antenna checks are required before accepting this trial; no antenna closure
is claimed from diode insertion alone.

Independent KLayout DRC on iteration 015 completes with zero markers across
261 categories. All FEOL, BEOL, off-grid, floating-metal and seal options are
enabled; SRAM exclusion is disabled. The populated GDS has 69,569 top-level
instances and 199 cells, and its checksum matches the candidate's signoff
input. The separate PDK global minimum clear-area ratio deck also passes on
all six layers with finite ratios. That deck checks global upper metal-density
limits; it does not establish complete windowed minimum/maximum density
qualification. Pinned reports and assessments are under the candidate's
`signoff/klayout_full` directory. Electrical, antenna, density/EM/IR, full PVT,
interface and whole-PLL gates remain open.

The repository now exposes the candidate-owned `klayout` target through
`verification/timing450/verify_klayout.py`. It validates signoff GDS/database
hashes and populated geometry, executes the pinned full DRC and global
clear-area density decks, rejects incomplete reports and invalid ratios, and
pins the exact commands, reports and source. All 23 verification tests pass,
including stale-input and false-green evidence guards. The new command
reproduces both passing KLayout results on iteration 015. This adds a
repeatable physical gate without claiming full density or release qualification.

Iteration 018 prepares an independent electrical repair from iteration 015.
Native topology checks confirm DLF_CODE[7] still loads the original O31AI gate,
while its existing BUF16 branch serves an internal sink. The trial moves only
that output port onto the existing buffer output and strengthens two compatible
data gates. It retains register latency and clock connections, and routes the
changed data nets with met1 available. Fresh extraction and full functional
checks are required before accepting the geometry; routing is still live.

Iteration 018's fresh setup is +0.117037 ns, but exported Verilog and powered
schematic checks reject it: the original internal net retains DLF_CODE[7]
after that output port moves to the buffer output, merging two drivers in
the exported views. Gate simulation, the global driver guard and LVS catch
the error. The trial is rejected and its evidence is preserved.

Iteration 019 corrects only that internal net name. Native fingerprints of
all signal-wire encodings, placements and pin/port connectivity match before
and after renaming. Fresh extraction preserves +0.117037 ns setup and gives
+0.078459 ns minimum; electrical violations fall from 35 to 25 rows. The
six-state handoff proof and its negative control pass. Full equivalence,
gate simulation, all-mode timing and independent physical checks are required
before accepting this corrected candidate. Iteration 015 remains the current
fully verified checkpoint while those checks run.

Iteration 019 completes functional, margin and DRC checks on the supplied diagnostic models.
All 45 margin screens, 918 equivalence comparisons, both gate phases, router
and Magic DRC, unique transistor LVS and repeatable full KLayout DRC pass.
All 74,690 supply pins connect. The PDK global clear-area density deck
also passes, and the audit finds no altered direct synchronizer links,
incorrect clock roles or unannotated functional pins. Fresh 450 MHz setup,
recovery and minimum are +0.117037, +0.179766 and +0.078459 ns.
Iteration 019 is now the fully verified checkpoint; iteration 015's assessment
is archived separately. It remains unselected and unqualified because 25
electrical rows, 16 antenna nets/17 pins and the broader release gates remain.

Iteration 020 targets the five drivers responsible for the remaining rows:
four BUF16 branches and one compatible XNOR strength increase. Native checks
show no clock sinks or output ports on these branch nets. The trial preserves
register latency, protects the clock cells and routes the changed data nets
with met1 available. It requires fresh extraction and verification before
acceptance; the trial is separate from the current checkpoint.

Iteration 020 meets timing margins (+0.128962 ns setup, +0.197958 ns recovery,
+0.075427 ns minimum), with passing gate/control, router/Magic DRC and unique
LVS checks. Its original five problem-driver nets clear, but electrical rows
increase from 25 to 28 and worst SS/max slew increases from 1.07 to 1.38 ns.
It is rejected; full physical equivalence and other mode screens are not run
for this rejected geometry. Iteration 019 remains the verified checkpoint.
Iteration 021 repeats the branch repair with BUF8 cells and freezes every
unchanged placement during legalization, aiming to avoid collateral routing
and loading changes. It requires fresh routed checks before acceptance.

Iteration 021 freezes every unchanged placement and uses compact BUF8 branches.
Fresh setup is +0.117090 ns, recovery +0.179774 ns and minimum +0.078459 ns.
All nine 450 MHz reports contain zero maximum-slew, maximum-capacitance or
minimum-pulse violations. All five supplied-mode diagnostic timing/electrical
screens pass. Both gate phases, the six-state handoff proof, router/Magic
DRC and unique transistor LVS pass. Full equivalence and independent KLayout
checks are still required before recording this as the current checkpoint.

Iteration 022 prepares antenna diodes at all 17 violated pins on the 16 nets
reported by iteration 021. It freezes every existing placement and uses met1
for signal routing. The one shared clock/data net, fine_signal_output_out,
is explicitly identified and receives a diode at its data sink; its clock
connections are unchanged. Fresh extraction must check the additional load,
including minimum pulse widths. No antenna closure is claimed before the
routed audit. The exported-output alias failure now has a dedicated regression
that requires the global driver guard to reject a short outside the handoff
control cone; all 24 verification tests pass.

Iteration 021 is now the current verified diagnostic checkpoint. Full physical
equivalence proves 918 comparisons (916 directly and two through the pinned
six-state induction proof). Independent KLayout full DRC reports zero
violations and the global clear-area density deck passes. Refreshed reports
and their audit pass after the regression source update. All 45 supplied
mode/corner timing, electrical and pulse screens pass. Antenna remains at
16 nets/17 pins; full PVT and broader release qualification remain outstanding.

Iteration 022 reduces antenna to one net/pin but is rejected as a checkpoint:
retimed clock output setup is +0.068116 ns, below the +0.100 ns floor. Its
passive diode also exposed a missing Boolean formal-library model and a
legacy SPICE primitive/geometry mismatch. The formal-only input load model
preserves strict unknown-port rejection; the expanded regression passes
26 tests. No transistor LVS waiver or geometry substitution is applied.
Iteration 023 separates the retimed output onto a dedicated BUF16 clock
branch from the original FF Q and adds a second diode on thermal_code[31].
It preserves original register latency and freezes unchanged placements.
Routed extraction and qualification are required before acceptance.

The formal diode loader now passes native handoff induction and its negative
control. An independent KLayout measurement of the original HS diode GDS
shows diffusion/diode-marker area 0.6417 um2 and external perimeter 3.24 um;
the legacy schematic claims 7.32 um (including 4.08 um of contact boundaries).
A strict candidate-local schematic correction preserves terminal order,
checks the actual library GDS geometry and uses the installed 05v5 primitive
with area/perimeter parameters in its native units. The shared PDK is unchanged.
Isolated native LVS passes the corrected view, rejects reversed terminals
and reports property errors for doubled area. Signoff acceptance now rejects
property errors even when Netgen also prints a unique topological match.
The expanded verification regression passes 32 tests.

Iteration 023 preserves functional gate behavior and control induction, but
its dedicated BUF16 output raises retiming-Q capacitance from about 0.030
to 0.086 pF and reduces worst setup to +0.026209 ns. One met1 antenna side-area
ratio remains at 482.72 against 400. This trial is rejected as a timing
checkpoint. Iteration 024 uses BUF8 at the dedicated output and launch-clock
leaf and reroutes the residual antenna net with signal trunks starting at met2.
It requires fresh extracted timing and physical qualification.

Iteration 025 restores the original shared retimed-output buffer, removing
the additional Q load measured in iteration 023, and increases only its
launch-clock leaf to BUF8. Native ODB inspection identifies an exact vacant
960-DBU filler site at (335040,26640), immediately beside FF16748's input;
the extra diode moves there from the far side of the 11040-DBU-wide flop.
Unchanged functional placements remain frozen. This tests a short local
antenna connection with met1 signal access rather than broad layer changes.
The two historical iteration 016/017 routers are stopped as superseded by
verified compact electrical repair and complete diode trials; their artifacts
and explicit supersession reasons remain preserved.

Iteration 025 clears all post-route antenna violations (zero nets/pins) with
the closer diode connection. Router and Magic DRC report zero; unique
transistor LVS passes with the candidate-local corrected diode view and
strict property-error rejection. All 74,778 supply pins connect.
Fresh 450 MHz setup is +0.123029 ns, recovery +0.168626 ns and worst
hold/removal is +0.078696 ns. All nine 450 MHz timing/electrical/pulse screens
pass with zero electrical/pulse violations. Both functional gate phases and
the six-state handoff proof plus negative control pass. Full physical
composition, other-mode screens and KLayout remain required before acceptance.

Iteration 025 is now the current verified diagnostic checkpoint. All 918
physical equivalence comparisons pass (916 direct plus two covered by the
pinned six-state induction proof), and all 45 supplied-mode/corner timing,
electrical and pulse screens pass. Independent KLayout full DRC has zero
violations; its global clear-area density deck passes. The final audit finds
zero altered direct synchronizer links, incorrect clock roles or unannotated
functional pins. Router/Magic DRC, unique transistor LVS, power continuity,
both gate phases and zero-net/zero-pin antenna checks pass. The prior verified
iteration 021 assessment is archived. The assessment pins candidate-owned
source snapshots, including formal and diode-view helpers, preserving older
checkpoints while work continues. All 32 verification unit tests pass.

No selected RTL promotion or release qualification is claimed. The exact
model inventory remains one point of the required 45-point PVT grid;
characterized interface/CDC/bundle/pulse constraints, full windowed density
and EM/IR checks and whole-PLL qualification remain outstanding.

Release follow-up confirms iteration 025 remains the verified diagnostic
checkpoint and the canonical hot-SS analog calibration process remains live
(PID 2054185), advancing to approximately 252.65 ns of its 300 ns transient.
No live calibration deck or provenance is modified.

The pinned upstream HS JSON source contains additional characterized models
not installed in the original three-view overlay. The official SkyWater
Liberty generator now produces ss/tt/ff at 150 C and 1.60/1.80/1.95 V in
`build/timing450/extended_models`; 1,137 source/output hashes pin generation.
These points add no exact required PVT-grid coverage. Native extracted
450 MHz timing passes the margin floors for all nine additional model/RC
screens. SS/max reports five electrical violations on one NAND2_1 output:
four slew rows at about 1.02 ns against 1.00 ns and one capacitance row.
An independently repeated, hash-checked extended-model sweep confirms this
failure; eight other screens pass. The helper rejects incomplete timing
matrices, SPEF mismatch and stale baseline inputs. Its regression expands
the verification suite to 35 passing tests.

Iteration 026 increases only this compatible data driver to NAND2_2, guards
against clock-driver/sink changes, preserves unchanged placement and routes
a separate candidate. It requires fresh original and extended-corner
qualification before acceptance. Missing exact PVT models, density/EMIR,
interface/CDC characterization and whole-PLL release gates remain open.

Iteration 026 preserves original 450 MHz margin floors (+0.122951 ns setup,
+0.078696 ns worst hold/removal) and clears every additional 150 C electrical
row. All nine additional 450 MHz screens now pass. Both functional gate
phases, handoff induction with the negative control, router/Magic DRC, unique
LVS and zero-net/zero-pin antenna checks pass. Full physical composition,
other-mode original/additional sweeps and KLayout remain required before
acceptance. The new model suite is diagnostic and adds no exact required
PVT-grid points.

Iteration 026 is now the current verified diagnostic checkpoint. All 90
original/additional model/RC/mode timing, electrical and pulse screens pass.
Full physical equivalence proves 918 comparisons (916 direct and two composed
through pinned six-state induction). The final audit has zero altered direct
synchronizer links, incorrect clock roles or unannotated functional pins.
Router/Magic/KLayout DRC, unique transistor LVS, both gate phases, connected
power grids and zero-net/zero-pin antenna checks pass. Global clear-area
density checks pass. Fresh original SS/max setup, recovery and worst minimum
are +0.122951, +0.169483 and +0.078696 ns. The prior iteration 025 checkpoint,
including its additional-model failure, is archived separately.

The native container verification suite passes all 35 tests using its pinned
Tcl 8.6.16 executable on PATH. An initial invocation without that directory
failed three Tcl margin-guard tests solely because `tclsh` was not exposed;
the failure log is preserved and no test is skipped or weakened. Current
checkpoint source/input hashes verify. Missing exact model coverage remains
44 of 45 required PVT points. Full windowed density/enclosing context, EMIR,
measured interface/CDC/pulse/bundle constraints and whole-PLL qualification
remain open. No selected RTL promotion or release qualification is claimed.

The next implementation step adds `characterize_interfaces.py` to reproduce
the current checkpoint's routed interface loads and SDF without changing its
accepted source snapshots. It verifies all baseline dependencies before and
after characterization, checks load completeness/units/driver/sums, and pins
the native tool binaries, inputs, recipes and outputs. At SS/1.60 V/100 C with
maximum RC, BBPD[0], BBPD[1] and PLLOUT total input loads are 0.189715251,
0.166840822 and 0.142693922 pF respectively. These measured loads must inform
subsequent analog interface pulse/slew characterization.

Native SDF export includes 14,042 interconnect delays, 20,622 cell IOPATHs,
1,728 setup and 1,728 hold checks, 864 recovery and 864 removal checks, and
3,456 pulse-width checks. A deliberate 0.5 ns setup violation against a 1 ns
requirement produces no notifier event in the installed Icarus 12.0. The
actual HS timing views also fail compilation without `FUNCTIONAL` and report
unsupported delayed timing-check signals. The pinned supplemental receipt
is `build/timing450/interface_characterization/checkpoint026/assessment.json`;
it explicitly retains `timed_gate_simulation_pass: false` and
`release_qualified: false`. SDF generation is verified, timed gate simulation
remains open, and no timing model is patched to manufacture a passing result.
The verification suite now passes 39 tests, including missing/duplicate
interface, invalid capacitance, incorrect driver and extraction-error controls.

Static power-grid characterization now completes all 45 supplied cell/RC/mode
screens on the unchanged checkpoint 026 geometry. The reusable
`characterize_power_grid.py` reads the pinned installed Magic nominal/high/low
resistance tables, converts sheet/contact units, forces generated-clock timing
propagation and validates all five clock periods before calculating power.
Its declared uniform non-clock activity is 0.5 transitions per mode cycle with
duty 0.5; sources use a 140 um bump pitch, 70 um size, interval one and zero
external resistance. Both VDD and VSS solve at each screen, each reporting
20,093 matching instances and 13,998/14,358 current segments respectively.
The verified matrix and input/artifact hashes are retained at
`build/timing450/power_grid/checkpoint026/verified_matrix/assessment.json`.

At 450 MHz/max RC, SS/1.60 V/100 C gives 114.376 mW, 2.59 mV worst VDD drop,
3.36 mV worst VSS rise and 1.594054 V minimum effective instance supply.
TT/1.80 V/25 C gives 137.297 mW, 2.81/3.70 mV rail excursions and 1.793488 V
effective supply; FF/1.95 V/-40 C gives 171.118 mW, 3.07/4.04 mV excursions
and 1.942889 V effective supply. The common worst effective-supply instance
is the PLLOUT root clock buffer. Power is an explicit activity screen, not
measured acquisition/tracking or whole-PLL power. The supply/package model,
dynamic noise, temperature/lifetime EM checks and voltage-aware timing remain
unqualified; the receipt keeps EM/IR signoff and release qualification false.

The first native attempt is retained: HS LEF's missing via resistances make
PDNSim reject its resistance map, and `-activity` before generated-clock
initialization produces nonfinite power. Separate probes show FINECLK's period
changes from zero to 40 ns after `report_checks`. The accepted helper requires
that initialization and rejects unresolved clocks. Initial matrix outputs
without the explicit period guard are superseded. A subsequent implementation
attempt with an overwritten result key is also superseded; no partial matrix
is accepted. The native verification suite now passes 48 tests, including
clock, resistance-table, finite-value, power-sum and paired-rail controls.

The first extracted BBPD transient with checkpoint 026's measured lumped
loads completes under native Xyce at SS/1.62 V. Its requested `.temp 125`
directive is ignored by Xyce, so temperature remains unverified and this
run cannot establish 125 C behavior. REF leads CLKDIVR by
50 ps, with 40 ns periods and 20 ps input transitions. Over the two complete
pulse opportunities in 5–85 ns, BBPD[0]/[1] reach only 0.355709496/0.423076486 V;
neither crosses half the 1.62 V supply. This is a concrete loaded-interface
failure, although the standalone digital timing diagnostic remains passing.
The 90 ns waveform, deck, logs and failure receipt are preserved in
`build/timing450/interface_characterization/bbpd_loaded_ss`.

The installed native PDK provides actual `special_nfet_01v8` corner models;
no generic NFET compatibility alias is used in this transient. Its 860-file
model/input manifest was captured during the simulation and verified after it,
so the receipt explicitly retains that provenance limitation and does not
claim release qualification. Full PVT, phase and receiver-nonlinearity coverage
remain required.

An isolated macro candidate under
`build/timing450/interface_characterization/bbpd_output_buf8` increases only
`up_out` and `dn_out` from HD BUF1 to BUF8. Its source manifest pins the original
and changed sources/configuration. The original BBPD source, current digital
checkpoint and live canonical DCO calibration remain unchanged. Physical
implementation, fresh extraction and loaded pulse/slew characterization are
required before adopting this output-drive repair.

The isolated BUF8 macro completes native Librelane routing and signoff with
zero router/Magic/KLayout DRC violations, zero antenna violations and unique
LVS with no property errors. Its two reported disconnected pins are noncritical;
that count is retained in `physical_assessment.json`. A read-only Nix profile
prevents `nix-shell` startup; the installed pinned Librelane executable runs
the complete flow directly, with the failed startup log preserved.

Fresh capacitance extraction preserves the BBPD port order and completes under
Magic 8.3.623. It reports 1,621 extraction warnings, which are retained and need
scope review; this extraction is not a complete resistance/signoff claim.
The exact loaded SS/1.62 V/125 C/50 ps test is prepared against this new macro.
All 860 original model/input hashes are rechecked, and the changed macro,
source, physical evidence, extraction, tool and complete Magic technology
inputs are pinned before starting this BUF8 transient. Its live outputs are
under `bbpd_output_buf8/loaded_ss`; no loaded-pulse pass or adoption is claimed
until that run and the remaining characterization complete.

Temperature/model review rejects the first BUF8 transient: Xyce ignores the
ngspice `.temp 125` directive, and the newly inserted antenna diode's original
model causes a parser failure. The earlier baseline failure receipt is also
corrected to record requested but unverified temperature; its waveform remains
diagnostic, with no 125 C claim. A fresh original-macro run uses supported
`.options device temp=125` under `bbpd_loaded_ss_125C`.

The existing checked diode translation validates its complete comparison
evidence and the native PDK model, matches the new diode's exact area/perimeter,
and translates that single instance specifically for SS/125 C. Its output and
sidecar retain geometry, node order, source/model/evidence hashes and scope.
A corrected BUF8 run uses this translated include and the supported global
temperature option under `bbpd_output_buf8/loaded_ss125_translated`; all prior
911 model/technology/physical hashes are rechecked and new inputs are pinned
before launch. Both corrected transients require terminal output and waveform
checks before any loaded-interface conclusion at 125 C.

The canonical DCO campaign independently completes code 18 with a completed
provenance sidecar and advances to code 24 (confirmed live PID 2124442).
No canonical deck or campaign input is changed by these interface experiments.

The corrected original-BBPD 125 C transient completes successfully with the
temperature directive accepted. With the same 0.189715251/0.166840822 pF
loads, BBPD[0]/[1] peak at 0.431468159/0.512728552 V over two complete pulse
opportunities and never cross 0.81 V. This confirms the loaded-interface
failure at the requested SS/1.62 V/125 C point. The current implementation
assessment now references this corrected receipt instead of the earlier
unverified-temperature run. The BUF8 comparison remains live and unselected.

The corrected BUF8 comparison now completes with all 917 model/technology/
physical/translation inputs hash-matching. Its two complete pulses on each
output reach approximately 1.645/1.649 V. BBPD[0]/[1] minimum high widths at
half supply are 1.360625/1.422056 ns. Rising 20–80% slew is approximately
0.372314/0.331172 ns, and falling 80–20% slew is 0.197522/0.178139 ns.
This restores output pulses at the measured-load SS/1.62 V/125 C/50 ps point
where the original BUF1 macro never reaches half supply. The replayable
`build/timing450/interface_characterization/analyze_loaded.py` rejects stale
inputs, unsupported temperature directives and incomplete/nonfinite waveforms;
the point receipt pins that analyzer and all native artifacts.

The current implementation assessment records this isolated repair's point
evidence and keeps `repair_adopted: false`. The measured edge slew exceeds the
digital diagnostic's provisional 0.1 ns interface assumption, so fresh timing
screens with characterized slew, full phase/PVT/slew coverage and coupled HS
receiver evaluation are required. Pulse presence at one model/phase point does
not close those gates, full resistance/noise checks or whole-PLL qualification.

Measured-interface timing screens now complete for checkpoint 026. The root
`verify_extended_models.py --bbpd-characterization` option verifies the completed
BUF8 point and its pinned native inputs, checks the Liberty 20–80% slew units,
and applies both input and propagated-clock source slew. It uses a 25 ps guard
and granule to obtain 0.400 ns rise, 0.225 ns fall and 1.325 ns high time for
both 40 ns BBPD event clocks. Mode-dependent PLL clocks and existing CDC/reset
exceptions remain in their original recipes. Native path rows must demonstrate
both applied edge slews; ignored or missing source slew fails the check.

All 90 new screens pass: five modes times nine model/RC combinations in each
of the original and additional 150 C model suites. The minimum maximum-path
margin is 0.122951 ns and minimum minimum-path margin is 0.078696 ns; electrical
violation counts remain zero. All ten receipts and every pinned input/artifact
are rechecked by `build/timing450/interface_characterization/verify_supplemental.py`.
Their aggregate receipt is `slew_timing/assessment.json` in that directory and
the primary implementation assessment references it by SHA256. These are
diagnostic screens using bounds from one SS/1.62 V/125 C/50 ps macro point,
not a replacement for the required exact PVT matrix or coupled receiver checks.
The candidate remains unselected and release qualification remains false.

`reduce_bbpd_fixed_rails.py` adds an isolated signal-only simulation reduction.
It removes only known MOS instances whose four terminals all connect to ideal
constant supply rails, and preserves every signal MOS, resistor, capacitor and
qualified antenna-diode model. It rejects dynamic rails, missing fixed supply/
temperature and non-transient analysis requests. Four regression cases cover
these restrictions; the complete timing-helper suite now passes 55 tests.
The accepted `bbpd_signal_reduced_v2` experiment removes 1620 such filler MOS
loads. Its full-versus-reduced bidirectional waveform comparison over 5–85 ns
passes declared limits of 1 mV signal error and 1 ps pulse-metric error: worst
voltage discrepancy is 0.884949 mV and worst pulse-width discrepancy 0.186005 ps.
All source, deck, model and result hashes match. The reduction preserves signal
behavior only at this screened point with ideal rails: current, power, noise,
and nonideal supply behavior are excluded. Earlier reduction artifacts are
superseded and unused. Broader phase/PVT/slew characterization remains required
before adopting the BUF8 repair. The independent canonical DCO code-24 campaign
continues; its inputs and live simulation are unchanged.

The loaded BUF8 signal-voltage screen now completes all 45 required primitive
PVT points (ss/tt/ff/sf/fs; 1.62/1.80/1.95 V; -40/27/125 C) at 50 ps relative
phase and 20 ps input edges. Both outputs have two complete pulses in every
point. `characterize_bbpd.py` validates the complete diode qualification
evidence once, emits corner/temperature-specific checked-geometry diode
models, preserves active MOS and all R/C, pins native inputs/decks/binary,
requires terminal finite monotone 90 ns waveforms, and rechecks input hashes
after the campaign. Its scope excludes current/power/noise/nonideal rails and
nonlinear receivers. All four new regression tests pass; with the complete
PVT-bound guard regression the root helper suite passes 60 tests.

This matrix supersedes the single-point BBPD timing bounds: the conservative
25 ps guard/granule produces 0.575 ns rise, 0.250 ns fall and 0.350 ns high time.
`verify_extended_models.py --bbpd-pvt-characterization` requires the exact
unique complete 45-point set and verifies every receipt, native waveform/deck
and model hash. Both original and additional 150 C digital timing suites
complete for every mode with these wider bounds: 90 screens pass, zero
electrical violations, minimum setup/max-path margin 0.122951 ns and minimum
hold/min-path margin 0.078696 ns. The aggregate pinned receipt is
`build/timing450/interface_characterization/pvt_timing/assessment.json`.
Earlier single-point timing receipts are historical and superseded after the
helper update. The primary assessment now references the new aggregate.

A full-extraction FF/1.95 V/-40 C/50 ps/20 ps transient confirms the shortest
BBPD[0] high widths of 0.393638/0.393478 ns, supporting the 0.350 ns guard.
Its full/reduced waveform comparison fails the predeclared 1 mV limit slightly
(1.076298 mV maximum), although every pulse metric differs by less than
0.1 ps. The failed receipt remains under `bbpd_full_ff195_n40/comparison.json`.
Fresh full and reduced runs under `bbpd_ff_finer` use 1 ps maximum step and
1e-6/1e-10 relative/absolute tolerances to test convergence; only the reduced
run is terminal so far. No relaxed voltage threshold or two-point agreement
claim is used. The broader 810-point legacy BUF8 phase/slew/PVT sweep remains
live under `bbpd_phase_pvt`: nine offsets from -5 ns through coincidence to
+5 ns, two input edge times (20/200 ps), and the same 45 PVT points.

The new coupled receiver fixture extracts the actual mapped cone for both
event toggles: 17 HS cells, 19 routed nets, 31 resistors and 67 capacitors from
the checkpoint 026 maximum-RC SPEF. It retains coupling within the cone and
grounds omitted static aggressors; the two omitted synchronizer D pins use
pinned Liberty capacitance. The reset network is replaced by an ideal settled
reset. Seven SS/1.62 V/125 C/20 ps phase-offset transients complete and retain
source, model, fixture and waveform hashes. At -100 ps and -50 ps both event
toggles change and UP reaches half supply first. At -1000 ps only DN changes.
This is a deterministic capture diagnostic, not a full synchronizer,
metastability, switching-aggressor or whole-PLL signoff claim.

Replay of these completed native toggle edges into the exact checkpoint core
RTL/parameters at 450 MHz confirms the direction bias: all 90 sampled clock
alignments at -100 ps and all 88 at -50 ps produce UP; the -1000 ps control
produces DN in all 91 alignments. Alignments within a declared 100 ps clock
aperture are omitted. The first replay harness had a reset/clock coincidence
initialization failure and is unaccepted; `receiver_replay_v2` uses an explicit
reset assertion and a distinct release time, records all native Icarus runs
and checks provenance. The primary assessment records this failed direction
screen. Stronger BUF8 output drive alone cannot qualify this receiver.

A new isolated `bbpd_sampled` source now samples CLKDIVR on REF rising, waits
for a four-cell delayed REF window, and drives mutually exclusive UP/DN pulses
through BUF8 outputs. A valid-sample FF suppresses outputs until the first REF
sample after reset. This is a candidate bang-bang phase detector for the
tracking loop; frequency acquisition remains in the existing acquisition
core. Its first flow invocation incorrectly selected automatic PDK lookup
and failed on the read-only PDK installation; the corrected manual-PDK flow
uses the already pinned installed PDK. Physical, loaded PVT/phase/slew,
metastability/settling, receiver, and whole-PLL acquisition/lock/jitter
qualification remain required. No candidate is adopted or release-qualified.

The first manual-PDK sampled-macro flow stops at the structural assign checker
because `window_delay[0] = REF` leaves an alias assignment in the elaborated
netlist. The next source connects the first delay cell directly to REF and
uses only stages [4:1]; the prior source/manifest and failed run are archived.
The distinct `timing450_sampled_v2` run passes this check and advances through
placement and routing. No failed run is restarted in place or counted as a pass.

The sampled detector's corrected physical flow completes: router/Magic/KLayout
DRC zero, unique transistor LVS with zero property errors, antenna zero nets/
pins, and zero critical disconnected pins (two noncritical pins retained in
metrics). A candidate-local capacitive/coupling extraction at 0.01 fF completes
with 1616 warnings preserved; extresist remains off. The initial manual Magic
invocation lacks PDK_ROOT and exits before extraction despite status zero;
that log is rejected and archived. A corrected run supplies the installed
PDK_ROOT and verifies the actual extracted file. No antenna diode is inserted
in this candidate, so no diode model translation is applied.

Seven completed loaded SS/1.62 V/125 C/20 ps signal-only transients produce one
active output and one quiet output in every case, with active high widths
approximately 20.34 ns and rise slews approximately 0.330/0.371 ns for UP/DN.
The -1000 and -100 ps cases produce DN, and +50/+100/+1000 ps produce UP. At
coincidence the native deterministic model chooses UP. At -50 ps it also chooses
UP, so the strict signed-direction screen is false; this observed transition
region is retained, not declared correct or dismissed as noise. The physical
and point receipts are under `bbpd_sampled/physical_assessment.json` and
`bbpd_sampled/loaded_ss125/assessment.json`. The sampled detector must measure
its phase transfer/offset and settling across PVT/input slew, then pass coupled
receiver and whole-PLL phase/lock/jitter requirements before adoption.

A pinned 180-point sampled-detector campaign now tests both +/-250 ps offsets
(the 450 MHz phase-mean limit is 0.1 output period, about 222 ps), both 20/200 ps
input edge times, and every required primitive PVT point. Its scoped directional
screens do not establish a whole-PLL phase error or replace characterization
of the near-coincidence transition region. Results remain unqualified until
terminal native waveforms and all input/artifact hashes are checked.

The sampled-detector 180-point campaign completes all native transients and
passes every directional/exclusivity screen at +/-250 ps across all 45 PVT
points and both 20/200 ps input edge times. All inputs match after completion.
This is a limited phase/slew screen, not whole-PLL phase/jitter qualification.
Nine coupled sampled-detector SS/1.62 V/125 C/max-routed-RC cases also complete.
Only one receiver event toggle changes in each case; -100/-250/-1000 ps capture
DN, positive offsets capture UP, and -50 ps retains the detector's UP choice.
Replay through exact checkpoint RTL/parameters at 450 MHz gives the expected
polarity in 91 safe clock alignments per case at each of -100/-250/-1000 and
+100/+250/+1000 ps. It gives UP in all 91 alignments at -50 ps. Unlike the prior
receiver, the sampled detector fixes the -100 ps direction error; its observed
near-coincidence transition region, metastability/settling and whole-PLL phase
limits remain to be qualified. The replay uses the eight then-terminal native
traces and does not invent a result for the later ninth trace.

The 1 ps full FF convergence run completes. Its initial reduced waveform fails
strict monotonicity because the default printed precision aliases eleven
sub-step timestamps; that result is rejected. A fresh reduced run changes only
printed precision to 16 digits. The complete full waveform already has strictly
monotone timestamps and is reused with its pinned completion receipt. Both
accepted waveforms now pass integrity checks. Their maximum interpolated voltage
difference is 0.307771 mV and maximum pulse-width difference 0.020050 ps, within
the unchanged 1 mV/1 ps limits. This resolves the two fast-point numerical/output
issues without weakening the guard or replacing rejected evidence. Current,
power, noise and nonideal-supply behavior remain excluded from the reduction.

`normalize_hs_timing_views.py` now corrects two illegal numeric wire declarations
and case/spelling mismatches in timing-check signal references, only for the
exact pinned HS Verilog hash and in an isolated copy. All timing-check statements
remain. Three regression cases cover declared aliases, rejected undeclared
signal targets, and unchanged unrelated logic. Three compatibility helper names
map directly to shipped power-aware notifier UDPs. A native UDP probe confirms
async reset/set, clock capture, notifier unknown injection, clock recovery and
power-failure unknown injection. The corrected timing-view FF probe compiles,
but Icarus still leaves delayed timing-check signals undriven and Q unknown;
compilation does not close the timed gate-simulation gate.

A second view defect is independently demonstrated: physical-cell SDF paths
cannot annotate paths hidden in nested generic `base` instances. A 0.75 ns
clkbuf_16 IOPATH probe reports an unmatched ModPath and stays at zero delay.
`flatten_hs_timing_cells.py` inlines 373 generic timing models into strength
wrappers after explicit nonfunctional preprocessing, checking identity pin
mapping and preserving all model logic, supplies, timing checks and notifiers.
Seventeen passive/constant wrappers retain their original structure. Two new
regressions check owning-cell paths/supplies/checks and rejected port remapping
or conditional/unexpected input. The same native SDF probe then delays the
buffer correctly (old at 0.1 ns, new at 0.8 ns) without unmatched-path warnings.
A timing-check-capable simulator still must demonstrate timing-check/delayed-
signal/notifier semantics before these views can support release simulation.

The local CVC source build (commit
`1c5e043ec33ef6f1fdbf38565501c944893a83cf`) detects an injected setup violation
and reproduces the flattened model's SDF buffer delay. Its actual HS flip-flop
probe warns that optional timing-check conditions and delayed reference/data
signals are ignored; Q remains unknown. This tested simulator is rejected for
full HS timed gate qualification. The native logs, binary, source/license and
model hashes are recorded in `cvc_qualification/assessment.json`. A passing
simple timing check cannot substitute for the missing HS timing semantics.

The legacy BUF8 phase/slew screen completes all 810 native points and its
input, grid, receipt and output hashes verify independently. Every point has
two full pulses on both outputs. This establishes pulse presence only; the
previous coupled receiver/replay sign failures still disqualify adoption.

The sampled detector's finer phase-transfer campaign tests 17 offsets from
-200 through +200 ps at 25 ps spacing, both 20/200 ps input edges and all 45
primitive PVT points (1530 native transients). It is running. A fresh separate
snapshot verifies 68 terminal point receipts against their native waveforms.
Four curves are complete: SS/1.62 V at -40/27 C with both edge times. Each is
exclusive and monotone, with its deterministic DN-to-UP transition bracketed
between -100 and -75 ps. These partial detector measurements do not prove
whole-PLL phase error or metastability settling.

`analyze_phase_transfer.py` rejects duplicate/unexpected grid points, changed
inputs/artifacts and receipts inconsistent with native measurements. Missing,
ambiguous, nonmonotone and unbracketed curves cannot yield an all-PVT transition
bound. Four regressions protect those failure cases and prevent a detector
bracket from claiming a whole-loop pass; all 69 timing helper tests pass.
The measured sampled-detector RTL is retained byte-for-byte for review under
`verification/timing450/candidates/sampled_bbpd`, without selecting it in the
production hierarchy. Checkpoint 026 and release qualification remain unchanged.

The next separate phase-transfer snapshot verifies 140 terminal native points
and eight complete SS curves. The SS/1.62 V/125 C/200 ps-input curve brackets
the transition at -125..-100 ps; the other completed 1.62 V curves are
-100..-75 ps, and SS/1.8 V/-40 C curves are -75..-50 ps. Every completed curve
is exclusive and monotone. Full 90-curve coverage is still pending; no grid-wide
or whole-PLL phase bound is claimed from this snapshot.

`characterize_coupled_bbpd.py` now prepares and runs a separate 180-point
native campaign: both +/-200 ps phase offsets, both 20/200 ps input edges and
all 45 primitive PVT points, using the actual mapped 17-cell receiver and its
fixed maximum routed RC. It replaces the lumped loads with the nonlinear
receiver, retains all input/model/extraction hashes and prints 16-digit times.
The signed capture check requires initialized-low event outputs, exactly one
rise and one fall on the expected event toggle across the two opportunities,
settled high/low levels, and no wrong-direction event. Native waveform integrity
and global-temperature handling remain strict.

Five new regressions cover wrong sign/double capture, missing second events,
glitches, bad reset initialization, PVT/deck integrity and incomplete/nonfinite
waveforms. The helper also reproduces the existing eight nonzero native traces:
-50 ps fails its signed screen, while the other seven cases capture both events
correctly. All 74 timing helper tests pass. The new campaign is confirmed live
with two native Xyce workers. Its limits include static omitted aggressors,
linear omitted synchronizer loads, fixed RC and ideal rails; it cannot prove
whole-PLL phase/lock/jitter or metastability probability/settling.

The first two coupled PVT points complete natively: SS/1.62 V/-40 C/-200 ps
with both 20/200 ps input edges. Both pass the signed two-event capture screen;
their circuit/log/waveform hashes verify independently. The remaining campaign
continues under its existing parent process; this is partial coverage.

The first four coupled PVT cases now pass: SS/1.62 V/-40 C at both +/-200 ps
and both 20/200 ps edge times. Their native artifact hashes verify; remaining
PVT coverage continues in the original campaign.

`bbpd_reset_metrics.py` adds a first-sample inhibition screen for startup. The
new 16-point coupled native campaign uses SS/1.62 V/125 C and FF/1.95 V/-40 C,
both +/-200 ps offsets and 20 ps input edges. Initial reset releases at
1/15/25/35 ns cover release before the first REF rising edge, during its high
phase, and during the following low phase. Until a post-reset rising reference
edge, both BBPD clocks and receiver toggles must stay low. The checker then
requires the expected number and sign of clock/captured events and settled
receiver state. Its existing +/-250 ps SS native controls pass.

Four regressions reject premature output, incorrect sign, missed capture,
clock glitches and missing/unsupported observation scenarios. All 78 timing
helper tests pass. The campaign is confirmed live under parent PID2164109
with three native Xyce workers. Its source, decks, primitives, physical macro
and receiver extraction are pinned. This limited initial-reset screen does
not qualify reset-release apertures/metastability, in-flight reset, full PVT,
synchronizer coupling or whole-PLL acquisition/phase/jitter behavior.

`characterize_density.py` measures standalone-core window geometry independently
with native KLayout/Python. It uses the drawing/fill layer selections of the
installed global-density deck, recursively unions shapes, merges overlaps and
clips each complete window. The diagnostic uses 50 um windows at 25 um steps
and 700 um windows at 70 um steps, based on the published periphery-rule window
sizes: https://skywater-pdk.readthedocs.io/en/main/rules/periphery.html.
Process flags and derived oxide/waffle/exclusion rules need separate qualification;
these raw metal unions are not a foundry signoff deck.

Checkpoint 026 has a 450.03 um square GDS bounding box. Its 289 complete 50 um
windows have maximum metal-area fractions li1=0.491078, m1=0.331140,
m2=0.176498, m3=0.271512, m4=0.294738 and m5=0.184000. There are no complete
700 um windows. No surrounding chip material is invented and no empty-window
check is counted as a pass. Large-window/die-edge density qualification requires
the assembled chip and applicable process rules; full-windowed-density signoff
remains false. The candidate GDS stays unchanged.

Native synthetic controls verify overlapping drawing/fill union, window clipping,
annotation/via exclusion and missing-large-window handling. Three regressions
protect overlapping/exact grids, absent large windows and invalid dimensions;
all 81 timing helper tests pass. Native environment evidence pins Python and
loaded KLayout 0.30.7 module files. The geometry, inputs, helpers and results
are recorded under `build/timing450/density/checkpoint026_windows` and referenced
in the primary assessment as a supplemental characterization only.

The initial-reset campaign now completes all 16 native cases with every startup
inhibit/capture screen passing. The original parent and final worker exit, and
the independent completion audit verifies all 16 unique expected grid points,
all pinned inputs/native artifacts and recomputed waveform metrics. No output
or event toggle appears before a post-reset reference sample, including release
during REF-high. Two extreme PVT points and four initial-release times are now
screened; reset-release apertures, in-flight reset, full PVT and metastability
settling remain unqualified. The final audit is
`build/timing450/interface_characterization/startup_completion_audit.json`.

Phase-transfer snapshot 003 validates 352 terminal native point waveforms and
20 complete curves: all 18 SS phase/slew curves over the three voltages and
three temperatures, plus both TT/1.62 V/-40 C edge-rate curves. Every completed
curve is exclusive and monotone. Bracket magnitude is at most 125 ps in this
subset. The full sweep continues; this partial detector offset bound cannot
establish the whole-loop mean/span/drift limits.

The whole-PLL boundary review finds that `scripts/pll_rtl_cosim.py` instantiates
an unloaded BBPD directly into ideal ADC-driven RTL BBPD inputs. Its ADC levels
are VDD/0 and it does not contain the mapped nonlinear receiver or the measured
routed load. Those historical diagnostics cannot qualify the routed receiver
path. Future whole-PLL qualification must integrate the mapped receiver event
state into exact candidate RTL with validated reset/CDC mapping, an appropriately
calibrated DCO model and complete PVT/mode lock/phase/jitter coverage. Source
hashes and the unresolved boundary are recorded in the primary assessment.

`characterize_sampled_bounds.py` independently verifies all 180 sampled-detector
PVT receipts and recomputes measurements from their native waveforms. It rejects
missing/duplicate/unsupported points, wrong polarity, nonexclusive output and
invalid pulse intervals. Across the two opportunities, the guarded source bounds
are rise=0.575 ns, fall=0.250 ns, minimum high=19.750 ns, minimum low=19.425 ns
and maximum high=20.575 ns (25 ps guard and granularity). The observed rising
period spans 39.998205..40.000306 ns. Low time is measured between the first
falling edge and second rising edge, not inferred from the minimum high time.
This remains a +/-250 ps/20-200 ps-input/ideal-rail/lumped-load screen.

The source slews fit the earlier digital timing bounds, but its 0.350 ns high
clock waveform implies a 39.650 ns low interval. That recipe does not test the
sampled detector's minimum low time. `verify_sampled_pulses.py` now replays the
pinned STA recipes with two separate 40 ns event waveforms: high/low
19.750/20.250 ns and 20.575/19.425 ns. Together they screen both measured pulse
extremes while retaining original CDC/reset/other clock constraints. It checks
native clock-property reports for both BBPD ports and verifies their measured
rise/fall slews in the actual timing paths.

A native SS/max-RC/450 MHz pilot passes with the 19.750 ns high waveform. The
first pilot is rejected because the installed OpenSTA does not expose a clock
`waveform` through `get_property`; the corrected pilot uses the supported
`report_clock_properties` command and verifies the actual source-clock report.
A separate 180-screen campaign covers all five modes, both original/hot
supplied-library suites, all nine model/RC combinations and both pulse extremes.
Its parent is live, validating pinned inputs before executing recipes; full
results are pending. No baseline geometry, recipe or existing receipt is edited.
Four bounds and two pulse-recipe/report regressions pass; all 87 timing helper
tests pass. These supplemental screens cannot replace the 44 missing exact
cell-library PVT points or whole-PLL/interface/CDC/metastability qualification.

The sampled pulse-extreme STA campaign completes all 180 native screens and
passes both guarded waveforms across every supplied suite/mode/model/RC
combination. All source clock-property/slew checks pass; electrical and
minimum-pulse-width violations are zero. The independent completion audit
verifies all input/recipe/native-log hashes, exactly 180 unique expected grid
points, recomputed timing rows and actual clock properties. Worst maximum-path
margin remains +0.122951 ns and worst minimum-path margin +0.078696 ns.
This closes the supplemental minimum-high/minimum-low waveform screen without
any geometry or baseline constraint/receipt changes. Exact required cell PVT,
metastability/receiver and whole-PLL gates remain separate and unqualified.
Final evidence is `sampled_pulse_timing_audit.json` under interface characterization.

Phase-transfer snapshot 004 now independently verifies 614 terminal native
waveforms and all 36 complete SS/TT curves (all three voltages, temperatures
and both input edge times). Every completed curve is exclusive and monotone;
transition brackets span -125..-100 through -50..-25 ps, with magnitude at most
125 ps in the completed subset. FF/SF/FS phase coverage remains incomplete.
The coupled receiver campaign completes and passes all 36 SS cases: both
+/-200 ps offsets and both input edge times at all SS voltage/temperature
points. Native per-point artifacts verify. Remaining primitive corners continue
under the original parent process; full PVT and whole-PLL claims remain false.

`extract_receiver_cdc.py` extends the mapped event-receiver fixture to include
both stages of the UP/DN tracking synchronizers and their actual clock paths.
It retains separate ideal event/pipe reset roles, checks input hashes against
the original checkpoint extraction and detects changes during extraction.
The checked-in extractor reproduces the private native fixture byte-for-byte.
The extended cone contains 26 cells, 29 routed nets, 109 resistors, 131 grounded
capacitances and 37 retained in-cone coupling capacitances. Omitted loads remain
linear Liberty capacitance and omitted aggressors remain static.

One SS/1.62 V/125 C/+250 ps native pilot completes at an ideal 450 MHz PLL
clock with 200 ps ramps and 50% duty. Both events propagate correctly through
the tracking synchronizer: UP event Q rises at 16.058007 ns, first-stage Q at
16.702578 ns and second-stage Q at 18.881489 ns. The second event falls at
56.019012/56.688819/58.790077 ns respectively. The DN channel stays quiet.
All native waveform/integrity and signed two-event capture checks pass and input
hashes match at completion. First-stage data/clock nodes are exposed for measuring
actual alignment without assuming that ideal PLL phase is its pin arrival time.

A separate six-case campaign now tests one DN pilot and five UP clock phases
around the pilot's estimated first-stage DATAUP1/CLKUP1 coincidence, at offsets
-50/-5/0/+5/+50 ps. Its parent/native workers are confirmed live. It records
actual pin data-minus-clock deltas rather than calling the estimate a setup/hold
boundary. These are deterministic transients at one PVT point. Separate settled
resets omit the full ready/reset network, PLL remains ideal, and the shipped
library transistor definitions omit explicit cell-internal routing R/C. Thus
this fixture includes routed interconnect and BSIM device behavior, but does not
prove full extracted cell timing, statistical metastability/MTBF or whole-PLL
qualification. Those limitations remain explicit in the primary assessment.

Phase-transfer snapshot 005 independently verifies 1018 terminal native points
and 58 complete exclusive, monotone curves: all 18 SS, 18 TT, 18 FF and four SF
curves. Their transition brackets span -125..-100 through -25..0 ps. Remaining
SF/FS curves are pending; this is a completed-subset bound, not full PVT phase
qualification. A separate native waveform remeasurement audit verifies 74
completed passing coupled-receiver cases (36 SS, 36 TT and two FF).

`add_receiver_cell_caps.py` constructs a new diagnostic 26-cell receiver fixture
using GDS-extracted internal cell capacitance. Eight cell types contain 385
explicit capacitances. Native transistor-only LVS matches topology and W/L for
all eight types; a doubled transistor width produces property errors. The
capacitor-stripped models are byte-identical to the actual LVS inputs. Port
wrappers preserve the original named pin connections, and the entire mapped
cone and external routed RC are retained byte-for-byte. Geometry, extraction
technology, recipes, native logs and model receipts are hashed in the new
fixture assessment. Existing live campaigns retain their original inputs.

A separate SS/1.62 V/125 C/+250 ps capture pilot runs with the new cell models,
an ideal 450 MHz PLL clock and both stages of the tracking synchronizer. Results
are pending. These models include nominal Magic cell capacitance above 0.01 fF
and extracted junction geometry, but omit cell-internal resistance. The PDK LVS
setup does not compare junction area/perimeter. Statistical metastability,
nonideal supplies, the full reset network, exact cell-library PVT and whole-PLL
release qualification remain unproved.

The six-case mapped CDC clock-alignment campaign completes at SS/1.62 V/125 C.
An independent auditor verifies pinned manifests/native artifacts, the exact
six-case grid, every complete waveform, signed second-stage two-event capture
and actual first-stage data-minus-clock crossings. All six capture screens
pass. Measured UP alignments are approximately +29.85, -27.19, -33.87, -40.60
and -101.67 ps; the DN pilot measures -340.60 ps. These are deterministic cases
with the original intrinsic-only cell definitions, not an MTBF result or an
exact aperture boundary. Evidence: `receiver_cdc_aperture/independent_audit.json`.

`extract_receiver_ready.py` adds both mapped capture re-arm flip-flops and their
actual data/clock paths. Its native extraction reproduces the private fixture
byte-for-byte. The resulting cone has 30 cells, 34 routed nets, 136 resistors,
161 grounded capacitances and 49 coupling capacitances. The eight existing
GDS cell-capacitance models apply to all selected cell types. Tie-high is driven
at the actual omitted tie-cell output node, retaining the routed tie net; its
source is ideal. A new SS125 transient withdraws the event reset briefly between
PLL edges after the first event, while tracking reset stays released, exposing
both ready stages and event synchronizers. It is running. Reset generation,
acquisition capture gating, downstream consumption and statistical metastability
remain outside this fixture; no full reset/CDC/whole-PLL qualification is claimed.

The SS125 450 MHz pilot with GDS cell capacitance completes natively with exit0.
An independent audit verifies all input/artifact hashes, complete monotone finite
waveform rows, recomputed second-stage capture metrics and every reported signal
crossing. UP event Q rises/falls at 16.248350/56.249752 ns, first-stage Q at
16.988053/57.002766 ns and second-stage Q at 19.069353/58.983799 ns; DN stays
quiet. Both intended events are captured. The increased delay relative to the
intrinsic-only fixture is retained in the evidence. A fresh six-case alignment
campaign now uses these GDS cell models; native workers are confirmed live.
These results improve physical model coverage without qualifying statistical
metastability, all PVT points, cell-internal resistance or whole-PLL release.

Phase-transfer snapshot 006 independently verifies 1326 terminal native points
and 78 complete exclusive, monotone curves: all 18 SS/TT/FF/SF curves and six FS
curves. Completed-subset brackets remain -125..-100 through -25..0 ps. Remaining
FS coverage is pending; no full-grid bound or whole-PLL claim is made.

The first mapped re-arm transient completes, but its short withdrawal fails.
The requested 130 ps low plateau produces 0.150 ns low width between half-supply
crossings. The physical ready guard does not drop, and checkpoint026 RTL
consumption replay accepts a stale UP at 20.100 ns, then the later UP at
60.100 ns. `replay_receiver_ready.py` digitizes the complete measured stage and
guard crossings, forces only those RTL storage registers, verifies that the
forced storage tracks the physical signals, and runs the remaining consumption
logic. An independent failure audit verifies original input/native waveform
hashes, the actual reset width, unchanged guard and the rejected RTL replay.
The original replay source is archived and hash-matched because a subsequent
helper revision also accepts the longer pulse recipe. Initial compile attempts
include duplicate alternative mode modules and are rejected; corrected attempts
compile the checkpoint026 core/retimer plus their three required dependencies.
The replay now includes crossings from time zero, retaining initial guard and
capture release; the measurement helper's default 5 ns window is unsuitable
for this startup replay.

This failure is retained. The supplied SS/1.60 V/100 C dfrtp2 RESET_B Liberty
min-pulse-width table starts at 1.01667 ns for 10 ps input slew, increasing with
slew; the 0.150 ns pulse is below this supplied diagnostic view's range. The
exact SS/1.62 V/125 C Liberty view is still absent. A fresh native transient
uses 1.500 ns measured-source low width, remaining shorter than one 450 MHz
period. Its result and RTL replay are pending. Actual integrated reset generation
and pulse widths must be qualified; this test does not impose a new external
interface contract or establish a full-PVT reset bound. Guard-bypass control
also rejects the short-pulse trace, but cannot distinguish guard effectiveness
until a valid-width baseline passes. Full reset/CDC/metastability and release
gates remain false.

`extract_receiver_reset.py` extends the receiver/guard cone through mapped reset
generation: both fast-reset synchronizer stages, the tracking-release pipeline,
reset buffer branches, track-reset decode and event-reset AND gate are nonlinear.
It includes 46 cells, 12 flip-flops, 55 routed nets, 350 resistors, 389 grounded
capacitances and 160 retained coupling capacitances. The root extractor reproduces
the private native fixture byte-for-byte. All 15 selected cell types have fresh
Magic GDS extraction, totaling 558 explicit cell capacitances; all 15 transistor
LVS comparisons match topology and W/L without property errors, and a doubled
width control produces property errors. Capacitor-stripped models exactly match
the actual LVS inputs. Geometry/technology/recipes/models/native logs are pinned
by `receiver_reset_fixture_caps/extraction.json`.

A new native SS125/450 MHz transient withdraws the committed RUN boundary control
for 1.500 ns between half-supply crossings. Reset synchronization, tracking
release and event/pipe reset-buffer waveforms now come from the mapped circuit.
External reset, acquisition-inactive and committed RUN control generation, PLL
and tie-high remain ideal boundaries; acquisition/handoff state generation and
BBPD reset export remain outside the fixture. The sampled BBPD stays connected
to the initial external reset for this receiver stress test. Results are pending.
The separate direct 1.500 ns event-reset withdrawal transient also continues.
Existing native campaigns and their pinned sources are unchanged.

The direct 1.500 ns event-reset withdrawal transient completes at SS125 and
passes the corrected checkpoint026 RTL consumption replay. Physical READY2 drops
at 17.619629 ns and re-arms at 23.605259 ns. The stale UP2 stage clears at
21.206003 ns, 2.399255 ns before re-arm. RTL consumes only the next UP at
60.100 ns: one UP, zero DN and zero stale UP. A separate guard-bypass negative
control accepts a stale UP at 20.100 ns and is rejected. An independent audit
verifies native input/artifact hashes, the full finite monotone waveform,
measured 1.500 ns reset width, ordering of stale stage/guard crossings, both RTL
artifact hashes and the positive/negative replay outcomes. Evidence:
`receiver_ready_withdrawal_1500ps/independent_audit.json`. The 0.150 ns failure is
retained. This establishes deterministic guard behavior at one valid-width
source case; full-PVT/integrated reset generation and statistical MTBF remain
unqualified. The 46-cell integrated reset transient continues separately.

The sampled detector phase campaign completes all 1530 native simulations at
45 PVT points, 17 offsets and both edge times. The original parent is terminal.
Strict signed screens do not all pass near the detector transition region; those
failures remain in the per-point receipts. A final independent full-grid native
waveform/hash/curve audit is running, with output `phase_transfer_final.json`.
Until that audit completes, the verified phase claim remains snapshot006's
1326 points/78 curves; no full-PVT detector bound or whole-PLL claim is made.

The final sampled phase-transfer audit verifies all 1530 terminal native waveforms
and all 90 expected curves across the complete 45-PVT/17-phase/two-edge grid.
Every curve is exclusive, monotone and bracketed. Transition brackets span
-125..-100 through -25..0 ps; maximum absolute deterministic bound is 125 ps.
Near-zero strict sign failures remain recorded. Lumped loads, fixed-rail signal
reduction and the absence of full-loop settling/jitter/MTBF still limit this
result. Evidence is `bbpd_sampled/phase_transfer_final.json`.

The six-case alignment sweep using GDS cell capacitance also completes and passes
an independent grid/waveform/hash/capture audit. UP first-stage data-minus-clock
crossings range from +49.20 to -63.73 ps, including +0.66/-4.89 ps near coincidence;
the DN pilot measures -312.85 ps. This is deterministic SS125 behavior, not a
statistical aperture/MTBF result.

The 46-cell mapped-reset transient completes and checkpoint026 RTL replay consumes
only the next UP event at 60.100 ns. A 1.500 ns committed-RUN withdrawal produces
a 5.636375 ns event-reset low pulse through the actual reset logic. Stale UP2
clears 4.620930 ns before READY2 re-arms. An independent audit verifies full native
waveforms, input/artifact hashes, pulse widths/orderings and RTL outcomes. The
integrated guard-bypass variant also passes this alignment, so that control is
inconclusive; only the earlier direct-reset control demonstrates a distinguishing
stale event. No guard-redundancy or full-PVT/reset/MTBF claim is made. Evidence is
`receiver_integrated_reset_withdrawal/independent_audit.json`.

`collapse_cell_rc.py` creates a verification-only MOS view by shorting extracted
resistors and omitting capacitors. It rejects resistor components joining distinct
external ports. `add_receiver_cell_rc.py` retains the physical resistor/capacitor
models and wraps their named pin order while keeping the mapped cone/external RC
byte-for-byte. Fresh extraction covers all nets of all 15 selected cell types:
3097 cell resistors and 2669 distributed cell capacitors. Native collapsed-MOS
LVS matches topology and W/L for all types; a wrong-width control is rejected.
Junction area/perimeter remain GDS-derived and are not checked by the PDK LVS setup.

A separate dfrtp1 RC probe passes native SS125 capture and 1.500 ns reset behavior,
with a 20 fF output load and 450 MHz/200 ps clock ramps. Its 32 MOS devices, 294
resistors and 245 capacitors produce correct low/high/reset/recapture states.
Internal R adds approximately 15.84..33.82 ps to these four crossings relative
to the capacitance-only model. This difference is retained rather than assumed
negligible. Initial RC recipes are rejected: two target the pre-flatten root,
one requests unsupported zero tolerance, and the first bulk script has a missing
brace. The accepted recipe uses positive tolerance 0.0001 and explicitly runs
`extresist all` after automatic resistance extraction, which otherwise extracts
only the dfrtp1's eight port nets. All 23 dfrtp1 nets are then extracted, and
native logs confirm complete-net extraction for every bulk cell.

The installed Magic 8.3.623 uses the post-8.3.597 resistance extraction flow
outlined in the [official Magic extraction guide](https://opencircuitdesign.com/magic/howto.html).
The native recipes/logs, geometry, technology, tool binaries, collapsed views and
physical models are pinned in `receiver_reset_fixture_rc/extraction.json`.
A fresh 46-cell reset transient now includes those internal cell resistances
and distributed capacitances, with 16531 native unknowns; it is running. Cell RC
is nominal with no R/C process corners. Full acquisition/handoff generation,
BBPD reset export, supply noise, exact missing cell libraries, statistical MTBF
and whole-PLL release qualification remain open.

`audit_cell_rc.py` independently validates complete-net extraction for every one
of the 15 physical cell models. It checks each native Magic section's final
extracted/output counts equal its total net count, rejects tool usage/parse/open
errors, regenerates every resistor-collapsed MOS view, and requires byte equality
with the actual native LVS input. It verifies all per-cell counts, unique native
transistor matches, identical logical pin lists, no topology/property errors,
the wrong-width rejection and the pinned fixture/source hashes before and after
the audit. All 15 cells pass. Evidence is
`receiver_reset_cell_rc_audit/assessment.json`. The 46-cell transient with these
models remains live under its original process; results and expanded PVT coverage
remain pending. No cell-RC timing or whole-PLL release gate is promoted by this
model-integrity audit.

An upstream HS timing-file inventory checks the recursive `main` and `new-spice`
trees of the [SkyWater HS repository](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hs),
pinned respectively at 1d051f49bfe4e2fe9108d702a8bc2e9c081005a4 and
f10036804d232de8f7842517eb569748a6df88b1. Both contain 7918 Liberty JSON/file
paths and 21 distinct PVT suffixes when CCS-noise variants are included. Only
FF/1.95 V/-40 C matches the required engineering grid; 44 exact grid points are
absent from these filenames. This is a filename inventory, not cell-content or
compatibility qualification, and no library is adopted. Typical25C does not
replace required27C. Evidence is `upstream_hs_timing_inventory/assessment_v3.json`.
Earlier analyses are rejected for truncating string matches and then omitting
CCS-noise suffixes; the fetched tree responses are preserved and the corrected
analysis uses those same responses without another download.

The primary assessment's outstanding-work list now reflects the completed phase
and model audits while retaining the actual remaining release requirements:
exact PVT timing coverage, a qualified SDF engine, nonlinear receiver/reset and
metastability coverage, full DCO/acquisition calibration, all225 whole-PLL cases,
applicable assembled-chip density/EM/IR and final candidate adoption/re-audit.
The full-cellRC reset transient and coupled PVT campaign remain live and are
not restarted. An optional question asks whether additional characterized HS
Liberty sources are available; work not depending on them continues.

The full-cellRC 46-cell reset transient completes natively at SS/1.62 V/125 C,
with the original 450 MHz/200 ps-ramp PLL source and committed-control waveform.
Checkpoint026 RTL replay consumes only the next UP at 60.100 ns and no stale or
DN event. The 1.500 ns command-low interval produces 5.659649 ns event-reset low
width. Stale UP2 clears 4.646974 ns before READY2 re-arms. Independent remeasurement
verifies complete finite/monotone native rows, original input/artifact hashes,
command/reset pulse widths, stage/guard ordering and both RTL outcomes. The
integrated guard-bypass remains inconclusive in this alignment; its simulation
also passes and its expected-failure harness explicitly rejects the control as
non-distinguishing. Earlier direct-reset guard-bypass evidence remains separate.
Evidence: `receiver_integrated_reset_rc_withdrawal/independent_audit.json`.

This result includes nominal internal cell resistance/capacitance and maximum
routed interconnect RC. It remains one PVT/alignment with ideal external reset,
committed controls, PLL and tie sources; acquisition/handoff generation, BBPD
reset export, cell-RC process corners, statistical metastability and full-loop
release criteria remain unproved. The completed transient is not restarted.
The original coupled180 PVT campaign and extracted-DCO calibration are still
confirmed live. Release and final-candidate selection remain false.


The full-cell-RC reset test now extends to all 45 primitive PVT points, both
+/-250 ps input directions and both 20/200 ps REF/DIV edge times: 180 native
90 ns transients at 450 MHz. `characterize_receiver_reset_rc.py` preserves the
46-cell mapped cone, nominal internal cell RC and maximum routed RC, with the
same 1.500 ns committed-RUN withdrawal. All 180 circuits are prepared, and
1345 pinned input hashes verify inside the native-tool container. Four Xyce
workers are running under original parent PID2210548; no point has completed
at this observation. Evidence is `receiver_reset_rc_pvt/input_manifest.json`.

The measurement control reuses the completed full-RC SS/1.62 V/125 C waveform:
the correct UP interpretation passes, and deliberately interpreting it as DN
fails. Evidence is `reset_rc_metrics_native_control.json`. The sweep measures
physical stage capture and re-arm behavior; later RTL consumption replay is
still required. Earlier events before withdrawal can be legitimate and are
retained. Ideal external reset, committed controls, PLL and ties, nominal cell
RC without process corners, omitted acquisition/handoff generation and BBPD
reset export, and absent statistical metastability/full-loop proof limit this
screen. Release and candidate selection remain false. The other coupled-receiver
campaign and extracted-DCO calibration continue under their original processes.


`replay_receiver_reset_pvt.py` extends deterministic measured-storage RTL replay
to both UP/DN phase directions and all three supply voltages, using each supply's
half-voltage crossing threshold. It checks exactly one event of the expected
direction consumed in 50..85 ns and no opposite-direction consumption over the
full replay. Legitimate pre-withdrawal events remain allowed and reported; this
check alone does not prove absence of stale same-direction consumption.
The completed SS125 full-cell-RC waveform consumes one UP at60.1ns. Swapping only
the UP/DN measured-storage connections consumes DN at60.1ns and is rejected.
Independent audit verifies all input/artifact hashes, event counts, and that
only the two storage connections differ. Evidence is
`receiver_reset_pvt_replay_control_audit.json`.

`watch_receiver_reset_replays.py` is live under PID2211729 and waits for terminal
receipts from the original 180-point analog campaign, replaying each completed
waveform and retaining failures. It never restarts analog jobs. Analog and
full-PVT RTL replay coverage remain pending; remaining logic still uses RTL
rather than mapped gate timing, and statistical metastability and whole-PLL
qualification remain open. Release and candidate selection remain false.


`audit_coupled_receiver.py` independently audits the coupled180 campaign's
exact grid, all prepared input hashes, native terminal logs, complete finite
monotone90ns waveforms, and expected receiver polarity/initialization/two-event
capture and settling levels. It remeasures threshold crossings directly and
compares them with each original receipt; deliberately reversing the expected
direction must fail every completed waveform. Input and artifact hashes are
checked again after the audit. All168 completed cases pass and reject the
opposite-direction control: SS36, TT36, FF36, SF36 and FS24. Evidence is
`coupled_receiver_progress_002.json`. Twelve FS cases remain pending under the
original live process. This remains the17-cell event receiver screen with fixed
maximum routeRC and ideal rails; synchronizer/reset coupling, statistical MTBF
and whole-PLL behavior are outside its scope. No release gate is promoted.


The original coupled180 campaign completes natively with all180 capture screens
passing. `audit_coupled_receiver.py` independently validates all180 exact-grid
waveforms and input/artifact hashes, recomputes both signed event captures and
settling levels, and rejects the deliberately wrong direction for every case.
Each of SS/TT/FF/SF/FS contributes36 completed cases. The native final assessment's
complete receipt set and hashes match the independently audited180 receipts.
Evidence is `coupled_receiver_final_audit.json` and
`coupled_receiver_final_receipt_audit.json`. The original parent has terminated;
the campaign is not restarted. The primary assessment and retained candidate
README now reference these terminal results.

This completes the45 primitive-PVT x +/-200ps x20/200ps event-receiver screen,
with17 mapped nonlinear cells and fixed maximum routed RC. It does not include
nonlinear synchronizers/reset generation or statistical metastability, and its
ideal rails/static aggressors do not qualify whole-PLL phase/lock/jitter/power.
The separate full-cell-RC46-cell reset campaign, automatic RTL consumption
replays and canonical extracted-DCO calibration remain live. Exact cell timing
library coverage and other release requirements remain open; release and final
selection remain false.


`audit_receiver_reset_replay.py` independently checks same-direction stale
consumption, beyond the replay's signed post-window count. It derives supply
and phase directly from the native deck, remeasures the physical event-reset
assertion and next REF opportunity, verifies complete finite/monotone native
rows and all native/RTL artifact hashes, and reconciles actual accepted-event
log entries with replay counters. The full-cell-RC SS125 pilot passes: event
reset asserts18.243316ns, next REF opportunity is50.010ns, no event is consumed
between those boundaries, and only the fresh UP at60.100ns is consumed.
Evidence is `receiver_reset_pvt_replay_stale_audit.json`.

The initially assumed pipeline-reset boundary is rejected: RUN withdrawal
leaves pipeline reset deasserted, while event reset flushes pending captures.
The rejected source and evidence are retained as
`audit_receiver_reset_replay_rejected_pipeline_boundary.py` and
`receiver_reset_replay_rejected_boundary.json`. Other PVT stale-consumption
audits remain pending. This deterministic mixed-boundary check does not add
mapped gate timing, MTBF or whole-PLL proof; release remains false.


The first four180-point full-cell-RC reset cases complete at SS/1.62V/-40C,
covering both +/-250ps directions and20/200ps REF/DIV edges. All four native
stage screens and actual signed RTL replays pass. Independent reset-to-next-REF
consumption audits verify whole native waveform and artifact hashes, reconcile
actual accepted-event logs with counters, and find no stale or opposite event.
The two UP cases consume only UP at60.100ns; the two DN cases consume only DN
at62.322222ns. Evidence is `receiver_reset_rc_pvt_progress_001.json` and its four
pinned `reset_stale_audit_ss_1.62V_-40C_*.json` audits. The original campaign and
replay watcher continue;176 points remain pending. This is functional measured
storage replay at deterministic thresholds, not gate timing, statistical MTBF
or whole-PLL signoff. Release and selection remain false.


`watch_receiver_reset_audits.py` is live under PID2214320. It independently
checks every terminal native/RTL replay pair through
`audit_receiver_reset_replay.py`, preserves native/replay/audit failures and
writes atomic progress records. It waits for actual terminal receipts, verifies
source/artifact pins, and never restarts or modifies analog jobs. Its first four
results are byte-identical to the earlier manual stale/direction audits.
Evidence is `receiver_reset_rc_pvt_consumption_snapshot_001.json`; continuing
results go to `receiver_reset_rc_pvt_consumption_audits`. Remaining176 native
points and their replay/audits are pending. This automation adds independent
stale-consumption coverage as results arrive without promoting gate timing,
MTBF or whole-PLL release qualification.


The next uncovered detector-reset boundary is now extracted rather than replaced
by an ideal copy of the receiver tracking guard. In checkpoint026,
BBPD_RESET_N is exported through export_alias_0 from net392, driven by the
separate gen_feedback_tracking.release_pipe path. Tracing its actual dependencies
includes coupled divider, handoff, acquisition and loop-filter control state.
`extract_receiver_macro_reset.py` emits4547 mapped cells,554 flip-flops, six
attached nonlinear antenna diodes and169 cell types, with4573 routed nets,
19101 routed resistors,21720 ground capacitances and36761 coupling capacitances.
The actual package BBPD_RESET_N node retains its output wire to the mapped
export buffer. Explicit top-level configuration and additional tie sources are
listed in the receipt. All46 previous mapped receiver/reset cells are preserved
with identical types/connections, and fresh reproduction is byte-identical.
Input hashes verify. Evidence is `receiver_macro_reset_extraction_audit.json`.

This is a graph/extraction result, not simulated reset qualification.154 cell
types beyond the existing15 still need qualified internal-RC models. The expanded
graph includes partial acquisition/handoff/control generation but continues to
cut acquisition-inactive and committed RUN signals; it is not the complete
acquisition/PLL boundary. Its inherited extraction-receipt limitation text about
omitted acquisition/handoff generation is coarse; the independent audit records
this more precise scope. REF, PLL, external configuration/reset and ties remain
ideal; physical chip/macro wiring, cell-RC corners, actual DCO, supply noise,
MTBF and whole-PLL behavior are still unproved. Early attempts were rejected for
missing explicit REF/configuration/tie terminals, mismatched escaped net names
and treating an attached diode as an ordinary Liberty capacitance. Those output
directories remain separate. The existing full-RC reset PVT jobs and both replay
watchers are unchanged and live. Release and final selection remain false.


`extract_macro_reset_cell_rc.py` completes nominal internal-RC extraction for
all168 active transistor cell types needed by the expanded detector-reset graph.
It uses the previously validated complete-net Magic flow (0.0001 resistance
tolerance, all nets, simplify off,0.01fF capacitance threshold), retains actual
GDS junction geometry and checks every transistor-only resistor-collapsed view
against the pinned cell schematic with native Netgen. All168 topology and
width/length comparisons pass. A single doubled-width dfrtp_1 transistor is
rejected for property errors. Independent audit regenerates every LVS projection
byte-identically, verifies all168 complete-net statistics, native comparisons,
input/artifact hashes before and after and the exact one-width mutation. The
unique cell definitions contain21839 resistors and21901 capacitors. Evidence is
`receiver_macro_reset_cell_rc/assessment.json` and
`receiver_macro_reset_cell_rc_audit/assessment.json`.

The antenna diode is excluded from this MOS-cell RC qualification. The raw
expanded fixture inherited the uncorrected legacy diode schematic, whose
perimeter disagrees with the physical junction; it is rejected for simulation.
Fresh native KLayout measurement gives junction area0.6417um2 and perimeter3.24um.
The existing strict HS diode normalization prepares a separate private canonical
view; raw PDK and extracted graph are preserved. Evidence is
`receiver_macro_reset_diode_geometry/assessment.json`. Diode electrical/internalRC
validation and assembly of the corrected expanded RC fixture remain pending.
No native expanded-cone or whole-PLL result is claimed. CellRC is nominal without
process/temperature corners, and LVS does not compare junction area/perimeter.
The original reset PVT campaign, its two watchers and DCO calibration stay live;
release and selection remain false.


The remaining diode physical model now has seven resistors and eleven
capacitors, with all five nets extracted. Native Netgen matches its actual
junction topology, area and perimeter against the independently GDS-measured
canonical view; one doubled-area and one doubled-perimeter control are both
rejected for property errors. Independent resistor-collapse regeneration matches
the native verification input byte for byte. Evidence is
`receiver_macro_reset_diode_rc/assessment.json`. Unmodified Xyce probes atSS125
andFFcold reject the PDK level3 diode model; those failures are preserved.

The older diode translation qualification covers a different junction geometry
and is not reused as proof. Separate geometry-specific helpers in
`verification/timing450` retain the model equations and error limits while using
actual area0.6417um2/perimeter3.24um, DC bias-0.2..1.95V, five AC/noise biases
0/0.81/1.62/1.8/1.95V, and all five primitive corners/three temperatures. All15
ngspice47/Xyce electrical cases and all75 noise cases pass. Maximum relative
differences are0.0220624% DC,0.000541031% complexAC,0.0174164% rising charge,
0.0383274% falling charge and0.00187786% noise PSD. The independent checker
verifies complete coverage, actual geometry and temperature directives, PDK,
reference/native binaries, input hashes and raw DC/AC/charge/noise measurements.
It pins1000 evidence files. Evidence is
`receiver_macro_reset_diode_qualification.json`. The first copied harness
incorrectly retained the legacy110-point DC count; it is rejected and preserved.
The corrected87-point harness and fresh output are separate; model equations and
comparison limits are unchanged. Original `scripts/*.py` remain unchanged by
this geometry-specific experiment.

`add_macro_reset_cell_rc.py` assembles all169 physical cell definitions while
retaining the complete4547-cell mapped graph and routed RC byte for byte. Its
SS125 diode translation uses only the checked geometry and fixed corner and
temperature. The unique definitions total21846 resistors and21912 capacitors.
The assembly audit checks all named-port wrappers and modelRC counts. Evidence is
`receiver_macro_reset_fixture_rc_ss125/assembly_audit.json`. No inherited raw
diode view is used in this fixture.

`characterize_receiver_macro_reset.py` launches a native90ns SS/1.62V/125C
integration pilot at450MHz, connecting the sampled detector's reset to the actual
mapped package BBPD_RESET_N output. Original parentPID2234052/nativePID2234105
are live; native completion and full functional audit remain pending. Source
pins and fixed model corner/temperature are checked. REF/DIV/PLL/configuration,
ties, acquisition-inactive and committed RUN cuts remain ideal; partial coupled
acquisition/handoff/divider/control state is retained. This is still not complete
acquisition/DCO/whole-PLL qualification, statistical metastability or cellRC
process-corner coverage. The original180-point reset campaign, its two watchers
and DCO calibration continue. Release and selection remain false.


The assembled169-model reset-export fixture now has an additional independent
wrapper audit. Every active wrapper's exact physical port order and internal
body matches its native GDS model, rather than comparing only port sets andRC
counts. The diode wrapper preserves all seven resistors/eleven capacitors and
changes only its one primitive to the checked fixed-geometry translation.
Native Netgen confirms a positive buffer wrapper against its schematic. A
control swapping only the wrapper's input/output connections fails top-level
pin matching; transistor topology stays equivalent but boundary pin roles do
not. The native JSON contains unmatched pins even though badnets/badelements
are empty, so the audit checks the actual native pin result. Evidence is
`receiver_macro_reset_wrapper_audit/assessment.json`.

The expanded native pilot remains live and reports672589 unknowns and1144394
devices (553757 capacitors,528390 resistors,62206 MOS and six translated diodes).
Its DC initialization is not a functional pass. The smaller reset PVT campaign
has eight completed native/replay/independent-consumption audits, all passing;
`receiver_reset_rc_pvt_consumption_snapshot_002.json` freezes that progress.
Original analog jobs, both watchers and canonical DCO calibration are live.
Release, final selection and expanded-cone qualification remain false.

The expanded physical macro-reset pilot now has a frozen partial observation
in `receiver_macro_reset_ss125_partial_observation_001/assessment.json` and a
separate terminal-audit watcher. In this observation the actual BBPD reset output
has not crossed half supply and UP2/DN2 have not risen, although the event reset,
tracking-active and ready guards have cycled. This is not an active-detector
qualification or a terminal design failure. Checkpoint026 RTL releases the
macro reset only after its fine-domain bundle and tracking conditions are met;
the graph retains that acquisition/handoff dependency despite the separate
ideal fast-domain acquisition-inactive/committed RUN cuts. The acquisition RTL
uses four settling cycles and 32 scan cycles per coarse band, so a cold-start
90ns pilot cannot be assumed to have completed acquisition at a 25MHz reference.

New helpers `audit_receiver_macro_reset_native.py` and
`replay_receiver_macro_reset.py` require a terminal native receipt, exact
23-column header, full finite monotone 90ns waveform, native end marker and
unchanged source/artifact hashes. The native audit records actual macro-reset
and storage exercise separately from completion; it never grants functional
qualification. The replay derives signed phase from the actual deck and retains
missing/wrong-direction consumption failures. `watch_receiver_macro_reset.py`
waits for the existing pilot receipt, runs both checks, and preserves their logs
without starting or restarting analog work. A positive replay would still need
an independent stale-consumption audit and a direction mutation control. The
new native checker rejects the live pilot before it has a terminal receipt.
The existing pinned analog helpers and native input decks remain unchanged.

A successor diagnostic separates committed tracking from cold acquisition.
`extract_receiver_committed_macro_reset.py` introduces explicit boundaries at
actual mapped divider-output Q, committed fine RUN, and the six source and six
committed coarse bits. It preserves all46 original receiver/reset cells and the
actual fine reset synchronizer, coarse comparator, two release stages, clock
paths and macro-reset export. The resulting98 mapped cells use31 physical cell
types across121 routed nets,895 route resistors,971 ground capacitors and477
coupling capacitors. A fresh extraction reproduces its SPICE byte for byte.
Evidence is `receiver_committed_macro_reset_structural_audit.json`.

`assemble_committed_macro_reset.py` reuses the qualified SS125 physical cellRC
and diode definitions byte for byte, verifies their provenance and port orders,
and preserves the successor routed graph exactly. Its native pilot extends to
300ns and withdraws committed fast/fine RUN for1.5ns at147.05ns, leaving time for
actual fine-domain release and later detector sampling. Both coarse bundles are
zero and the ideal divided clock is25MHz, consistent with450MHz/divide18. The
native result remains pending. This diagnostic supplies committed conditions;
it does not prove acquisition, bundle handoff or divider generation. The full
4547-cell cold-start pilot and original180-case reset campaign remain running.
The first successor extraction is retained as stale evidence after an output
format-only helper change; version2 is the pinned source used by the pilot.
Release and candidate selection remain false.

The committed-bundle300ns pilot now has its own pinned terminal-check watcher,
`watch_committed_macro_reset.py`, with native waveform audit, measured-storage
RTL replay, independent fresh/stale consumption audit and signed-direction
mutation control. The replay requires actual physical macro-reset release after
withdrawal and derives its acceptance window from the next measured REF rise;
it does not reuse the earlier90ns fixture's50..85ns window. The independent
checker derives that opportunity again from native traces, reconciles logged
consumption against counters, requires one correctly signed fresh event, and
rejects any consumption between event-reset assertion and the new opportunity.
It additionally requires physical macro-reset assertion/release and initial
release before withdrawal. Direction swap is run only after a positive replay
and independent consumption audit, avoiding a vacuous failure control.

All four new helpers compile. Passing the earlier terminal22-column90ns fixture
to the successor replay is rejected at the exact waveform-header check. Native
simulation and watcher are live (nativePID2266776/watcherPID2267065); the first
partial observation is7.63ns/300ns and is not a functional result. Terminal
checks remain pending and release/selection remain false. The original reset
PVT campaign remains136/180 passing native/replay/independent audits.

The original reset PVT campaign has advanced to140/180 native points with actual
RTL replays and independent consumption audits, all passing. The four newly
terminal SF/1.95V/27C cases cover both signed250ps phase directions and both
20/200ps edges. Their native/replay/audit artifact hashes are independently
rechecked; each has one correctly signed fresh consumption, no opposite event
and no stale consumption after event-reset assertion before the next REF.
`receiver_reset_rc_pvt_consumption_snapshot_003_140points.json` freezes the
watcher's140-point receipt. Main implementation assessment observation counts
are updated;40 points and broader reset/mode/MTBF/wholePLL qualification remain.
Both physical macro-reset pilots and their watchers are live. Release and
candidate selection remain false.

Reset PVT coverage has advanced to144/180 passing native/RTL/independent
consumption cases. The four newly completed SF/1.95V/125C cases cover both
signed250ps phases and both20/200ps edges. Independent revalidation checks1387
unique artifact pins, one correct fresh event, no opposite event and no stale
consumption for each. Snapshot
`receiver_reset_rc_pvt_consumption_snapshot_004_144points.json` and the main
assessment record the new count. The final36 points and broader mode, physical
macro-reset, metastability and wholePLL qualification remain pending. Original
native jobs and watchers remain live; release and selection remain false.

The committed300ns pilot now demonstrates initial physical macro-reset release
at133.313807862ns in a frozen partial observation,
`receiver_committed_macro_reset_partial_release_001/assessment.json`. This is
still a nonterminal observation. The release follows REF130ns, and its147ns
withdrawal precedes the next REF170ns. Therefore that alignment does not exercise
withdrawal of an event loaded by REF sampling. It remains valid startup/rearm
diagnostic evidence and remains running; it must not be promoted to loaded-event
withdrawal qualification.

A separate350ns pilot in `receiver_loaded_macro_reset_ss125` uses the same pinned
98-cell physical fixture and moves withdrawal to187.05ns, after the REF170ns
opportunity. `characterize_loaded_macro_reset.py` leaves existing native inputs
and jobs unchanged. A separate watcher and native/replay/independent-consumption
helpers retain full waveform/source/hash checks and signed-direction mutation.
The independent loaded-event auditor additionally requires exactly one correct
pre-withdrawal consumption and actual second-stage event storage high at
withdrawal. This prevents a passing fresh-event case from masking an unexercised
loaded-event reset condition. All new helpers compile; native functional results
remain pending. This is still one SS125/1.62V/450MHz alignment with ideal
committed boundaries, not acquisition/handoff/mode/MTBF/wholePLL qualification.
Release and selection remain false.

### Reset PVT progress: 148 independently audited points

The live 180-point campaign now has 148 terminal native traces, RTL replays and independent signed/stale consumption audits passing. The four new FS/1.62 V/-40 C points cover both +/-250 ps phase offsets and 20/200 ps edges. Their audit artifacts and 1,387 unique evidence pins were independently reverified in the native container. Each has exactly one correct fresh event, no opposite event and no stale event in the audited reset interval. The frozen receipt is `build/timing450/interface_characterization/receiver_reset_rc_pvt_consumption_snapshot_005_148points.json`. The original parent and both audit watchers remain live; 32 points remain pending. This retains the 450 MHz, fixed route RC, nominal internal RC and ideal external-control limitations; it does not establish statistical MTBF, physical macro-reset qualification or whole-PLL release readiness.

### Reset PVT progress: 152 independently audited points

The live campaign has 152/180 terminal native, RTL replay and independent consumption audits passing. The four new FS/1.62 V/27 C points cover +/-250 ps phase and 20/200 ps edges. Their audit artifacts and 1,387 unique evidence pins were independently verified in the native container; each has exactly one correct fresh event, no opposite event and no stale event in the audited interval. The immutable receipt is `build/timing450/interface_characterization/receiver_reset_rc_pvt_consumption_snapshot_006_152points.json`. The parent and both audit watchers remain live; 28 points remain. Scope remains 450 MHz with nominal internal RC, fixed route RC and ideal external controls; physical macro-reset, statistical MTBF and whole-PLL release qualification remain incomplete.

### Committed physical macro reset: complete 300 ns diagnostic

The 98-cell SS/1.62 V/125 C committed-control pilot completed natively with exit code zero and an Xyce end marker. All four terminal checks pass: complete finite-wave audit, positive measured-storage RTL replay, independent fresh/stale consumption audit, and rejection of the direction-swap control. Independently verified 3,589 unique evidence pins plus command-log and receipt hashes. Physical macro reset asserts at 149.624443 ns and releases at 213.313847 ns after withdrawal; the replay consumes exactly one fresh UP at 260.1 ns, with no opposite event and no stale event in the audited interval. Receipt: `build/timing450/interface_characterization/receiver_committed_macro_reset_ss125_terminal_checks/assessment.json`.

This remains a startup/rearm diagnostic: initial physical reset release occurs after REF130 and before withdrawal147, without a REF sampling opportunity between them. It therefore does not exercise withdrawal of an already loaded event. The separate 350 ns loaded-event pilot remains live. Ideal committed controls/clocks, one PVT/alignment, nominal cell RC and fixed route RC remain limitations; full acquisition/handoff, statistical MTBF and whole-PLL qualification are incomplete. Release and selection flags remain false.

### Reset PVT progress: 156 independently audited points

The live campaign has 156/180 native, RTL replay and independent consumption audits passing. The four new FS/1.62 V/125 C points cover +/-250 ps phase and 20/200 ps edges. Their audit artifacts and 1,387 unique evidence pins were independently verified in the native container; each has exactly one correct fresh event, no opposite event and no stale event in the audited interval. Frozen receipt: `build/timing450/interface_characterization/receiver_reset_rc_pvt_consumption_snapshot_007_156points.json`. The original parent and both audit watchers remain live; 24 points remain. Scope remains 450 MHz with nominal internal RC, fixed route RC and ideal external controls; statistical MTBF and whole-PLL release qualification remain incomplete.

### Reset campaign terminal reconciliation and loaded-event result

The original 46-cell receiver/reset campaign is complete: all 180 native traces, RTL replays and independent signed/stale consumption audits pass. All 180 audit receipts and their input/output evidence pins were independently reverified in the native container (2,975 unique pins). The frozen receipt is `build/timing450/interface_characterization/reset_terminal_independent_reverification_001.json`. The primary implementation assessment now records completion. This covers 450 MHz, 45 primitive PVT points, +/-250 ps phase and 20/200 ps edges, with nominal internal cell RC, fixed routed RC and ideal external reset/committed controls. It does not qualify statistical MTBF, upstream acquisition/handoff or whole-PLL behavior.

The 98-cell 350 ns loaded-event physical-reset pilot also completed and passed all four terminal checks, including independent consumption and direction-swap rejection. Storage is high before withdrawal and the replay consumes UP at 180.1 ns. Physical macro reset asserts at 189.624855 ns and releases at 253.313814 ns; after REF290.01 the replay consumes one fresh UP at 300.1 ns, with no stale or opposite event. All pinned evidence was independently reverified; the combined receipt above records 5,409 unique pins across the campaign, loaded-event pilot and expanded-test evidence. This remains one SS/1.62 V/125 C alignment with ideal committed boundaries and mixed measured-storage/RTL timing, not full PVT/mode/acquisition or MTBF signoff.

The expanded 4,547-cell 90 ns native test completed and passed its complete-wave audit, but physical macro reset never released and event storage was not exercised. The fresh-event RTL replay failed with exit code 1. Its failed terminal qualification is retained in the primary assessment; native completion does not qualify this acquisition/handoff path. Release, timing-closure and selection flags remain false.

A separate DN loaded-event pilot is now running in `receiver_loaded_macro_reset_ss125_dn`, using `characterize_loaded_macro_reset_direction.py`. Its deck is byte-identical to the verified UP pilot except DIV phase (10.25 ns to 9.75 ns). The same finite-wave, measured-storage replay, independent loaded/fresh/stale consumption and signed-direction mutation checks are attached. Native and functional results remain pending; this adds direction coverage at the same SS/1.62 V/125 C point and does not replace full interface, acquisition or whole-PLL qualification. The first launcher attempt rejected a campaign prototype lacking a standalone input manifest before any simulation; its log is retained.

### Completed canonical DCO waveform audit

`audit_dco_completed_waveforms.py` independently audited all eleven terminal coarse0 SS/1.62 V/125 C points while the original calibration continues at code072. The frozen receipt is `build/timing450/interface_characterization/canonical_dco_terminal_wave_audit_001.json`; 6,746 evidence pins cover source/model provenance fingerprints and completed native decks/logs/waves/measurements. Each full300ns waveform is finite and strictly monotone in time. Every complete100..300ns rising-edge cycle contains exactly one falling edge, positive high/low widths and a first-two-cycle frequency consistent with the native measurement. Original negative crossing-index pulse measurements are retained, and pulse widths are independently derived from the waveform.

Code057 has92 complete cycles, first-two-cycle frequency464.693394MHz and whole-window mean464.759858MHz. These different window estimates remain convergence evidence to assess, not proof of settled frequency or physical jitter. A waveform truncated at250ns while retaining the Xyce end marker is rejected by the duration check; its frozen control receipt is `canonical_dco_truncated_wave_control_001/assessment.json`. Missing codes, convergence/interpolation, fullPVT/acquisition model, physical noise/jitter and wholePLL qualification remain incomplete. Release, timing closure and selection remain false.

### Baseline DCO window settling screen and independent probe

`audit_dco_window_settling.py` compares the completed baseline first-two-cycle estimate with four50ns windows spanning100..300ns, using the engineering allowance of the smaller of100ppm of450MHz and0.25 of the measured available adjacent-code spacing. The frozen receipt is `build/timing450/interface_characterization/canonical_dco_window_settling_001.json`. Codes24,25,40,41,56,57 fail the initial-to-final diagnostic screen. All final adjacent-window differences remain within that allowance, but this does not prove independent convergence. At code17 the difference is28.543487kHz against37.808913kHz allowance, and the final250..300ns frequency is450.024267MHz.

A separate code57 canonical extracted-DCO probe now runs in `build/modern_25mhz/canonical_hot_ss_450_c0_code57_settling_probe_001`:200ns measurement start,600ns end,5ps maximum step, reltol1e-6 and abstol1e-10. These match the existing calibration controller's planned longer-settling variant and leave the original35-point parent and its pinned inputs unchanged. The probe remains pending; its result must be audited and compared with baseline, tighter-tolerance and half-step variants before convergence can be qualified. Full code/PVT/interpolation, wholePLL, physical jitter/power and release qualification remain incomplete.

### Parallel canonical convergence variants

The full35-code SS/1.62 V/125 C tighter-tolerance and half-step variants now run with two workers each in isolated `build/modern_25mhz/canonical_hot_ss_450_parallel_convergence_001/ss_1.62V_125C/{tolerance,step}` directories. The original baseline parent, loaded-event DN pilot and independent code57 longer-settling probe remain live. All6,690 source/model provenance files and the complete35-code vector match baseline. Only reltol/abstol change to1e-6/1e-10 for tolerance; only print/maximum step change to5ps for step. The frozen recipe audit is `build/timing450/interface_characterization/canonical_dco_parallel_variants_recipe_audit_001.json`. Native results remain pending; verified terminal caches may later be reconciled with the controller after matching deck/provenance/completion checks.

The initial launch used future controller variant directories. Those two new process groups were stopped and their partial files retained in `canonical_dco_initial_parallel_launch_retained_001`; isolated replacement launches remove the possibility of concurrent writes when the original controller advances. Original jobs and their active inputs were not altered. These variants add full code coverage at one PVT point and do not establish full45-point calibration, interpolation, wholePLL or release qualification.

### Full longer-settling convergence sweep

The full35-code SS/1.62 V/125 C longer-settling variant runs with two workers in the isolated parallel convergence `settling` directory. Its6,690 source/model provenance files and code vector match baseline, with200ns measurement start,600ns end,5ps print/maximum step and reltol1e-6/abstol1e-10. The frozen recipe audit is `build/timing450/interface_characterization/canonical_dco_parallel_settling_recipe_audit_001.json`. All four required convergence variants now advance concurrently; terminal and independent calibration results remain pending.

Exact cache reuse remains conditional: the controller computes reltol by dividing baseline by10, whose floating-point serialization differs by one rounding unit from literal1e-6 in the parallel tolerance/settling launches. Their actual parameters are recorded without changing provenance. Do not promote these as exact controller-cache matches; use separate independently audited calibration integration or require exact fingerprint/deck compatibility. The half-step variant has no such tolerance serialization change. FullPVT/interpolation, acquisition/wholePLL and release qualification remain incomplete.

### Corner-matched physical reset fixture grid

`prepare_committed_reset_pvt_fixtures.py` prepares15 fixed-diode corner/temperature views for the98-cell physical reset fixture from the qualified diode electrical/noise grid. It verifies2,408 source pins. An independent audit compares each model block against its frozen Xyce electrical test deck and checks every physical cell/route prefix byte-for-byte; the SS/125C fixture reproduces the prior view byte-identically. Receipts are `receiver_committed_macro_reset_pvt_fixtures_001/assessment.json` and `receiver_committed_reset_pvt_fixture_independent_audit_001.json`. These are prepared models, not completed PVT behavioral tests; nominal cellRC/fixed routeRC, ideal committed controls, metastability and wholePLL limitations remain.

A separate FF/1.95V/-40C/450MHz/+250ps loaded-event pilot runs in `receiver_loaded_macro_reset_ff195_cold_up`, with matching diode translation and native primitive corner/temperature/supply. Separate PVT native driver/auditor/watcher preserve the active SS inputs. The existing complete-wave replay, independent loaded/fresh/stale signed consumption and direction-swap checks are attached. Native and terminal functional results remain pending; release/selection remain false.

Loaded reset discrete edge preparation: added separate `characterize_loaded_macro_reset_pvt_edges.py` with 20/200ps REF/DIV edges and preparation-only mode; running PVT sources unchanged. Prepared SS/1.62V/125C DN200ps deck. Independent byte comparison confirms only REF/DIV edge changes and replacement by a byte-identical matching SS125 fixture. Receipt: `build/timing450/interface_characterization/receiver_loaded_macro_reset_edge200_deck_audit_001.json`. No simulation launched or behavioral qualification claimed; full180-case PVT/phase/edge grid and full release gates remain outstanding.

Prepared all180 loaded-reset decks (45 primitivePVT x2 signed phases x20/200ps edges). Source pins verified before/after generation. Independent deck audit checks complete Cartesian coverage, matching fixtures/settings and unchanged remaining circuit bytes: `build/timing450/interface_characterization/receiver_loaded_reset_pvt_grid_deck_audit_001.json`. No grid native jobs launched; no behavioral passes or full release qualification claimed.

Started loaded-reset PVT grid supervisor2494896/python2494921 with two workers. Native SS125 DN200ps2494987 and UP200ps2494990 confirmed live. Queue177 new cases; reuse3 existing SS125UP20ps/SS125DN20ps/FF1.95V-40CUP20ps cases without duplicate native simulations. Reuse deck identity and fixture bytes verified. Four terminal native/replay/consumption/direction-control commands configured per new case; failures retained. Scope remains450MHz, nominalcellRC/fixedrouteRC/idealcommittedcontrols; fullmode/MTBF/acquisition/wholePLL/release gates outstanding.

Independent loaded-reset terminal verifier added separately from active campaign helpers. Reverified the completed SS125 UP20 case, including native/replay/consumption/direction-control receipts and 3598 evidence hashes before/after checks. Frozen receipt: `build/timing450/interface_characterization/receiver_loaded_macro_reset_ss125_independent_terminal_002.json`. SS125 DN20 native simulation completed350ns with exit0; watcher native/replay/consumption/control audits still running. Native completion alone does not establish functional or release qualification.

SS125 DN20 loaded-reset pilot completed350ns. All four terminal commands passed, including expected rejection of swapped direction. Independent verifier checked3599 evidence hashes: `build/timing450/interface_characterization/receiver_loaded_macro_reset_ss125_dn_independent_terminal_001.json`. Physical storage loaded before withdrawal; one DN accepted180.1ns, physical macro-reset asserted189.624841ns/released252.813466ns, one fresh DN accepted300.1ns, no stale/opposite acceptance. Primary DN assessment updated pendingfalse; release/selectionfalse. Scope remains one450MHz SS125 signed-phase/edge case, fixedRC/ideal committed controls; broader grid, allmodes, acquisition, MTBF and release gates outstanding.

Canonical SS125 DCO baseline code072 completed300ns; baseline12/35 points terminal. Extended frozen terminal waveform audit `_002.json` verifies all12 completed traces and6751 evidence hashes; code072 has93 complete measured cycles. Original baseline worker advanced to code073 (native2518591). Independent tolerance/step/settling variants remain pending; terminal waveform audit is not convergence, interpolation or fullPLL qualification. Release/selectionfalse.

Completed DCO code072 baseline diagnostic: first-two-cycle468138580.720Hz versus complete100..300ns mean468224098.686Hz, difference85517.967Hz exceeds45000Hz (100ppm of450MHz). This reinforces baseline estimator/settling concerns; localLSB/four-window helper requires adjacent code073 completion and remains pending. No independent convergence or release claim.

Loaded reset coverage expanded in separate preparation to allfive required modes100/250/300/400/450MHz:900 decks (5x45primitivePVT x2signedphases x2REF/DIVedges). Separate generator/auditor preserve all active campaign inputs. Independent audit confirms exact Cartesian coverage, PLL periods/50percent threshold duty,180 byte-identical450MHz decks, and all other circuit bytes unchanged. Lower modes450ns trace to leave room for slower receiver response,450MHz remains350ns. Frozen audit `build/timing450/interface_characterization/receiver_loaded_reset_all_modes_deck_audit_001.json`; preparation `receiver_loaded_reset_all_modes_prepared_001/preparation.json`. Native mode-aware waveform/replay/consumption/control validation required before launch; no new native jobs or behavioral passes claimed. FixedRC/ideal committed boundaries remain; acquisition/resetgeneration/MTBF/wholePLL/release gates outstanding.

Mode-aware replay work found existing pinned450MHz replay schedules only271PLL edges, stoppingnear300.1ns within350ns trace. Active helpers left immutable. Separate `replay_loaded_macro_reset_modes_v2.py` generates the full trace clock schedule and mode divider ratio, and defines first-fresh consumption interval by measured next storage transition (avoids counting subsequent legitimate events at slower modes). Separate mode-aware consumption/native auditors added. Completed SS125UP/DN pilots replayed with315PLL edges through348.988889ns: signed events180.1,300.1,340.1ns; first fresh300.1ns, no stale/opposite; swapped-direction controls rejected. Independent decimal clock schedule/evidence regression verifies both cases and3606 hashes: `build/timing450/interface_characterization/receiver_loaded_reset_full_clock_regression_001.json`. The340.1ns events were omitted by old replay clock truncation. Native450MHz grid remains running and reusable, but every completed grid case needs separate full-clockv2 consumption/control reaudit before campaign qualification. Lower-mode native/replay validation still pending; no full release claim. Initial mode replayv1 artifacts retained; onlyv2 measured-storage interval is designated for future mode work.

Mode-aware native auditor validated on completed450MHz SS125 pilot. Separate watcher passed allfour native/full-clock replay/measured first-event consumption/direction-swap checks on the same pilot; receipt `receiver_loaded_macro_reset_ss125_modes_watcher_validation_001/assessment.json`. Launched lower-mode pilot supervisor2526644/python2526671, eightSS12520ps cases100/250/300/400MHz xUP/DN, twoworkers. Initial100MHz DN2526733/UP2526756 actualXyce handles verified live; copied decks exactly match independently audited all-mode preparation (10nsPLL period,450ns duration). Frozen initial identity audit `receiver_loaded_reset_lower_mode_pilots_initial_deck_audit_001.json`. No duplicate450MHz natives; existing campaigns remain active. Terminal behavior, allPVT/edges/resetalignments/MTBF/fullacquisition/wholePLL and release qualification remain pending.

Started separate full-clock grid reaudit supervisor2527236/python2527261, twoaudit workers, `receiver_loaded_reset_full_clock_grid_reaudits_001`. Verified both completed SS125UP/DN source deck/fixture identity and3606-regression evidence pins; initial terminal/pass2 reused. Remaining178 cases wait for existing native receipts (includes liveFFcold and177new nativegrid cases). Supervisor invokes new mode-aware native/full-clock replay/measured first-event consumption/direction-swap watcher, retaining any failure. No new analog jobs or restarts. Full450MHz grid qualification still pending; lower-mode pilots and fullresetgeneration/acquisition/MTBF/wholePLL/release gates remain separate.

Added separate immutable mode-aware independent terminal verifier `verification/timing450/verify_loaded_reset_modes_terminal.py`. Completed SS125450MHz watcher receipt passed3598 evidence hashes and independently derived all315PLL transitions through348.988889ns (full350ns trace), mode/PVT/native deck identity, measured storage interval, no stale/opposite signed events and direction-swap rejection. Frozen `receiver_loaded_macro_reset_ss125_modes_independent_terminal_001.json`. Wrong-mode control450MHz receipt required as400MHz rejected before writing a passing receipt; `receiver_loaded_reset_modes_wrong_mode_control_001/assessment.json`. Supports allfive required modes but lower native terminal behavior remains pending; fixedRC/ideal committed cuts/MTBF/fullacquisition/wholePLL/release limitations retained. Active native/replay helpers unchanged.

Launched separate independent terminal collector `verify_loaded_reset_campaign_terminals.py`, supervisor2528551/python2528577, oneverification worker, no analog launches. Exact188-case queue covers180450MHzPVT/phase/edge grid plus8 lower-modeSS12520ps pilots; inherited completedSSUP/DN full-clock regression reused2passes,186pending. Verifies prepared/native deck and fixture identity then invokes mode-aware independent verifier after actual terminal watcher receipts appear, retains failures without retries, and records frozen individual evidence. Live initialized status verified2terminal/2pass; frozen10-pin launch/Cartesian identity audit `receiver_loaded_reset_campaign_independent_collector_launch_audit_001.json`. Remaining712 lower-modePVT/edge cases outside current queue; fixedRC/ideal committed controls/fullresetgeneration/acquisition/MTBF/wholePLL/release gates remain.

FF1.95V/-40C UP20ps loaded-event physical macro-reset native completed350ns with exit0; native2482711 terminated normally and `receiver_loaded_macro_reset_ff195_cold_up/assessment.json` records simulation_completedtrue. Separate corrected full-clock watcher launched by reaudit supervisor (watcher2529159/nativeauditor2529160 confirmed live), independent terminal collector remains waiting for completed watcher receipt. Native completion recorded; signed fresh/stale/opposite event behavior/control rejection/full-clock independent verification remain pending. No functional or release pass inferred from native exit.

FF1.95V/-40C UP20ps actual physical loaded-reset case now passes corrected full-clock terminal checks and independent verification:350ns native exit0, allfour watcher commands exit0,315PLL edges through348.988889ns independently derived,3602 evidence hashes verified. Frozen `receiver_loaded_reset_campaign_independent_terminals_001/450MHz_ff_1.95V_-40C_+250ps_20ps_independent.json`. Measured macro reset release251.532727079ns; consumedUP177.877778/297.877778/337.877778ns, fresh297.877778ns in first post-release storage interval, physically loaded pre-withdrawal, no stale/opposite events, direction-swap rejected. Full-clock450grid3/180passing, independent staged188-case collector3passing185pending. One deterministic fixedRC/ideal committed-control FFcold case; all remaining PVT/modes/resetgeneration/acquisition/MTBF/wholePLL/release gates retained.

Both SS1.62V/125C450MHz UP/DN250ps200psREF/DIVedge loaded-reset grid natives completed350ns/exit0 and passed corrected full-clock terminal checks, fresh/stale/opposite signed-event consumption, direction-swap rejection and independent verification. Frozen independent receipts `receiver_loaded_reset_campaign_independent_terminals_001/450MHz_ss_1.62V_125C_+250ps_200ps_independent.json` and `..._-250ps_200ps_independent.json`, each3649 evidence hashes and315PLLedges. UPfresh300.1ns/macrorelease253.445888187ns; DNfresh302.322222ns/macrorelease252.945868959ns; pre-withdrawalphysicalstoragehigh, no stale/opposite. Full450grid now5/180independently passing; staged188-case independent collector5pass/183pending. Original native workers advanced to FF1.62V/-40C DN20ps(native2530323) andDN200ps(2530537); actualKLUcmdline and exactprepareddeck identity independently verified in `receiver_loaded_reset_grid_next_workers_identity_audit_001.json` (7pins). RemainingPVT/modes/fullresetgeneration/acquisition/MTBF/fullPLL/release gates retained.

Reconciled primary seven-gate release checklist with terminal evidence: removed stale SS125DN-live wording after independently verified SS125UP/DN20/200ps and FFcoldUP20ps passes. The full450actual loaded-reset grid, all-five-mode behavior, acquisition/handoff/resetgeneration, statisticalMTBF and remaining full release gates remain explicitly incomplete. No gate dropped or marked complete; all900 prepared decks remain preparation rather than behavioral qualification. Native handles for nextFFDN20/200ps, lower100MHzUP/DN and allDCOvariants confirmed live and advancing.

Frozen130ns startup-only prefixes of both live100MHzSS1.62V/125C20ps UP/DN pilots using separate `snapshot_loaded_reset_prefix.py`; `.prefix.txt` files intentionally do not mimic completed native traces. READY2 first rise61.492075/61.492078ns and EVENT_RESET release41.677899/41.677901ns; physical BBPD_RESET_PHY remains belowhalfVDD through130ns, UP2/DN2notexercisedyet. Independent9-pin prefix evidence/byteidentity audit `receiver_loaded_reset_100MHz_startup_prefix_independent_audit_001.json`. These are diagnostic startup observations only; physical storage loaded before187.06nswithdrawal and terminal fresh/stale/opposite consumption/directioncontrol remain pending. Active natives and pinned qualification helpers untouched; no lower-mode or release pass claimed.

100MHzSS125UP/DN20ps pre-withdrawal snapshots prove fixed187.06nswithdrawal does not exercise loaded-event condition: firststorage stagehigh, finalUP2/DN2 belowhalfVDD and neverrose throughout0..187.055ns, COMMAND_RUNstillabovehalfVDD. Independently frozen9-pin byte-identity/condition audit `receiver_loaded_reset_100MHz_prewithdrawal_condition_audit_001.json`; physical startupmacrorelease132.813261959nsDN/133.313201141nsUP. Original pilots preserved and continue450ns; this is a fixture coverage problem for the loaded-event test, not a complete circuit functional/release verdict. Prepare separate100MHzwithdrawal207.05ns stimulus to permit two additional10nsPLLcycles before next210nsREFopportunity; loaded/fresh/stale/control and allPVT behavior still require independent native qualification.

Prepared separate100MHzaligned stimulus family `receiver_loaded_reset_100MHz_aligned_prepared_001` (180=45PVT x2phases x2REF/DIVedges), shifting onlyCOMMAND_RUNwithdrawal187.05..188.57ns to207.05..208.57ns, two10nsPLLperiods later and before210nsREF. Same450ns/5ps transient, circuit/RC/models/clocks/phase/edges; original900decks andactivepilots preserved. Independent exactCartesian/byte-delta/PVT/clock-duty audit `receiver_loaded_reset_100MHz_aligned_deck_audit_001.json` verifies4158 evidence pins; first audit rejected an incorrect parser source-line pattern, corrected before successful frozen receipt, decks unchanged. No analog launches or loaded behavioral passes. Compatible207ns mode-native/replay/consumption/control/independent terminal auditors and two correctedSS125pilots must validate the full loaded-event condition before broader100MHzqualification. Remaining release scope retained.

Added separate explicitly profiled withdrawal audit helpers (original187.05ns or100MHz207.05ns), preserving actual finalstoragehigh beforewithdrawal, exactlyone signed pre/fresh consumption, no stale/opposite, direction-swap rejection and fullclock/evidence verification. Newwatcher original450MHzSS125 regression passed allfour commands and independent3599pins/315edges; `receiver_loaded_macro_reset_ss125_aligned_independent_terminal_001.json`. Wrong-profile control rejects original187ns100MHzdeck labeled207ns; `receiver_loaded_reset_aligned_wrong_profile_control_001.json`. Launched separate corrected100MHzSS125UP/DN20ps450ns/5ps native pilots supervisor2535791/python2535817, two workers nativeDN2535919/UP2535920; verified actualKLUcmdline, copiedprepareddeck/manifest profileidentity in9-pin `receiver_loaded_reset_100MHz_aligned_pilots_initial_identity_audit_001.json`. Driver invokes full native/replay/consumption/direction-control plus independent terminal verifier, retaining allfailures. All original campaigns/pinned helpers remain running/immutable. Corrected physicallyloaded100MHz behavior andbroaderPVT/edges/modes/MTBF/acquisition/wholePLL/release qualification remain pending.

Prepared exact720remaining lower-mode input index `receiver_loaded_reset_remaining_modes_prepared_001/preparation.json`:180 revised100MHz207.05nswithdrawal decks plus540 original250/300/400MHz187.05nswithdrawal decks, each180=45PVT x2signedphases x2REF/DIVedges. References existing frozenprepareddecks and preserves original180450MHz native campaign. Independent auditor confirms exactmode/PVT/phase/edgeCartesian coverage, sourceidentity, PLLperiod/50percentduty,450ns/5psduration andexplicitwithdrawalprofiles,4885 evidence hashes: `receiver_loaded_reset_remaining_modes_deck_audit_001.json`. No broader720native launch orbehavioralqualification; corrected100MHz andotherlower-mode positive loaded/fresh/stale/control/independent pilotresults remain prerequisites. Livecorrected100MHz nativeDN2535919/UP2535920 advanced34.5/32.5ns, original100MHzstresspilots266.6/269.7ns andnewFFDNgrid84.0/79.4ns; allfullrelease/MTBF/acquisition/wholePLLrequirements retained.

Corrected 100MHz loaded-reset pilot precondition (2026-10-08): froze both SS1.62V/125C, signed250ps,20ps-edge native prefixes through207.055ns, before the207.06ns command withdrawal threshold. Independent audit `build/timing450/interface_characterization/receiver_loaded_reset_100MHz_aligned_prewithdrawal_condition_audit_001.json` verified nine pinned files and exact prefix identity against each growing native waveform. DN2 rose at191.403875735ns and UP2 at191.391709579ns; each correct final storage state remained above halfVDD at the prefix end, the opposite state stayed below halfVDD, and READY2/EVENT_RESET/macro reset release and COMMAND_RUN were high. This confirms that delaying withdrawal by20ns exercises the intended loaded-storage precondition in these two pilots. Original187.05ns100MHz runs and their unexercised precondition evidence remain preserved. Both corrected450ns native simulations and full reset/replay/consumption/direction-control/independent terminal checks remain pending. This bounded diagnostic does not qualify the full PVT grid, MTBF, acquisition, wholePLL, or the450MHz release.

Original100MHz terminal outcomes and250MHz pilot progression (2026-10-08): both original SS1.62V/125C signed250ps20ps cases completed450ns natively with exit0. Each terminal command sequence was[0,0,1]: native/replay passed, strict consumption failed because no signed prewithdrawal consumed event existed and final storage was unloaded before187.06ns. Each produced one fresh event in the designated interval with no stale or opposite-direction events. Retained failure classification audit `build/timing450/interface_characterization/receiver_loaded_reset_original_100MHz_terminal_failure_audit_001.json` verified32 native/terminal command-log/output-receipt/source-helper and prior diagnostic file pins; it is not a full PDK or positive qualification audit. This confirms the original fixture precondition issue rather than establishing a global hardware failure; no failed result was counted as passing or deleted. The existing runner advanced to250MHz signed-phase20ps pilots, nativePIDs2545960(DN) and2546119(UP). `receiver_loaded_reset_lower_mode_250MHz_initial_identity_audit_001.json` verified six deck/manifest pins, byte identity with prepared250MHz inputs, and actual liveXyce/KLU command identities. New250MHz behavior and corrected100MHz terminal behavior remain pending; all release flags remain false.

Both corrected 100 MHz SS1.62 V/125 C signed-phase 20 ps pilots completed their full 450 ns native runs with exit code 0. The frozen `build/timing450/interface_characterization/receiver_loaded_reset_100MHz_aligned_native_completion_observation_001.json` records manifest receipt identity, finite monotonic 23-column waveforms, full duration, and ten evidence hashes. Replay, event-consumption, direction-control and independent terminal verification remain pending; this observation does not qualify the pilots or the release.

Both corrected100MHz pilots now pass allfour terminal checks (native, fullclock replay, strict consumption, wrong-direction control). The DN independent terminal receipt verifies4020 evidence hashes and90 PLL transitions: loaded prewithdrawal DN consumed200.1ns; fresh DN consumed360.1ns; no stale or opposite events. UP independent terminal verification remains pending at this observation. These are two fixedRC/ideal-control SS1.62V/125C cases, not fullPVT, MTBF, acquisition, wholePLL or release qualification.

The UP independent receipt completed during the assessment update: both corrected100MHz signed-phase pilots now independently pass, each verifying4020 evidence hashes and90 PLL transitions. UP consumes the loaded event at200.1ns and the fresh event at360.1ns, with no stale or opposite events. The assessment now records both independent receipt hashes and clears the pilot terminal-validation pending flag. Broader lower-mode campaign still awaits the250/300/400MHz pilots; release qualification remains false.

The720-case lower-mode loaded-reset campaign is now launched with four workers. Launch validation rechecked the exact Cartesian720 grid, source/deck/withdrawal identities, and all eight independently passing pilot receipts and their frozen source hashes. Eight pilots are reused;712 new450ns cases are queued. The first four corrected100MHz FF1.62V/-40C signed-phase20/200ps workers have independently observed live command, manifest and exact prepared/native deck identities in `receiver_loaded_reset_remaining_modes_initial_identity_audit_001.json`. Each new case runs explicit-profile native/fullclock replay/strict-consumption/wrong-direction and independent terminal checks, retaining failures. Existing180450MHz work continues separately. FixedRC/ideal controls; no MTBF, full acquisition, wholePLL or release qualification.

Completed canonicalDCO waveform audits now cover25 baseline points (6816 evidence hashes),26 step points (6821),8 tighter-tolerance points (6731),4 longer-settling points (6711), and the completed600ns code57 probe (6696). All complete-wave/provenance audits pass; negative native width measurements remain retained and reconstructed widths are positive. The refreshed25-point baseline four-window diagnostic finds20 initial-to-final estimate differences above the calibration limit; code17 remains within its local limit. This does not establish cross-variant convergence, full35-point interpolation/calibration, fullPVT, physical jitter, acquisition or wholePLL/release qualification. Receipts are frozen under `build/timing450/interface_characterization/canonical_dco_*wave_audit*` and `canonical_dco_window_settling_002.json`.

The independent final50ns DCO variant convergence screen (`canonical_dco_variant_convergence_screen_001.json`) verifies all frozen variant evidence and matching circuit/PVT/solver settings, retains missing35-code coverage, and checks both cross-variant final frequencies and adjacent final-window drift against min(100ppm,0.25localLSB). Available complete codes8/9/16/17 pass step/tolerance/600ns-settling comparisons. Code57 final600ns frequency464882984.125Hz differs84257.882Hz from final300ns464798726.243Hz, above38552.787Hz limit; its300ns estimate is not converged. Codes120/121/136/137/152/153/168/169 fail final adjacent-window drift at300ns. Baseline and half-step final estimates agree closely; these observations point to insufficient settling duration rather than a half-step numerical discrepancy. All35-code convergence, interpolation/fullPVT and wholePLL release qualification remain false. Existing source-pinned native jobs and controller are unchanged.

Two source-matched longer-settling DCO probes (codes57/169, coarse0 SS1.62V/125C,1200ns end,600ns measurement start,5ps step, reltol1e-6/abstol1e-10) are now live. Their prelaunch validation verifies7019 frozen evidence/source hashes and the observed calibration-drift failures. Initial identity audit verifies same-code reference/new deck bytes apart from planned duration, resetpulse extension, measurement delay and169 tighter options, exact matching source manifests, canonical fingerprints and actual native KLU command lines. Provisional point provenance and growing waveforms are not pinned. Existing35-point sweeps and receiver campaigns continue; these two pending probes do not qualify calibration, fullPVT or the release.

The first four100MHz FF1.62V/-40C signed-phase20/200ps campaign workers have independently verified loaded prewithdrawal conditions in frozen207.055ns prefixes. Correct storage rises190.807..190.815ns and remains high; opposite storage never rises, READY2/reset-release signals are high and COMMAND_RUN remains above half supply before207.06ns. Independent byte equality against each growing native prefix, finite23-column/index/monotonic checks and17 frozen evidence hashes are recorded in `receiver_loaded_reset_100MHz_ff162_cold_prewithdrawal_condition_audit_001.json`. This bounded observation does not qualify native completion, fresh/stale consumption, fullPVT/MTBF/acquisition/wholePLL or release; all four450ns terminal validations remain pending.

Baseline canonicalDCO code184 completed300ns and passed full waveform/provenance audit, bringing baseline audited points to26 (`canonical_dco_terminal_wave_audit_004.json`,6821 evidence hashes). The original controller advanced to code185 with nativePID2947418. The independent code184 final50ns baseline/half-step diagnostic retains both final frequencies and adjacent-window drift; the exact localLSB threshold awaits185 baseline completion and no calibration qualification is inferred. The100ppm upper bound remains45000Hz, with any larger adjacent drift necessarily outside the full min(100ppm,0.25LSB) limit. Existing jobs/controllers and frozen sources remain unchanged.

2026-10-13: The loaded-reset 450 MHz FS/1.8 V/125 C UP/200 ps case completed 350 ns with native exit 0 and passed all four full-clock terminal checks. Its separate independent terminal receipt verified 3,649 evidence hashes and 315 PLL transitions through 348.988889 ns. Pre-withdrawal UP consumption at 177.877778 ns, fresh UP at 297.877778 ns and subsequent UP at 337.877778 ns were verified, with no stale or opposite events. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_campaign_independent_terminals_001/450MHz_fs_1.8V_125C_+250ps_200ps_independent.json`. This proves one deterministic fixed-RC case with ideal committed controls; MTBF, whole-PLL and release qualification remain incomplete. The full-clock 450 MHz campaign now has 64/180 terminal passes; the staged independent collector has 72 terminal results, 70 passes and two retained original 100 MHz fixture failures.

2026-10-13: The first new case in the 720-case remaining-mode campaign, 100 MHz FF/1.62 V/-40 C DN/200 ps with command withdrawal starting 207.05 ns, completed 450 ns and passed all four terminal checks plus separate independent verification. The receipt verified 5,120 evidence hashes and 90 PLL transitions through 445.1 ns. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_-40C_-250ps_200ps_independent.json`. The campaign now has nine verified passes including eight reused positive pilots. The native driver automatically advanced to a 27 C case. This is one deterministic loaded-reset case with fixed RC and ideal committed controls; full-PVT campaign coverage, MTBF and whole-PLL/release qualification remain incomplete.

2026-10-13: The second new remaining-mode case, 100 MHz FF/1.62 V/-40 C DN/20 ps, completed 450 ns and passed all four terminal checks and separate independent verification of 5,120 evidence hashes and 90 PLL transitions. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_-40C_-250ps_20ps_independent.json`. Both cold-corner DN edge cases are now independently verified. The campaign has 10/720 passes, including eight reused pilots, and automatically started the next 27 C DN/200 ps case. Fixed-RC/ideal-control limitations and outstanding MTBF, whole-PLL and release qualification remain.

2026-10-13: The 100 MHz FF/1.62 V/-40 C UP/200 ps case completed 450 ns and passed all four terminal checks and separate independent verification of 5,120 evidence hashes and 90 PLL transitions. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_-40C_+250ps_200ps_independent.json`. The remaining-mode campaign now has 11/720 independently verified passes. UP/20 ps has passed its four terminal checks but remains pending separate independent verification. Existing fixed-RC/ideal-control limitations and incomplete MTBF/whole-PLL/release qualification remain.

2026-10-13: The 100 MHz FF/1.62 V/-40 C UP/20 ps case passed all four terminal checks and independent verification of 5,120 evidence hashes and 90 PLL transitions through 445.1 ns. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_-40C_+250ps_20ps_independent.json`. All four new 100 MHz FF/1.62 V/-40 C direction/edge cases are now independently verified, giving 12/720 remaining-mode passes including eight reused positive pilots. This is four completed deterministic fixed-RC cases with ideal committed controls; full-PVT coverage, MTBF and whole-PLL/release qualification remain incomplete.

2026-10-13: DCO code 200 completed the canonical coarse0 SS/1.62 V/125 C 300 ns step-refinement run (5 ps print/max step). The frozen completed-waveform audit `build/timing450/interface_characterization/canonical_dco_step_terminal_wave_audit_002.json` now verifies 27 completed points, including code 200, with full finite monotonic waveforms, source/provenance hashes, complete-cycle positive widths and agreement with native frequency measurements. The original step controller automatically advanced to code 201. This establishes waveform/provenance integrity only; comparison against the matching baseline code 200 and tighter-tolerance/longer-duration runs, settling/calibration, full-PVT and whole-PLL/release qualification remain incomplete.

2026-10-13: DCO code 185 completed its 300 ns step-refinement run, and the original controller advanced to code 216. The frozen waveform audit `build/timing450/interface_characterization/canonical_dco_step_terminal_wave_audit_003.json` passed for 28 completed points and 6,831 evidence hashes, retaining prior receipts. This proves source/provenance and completed-waveform integrity; baseline code 185 remains running, and matching frequency-convergence, longer-duration, calibration/interpolation/full-PVT and whole-PLL/release qualification remain incomplete.

2026-10-13: The loaded-reset 450 MHz FS/1.95 V/-40 C DN/20 ps case completed 350 ns with native exit 0 and passed all four full-clock terminal checks plus separate independent verification of 3,649 evidence hashes and 315 PLL transitions through 348.988889 ns. Evidence: `build/timing450/interface_characterization/receiver_loaded_reset_campaign_independent_terminals_001/450MHz_fs_1.95V_-40C_-250ps_20ps_independent.json`. The full-clock campaign now has 65/180 passes; the staged independent collector has 73 terminal results with 71 passes and two retained original 100 MHz fixture failures. The native controller advanced to the corresponding UP/20 ps case. One deterministic fixed-RC case with ideal committed controls does not qualify MTBF, whole-PLL or the release.

At 2026-10-13T15:55:11.553190+00:00, the corrected 100 MHz FF/1.62 V/27 C DN/20 ps loaded-reset case completed its 450 ns native transient, all four terminal checks, and separate independent verification (5,120 evidence pins and all 90 PLL edges). Receipt: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_27C_-250ps_20ps_independent.json`, SHA-256 `0061d6498f9e58522758e86de7d29aecc38575cfba7553e036c5e4658cef9591`. Storage was physically loaded before withdrawal at 207.05 ns; consumption occurred at 200.1 ns before withdrawal and freshly at 360.1 ns, followed by 400.1/440.1 ns, with no stale or opposite-direction events. Root verification rechecked 4216 host-accessible receipt hashes; 904 container tool/PDK hashes had been checked by the independent verifier. This proves one deterministic fixed-RC case with ideal committed controls; MTBF, full acquisition, whole-PLL behavior, and release qualification remain incomplete. The lower-mode campaign now has 13/720 independently verified passes and automatically queued FF/1.62 V/125 C DN/20 ps.

At 2026-10-13T15:59:13.748599+00:00, the corrected 100 MHz FF/1.62 V/27 C DN/200 ps loaded-reset case completed its 450 ns native transient, all four terminal checks, and separate independent verification (5,120 evidence pins and all 90 PLL edges). Receipt: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_27C_-250ps_200ps_independent.json`, SHA-256 `749068071c6dc79f9e7c00da02f6f94872b7941e93ac1ab81ecc9e1ce002c254`. Storage was physically loaded before withdrawal at 207.05 ns; consumption occurred at 200.1 ns before withdrawal and freshly at 360.1 ns, followed by 400.1/440.1 ns, with no stale or opposite-direction events. Root verification rechecked 4216 host-accessible receipt hashes; 904 container tool/PDK hashes had been checked by the independent verifier. This proves one deterministic fixed-RC case with ideal committed controls; MTBF, full acquisition, whole-PLL behavior, and release qualification remain incomplete.

At 2026-10-13T16:02:30.261517+00:00, the corrected 100 MHz FF/1.62 V/27 C UP/20 ps loaded-reset case completed its 450 ns native transient, all four terminal checks, and separate independent verification (5,120 evidence pins and all 90 PLL edges). Receipt: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_27C_+250ps_20ps_independent.json`, SHA-256 `437da51ce1c3cd135c3d5634dc4eca50f4e900c0c95bdf3d4a21f58c1ac8b4d9`. Storage was physically loaded before withdrawal at 207.05 ns; consumption occurred at 200.1 ns before withdrawal and freshly at 360.1 ns, followed by 400.1/440.1 ns, with no stale or opposite-direction events. Root verification rechecked 4216 host-accessible receipt hashes; 904 container tool/PDK hashes had been checked by the independent verifier. This proves one deterministic fixed-RC case with ideal committed controls; MTBF, full acquisition, whole-PLL behavior, and release qualification remain incomplete.

At 2026-10-13T16:03:47.319358+00:00, the corrected 100 MHz FF/1.62 V/27 C UP/200 ps loaded-reset case completed its 450 ns native transient, all four terminal checks, and separate independent verification (5,120 evidence pins and all 90 PLL edges). Receipt: `build/timing450/interface_characterization/receiver_loaded_reset_remaining_modes_native_001/100MHz_ff_1.62V_27C_+250ps_200ps_independent.json`, SHA-256 `986f474acd286434cea0f0f8118655e24a9d412d5cc9d58b11db6ecdd9960900`. Storage was physically loaded before withdrawal at 207.05 ns; consumption occurred at 200.1 ns before withdrawal and freshly at 360.1 ns, followed by 400.1/440.1 ns, with no stale or opposite-direction events. Root verification rechecked 4216 host-accessible receipt hashes; 904 container tool/PDK hashes had been checked by the independent verifier. This proves one deterministic fixed-RC case with ideal committed controls; MTBF, full acquisition, whole-PLL behavior, and release qualification remain incomplete.

At 2026-10-15T07:07:08.763024+00:00, refreshed independent terminal waveform audits of completed canonical extracted-DCO runs: baseline 30/35 (6841 evidence pins), step 35/35 (6866 evidence pins), tolerance 10/35 (6741 evidence pins), settling 4/35 (6711 evidence pins). All four waveform audits passed their completed-trace, provenance, finite/monotonic time, pulse/cycle and native measurement consistency checks. Receipts: `build/timing450/interface_characterization/canonical_dco_terminal_wave_audit_005.json`, `build/timing450/interface_characterization/canonical_dco_step_terminal_wave_audit_004.json`, `build/timing450/interface_characterization/canonical_dco_tolerance_terminal_wave_audit_002.json`, `build/timing450/interface_characterization/canonical_dco_settling_terminal_wave_audit_002.json`. The smaller-timestep campaign now covers all 35 codes; waveform integrity does not establish settled frequency or cross-variant convergence. Baseline code 216 is complete but adjacent code 217 remains live, so the existing adjacency-dependent convergence screen is not promoted. Full PVT/interpolation/acquisition/noise and release qualification remain incomplete.

Release verification strategy review: `build/timing450/interface_characterization/release_verification_strategy_review_001.json` distinguishes required five-mode/45-PVT behavior from the implementation-selected 900-case native reset matrix. The approximately four-week reset-sweep estimate is not a prescribed release duration. Priorities are DCO convergence, qualified digital timing, conservative interface models with independent extracted-case correlation and digital proofs, whole-PLL acquisition/performance, then physical signoff/adoption. No remaining case has been waived: replacement coverage is unproven, live immutable campaigns and receipts are preserved, and all original release requirements remain in force.

Refreshed DCO convergence screen: `build/timing450/interface_characterization/canonical_dco_variant_convergence_screen_002.json` uses separately versioned `verification/timing450/audit_dco_variant_convergence_v2.py`, preserving the original helper and frozen evidence. Available counts are baseline30, smaller-step35, tolerance10 and settling4, plus the single code57 longer-settling probe. Only codes8/9/16/17 have all required variants and pass. Observed failures are [57, 120, 121, 136, 137, 152, 153, 168, 169, 184, 185, 200, 201, 216]. Codes184/185/200/201/216 show baseline final-window drift85.5/85.8/93.3/96.2/104.6kHz, while smaller-step final means differ by only130/310/258/359/346Hz. Thus timestep agreement does not resolve settling. Code216 lacks adjacent baseline217: its local calibration limit remains unknown, but104.6kHz exceeds the absolute45kHz cap and conclusively fails. Validation `build/timing450/interface_characterization/canonical_dco_variant_convergence_v2_validation_001.json` proves exact preservation of prior results, omission of an otherwise passing code8 neighbor cannot produce a pass, and absolute-cap exceedance still fails. No physical cause or global convergence is established; all release gates remain incomplete.

DCO settling investigation: `build/timing450/interface_characterization/canonical_dco_rail_resistance_diagnostic_001.json` checks the immutable unreduced/reduced extracted resistor networks using `verification/timing450/audit_dco_rail_resistance.py`. All7,265 VPWR-named and5,947 VGND-named transistor terminals are resistively reachable from the corresponding external rail in both networks. Maximum shortest-path bounds agree (VPWR1305.8287ohm, VGND6203.848ohm). The reduced graph contains2,695 individual resistors above1Mohm, including4.86e84ohm, but their presence alone does not imply isolated terminals: alternate paths remain. These are path upper bounds, not effective resistance or IR-drop estimates. No dynamic rail voltage, body-node relaxation or physical settling cause is established; no extraction, PDK, live deck or pinned helper was modified. This narrows the investigation while preserving all release requirements.

Bounded DCO settling diagnostic: `build/timing450/interface_characterization/canonical_dco_390ns_prefix_independent_diagnostic_001.json` independently verifies exact390ns raw prefixes from the live1200ns code57/169 probes and Decimal half-supply window-frequency agreement within0.01Hz. Final290..340 versus340..390ns changes are16,375Hz(code57) and57,032Hz(code169). Code169 still exceeds the absolute45kHz calibration cap. Code57's390ns final-window estimate differs from its completed600ns final-window reference by51497.171Hz, exceeding45kHz despite a quieter adjacent pair; a single locally quiet pair must not terminate convergence checking. A requested unavailable2000ns prefix is rejected before any receipt directory is created. Frozen prefixes and static inputs are hashed; growing waveforms are explicitly unpinned. This is diagnostic evidence only, not terminal or physical-cause qualification. No new analog simulations were launched.

Launched one focused internal-voltage diagnostic, code169 SS1.62V/125C300ns5ps at the existing smaller-step baseline tolerances, in `build/modern_25mhz/canonical_hot_ss_450_internal_voltage_probe_001`. The sole deck change is additional .print observations: four named supply locations, eight internal transistor nodes and externalVPWR/VGND. Circuit, extractedRC, stimuli, solver settings, duration and source/PDK remain unchanged. Xyce topology check passed; controller independently verified6,696 input hashes before launch. Initial identity audit `build/timing450/interface_characterization/canonical_dco_internal_voltage_probe_initial_identity_audit_001.json` pins preparation/deck/topology-log/launch/controller and verifies actual nativeKLU PID3119678. This single hypothesis-driven diagnostic will compare voltage evolution against output drift; it does not qualify the cause, calibration, PVT or release. Existing runs and frozen receipts are preserved.

Reset evidence coverage/envelope report `build/timing450/interface_characterization/loaded_reset_coverage_envelopes_003/assessment.json` aggregates138 independently passing cases against frozen discovery snapshots and verifies receipt hashes, positive loaded/fresh/no-stale/no-opposite predicates, and exact900-case Cartesian identities. Coverage is100MHz52cases/12fully covered PVT points;250/300/400MHz2cases each/0fully covered PVT points;450MHz80cases/20fully covered PVT points. Two legacy450SS full-clock regression passes are counted but have no timing-envelope fields; these missing metrics are not invented. Observed event-reset assertion delays span0.443..1.139ns, macro assertion after event0.622..1.499ns, macro-reset holds62.886..83.758ns. Different cases set these extrema; finite-sample extrema do not prove conservative bounds or dominate unmeasured conditions. Independent negative control `build/timing450/interface_characterization/loaded_reset_coverage_hash_control_001/control_result.json` rejects a receipt hash mismatch before creating a qualifying assessment. Nested evidence was checked by the prior independent verifiers and is not reverified by this aggregation. No missing case is waived; model-based replacement coverage remains unproven. Failed aggregation attempts001/002 are retained with snapshots only and no assessment.

Receiver RTL guard proof: `build/timing450/interface_characterization/receiver_guard_rtl_proof_001/assessment.json` proves seven candidate-source logical state invariants with Yosys sequential SAT and temporal induction (step2), and rejects a negative control removing the consumer guard. CandidateRTL is byte-identical apart from inserted assertions; design/PDK/live inputs remain unchanged. The proof checks clearing of five state fields after inactive/unready capture, and holding of UP/DN consumed state when no new event exists under the specified ready/seen conditions. It uses initialRESET_N=0 and async2sync/common-step clock abstraction, so it does not establish arbitrary clock-phase timing, analog recovery/removal, metastability, storage delay bounds, exactly-one fresh-event refinement, or whole-PLL/release qualification. This separates a proven digital invariant from the analog assumptions still needed for model-based replacement of native cases. Existing918 equivalence comparisons remain a separate claim.

Receiver event-consumption proof preparation: `build/timing450/interface_characterization/receiver_event_consumption_rtl_proof_003` extends the candidateRTL guard properties with eligible-event acknowledgment, nonduplication while each synchronized toggle is stable and reception remains armed, and history-monitor strengthening (13assertions total). Disabled-UP-acknowledgment negative control is rejected. Exact assertion fan-in is retained while unused output port flags/output-only logic are pruned. Initial progress `build/timing450/interface_characterization/receiver_event_consumption_rtl_proof_003/initial_proof_progress.json` records finite base cases and live solver identity; positive induction is pending and no new unbounded safety/refinement claim is made. Earlier attempts001/002 are retained as incomplete, superseded solver formulations; only those new solvers were stopped. Existing native campaigns and the completed seven-invariant guard proof remain unchanged.

Receiver event-consumption proof completed: `build/timing450/interface_characterization/receiver_event_consumption_rtl_proof_003/assessment.json` records successful unbounded temporal induction at step52 for all13assertions, with disabled-UP-acknowledgment negative control rejected. The seven prior guard properties are extended by two acknowledgment, two stable-toggle nonduplication and two monitor-strengthening assertions on actual candidateRTL. Only unused output port flags/output-only logic were pruned; all assertion fan-in and original design semantics relevant to these properties remain. This supersedes the pending observation. Initial reset and common-step async2sync limits remain: no arbitrary phase/analog timing/metastability/physical-event refinement or release qualification is established, and no native cases are waived.

Independent-clock receiver check: `build/timing450/interface_characterization/receiver_event_multiclock_proof_001/assessment.json` passes all13 receiver properties through40 global transition steps with Yosysclk2fflogic preserving independent primary/derived clock transitions. Disabled-UP-acknowledgment control fails and retains a concreteVCD counterexample. The history-validity monitor is asynchronously reset to avoid incorrectly comparing across an intervening reset pulse; candidate designRTL remains unchanged. This is bounded safety, not40PLLOUTcycles or unbounded multiclock induction. Analog delay/aperture/metastability, fullPLL and release qualification remain incomplete; no native cases are waived.

Unbounded independent-clock receiver safety: `build/timing450/interface_characterization/receiver_event_multiclock_pdr_001/assessment.json` proves all13 receiver assertions with ABCPDR/IC3 on actual candidateRTL using Yosysclk2fflogic and AIGER export, preserving independent ideal digital clock transitions. FaultyUP acknowledgment disproves3properties (10stillprove), and a minimal initial-reset polarity control proves!RESET_N and disprovesRESET_N under the initial-reset assumption. DefaultABCfold is the verified constraint translation; complementedfold is rejected because it incorrectly makes the faulty design pass. Uninitialized FFs retain arbitrary initial states throughwrite_aiger-zinit extra inputs. This removes the bounded-depth/common-step limitation for these logical invariants while retaining analog setup/hold, reset recovery/removal, storage delay, metastability/MTBF, aperture and wholePLL gaps. No physical reset cases are waived and release qualification remains false.

Receiver proof/candidate provenance audit: `build/timing450/interface_characterization/receiver_proof_candidate_provenance_link_001.json` verifies byte identity of DigitalCore/MMD_Retimer/DLF/B2TH/Divider proof sources with the frozen synthesis snapshot, exact candidate numeric parameter matches and defaultDLF_UPDATE_ON_PLLOUT=0/registered decision=1, mapped source attributes naming that snapshot, and all pins of the existing918 mapped-to-routed ideal-functional comparisons (916direct plus two jointly proven state instances). This is a provenance/parameter and existing-evidence revalidation, not a new end-to-endRTL-to-gate equivalence proof. No physical timing, analog/storage/reset delay, metastability/MTBF or release claim is inferred.

Timing coverage requirement review: `build/timing450/interface_characterization/release_timing_corner_requirement_review_001.json` distinguishes required45-point operating coverage from exact45 library filenames. Qualified conservative corner envelopes are a possible verification method, but are not established here. SourceJSON comparison `build/timing450/interface_characterization/hs_ss100_ss150_used_cell_table_ordering_002.json` compares183 used cell types over common slew/load domains with bilinear interpolation/union knots and no extrapolation;5,764 tables have different grids. Many SS150 values are smaller thanSS100, including992 constraint entries, so hotter-is-worse cannot be assumed. Three large rise-delay counterexamples were independently checked by edge-of-grid linear interpolation (largest difference about-0.221ns). clkinv8 template-size changes are explicitly left unpaired; physicaldiode/fill/tap timingJSON gaps remain listed. Interpolation controls pass analytic linear/bilinear,25-point resampling, and no-extrapolation checks. The implementation remaining gate wording now allows validated enclosure methods while retaining all45 operating points and all physical timing requirements. No view is adopted and no timing point is qualified by this review.

Measured analog reset/rearm contract: `build/timing450/interface_characterization/receiver_reset_rearm_margins_001.json` revalidates independent terminal/native-audit receipt hashes and verifies136 positive cases. UPQ/DNQ/UP1/DN1/UP2/DN2 all clear before tracking/READY2 rearming and remain low until the first post-macro-releaseREF. Minimum observed clear-to-rearm margin is4.512810065856ns at450MHzFS/1.95V/125C DN/200ps; this mixed corner, rather than a presumedSS extreme, is the limiting measured case. Two legacySS450MHz regression receipts lack directly referenced native timing audits and remain explicitly unavailable to this margin calculation; their prior functional passes are preserved. Timeline validation `build/timing450/interface_characterization/receiver_reset_state_timeline_validation_001.json` checks crossing boundaries, constant levels and rejection of missing-state evidence. Half-supply crossing contracts are measured fixedRC/ideal-control cases, not conservative bounds over unmeasuredPVT/phase/RC, metastability or full analog-to-formal refinement. No native case is waived and release remains unqualified.

Internal DCO startup evidence: `build/timing450/interface_characterization/dco_internal_voltage_20ns_prefix_001/assessment.json` freezes the observation-only probe through20ns and computes time-weighted means over six complete output cycles. Two internal nodes shift about-99.2mV and another+37.0mV, while the four measured rail-node cycle-mean changes are at most about3microvolt. Connectivity trace `build/timing450/interface_characterization/dco_internal_disabled_branch_trace_001.json` maps them to branches nominally disabled by fixed-lowDCO_THERM32/130 (inverted gate drive for railPMOS) andDCO_THERM21 (direct gate drive for railNMOS). Static CMOS topology infers nominal off state; internal gate voltage/conductance is not measured. Independent validation `build/timing450/interface_characterization/dco_internal_20ns_prefix_independent_validation_001.json` verifies exact original/frozen raw-prefix identity and90 cycle means by cumulative time integration. This supports internal disabled-branch charge relaxation as an early-startup hypothesis, not a proven cause of late100..300ns frequency drift or a physical defect/fix. The unchanged single native voltage probe remains live; no additional sweep was launched.

Direct routed receiver safety: `build/timing450/interface_characterization/receiver_routed_multiclock_pdr_001/assessment.json` proves12 observable state/acknowledgment/nonduplication properties by unboundedABC PDR on instrumented iteration026route.v, using actual routed combinational/FF/reset/clock logic with idealHS Liberty functions and independentclk2fflogic clock edges. The RTL update-edge state is optimized away in the selected clock mode and its property is not counted. Filler/tap instances are verified to have zero signal ports before using empty functional models; diodeinput-only models remain passive. The actualUP-consumed FF D-pin stuck-high fault produces a counterexample at frame8. A separate self-hold acknowledgment fault search remains unclassified here. This establishes direct routed logical safety in addition to the RTL/provenance/equivalence results, while cell/route timing, analog/reset/storage delay, recovery/removal, metastability and physical-event refinement remain unqualified. No physical case is waived and release flags remain false.

The separate routedUP-FF self-hold acknowledgment-fault PDR search reached its configured300second limit with12undecided properties (none proved/disproved): `build/timing450/interface_characterization/receiver_routed_multiclock_pdr_001/negative_ack_search_result.json`. It is retained as inconclusive, not counted as a rejected fault or a design pass. The successful12-property original routed safety proof and separately rejectedD-stuck-high clearing fault remain distinct evidence.


2026-10-16: User established a 12-hour wall-clock budget per individual check, not a one-night deadline for the entire release. Policy `build/timing450/interface_characterization/release_check_budget_policy_001.json` preserves all mandatory requirements: timeout is inconclusive execution failure, never verification success or proof of a circuit defect. New non-native checks use a 12h timeout; native Xyce invocations are covered by a detached workspace-scoped watchdog with process-start/pidfd identity protection, at most 5s polling and 30s termination cleanup. No automatic identical retry. Frozen runners, decks and evidence remain unchanged. A corrected integration control verifies actual container checks are excluded from a temporary test workspace, stale process identity rejects signalling, the owned test process times out, and unrelated processes survive.

The initial watchdog test had a bind-alias isolation error and interrupted production simulations. Incident `build/timing450/interface_characterization/native_check_budget_test_incident_001.json` lists affected reset/DCO cases and distinguishes infrastructure interruptions from circuit failures. Partial files are preserved; no affected case is counted as qualified. The corrected guard checks the actual bind-mounted directory through /proc/PID/root instead of trusting alias text. Existing campaigns may advance to different cases; no automatic rerun of interrupted cases is launched here. Six pre-existing DCO processes had already exceeded 12 hours, including the two approximately 74-hour settling probes. No multi-day check remains running. Full mandatory release gates remain open.

Corrected interruption inventory `build/timing450/interface_characterization/native_check_budget_test_incident_002.json` supersedes001: 18 reset cases and 16 DCO cases were interrupted. Still-running newly started DCO cases are excluded; reset receipt paths resolve through the actual workspace bind. Runtime policy002 references this corrected inventory. The interruptions remain infrastructure failures; original receipts are retained unchanged.


2026-10-16: User narrowed release qualification to nominal1.80V only. Active criteria are now `verification/release_requirements.json`, preserving all prior functional, timing, acquisition, calibration, temperature/process, physical characterization and artifact requirements while replacing the supply set with [1.8]. Required coverage is15PVT points and75mode/PVT combinations. Each check retains its12h wall-clock budget; timeout does not qualify a requirement. `verification/engineering.json` is retained byte-for-byte as the historical input pinned by live/frozen campaigns; new release work must explicitly use the active requirements file. Existing off-nominal evidence is diagnostic history and is outside the mandatory matrix. This scope change does not establish a passing nominal-voltage candidate. README and the primary assessment reference the active criteria.


2026-10-17 scheduling correction: retired six legacy analog-queue controllers and their11 native children before any further off-nominal launch (`scheduling_scope_cancellation_001.json`); retired the two read-only legacy collectors separately. Artifacts and original status remain historical. The new immutable `run_nominal_release_reset_checks.py` explicitly loads active nominal-only requirements, rejects both off-nominal supplies, retains independently verified nominal receipts and selects at most12 missing-mode checks at250/300/400MHz (SS125/20ps andFS125/200ps, both signed phases) before broader expansion. It uses four workers and a12h deadline for each native-plus-terminal-audit chain; termination controls verify entire process-group cleanup and timeout124. Native launch follows input/hash validation; status is owned by `nominal_release_reset_native_001`, not legacy statuses. The300-case nominal matrix remains a strategy, not a prescribed release count.

DCO duration review `dco_300ns_duration_review_001.json`: the prior300ns total is configurable100ns settling plus200ns measurement, not a specification threshold. The completed observation-only SS1.62V diagnostic still changes76,166Hz between200..250ns and250..300ns (above the45kHz absolute cap for450MHz calibration). This historical off-nominal example does not set nominal duration or establish a nominal design defect. Shortened nominal calibration must establish settled values and timestep/tolerance/duration agreement within min(100ppm target,0.25localLSB), including correlation against longer hold-out evidence; a short locally quiet window alone is insufficient. No shortened duration is qualified by this review. The wholePLL200us acquisition/four5120ns sustained-window requirements remain unchanged.

Nominal scheduler validation passed with66 reused independent nominal passes; selected12 missing-mode cases. Execution plan exactly matches validated input pins and case list. `nominal_release_reset_initial_identity_audit_001.json` verifies four live native commands, nominal1.8V deck/manifest identity, intended250/300/400MHz modes and no remaining legacy native-queue controllers. Future current-state reports should read `active_nominal_reset_scheduler` and its new status; legacy campaign snapshots are historical. No new native completion or release pass is claimed.


2026-10-18 nominal reset batch completed: all12 new250/300/400MHz SS/FS nominal1.8V cases pass native simulation, terminal audits and separate independent verification. No failures/timeouts in this batch;78 nominal passes including66 reused. Completion review `nominal_release_reset_batch_completion_001.json` checks all12 frozen receipt hashes, pass/supply metadata and per-case runtime (maximum3.665h). Batch ended03:28UTC; no native simulations remain running. Remaining222 prepared cases are deferred strategy coverage, not a prescribed release count. DCO convergence, qualified timing, wholePLL acquisition/performance, analog/CDC refinement and physical signoff remain open; no release/adoption claim.


2026-10-18: User approved the minimum six-gate release strategy. Active machine-readable plan `verification/release_plan.json` preserves nominal1.8V,450MHz/five modes,15PVT,75wholePLL cases and all existing numerical performance thresholds. It replaces blanket test-method requirements with qualified evidence: no remaining Cartesian reset sweep, all-fine-code sweep or fixed300ns duration is intrinsically required; any interpolation/enclosure or shortened duration must still establish its error and coverage. STA/proofs plus targeted timing-aware checks must collectively cover physical timing; unsupported blanketSDF replay cannot silently waive uncovered checks. Existing78nominal reset passes and unbounded13RTL/12routed logical properties remain scoped evidence. Physical signoff remains incomplete.

Nominal DCO path: discovery found no completed nominal exact-candidate calibration in the existing canonical/layout-family runs; older presets use other geometry. New `run_nominal_dco_release_path.py` is launched atTT1.8V/27C with six80ns endpoint measurements (coarse0/1/16,fine8/247), four native workers and12h per-native cap. Only a measured band bracketing450MHz enables a three-adjacent-code local baseline/timestep/tolerance/160ns-duration comparison. Search seeds and local convergence are not full-band calibration models. No automatic identical retry or all-PVT expansion on failure. Controls reject extrapolation, missing endpoints/reversed bands and long-duration disagreement.

WholePLL preparation: `release_functional_matrix_001/assessment.json` records the75required nominal cases and compiles a new boundary harness from the actual frozen candidate RTL snapshot. Reset/disable smoke passes. The root RTL differs in five modules, including the pipelinedMMD configuration, so the old mixed-signal wrapper is rejected as candidate qualification evidence. All75qualification cases remain explicitly blocked pending converged DCO, analog-correlated receiver/BBPD/reset models and a validated phase-continuous closed-loop driver. No fictional lock or acquisition results were generated.

Nominal timing characterization completed120/120 native5ns cases: extracted/LVS-checkedHS buf8 and nand2_2 A->output,15PVT,20/200ps input ramps and5/50fF loads. Independent validation checks361artifact hashes and240Decimal delay calculations (maximum numerical difference5.7e-16ns). The slowest sampled NAND input-rise propagation isFS125/200ps/50fF at0.229426ns, versusSS1250.219185ns. This confirms mixed corners require evidence rather than presumedSS dominance. No full-cell/constraint/RC/operating-domain coverage is claimed.

Candidate timing-envelope test `nominal_hs_sampled_delay_envelope_001.json` uses no-extrapolation bilinear sourceLUTs: fastFF-40/1.95V versus entrywise maxSS100/SS1501.6V. It fails20/240sample comparisons (largest above-slow30.46ps; below-fast13.36ps); this candidate envelope is rejected, not adopted. Source common/corner threshold and unit controls verify50% delay and20..80% slew, so linear input ramps convert by0.6. SourceJSON-to-installedLiberty equivalence, all-cell/arcs, setup/hold/recovery/removal and metalRC bounds remain open. These are model-bound failures, not failed native functional tests or a final circuit verdict.

Initial live DCO identity audit verifies fourTT1.8V/27C native decks against recorded fingerprints and nominal requirements, with two endpoint cases still queued; growing outputs remain unpinned. Remaining DCO stages execute only after their measured dependency passes. No off-nominal native work or new reset matrix was launched.


2026-10-19: All sixTT1.8V/27C80ns endpoint screens completed without native failures/timeouts. Full20..80ns window means: coarse0[807.911,1012.468]MHz, coarse1[539.669,592.768]MHz, coarse16[86.791,88.091]MHz at fine8/247. None brackets450MHz, so the dependency correctly did not launch local convergence or extrapolate a model. This is an incomplete coarse search, not an exclusion proof. Root rechecked all six frozen waveform hashes. New separately pinned `run_nominal_dco_coarse2_release_path.py` changes only the screened coarse list to[2]; the prior helper/artifacts are preserved. Two nominal80ns endpoints are launched under the same12h per-native cap, and local convergence remains conditional on a measured bracket.


2026-10-19 coarse2 screening completed2/2native cases without failures/timeouts. TT1.8V/27C fine8/247 means are363.8265/387.7502MHz; prior coarse1 endpoints are539.6686/592.7685MHz. No450MHz bracket was found. The151.9184MHz separation between these measured endpoint ranges flags a potential nominal tuning-coverage gap; this is not an all-fine/all-coarse reachability proof. Both frozen waveform hashes were rechecked. Local convergence did not launch, no native simulations remain running, and no model is qualified. Next work must inspect coarse/fine mapping/attainable range before spending further time on settling or calibration; blind additional coarse sweeps are not scheduled.

2026-10-19: Implemented the approved coarse-1 fine-controlled load-bank repair
as three isolated `OSC8_LOAD36_C1FINE144/160/192` candidates. Each extra
`sky130_fd_sc_hd__einvp_1` has A=`mirror_turn_n[1]`,
TE=`DCO_THERM[floor(255*j/N)]`, and its own unused Z output. The original RTL,
all 531 original cells, 255 independent fine controls, 47 coarse controls,
36 fixed loads, oscillator/turn boosts and external ports are preserved.
New OpenLane configurations inherit the baseline floorplan and flow.

Actual Yosys-elaborated connectivity comparisons passed for all three banks.
Eleven tests passed, including corrupted original-driver, wrong turn/control,
aliased dummy, missing/extra cell, margin/order, missing-bracket, reversed-range
and native-nonpass controls. Input/output/log hashes and results are recorded
in `build/timing450/dco_c1_fine_load_001/initial_validation.json`.

The pinned controller `verification/timing450/run_dco_c1_fine_load.py` is
routing all three candidates and will extract all-net R/C with the existing
Magic helper and resistor-only Schur reduction. Routing before selection is
an implementation refinement to include routing effects directly in the
screens. It then measures TT1.8V27C, coarse1, fine8/128/247, 80ns with a
20..80ns measurement window, 10ps print/max timestep, reltol1e-5 and abstol1e-9.
A viable screen must have f8<=390MHz, f247>=460MHz and strictly increasing
sampled fine frequency. These margins select experiments, not new release
criteria or calibrated models. Full late-window measurements and native
artifacts are retained. Each tool/native stage is bounded by12h, and no
identical run is retried automatically.

A separately pinned dependent controller,
`verification/timing450/screen_dco_c1_fine_load_pvt.py`, waits for the TT
decision, tries viable banks from smallest upward and checks measured target
brackets for all five modes at15 nominal-voltage PVT points. TT27 is checked
first to reject another missing nominal mode before launching the remaining
points. Coarse monotonicity is a search heuristic only; a pass requires actual
measured ordered endpoints around each target. A missing bracket rejects the
candidate for this conservative screen without claiming global unreachability.
No calibration or extrapolated model is adopted. If all75 brackets pass,
measured fine-code search, adjacent-code numerical/settling qualification and
affected physical/interface qualification remain necessary. If no candidate
passes, the experiment stops without promotion. Existing pinned scripts,
PDK, prior decks, receipts and release requirements were not modified.

All three new layouts completed routing with zero route/Magic/KLayout DRC,
LVS and antenna errors. Independent metrics review is retained in
`build/timing450/dco_c1_fine_load_001/routed_physical_review.json`.
The144/160/192 variants have148/164/196 reported slew violations respectively
and4 capacitance violations each; the baseline reported0/0. These new
loaded-node electrical warnings are unresolved and block physical
qualification. Range simulations remain diagnostic; there is no electrical
waiver. A viable tuning candidate will need electrical qualification or a
separately versioned drive-strength repair before adoption.

All three all-net extractions and resistor-only reductions completed. Final
extracted-net counts are2622/2686/2814 for144/160/192 loads respectively
(total-net counts2624/2688/2816; the two common power/body nets account for
the difference, as in the baseline). The144-load TT screen has launched
three actual Xyce processes for fine8/128/247. Initial deck/provenance identity
and native PIDs are recorded in
`build/timing450/dco_c1_fine_load_001/initial_native_identity.json`.
The160/192 screens follow automatically; PVT remains dependent on measured
TT viability. No terminal range, calibration or release pass is claimed.

2026-10-19: User selected400MHz for the first release and approved implementation.
The active scope is100/250/300/400MHz,25MHz reference, nominal1.8V,
five process corners and three temperatures:60mode/PVT cases. Versioned
`verification/release_requirements_400mhz.json` and
`verification/release_plan_400mhz.json` retain all other acceptance criteria.
`verification/active_release.json`, README and the primary implementation
assessment now identify this scope. Original450MHz requirements, plan,
source, native artifacts and their33 controller input pins are preserved.
New unqualified divider presets are4/10/12/16; calibrated coarse/fine settings
remain unset. No hardware port or frozen digital RTL was changed.

Retired only the verified waiting450MHz PVT scheduler using a pidfd after
checking its exact script, experiment, workspace bind and process start ticks.
Its exit is recorded in `build/timing400/release_001/retired_450_scheduler.json`.
The three in-flight192-load native simulations continue; their results are
retained. The existing12h native watchdog remains active and covers new jobs.

The new400MHz DCO controller first tries160loads, then144. It independently
remeasured six completed TT traces and verified their inherited provenance;
6,727 input hashes are pinned. TT400MHz measured endpoint brackets are reused.
The next range checks are300/250/100MHz atTT27; missing brackets stop that
candidate before broader PVT. On a completeTT pass, the controller checks all
15PVT points, prioritizingSS125, FF-40 andFS125, at most twoPVT points at a time.
Every mode pass requires actual measured ordered endpoints, not an extrapolated
model or a claim of global monotonicity. A full60-bracket pass gates measured
fine-code search and adjacent-code baseline/half-step/tighter-tolerance/160ns
comparisons, with the existing min(100ppm target,quarter localLSB) error limit.
Local results alone cannot qualify interpolation/model coverage or a release.

One engine owns one native check and a12h wall-clock deadline. Pending engines
reserve slots during preparation, and surviving external workspace Xyce jobs
count against the shared four-worker maximum. There is no automatic identical
retry. Initial live audit confirmed three retained192-load native jobs plus
one new160-load coarse3 endpoint check, with the second endpoint waiting for
a slot. The400MHz queue has its own exclusive controller lock. Current progress
is `build/timing400/release_001/dco/status.json`.

Fifteen controls passed: stale450MHz modes/presets, wrong dividers/count/supply,
missing PVT/mode coverage, native/nonmonotonic/missing-bracket failures, slot
accounting including pending preparation and external jobs,400MHz40kHz
calibration cap, tighter-tolerance/long-duration/drift failures, and missing
adjacent codes. A new HDL test against the exact frozen physical candidate
passed reset/disable boundaries and measured twelve output periods each for
actual candidate divider configurations4/10/12/16. The60-case functional
manifest includes all12directed supported-mode changes perPVT but remains
blocked on qualified DCO/dynamic interface models and a validated continuous-
phase driver. No acquisition/lock or release qualification is claimed.
Initial evidence is `build/timing400/release_001/initial_validation.json`.
Applicable electrical warnings, nominal15PVT timing, model lookup coverage,
wholePLL behavior, physical signoff/characterization and final adoption remain
mandatory. A measured range or convergence failure stops expansion and retains
its evidence; changing the top frequency does not waive other release gates.

400MHz timing preparation advanced while the bounded DCO range check continued.
The exact routed digital candidate contains20,093 instances,189 cell types,
181 timing cell types and1,475 source timing-arc identities. The receiver-reset
model corpus covered168 of these timing cell types, leaving13 actual routed
models missing. A separate extraction generated the13 missing cellRC views
without changing the PDK or old models. All13 passed complete-net extraction
and transistor topology/width/length LVS; a doubled-width negative control
was rejected. New artifacts:
`build/timing400/release_001/hs_missing_cell_rc_001/assessment.json`.

An independent combined audit regenerated all181 transistor-only LVS projections,
compared them byte-for-byte with the native LVS inputs, verified complete-net
statistics/native JSON comparisons/input hashes, and checked both old/new
wrong-width controls. The complete181-type model index is
`build/timing400/release_001/hs_cell_model_index_001/assessment.json`.
This closes the missing cellRC model prerequisite for the present digital
route. These are nominal cellRC models at0.01fF extraction threshold; they do
not qualify timing, junction area/perimeter, RC variation, interfaces or release.

The earlier source-corner delay envelope omitted available cold-SS and hot-FF
views. A separately versioned audit forms mathematical union-grid min/max
interpolants over threeFF and threeSS temperature views, without extrapolation,
and reuses the independently validated240 native delay samples. Violations
fall from20 to1. The remaining NAND2 A->Y rising-output case atFS1.8V125C,
200ps full input ramp and5fF load measures36.548185ps, below the proposed fast
bound37.820479ps by1.272294ps. Thus even the expanded source-corner envelope
is rejected and is not adopted; no fitted guard or assumption thatFF/SS
necessarily bound mixed corners is introduced. Three interpolation/domain
negative controls passed. The report is
`build/timing400/release_001/hs_timing_coverage_001.json` and completion receipt
is `build/timing400/release_001/timing_preparation_completion_001.json`.
Nominal-PVT delay/slew and sequential-constraint coverage remain open.
No additional Xyce simulation was launched by this preparation; the three
retained192-load jobs and one new160-load range check still occupy four slots.

400MHz wholePLL preparation: implemented a separate Icarus VPI phase-clock
component under`verification/timing400/`. Coarse/fine frequency changes preserve
accumulated phase. Integer millihertz frequencies integrated over1ps ticks keep
an exact sub-tick phase residual between events, avoiding rounded-halfperiod
accumulation. The machine lookup table is exact and discrete; missing lookups,
X/Z controls, invalid/duplicate points, unsupported widths or time precision
stop simulation with a nonzero exit. Reset holds PLLOUT high, matching the
NAND-gated DCO. No measured frequency table was generated, interpolated or adopted.

Sixteen component checks passed in
`build/timing400/release_001/phase_bridge_validation_003/assessment.json`.
A separate Fraction oracle matches40,728 edge times across fixed frequency,
mid-halfcycle fine/coarse changes, simultaneous control changes, edge-coincident
and one-tick-before/after changes, reset/restart, and a200us fractional-period
run. The rounded-halfperiod negative control accumulates over1ns of error and
is rejected. Eight negative controls verify missing-code rejection, X/Z values,
duplicate/invalid/incomplete models, time precision and argument widths.
The actual frozen candidate RTL also passes reset/disabled bridge integration
with an explicit asynchronous reset assertion and a synthetic model grid.

The first diagnostic run contained an invalid timescale in a negative fixture;
the second exposed declaration-initialization dependence in the stopped-clock
integration bench. Both are retained. The final bench delivers a real reset
assertion before clock startup, rather than masking unknown DCO controls or
changing frozen RTL. The driver continues to reject unknown controls.
An independent Decimal auditor verifies40,836 phase-conserving transitions
including the frozen-RTL bridge trace, exact lookups, trace and source hashes,
and all eight negative exits:
`build/timing400/release_001/phase_bridge_independent_001.json`.
Completion receipt:`build/timing400/release_001/phase_bridge_completion_001.json`.

All phase-driver fixtures are explicitly synthetic. This is a validated
scheduler component, not a physical DCO or interface model. Ideal50percent duty,
reset/startup timing, tuning/settling response, analog interface behavior,
physical noise/jitter and supply effects remain unqualified. All60wholePLL
qualification cases remain blocked; this work contributes zero passing release
cases. No extra Xyce job or existing pinned helper/model was changed.

400MHz functional acceptance preparation found two reproducible false positives
in the frozen historical checker: periodic traces with fine7 or248 pass despite
the required8..247 operating range, and a divided-clock channel truncated100ns
before the observation end can pass because the old helper shifts its end to
the earliest last edge. The frozen helper and its pinned runs are unchanged.
New `verification/timing400/functional_acceptance.py` requires the explicit
observation stop and actual reference guard edges, uses the exact final5120ns
windows at that stop, and checks complete tuning changes plus clock samples
against inclusive fine8..247. Invalid excursions between sampled clock edges
cannot disappear from the operating-code check. Truncated tails, missing guard
or tuning data, noninteger/nonfinite/nonmonotonic data and missing reference
interior edges cannot qualify. Existing frequency, phase span/mean/drift,
cycle-slip and conservative acquisition-confirmation criteria are retained.

Sixteen unit controls pass, including all four modes, valid8/247 boundaries,
invalid7/248, short between-edge tuning excursions, clock truncation, missing
reference/control traces, signed phase bias, span/drift, exact-period cycle
slips, frequency error, acquisition deadline and insufficient final windows.
Three end-to-end CSV/CLI controls verify a synthetic functional pass and
nonzero exits for invalidfine7 and a truncated divided-clock tail. Evidence:
`build/timing400/release_001/functional_checker_validation_001/assessment.json`
and `functional_acceptance_tests_001.log`. Every report explicitly leaves
wholePLL/release qualification false. Terminal capture identities, independently
qualified physical models, a validated closed-loop driver and the remaining
release gates are still required; these synthetic checks add zero passing
wholePLL qualification cases. No extra Xyce job was launched.

400MHz compact-mapping feasibility uses the exact frozen candidate RTL and
external interfaces. `verification/timing400/check_compact_mapping.py` compares
a full-library control (72 synthesized types,4838 cells) with a restricted
functional set (12 synthesized types,6057 cells). SAT proves every external
output and all863 paired state primitives' data, clock and asynchronous control
functions for arbitrary paired binary state. A deliberately inverted data
function is rejected. This proves the two mappings' transition/output relation;
it is not a new RTL-to-layout or analog timing qualification.

Evidence:`build/timing400/release_001/compact_mapping_004/assessment.json`.
The supplied-TT ideal-clock/unrouted PLLOUT setup margin is1.496436ns versus
1.526313ns for the control. Recovery still fails in both:−0.787731ns compact
and−0.785825ns control on a heavily loaded reset-source path. Cross-domain
paths are excluded in this capacity diagnostic. No all-path timing pass is
claimed. The12 types are synthesized types, not a replacement count for the
original181 routed timing types; later buffering/CTS can expand the inventory.

An isolated restricted-master placement trial is started in
`build/timing400/release_001/compact_placement_001` by
`verification/timing400/check_compact_placement.py`. It validates the mapping
receipt and all pinned inputs, constrains resizer cells to the explicit allowed
set, uses estimated placement parasitics, and inventories every output master.
The diagnostic exceptions remain explicit. No old physical artifact or live
DCO controller is changed, and no compact mapping is selected. DCO checks
continue within the shared four-native-check and12h per-check limits.

The compact placement trial completed successfully with6147 instances and
24 functional types, all within the allowed set. Diagnostic TT estimated
setup/recovery slacks are1.427875/1.409743ns; minimum reported hold/removal
slacks are0.066528/0.254519ns. The previously failing reset recovery improves
after fanout buffering/upsizing. Reported slew, capacitance and pulse-width
screens are positive in this supplied-TT estimated context. Evidence:
`build/timing400/release_001/compact_placement_001/assessment.json`.

Only ideal-clock placement estimates are complete. Postplacement logical
equivalence, actual CTS/routing, qualified nominal15PVT views and interface
bounds remain open; no new release gate is marked complete. Placement input
and artifact identities were rechecked after completion. This trial introduces
zero additional native Xyce checks; existing queued DCO range work continues.

Compact placement logical qualification initially fails: the OpenROAD
pre-tie Verilog export has undriven `one_`/`zero_` nets. A SAT counterexample
identifies five captured D inputs with a required constant1 but unconstrained
physical nets. The timing diagnostic did not establish connectivity and is
not adopted. Exact source/physical state correspondence also requires an
explicit, collision-checked alias for the writer's literal leading backslash.
Drive-strength FF substitutions are accepted only after imported functional
model structure comparison, including clock/reset/data connections.

`verification/timing400/complete_compact_ties.py` connects actual conb_1
HI/LO drivers and repairs their fanout in a new isolated database.
`build/timing400/release_001/compact_tied_placement_001/assessment.json`
records completed constant connectivity and the restricted inventory.
`check_compact_physical_equivalence.py` now checks this actual tied netlist;
no logical constants are supplied as assumptions to hide undriven nets.
The failed attempt is retained in `compact_placement_equivalence_003`.

The tied-placement transition/output SAT proof passes for all863 matched
state primitives and every external output. A deliberately inverted captured
reset function fails the same proof, demonstrating asynchronous controls
remain observable. Imported dfrtp_1/2/4 functional models match structurally
before accepting drive-strength substitutions. Evidence:
`build/timing400/release_001/compact_tied_equivalence_001/assessment.json`.
The untied mismatch is retained as additional negative evidence.

`check_compact_clock_tree.py` starts an isolated restricted CTS estimate in
`compact_cts_001` only after validating the tied-placement identity and passing
equivalence/negative-control receipts. It includes REFCLK, PLLOUT, the exact
generated-clock driver and both BBPD event-clock nets; propagated clocks and
placement-estimated parasitics replace the previous ideal clock estimates.
The diagnostic cross-domain exceptions remain explicit and do not qualify CDC
or interface timing. New CTS must still pass post-CTS equivalence, routed
checks and full qualified nominal15PVT coverage before any adoption.

Compact CTS completes with34 functional-library types including tie cells.
Diagnostic supplied-TT estimated setup/recovery margins are1.421077/1.394269ns;
minimum reported hold/removal margins are0.050559/0.256245ns. Slew, capacitance
and pulse-width screens are positive in this bounded context. Post-CTS
transition/output equivalence passes for all863 paired state primitives and
external outputs, including the reset-function negative control. Receipts:
`compact_cts_001/assessment.json` and `compact_cts_equivalence_001/assessment.json`
under `build/timing400/release_001`.

`verification/timing400/route_compact_candidate.py` now creates isolated tap,
filler and PG-connected PDN infrastructure, routes signals and extracts nominal
signal RC in `compact_route_001`. It requires the matching CTS equivalence
receipt and tracks all inputs. The physical-only master whitelist is separate
from the restricted functional set. The route is not selected; router results,
routed equivalence, independent physical signoff, min/maxRC and qualified
nominal15PVT timing must be assessed before it can replace any candidate.

Compact CTS completion receipt:`compact_cts_completion_001.json` under the
400MHz release build. Output identities for tie connection, post-tie proof,
CTS and post-CTS proof were rechecked. The detailed router is confirmed live
by PID, start ticks and command, not merely by a status file.
`check_compact_layout.py` is prepared for the completed route and has not yet
been executed. It adapts only build-root/fresh-output handling in a retained
copy of the existing audit, with the original sources unchanged and an outer
12h budget including preparation plus process-group cleanup on timeout.
The full release remains unqualified; no candidate is selected.

Compact route_001 completes with router DRC0, Magic DRC0 and90500/90500
PG pins connected. The restricted functional inventory remains34 types
including conb ties. Audited removal of PG-only tap/decap/fill cells and unused
logical VDD/VSS ports permits the routed transition/output SAT proof to pass
for all863 state primitives and external outputs, with a reset negative
control. Evidence:`compact_route_equivalence_003/assessment.json`. Initial
attempts retained strict missing-module/port checks and are preserved; no
functional cell or signal port is silently removed. Physical ports/connectivity
remain subject to actual powered-GDS LVS.

Four-mode supplied-TT25 timing across nominal/min/maxRC reports positive
400MHz setup at worst0.668689ns but reference-domain input hold fails at
−0.098769ns. Maximum-RC electrical violations include3.82ns slew against1ns
and0.51pF against0.15pF. These invalid domains prevent timing qualification
even where numeric setup slack is positive. Independent layout audit finds
17 antenna nets/21 pins and a top-level LVS pin error: TRACKING and
BBPD_RESET_N share one output net, so routing/export loses a distinct physical
port. Their logical alias is preserved in the SAT relation; separate physical
output drivers are needed before LVS can pass. No waiver is granted.

`compact_parasitic_audit_001/assessment.json` independently resolves all184
unannotated drivers to actual OpenDB output pins with zero sinks and zero
external ports. The required RESET_N endpoints are resistively connected in
all3SPEF sets. An RCX loop warning is retained: connectivity alone does not
qualify loop-reduction fidelity, min/maxRC accuracy or reset timing bounds.
All route/timing/layout receipts remain unqualified. Next work is isolated
output separation plus electrical/hold repair, then antenna closure and fresh
equivalence/timing/layout checks. All old artifacts and active DCO jobs remain
unchanged. The legacy192 screen completed356.904–410.862MHz at TT, which
brackets400 but is not selected or calibrated; the active160/144 ordering is
unchanged pending its other-mode range evidence.

`verification/timing400/repair_compact_route.py` starts fresh
`compact_route_repair_001` from the immutable first route. It uses the
existing audited output-export separation, extracted maximum-RC loading for
initial electrical repair, then global-route estimates for new topology,
restricted masters, setup repair and0.15ns diagnostic hold margin. This does
not relax acceptance or qualify supplied model extrapolation. A jumper-only
antenna repair is attempted before detailed routing; any remaining antenna
violation must still be fixed. No diode master is silently added to the
restricted inventory. Old route/failed signoff receipts are preserved.

This turn completes actual routed proof,12 supplied-TT mode/RC screens, an
independent Magic/Netgen/antenna/PG audit, and an OpenDB/SPEF annotation audit;
its classification is progress. None of these grants release qualification.
The first route fails hold/electrical/antenna/pin-export checks, and its repair
requires fresh checks against the changed layout. Native DCO160 coarse3
endpoint simulations continue; all legacy192 checks are now terminal.

The first compact repair completes router DRC0, independent Magic DRC0 and
unique powered-GDS LVS matching, with89476/89476PG pins connected. Output
separation clears the original top-level pin mismatch. Routed binary
transition/output equivalence passes with all863 matched state primitives
and a rejected reset negative control. The strict first checker expected
logical VDD/VSS ports; this export omits unused PG ports, so the new
`check_compact_routed_equivalence_v2.py` accepts only an optional subset of
VDD/VSS while retaining every functional port and rejecting connected PG
projection. The old checker and its pinned receipts are unchanged. Evidence:
`compact_repaired_equivalence_002/assessment.json`.

Twelve four-mode/RC supplied-TT25 screens pass their reported setup/hold
checks, with minimum hold0.052466ns and worst400MHz setup0.713772ns. These
do not qualify timing: electrical domains still fail at1.83ns slew versus1ns
and0.49pF versus0.27pF, and the independent antenna audit reports5nets/5pins.
All46 functional-library types including ties remain in the allowed set;
45timing types have existing extracted cell RC models, but no complete
nominal15PVT timing views are qualified. The original181-type index remains
reusable, with its actual model scope unchanged.

The retained electrical diagnosis002 reports that the worst0.49pF net has
0.05pF pin capacitance and0.44pF wire capacitance, with only8loads spread over
the core. Additional gate upsizing alone is insufficient. The resizer logs
also show its initial use of wire-load estimates despite loading SPEF;
read_spef did not establish an extracted-repair estimator. Extracted timing
after each route remains the check, and no old estimate is promoted.

`repair_compact_route_clustered.py` and `cluster_electrical_nets.tcl` now
create a new isolated repair in `compact_route_clustered_001`:53actual failing
nets receive strong local root buffers and211spatially grouped branches
(max8sinks per50um bin chunk), with clock sinks handled by allowed clock
buffers. Every original sink and output port is retained. Buffer removal is
skipped during setup optimization to preserve that intended implementation.
These placement choices are engineering heuristics, not new timing/model
bounds. The resulting route must pass fresh logic equivalence, actual
extracted electrical/hold/setup and independent physical checks; remaining
antenna violations are not waived. Both active DCO endpoint processes are
preserved, and no additional native analog job is launched.

The first spatial-buffer route completes router/Magic DRC0, unique layout
LVS and routed transition/output equivalence. Its12supplied-TT mode/RC screens
have minimum hold0.053318ns and worst400MHz setup0.739156ns. Electrical
failures improve to1.23ns versus1ns slew and worst capacitance excess0.02pF
(0.29versus0.27pF). Antenna is still open at11nets/12pins, with87860/87860PG
pins connected. Evidence:compact_clustered_{equivalence,timing}_001 and
compact_route_clustered_001/signoff receipts. No physical or timing adoption.

A separate repair-target diagnostic tightens only max capacitance/transition
limits by20percent, preserving all delay/load/function data and the original
PDK/library. This implementation margin selects both residual and near-limit
nets; it is not a new qualified view or relaxed acceptance.
`compact_clustered_guard_diagnosis_001/assessment.json` records exact changes.
`repair_compact_route_clustered_v2.py` provides a fresh instance prefix and
starts `compact_route_clustered_margin_001`; all prior pinned scripts/data are
unchanged. The result must be checked using the original limits, not the
artificial repair targets. Antenna remains mandatory regardless of buffering.

`characterize_compact_propagation.py` launches one native Xyce batch at
FS/125C/1.8V in `compact_propagation_fs125_001`. It covers891independent
fixtures for all40combinational types in the assessed mapping:99sensitizing
input/side-state conditions times3full-ramp slews times3external loads.
Three slew values correspond to12/120/1000ps20–80percent transitions; loads
are0,one-quarter and the supplied-TT declared maximum capacitance for each
output. All154binary truth-table rows are independently checked against
explicit standard-gate Boolean definitions before preparing native circuits.
Extracted model port sets and model hashes are verified, and native PDK
provenance is pinned.

Admission is a single native launch only, requiring two free slots, no DCO
worker waiting/preparing, and live native children for every reported running
DCO engine. The existing controller sees the batch as an external native
process once launched; actual native count is3(twoDCO plusonebatch), within4.
No identical retry or per-fixture worker fanout occurs. The check has a12h
budget including preparation before native execution. Terminal waveform
coverage and measured delays still need assessment. Five sequential types,
other14PVT points, output-slew characterization, numerical error, interpolation
bounds, cell/routed RC and physical interface qualification remain open.
This raw batch is not a timing library and does not pass any release gate.

Margin-buffer route diagnostics retain positive setup/hold but fail electrical
limits(1.19ns versus1ns slew, worst capacitance excess0.03pF) and11antenna
nets/14pins. Independent LVS fails despite Magic DRC0 and a passing binary
transition relation. Investigation identifies a Verilog namespace collision:
internal DLF_CODE[3]/[5]/[7] nets retain the public port identifiers after those
ports move to buffer outputs. write_verilog aliases the distinct OpenDB nets;
the physical GDS actually has three additional nets compared with that bad
reference. Ideal-buffer Boolean equivalence cannot establish electrical net
isolation, so it cannot replace this independent topology check.

`repair_compact_export_names.py` renames those3internal nets in a fresh
`compact_export_names_003` database. An exact DEF comparison proves only
NETS identifiers change; matching PINS names, all components, coordinates,
routes, PG and connectivity remain byte-identical. Two retained attempts
failed the DEF guard's bracket/section handling after successful native
renames; the corrected guard is checked against their saved native output
before the completed run. No physical rerouting is used to hide the mismatch.
Fresh unique LVS matching and Magic DRC0 pass, with85264PG pins connected,
and routed transition/output proof passes. All12mode/RC timing results match
the source exactly. Antenna and electrical failures persist and remain open.

An exact-revision OpenRCX source audit is retained in
`openrcx_loop_source_audit_001/assessment.json`. At the logged loop warning,
addRSeg returns before creating the segment when both cap-node IDs match;
some callers subsequently reset the accumulated R/C. This does not establish
a conservative bound for the affected RESET_N geometry. Connected SPEF
endpoints alone cannot qualify it; no extractor or PDK is patched or waived.

`upsize_electrical_drivers.tcl` and `isolate_external_reset.tcl` drive a fresh
`compact_route_drive_reset_001` via `repair_compact_route_drive_reset.py`.
Actual extracted failing nets select9drivers for stronger allowed masters.
Sixexternal-reset receivers get short private buf_4-driven connections to
remove the problematic shared terminal attachment. This changes physical
reset delay and requires fresh reset/interface bounds. Buffer removal and
size-down are skipped during setup optimization. All original state and
interfaces are retained, subject to fresh routed proof and independent layout
checks; current template results do not grant qualification.

The891-fixture native propagation batch remains live alongside both DCO
endpoints, for3native simulations total. An immutable initial-row snapshot
checks all891native DC input/output states against their expected logic
orientation before any timing assessment. This is an early fixture consistency
check, not a terminal transient pass or a timing-library qualification.
No native simulation or pinned helper is restarted or modified.

The first private-reset route removes the nominal/min/maxRC loop warning,
passes routed Boolean equivalence and sampled setup/hold, but independent
PG audit aborts: six protected reset leaves have24unassigned power pins.
This is an implementation mistake, not a waiver. `global_connect` skips
protected instances. The fresh `repair_compact_route_drive_reset_v2.py`
validates/reuses the six reset leaves, temporarily clears their protection
for PG connection, restores it and asserts all PG pins are connected before
routing. Extracted near-limit diagnostics select53additional driver upsizes;
6targets are already at the strongest allowed master.

`compact_route_drive_guard_001` completes router DRC0, independent Magic
DRC0, unique powered-GDS LVS and84512/84512PG pins connected. All12four-mode
nominal/min/maxRC supplied-TT25 screens have positive/nonnegative reported
setup/hold/electrical/pulse checks, with worst400MHz setup0.789491ns and
minimum hold0.053730ns. No RCX loop warning remains in any of the3extractions.
Routed transition/output equivalence passes with its reset negative control.
Antenna remains14nets/15pins; full nominal15PVT timing and requalified reset
interface bounds remain open, and no candidate is selected.

`prepare_compact_sequential_propagation.py` prepares108fixtures for all6
currently needed dfrtp/dfstp strengths1/2/4 atFS/125C/1.8V. It checks source
clocked-on/data/clear/preset definitions, exact extracted-model port sets,
hashes, monotone PWL stimulus times,3slews and3loads. Fixtures separate
clock-toggle and asynchronous-assertion propagation with reset assertions
away from clock transitions. No native job is started. These do not cover
setup/hold, recovery/removal, minimum pulse or a qualified library.

The existing `check_diode_qualification.py` rechecks retained geometry, raw
DC/AC/charge/noise comparisons,15PVT coverage and all source/tool/artifact
identities into `diode_reuse_qualification_001.json`. Its fixed-geometry
electrical-model equivalence screen passes; it is explicitly not PLL release
qualification. This evidence can support antenna-diode integration without
repeating native measurements, subject to actual layout and loading checks.
All3active native simulations remain unchanged and advancing, with the
independent12h watchdog confirmed live and reporting3checks/0pending kills.


Antenna repair now uses an explicit conditional input-capacitance view from
`prepare_antenna_diode_load.py`: 0.00326159068053 pF per diode, derived from
the revalidated electrical model and nominal extracted cell capacitances.
This is a screening bound under its stated assumptions, not a qualified full
load/noise envelope. `compact_route_antenna_001` inserts 68 diodes and passes
fresh powered-GDS LVS, Magic DRC0 and 84688/84688 PG connections. Diode-aware
Boolean proof passes; passive load effects are separately excluded from that
proof. Fresh antenna audit leaves three nets/three pins. Loaded TT25 timing
retains positive setup/hold but fails slew/capacitance on an a21oi_1 driving a
clkinv_16. No release or timing qualification is granted.

`repair_compact_antennas_v2.py` addresses the measured local met1 side-area
violations at three dfstp_1 D inputs by selecting dfstp_4, and strengthens the
identified a21oi_1 driver to a21oi_4. It reroutes into a separate build root,
retaining explicit diode loads and requiring fresh logic/timing/layout checks.
`check_compact_routed_timing_with_diodes_v2.py` now records every reported
constraint violation and an explicit per-screen pass flag, so positive path
slacks cannot hide electrical failures. Historical receipts stay immutable.

The prepared sequential propagation runner is queued behind a terminal passing
891-fixture combinational assessment and conservative shared native capacity.
Its total 12-hour budget includes queue time; it makes one native attempt and
never retries automatically. Current prepared coverage remains clock-to-Q and
asynchronous assertion only, excluding setup/hold/recovery/removal and MTBF.


The v2 size-only antenna trial is cancelled and retained as unqualified.
A direct LEF comparison establishes that dfstp_1 and dfstp_4 both have
D ANTENNAGATEAREA 0.126, so the proposed input-area increase was incorrect.
`repair_compact_antennas_v3.py` instead inserts three buf_8 leaves adjacent
to the measured D sinks, creating short private D connections, and retains
the actual a21oi_4 electrical repair. Fresh geometry and loaded timing must
validate this implementation heuristic; output-strength sizing alone is not
antenna evidence. The original native characterization jobs remain untouched.


The FS/125C/1.8V combinational native batch completes with all891fixtures
passing terminal finite/event/rail/delay checks across40cell types. The result
is retained in `compact_propagation_fs125_001/assessment.json`; no simulation
retry was used. This is raw propagation coverage at one PVT, not qualified
numerical/interpolation/output-slew or nominal15PVT timing coverage. The queued
108-fixture sequential runner can proceed after verifying this receipt and
shared native capacity.


`measure_compact_output_slew.py` reads the completed891-fixture waveform
without launching native jobs. It checks terminal/header/index/finite/time
integrity, all provenance hashes, input ramp correspondence and20/50/80%
threshold counts/order.888/891fixtures pass strict slew extraction. Cases
774/837/873 (fast unloaded xnor2_4, xor2_2, xor2_4) have extra20% or80%
crossings while preserving two50% crossings per direction. Raw crossing
diagnostics are retained; no filtering, waiver or rerun is applied. Thus the
891/891propagation result remains narrower than output-slew qualification.
The108-fixture sequential native batch starts at17:19:39UTC withPID3825787;
total workspace native concurrency remains3 and the12h watchdog remains live.

The buffer-leaf route `compact_route_antenna_003` completes router DRC0,
independent Magic DRC0, unique powered-GDS LVS,84884/84884PG connections
and routed transition/output equivalence. Its145diodes use the conditional
input load view. The original three D-pin antenna failures are gone, but
fresh audit finds three different nets: DLF_CODE[6], thermal_code[244] and
electrical_margin_root_59_out. Loaded twelve-mode/RC screens retain minimum
400MHz setup0.747136ns and hold0.053594ns but fail preset-distribution slew
and place165 output capacitance (1.04pF versus0.88pF). Further broad diode
accumulation is not justified by these results. Target the remaining antenna
components and loaded preset distribution before adoption. Full15PVT timing,
reset/interface bounds and whole-PLL gates remain open. No candidate selected.
Completion evidence is `compact_antenna_checks_completion_001.json`; allthree
native simulations and the independent12h watchdog remain live.

The next repair switches from another full global reroute to the installed
OpenROAD revision's supported detailed-route antenna repair. Source audit
`postroute_antenna_source_audit_001` pins revision
`dcf36133a369abc8f3c5e5738cd4d82e4903c0e0`: detailed-route repair uses one
iteration, fixes unrelated instances during diode legalization, and updates
dirty route guides. The measured preset driver place165 is clkbuf_8; its
allowed clkbuf_16 replacement addresses the actual slew/load failure.

`repair_compact_postroute.py` and v2 retain two DRT-1231 failures at
`electrical_margin_branch_319/X`. The driver's placement changes, while its
input wire is present in the pre-DRT checkpoint even after v2 explicitly
removed it. Source inspection of `WireBuilder.cc` and `RepairAntennas.cpp`
clarifies that mixed detailed/global antenna checking creates temporary guide
wires for unrouted nets, and preserves them in detailed-route mode. Therefore
wire presence alone did not prove the old detailed wire survived. The v3
repair clears both incident preset wires after antenna checking as well as
before guide updates, then starts DRT. It preserves other routed geometry
and requires new loaded STA, logic equivalence and independent layout checks.
This is an implementation correction, with no PDK/extractor patch or waiver.

`compact_postroute_003` completes router DRC0, independent Magic DRC0,
unique powered-GDS LVS,84904/84904PG connections and antenna0nets/0pins.
Its routed transition/output proof passes. The preset slew/load failure is
resolved; loaded TT25 min/maxRC still expose two decoder nets: thermal184
has o21ai_1 drive/slew trouble, and thermal192 exceeds o21ai_4 maxcap slightly.
Parasitic audit finds184unannotated outputs, all with no sinks or ports;
RESET_N's seven endpoints remain resistively connected in all3RC extractions.
No nominal15PVT timing qualification is claimed.

`repair_compact_electrical_incremental.py` reads the actual twelve-screen
violation lists, groups their nets, and upsizes an allowed smaller driver or
isolates a strongest complex gate with buf_16. It preserves original public
net names and other placements, invalidates every signal wire incident to a
changed/moved cell, and reroutes without adding diodes or checking mixed-route
antenna geometry. Its copied introductory antenna-iteration sentence describes
the parent helper; this electrical pass does not call repair_antennas. The
actual emitted Tcl and added_antenna_diodes field define the operation. Fresh
layout, equivalence, loaded timing and final antenna checks remain required.

All-violator timing reports now use `-violators -no_line_splits -digits 6`.
The old display reported the worst row per check type, which was sufficient
for a zero-violation screen but incomplete for repair diagnosis. On the
incremental candidate the complete30violating pins group onto2nets.
Subsequent allowed resizes clear those failures; tiny new coupled-load
failures motivate implementation headroom instead of successive near-limit
repairs. The private selection library scales only maximum transition and
capacitance limits by0.9. Final checks always read the original supplied TT
library and the same explicit conditional diode load view. No release limits,
arc delays or PDK files are modified.

`compact_incremental_headroom_001` completes router DRC0, independent Magic
DRC0, unique powered-GDS LVS, antenna0nets/0pins and84904/84904connected PG
pins. Routed transition/output equivalence and reset negative control pass.
All12four-mode×nom/min/maxRC supplied-TT25 screens pass original setup/hold/
slew/capacitance/pulse limits with every electrical violator requested.
Minimum400MHz setup is0.747114ns; minimum sampled hold is0.022908ns.
The159diodes retain the conditional0.00326159068053pF screening load.
No RESET_N RCX loop warning remains in any of3extractions. Parasitic audit
resolves184unannotated outputs, all without sinks or ports, and checks all
seven RESET_N endpoints connected in all3RC. All46timing cell types match
extracted-model hashes and the40-combinational/six-sequential fixture plans.
These diagnostics do not qualify nominal15PVT timing, full load/noise bounds,
reset/interface behavior or the wholePLL. No candidate is adopted.
Completion evidence: `compact_incremental_closure_completion_001.json`.

The first new DCO endpoint completes at305.73016156378543MHz for the300MHz
band,160extra loads/TT27C/1.8V/coarse3/fine247. Its80ns waveform has17measured
periods and0.04829583113382796MHz half-window difference; this is a raw range
sample, not numerical calibration qualification. Its paired fine8 endpoint
continues, so this band is not yet proven bracketed. The previously measured
400MHz TT bracket remains separate.

The three ambiguous zero-load XOR/XNOR fixtures receive one new native
refinement: maximum step2ps→1ps, tolerances tighter by10. Allthree complete
terminal finite/event/rail checks; maximum observed50%delay change is
0.0012778950030933878ps. Their extra20/80%crossings persist with identical
counts. No filtering or waiver turns them into monotone output-slew passes;
this limited refinement does not enclose the full numerical/model domain.
The remaining DCO endpoint and108-fixture sequential batch continue under
the existing12h limits and shared native capacity.

The sequential native batch completes108/108fixtures atFS125C/1.8V.
A verified terminal provenance audit preserves its original receipt and raw
waveform, checks every input/raw artifact hash, and replaces only the known
mutable-status reference with a frozen terminal snapshot. Preferred evidence
is `compact_sequential_propagation_fs125_001/audited_completion_001/assessment.json`.
This adds clock-to-Q/assertion/output-slew observations for all6used FFtypes;
setup/hold/recovery/removal, numerical-domain and nominal15PVT qualification
remain open. No native rerun was used to repair the manifest.

Completed DCO profiling finds34791successful steps,145failed steps,0nonlinear
convergence failures and70526linear solves. Linear solution costs7764.54s
of13236.2s elapsed, about58.7%. The installed Xyce reports Amesos2KLU2 and
Basker enabled. `benchmark_dco_linear_solver.py` starts isolated10ns prefix
benchmarks with those backends, preserving circuit/initialization/tolerances/
step limit, and comparing raw waveform/edge results with the completed80ns
KLU reference. The out-of-window .meas directives are removed. These are
performance/fidelity probes, not full80ns or release/model qualification;
no backend is adopted. Each total12h budget includes admission wait, and
existing DCO native work is preserved. Source/profile evidence is retained
in `dco_solver_profile_001`; current native concurrency is3.

The existing KLU DCO process has21threads with no OMP/OPENBLAS/MKL thread
variables explicitly set; both alternative-backend probes have2threads.
A KLU10ns control with the same single-thread BLAS environment as the
alternatives is prepared and queued, so any observed speedup is not falsely
attributed to backend choice alone. It uses the v2 benchmark helper, which
allows KLU explicitly. Original native work is not restarted or altered.
No short benchmark proves the full80ns or complete numerical/model domain.

The completed fine8/coarse3 TT27C/1.8V endpoint is290.6820184467989MHz,
with17measured periods and0.0026680341671294627MHz half-window difference.
Together with305.73016156378543MHz atfine247 it brackets300MHz. The live
controller has advanced to the coarse4 TT250MHz endpoint pair; its pinned
inputs and existing native work are preserved. Range coverage is separate
from calibration accuracy, and TT100MHz plus remainingPVT coverage are open.

`audit_dco_settling_windows.py` audits seven completed waves across allfive
predeclared20/30/40/50/60ns measurement starts, each ending80ns. Its35
independent40-digit Decimal edge/frequency/drift calculations agree with the
canonical estimator. Near400MHz, the20..80ns baseline atfine128/fine247 has
half-window drift exceeding the40kHz100ppm cap. The60..80ns high-code samples
still exceed40kHz. All windows and raw observations remain in
`dco_window_sensitivity_001/assessment.json`; no favorable measurement window
is adopted. LocalLSB/4, duration/step/tolerance comparisons and validated
model-domain coverage remain required. No fixed300ns duration is imposed.

The10ns KLU single-BLAS control completes in1050.0166s andKLU2 in1069.0896s.
Both retain the original circuit, initialization, tolerances and step limit;
the prefix includes5ns reset and only5ns free oscillation. KLU's printed edge
times match the reference prefix; KLU2's largest observed paired shift is
0.000846647ps. Neither demonstrates a useful speedup. BASKER is intentionally
stopped after2302.46s, still inDCOP with no transient waveform, exceeding twice
the completed KLU control runtime. Its performance-stop receipt rejects this
short-run performance candidate; it is not a global backend/hardware failure
or a12h timeout. No alternative solver/thread policy is adopted.

`reduce_dco_resistors_exact.py` checks case-insensitive SPICE node identity,
protects all device/capacitor/port connections and replays exact resistor KCL
identities with wrong-R/missing-C negative controls. The existing reduced
macro already has no resistor-only leaves or series nodes:85467resistors
remain85467, with no effective reduction. The preliminary case-sensitive
node screen was incorrect and is superseded by
`dco_solver_profile_001/resistive_node_screen_casefolded.json`. No replacement
macro is adopted or benchmarked, and no capacitor or dynamic state is removed.

The891-fixture TT27C/1.8V combinational batch is running with KLU and explicit
single-thread BLAS. An independently pinned891-fixture SS125C/1.8V batch is
prepared and queued with the same runner. It waits for conservative shared
capacity admission, with a total12h budget including admission/assessment
and no identical automatic retry. The runner retains raw ambiguous output
crossings, checks initial truth/rails and terminal finite event correspondence,
and excludes mutable status from its terminal artifact hashes. These are raw
propagation/slew observations, not setup/hold/recovery/removal, full15PVT
library qualification or a release. At the progress receipt, three native
checks are live and SS125 is waiting; the shared limit remains four.

Current evidence and live-process identities are recorded in
`build/timing400/release_001/qualification_progress_002.json`. The mutable
implementation assessment points to this receipt and the completed solver,
settling and reduction evidence. Calibration, full timing/interface models,
whole-PLL acceptance and assembled physical qualification remain open. The
candidate remains unselected and release_qualified=false.

The next sequential timing toolchain is prepared in
`compact_capture_boundaries_fs125_001`:198fixtures over six FF types, data
rising/falling and asynchronous release at eleven clock-relative offsets.
All times are50%crossings, with200ps full ramps and5fF load. Thirty-six
separated +/-1ns controls assert expected captures; intermediate captures,
ambiguous final levels and every extra output crossing are retained rather
than converted into constraint passes. The raw observer checks initial and
pretest states, actual input/clock timing and the full final observation tail.
A separate ideal edge-triggered voltage oracle validates198synthetic captures
and36controls; wrong expectation, hidden extra output pulse, missing clock,
missing changing-input edge and wrong pretest-state faults are rejected.
Evidence is `capture_boundary_observer_validation_001/assessment.json`.
No native boundary scan is started or queued while SS125 is already waiting.
Sparse boundary observations do not qualify constraints or metastability.

A queue audit finds the newly waiting SS125 wrapper was launched through a
relative container script path. ROOT therefore resolved to `/work/OpenPLL`,
whereas the existing controller's native output paths use the canonical host
workspace prefix. Its conservative admission saw no matching native processes
and refused to launch. The wrapper is verified childless, without launch.json,
and waiting; only that wrapper is stopped, with its original receipts intact.
`compact_propagation_ss125_002` replaces this unlaunched preparation using
canonical absolute paths and `run_prepared_compact_propagation_v2.py`. The new
runner requires explicit canonical-workspace identity and a positive total
budget no greater than12h. The handoff subtracts all elapsed waiting time from
the original budget; it does not restart the clock or retry a native case.
Corrected admission now sees the three native jobs and waits for two free slots.
Three negative controls reject a wrong workspace, an oversized budget and a
zero budget before creating output (`compact_queue_guard_validation_001`).
All existing native DCO and TT27 jobs remain untouched and live.

Closed-loop driver bring-up now uses the exact frozen candidateRTL, the
phase-continuous VPI clock and explicitly synthetic DCO/BBPD models. The
48x256integer-frequency grid is generated only for this diagnostic; no measured
sample is replaced or interpolated into a qualified model. The synthetic BBPD
makes a wrapped phase decision at each actual feedback edge and emits an ideal
200ps-delayed/200ps-wide pulse, only while detector reset is released. Neither
this timing nor its aperture/storage/metastability behavior is physical evidence.
All traces, sources, tools and synthetic models have pinned hashes.

Allfour modes reach tracking in approximately96.6/104.5/107.1/112.6us at
100/250/300/400MHz, respectively. The initial KI4/KP0 diagnostic does not pass
sustained frequency/phase criteria, despite tracking=1 and FAILED=0. A controlled
KI1/KP8 comparison restores frequency control;100/250MHz pass trace acceptance,
while300/400MHz exceed the phase-span limit. The next KI1/KP4 diagnostic passes
allfour existing trace criteria, including the acquisition-confirmation deadline,
final four5120ns windows, code8..247, frequency, phase mean/span/drift and gaps.
Its last-window phase spans are0.183/0.145/0.224/0.146ns and frequency errors
3.914/5.082/16.212/4.495ppm, respectively. No release gain or PVT behavior is
selected from these synthetic results, and no frozenRTL is changed.

`audit_closed_loop_driver.py` independently checks each saved clock trace with
60-digit Decimal phase integration under the actual RTL tuning changes. Every
edge must be the first1ps tick after its continuous-phase crossing; every
reported TUNE must match the pinned synthetic table. It also compares every
phase-driver rising edge with the independently recorded RTL output-clock CSV.
Allthree four-mode diagnostic groups pass this audit. Missing-edge, wrong-level
and wrong-tuning-frequency controls are rejected. The original16phase-bridge
component checks retain their separate scope. These new audits establish driver
clock delivery under acquisition/tracking, not analog detector/model validity.

Evidence is retained in `frozen_closed_loop_diagnostic_001`,
`frozen_closed_loop_diagnostic_ki1_kp8_001`,
`frozen_closed_loop_diagnostic_ki1_kp4_001` and their three driver-audit directories
under the active400MHz build root. Each per-mode `trace_acceptance.json` reports
its actual result and whole_pll_qualification_pass=false. The60-case functional
matrix remains blocked on validated DCO/interface models; qualified cases remain0.
TT27cell characterization and both TT250DCO native endpoints remain live, with
corrected SS125 waiting for shared capacity. No native check is restarted.

The settling audit now has concrete longer-duration follow-up. Two independent
160ns plans reproduce the completed160-load/coarse1TT27C1.8V circuits atfine128
andfine247. Their original80ns runtimes are11524.8s and11082.3s. The crude
linear160ns projections are6.403h and6.157h, respectively, below the12h check
cap but not runtime guarantees. No fixed300ns check is introduced. The decks
preserve all circuit, capacitor, initial-state, tolerance and maximum-step
statements; only stop time and instrumentation measurements change. New
runs use KLU and explicit single-thread BLAS; the historical source environment
had no explicit thread variables, so that policy difference remains documented.
The previous KLU prefix control found matching printed edge times, without a
performance gain; no general numerical enclosure is inferred from it.

Each160ns plan predeclares20..80,40..80,60..80 and20/40/60/80/100..160ns windows.
Every result will be retained, with independent Decimal frequency/drift checks
and direct comparison of the original80ns prefix. No window, interpolation,
settling-error bound or calibrated model is adopted from this observation.
Validation independently compares every nonmeasurement SPICE statement,
checks three actual reference windows and eight synthetic160ns windows, and
rejects wrong baseline duration, a second transient declaration and insufficient
periods (`dco_duration_probe_validation_001/assessment.json`).

The fine128 probe is now waiting for the corrected SS125 runner's launch.json.
It does not compete for shared admission until that preceding external owner
has launched and cannot return to its admission loop. At handoff it verifies
the launch receipt and every preceding pinned input. Thus there is one external
admission contender at a time. The probe's single12h deadline starts before
this dependency wait and includes preparation, admission, native execution
and assessment. It has no identical automatic retry. Fine247 remains prepared
without a queued runner. The original DCO range controller, TT27 cell batch
and SS125 queue remain unchanged; all three native processes are live.
The new duration result will be observational evidence for choosing a defensible
convergence experiment, not a calibration or release pass by itself.

The closed-loop driver now exercises all12directed supported-mode changes.
`tb_frozen_mode_change_diagnostic.v` and `diagnose_frozen_mode_changes.py` use
unchanged frozen RTL, the exact previously tested synthetic frequency table,
explicit KI1/KP4, and the same ideal detector assumptions. Each ordered pair
runs an initial acquisition/lock interval, changes only the divider at220100ns
without external reset, and observes the new mode through440000ns with guard
edges afterward. The original trace criteria are applied independently to the
initial and changed-mode phases. All12cases pass both trace phases. These
results do not validate actual gain choices, physical DCO/interface behavior,
PVT coverage or release timing.

Every directed case independently checks continuous phase under the actual
RTL tuning sequence and exact identity of delivered oscillator rising edges:
2893462clock edges and1446728rising edges total. The separate
`audit_frozen_mode_changes.py` verifies all12ordered pairs exactly once,
all source/artifact hashes, the actual divider-change trace at220100ns,
tracking drop and reacquisition, both acceptance horizons/deadlines, and only
one oscillator RESET event at time0. The largest tracking reacquisition delay
is113104.351ns; tracking is not itself a lock verdict. Every actual trace,
acceptance and terminal-log path is bound to its recorded hash (72files).
Evidence: `frozen_mode_changes_diagnostic_001/assessment.json` and
`frozen_mode_changes_driver_audit_001/assessment.json` in the active build root.

This completes synthetic driver coverage for four reset-acquisition modes and
all12directed changes under the stated deterministic models. The60physical
mode/PVT cases and12directed physical changes perPVT remain blocked on
qualified DCO/interface models; qualified cases remain0. Existing native DCO
and cell-characterization runs are preserved, with SS125 and the serialized
160ns duration comparison waiting as previously documented. No release gate
is promoted using synthetic evidence.

The characterization-domain review adds an actual routed wire-cap inventory
for all40combinational masters over nom/min/maxRC. OpenDB output/net/sink/port
rows are compared with SPEF D_NET totals, retaining both source names and
resolved names. The first inventory reports101raw-name mismatches perRC;
inspection shows an extra quoting layer in OpenDB getName strings. The v2
audit decodes one quoting layer in each namespace, preserving literal
backslashes and case, and rejects collisions across all output-net names.
All used combinational outputs then resolve in all3RC sets. No R/C value,
physical net, live model or timing artifact is changed. The initial raw-name
inventory remains diagnostic evidence, not a physical missing-parasitic claim.

No reported wire-only total exceeds that master's maximum prepared external
fixture load. The minRC minimum reported wire totals for18used xnor2_4 outputs,
five used xor2_2 outputs and one used xor2_4 output are1.9928fF,6.60931fF and
83.8038fF, respectively. These are extraction observations, not guaranteed
physical/effective-load lower bounds. SPEF explicitly states PIN_CAP NONE;
sink/diode capacitance, coupling/effective-load behavior, input-slew coverage
and full nominal15PVT enclosure remain open. No zero-load fixture is excluded
and the three nonmonotone slew cases retain their previous unresolved status.

Preferred evidence is `compact_characterization_load_audit_002/assessment.json`;
`compact_characterization_load_parser_validation_001/assessment.json` preserves
case-sensitive positive parsing and rejects wrong units, negative/nonfinite
capacitance, duplicate D_NET entries and unknown NAME_MAP references. Both are
under the active400MHz build root and add no native checks or release passes.
The TT27cell native batch and two TT250DCO native endpoints continue to advance;
SS125 is still the sole external admission contender, with the160ns duration
runner waiting for its launch before attempting admission.

An independent native simulator check now reproduces the remaining sampled
fast-envelope counterexample using ngspice47. The circuit is the same retained
extracted NAND2_2 FS125C1.8V A-to-Y fixture,200ps full input ramp and5fF load;
its model also matches the current compact candidate's model index. The PDK,
geometry, parasitics and voltage stimuli are unchanged. Temperature/tolerance
and waveform-control syntax are translated for ngspice, with explicit1u
geometry scaling. No PDK/device-model patch or adoption is made. The source
Xyce log records its existing BSIM4.5-to4.6.1 fallback and pbswgd clamp warnings;
these observations do not isolate the cause of cross-simulator differences.

The2ps/reltol1e-5/abstol1e-10 ngspice result is37.0310604113ps output rise and
78.9330383152ps output fall, versus36.5481852966ps and78.5527289487ps in the
retained Xyce case. An independent1ps/reltol1e-6/abstol1e-11 reference gives
37.0298079951ps and78.9326953043ps. The largest observed ngspice refinement
change is0.0012524162ps. A separate40-digit Decimal waveform audit remeasures
allfour delays and verifies source/raw identities. The refined output rise
remains0.7906710624ps below the sampled37.8204790575ps fast bound. Thus this
counterexample persists in both simulators and the tested envelope remains
rejected. No fitted guard, broad numerical/model bound or timing-view adoption
is inferred from one case.

The small native probes each have a60s cap and use the remaining fourth native
slot. Their guarded handoff verifies the dispatch process and active engines,
briefly stops only dispatch (never its native children), checks capacity while
ngspice runs, and resumes dispatch in a finally block. Recorded dispatch pauses
are16.7775s and17.1137s; both checks exit0 and maximum combined native occupancy
is4. The original three Xyce checks retain their process identities and continue
running; dispatch is reverified live and unpaused afterward. No original native
check or12h deadline is restarted, and the existing12h watchdog stays active.

Evidence is `hs_ngspice_crosscheck_001/assessment.json`,
`hs_ngspice_crosscheck_refined_001/assessment.json` and
`hs_ngspice_crosscheck_audit_001/assessment.json` under the active400MHz build
root. Qualified release cases remain0; nominal15PVT characterization, effective
loads, sequential constraints, DCO/interface models and physical signoff remain
open. The native TT27cell batch and TT250DCO endpoint pair continue, followed
by the already serialized SS125 and160ns duration checks.

A nominal-only BBPD scope review separates reusable observations from unclosed
physical interface assumptions. It rechecks the retained phase-transfer
summary against its prior digest and verifies all60nominal coupled point-receipt
hashes. There are30complete/exclusive/monotone isolated curves:15process/
temperature points at1.8V with20/200ps input edges. Every transition bracket
is25ps wide; the largest absolute nominal endpoint is100ps (the earlier125ps
summary included off-nominal supplies). The coupled nominal subset comprises
all15PVT x +/-200ps x two input edges, with successful reported direction and
two-event capture. This review does not remeasure the historical raw native
waveforms or promote their fixed-rail/old-receiver extraction scope.

The frozen-candidate driver now tests static detector thresholds at both-100ps
and+100ps using the same synthetic48x256DCO table, KI1/KP4 and ideal pulse
latency/width as its earlier bring-up. Allfour modes at each extreme pass the
unchanged frequency/phase/fine-code/acquisition-window trace criteria; both
four-mode groups pass the independent Decimal clock-delivery audit. At400MHz,
the last-window means are-0.0999296875ns and+0.1000234375ns, with0.149ns spans.
These are below the0.25ns mean/span limits in this diagnostic. The static bias
observations alone therefore do not establish a400MHz phase-mean contradiction.
They do not qualify physical closed-loop behavior or dynamic noise/aperture.

Evidence is `bbpd_nominal_scope_review_001/assessment.json`,
`frozen_static_bias_n100ps_001/assessment.json`,
`frozen_static_bias_p100ps_001/assessment.json` and their two driver-audit
receipts under the active400MHz build root. Required reuse conditions remain:
exact detector macro/port/reset identity; current compact receiver topology,
extractedRC and pin-load bounds; clock/reset/rail/noise assumptions; near-
coincident capture/aperture and metastability holdouts; and the full physical
wholePLL matrix/directed changes. Release models and gains remain unselected,
qualified wholePLL cases remain0, and no additional native check is launched.

The TT27C1.8V compact combinational native batch completes891/891propagation
fixtures and888/891strict slew observations. The three ambiguous cases remain
774/837/873, the same identities as FS125; no filtering or waiver is introduced.
The domain review retains raw voltage and repeated-edge data. All594positive-
load fixtures are within the conditional diode bias range-0.2..1.95V, with
observed extrema-0.0832068041..1.90477583V. Sixty of297zero-external-load
fixtures leave that range (overall extrema-0.402108755..2.35712902V).
These standalone fixture observations do not prove actual routed voltage or
full load/noise enclosure. The largest repeated-opportunity delay difference
is10.7497561ps for xor2_2/inputB/20ps/0.10999pF, with raw delays0.7155748834ns
and0.7048251273ns. Its cause remains unassigned; no single-delay model is adopted.
Evidence: `compact_propagation_tt27_001/run_001/assessment.json` and
`compact_propagation_tt27_domain_review_001/assessment.json`.

SS125 begins normally when the TT27native exits. The old external admission
rule requires two free slots to launch one check, leaving the fourth slot idle
with two DCO engines and SS125 active. A new guarded admission mechanism uses
a short verified dispatch stop, then checks the complete stable reservation/
engine/native snapshot, launches one Xyce process and waits for its visibility
before resuming dispatch. It serializes external owners using a separate flock,
rejects full capacity and pending/preparing/awaiting-collection DCO engines,
and never stops native children. Every other external admission owner must
already have launched or use this guard; that condition holds at this handoff.
No pinned controller or live model source is edited.

The waiting duration wrapper is first stopped, verified childless/unlaunched,
then retired. Its native_run.json and prior receipts remain at their pinned
paths. The v3 wrapper uses a distinct native_run_v3.json and a handoff receipt
in the same case directory. It verifies the old claim, retirement and absolute
deadline derived from the original runner start ticks plus43200s. Waiting,
handoff, launch and assessment do not restart the12h budget. The160ns probe
starts as the fourth native process; dispatch is stopped51.843ms until the
new Xyce PID is visible and then resumes. Existing native children are unchanged.

Guard validation accepts stable0..3occupied snapshots, rejects full capacity,
pending reservation, preparing engine and missing child, then exercises the
actual full-four-slot rejection with Popen forbidden. No fifth child is created;
the original four native IDs remain and dispatch resumes. The validation also
checks the unchanged old claim and exact original absolute deadline. Evidence:
`guarded_native_admission_validation_001/assessment.json` plus the duration
case's `queued_runner_handoff_001.json` and `guarded_admission_v3.json`.

The198-fixture FS125sequential capture/release-boundary scan is now queued via
`run_compact_capture_boundaries_v2.py` with the same guard, canonical workspace
identity and a total12h budget. Its measurement functions remain identical to
the validated first version; only admission/timeout cleanup changes. It checks
full capacity before stopping dispatch, so a full queue causes an ordinary
budgeted wait. Four native checks are running: the TT250DCO endpoint pair,
SS125combinational batch and160ns TT400-region duration probe. Calibration,
full timing/interfaces, physical wholePLL and signoff gates remain unqualified.

Numeric DCO control now has a direct compatibility check independent of the
frequency lookup driver. `check_dco_control_encoding.py` instantiates the exact
frozen DigitalCore with the parameter block copied from its frozen AcquiringCore
parent, uses the real public DLF_Clear/seed-load path, and samples registered
outputs after three feedback-clock edges. It checks all48coarse x256fine code
pairs (12288vectors), including reset and rail encodings. Every observed numeric
fine word,255-bit active-low fine thermometer and47-bit active-high coarse
thermometer agrees with the native fixture encoding. A deliberately inverted
DUT fine-output polarity is rejected. No source RTL or physical macro is changed.

The reference consists of304SPICE decks emitted by the actual DCO generator:
256fine bases atcoarse1 and48coarse bases atfine128. Their control voltages are
checked against independent integer masks, and the completed160-load/coarse1/
fine128native input deck anchors the assumptions. Current routed exports retain
47/255/8/6-bit coarse-thermal/fine-thermal/fine-numeric/coarse-numeric outputs,
and the existing863-state Boolean-equivalence receipt remains applicable.

A separate binding audit verifies source/artifact identities and every ordered
XDUT port list:304emitted bases plus the retained completed native deck, all
matching the actual308-port extracted DCO subcircuit. This catches permutation
or positional mismatches at the fixture/macro boundary. Evidence is
`dco_control_encoding_001/assessment.json` and
`dco_control_binding_audit_001/assessment.json` under the active400MHz build root.
These checks add zero native simulations or wholePLL qualification passes.
They establish settled interface compatibility; startup/rail-frequency model
coverage, physical code-step/glitch/phase response and final assembled top
connectivity remain separate requirements. Four native checks and the queued
sequential-boundary scan continue with their existing budgets.


## Current compact event receiver fixtures (2026-10-19)

`extract_compact_event_receiver.py` traces the current routed candidate's
event-toggle cone from the equivalence projection and maps its exact SPEF
endpoints. The fixture contains two capture flip-flops, two XNOR gates and ten
clock buffers, with all17signal nets and four outside flip-flop input loads.
Nominal/min/max wire RC is retained, internal coupling is counted once and
omitted aggressors are static. Outside pin capacitances use the supplied TT25
scalar/range maximum; this is a conditional diagnostic load, not a qualified
PVT/Miller/noise bound. The ideal event-reset cut excludes reset generation.

`audit_compact_event_receiver.py` checks all102functional cell-pin bindings
across the three views against actual model port order, supply connections,
primitive inventories and pinned input/artifact hashes. Nine in-memory faults
(wrong supply, missing wire, missing leaf load in each view) are rejected.
Evidence: `compact_event_receiver_001/assessment.json` and
`compact_event_receiver_audit_001/assessment.json` under the active400MHz build
root. No new native simulation was launched and no physical gate was promoted.
The TT250 DCO endpoint pair, SS125 combinational batch and160ns DCO duration
probe continue; the sequential capture-boundary scan remains budgeted in queue.


The current receiver capture pilot is prepared in
`current_receiver_capture_tt27_002` and queued by
`check_current_receiver_capture.py`. It checks TT27C/1.8V/maxRC at both signed
200ps phase offsets and20/200ps input edges (four cases). It reuses the retained
fixed-rail sampled BBPD, verifies the historical model digest across its
container/canonical path alias, and binds the current14-cell receiver.
It waits for the earlier sequential-boundary scan to launch before competing
for guarded native capacity. One12h total deadline includes that dependency
wait, admission and all four cases; no identical retry is scheduled.
The prior empty preparation directory is retained with a failure explanation;
it launched no simulator. This pilot does not qualify generated reset,
metastability, PVT timing, dynamic pin loads, power or noise.


## Provisional current-candidate top connectivity

`prepare_candidate_top_v2.py` links the actual current routed AcquiringCore
netlist, the160-load DCO candidate and the sampled detector using explicit
macro declarations. The detector reset uses BBPD_RESET_N, its reference uses
REFCLK and its feedback uses CLKDIV_RETIMED. DCO reset uses RESET_N. The302
thermometer controls and two detector feedback bits remain internal. Gains
and the feedback divider remain explicit configuration inputs.

`candidate_top_004` contains the wrapper, declarations, Yosys hierarchy/driver
check and structural audit. All317scalar analog-macro LEF pins match expected
port sets; swapped detector reset and reversed fine-bit controls are rejected.
All functional standard cells use the existing library. Tap/filler/antenna
instances are preserved as physical-only declarations; no instances or wires
are deleted to pass linking. The routed digital netlist has implicit power,
so physical assembly must connect it using its existing PG geometry.

The earlier attempts are retained:001/002failed on missing physical-only
declarations;003links but exposes internal control buses as diagnostic ports.
004is the corrected structural integration candidate. This is not an assembled
layout: intermacro wire RC, macro interfaces, PG/noise, DRC/LVS and all other
release gates remain open. No native simulation was added or interrupted.


## Current physical assembly inputs and provisional macro floorplan

`prepare_digital_macro_abstract.py` exports the current routed digital database
with occupied routing layers blocked. The357macro pins preserve all406source
pin rectangles, directions and signal uses exactly. The GDS/database identities
match the current digital signoff receipt. Physical digital power pins are
VDD/VSS, which internally connect the standard-cell VPWR/VPB and VGND/VNB
respectively; this differs from the separate analog-macro body pins.
Evidence: `digital_macro_abstract_001/assessment.json`.

`candidate_floorplan_002` places the current454.615um-square digital macro at
(20,20), the125um-square160-load DCO at(515,20), and the120um-square sampled
detector at(515,185), within a660x500um provisional die. The nearest digital/DCO
channel is40.385um. These dimensions are initial assembly choices, not a
congestion/RC/noise-qualified floorplan. The first attempt is retained; it
stopped before placement because OpenROAD required a standard-cell site.

`audit_candidate_floorplan.py` checks674actual macro ITerm connections, all
three bounding boxes and lack of overlap. It verifies the two explicit digital
power connections, macro reset/clock wiring and thermometer bit identities.
Wrong detector reset, reversed fine-code binding and wrong digital power are
rejected. The physical top differs from the checked structural top only by
adding digital VDD->VPWR and VSS->VGND. Analog body rails stay separate.

The database and DEF are preparation for intermacro routing. Top pin placement,
power grid, route/RC extraction, assembled DRC/LVS/antenna/density/integrity and
physical timing/noise remain open. Missing macro Liberty warnings retain the
known unqualified timing scope. No timing or release gate is promoted. Four
native analog simulations and the existing budgeted receiver queues continue.


## Intermacro routing-capacity screen

The first355-net global route (`candidate_global_route_001`) overflows21130
resources. Digital thermometer pins are split152on the top edge and150on the
bottom edge, so the original narrow perimeter channels do not suffice. A
1000x850um provisional floorplan (`candidate_floorplan_003`) places digital at
(150,150), oscillator at(750,150), detector at(750,400). The unchanged674macro
connections, bounding boxes and non-overlap pass `audit_candidate_floorplan_v2.py`.
This larger placement with met2-met4 and two-grid macro extension still has
2457overflow (`candidate_global_route_002`).

Allowing signal routing on met1-met4 and using actual macro obstructions without
an additional halo gives zero global overflow (`candidate_global_route_003`).
It preserves355guide-covered signal nets,674macro bindings and55top pin shapes,
independently audited by `audit_candidate_global_route.py`. Reported signal
wirelength is251359um. All earlier congested results remain preserved and marked
nonpassing. The layer and spacing changes have not passed detailed DRC; zero
global overflow does not establish pin accessibility or detailed-route success.

Metal5is reserved in this screen. A power grid must be constructed and routing
capacity rechecked with its actual obstructions before final signal routing.
The standalone DCO calibration decks include extracted internal loading but no
assembled external PLLOUT receiver/interconnect load. Their measurements remain
unqualified for the assembly; final wire/pin loading and its effect on DCO and
BBPD behavior must be enclosed in the physical models. No native check is
restarted, no frequency model is adopted and no release gate is promoted.


## Main power grid and routing with its obstructions

The analog macro LEFs expose VPB/VNB as small met3 SIGNAL pins. These retain
separate top-level body-bias connections and are included in ordinary routing;
they are not silently tied to the main rails. The main VPWR/VGND grid uses
met4/met5 rings and stripes. The first generated core and macro grids were
disconnected. Explicit70met5bridges close the gaps, each outside all macro
bounding boxes with3um clearance and1.6um clearance from opposite-net met5
shapes. The two main rails pass `check_power_grid -floorplanning`.

`candidate_power_grid_audit_001` independently compares source/output database
geometry, checks that the only70added rectangles match the bridge manifest,
preserves existing shapes/vias and all674macro connections, and rechecks bridge
clearances. This is a connectivity screen, not full DRC, EM/IR or noise signoff.
The current grid is `candidate_power_grid_013`; failed attempts remain retained.

An isolated special-router attempt crashed before saving a database. Exact
OpenROAD dcf36133source is pinned in `pdn_source_audit_001` with matching Git
blob identities. Its ring selector finds21VPWR/19VGNDcandidate shapes in this
mesh while its group array is fixed at four. That path was abandoned; the final
bridges do not use temporary aliases, change pin names or modify OpenROAD.
Official command context: https://openroad.readthedocs.io/en/latest/main/src/pdn/README.html

`candidate_global_route_004` routes all357signal nets including both body-bias
nets with zero global overflow and rechecks both main rail connections after
pin placement/routing. The independent v2guide audit preserves674macro
bindings and55placed scalar top pins. Reported wirelength is252777um.

Detailed routing is running in `candidate_detailed_route_002`, with current
owner and input manifest in that directory. The first attempt stopped before
routing because the advertised bottom/top layer flags are deprecated. The
corrected invocation uses set_routing_layers and retains the first attempt's
absolute12hdeadline, including startup/correction time. No identical retry is
scheduled. Detailed DRC/route connectivity, antenna, extracted RC, assembled
LVS/density/integrity/noise and physical model/load closure remain open.


## Detailed top routing completed

`candidate_detailed_route_002` finishes detailed routing with zero reported
router DRC violations, an empty route.drc and both main rail connectivity checks
passing. It finishes within the original first-attempt12hdeadline.
`candidate_detailed_route_audit_001` independently verifies all357signal nets
have detailed wires (including VPB/VNB), preserves all674macro connections and
compares every power special-wire rectangle/via bounding shape against the
audited source grid: no power geometry changed during signal routing.

This closes the provisional top's routing-feasibility step, not assembled
physical signoff. Full streamed-layout DRC/LVS, antenna/density, extracted
intermacro RC and EM/IR/noise remain open. In particular the exported digital
macro LEF has no ANTENNAGATEAREA/ANTENNADIFFAREA annotations. A top-level antenna
pass that ignores internal macro gate/diffusion/metal geometry would not prove
the requirement; derive qualified hierarchical antenna models or perform an
applicable flattened geometry check before promoting that gate. Existing
standalone macro antenna receipts retain their original limited context.

The four native analog simulations and the two existing receiver queues
continue. No frequency/interface model, loop gain or final release candidate
is selected or qualified by the routing result.


## Completed SS125 observations and assembled-layout repair

The SS125/1.8V batch completes891/891propagation observations and888/891strict
slew observations. Cases774/837/873 retain the same ambiguous output crossings
as TT27/FS125. `review_completed_propagation.py` verifies terminal source hashes
and independently recomputes their crossings with40-digit Decimal arithmetic
from19354raw rows. All594positive-load outputs stay inside the conditional
diode bias range;64of297zero-load outputs leave it (overall-.437827..2.39953V).
The largest repeated-opportunity delay difference is14.6694ps, case839input
rise. These observations neither exclude zero-load cases nor qualify a library.
The FS125capture-boundary scan starts after the batch frees its native slot.

The first assembled GDS retains all source macro geometry and labels, but full
Magic DRC finds256rectangles and LVS detects a VPWR/VGNDshort in the added top
power geometry. All three underlying macro comparisons pass. Generic PGstraps
and vias inside the macros are replaced with connections to their existing
met5power ports; source macro GDS and all ordinary signal DEF routes remain
unchanged. No physical failure is waived.

The repair preserves separate external legacy VPB/VNB connections. The actual
DCO/BBPDpowered netlists leave those top ports unreferenced and connect all cell
well pins to VPWR/VGND; these ports do not provide independent body-bias control.
This corrects the earlier body-bias description.

Port-based power repair then passes LVS. Remaining met5width errors are addressed
by legal1.6um via wire pads and pruning unprotected external tails. A completed
iteration (`candidate_layout_checks_003`/`candidate_lvs_003`) has Magic DRC0and
a unique complete LVS match, but two cleanup-marker coordinates were off the
5nmmanufacturing grid. `repair_assembly_macro_power_v4.py` snaps removal masks
outward onto that grid and asserts every generated met5coordinate is on grid.

The current corrected design is `candidate_macro_power_repair_007`, streamed
and audited in `candidate_stream_006`: all three macro geometries/labels and
nine shared definitions match their sources. Current checks are
`candidate_layout_checks_004` and `candidate_lvs_004`, sharing the original
layout-check12hdeadline. Initial/native failures and all earlier candidates
remain preserved. Antenna/density, PI/noise, routed load/RC models, complete
nominal15PVT timing/calibration and the60physical wholePLL cases remain open.


## Exact assembled GDS DRC/LVS evidence

`candidate_assembled_layout_audit_001/assessment.json` binds full-style Magic
DRC0and complete unique LVS to the exact `candidate_stream_006/assembly.gds`
and `candidate_macro_power_repair_007/route.odb`. All55top pins match; all three
macro circuits are expanded in LVS. There is no Magic input-grid snapping.
All generated met5coordinates lie on the5nmgrid, the source macro geometries
and labels are preserved, and ordinary signal routes match the original
detailed route. The audit also retains the real256-DRC/shorted-power negative
case, which is rejected. These are DRC/LVS passes, not complete physical signoff.

The FS125capture-boundary batch completes198/198observation-integrity checks
and36/36separated controls. Its outcome review preserves all near-boundary
results; none has multiple post-test50% edges. Constraint/MTBF/model enclosure
qualification remains open. The current max-RC receiver pilot also completes
4/4signed two-event captures at TT27C/1.8V, with both200psphase directions and
20/200psinput edges. It still excludes parent intermacro wire RC, generated
reset, fullPVT/load/noise bounds and near-coincident/metastability holdouts.

A fixed20..60nslive DCO prefix screen measures244.8786/255.4641MHz at TT/coarse4/
fine8/247, provisionally surrounding250MHz. Only frozen prefix copies are
hashed; the ongoing native checks and growing waveforms are untouched. This
does not claim native completion, settled frequency or a qualified range.

After the receiver owner terminates, `run_dco_duration_probe_fresh.py` admits
the prepared coarse1/fine247160nsprobe through the shared guard. Admission
moves the workspace from three to four native analog processes, with only
~52msdispatch pause and no paused native children. It retains all eight
predeclared windows and independent Decimal comparisons; one total12hbudget
includes verification/admission/assessment. The fine128duration comparison
and TT250range endpoints continue. No numerical window or frequency model is
adopted before convergence evidence is complete.

Antenna/density, measured power/jitter and PI/noise, actual routed-interface
load/RC bounds, full nominal15PVT timing/calibration and the60physical wholePLL
cases remain open. The goal and all release-qualification flags remain active
and unqualified; no release tag or candidate selection is made.

The mutable assembly overview now points its power-grid fields to the corrected
007database and exact assembled-layout audit. The earlier013grid/connectivity
audit and004global-route report are historical references. The signal route
baseline is retained; power geometry intentionally changed to fix the observed
short and DRC errors. EM/IR/noise and the full physical-signoff aggregate remain
unqualified.

### 2026-10-19: actual assembled parent RC and loaded capture preparation

Implemented `extract_assembled_interconnect.py`, tied to the exact repaired
DRC/LVS-passing database, and extracted nominal/min/max parent RC in4.46s.
`audit_assembled_interconnect.py` checks357 nets/721 boundary endpoints perview,
wire connectivity, cap totals and reciprocal coupling, then emits matching
coupled SPICE and boundary bindings. An independent serialization readback
checks every exported edge/value;12 structural fault injections are rejected.
The first audit rejected OpenRCX's INOUT-as-I encoding for legacyVNB/VPB;
its source and failure explanation are preserved, and the successful audit
explicitly reconciles those six directions while retaining database semantics.

The assembled PLLOUT wire alone totals0.185289pF nominal,0.421899pF min-view,
0.464795pF max-view. Receiver/pad loads are additional, and coupling cannot
be replaced by a fixed effective load without electrical justification.
No intrinsic DCO range result is promoted to assembled frequency coverage.

Prepared and queued four TT27/1.8V parent-loaded detector/receiver capture
cases with `check_assembled_receiver_capture.py`. All357 parent-net wires and
couplings are present; other drivers remain explicitly static, with ideal
REF/divider/reset cuts and no external pad load. Guarded admission preserves
the four-native limit. One total12hbudget includes capacity wait and allfour
cases; timeout stays inconclusive and no identical automatic retry is allowed.
Existing native DCO jobs continue unchanged. Evidence and live observation are
recorded in `qualification_progress_021.json`; remaining release gates stay open
until their actual physical/model/timing and wholePLL evidence is complete.

The first assembled-RC capture case starts native transient analysis at22:51UTC
after the TT/coarse4/fine24780nsendpoint completes. Guarded admission records
three native jobs before and four after, ~40msdispatch pause, and no paused
native children. `qualification_progress_022.json` records the actual launch;
no capture result or loaded-DCO qualification is claimed yet.


### 2026-10-19: assembled density repair and antenna localization

The exact unfilled assembled GDS fails all175 constrained checks in the PDK's
stock density workflow (195raw70umtiles,24nominal700umstepped windows with the
PDK's clipped-edge convention, plus global checks). A separate PDK-generated
fill pattern reduces failures to25, allmetal5. The stock-filled candidate passes
fullMagicDRC0 but is not selected. `repair_assembled_metal5_fill.py` replaces
only the newly addedmetal5fill; it preserves originalmacro/parent geometry,
originalmetal5fill, all labels and the other seven newfill layers. It checks
1.6umclearance/minwidth and5nmgrid, with an8umtile/10umpitch pattern.

`candidate_stream_filled_002` now passes all175PDKdensitychecks, independently
recomputed from rawtiles by `audit_assembled_density.py`. Global densities are
FOM43.2%,LI52.3%,M1 48.2%,M2 45.6%,M3 44.7%,M4 43.9%,M5 59.2%; poly11.3%
is reported without inventing a numerical limit. The currentfilledGDS is a
separate pendingcandidate. DRC/extraction and completeLVS are running in
`candidate_layout_checks_filled_002`/`candidate_lvs_filled_002`, sharing the
originalassembled-layout12hdeadline. No oldpassingGDS or database is overwritten.
PriorparentRC explicitly excludesfill; matching fill-aware electrical evidence
is required before adopting the filled candidate.

`run_assembled_antenna.py` completes the PDK's transistor-awareMagicmethod on
the unfilledexactassembly, with5053feedbackrectangles (not5053uniquenets).
The PDKdeclares itsmodelpartial and diode-diffusioncoverage remainsunqualified.
A cleanphysicalinverter has0feedback, while an injected1000umlocalinterconnect
on itsgate triggers10feedbackrectangles. `candidate_antenna_localization_002`
resolves680exactrectangularMOSgateboxmatches to137extractednets, including
131DCOthermometernets and REFCLK,CLKDIV_RETIMED,BBPD_RESET_N,KI[5],DLF_CODE[3].
This is partialdiagnosticlocalization, not proofthat allviolatingnets are found
or that a diode/routing repair is qualified. Antenna remainsopen.

The firstparent-loadedcapturecase (TT27/1.8V,phase-200ps,edge20ps) completes
and passes signedtwo-eventcapture. The remainingthree cases wait for guarded
capacity within their originaltotal12hbudget; four nativeDCOjobs remainlive.
This capture evidence applies to the unfilledparentRC and fixedrail/resetcuts,
not to finalfilledphysicalmodels. TT/coarse4/fine8/247 nativewaveforms now
complete and bracket250MHz at244.878858/255.474846MHz. Tenfixedwindow checks
with independent40digitDecimal comparisons show fine247's20..80nsdrift is
32.2676kHz, above the25kHznecessarycap. Allwindows are retained and no window,
calibration or loadedmodel is adopted. The review saved itscompleteassessment
before a console-summarykeyerror; `dco_tt250_window_review_completion_001`
independently rechecks all10results, and a v2script fixes only futureprinting.
No nativecase is repeated for that reportingerror.

`qualification_progress_023.json` and the mutableimplementationassessment bind
these receipts and liveowners. Full15PVTtiming/calibration, antenna, matching
loaded/fill-aware models, reset/CDC, PI/noise, physicaljitter/power and the60
physicalwholePLLcases remainopen. Allrelease/adoptionflags remainfalse.


At23:13UTC the repairedfilledcandidate completes fullMagicDRC0 and uniqueLVS,
with allthree macro circuits expanded and55matching top pins. The sameGDS
passes175/175installedPDKdensity checks, and its physicalbbox is independently
verified as0..1000um by0..850um. `candidate_assembled_layout_audit_filled_002`
and `qualification_progress_024.json` bind allthree results to the exactGDS.
The mutableassemblyoverview now points to this filledGDS and retains historical
unfilledstream/audit pointers. Its database still describes conductive wires
and power; floatingfill is a separateauditedGDSoverlay. ExistingparentRC and
loadedcapturemodel exclude thisfill and are explicitly not finalfilled models.
Antenna, matching fill-aware electrical/model/timing and remainingreleasegates
stayopen; the fullphysicalsignoff/release/adoptionflags remainfalse.

`antenna_localization_geometry_validation_001` additionally checks all680
localizedgateboxes against the actualGDS poly/diff polygonintersection. All
are realMOSgategeometry at the inferred5nmcoordinate scale. This strengthens
localization, while incompletefeedbackcoverage and antenna-rule qualification
remainopen. `qualification_progress_025.json` records this addedproof.


### 2026-10-19: antenna rule semantics, formation connectivity and first repair

`antenna_rule_semantics_audit_001` corrects the earlier interpretation of the
PDK's antenna settings: partial means per-layer ratio, not a declaration of
incomplete coverage. The implementation computes diffusion credit; its displayed
limit is normalized to the maximum layer limit. UpstreamMagic8.3.623source is
retained with verifiedGitblob identities alongside the publishedSkyWater rule.
The defaultngspicestyle makes the n-diffusiondiode anMSUBCKT, which also enters
Magic's sensitive-gate mask. The same1000umcable passes with one diode in that
style; with built-inngspice(orig), one and two diodes fail and three pass.
The publishedMOS-onlygate denominator independently rejects the one/two-diode
cases even using only the unambiguousstraightcable sidewall lowerbound.
No installedPDK or binary is modified. Nativeantenna work now usesorigstyle.

The currentfilledGDS is checked again with the correctedstyle and debugoutput:
151reported violations,5053feedbackrectangles,137uniquenets. Everyreportedgate
and net is localized in `candidate_antenna_localization_003`; the geometry
matches the independentlyvalidated680gateboxes. A separateKLayout formation
connectivity audit passes150full-stack gate/portbindings and150wrong-port
controls. All143DCOrecords reach their externalports at the failing layer;
the twoBBPDREF/divider metal2records cannot reach their metal3ports yet and
need internalprotection. Externalprotection remains topologically possible
for the other reportedportcases. This is not a complete antenna-area checker.
The stockMagic implementation starts from onegate per finalnet, so coverage of
all disconnected intermediate forming-subnetworks remains an explicit concern.

`repair_compact_internal_antenna.py` replacesFILLER_19_546 with oneHSdiode_2
at the identical272.160/76.590umsite andMXorientation, on electrical_root_33_out
near electrical_branch_124/A. The remaining22635componentrecords and allmacro
pinshapes/locations are unchanged;32existing regularnetrecords change during
incrementalrouting. NewregularVDD/VSSconnectionrecords are power metadata,
not newsignalnets. The isolatedcore now passes zero router and fullMagicDRC,
uniqueLVS,84904/84904powerconnections,863state/output equivalence functions
with wrong-reset rejection, and all12TT25RC/mode timing screens. Reported
400MHzmargins remain+.747114nssetup and+.022886nshold. The MOS-onlyantenna
check has0feedback. `compact_internal_antenna_closure_audit_001` binds these
results; they do not qualify the full15PVTtiming or finalassembly.

The repairedcore is retained as a separateunadoptedcandidate until integration
and remainingprotection/model checks pass. Existingfilledassembly DRC/LVS and
175densitypasses retain their exact priorGDS identity. DCOintrinsicrange and
duration jobs continue with the original oscillator; no fifthanalog process or
identicalnative retry is introduced. `qualification_progress_026.json` records
thisprogress. Release/adoption flags remainfalse and the fullgoal staysactive.


### 2026-10-20 — Detector protection and repaired-macro integration

Implemented `repair_bbpd_internal_antennas.py`: two local decap12 sites become
same-footprint decap6 + decap4 + HD diode2 groups on REF and CLKDIVR. All 13
functional cells, both flip-flops, retained placements and macro ports remain
identical. Only the REF and CLKDIVR existing routed signal records change.
The identity checker initially rejected regular POWER/GROUND endpoint metadata
added by explicit rail attachment; comparison now excludes PG pins while
requiring exact macro ports, functional signal bindings and bad-clock/diode
negative controls. No native simulation was repeated for that metadata fix.

The detector candidate passes full Magic DRC (zero), unique LVS and a zero-
feedback MOS-only antenna scan. Independent GDS topology confirms both known
metal2 gate failures now reach distinct physical diode diffusions before
higher metal forms; wrong-diode probes are rejected. The actual HD diode
geometry is 0.4347 square microns with 2.64 micron perimeter. The GDS boundary
is exactly 120 by 120 microns, resolving the Magic boundary-redefinition warning.
`bbpd_internal_antenna_closure_audit_001` binds the results. Diode input loading
and reduced decoupling still require fresh analog checks; complete coverage of
all forming-subnetwork ratios is not claimed.

`stream_candidate_assembly_v6.py` creates a separate unfilled candidate with
both the repaired core and detector, preserving each source macro's geometry
and labels. The parent route and oscillator geometry remain unchanged. Full
assembled DRC/extraction and LVS against the matching repaired netlists are
running in `candidate_layout_checks_repaired_macros_001` and
`candidate_lvs_repaired_macros_001`, under the original shared layout deadline.
The previously passing filled assembly retains its exact historical identity;
its fill, RC and qualification receipts are not transferred to the new GDS.
Four existing DCO jobs continue, without a fifth analog process or identical
retry. `qualification_progress_027.json` records this progress. Release and
adoption remain false; the 400 MHz goal remains active.


### 2026-10-20 — Full assembly passes and independent antenna coverage

The unfilled repaired-macro assembly passes full Magic DRC with zero errors,
unique Netgen LVS with all three macros expanded, and 55 matching top pins.
`candidate_assembled_layout_audit_repaired_macros_001` binds the exact GDS.
The prior filled candidate and its density receipts remain separate.

The corrected MOS-only native scan now reports 147 violations on 135 nets,
with 4,940 feedback rectangles, versus 151 records on the previous assembly.
The two BBPD metal2 failures, one BBPD metal4 failure and the internal-core
metal4-contact failure have cleared. Remaining records are 129 on metal3 and
18 on metal4. All 147 records have exact extracted MOS gate localization.

`check_forming_antenna_geometry.py` independently enumerates every drawing
MOS-gated component at 13 conductor/cut stages, conserving total gate area at
each stage and excluding pure diodes from gate area. Actual-cell LI controls
reject zero, one and two diodes and accept three. A second control confirms
that two early gated components remain separately visible even when they
merge into one final net. The original assembly gives 148 geometry violations;
its three-record difference from native Magic is retained as unresolved.
The repaired assembly gives exactly 147. A fresh spatial probe binds every
native violating MOS point one-to-one to all 147 independent violating
components, including formerly ambiguous overlapping bounding boxes.

An initial crosscheck rejected the assumption that complete drawn perimeter
always bounds native contact-edge accounting: one ratio was 536.943624 versus
537.659. The failed attempt and exact source are preserved. The corrected
crosscheck records, rather than suppresses, numerical differences, from
-0.1331% to +2.0465%; no certified ratio bound or complete process-rule
qualification is claimed. Both methods flag every matched component.

`parent_dco_antenna_placement_002` is a separate unadopted candidate with four
HS diodes and a local well tap on each of 131 failing DCO control nets: 524
diodes and 131 taps. Placement passes. The first placement candidate lacked
local taps and is retained as provisional history. The second uses alternate
R0 rows and at least 1.92 micron horizontal island clearance; worst center
distance from its DCO port is 30.715 microns. This initial sizing still needs
physical power connections, local branches connected by metal3 or lower,
full layout/antenna checks and analog loading qualification. Macro geometry
and all live oscillator inputs remain untouched. The other four failing
interface/control nets still need protection.

Four existing native oscillator jobs remain live, with no identical retry or
fifth analog worker. Broad PVT expansion must not silently adopt the already
unqualified 80ns measurement profile; scheduling handoff is an upcoming task.
`qualification_progress_028.json` records the exact evidence and next steps.
Release/adoption remain false and the full 400 MHz goal stays active.


### 2026-10-20 — Powered protection, full layout repair and duration testbench fix

The external candidate now has 524 HS diodes and 131 local well taps on 131
DCO control nets, with M1 power connections to existing M4 stripes. Preserving
old signal routes prevented collision-free power routing, so all 357 parent
signal nets were rebuilt. Power checks passed. One wrapper expected the wrong
success wording after native completion; the separate completion audit binds
its finished outputs without repeating construction. PG cleanup merged M1
rectangles and removed 456 duplicate via records, leaving 330 unique new via
records with identical physical union and unchanged signal routes/placements.

The first protected GDS passed unique LVS but full Magic DRC found 338 markers:
330 M3 minimum-area markers at 110 PG landing sites and eight M5 spacing markers.
The failed geometry and successful LVS are retained. Its independent antenna
count fell from147 to40. Adding 0.6um-square M3 PG pads and rerouting ordinary
signals on M1 through M4 produced parent_dco_antenna_route_002 and stream_002.
This candidate passes router DRC0, full Magic DRC0, complete unique LVS and55
matching top pins. parent_dco_antenna_layout_audit_002 binds the exact GDS,
three preserved macro interiors, 524 diodes and131 taps. It is unfilled and
unadopted. Independent13-stage geometry finds32 remaining antenna violations:
27 M3 and five M4. Native MOS-only checking is running in native_002.

The completed lower duration probe exposed a testbench error: .tran extended
to160ns while reset pulse width stayed80ns. Reset reasserted around85.05ns,
invalidating late windows. All eight windows and the completed waveform are
retained in dco_duration_reset_failure_windows_001. Its three early20/40/60-to-
80ns frequencies exactly match the original reference. This stopped oscillation
is not a DCO failure. The upper invalid probe was explicitly stopped. Faulty
decks, plans and partial/completed evidence are preserved, not overwritten.

run_corrected_dco_duration.py changes only reset width/period to160/320ns so
reset remains released throughout the160ns observation. Both corrected probes
are running with their original absolute cutoffs; no12h allowance was reset.
Every declared window is retained, including unmeasurable windows, and rising
edges must cover the end of each requested window. A stopped oscillator cannot
pass using only earlier edges. No measurement window or model is adopted.

scheduling_handoff_002 retired the old DCO dispatcher before broad PVT expansion
with an unqualified80ns profile. Both live TT100 endpoint jobs and their one-
case wrappers continue; completed CSV/provenance can be collected without a
new simulation. The old receiver campaign used superseded parent RC. Completed
case0 is retained, active case1 was explicitly stopped and kept as partial
superseded evidence, and unlaunched cases2/3 were canceled. These are not silicon
failures. Its original cutoff remains applicable to matching replacement checks.
An earlier retirement preflight found case1 active and changed nothing; the
executed handoff accounts for the actual live state. Old pinned dispatcher and
guard inputs were not edited. Future admission must use the retired-dispatch
mode, rather than restart obsolete controllers.

Four analog native jobs are live: two TT100 endpoints and two corrected duration
probes. Nominal-supply15-PVT requirements and every remaining physical/model/
full-PLL gate remain unchanged. qualification_progress_029.json records exact
native identities, deadlines and next actions. Release/adoption remain false.


### 2026-10-20 — Antenna routing improvements and ten targeted banks

The completed native scan of protected candidate002 reports32 violations on32
nets, with129 exact gate feedback matches. All32 debug gate records map exactly
to independently violating forming components. Two nonfatal freeMagic(NULL)
messages are retained in the native log; the scan finishes with exit0 and all
reported failures are spatially cross-checked. No qualification is inferred
from a silent or incomplete native log.

The independent checker now includes a conservative contact-area allowance.
The audited native source adds surface-contact area to metal residue totals;
check_forming_antenna_geometry_v2.py adds twice the connected adjacent-cut area
to drawn sidewall area, including upper cuts without connecting upper metal.
Cut-stage bottom areas and gate/diffusion geometry remain unchanged. Actual
zero/one/two-diode failures, three-diode success, and the separated-component
control still pass. On candidate002 the bound retains the same32 failures and
exceeds every matched native displayed ratio (minimum relative margin about
5.35e-7). General process-rule qualification is not claimed from these controls.
The former unbounded geometry comparison is retained as historical evidence.

Routing more long conductors on lower layers reduced diagnostics further:
route003 (M3 adjustment0.8) gives18 violations, ten M3 and eight M4. Route004
(M3 adjustment0.99, M4 adjustment0.9) passes router DRC0 and the corrected
conservative checker finds ten M3 failures, with no other stage failures.
Both trials preserve all macro geometry and the existing protection placement;
full-GDS physical passes are not claimed for these intermediate trials.
Exact macro-port topology localizes all ten failing components. Seven are
newly failing unprotected fine-control nets, two already protected fine nets
need more diffusion credit, and one is BBPD_RESET_N. Some earlier inference
about late diode connectivity was superseded by this precise localization.

Forty additional HS diodes and ten local taps were placed in existing power-
rail coverage. The plan proves complete M1 coverage of both cell power ports;
no new PG straps or vias are required. Existing macro and cell placements are
preserved. The first targeted routing preflight showed that incremental DEF
import updates floorplan objects without restoring the intended fixed-wire
encoding. It exited before routing, and its outputs remain retained. A fresh
technology/macro LEF and full DEF import establishes the FIXED encoding.
The revised targeted run reroutes just ten nets, reaches router DRC0, and
verifies all347 background signal route records unchanged after normalizing
the fixed/routed metadata. All old pin bindings and macro ports are unchanged.
The source audit of this OpenROAD revision confirms first-path FIXED encoding
marks the complete net fixed; partial-path pinning was not assumed.

parent_dco_antenna_targeted_006 and stream_006 contain564 parent diodes and141
taps in141 banks on139 unique parent nets. Full-chip DRC/extraction, unique LVS,
and the corrected13-stage antenna checker are running. The earlier candidate002
remains the last full-GDS DRC/LVS passing reference, with32 antenna failures.
The targeted candidate is unfilled and unadopted. No passing evidence from the
earlier GDS is transferred to this candidate.

The two TT100 endpoints and both corrected160ns probes remain live, keeping
four native analog jobs. Their existing absolute budgets and the retired-
dispatch scheduling policy remain unchanged. No native analog rerun or new
analog job was introduced in this turn. qualification_progress_030.json records
exact evidence and live check identities. Calibration, interface,15-PVT timing,
whole-PLL, final density/RC/supply/noise and release gates remain open.

### 2026-10-20 — Independent parent geometry closes after local repair

The targeted candidate006 failed full DRC/LVS: eight M1 spacing markers and
shorts joining THERM77/53/101 and THERM11/21. The new independent topology screen
confirms both groups across 743 macro-port probes and passes on source004.
Its antenna zero is explicitly rejected as evidence of closure. Candidate008
repairs the physical failures and passes full DRC/LVS, leaving one conservative
M3 antenna failure on THERM53. Candidate011 reroutes only that net, reducing its
parent M3 wire length from 532.38 to 384.54 um while preserving all 356 other
signal routes and every placement and binding. Full Magic DRC is zero, LVS
matches uniquely, and all 13 conservative forming-stage antenna checks pass.
The 743-port topology screen finds no shorts, opens, or split nets.

The passing unfilled candidate now has fresh PDK density fill generation in
progress. Final filled GDS must pass its own physical, density, and native
MOS-only antenna checks; matching fill-aware RC and interface models are still
required. Existing native analog jobs and all original deadlines are preserved.
The superseded fixed-keepout attempt and two rejected layer-access preflights
remain retained with their actual outcomes. qualification_progress_031.json and
the implementation overview record the new evidence. This is qualification
progress, not a release: calibration, nominal 15-PVT timing, physical interfaces,
whole-PLL, supply/noise, and final integration gates remain open.

### 2026-10-20 — Final filled geometry validated on one GDS

parent_dco_antenna_final_geometry_011 binds full DRC zero, unique LVS, 55 top pins,
175 passing PDK density checks, 13 conservative antenna stages, native MOS-only
antenna zero, and the passing 743-port topology screen to one exact filled GDS.
All three macros, 564 external HS diodes and 141 taps are preserved. The extent
is exactly 1000 by 850 um. Native warnings are retained, including one nonfatal
freeMagic(NULL) message. Geometry passes do not establish electrical signoff.

Physical controls show that stock fill-purpose metal contributes no modeled
capacitance, while the identical conductor drawing produces a floating coupling
branch. Merely overlaying drawing purpose is also ineffective. The first CAD
capacitance diagnostic was stopped with its partial outputs preserved. A
corrected extraction-only view now replaces the converted LI/M1-M5 purposes,
retains all conductor footprints and 359 topology-derived parent labels, and
leaves the manufacturing GDS unchanged. Its raw capacitance extraction is live
under the original deadline. Floating nodes remain explicit; resistance,
FOM/poly fill, numerical/process enclosure and interface validation are pending.
No electrical model is adopted. qualification_progress_032.json records exact
evidence and live state. The four existing native analog jobs and original
budgets continue unchanged. Nominal 15-PVT timing/calibration, interfaces,
whole-PLL, supply/noise, power/jitter and final release qualification remain open.


2026-10-20: qualification_progress_033.json records completed metal-fill
capacitance extraction, digital-node correlation, the TT100 range result and
an isolated return-stage fine-range candidate. The network retains 21,007,169
positive capacitors and all floating branches; 21,579,265 exactly zero entries
were removed without changing nonzero values. All 359 parent labels and 7,468
digital targets are mapped. Device gate area is conserved. The 2,288 extraction
warnings match known decap instances by count, but full flattened feedback was
not captured. Poly/FOM fill, resistance, nonlinear device loads and RC enclosure
remain unqualified. Five combinational driver types have observed wire matrix
diagonals above their old characterization fixtures; these sums are not
qualified effective loads or timing bounds.

The completed coarse13 TT27 endpoints are 102.3183645443 and 104.1249809134 MHz,
so that band does not bracket 100 MHz. Neighboring coarse14 endpoint checks are
running. The two new 5 ps timestep checks were explicitly stopped, with partial
outputs retained, to prioritize this range gate; identical retries are not
authorized. Both corrected 160 ns duration checks continue. Four native analog
engines remain the maximum, with all original absolute deadlines preserved.

The separate IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80 source/config adds 80
existing einvp_1 input load cells on mirror_pass_n[0]. Yosys elaboration confirms
all 691 original cell connections and public ports are preserved, the new
controls avoid the existing coarse1 bank, and dummy outputs are independent.
A wrong-control negative case is rejected. No layout or analog check has begun
for this candidate; neither range nor release adoption is established. Await
neighboring-band evidence before committing physical implementation resources.
The passing filled-GDS geometry receipts apply only to the original candidate.
Nominal 15-PVT and all four target modes remain required. Qualified physical
whole-PLL passes remain zero; release, model adoption and timing closure remain
false.


2026-10-20: qualification_progress_034.json records a new extraction-only
poly+metal fill view and its live native Magic extraction. Actual poly-fill
geometry has zero overlap with active, tap, existing poly, licon or recognized
poly resistor/short markers. Gate area and every other mask region are
preserved. Poly fill is moved from fill to drawing purpose without retaining
an overlay. The manufacturing GDS remains unchanged. This CAD check shares the
original layout deadline and requests full flattened extraction feedback;
floating branches remain explicit. No analog engine was added or restarted.

lower_fill_control_node_audit_001 confirms that the automatically named P-tap
reference node is the substrate, not a floating electrode. It independently
reduces only the isolated poly control's explicitly floating branch. Neither
an ohmic FOM surrogate nor full fill/material/process enclosure is qualified.
The raw poly+metal network is still being extracted and must be assessed before
use. Four native analog engines continue with their original absolute cutoffs.
All four modes and nominal 15-PVT scope remain mandatory; release stays false.


2026-10-20: qualification_progress_035.json adds fresh min/nom/max OpenRCX
extractions of parent_dco_antenna_targeted_011/route.odb. Each corner contains
357 signal nets. All DEF terminals match, every resistance is positive, all
357 graphs are connected trees, and source-to-terminal path resistances are
ordered min <= nom <= max. A deliberately wrong terminal is rejected.
A full-GDS conductor audit locates all 10,636 exported node coordinates on
their expected logical nets across the three corners, with no unmatched
coordinates and a wrong-net negative control rejected.

This proves current parent-wire topology and coordinate correspondence only.
SPEF lacks pin capacitance, macro internals and generated GDS fill. The native
extractor grounds couplings below its default 0.1 fF threshold. Its C entries
must not be added to the full-GDS network a second time. Coordinate membership
does not yet identify a unique conductor layer or distribute the fill-aware C
onto resistance nodes. Full RC/process enclosure and physical timing remain
unqualified. The poly+metal Magic extraction and four native analog checks
remain live under original cutoffs. No additional analog engine was launched.
All release modes and nominal 15-PVT scope remain unchanged; release stays false.


2026-10-20: flat_decap_warning_gate_inventory_001 locates all 2,288 decap
channel boxes across 1,144 actual final-GDS instances. Well overlap independently
identifies the expected VPWR or VGND connection for each gate. Preliminary saved
flat feedback matches every expected box and rail; terminal MOSCAP device checks
and the complete network audit remain pending in the bounded collector. Native
Magic has finished the poly+metal extraction; the original runner is writing
its terminal receipt. No source model has been adopted.

The [SkyWater mask reference](https://skywater-pdk.readthedocs.io/en/main/rules/masks.html)
identifies FOM as the field-oxide mask, and its
[layer reference](https://skywater-pdk.readthedocs.io/en/main/rules/layers.html)
describes dummy FOM waffles. These references do not establish an electrical
resistance/capacitance model for this layout's dummy material. The installed
Magic technology and isolated controls remain the evidence for extraction
behavior; an ohmic-tap surrogate is still unqualified as a manufacturing model.


2026-10-20: qualification_progress_036.json records terminal poly+metal fill
capacitance extraction and its assessments. The source contains 49,357,430 C
records, 99,720 MOS devices, 726 diodes and 16 modeled resistors. All 359 parent
nodes participate; no negative capacitor was found. Removing only 26,845,001
exact zeros retains 22,512,429 positive capacitors, all device cards and every
floating branch. No nonzero values are changed or floating nodes grounded.

Every one of the 2,288 flat missing-terminal warnings matches an exact final-GDS
decap gate, its well-derived rail, and a native MOSCAP at the same position with
matching gate area and D=S=bulk on that rail. There are no unclassified, duplicate
or missing feedback entries. Wrong-rail and wrong-box controls are rejected.
Comparing full native device statements between metal-only and poly+metal views
finds all 100,462 statements unchanged, including geometry and connectivity; a
missing-device control is rejected. The expanded network replaces the older
view, rather than adding a second C patch to it.

The digital load inventory now uses this expanded network for all 7,468 mapped
targets. Reusing their identities is conditioned on unchanged native device
statements and original conductors, plus no new poly/contact overlap. Five
combinational driver types still exceed the old characterization fixtures by
observed wire matrix diagonal. Those sums exclude nonlinear device charge and
are not effective timing loads. PLLOUT, REFCLK and BBPD_RESET_N diagonals are
0.25536468, 0.29508430 and 0.39440007 pF respectively. FOM/bulk material coverage,
distribution of C onto wire resistance nodes, process/RC enclosure, calibrated
models and physical timing remain open. No electrical model is adopted. Four
native analog checks continue with original absolute cutoffs; all four modes,
nominal 15-PVT scope and remaining release gates are unchanged. Release and
adoption remain false, with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_037.json records 18 native CAD corner
controls and a live FOM bulk-surface sensitivity extraction. Known M1 baseline,
floating poly, P-bulk surface, N-bulk surface and floating M5 controls were each
extracted with installed ngspice(lrlc), ngspice(orig) and ngspice(hrhc) styles.
Independent reductions keep the explicitly floating electrode floating and
assume ideal bulk/supply references only in these isolated controls. All five
effective control capacitances strictly satisfy min < nom < max. The actual HS
nand2_2 GDS also preserves all eight native MOS statements after schema
normalization and all exported geometry/terminal parameters across M and X
forms. Missing-device and reversed-order controls are rejected. These checks do
not substitute for full-layout corner extraction or RC/timing enclosure.

The new FOM reference reuses the expanded poly+metal view and places diagnostic
ohmic surfaces on the remaining FOM footprints, partitioned by actual nwell.
The total footprint is 311916.8503 um2: 311869.8553 outside nwell and 46.995
inside. Added TAP/implant purposes exist only in this counterfactual view;
manufacturing GDS and all original gate/contact geometry remain unchanged.
No finite bulk impedance, actual FOM material equivalence or quantitative
upper/lower enclosure is claimed. A bounded collector waits for the running
extraction, then checks feedback, the full network, native device identity and
parent-diagonal sensitivity. Both retain the original layout deadline; no
native analog job is added. Four DCO checks and all original absolute cutoffs
remain active. Nominal 15-PVT, all four modes and all release gates remain;
release/adoption stay false with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_038.json records the completed counterfactual
FOM sensitivity extraction: 49,727,566 raw capacitor records, 26,920,418 exact
zeros, no negative capacitors, all 359 parent nodes and 2,288 individually
classified decap warnings. All 100,462 native device statements are unchanged
from the poly+metal view. Monitored parent matrix diagonals change by 0.4575%
(BBPD_RESET_N), 0.6323% (REFCLK) and 0.7360% (PLLOUT). These are sensitivity
observations, not effective timing loads or a qualified material enclosure.

Twelve additional native CAD controls preserve HD/HS tie and diode geometry,
terminal order and extracted parameter magnitudes across primitive/wrapper
forms. pj/perim names are normalized for comparison only; the documented diode
scaling is retained. Inventory of the actual full-GDS extraction finds two HD
diodes at effective area0.4347um2/perimeter2.64um and724 HS diodes at
area0.6417um2/perimeter3.24um. Parent, digital, detector and DCO DEF counts
independently agree. The existing fixed-geometry translator correctly rejects
the HS geometry; previous HD equivalence cannot qualify those724 instances.

A fresh HS comparison is prepared from pinned checked decks, changing only
geometry. All360 decks pass geometry, temperature and coverage preflight.
The bounded host runner is queued for one native analog slot, covering15
PVT electrical cases and75 noise-bias cases using ngspice47 as independent
reference and upstream Xyce as golden simulator. It holds the shared admission
lock through each simulator exit, including ngspice, so total analog concurrency
remains at most4. The single12h deadline includes preparation, queue, execution
and raw-data assessment. No translated HS model is adopted before it passes.

Full-layout min/max capacitance extractions are sequentially queued behind the
completed large FOM extraction; minimum is now live. The original empty queue
was retired before any corner worker/native launch to add15s parent cleanup
grace around the worker's existing10s native termination cleanup. The worker's
original absolute native cutoff is unchanged. Corner readers now recognize
foundry-wrapper active nodes and retain all wrappers during exact-zero cleanup;
their full-layout assessments remain pending. Four existing DCO runs continue.
All modes, nominal15PVT scope and remaining release gates remain unchanged,
with zero qualified physical whole-PLL cases and release/adoption false.


2026-10-20: qualification_progress_039.json records the corrected corner
warning assessment and a lumped floating-capacitance reduction. The first
reader stopped because wrapper export produces726 "Could not determine device
boundary" diagnostics in addition to2,288 decap terminal diagnostics. That
failed assessment is retained. Actual final-GDS diode diffusions are now located
individually; all3,014 minimum-corner messages match known devices, with native
position, area/perimeter or gate-area and connection checks. No native
extraction was rerun. The minimum network contains99,720 MOS,726 diode and16
resistor wrappers, all359 parent nodes and no negative capacitors. Exact-zero
cleanup retains21,384,654 positive entries and all100,462 wrappers unchanged.
The maximum source and its bounded collector remain live.

An isolated NumPy2.2.6/SciPy1.15.3 environment is recorded in
numerical_environment_001.json. The reduction preserves the parsed positive
network and solves zero incremental charge on2,095,561 floating nodes in174
anchored components. It assumes zero wire resistance and holds other active
terminals/supplies incrementally fixed; nonlinear device charge is excluded.
Energy/residual certificates, including floating-point allowances, give wire
capacitance intervals214.239114198..214.239114751 fF for PLLOUT,
265.956242762..265.956243306 fF for REFCLK and
331.333226191..331.333226749 fF for BBPD_RESET_N. These meet the requested
0.0001fF numerical interval width. Existing native poly and metal controls
agree with independent Decimal series reductions. Isolated unanchored test
components preserve port C; inaccurate trials retain wide intervals and
negative C is rejected. This numerical result does not qualify material,
distributed RC, nonlinear loading or physical timing.

The PLLOUT diagnostic exceeds buf_1's nominal TT25 library limit0.130015pF.
A separate unadopted RETURNFINE80_BUF8 candidate therefore changes only out_buf
from buf_1 to buf_8, whose nominal5pF library domain contains this diagnostic.
Both library logic functions are A. Elaboration preserves all771 instance
connections, all public ports/encoding, all80 return loads and the other770
cell types; wrong-input and extra-cell controls are rejected. This is a design
margin experiment, not proof of functional overload. Fresh layout, analog,
loaded-interface and15PVT/four-mode validation are required. Physical work
still awaits terminal range evidence. All original checks and deadlines
continue, HS geometry comparisons remain queued, and release/adoption stay
false with zero qualified physical whole-PLL cases.


2026-10-20: qualification_progress_040.json records terminal min/nom/max
full-layout capacitance comparisons. All359 parent diagonals are ordered;
these are matrix sums, not effective timing loads. Maximum-corner assessment
classifies all3,014 diagnostics and retains23,107,833 positive capacitors after
removing26,267,595 exact zeros, preserving99,720 MOS/726 diode/16 resistor
wrappers. No source extraction was rerun.

Eight NFET model names differ between orig and each wrapper corner. The
installed technology maps0.36um scnfet devices to ordinary nfet in orig and
special_nfet_01v8 in wrapper styles; all other native fields match. The special
PDK model has a matching0.15um length/0.36um width bin. The two models remain
distinct; no electrical equivalence or full-layout nominal model is adopted.
A follow-up actual detector dfrtp_1 control, recorded in
narrow_mos_corner_exports_001/assessment.json, completes four native CAD cases.
Orig and nominal-wrapper complete wire-C matrices agree exactly; all three
wrapper styles have identical normalized native devices. This small control
does not replace full-layout nominal wrapper/model validation.

Distributed-RC controls are retained with their failures. The initial wire-only
control stopped without completion. The first driven control had conflicting
port indices; a subsequent duplicate-conductor-port case terminated with
signal11. The sequence does not independently prove the signal's cause,
despite the stronger wording in that control's frozen docstring. Corrected
single-driver-port controls complete for both floating and explicitly ported
metal tiles without port-definition errors. An independent resistor-component
collapse and Decimal branch comparison finds11 and12 changed capacitor pairs,
respectively, including lost internal-node coupling and altered substrate
capacitance. Both exports also contain four negative capacitors. These facts
do not by themselves establish whole-network nonpassivity, but the default
extresist capacitor export fails the necessary matrix preservation check and
is not approved for full-layout use. Exact unchanged matrices pass the checker;
deleting the actual tile coupling is rejected. Raw outputs and failed control
receipts are retained. The checked parent wire R and full-GDS positive C
networks remain separate until a geometry-supported distribution or timing
enclosure is qualified.

The four original DCO jobs continue under unchanged absolute deadlines and the
four-engine limit. HS diode comparisons remain queued within their original
12h check budget. No DCO candidate has been physically adopted. Release and
model-adoption status remain false, with zero qualified physical whole-PLL
cases; nominal1.8V, all100/250/300/400MHz modes and15PVT remain required.


2026-10-20: qualification_progress_041.json records the full-layout nominal
wrapper extraction and further RC controls. The four-case actual dfrtp_1
control has28 MOS and four width-selected special NFETs per cell. Orig and
nominal wrapper wire-C matrices match; nominal/min/max wrapper native device
sets match without aliases. A fresh full-layout ngspice() wrapper extraction
is live in poly_metal_full_nominal_wrapper_001. Its collector will audit all
warnings, network entries and exact-zero removal, then compare its complete
capacitor export stream with the retained orig view and its device statements
with both RC corners. The original09:44UTC CAD deadline is retained for
preparation, execution and assessment. No native analog engine is added.

Matching upstream Magic8.3.623 source is pinned at
fd12c39c37f26a0fe6e04698b1011e31b8bd3229 in
rc_extraction_source_analysis_001; binary/source equivalence is not asserted.
The manual command sets signal mode, whose capacitor reader adds each
coupling value to both node totals. Native manual-only controls still change
11/12 branch pairs and lose five internal coupling pairs. Automatic-only
controls retain those internal pairs but still change5/6 substrate branch
pairs. Both paths retain four negative C entries. Removing the duplicate
resistance stage therefore does not make this export acceptable. See the
[matching reader source](https://github.com/RTimothyEdwards/magic/blob/fd12c39c37f26a0fe6e04698b1011e31b8bd3229/resis/ResReadExt.c)
and [command source](https://github.com/RTimothyEdwards/magic/blob/fd12c39c37f26a0fe6e04698b1011e31b8bd3229/resis/ResRex.c).
Installed tools and existing physical models are unchanged.

charge_preserving_rc_controls_002 reconstructs both small controls by keeping
all31 native resistors, MOS records and public ports, discarding the altered
C export and restoring the original positive capacitors. Deleted original
nodes attach to an existing MOS terminal on the same original conductor.
There is no nearest-coordinate guess. An attempted exact original seed
mapping failed because the seed is absent from the emitted R nodes; that
attempt is retained and exact seed preservation is explicitly unproven.
After resistor-component collapse, every original capacitor branch agrees
exactly, with zero negative capacitors. Wrong-conductor attachment is rejected.
This is a lumped-placement prototype: physical distributed C placement,
transient error and full-layout RC/timing remain unqualified. It is not adopted
for release timing.

The original four DCO simulations and queued HS geometry comparison remain
live under their unchanged deadlines and four-engine admission limit. All
100/250/300/400MHz modes and nominal15PVT remain required; zero physical
whole-PLL cases are qualified. Release and model-adoption status stay false.


2026-10-20: qualification_progress_042.json changes the DCO model gate based
on an audit of the actual source used by all four live probes. Exporting the
retained native .ext without RC backannotation at the same0.01fF threshold and
collapsing explicit wire R exposes at least1,799 changed capacitor branch pairs
above a conservative print-rounding allowance, including256 removed pairs.
The source contains126 negative intermediate rnode C entries. The raw export
also changes two junction-area/perimeter records; MOS models, dimensions and
collapsed terminal identity otherwise match. The existing resistor reduction
preserves every capacitor record, so it does not repair these discrepancies.

The exact reduced-model hash is disqualified for physical range/calibration
in DCO_RC_model_invalidation_001. All four DCO diagnostics were stopped under
the shared admission lock; decks, logs and partial waveforms are retained in
unqualified_dco_RC_retirement_001. Their original deadlines were not reset and
no identical retry was started. Earlier TT frequency brackets remain results
of that model and cannot choose presets or prove physical range failure. This
supersedes the earlier plan to wait for coarse14 terminal evidence before
choosing a return-fine physical experiment. A fresh validated replacement
model must precede that decision. Retired dispatcher status files retain
historical observations; the latest progress/invalidation receipt overrides
their eligibility for physical range decisions.

The freed analog slot completed the HS diode comparison: all360 upstream-Xyce
and ngspice47 analyses,15 electrical PVT cases and75 noise-bias cases pass.
Maximum relative errors are0.0002206245 DC,0.0000054104 complex AC,
0.0000048452 imaginary AC,0.0001422093 rising charge,0.0002426655 falling
charge and0.0000187787 noise PSD, within unchanged limits. Both physical
diode geometries now have checked compatibility scope. The new
scripts/translate_sky130_checked_diode_geometries.py binds HD/HS evidence,
foundry-model hashes, native outputs and prepared decks before accepting only
HD area4.347e11/perim2.64e6 or HS area6.417e11/perim3.24e6 native wrapper
arguments. It emits explicit effective0.4347um2/2.64um or0.6417um2/3.24um
fixed-temperature level1 wrappers. The caller must use the same global
Xyce temperature. Actual726 wrapper cards (2HD+724HS) pass all15 model-template
checks against the completed native HS models and an end-to-end CLI check.
Unknown geometry, duplicate/continued cards, conflicting global scaling,
complete decks and already translated input are rejected. This prepares
compatibility fragments; no physical PLL model is integrated or released.

Independent OpenRCX DCO inter-cell R extraction completes min/nom/max. All505
routed nets match their DEF terminal sets;453 omitted nets are unrouted
singletons. All R graphs are positive and connected; path ordering has zero
inversions, with seven multiple-driver nets kept explicit. Exact GDS/DEF
transforms match1,736 instances and2,071 signal terminals on956 signal nets.
The two extra DEF singleton names are body-only VPB/VNB public ports. All
2,641 internal wire-coordinate records and5,418 terminal-coordinate records
probe the expected conductors. Another354 terminal records fall outside their
conductor, but independently equal the mean of their actual pin-rectangle
centers within1nm; every actual rectangle probe is on the expected component.
They remain virtual terminal coordinates and are not used as physical C
locations. No coordinate or connectivity waiver is applied. Cell-internal R
and spatial C-to-R assignment are still unqualified.

charge_preserving_DCO_RC_prototype_001 retains97,616 native wire R and restores
all35,051 original nonnegative C plus original parameters of8,618 MOS and two
intrinsic R wrappers, including the two changed junction records. Exact
capacitor matrix and device equality are checked after wire-R collapse;
wrong attachment/value controls are rejected. Deleted capacitor nodes attach
to a device terminal on the same original conductor. This lumped-placement
prototype excludes assembled loading/fill/supply effects and has no spatial
C or transient-error qualification; no native analog run or release adoption
is authorized by its receipt.

Full-layout nominal wrapper extraction and warning/network/zero cleanup are
terminal. All100,462 normalized device statements match min/nom/max wrapper
styles without model aliases. The49,357,430 capacitor exports have different
record order and IDs, so the initial raw-stream comparison does not prove C
matrix equivalence. An exact Decimal, endpoint/order-independent comparison
of both22,512,429-positive-record multisets is live under the original09:44UTC
CAD deadline. No extraction was retried. All four nominal1.8V modes,15PVT,
physical timing/interface bounds,60 wholePLL cases, mode changes, material/RC
and supply/noise/jitter/power/integration gates remain required. Zero physical
wholePLL cases are qualified; release/adoption stay false.


2026-10-20: qualification_progress_043.json proves exact nominal capacitor
network equivalence despite changed export ordering. Both positive views have
22,512,429 records. Exact Decimal values, unordered endpoints and removed
instance IDs are externally sorted; both complete multisets have SHA256
4d03c57417ac17d6bd81409521051958b326f562dcff020ff412ea29fa0c1c15.
Actual-record reorder/ID/endpoint controls preserve equality; deleting a record
breaks it. Together with the prior100,462-device wrapper comparison, this
establishes consistent nominal/min/max wrapper model selection without aliases
and preservation of the original nominal C matrix. Floating branches remain
explicit. This does not qualify material, spatial RC, nonlinear loading or
physical timing, and no runtime model is adopted.

An isolated unmodified Magic8.3.623 source build is prepared at the pinned
fd12c39c37f26a0fe6e04698b1011e31b8bd3229 revision. Build attempts retain their
logs: missing X11 headers first stopped compilation; a modular configuration
lacked the expected export backend; changing configuration without cleaning
left stale conditional-compilation objects. A clean fixed-configuration build
in isolated_magic_stock_build_004 completes and passes24 native baseline
checks. Four physical controls (floating metal, floating poly, HS NAND and
the actual HD narrow-device FF) have exactly matching parsed C matrices,
native devices and feedback against the installed extractor at min/nom/max.
Installed tools and the golden upstream Xyce backend are unchanged. Control
agreement does not establish full-layout binary/source equivalence.

The isolated diagnostic patch exposes the existing native node/coupling clip
arguments through an opt-in internal-coordinate rectangle. It also logs signed
ground/coupling values before the original output clamp at17 significant
digits. The first diagnostic build catches a missing stdlib declaration;
that attempt is retained. The corrected diagnostic build passes24 further
native default-mode comparisons at all3RC corners. No capacitance arithmetic
is changed in default mode; the diagnostic code is separate from installed
tools and qualified physical models.

Native window accounting in magic_cap_clip_window_controls_001 completes24
CAD runs across four nominal physical controls. Every covering window matches
the unclipped matrix after native print precision is accounted for. Quadrant
sums agree for the HS NAND and HD FF, but fail for floating metal/poly fill.
For metal fill, SIG-to-ground changes by+2.9343999344fF and SIG-to-tile coupling
by-0.8850111643fF; poly-fill changes are+3.9341178665fF and-0.8519359402fF.
These exceed the declared0.0001fF plus1e-9 relative accounting tolerance.
Negative local ground contributions on the cell controls are retained rather
than clamped before summation. All node names are preserved and omission of
a nonzero quadrant is rejected. The rectangular-clipping decomposition is
therefore rejected for DCO/full-layout capacitor placement; no broad layout
extraction or long analog sweep uses it.

The next spatial method must trace contributions from unchanged full geometry,
retain support locations plus signed shielding/clamp adjustments, and recover
the original matrix before using the resulting placement with wire/device R.
Junction-parameter location and transient-error enclosure are also open. The
previous DCO model remains disqualified; its four retired jobs are not retried.
The diode compatibility results remain valid in their checked scope. All
100/250/300/400MHz modes, nominal1.8V/15PVT and remaining physical timing,
wholePLL, mode-change, material/RC, supply/noise, power/jitter/area and integration
gates remain required. Zero physical wholePLL cases are qualified, and release
and model-adoption status remain false.


2026-10-20 checkpoint044: full-geometry DCO charge accounting and substrate context

The current immutable checkpoint is
build/timing400/release_001/qualification_progress_044.json. An isolated623
contribution tracer now uses a private exclusive file and completion marker.
The failed shared-log attempts and the corrected uninitialized fringe-support
rectangle are retained. Default mode passes24 native installed-tool comparisons;
four small physical controls pass12 traced corner comparisons. A streaming
reader agrees exactly with the original reader on12 native control logs and
rejects malformed/truncated records and omitted actual contributions.

The actual DCO passes installed-tool C/device comparisons and signed contribution
accounting at all3RC corners: nine native C-only runs and six resistance-enabled
runs. Each corner retains all8620 native devices. C-only traces contain about
7.74million events; resistance-enabled traces contain about8.30million. Their
recovered matrices agree within explicit native print/arithmetic allowances.
No full-DCO output-clamp contribution is unlocated. These are numerical/native
accounting controls, not physical capacitor-placement or transient-error proof.

A separate context audit finds1753 nominal C-pair differences, up to0.5114fF,
between a new C-only extraction and the retained pre-RC extraction. Exported X
devices and ports are identical. Re-enabling native resistance extraction
recovers the retained nominal capacitor matrix exactly. PDK technology files
are identical. Pinned upstream ExtCell.c and ExtBasic.c show that EXT_DOEXTRESIST
changes both substrate preparation and default-substrate-type membership;
ExtMain.c also runs a full resistance pass. C-only and RC contexts must not be
mixed without a direct equivalence proof.

The independent native-R coordinate survey retains89955 coordinate records and
finds coordinates for all78613 exported R/MOS/port nodes. It classifies72225
records on the expected conductor,10314 as unexported intermediate records,
7382 as MOS body terminals outside the wire-only geometry model, and34 as
unresolved VGND internal coordinates. Substrate records are included when
mapping the ground seed. Well/bulk material, finite impedance, virtual/internal
coordinates, junction distribution and spatial C/R error bounds remain open.

An opt-in C-only RC-substrate mode is prepared to preserve the native RC
substrate context while skipping the automatic full wire pass. Its direct DCO
corner equivalence controls are the next gate before any assembled-layout use.
The former DCO RC model stays disqualified and its four retired analog jobs
remain stopped. Original absolute CAD deadlines and frozen nominal1.8V/15PVT,
100/250/300/400MHz scope remain unchanged. No physical wholePLL case is qualified;
release and model-adoption status remain false.


2026-10-20 checkpoint045: common native RC substrate context validated

build/timing400/release_001/qualification_progress_045.json is the latest
immutable checkpoint. The opt-in OPENPLL_CAP_RC_SUBSTRATE mode passes24 native
default comparisons,24 installed-RC versus opt-in-C-only physical-control
comparisons, and three actual-DCO corner comparisons. All three DCO capacitor
matrices,8620 native devices and feedback match installed resistance-enabled
extraction exactly. Signed contribution accounting passes at all three corners.
No automatic full wire-R pass or .res.ext output occurs in the new C-only mode.
This proves the implemented substrate-context operation in the checked scope;
it does not qualify spatial C/junction placement, bulk impedance or timing.

Assembled-layout min/nom/max raw capacitor extractions are now attached at
poly_metal_full_RC_substrate_capacitance_001/{min,nom,max}. They share the existing
full-layout CAD memory lock, so only one native extraction runs at a time.
RC_substrate_capacitance_collection_001/{min,nom,max} waits on those exact jobs
and then audits all warning geometry, capacitor/wrapper coverage, and exact-zero
removal. Tracing is disabled on the broad views to bound output and runtime.
All jobs and assessments inherit the original deadline3136114.566309955
(about09:44UTC); preparation, queuing and assessment count against that cutoff.
Timeout remains inconclusive, and none of these jobs automatically retries.

The former C-only parent networks remain separate diagnostic evidence. No new
network is adopted as a physical runtime model. Bulk/well geometry and finite
impedance,34 VGND internal coordinate supports, physical C and junction
allocation and transient-error qualification remain open. No fresh native
frequency sweep is started with the retired model. The frozen nominal1.8V,
15PVT,100/250/300/400MHz scope and all release gates remain required. Physical
wholePLL passes remain zero; timing closure and release qualification are false.


2026-10-20 checkpoint046: native resistor material and minimum-corner full C

The latest immutable checkpoint is
build/timing400/release_001/qualification_progress_046.json. A private opt-in
R-node tracer records node origin bits and incident material types. The first
strict output comparison is retained as a failed attempt: native-generated
node names are unstable, and220 unattached internal representative coordinates
change. A coordinate/device anchored graph comparison proves a bijection for
all78613 exported nodes, checks four residual symmetry assignments, and
preserves resistor branch multiplicities, printed R intervals, MOS parameters
and exact mapped terminals. Real resistor-value, connection and MOS terminal
coordinate faults are rejected. The original pre-RC C matrix and native devices
are preserved. Backannotated C remains excluded:45 default-comparison pairs
differ beyond local print intervals, at most0.00001fF. The already-invalid old
RC model is not requalified by the R-only proof.

The native trace contains2994 output groups (automatic subset plus explicit
all-net pass). Its last2686 conductor groups recover all89955 .res.ext node
coordinate records exactly. All34 previously unresolved VGND internal points
are junctions with pwell-only incident resistors. Independent actual-GDS masks
place all34 in the default pwell domain; deep nwell is absent. All8204 internal
MOS-body records lie in the expected well material. Four additional records
are supply origins on metal4/metal5. Their actual top-level VGND/VPWR labels,
GDS conductors and cross-layer connectivity are verified independently. These
four origin coordinates are not asserted to be local physical MOS-body
locations. Bulk impedance, body connections at the origins, spatial C and
junction allocation, and transient-error enclosure remain unqualified.

Minimum-corner full-layout RC-substrate assessment completes:100462 devices
(99720MOS,726diodes,16intrinsic resistor wrappers),33669 active nodes and all359
parent nets. The raw49355117 C records contain27970463 exact zeros and21384654
positive capacitors, with no negatives. Zero removal changes no nonzero C,
floating branches or device cards. Native RC substrate preparation determines
all diode boundaries, so the old3014-warning assumption correctly fails and is
retained. Its replacement individually validates2288 decap warnings and all726
diode positions, areas, perimeters and body connections. The two obsolete
queued assessors are retired through verified pidfds after replacement
collectors are confirmed live; no native extraction or analog process is
signalled or retried.

Maximum and nominal extraction/assessment and exact old/new capacitor-context
comparisons remain under the original09:44UTC cutoff. Zero physical wholePLL
cases are qualified. The frozen nominal1.8V/15PVT,100/250/300/400MHz requirements,
remaining timing/interface and physical release gates are unchanged. Release,
model-adoption and timing-closure status remain false.


2026-10-20 checkpoints047/048: common-substrate check closed inside12h

The latest immutable state is
build/timing400/release_001/qualification_progress_048.json. All min/nom/max
native full-layout C extractions, geometry/warning audits, complete network
checks, exact-zero removal and sorted matrix comparisons finish before the
original09:44UTC cutoff. All source, assessment and comparison processes are
verified terminal; no native CAD/analog engines remain live. Historical running
observations are retained separately from the reconciled terminal job state.
The original budget is not reset and no native extraction is retried.

Each corner preserves100462 devices:99720MOS,726diodes and16intrinsic resistor
wrappers, with33669 active nodes and all359 parent nets. There are no negative
capacitors. Positive C counts are21384654(min),22512429(nom),23107833(max).
All device/continuation bytes match the corresponding older context exactly.
The new context changes12184/12188/12192 non-self C pair sums, respectively;
maximum pair changes are5.4/6.7/8.4fF and sums of absolute pair changes are
62.58900/87.34786/133.38906fF. These are matrix observations, not effective input
loads or a transient enclosure. Old C-only and RC-substrate data are separate.

For nominal, every changed edge connects fixed boundary nodes, so the old
floating-node energy certificate transfers by exact boundary-energy shifts;
no floating-node linear solve is repeated. Correct-context wire-only bounds
are PLLOUT214.299484198496..214.299484751137fF,
REFCLK266.006042761571..266.006043306299fF and
BBPD_RESET_N331.446626191197..331.446626748922fF. Other active boundaries remain
fixed incrementally, wire R is zero, nonlinear charge is excluded and the
actual FOM/distributed-RC enclosure remains unqualified.

An isolated unmodified upstream8.3.685 build is also checked after preserving
a premature-configure failure. Its actual DCO before/after full-R comparison
still loses the same two global junction area/perimeter parameter records and
changes14818 C pairs beyond local print intervals at zero export threshold.
It is not adopted, and neither installed Magic nor golden Xyce is replaced.
This does not compare failure counts directly against the older thresholded
model: the extractor version, formulas and export thresholds differ.

An isolated original-C1FINE160 buffer-only candidate is prepared at
sky130/IntegerPLL_DCO_einvp_c1fine160_buf8_sky130.v with OpenLane configuration
openlane/IntegerPLL_DCO_EINVP_C1FINE160_BUF8. It changes only out_buf fromHD buf1
toHD buf8; all691 connections, other690 cell types, original160-load fine bank,
public ports and encoding are preserved. Both library functions are A; wrong
input and extra-cell-change controls reject. No return-fine bank is added.
The new nominal library load domain contains the certified diagnostic load,
while buf1's nominal domain does not. Actual functional overload is not proven.
The candidate has no layout/native analog qualification and is not adopted.

The C/R support inventory covers8297230 native contribution events and12390661
support endpoints, with1295670 unique conductor/box pairs. Every original
conductor has a retained R representative;2030879 endpoint observations contain
one directly, while10359782 require nonzero geometric padding. The largest
representative-point gap is43835nm (for COARSETHERMAL_CODE[23]). Proximity alone
does not assign a physical capacitor location or bound transient error.
Canonical R-component/alias membership, omitted intermediate coordinates and
actual resistor-segment support must be resolved before interpreting large
gaps or constructing a runtime model. Intrinsic-resistor C, local junction
allocation, supply-origin body connections and bulk impedance remain open.

The full100/250/300/400MHz nominal1.8V/15PVT scope and all release gates remain
required. Physical wholePLL passes are zero. Fresh eligible runtime models,
range/calibration/reset reachability, timing/interfaces, mode changes and
physical release qualification are still needed; no release is declared.


Progress049 records the distributed-RC geometry work under
build/timing400/release_001/distributed_RC_model_qualification_001/owner.json.
Its12h deadline includes preparation, tool builds, extraction and assessment;
the completed common-substrate C check is not restarted. All native CAD/analog
engines are terminal at this checkpoint. Runtime and release eligibility remain
false, and physical wholePLL passes remain zero.

The retained reduced-network audit binds all78613 R/MOS/port nodes to original
conductors with no ambiguous bindings or provenance-group name differences.
The100 most remote signal C supports all touch the expected independent GDS
conductor. The source investigation finds that extresist simplify off still
allows ResDoneWithNode to combine series/parallel/triangle networks. A single
exported resistor therefore cannot inherit just its last creation rectangle.
The rejected single-segment binding and its evidence are preserved separately.

An isolated opt-in OPENPLL_R_RETAIN_MESH switch skips that reduction stage,
retains normal native output and avoids geometry mode's node alignment. Its
switch-off actual-DCO regression preserves the reference R/MOS graph and
original pre-R C/devices. The enabled extraction retains164344 positive SPICE
resistors versus97616 in the default export, with original pre-R C/devices,
exported model/geometry parameters and public ports preserved. Its independent
terminal-connectivity audit binds137004 voltage nodes and34476 MOS/intrinsic-R
terminals to original conductors with no shorts or missing bindings. These
checks do not qualify electrical impedance or repair inherited junction charge.

Creation geometry is recovered for130708 rectangular wire segments, alongside
35578 native contact branches. The native166286 resistor records exceed the
SPICE164344 branches;779 native branches have identical printed endpoint names.
Alias, repeated-name, killed-node and omission handling still require explicit
reconciliation before the mesh can become a runtime model. Pointer identity
must be preserved during that audit; conductor identity alone cannot merge
voltage nodes across a finite resistance.

For304 matched routed signal conductors,192763 unique C support boxes intersect
native resistor spans, including180920 that lacked an old retained node point.
Of15901 remaining boxes,7688 intersect full creation-tile extensions beyond
resistor breakpoints;8213 remain outside recorded creation tiles. Another
1087006 original support boxes are outside this survey's routed-signal scope.
The former43.835um maximum-gap example lies in a165nm terminal tile extension.
This establishes geometry context, not endpoint attachment, C integration
weights, an open-end resistance bound or spatial convergence.

Evidence is in DCO_retained_R_mesh_default_controls_001,
DCO_retained_R_mesh_001, DCO_retained_R_mesh_conductor_audit_001,
DCO_retained_R_mesh_geometry_001, DCO_C_R_segment_support_inventory_001 and
DCO_C_R_terminal_tile_support_001. The installed extractor and golden Xyce are
unchanged. Native-export reconciliation, unrecorded terminal regions, layer
identity, local junction/intrinsic-resistor charge, supply/body impedance and
transient convergence remain open before fresh frequency qualification. Frozen
100/250/300/400MHz nominal1.8V/15PVT scope and all release gates are unchanged.


Progress050 completes the native-to-SPICE resistor export accounting using
DCO_R_export_alias_audit_002. Original equivalence aliases explain all1942
omitted native branches:1163 join distinct native pointers with different
original alias names, and779 join distinct pointers with the same printed
name. None is a self-loop of one native pointer. Their physical voltage
equivalence is not established, so this is accounting evidence, not approval
to collapse them in a distributed model.

The remaining164344 branch multiplicities match exactly. Their values reproduce
SPICE exactly under the pinned EFread.c expression
float32(0.5 +1000*atof(native_ohms)), followed by six-significant-digit output
in ohms. The0.5 term adds0.0005ohm before float/print rounding; it remained after
resistor storage changed from integer to floating point.123102 exported printed
values differ from their native printed inputs. The first comparison, which
allowed only print intervals, rejects; its script is retained and the revised
audit models the actual source semantics rather than increasing a tolerance.

The next runtime-model step must preserve native node-pointer identities and
capture device-terminal bindings, handle public and supply boundary points
explicitly, and retain native resistance values without that reader bias.
No native CAD or analog runs are added in this accounting phase, the original
12h distributed-RC check deadline is unchanged, runtime/release qualification
remain false, and physical wholePLL passes remain zero.


Progress051 materializes lossless native resistor primitives at
build/timing400/release_001/DCO_private_R_primitives_001. All166286 positive
native resistors and148346 distinct voltage vertices are preserved. Values
come from full-precision native resistance records, without the extflat reader's
0.0005ohm addition. Every native .res.ext branch/value is independently
reproduced under its float32/six-significant-digit print semantics; parallel
branch multiplicities are retained and printed aliases never merge vertices.

Private node allocation/merge events resolve lifetimes and all34476 device
terminals without ambiguous bindings. Unique physical geometry associates all
8620 devices(4309NFET,4309PFET_HVT,2poly resistors) with original model cards.
The original and retained device-ID exports preserve their respective complete
cards and C matrices; the retained export also preserves all R records. All
original global junction records are retained as metadata. Zero-wire-R device
conductor correspondence passes, and an intentional gate/drain swap rejects.
These checks do not qualify physical local junction-charge distribution.

The new native binding run preserves the prior R/MOS graph and original pre-R
C/devices. Its separate device-ID assessment initially fails because logging
does not cover the active hierarchical writer selected by lvs defaults. The
completed native resistance data is reused. After adding that writer hook,
original and retained device-ID exports pass from saved .ext/.res.ext files;
no full R extraction is repeated for a missing diagnostic. Preparation and
failed diagnostic evidence are retained. This phase adds one full R run and
five saved-file exports, within the existing12h owner/deadline.

The trace also recovers8997 one-breakpoint conductor tiles. In the existing
304-signal-conductor survey, these explain7912 of8213 previously outstanding
C support boxes. Four boxes have multiple private-node candidates and297 remain
uncovered. Other original conductors outside that survey still require mapping.
Geometric intersections are not capacitor weights or an AC resistance bound
for a terminal region.

The wire_R_elements_unqualified.spice file contains resistor primitives for
later assembly; device_connections.json retains the geometry-linked original
cards and private terminal identities. Public signal/supply boundary attachment,
local junction/intrinsic-resistor charge, all-conductor C layer/weight mapping,
spatial convergence and transient correlation remain open. No new model or
candidate is adopted, no native CAD/analog engine remains live at checkpoint051,
and physical wholePLL passes remain zero. Frozen nominal1.8V/15PVT four-mode
100/250/300/400MHz qualification and all release gates remain required.


Progress052 checks all166286 private R branches and148346 voltage nodes:
there are exactly2686 resistor-connected components, one per original conductor,
with no split conductors or cross-conductor R links. Actual GDS pin labels,
native port rectangles, drawing coverage, origin flags and incident materials
map all308 public pins to310 physical layer interfaces and328 native origin
vertices. Eighteen signal pins have two coincident M3 origin vertices; both
remain identified as interface candidates. M4/M5 rail origins are kept on
separate physical interfaces despite their coincident xy coordinates.

The two declared VPB/VNB pins are isolated vertices with no MOS attachment and
no incident R layer. Their layer is established by the native declared port and
independent GDS M3 pin geometry. They are preserved as declared interface stubs.
The4309PFET and4309NFET bulk terminals instead bind to the VPWR and VGND mesh,
respectively. The initial incident-R-only boundary audit rejects the isolated
pin case; that failure is preserved and the separate geometry case is checked.

DCO_private_R_public_boundary_audit_002 holds the geometry/component evidence.
DCO_physical_boundary_connections_001 emits328 zero-volt point connectors under
an explicit point-boundary representation. Each connector matches the checked
map; the310 physical interface IDs keep M4/M5 supply feeds separate. This does
not qualify uniform potential over a complete pin surface, external driver or
parent-PDN feed distribution, or the final308-pin macro adaptor. No interior
R vertices are merged by a logical alias in these primitives.

No native CAD/analog run is added in this phase; all engines are terminal at
checkpoint052. The original12h distributed-RC deadline is unchanged. Capacitor
material/plane identity and all-conductor weighting, remaining297 surveyed
signal support boxes and4 multiple-node cases, local junction/intrinsic-R
charge, and external feed/body impedance qualification remain open. Runtime
eligibility, adoption and release remain false, with zero physical wholePLL
passes and the frozen four-mode nominal1.8V/15PVT release scope unchanged.


Progress053 completes capacitor surface accounting at minimum, nominal and
maximum RC using the original RC-substrate context. All8,297,231/8,297,230/
8,297,288 respective contributions have aligned plane/material metadata;
reconstructed matrices match within explicit native arithmetic/print allowances.
Native capacitance and all8620 device cards remain identical to the installed
reference. Missing-contribution and displaced-surface-serial controls reject
corruption. These are accounting checks, not spatial or transient qualification.

DCO_zero_length_junction_source_audit_001 independently maps152 zero-length
source terminals to actual poly/diffusion gates in76 decap_3 GDS instances.
Only two have nonzero pre-R exported source area/perimeter. The exporter falls
back to the entire connected node junction area/perimeter when local attributes
are absent. Consequently the prior requirement to blindly restore those two
global records is not a physically justified model repair. Local diffusion
geometry and nonlinear charge must establish the correct allocation first.
No junction area has been changed or adopted. Three diagnostic checker failures
are preserved separately; their fixes required no native CAD/analog retries.

The original12h check deadline is unchanged. Spatial weights for all conductors,
junction and intrinsic-resistor charge, external supply/driver feeds, body
impedance and the308-pin runtime adaptor remain open. No native CAD or analog
engine remains active at checkpoint053. Runtime eligibility, release and adoption
remain false; physical wholePLL passes remain zero. Frozen nominal1.8V/15PVT
100/250/300/400MHz qualification and all release gates remain required.


Progress054 resolves the static decap junction-area discrepancy. Actual GDS
diffusion polygons on both sides of each of152 decap MOS devices match the
private source/drain boundary points. Existing local drain area/perimeter values
match those independent polygons exactly. Each missing source has an equal,
separate physical region. DCO_local_decap_junction_candidate_001 adds local
source-area/perimeter candidate metadata for all152 devices and preserves all
original cards, all other device parameters and every private connection.

Native integer area/perimeter balance now holds exactly for both supply nodes:
NFET explicit(9638976,500830)+missing(434720,24624)=(10073696,525454);
PFET explicit(31593136,1211866)+missing(687648,34352)=(32280784,1246218).
Area units are25nm2 and perimeter units5nm. The original pre-R global fallback
adds the entire node inventory on top of already explicit local junctions.
Dropping those global records without recovering the missing local sources
also fails conservation. Both legacy choices are rejected. The corrected
geometry candidate is the basis for subsequent junction-charge qualification;
no new runtime model has been adopted and no capacitor matrix has been changed.

This phase adds no native CAD/analog runs and retains the existing12h deadline.
Nonlinear junction charge and spatial integration, all-conductor capacitor
weighting, intrinsic resistor/body charge, external public driver/PDN feeds and
the308-pin runtime adaptor remain open. Runtime eligibility/release/adoption
remain false and physical wholePLL passes remain zero. The frozen nominal1.8V/
15PVT100/250/300/400MHz qualification and all release gates remain required.


Progress055 recovers exact plane/material metadata for the301 unresolved signal
C support boxes. Independent GDS net probes on the recorded metal layer pass
for every box. The four multiple-single-tile cases each select one tile on the
correct layer. All297 previously uncovered boxes lie on metal1 islands with
one private mesh vertex identified by incident viali and via1 branches. This
identifies candidate locations; it does not establish uniform island voltage,
capacitor weights, resistance discretization error or transient accuracy.

DCO_unresolved_C_surface_survey_001 and DCO_unresolved_C_layer_geometry_001
preserve the ordered trace/GDS evidence. DCO_layer_qualified_C_endpoint_inventory_001
scans all8,297,230 nominal contributions and12,390,661 endpoint occurrences.
It retains1,355,315 distinct conductor/plane/material/box entries, including
active, local interconnect, every metal layer and wells. Every recorded endpoint
conductor has a corresponding native private-R conductor after explicit
@SUBSTRATE-to-VGND normalization. Logical conductor coverage does not establish
physical placement or impedance. Implicit ground endpoints and intrinsic
resistor/body charge still require their physical distributed representation.

No native CAD/analog run is added; the original12h deadline remains unchanged.
Complete all-conductor physical geometry/weights, min/max endpoint coverage,
junction/nonlinear charge and integration error, external driver/PDN feeds and
the308-pin runtime adaptor remain open. Runtime eligibility/release/adoption
remain false; physical wholePLL passes remain zero. The frozen nominal1.8V/
15PVT100/250/300/400MHz qualification and all release gates remain required.


Progress056 establishes a bijection between all2686 native conductors and2686
independent GDS connectivity clusters. All26,168 transistor/resistor-terminal and
public-pin seeds match without missing/ambiguous probes or multiple clusters.
This topology registry does not merge any private resistor voltage vertices.

DCO_all_C_endpoint_GDS_identity_001 checks all1,355,315 distinct nominal
conductor/plane/material/box entries:1,283,682 conductor-layer entries and71,633
well entries pass endpoint/midpoint sampling with1nm boundary neighbourhoods.
This checks sampled identity, not continuous box coverage or voltage weights.
Min/max support sets differ slightly from nominal: min adds5 and omits8 boxes;
max adds10 and omits6. DCO_corner_extra_C_support_geometry_001 checks all15
extra diffusion boxes against their full GDS conductor area and correct well.
Thus every corner's recorded supports are covered by nominal sampled evidence
plus explicit extra-box geometry checks. Capacitance coefficients still differ
by corner and must receive their own conservative distributed representation.

DCO_all_junction_region_audit_001 maps all17,236 source/drain terminal records
of8618 MOS devices to10,386 independent physical diffusion regions. Every local
area/perimeter share matches; there are no missing/ambiguous terminal regions,
mismatched shares or unowned regions. Exact GDS totals are NFET1,032,241,950nm2/
9,803,860nm perimeter and PFET1,553,464,600nm2/13,098,620nm perimeter. This closes
static local junction geometry after the152 decap-source repairs; nonlinear
charge, body impedance and distributed integration accuracy remain unqualified.

DCO_exact_junction_device_primitives_001 emits8620 device primitives on private
mesh vertices with34,472 exact MOS junction parameter values. It removes1138
rounded parameter values from the previous local candidate; maximum relative
print rounding was0.0000539811066127, approximately54ppm. Original cards remain
unchanged in metadata; all other parameters and every private terminal connection
are checked on readback. This is a component for model assembly, not an eligible
runtime deck. No distributed capacitor model or external feed has been adopted.

This phase adds no native CAD/analog runs. All check processes are terminal at
checkpoint056 and the original12h deadline remains unchanged. Distributed C
voltage weights, full native-matrix conservation/passivity, whole-support and
spatial integration error, implicit-ground and nonlinear/intrinsic-resistor
charge, min/max private-R values, external driver/PDN feeds and the308-pin adaptor
remain open. Runtime/release/adoption remain false, physical wholePLL passes
remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz qualification and all
release gates remain required.


Progress057 resolves creation-to-private-node orientation for all130,708 wire
branches from retained allocation/merge histories. ResSetPathRes can reverse
endpoint slots, so creation order cannot be copied blindly. All14,913 reused
allocation addresses are considered with every possible lifetime;8617 branches
require merge ancestry. Every branch has one admissible final endpoint pairing.
No closest-coordinate inference or printed-name voltage merge is used, and no
native extraction is repeated. The first CPU checker is stopped to replace a
per-branch full-node scan with direct lookups; its script/interruption receipt
is retained separately and the completed v2 is pinned.

DCO_native_tile_voltage_basis_001 builds55,663 continuous piecewise-linear tile
voltage bases from those branches. There are no axis gaps/overlaps or voltage
discontinuities between adjacent segments. Exact rational nonnegative axis
integration preserves partition of unity; nonuniform-chain affine controls,
open-end clamp integrals and a reversed-endpoint rejection control pass. Native
geometry includes140 branches whose breakpoints extend outside their creation
tile and21,200 tiles with open-end extensions. Their physical approximation
error remains unqualified; no capacitor contribution weights are emitted.

DCO_C_charge_kernel_metadata_audit_001 confirms that existing support boxes
identify candidate geometry but do not retain every local charge integration
region. The309,861 nominal tile_perimeter entries use whole tile bounds, losing
the contributing local edge interval. The3,460,669 edge_fringe entries retain
whole target tile bounds, while the native computation first clips the target
to a local fringe halo and uses a distance-dependent atan kernel with recursive
shield corrections. An actual traced target-well example rejects uniform charge
over the complete target box because it spills charge outside the native
longitudinal integration interval. Earlier matrix-accounting and sampled GDS
identity evidence remains valid; it never qualified local charge weights.

Next instrumentation must preserve local perimeter edges, overlap patches,
clipped fringe/sidewall kernels, shield exclusions and roundoff residuals aligned
with contribution/surface serials. Use a new isolated Magic source/prefix to
preserve currently pinned sources. Then integrate the kernels on the private
voltage bases and check full native matrix conservation, passivity and physical
error before runtime use. This phase adds no native CAD/analog runs; all checks
are terminal and the original12h deadline is unchanged. Runtime/release/adoption
remain false, physical wholePLL passes remain zero, and frozen nominal1.8V/15PVT
100/250/300/400MHz qualification and all release gates remain required.


Progress058 creates an isolated Magic source/prefix for local charge kernels;
previous pinned sources are unchanged. The new optional kernel stream preserves
local area/edge supports, clipped fringe rectangles, near/far distances and atan
multipliers, overlap and recursive shield patches, sidewall paired edge spans,
physical coefficient/rule values and links to every existing contribution serial.
Existing contribution and surface formats and native capacitance formulas remain
unchanged. A fresh parallel build exposes Magic's generated database-header
race; its failed logs are preserved. Build002 generates the header serially
before parallel compilation and completes without replacing the installed tool.

All12 small case/corner controls preserve native C/device/feedback output and
reconstruct local kernel integrals. Wrong kernel ID, whole-tile perimeter and
whole-target fringe substitutions are rejected in every case. The bounded-memory
reader with deadline checks reproduces all12 saved native outputs exactly and
rejects an expired deadline without repeating extraction.

Actual nominal DCO extraction passes8,297,230 contribution checks on7,421,041
local kernels, including1,626,941 candidates that emit no nonzero contribution.
There are no split rectangles. Native capacitance,8620 device cards and feedback
match the original RC-context reference; native matrix reconstruction also
passes. Accumulator/zero-clamp residuals are retained separately from physical
local integrals and do not yet constitute a qualified transient error bound.
The same controller continues minimum/maximum RC under the original12h deadline.
Its active handle is DCO_C_kernel_trace_controls_001/status.json; preserve
completed native outputs if any later assessor fails.

local_C_energy_integration.py integrates voltage products with exact rational
second moments and a positive Gram decomposition for positive uniform patches.
Controls check analytic mass matrices, zero-wire-R uniform voltage conservation,
orthogonal affine fields and refinement invariance; squaring an average voltage
is rejected by a nonuniform-field counterexample. This is a local integration
component, not a full signed DCO capacitance matrix or global passivity proof.

DCO_native_mesh_node_plane_inference_001 resolves all35,578 contact endpoint
plane pairs and8997 single-breakpoint tile planes in three propagation passes.
All148,346 private vertices have native plane associations. Multiple-plane
zero-R interfaces, including312 native locali/well vertices, remain explicit;
this topology inference is not physical contact-sheet impedance qualification.

A parallel check now tests every complete nominal C box/edge/point against its
actual GDS conductor and material/well mask, strengthening earlier samples.
It uses1nm conductor expansion and a1nm corridor around closed edges/points.
The verified live handle is DCO_complete_C_support_GDS_geometry_001/status.json.
Both follow-ups retain the existing12h deadline; no analog engine is running.
Min/max kernel assessment and complete-support geometry are pending at058.
Full C field assignment, signed global passivity, implicit-ground/nonlinear
charge and RC error, min/max R values, external feeds and the308-pin adaptor
remain open. Runtime/release/adoption remain false, physical wholePLL passes
remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz qualification and all
release gates remain required.


Progress059 completes all three actual-DCO local charge-kernel checks. Native
C matrices,8620 devices and feedback match the reference at min/nom/max; every
contribution has aligned local kernels and reconstructed physical integrals.
The complete nominal GDS box/edge/point check passes all1,355,315 entries.
Neither result by itself qualifies capacitor voltage weights or runtime timing.

A separately isolated R-domain tracer captures every pre-merge tile breakpoint
and the actual working plane of each contact copy. Native resistance/device
comparisons pass. The complete lifetime index resolves65,162 anchored domains:
55,663 multi-voltage wire domains and9499 constant domains. Of the latter,502
had multiple coincident breakpoints and were absent from the old segment/single-
breakpoint inventory. No domain or contact working plane is missing. A premature
build invocation is stopped by its missing-preparation-receipt guard before any
compiler/native launch; its failure is preserved and source preparation is
confirmed terminal before the actual build. No native extraction is retried.

DCO_complete_domain_model_primitives_001 rebuilds166,286 positive native wire
resistors,8620 devices with the exact local junction parameters, and all65,162
voltage fields in a consistent new _rdomain_ namespace. Wire endpoints are
bound by exact tile breakpoint lifetimes. Native printed R multiplicities and
values reproduce exactly; no older private node identities are mixed. All
148,346 nodes form exactly2686 R-connected components, one per original
conductor, without split or cross-conductor components.

Correction to058's unqualified plane inference: all480 well-tap contacts have
three copies on well, active and local-interconnect planes, with three distinct
voltage nodes and two finite contact resistors. There are160 psubdiffcont and
320 nsubdiffcont taps. The earlier two-plane inference is rejected for runtime
use; its312 combined locali/well annotations were inference artifacts, not
established zero-R interfaces. Direct records now give one working plane for
each private node; the two isolated public stubs use their checked port-layer
evidence. All35,578 contact edges reproduce the direct adjacent-copy topology.
DCO_direct_native_planes_and_boundaries_001 rebases328 point connectors for308
logical ports/310 layer interfaces using original source BPs and native origin
flags. M4/M5 supply interfaces remain separate; external feeds and uniform
whole-pin potential remain unqualified.

DCO_voltage_domain_coverage_002 checks every complete nominal C support against
typed anchored voltage domains using exact5nm-grid rectangle/interval unions.
Every support passes and typed domain interiors are disjoint. Its1370 independent
KLayout controls match the prior1nm expansion/corridor definition across all15
material types. All5 minimum and10 maximum corner-only supports also pass. The
slower duplicate Boolean assessor is stopped only after the equivalent full
check completes; partial results and supersession evidence are preserved. No
native result is repeated and the original12h deadline is unchanged.

All checks are terminal at059. The next stage assembles local area/perimeter/
overlap/fringe/sidewall energy matrices on the complete family, retaining signed
shield corrections and roundoff residuals. Full native zero-R C conservation,
signed global passivity, spatial/open-end/transverse error, nonlinear/implicit-
ground/intrinsic-resistor charge, min/max R values, external feeds and the308-pin
runtime adaptor remain open. Runtime/release/adoption remain false, physical
wholePLL passes remain zero, and frozen nominal1.8V/15PVT100/250/300/400MHz
qualification and all release gates remain required.


2026-10-20: qualification_progress_060.json records the first owned local C
operator compilation on the complete native resistance-domain family.
DCO_local_C_operators_nom_001 contains15,646,598 signed operators from all
8,297,230 nonzero nominal contributions and7,421,041 native kernels. Every
operator integral matches the separately recorded physical kernel total; all
9511 field entries (including the explicit substrate reference) are accounted
for. Every physical field maps to the complete typed domain atlas. Area,
perimeter, overlap, sidewall, clipped arctan fringe and signed shield corrections
remain separate. Native accumulator/clamp residuals have their own ledger.
The native convention omitting explicit intra-conductor pair coupling is kept;
this result is numerical extraction accounting, not absolute silicon accuracy.

local_C_operator_compilation_001 audits all12 saved native control cases and
pins the nominal compiler inputs to the preceding native extraction receipt.
The first small-control implementation failed on an unlocated zero-clamp
plane=-1; its partial outputs and source are retained. Version2 gives that
adjustment no spatial operator and records its arithmetic-only conductor
ledger. All12 control cases then pass. No native extraction was repeated.

local_C_field_integral_controls_001 passes exact rational area comparisons,
an exact line mass comparison,21 independent adaptive fringe-moment checks,
and8 signed fringe-field energy/charge checks spanning all four directions.
Adjacent independent domain partition controls pass; wrong inward-side and
uncovered-area controls are rejected. These checks integrate voltage products,
including their variance; they do not square an averaged field.

The nominal full sparse matrix assembler and the min/max saved-trace compilers
are live at060; process identities and observed statuses are retained in that
snapshot. The assembler uses one-sided physical edge ownership and actual
source-edge projections, with no nearest-node attachment or logical-alias
voltage collapse. The substrate reference is explicit and does not merge the
interior well voltages. check_assembled_local_C_matrix.py is prepared to check
zero-wire-R collapse and diagnose the signed global spectrum after assembly;
it has not yet qualified a DCO matrix. Full passivity, spatial/numerical error,
corner R values, external feeds, runtime integration and all frozen release
gates remain open. No runtime model is adopted; physical wholePLL passes remain
zero. The original12h owner/deadline is unchanged and release remains false.


2026-10-20: qualification_progress_061.json records the first complete nominal
C matrix and its rejection. All three retained native RC operator streams pass
accounting. DCO_domain_R_corners_002 reproduces every one of166,286 nominal
native R values exactly from float32 sheet/geometry or contact-array formulas,
and emits positive ordered min/nom/max values on the same private topology.
DCO_contact_cut_count_geometry_001 independently matches all35,578 finite
contact branches to actual GDS cuts. DCO_poly_resistor_charge_accounting_001
resolves the two generic-poly intermediate records: their native fields are
R=50,C=0, with no nonzero pair capacitors. The original two-terminal PDK model
contains one resistor and no charge element, and both exact devices remain.
This is native/PDK bookkeeping, not an absolute silicon charge claim.

signed_C_Xyce_controls_002 checks the signed-branch realization of a passive
field mass matrix against its independent analytic PWL response. Golden Xyce
accepts the negative individual capacitor required by that matrix; errors are
below1e-5V. The two configured max-step variants take identical adaptive samples,
so this proves representation compatibility, not independent time-step
convergence or actual-DCO accuracy. A CSV case-name reader failure reuses the
completed baseline; it does not repeat an identical native check.

DCO_local_C_matrix_nom_001 integrates15,646,598 operators into a148,347-vertex
matrix with9,371,163 nonzeros. Its maximum relative charge-row residual is
7.2606e-12, and DCO_local_C_matrix_nom_checks_001 passes zero-wire-R native
physical-total recovery. It FAILS signed passivity:101 diagonal entries are
negative and the minimum normalized eigenvalue is-0.3333764003. The matrix is
explicitly rejected for runtime adoption. DCO_corner_matrix_stop_after_nominal_
failure_001 preserves and stops both CPU corner assemblies at9,220,000 operators;
no DCO transient is launched with the rejected matrix.

DCO_negative_C_diagonal_diagnosis_001 reconstructs the worst private metal2
VPWR diagonal exactly:-11.74349141 native capacitance units. Ground-shield
subtractions exceed the local positive ground and coupling contributions.
DCO_negative_C_kernel_inspection_002 examines the ten largest negative events:
eight are fringe-halo and two blocked-fringe kernels; six explicitly skip pair
updates because both surfaces belong to the same ideal conductor. Those pairs
can carry different local voltages after finite wire resistance is retained.
Recovering their latent overlap/fringe/sidewall energy is a concrete candidate
repair; its sufficiency is not yet established. No eigenvalue clamp, arbitrary
capacitor relocation, or runtime adoption is performed.

qualification_progress_062.json records the isolated owner-trace followup.
magic_C_owner_source_001 reproduces the frozen tracer before adding optional
pair ownership records and otherwise skipped self-sidewall geometry/rules.
Self-sidewall diagnostics return before the native coupling hash is touched.
The isolated build and all12 native controls pass exact C/device/feedback
comparisons. DCO_C_owner_trace_001 also preserves the actual nominal DCO native
matrix, all device cards and feedback. The installed extractor and golden Xyce
are unchanged.

DCO_self_C_extension_controls_002 verifies all12 cases with contact-plane
normalization from the exact retained native SURFACE observations. It preserves
all83,838 original energy operators exactly and adds10,050 self-pair operators.
These added terms vanish when each original conductor has uniform voltage.
The decoder verifies78 actual contact normalizations, including distinct poly/
locali and locali/metal1 residues. Earlier CPU reader failures and partial
outputs are preserved; the contact decoder correction needs no native rerun.

compile_local_C_operators_v5.py is running on the full nominal owner trace in
DCO_local_C_operators_nom_self_002 at062. After it finishes,
separate_DCO_self_C_increment.py must prove exact identity of every original
operator before assemble_DCO_self_C_increment.py may reuse the original
numerical sum and add only missing terms. The corrected matrix then requires a
fresh zero-R collapse and signed passivity check before diagnostic SPICE export.
The first matrix remains rejected. Full corrected min/max, numerical/spatial
and integration qualification and all frozen nominal1.8V/15PVT four-mode
release gates remain open. Physical wholePLL passes remain zero. The original
12h owner/deadline is unchanged; release/adoption remain false.

qualification_progress_063.json records completed restored self-pair C matrices.
All three corners reproduce the zero-wire-R physical operator totals. Nominal
and minimum C pass the full numerical signed-passivity check. Maximum C fails
with two normalized negative modes (-0.00032808623 and -0.00013750135), despite
having no negative diagonal. DCO_max_C_negative_mode_diagnosis_001 preserves
both modes and confirms negative energy at max C for the same voltages that
have positive energy at min/nom C. The max matrix remains rejected; no clamp
or coefficient replacement is used. trace_DCO_max_C_mode_energy.py is tracing
the failed mode back to every owned operator under the original deadline.

All 15,646,598 original nominal operators are preserved exactly and 2,642,914
latent self-pair operators are added. Of 2,723,364 new nominal support boxes,
2,656,437 inherit previous complete GDS coverage; direct independent checks
pass for all remaining 66,927. This proves geometric support, not transient
accuracy or full RC-corner qualification.

DCO_domain_candidate_nom_001 exports the checked nominal matrix with all
166,286 finite resistors, 8,620 native devices and explicit point feeds. Its
ideal-feed wrapper is diagnostic. The initial full native point omitted an
explicit linear solver and entered the MPI default iterative/hypergraph path.
Its verified process was stopped with a configuration receipt; the changed
run explicitly selects upstream KLU with identical circuit and original 12h
owner. The KLU point is live at the063 observation, still at initial DC bias.
No oscillator frequency has yet been qualified.

split_DC_initialization_controls_001 passes all three native controls: removing
only constant capacitors preserves DC bias exactly; restoring their saved
initial charge with IC/UIC reproduces linear/BSIM waveforms within0.15uV.
The completed native outputs use STD .prn with explicit -o on this build;
assess_split_DC_initialization.py fixes the reader without repeating any native
case. run_DCO_C_free_DC.py now tests the actual DCO DC equations with all R,
nonlinear devices and feeds unchanged, preserving the active full-C baseline.
Saved-bias equivalence to the full DCO and actual startup remain unqualified.
All frozen release gates, nominal1.8V/15PVT scope, original deadline and zero
physical wholePLL passes remain unchanged; release/adoption remain false.

qualification_progress_064.json proves exact canonical support geometry identity
for all2,642,914 added self-C operators at min/nom/max. Their conductor, plane,
material, area/edge/fringe supports and directions have identical ordered SHA256
46abbb7a84b0e48e6280e7b9ecb8911974d9b8075389c77edd7163ee6a6e9d59.
The nominal prior-union/direct-GDS proof therefore covers the added supports at
all three corners. Coefficients and density multipliers were excluded only
from this geometric comparison; no electrical result transfers across corners.
Max C still has two negative-energy modes and remains rejected.

assess_DCO_domain_point_STD.py is prepared to read the completed golden native
STD output and original receipt without repeating a native case. It requires a
terminal successful simulator receipt, checks the stored waveform digest and
measures actual output edges. It does not qualify convergence, frequency models
or parent loading. At064 the full-C KLU point and C-free DC-only diagnostic are
both verified live; the owned max-C energy trace is also live. Their shared
original12h deadline is unchanged. All release gates and physical wholePLL
passes remain open/zero; release and adoption remain false.

DCO_DC_constraint_topology_001 independently unions all166,286 finite-R branches
and confirms exactly one connected component for each of2,686 original
conductors. All328 private point-constraint endpoints are unique; the ideal
constraint graph has no cycle. There is no purely resistive component lacking
both devices and ports, and no gate-only component without a conducting-device
terminal or port. This excludes those structural hypotheses for the slow DC
run; it does not establish nonlinear DC convergence or change the circuit.
The existing same-owner native runs and max-C energy trace remain active.

qualification_progress_065.json records the completed physical-R DC bias and
full max-C energy reconstruction. DCO_domain_nom_tt27_c0_f247_C_free_DC_001
passes upstream Xyce with all166,286 physical wire resistors and8,620 native
devices unchanged, only constant CFIELD capacitors open in DC. It saves all
174,508 voltage nodes. Native elapsed time is1,163.45s;53 linear solves consume
1,127.86s. No nonlinear convergence or linear-solve failure occurs. This is an
exact DC equation-preserving preparation, not dynamic-model qualification.

DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001 is a separate conditioning
comparison: original conductor components become ideal wires, all8,620 device
cards retain their models/parameters, and no dynamic result is claimed. Its DC
run passes in17.9582s with28,847 unknowns. The strong speed difference motivates
explicit initial-guess and stock-solver comparisons. Seeded physical-R DC runs
with upstream KLU and stock BASKER are live at065; the BASKER environment requests
8 OpenMP threads, but parallel speedup is not established and an intermediate
singular-pivot message is retained. No engine source is modified.

run_DCO_domain_point_v4.py verifies complete saved voltage coverage:148,346
physical nodes,25,854 BSIM internal nodes and308 public nodes. Small independent
native controls already verify full-C IC/UIC charge initialization from C-free
DC. The new80ns full-C deck preserves the actual candidate, ports, tolerances,
KLU solver and stimulus; only saved-IC/UIC initialization and output precision
change. The prior live full-C KLU DC solve is stopped only after preparation,
PID/argv/process-group verification and a reason receipt in
DCO_domain_nom_tt27_c0_f247_80ns_klu_001/stopped_for_saved_IC_initialization.json.
Its exit-15 is an intentional initialization change, not a physical test result.
DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001 is the one new full-C instance under
the same original deadline; no two large full-C instances overlap.

DCO_max_C_mode_energy_trace_001 reconstructs the negative mode from all18,290,414
unchanged owned operators: matrix energy-151.2715403562 versus reconstructed
-151.2715403126 in native capacitance times voltage-squared units. Ground terms
sum negative and pair terms only partially compensate. The largest negative
terms are retained with exact event IDs, fields and supports. Their underlying
max-C native kernels are being inspected in DCO_max_C_mode_kernel_inspection_001.
No eigenvalue clamp, coefficient replacement or max-C model adoption occurs.
All release gates, four modes, nominal1.8V/15PVT scope and original12h deadline
remain unchanged; physical wholePLL passes remain zero and release stays false.

qualification_progress_066.json records the substrate-output convention
experiment at all three RC corners. ExtBasic.c explicitly writes zero C for the
native global substrate node; the prior finite-R operator model retained its
internal G accumulator against a separate explicit reference. The experiment
omits all1,113,704 original-substrate G operators, positive and negative, while
retaining every explicit inter/intra-conductor pair operator. It does not clamp
eigenvalues or selectively remove negative coefficients.

DCO_local_C_matrix_{min,nom,max}_no_substrate_G_001 and their separate checks all
pass charge conservation, unchanged zero-R capacitance and numerical signed
passivity. The maximum corner's two former negative modes disappear; its first
three normalized eigenvalues are approximately0,0.00420188,0.00447171. Minimum
and nominal also pass. This is a candidate modeling-convention correction;
finite-R return geometry, spatial/dynamic uncertainty and actual PLL behavior
remain unqualified. The original raw-G max matrix remains rejected and all
revised model adoption/release flags remain false.

DCO_physical_C_ledger_native_output_001 independently compares each physical
operator ledger with the final native .ext capacitances, including substrate
coupling relocation. All three corners pass the retained native print and
arithmetic allowances. Independent missing-pair controls fail as expected;
there are no final output-zero-clamp events in these DCO traces. The20 largest
negative ground terms inspect as15 BLOCKED_FRINGE and5 FRINGE_HALO kernels.

The seeded physical-R KLU DC run passes in866.103s, versus1,163.45s without the
seed; their174,508 saved voltages differ by at most2uV at native SAVE precision.
The same-seed BASKER comparison is stopped after1,565.17s because it has already
exceeded completed KLU elapsed time. A PID/argv/process-stat and exact circuit/
initial-guess comparison receipt is retained; no physical failure is inferred.

DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001 runs the unchanged retained
native35051 capacitor statements and device deck as an ideal-wire diagnostic.
It reaches transient calculation and provides a reference waveform, never a
finite-R release result. The full-domain saved-IC transient also reaches
transient calculation. Both remain under the original12h owner at066; no
frequency range or calibration is yet qualified. All four release modes,
nominal1.8V/15PVT scope and remaining gates are unchanged; physical wholePLL
passes remain zero and release stays false.

qualification_progress_067.json records the corrected nominal diagnostic deck
DCO_domain_candidate_nom_substrate_output_001, exported from the checked
substrate-G output-convention matrix. It preserves all native nonlinear cards,
finite-R branches, physical ports and explicit pair capacitance, with the
native-discarded original-substrate G accumulator omitted. It remains an
unadopted candidate with finite-R return and dynamic-error qualification open.

The exact golden container build inventory confirms Release/-O3, KLU/BASKER/
KLU2 support, no SuperLU/MUMPS/ShyLU-BASKER, and no Kokkos OpenMP. The engine and
libraries are unchanged. Bounded AztecOO comparisons retain their actual failed
results: singleton filtering crashes in EpetraExt::LinearProblem_SolverMap;
factory ILUT without that filter fails in its U triangular solve; legacy
RILUK(k=1) reaches the180s performance limit without the requested1e-12 linear
residual. Inputs, decoded crash evidence and changed configurations are retained;
no numerical or physical pass is inferred and no identical native retry occurs.

DCO_fast_internal_R_node_analysis_001 measures61527 nonterminal degree1/2 R
vertices while retaining all34413 device/interface/reference vertices. Its
positive-inverse RC comparison bound peaks at4.958766ps;20481 candidate vertices
meet a1fs cutoff and51198 meet10fs. These are candidate-state comparison bounds,
not a qualified oscillator-frequency error. No state, resistor or capacitor is
removed. Any passive DC-exact condensation requires explicit dynamic-error and
native validation before adoption.

qualification_progress_068.json also records the final180s iterative comparison
using the stock MPI AMD ordering/default RILUK fill2 and a300-vector GMRES
subspace. It remains inconclusive at1e-12 tolerance; no iterative configuration
is adopted. The original full-domain saved-IC and native ideal-wire reference
transients remain verified live within the same original12h owner. Their partial
waveforms are not release frequency evidence. All four modes, nominal1.8V/15PVT
scope and six release gates remain unchanged; physical wholePLL passes remain
zero and release/adoption remain false.

qualification_progress_069.json records an isolated passive path-condensation
prototype, not a selected runtime model. passive_RC_condensation.py keeps every
device terminal and physical point port. It reconstructs only nonterminal R
paths of degree1/2 by their DC harmonic voltage, adds exact positive series
resistances, and projects the complete C energy as T-transpose*C*T. It preserves
within-field variance and accounts for every original R branch.

passive_RC_condensation_controls_002 passes independent analytic series-RC,
parallel-R/series-C and uniform distributed consistent-mass RC-line controls.
The line's DC resistance and first capacitance moment match closed-form values;
its complex port admittance respects the predicted dynamic error envelope over
61 frequencies. Opposite terminal voltages retain nonzero field energy. Device/
interface and unsupported branch-vertex elimination guards are tested. The
initial control failed on low-frequency Schur-subtraction roundoff (absolute
4.17e-20S below eps*G); its result is preserved and the reference allowance is
scaled to conductance. The implementation did not change for that correction.

DCO_passive_path_condensation_nom_1fs_001 retains127866 of148347 voltage vertices,
removing20481 internal candidates while preserving all34413 protected vertices.
Its recomputed internal RC comparison bound is0.888187fs. It has145764 positive
R branches and4895239 scalar C branches; the maximum DC Schur difference is
1.98e-13 relative, harmonic residual1.76e-16, and zero-wire-R C changes by at most
5.82e-9 native capacitance units. Separate numerical passivity and native zero-R
conservation checks pass. No nonlinear card, active native case or final design
is changed. A port-admittance bound alone does not qualify oscillator frequency,
waveform or physical return error; those checks remain required before adoption.

The original full-domain saved-IC and native ideal-wire transients remain live
under the unchanged original12h deadline. All four modes, nominal1.8V/15PVT
scope and six release gates remain unchanged; physical wholePLL passes remain
zero and all prototype release/adoption flags remain false.

2026-10-20: qualification_progress_070.json records passing native exact-ground
controls and an independent full DCO boundary/initial-condition audit. All308
macro ports,296 external zero-voltage substitutions and174212 retained initial
voltages are checked; removed initial voltages are exactly zero. The physical
macro R/C/device source and private point connectors remain byte-identical.
The full-R saved-IC run had only its time-zero sample and was stopped with its
PID/argv receipt before the exact-coordinate case started, under the unchanged
original12h deadline. Xyce reports174551 unknowns and starts transient analysis;
the ideal-wire reference remains live separately. No physical approximation or
frequency qualification is claimed. Full-DCO performance improvement remains
unproven, physical wholePLL passes remain zero, and all release/adoption flags
remain false.

2026-10-20: qualification_progress_071.json records preparation of the corrected
nominal substrate-output-C full-R exact-ground diagnostic. A streaming comparison
checks all non-capacitor macro statements for exact token identity. Only the
macro include path changes in the prepared testbench; saved DC bias, physical
resistors/devices, sources, timing settings and observations remain unchanged.
No new native process is launched and the original12h deadline is retained.
The corrected5492690-capacitor model remains unadopted pending physical-return,
dynamic and frequency/convergence qualification; all release gates remain open.

2026-10-20: qualification_progress_072.json records stock KLU symbolic analysis
of passive R/C patterns. Grounding the reference does not reduce estimated
factorization work; the isolated20481-state prototype reduces the grounded
estimate by about22%. Nonlinear Jacobians and point-source MNA rows are omitted,
so these results do not predict full native runtime. An isolated stock serial
Trilinos/Xyce build is live to evaluate the upstream serial-only KLU factor-reuse
option without source patches. Its prefix is separate; installed golden tools,
physical circuits and existing native jobs remain unchanged. The original12h
deadline is retained. Build/equivalence/reuse checks are pending and all six
release gates remain open.

2026-10-20: stock_serial_factor_reuse_controls_001 is queued against the live,
identified stock_serial_Xyce_001 build. The checker will compare serial KLU
repivot modes1/0 to the retained golden finite-R/signed-C/BSIM waveform, supply
current and crossings. It inherits the same original deadline, uses shared
native admission and stops on build failure or loss without retry. It cannot
replace the active DCO run or qualify full-DCO speed/frequency. Control results
remain pending build completion; no new simulator or physical model is adopted.

2026-10-20: the stock-serial corrected-C full-R handoff is now queued behind
passing native serial controls. It preserves any positive-time progress in the
prior full-R run; otherwise it requires a prepared pinned deck and process stop
receipt before starting one replacement instance. It retains the full physical
R/device model, saved bias,80ns duration,10ps step and original deadline. C
convention and stock solver both change, so no isolated speed attribution is
claimed. All physical frequency/convergence and release gates remain open.

2026-10-20: qualification_progress_073.json records the first full-R native
sample at10ps after about32min, plus passing stock serial dependency build and
installation. The old waiting handoff is superseded without interrupting either
native run. Its replacement records at least120s of throughput and preserves
measurement-window progress or a projected finish within twice the remaining
budget; otherwise it can replace an impractically slow run after serial controls
pass, retaining the partial waveform and stop receipt. The projection is a
scheduling diagnostic, not a runtime guarantee. The original deadline, full-R
device model and all frozen qualification requirements remain unchanged.

2026-10-20: qualification_progress_074.json records passing unmodified stock
serial Xyce7.10 build/install/version and both native KLU modes. Sampled voltage,
supply current and rising crossings match the retained golden control exactly
at printed precision. The handoff observes439.98s without advancement beyond
10ps, preserves the old partial waveform/stop receipt, and starts the corrected-C
full-R serial point with KLU_REPIVOT=0 after the prior instance exits. The native
ideal-wire reference continues separately. The original deadline and physical
R/device content are retained. No full-DCO speed, frequency, model-adoption or
release qualification is claimed; all six release gates remain open.

2026-10-20: qualification_progress_075.json records a degree-unrestricted
nonterminal RC analysis using actual nominal native-formula R values. Bounded
slow-anchor selection converges in30 iterations to44252 candidate internal
vertices at a numerical comparison bound0.999595fs. Direct device/point-file
membership audit keeps all34413 protected vertices. The earlier one-anchor
selection is preserved as iteration-cap inconclusive. No projection or active
model change is made; matrix fill, runtime benefit and oscillator error remain
unqualified. Both existing native runs continue under the original deadline.

2026-10-20: qualification_progress_076.json records the general44252-state
projection's passing rational DC, signed-energy, native zero-R capacitance and
numerical passivity checks. Despite fewer states, C nonzeros double and the
stock passive-block symbolic estimate increases work48.87% and factor fill29.69%.
The prototype is therefore rejected as a performance fallback, without a native
launch or model adoption. Actual runtime and clock error are unqualified. Both
existing native runs and the original deadline remain unchanged.

2026-10-20: qualification_progress_077.json records completed native ideal-wire
80ns data: exit0,59736 samples,98 measured periods and1647.878744MHz mean. The
independent waveform audit finds1570.33ppm spread across10ns window means and
about159ppm change between the last two windows. Settled calibration, physical
finite-R range and noise jitter are not qualified. A bounded25ns diagnostic with
tighter tolerances and0.5ps maximum step is live for a matched15..25ns numerical
comparison; it does not replace the80ns range gate or separate convergence
checks. The full-R serial case remains live under the same original deadline.

2026-10-20: qualification_progress_078–079.json records the separate stock OpenMP/
METIS/ShyLU build and queued one/eight-thread native controls. The earlier classic
BASKER adapter is a different backend. The first configure failure identifies a
missing global OpenMP flag; the revised build reuses completed dependencies and
the failed configure tree with correct global/Tpetra settings, retaining all
original logs. A literal full-order ROM is rejected for dense-array RAM cost.

The tighter0.5ps ideal-wire diagnostic fails at reset5ns following1.464e-22s and
2.928e-22s rounding-size steps, without producing a frequency result. Independent
analytic RC controls validate a0.47ps grid, avoiding the tiny step and matching
within21nV. The new25ns case changes only that maximum-step field; the physical
model, stimulus, tight tolerances and original deadline are unchanged. It and the
unreduced serial full-R case remain live. DCO breakpoint recovery, numerical
accuracy, parallel speed and all six release gates remain unqualified.

2026-10-20: qualification_progress_080.json retains an immutable live prefix
showing the revised numerical diagnostic past5.05ns, beyond its earlier reset
failure. Full completion and frequency convergence remain unproved. A guarded
threaded-solver handoff is queued after native controls, requiring byte identity
of the physical deck except solver options and bounded prior throughput. It
keeps the corrected C convention, full R/device content, bias, reset,80ns duration,
10ps step and original deadline. Both active native runs remain unchanged.

2026-10-20: qualification_progress_085.json records the original12-hour campaign
ending timeout/inconclusive. Both remaining native engines, their owners and
the full-window comparison helper are confirmed stopped. The threaded full-R
point reached10.33314ps of80ns; the tighter ideal-wire point reached8.70301ns of25ns.
The matched startup-cycle comparison was independently verified at-5.07510ppm,
but does not qualify settled calibration, independent one-at-a-time numerical
convergence or finite-R frequency behavior. Terminal waveforms/log hashes and
unchanged release requirements are retained in campaign_deadline_001/assessment.json.
No budget reset, identical retry, model adoption or release occurred. All six
release gates remain open and qualified physical whole-PLL passes remain zero.
