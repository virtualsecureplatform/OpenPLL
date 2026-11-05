# Extracted antenna diode compatibility

The strength-controlled DCO contains six `sky130_fd_pr__diode_pw2nd_05v5`
instances on coarse control nets. Its unmodified PDK wrapper instantiates D0
with a level-3 diode model. The current Xyce standard diode registers levels
1 and 2, so the extracted circuit fails before any KLS factorization. This is
separate from the intermittent solver crash.

Do not divide the extracted `area=4.347e11` and `perim=2.64e6` blindly. The
Magic SKY130 technology explicitly specifies `a=area*1E12 p=perim*1E6` for
these diodes, and comments that the model requires unusual scaling. Both the
wrapper and the model must be interpreted together. The PDK files are retained
unchanged by the diagnostic below.

Run a small DC/AC comparison before a full DCO simulation:

```sh
python3 scripts/sky130_diode_probe.py \
  --pdk /absolute/path/to/sky130A \
  --xyce /absolute/path/to/Xyce \
  --ngspice /absolute/path/to/ngspice \
  --corner tt --temperature-c 27 --bias-v 1.8 \
  --output /absolute/path/to/fresh-directory
```

The probe uses the exact extracted instance parameters, retains all model
warnings, and hashes the PDK files and simulator executables. It measures a DC
sweep from -0.2 to 1.98 V and one 1 MHz small-signal point. The AC capacitance
is `-imag(I(Vbias))/(2*pi*f)` because the voltage-source current has the opposite
sign to the shunt load. GMIN is explicitly 1e-18 for both simulators. Results are
always marked unqualified: parser success and a single AC point are insufficient
for model equivalence or physical-noise validation. A failed simulator or missing
measurement gives a nonzero process exit.

The 2026-09-12 workspace probe confirms ngspice can evaluate the supplied model,
while Xyce reports that D0 has no valid model. The TT/27 C/1.8 V
reference point gives approximately 0.434 fF at 1 MHz; this is one diode
measurement, not a PLL jitter or timing result. Ngspice itself warns that some PDK
parameters are ignored; those warnings must remain visible in any reference
comparison. Workspace results are under
`../build/openpll-verification/diode-compat-probe-v2/`.

The 2026-09-30 diagnostic defaults to upstream Xyce/KLU instead of KLS.
It now emits `.options device gmin=1e-18` for Xyce; the earlier bare
`.options gmin=1e-18` syntax was ignored by Xyce. The probe also explicitly
sets relative tolerance to 1e-8 and absolute tolerance to 1e-24, because
default current tolerances cannot reliably compare femtoampere leakage.
Both tolerances are configurable and retained in the report parameters.

A fixed-temperature translation feasibility screen at TT/27 C completed
against the pinned PDK and ngspice 42 reference. It retains area and
perimeter capacitance terms, series resistance, the two saturation-current
temperature factors, and the merged current emission behavior. The candidate
uses a standard Xyce level-1 diode, explicit geometry scaling, and parameters
evaluated at the selected temperature. It is an isolated diagnostic model;
the PDK and PLL decks were not changed. Across 110 DC sweep points from
-0.2 to 1.98 V, the maximum relative current difference is 0.0001695
(0.01695%), with maximum absolute difference 1.273e-16 A. At 1.8 V and
1 MHz, capacitance is 4.33692445e-16 F in ngspice and 4.33692202e-16 F
in Xyce, a relative difference of 5.615e-7. Decks, logs, and the explicitly
unqualified comparison report are in
`build/modern_25mhz/diode_upstream_klu_unmodified_tt27/`.
The ngspice reference was run on the host because its binary requires
`libXaw.so.7`, which is absent from the release container. Its model files
are an unchanged copy from the pinned release image under
`build/modern_25mhz/diode_pdk_cache/sky130A/`.

