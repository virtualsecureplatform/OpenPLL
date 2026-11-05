#!/usr/bin/env python3
"""Prepare a conditional antenna-diode load view from revalidated evidence.

The scalar is an implementation/STA screening envelope under the recorded
analytic diode and nominal extracted cell-RC models, fixed supplies and
pin bias -0.2..1.95V. It does not qualify full timing, voltage/noise enclosure,
metal variation or the PLL. Exact diode RC remains available for native checks.
"""
import argparse
import itertools
import json
from pathlib import Path
import re
import sys

from run_dco_qualification import ROOT,sha,save
sys.path.insert(0,str(ROOT/'verification/timing450'))
from diode_translation_probe_v2 import translated_model


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();qualification=args.qualification.resolve();out=args.output.resolve()
    q=json.loads(qualification.read_text());assert q['model_equivalence_screen_passed'] and not q['pll_release_qualified']
    pins={str(qualification):sha(qualification),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    for path,digest in q['evidence_sha256'].items():
        resolved=Path(path).resolve();assert sha(resolved)==digest,str(resolved);pins[str(resolved)]=digest
    old=ROOT/'build/timing450/interface_characterization'
    rc=old/'receiver_macro_reset_diode_rc/assessment.json'
    r=json.loads(rc.read_text());pins[str(rc)]=sha(rc)
    assert all(r[k] for k in ('native_topology_area_perimeter_lvs_pass','wrong_area_control_rejected',
                              'wrong_perimeter_control_rejected','geometry_matches_gds'))
    for path,digest in r['sha256'].items():
        resolved=Path(path).resolve();assert sha(resolved)==digest,str(resolved);pins[str(resolved)]=digest
    model=old/'receiver_macro_reset_diode_rc/sky130_fd_sc_hs__diode_2.spice'
    text=model.read_text()
    assert 'perim=3.24e+06 area=6.417e+11' in text
    caps=[float(v)*1e-15 for v in re.findall(r'^C\S+ \S+ \S+ ([0-9.eE+-]+)f$',text,re.M)]
    resistors=[float(v) for v in re.findall(r'^R\S+ \S+ \S+ ([0-9.eE+-]+)$',text,re.M)]
    assert len(caps)==11 and len(resistors)==7 and min(caps)>0 and min(resistors)>0
    grid=old/'receiver_macro_reset_diode_translation_v2/summary.json'
    data=json.loads(grid.read_text());assert data['all_screens_passed']
    assert data['effective_geometry']=={'area_um2':.6417,'perimeter_um':3.24}
    assert len(data['cases'])==15 and all(c['screen_passed'] for c in data['cases'])
    def depletion(c0,potential,grading,forward):
        # Standard SPICE depletion continuation at FC=.5; no transit-time
        # charge is present in this pinned model. Positive sidewall/bottom
        # derivatives make the maximum occur at the largest forward bias.
        fc=.5
        if forward<=fc*potential:return c0/(1-forward/potential)**grading
        return c0/(1-fc)**(1+grading)*(1-fc*(1+grading)+grading*forward/potential)
    rows=[]
    for corner,temp in itertools.product(q['corners'],q['temperatures_c']):
        aj,pj=data['corner_parameters'][corner]
        translated=translated_model(temp,aj,pj)
        cj=float(re.search(r'\bCJ=([0-9.eE+-]+)',translated)[1])
        cjsw=float(re.search(r'\bCJSW=([0-9.eE+-]+)',translated)[1])
        vj=float(re.search(r'\bVJ=([0-9.eE+-]+)',translated)[1])
        assert min(cj,cjsw,vj)>0
        bound=depletion(cj*.6417,vj,.44,.2)+depletion(cjsw*3.24,.2,.0009,.2)
        zero=cj*.6417+cjsw*3.24
        assert bound>=zero
        rows.append(dict(corner=corner,temperature_c=temp,zero_bias_junction_cap_f=zero,
                         analytic_junction_cap_upper_f=bound))
    # Use the predeclared model-comparison tolerance, never a fitted margin.
    error=q['limits']['ac_complex_current_relative_error'];assert 0<=error<1
    upper_pf=(sum(caps)+max(row['analytic_junction_cap_upper_f'] for row in rows)/(1-error))*1e12
    upper_pf=float(format(upper_pf*1.000000001,'.12g'))
    out.mkdir(parents=True,exist_ok=False)
    lib=out/'antenna_diode_load.lib'
    lib.write_text(f'''library (openpll_antenna_load_screen) {{
 time_unit : "1ns";
 voltage_unit : "1V";
 current_unit : "1mA";
 capacitive_load_unit (1, pf);
 input_threshold_pct_rise : 50;
 input_threshold_pct_fall : 50;
 output_threshold_pct_rise : 50;
 output_threshold_pct_fall : 50;
 slew_lower_threshold_pct_rise : 20;
 slew_upper_threshold_pct_rise : 80;
 slew_lower_threshold_pct_fall : 20;
 slew_upper_threshold_pct_fall : 80;
 cell (sky130_fd_sc_hs__diode_2) {{
  area : 3.1968;
  dont_use : true;
  pin (DIODE) {{
   direction : input;
   capacitance : {upper_pf:.12g};
   rise_capacitance : {upper_pf:.12g};
   fall_capacitance : {upper_pf:.12g};
  }}
 }}
}}
''')
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(lib):sha(lib)},cell='sky130_fd_sc_hs__diode_2',
        input_capacitance_upper_pf=upper_pf,nominal_extracted_cell_cap_sum_f=sum(caps),
        pvt_analytic_bounds=rows,pin_bias_range_v=[-.2,1.95],
        comparison_tolerance_used=error,supplies_assumed_fixed=True,
        native_diode_rc_model=str(model),native_model_equivalence_revalidated=True,
        full_timing_load_enclosure_qualified=False,physical_timing_qualified=False,
        release_qualified=False,scope=__doc__))
    print(f'Prepared conditional diode input load {upper_pf:.9g}pF; full timing qualification remains open',flush=True)


if __name__=='__main__':main()
