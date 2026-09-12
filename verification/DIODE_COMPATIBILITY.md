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

The next compatibility change must preserve the relevant DC, charge/capacitance,
and temperature behavior. Compare across the operating biases, all approved
corners and temperatures, then check transient charge and any required noise
behavior. A blind model-level substitution, removal of antenna diodes, or
unqualified geometry rescaling is not an accepted replacement. Once this gate
passes, resume the extracted SS fastest/FF slowest screens and then the 48-band
coverage campaign, keeping KLS as the PLL simulator's linear solver.

Reference for the independent simulator's diode equations and parameter scaling:
[ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf).
The local PDK and Xyce source versions used by a probe are authoritative for
interpreting that probe's compatibility results.
