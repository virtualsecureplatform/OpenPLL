"""Report observed isolated-DCO power from both saved fixed-rail source currents."""
import argparse,csv,json,math,re
from pathlib import Path
from common_v3 import save,sha,verify


def run(point,output):
    receipt=point/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256'])
    csvfile=point/'native/dco_postlayout_results.csv';rows=list(csv.DictReader(csvfile.open()))
    if len(rows)!=1:raise ValueError('one native operating point required')
    row=rows[0]
    if row['status']!='pass' or (row['corner'],int(row['coarse_code']),int(row['code']))!=(r['corner'],r['coarse_code'],r['fine_code']):raise ValueError('native operating point mismatch')
    if not row['subckt_name'].startswith('IntegerPLL_DCO_'):raise ValueError('actual routed DCO hierarchy required')
    native_receipt=point/'all_cycle_assessment/assessment.json';nr=json.loads(native_receipt.read_text());verify(nr['input_sha256']);verify(nr['artifacts'])
    if not nr['all_captured_measurement_cycles_assessed']:raise ValueError('independent completed cycle assessment required')
    deck,log=Path(row['netlist']),Path(row['log']);decktext=deck.read_text();logtext=log.read_text()
    for path in (csvfile,deck,log):
        if nr['input_sha256'].get(str(path))!=sha(path):raise ValueError('power observations not bound by native cycle receipt')
    if 'Using KLU as Direct Linear Solver' not in logtext:raise ValueError('verified KLU native power fixture required')
    if '.save v(PLLOUT) i(VVPWR) i(VVPB)' not in decktext:raise ValueError('both fixed-rail currents must be saved')
    values={key:float(row[key]) for key in ('vpwr_average_source_current_A','vpb_average_source_current_A','vpwr_minimum_source_current_A','vpwr_maximum_source_current_A','vpb_minimum_source_current_A','vpb_maximum_source_current_A')}
    if not all(math.isfinite(v) for v in values.values()):raise ValueError('finite native rail observations required')
    for rail in ('vpwr','vpb'):
        for label,suffix in [('average','avg'),('minimum','min'),('maximum','max')]:
            matches=re.findall(r'^\s*'+rail+'_current_'+suffix+r'\s*=\s*([-+0-9.eE]+)',logtext,re.M|re.I)
            if len(matches)!=1 or not math.isclose(float(matches[0]),values[rail+'_'+label+'_source_current_A'],rel_tol=1e-12,abs_tol=1e-18):raise ValueError('CSV/native current mismatch')
    for rail in ('vpwr','vpb'):
        if not values[rail+'_minimum_source_current_A']<=values[rail+'_average_source_current_A']<=values[rail+'_maximum_source_current_A']:raise ValueError('rail mean outside observed extrema')
    power=-1.8*(values['vpwr_average_source_current_A']+values['vpb_average_source_current_A'])
    if power<=0:raise ValueError('positive delivered fixed-rail energy required for this oscillating fixture')
    start,stop=[float(row[k]) for k in ('power_observation_start_ns','power_observation_stop_ns')]
    if not 0<=start<stop:raise ValueError('valid observed power interval required')
    output.mkdir(parents=True,exist_ok=False);detail=output/'power.json'
    save(detail,dict(corner=r['corner'],coarse_code=r['coarse_code'],fine_code=r['fine_code'],supply_v=1.8,
        observation_start_ns=start,observation_stop_ns=stop,average_fixed_rail_power_W=power,**values))
    pins={str(p):sha(p) for p in (receipt,native_receipt,csvfile,deck,log,Path(__file__).resolve())};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        native_two_fixed_rail_power_observed=True,integer_cycle_average=False,ideal_supply_sources=True,
        final_parent_load_complete=False,external_control_driver_power_included=False,
        BBPD_and_digital_power_included=False,macro_power_characterized=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--point',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.point.resolve(),a.output.resolve())
