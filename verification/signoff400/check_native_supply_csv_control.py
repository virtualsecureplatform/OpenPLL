"""Native resistor control for four-rail current signs, integration and extra print."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease
from run_full_corner_calibration_v2 import supply_csv
from assess_native_supply_csv import analyze
from assess_selected_detector_prefix import read_prefix


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';image=ROOT/'build/apptainer/openpll-release-modern.sif';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+300
    pins={str(p):sha(p)for p in(binary,image,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','compiled_charge_v2.py','run_full_corner_calibration_v2.py','assess_native_supply_csv.py','assess_selected_detector_prefix.py')))}
    tables=[];supplies=None
    for name in('baseline','additional_supply_csv'):
        d=output/name;d.mkdir();deck=d/'control.spice'
        text=f'''Four nominal supply/body rails feeding known resistors
Vpower VPWR 0 1.8
Vbody VPB 0 1.8
Vground VGND 0 0
Vbulk VNB 0 0
Rcore VPWR VGND 1000
Rbody VPB VNB 10000
.tran 10p 10n 0 10p
.print tran format=raw precision=17 file={d/'control.raw'} v(VPWR) v(VPB) v(VGND) v(VNB)
.end
'''
        if name!='baseline':text,supplies=supply_csv(text,d/'supply.csv')
        deck.write_text(text);pins[str(deck)]=sha(deck)
        with lease(1,2,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],d/'native.log',deadline,2)
        rows,info=read_prefix(d/'control.raw',{n:n for n in('VPWR','VPB','VGND','VNB')})
        if info['incomplete_final_sample_discarded']or abs(rows[-1][0]-10e-9)>1e-18:raise ValueError('complete native control waveform required')
        tables.append(rows)
    if tables[0]!=tables[1]:raise ValueError('adding current observations changed baseline voltage waveform')
    result=analyze(output/'additional_supply_csv/supply.csv',supplies,2,8,10)
    expected=(1.8**2/1000+1.8**2/10000)
    if abs(result['mean_supply_power_W']/expected-1)>1e-10 or abs(result['energy_J']/(expected*6e-9)-1)>1e-10:raise ValueError('native four-rail supply power sign/units/integral differs from analytic resistor control')
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()},expected_mean_supply_power_W=expected,measured=result,
        actual_native_four_rail_sign_and_energy_control_passed=True,extra_csv_preserves_native_voltage_samples_exactly=True,full_macro_power_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
