"""Native resistor/clock control for the DCO worker's two-rail power measurements."""
import argparse,importlib.util,json,os,sys,time
from pathlib import Path
from types import SimpleNamespace
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute


def run(output):
    sys.path.insert(0,str(ROOT/'scripts'))
    worker=ROOT/'scripts/spice_dco_postlayout_prototype_v6.py'
    spec=importlib.util.spec_from_file_location('power_worker',worker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output.mkdir(parents=True,exist_ok=False);model=output/'control.spice'
    model.write_text('.subckt SupplyMeasurementControl PLLOUT VPWR VPB VGND VNB RESET_N\nRmain VPWR VGND 1800\nRbulk VPB VGND 18000\nVclock PLLOUT VGND PULSE(0 1.8 1n 50p 50p 1.2n 2.5n)\n.ends SupplyMeasurementControl\n')
    args=SimpleNamespace(pdk_root='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae',pdk='sky130A',rcx_netlist=str(model),subckt_name='SupplyMeasurementControl',simulator='ngspice',corner='tt',temperature_c=27,vdd=1.8,therm_invert=True,ngspice_threads=1,reset_release_ns=5,sim_time_ns=80,meas_start_ns=20,step_ps=10,max_step_ps=10,supply_ramp_ns=0,supply_ramp_delay_ns=0,ngspice_waveform=True,ngspice_reltol=1e-5,ngspice_abstol=1e-9,ngspice_klu=True)
    deck=output/'control.cir';deck.write_text(module.dco_netlist(args,128,1,['PLLOUT','VPWR','VPB','VGND','VNB','RESET_N']))
    ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice';log=output/'native.log'
    pins={str(p):sha(p) for p in (worker,model,deck,ng,Path(__file__).resolve())}
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(1,4,deadline):execute([ng,'-b',deck],log,deadline,4)
    text=log.read_text();row=module.row_from_log(args,128,1,deck,log,text,0,False,0,False)
    if row['status']!='pass':raise ValueError('clock waveform parser/control failed')
    for key,expected in [('vpwr_average_source_current_A',-.001),('vpb_average_source_current_A',-.0001)]:
        if row[key] is None or abs(row[key]-expected)>1e-10:raise ValueError('supply current units/sign mismatch: '+key)
    power=-1.8*(row['vpwr_average_source_current_A']+row['vpb_average_source_current_A'])
    if abs(power-.00198)>1e-10:raise ValueError('two-rail power arithmetic mismatch')
    detail=output/'measurements.json';save(detail,dict(row=row,total_fixed_rail_power_W=power));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(log):sha(log),str(detail):sha(detail)},
        supply_current_sign_units_and_both_rails_verified=True,exact_redundant_print_rows_losslessly_supported=True,
        ideal_resistor_and_clock_control_only=True,DCO_power_characterized=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.output.resolve())
