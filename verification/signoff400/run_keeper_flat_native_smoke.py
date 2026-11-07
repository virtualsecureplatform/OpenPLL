"""One bounded reset-state DC point for the checked flat conductor-C reference."""
import argparse,csv,json,math,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_runtime import closure


def bias(pin):
    if pin in ['VPWR','VPB','STARTUP_INCREASING']:return 1.8
    if pin in ['VGND','VNB','REFCLK','RESET_N','PLL_ENABLE']:return 0
    for bus,code in [('STARTUP_COARSE',20),('STARTUP_FINE',112),('KI',1),('KP',2)]:
        m=re.fullmatch(re.escape(bus)+r'\[(\d+)\]',pin)
        if m:return 1.8 if code&(1<<int(m[1]))else 0
    return None


def run(model,output):
    receipt=model/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['constant_C_nonnegative']or not r['all_nonzero_C_endpoints_and_literal_values_preserved']or r['distributed_wire_R_included']:raise ValueError('checked endpoint-preserving conductor-C model required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{20});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice';pdk,edges=closure(os.getpid(),library)
    source=model/'model.spice';header=[line.split()for line in source.read_text().splitlines()if line.startswith('.subckt ')and not line.split()[1].startswith('__openpll_')]
    if len(header)!=1:raise ValueError('one model root required')
    top,ports=header[0][1],header[0][2:];controls=[]
    for pin in ports:
        value=bias(pin)
        if value is not None:controls.append(('VRESET'if pin=='RESET_N'else'Vbias'+str(len(controls)))+' '+pin+' 0 '+str(value))
    if len(controls)!=35:raise ValueError('expected exact selected external input interface')
    selected=['VPWR','VGND','VNB','VPB','RESET_N','PLLOUT','CONFIG_BUSY','CONFIG_READY','TRACKING','FAILED'];data=output/'dc.csv';deck=output/'smoke.spice'
    deck.write_text('* Diagnostic keeper flat conductor-C reset operating point\n'+f'.lib "{library}" tt\n.include "{source}"\n'+'\n'.join(controls)+'\nXDUT '+' '.join(ports)+' '+top+'\n.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.dc VRESET 0 0 1\n.print dc format=csv precision=17 file='+str(data)+' '+' '.join('v('+p+')'for p in selected)+'\n.end\n')
    folder=Path(__file__).resolve().parent;pins={**pdk,**{str(p):sha(p)for p in [receipt,source,deck,binary,Path(__file__).resolve(),folder/'compiled_charge_v2.py',folder/'capture_selected_native_runtime.py']}};verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,PDK_include_edges=edges,CPU=20,memory_GiB=16,native_cap_s=1800,max_native_cases=1,automatic_identical_retry=False,reset_asserted=True,release_ready=False))
    try:
        save(output/'status.json',dict(state='flat_native_reset_DC_running',release_ready=False));start=time.monotonic()
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);lines=data.read_text().splitlines();reader=csv.reader(lines);headers=next(reader);rows=[]
        for row in reader:
            if row and row[0].startswith('End of'):continue
            if len(row)!=len(headers):raise ValueError('incomplete DC output row')
            values=[float(v)for v in row]
            if not all(math.isfinite(v)for v in values):raise ValueError('nonfinite DC point')
            rows.append(dict(zip(headers,values)))
        if len(rows)!=1:raise ValueError('exactly one completed DC point required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [deck,data,output/'native.log']},elapsed_s=time.monotonic()-start,normal_native_exit=True,finite_reset_DC_point=rows[0],transient_correlation_qualified=False,frequency_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='flat_native_reset_DC_complete',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.model.resolve(),a.output.resolve())
