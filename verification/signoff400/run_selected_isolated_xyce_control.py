"""Compare the existing isolated DCO in Xyce and ngspice; diagnostic only.

Preserve all capacitor cards, control sources, and primitive geometry. Apply
only existing scoped backend adapters. Integration algorithms are not matched;
this screen cannot qualify a fast model or attribute every observed difference.
"""
import argparse,hashlib,json,os,re,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from prototype_xyce_resistor_translation import translate as resistor
from prototype_xyce_diode_translation import translate as diode
from assess_selected_detector_phase_probe_v2 import read_selected,transitions
sys.path.insert(0,str(ROOT/'scripts'))
from sky130_diode_translation_probe import translated_model,MODEL_SHA256


def caps(text):
    h=hashlib.sha256();count=0
    for line in text.splitlines():
        f=line.split()
        if f and f[0][0].lower()=='c':h.update((line+'\n').encode());count+=1
    return count,h.hexdigest()


def frequency(rows,column=1):
    rising=[t for t in transitions(rows,column)['rising_ns'] if 20<=t<=40]
    if len(rising)<3:raise ValueError('three oscillator rises in 20..40 ns required')
    periods=[b-a for a,b in zip(rising,rising[1:])]
    return dict(rising_edges=len(rising),frequency_mhz=1000/(sum(periods)/len(periods)),minimum_period_ns=min(periods),maximum_period_ns=max(periods))


def run(source,deck_source,ng_waveform,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_isolated_Xyce_control',release_ready=False))
    try:
        model_path=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice')
        if sha(model_path)!=MODEL_SHA256:raise ValueError('diode adapter PDK model mismatch')
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        pins={str(p):sha(p) for p in [source,deck_source,ng_waveform,binary,model_path,Path(__file__).resolve(),Path(__file__).with_name('prototype_xyce_resistor_translation.py'),Path(__file__).with_name('prototype_xyce_diode_translation.py'),ROOT/'scripts/sky130_diode_translation_probe.py',Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]}
        original=source.read_text();before=caps(original)
        text=original;nr=0
        if 'sky130_fd_pr__res_generic_po' in text:text,nr=resistor(text)
        text,nd=diode(text)
        if caps(text)!=before:raise ValueError('constant capacitor cards changed')
        model=translated_model(27,1,1)
        model=re.sub(r'(?m)^\+ CJ=\S+',r'+ CJ={1.3459e-15*sky130_fd_pr__nfet_01v8__ajunction_mult}',model)
        model=re.sub(r'(?m)^\+ CJSW=\S+',r'+ CJSW={3.6001e-17*sky130_fd_pr__nfet_01v8__pjunction_mult}',model)
        adapted=output/'model.spice';adapted.write_text(model+text);del original,text
        raw=output/'control.raw';deck=output/'control.spice'
        text=deck_source.read_text().split('.control')[0].replace(str(source),str(adapted))
        text='\n'.join(line for line in text.splitlines() if not line.lower().startswith(('.option','.tran','.temp','.save','.print','.meas','.end')))
        deck.write_text(text+f'''
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 10p 40n 0 10p
.print tran format=raw precision=17 file={raw} v(PLLOUT)
.end
''')
        pins.update({str(p):sha(p) for p in [adapted,deck]})
        save(output/'manifest.json',dict(input_sha256=pins,CPU=29,memory_GiB=16,native_cap_s=3600,automatic_identical_retry=False,
            original_capacitor_count=before[0],constant_capacitor_cards_exactly_preserved_sha256=before[1],resistor_adapters=nr,diode_adapters=nd,
            identical_control_sources=True,comparison_window_ns=[20,40],native_integration_algorithm_matched=False,
            physical_models_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        save(output/'status.json',dict(state='isolated_Xyce_native_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows=read_selected(raw,{'output':'PLLOUT'},40e-9)
        native=frequency(rows);ng=[]
        for line in ng_waveform.open():
            f=line.split()
            if len(f)!=2:raise ValueError('one time and voltage per ngspice waveform row required')
            t,v=map(float,f)
            if t<=40e-9:ng.append([t,v])
        reference=frequency(ng)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},all_saved_values_finite=True,
            Xyce=native,ngspice=reference,frequency_difference_ppm=1e6*(native['frequency_mhz']/reference['frequency_mhz']-1),
            integration_algorithm_matched=False,numerical_convergence_qualified=False,reduced_model_correlated_to_full_native=False,
            physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='isolated_backend_frequency_screen_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','deck-source','ng-waveform','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(a.source.resolve(),a.deck_source.resolve(),a.ng_waveform.resolve(),a.output.resolve())
