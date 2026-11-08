"""Check four non-TT library selections on the unchanged 27 C flat backend."""
import argparse,csv,json,math,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute

def corner_deck(text,reference,output,corner):
    if corner not in ['ff','ss','sf','fs']:raise ValueError('non-TT process corner required')
    if len(re.findall(r'^\.lib (.+) tt$',text,re.M))!=1:raise ValueError('one TT library selection required')
    if text.splitlines().count('.dc VRESET 0 0 1')!=1 or text.splitlines().count('.options device temp=27')!=1:raise ValueError('one fixed 27 C reset DC point required')
    if text.count(str(reference/'dc.csv'))!=1:raise ValueError('one reset DC output path required')
    return re.sub(r'^\.lib (.+) tt$',lambda m:'.lib '+m[1]+' '+corner,text,flags=re.M).replace(str(reference/'dc.csv'),str(output/'dc.csv'))

def run(reference,output):
    receipt=reference/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['normal_native_exit'] or not r['finite_reset_DC_point']:raise ValueError('completed TT reset reference required')
    backend=reference/'backend_model.spice';model=backend.read_text()
    required=['CJ={1.3459e-15*sky130_fd_pr__nfet_01v8__ajunction_mult}','CJSW={3.6001e-17*sky130_fd_pr__nfet_01v8__pjunction_mult}','R={rp1*(l*1e-6)/(w*1e-6+tol_poly+poly_dw)}']
    if any(s not in model for s in required):raise ValueError('corner-dependent junction/poly expressions required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200;save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';source=reference/'smoke.spice'
    pins={**r['input_sha256'],**{str(p):sha(p)for p in [receipt,source,backend,binary,Path(__file__).resolve(),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('resources.py')]}}
    save(output/'inputs.json',dict(input_sha256=pins,corners=['ff','ss','sf','fs'],CPU=27,memory_GiB=16,family_cap_s=7200,per_case_cap_s=1800,maximum_native_cases=4,concurrent_cases=1,automatic_identical_retry=False,temperature_C=27,supply_V=1.8,backend_model_unchanged=True,diode_and_poly_corner_expressions_preserved=True,release_ready=False));results=[];artifacts={}
    try:
        for corner in ['ff','ss','sf','fs']:
            folder=output/corner;folder.mkdir();deck=folder/'smoke.spice';deck.write_text(corner_deck(source.read_text(),reference,folder,corner));pins[str(deck)]=sha(deck);verify(pins)
            save(folder/'inputs.json',dict(input_sha256=pins,corner=corner,temperature_C=27,supply_V=1.8,reset_asserted=True,transient=False,release_ready=False));save(output/'status.json',dict(state='non_TT_reset_DC_running',corner=corner,release_ready=False));start=time.monotonic()
            with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+1800),16)
            data=folder/'dc.csv';reader=csv.reader(data.read_text().splitlines());headers=next(reader);rows=[]
            for row in reader:
                if row and row[0].startswith('End of'):continue
                if len(row)!=len(headers):raise ValueError('incomplete corner DC row')
                values=[float(v)for v in row]
                if not all(math.isfinite(v)for v in values):raise ValueError('nonfinite corner DC point')
                rows.append(dict(zip(headers,values)))
            if len(rows)!=1:raise ValueError('exactly one reset DC point required')
            verify(pins);record=dict(corner=corner,temperature_C=27,supply_V=1.8,normal_native_exit=True,finite_saved_reset_DC_point=rows[0],elapsed_s=time.monotonic()-start,transient_qualified=False,corner_model_qualified=False,release_ready=False)
            save(folder/'assessment.json',dict(input_sha256={**pins},artifacts={str(p):sha(p)for p in [deck,data,folder/'native.log']},**record));results.append(record)
            artifacts.update({str(p):sha(p)for p in [folder/'assessment.json',data,folder/'native.log']})
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_four_non_TT_reset_DC_checks_complete=True,backend_model_unchanged=True,full_node_state_capture=False,transient_qualified=False,corner_model_qualified=False,release_ready=False));save(output/'status.json',dict(state='non_TT_reset_DC_checks_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.reference.resolve(),a.output.resolve())