This nominal comparison does not establish equivalence across temperature,
corners, charge transients, or noise. A reusable translation and those
comparisons remain necessary before enabling antenna-diode repair in a
release candidate. The relevant reference behavior is implemented in
[ngspice diode temperature calculations](https://raw.githubusercontent.com/ngspice/ngspice/master/src/spicelib/devices/dio/diotemp.c)
and [diode current calculations](https://raw.githubusercontent.com/ngspice/ngspice/master/src/spicelib/devices/dio/dioload.c).

Temperature correction (2026-09-30): upstream Xyce ignores `.temp`. The
generators now emit `.options device temp=...`; a live temperature witness
confirmed -40 and 125 C in
`build/modern_25mhz/xyce_temperature_control_probe/summary.json`.
Earlier non-27 C probes using `.temp` must be rerun.

The corrected TT/27 C translation screen in
`build/modern_25mhz/diode_translation_v3_tt27/summary.json` passes its
diagnostic DC, AC and transient charge comparisons: maximum relative errors
are 0.01695%, 0.000276% and 0.03495%, respectively. This is one operating
point; noise and full bias coverage remain unverified, so it does not
authorize release model replacement.

The corrected five-corner by three-temperature diagnostic grid in
`build/modern_25mhz/diode_translation_grid_v3/summary.json` passes all 15
cases. Maximum relative differences are 0.02207% for DC, 0.000336% for AC
at 1.8 V, and 0.03744% for rising-edge charge. Multiple operating-bias AC,
falling charge and noise comparisons are still required.

The expanded grid in `build/modern_25mhz/diode_translation_grid_v5/summary.json`
also passes all 15 cases with AC biases 0, 0.81, 1.62, 1.8 and 1.98 V and
both charge transitions. Maximum AC complex-current difference is 0.000676%;
maximum falling-charge difference is 0.08285%. A first TT/27 C noise
measurement remains unresolved: comparisons depend on the measurement
transimpedance, with a residual mismatch at lower gains. Diagnostic decks
and raw results are preserved in `build/modern_25mhz/diode_noise_tt27_v1/`
through `diode_noise_tt27_v4/`. The measurement circuit must be validated
before interpreting this as a model defect or approving model replacement.

Lower-gain measurements (1e6 and 1e3 ohm) have consistent gain scaling.
At TT/27 C, the original candidate's output noise PSD is 1.215 times the
reference at 1 MHz and 2.300 times at 10 GHz. Multiplying its model RS by
the instance area 0.4347 reduces the noise mismatch to 0.305%, but changes
the electrical response: the TT/1.8 V/10 GHz real current becomes 43.6%
of the reference. The expanded grid
`build/modern_25mhz/diode_translation_grid_v6_rs/summary.json` rejects all
15 adjusted-resistance cases on AC comparisons. That adjustment was
reverted; it is not a compatible replacement. The original candidate
retains the passing DC/AC/charge behavior and remains unqualified for noise.

Source inspection identifies an independent-reference issue in packaged
ngspice 42: `diotemp.c` includes instance area in `DIOtConductance`, while
`dionoise.c` multiplies that conductance by area again. `dioload.c` uses the
already scaled conductance directly. For area 0.4347, the extra factor
predicts a reciprocal PSD ratio of 2.30044, matching the high-frequency
measurement. The exact version-42 source and download hash are preserved
in `build/tools/ngspice/source42/provenance.json`. This is evidence for a
reference-noise defect, not authority to change the PDK or waive noise
qualification. Recheck with a corrected independent simulator first.

The ngspice 47 packaged source removes the second area multiplication in
`dionoise.c` while retaining it in the electrical conductance calculation.
Source archive and dependency hashes are recorded in
`build/tools/ngspice47/build_inputs.json`. Its independent-reference build
is in progress. The new `scripts/sky130_diode_noise_probe.py` explicitly
uses ngspice `set sqrnoise` and selects the spectral plot, so both outputs
are compared in V^2/Hz. Its TT/27 C negative control with ngspice 42
reproduces a maximum 130.04% PSD difference
(`build/modern_25mhz/diode_noise_harness_tt27_ng42_v2/summary.json`).

The ngspice 47 build completed; binary hash and build commands are in
`build/tools/ngspice47/binary_provenance.json`. Its explicit diode area/PJ
arguments are no longer multiplied by `.option scale`, unlike version 42.
The diagnostic `--reference-geometry explicit` therefore supplies the same
effective physical geometry (area 0.4347, perimeter 2.64) to its unchanged
PDK model and wrapper. Retaining version-42 argument magnitudes in version
47 does not represent the same device; that initial comparison was rejected.

With equivalent geometry and ngspice 47, the original candidate passes the
TT/27 C/1.8 V noise spectrum comparison from 1 MHz to 10 GHz. Maximum PSD
difference is 0.00188%
(`build/modern_25mhz/diode_noise_harness_tt27_ng47_v2/summary.json`). This
resolves the nominal mismatch without changing the candidate resistance or
the PDK. Full electrical and noise grids remain necessary before qualification.

The complete ngspice-47 electrical grid
`build/modern_25mhz/diode_translation_grid_ng47_v2/summary.json` passes all
15 corner/temperature cases. Maximum relative differences are 0.02207% DC,
0.000676% complex AC current, 0.05465% rising charge and 0.04971% falling
charge. The associated noise grid
`build/modern_25mhz/diode_noise_grid_ng47_v1/summary.json` passes all 75
corner/temperature/bias cases with a maximum PSD difference of 0.001878%.
Together these establish model-equivalence screening for the tested fixed
geometry, temperatures and bias range. They do not sign off PLL jitter,
assembled-circuit behavior, other diode geometries or out-of-range biases.
Production translation must retain that scope and its provenance checks.

`scripts/check_sky130_diode_qualification.py` now validates complete case
coverage, input provenance and raw DC/AC/charge/noise measurements. It passes
the above grids and writes
`build/modern_25mhz/diode_qualification_ng47.json`, including hashes of all
evidence files. The artifact explicitly keeps PLL release qualification
false. Tests reject missing/duplicate cases, nonfinite measurements,
failed cases and errors at the acceptance bound. Use this checked evidence
for the next fixed-geometry translation integration experiment.

`scripts/translate_sky130_diode.py` now creates an experimental extracted
include using only the checked geometry. It validates evidence hashes,
rejects other geometries and ambiguous device statements, and records
corner/temperature and input/output hashes in a sidecar. The DCO deck
generator rejects reuse under another simulator, corner or temperature,
or after the translated include changes. Node order and other extracted
devices are retained. Six legacy strength-DCO antenna diode instances
were converted in `build/modern_25mhz/strength_diode_translation_tt27/`.
The upstream-Xyce integration completed a 25 ns TT/1.8 V/27 C transient
with return code zero in 167.1 s, removing the unsupported-model failure.
It did not produce enough output crossings for a frequency measurement;
the DCO runner correctly marks it failed. This confirms parser/device
integration only and does not promote the legacy DCO as the 450 MHz
release design.

The next compatibility change must preserve the relevant DC, charge/capacitance,
and temperature behavior. Compare across the operating biases, all approved
corners and temperatures, then check transient charge and any required noise
behavior. A blind model-level substitution, removal of antenna diodes, or
unqualified geometry rescaling is not an accepted replacement. Once this gate
passes, resume the extracted SS fastest/FF slowest screens and then the 48-band
coverage campaign with the pinned upstream Xyce simulator.

Reference for the independent simulator's diode equations and parameter scaling:
[ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf).
The local PDK and Xyce source versions used by a probe are authoritative for
interpreting that probe's compatibility results.


2026-10-20: fresh explicit-HS-geometry comparison is complete in
build/timing400/release_001/hs_diode_geometry_comparison_001/assessment.json.
All360 native analyses pass:15 electrical and75 noise-bias cases across the
five process corners and-40/27/125C. Scope is effective area0.6417um2 and
perimeter3.24um, DC bias-0.2..1.98V, AC/noise1MHz..10GHz at the checked bias
points. The prior HD geometry0.4347um2/2.64um remains separately qualified.

The new scripts/translate_sky130_checked_diode_geometries.py supports both
exact native wrapper geometries, verifies both evidence chains and the
foundry-model hash, and emits separate explicit-geometry wrappers sharing the
checked fixed-temperature diode model. It rejects unsupported geometry,
continued/duplicate cards, global scale, complete decks and repeated
translation. Required arguments are --hd-qualification, --hs-qualification,
--electrical (the checked HD parameter report), --pdk, --input, --output,
--corner and --temperature-c. The same global simulator temperature is
mandatory. The original HD-only translator and its scope guard are unchanged.

Controls in checked_diode_geometry_translation_controls_001 verify all726
actual current native cards (724HS+2HD), all15 model renderings against the
completed native HS decks, and six invalid-input cases. A CLI translation
also passes in checked_diode_geometry_translation_cli_001. These are model
compatibility results; physical RC, assembled supply/noise behavior and
whole-PLL qualification remain separate and incomplete.
