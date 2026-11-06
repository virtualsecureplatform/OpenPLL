"""Assess a completed full-device-corner point and verify observed preset identity."""
import argparse,json,math,os,re,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from run_full_corner_calibration import LIB

def binding(manifest,assessment,deck):
    op=manifest['operating_point'];corner=op['corner']
    if corner not in ('tt','ff','ss','sf','fs')or op['temperature_c']!=27 or op['supply_v']!=1.8:
        raise ValueError('declared prototype device corner and nominal temperature/supply required')
    if re.findall(r'^\.lib[ \t]+"([^"\n]+)"[ \t]+(\S+)[ \t]*$',deck,re.MULTILINE)!=[(LIB,corner)]:
        raise ValueError('actual PDK selector differs from declared corner')
    if deck.splitlines().count('.options device temp=27')!=1:raise ValueError('nominal native temperature required')
    expected={'VPWR':1.8,'VPB':1.8,'VGND':0.,'VNB':0.};found={n:[]for n in expected}
    for line in deck.splitlines():
        f=line.split()
        if len(f)>=3 and f[0].lower().startswith('v')and f[1]in found:
            if len(f)!=4 or f[2]!='0':raise ValueError('fixed external rail stimulus required')
            found[f[1]].append(float(f[3]))
    if any(found[n]!=[v]for n,v in expected.items()):raise ValueError('native supply/body rails differ')
    if assessment['end_ns']!=260 or assessment['measurement_window_ns']!=[200,260]:raise ValueError('complete native endpoint/window required')
    for name,width in(('coarse',6),('fine',8)):
        code=manifest['startup_'+name];key='coarse_code'if name=='coarse'else'dco_code'
        if type(code)is not int or not(0<=code<=47 if name=='coarse'else 8<=code<=247):raise ValueError('supported declared preset required')
        if assessment[key]['window_codes']!=[code]:raise ValueError('observed stationary '+name+' code differs from native request')
    signal=assessment['signals']['v(pllout)'];frequency=signal['mean_frequency_mhz']
    if signal['rising_edges_200_260ns']<3 or frequency is None or not math.isfinite(frequency)or frequency<=0:
        raise ValueError('measured positive-frequency point required')
    return dict(operating_point=op,coarse=manifest['startup_coarse'],fine=manifest['startup_fine'],
        observed_stationary_codes_match_request=True,actual_library_temperature_and_external_rails_match=True,
        passive_view='selected nominal geometric R/C',target_or_startup_qualified=False,release_ready=False)

def run(native,output):
    output.mkdir(parents=True,exist_ok=False);save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((native/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        while True:
            status=json.loads((native/'status.json').read_text())
            if status['state']not in('preparing_full_corner_calibration','running_loaded_startup_260ns'):break
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native controller disappeared')
            if 'native_deadline_uptime'in status:deadline=status['native_deadline_uptime']+300
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('observer deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_native_completion',release_ready=False));time.sleep(10)
        if status['state']!='native_startup_completed_waveform_assessment_pending':raise ValueError('normally completed native point required')
        manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        worker=json.loads((native/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker is still live')
        source=ROOT/'tools/xyce_waveform/extract_selected.cpp';assessor=Path(__file__).with_name('assess_selected_startup.py')
        pins={str(p):sha(p)for p in(source,assessor,manifest,Path(__file__).resolve(),Path(__file__).with_name('run_full_corner_calibration.py'),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'))}
        os.sched_setaffinity(0,{24})
        with lease(1,2,deadline):
            save(output/'status.json',dict(state='extracting_completed_waveform',release_ready=False))
            subprocess.run(['/usr/bin/g++','-O3','-std=c++17',source,'-o',output/'extract'],check=True,timeout=60)
            pins[str(output/'extract')]=sha(output/'extract')
            with(output/'extraction.log').open('x')as log:subprocess.run([output/'extract',native/'profile.raw',output/'signals.csv'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
            with(output/'assessment.log').open('x')as log:subprocess.run(['/usr/bin/python3',assessor,'--output',output],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        result=binding(m,json.loads((output/'assessment.json').read_text()),(native/'profile.spice').read_text())
        bound=output/'operating_point_binding.json';save(bound,result)
        verify(pins);verify(m['input_sha256'])
        artifacts={str(p):sha(p)for p in(output/'assessment.json',output/'signals.csv',output/'extraction.log',bound)}
        save(output/'provenance.json',dict(input_sha256=pins,native_input_sha256=m['input_sha256'],raw_sha256=sha(native/'profile.raw'),artifacts=artifacts,
            namespace_tool_sha256={p:sha(p)for p in('/usr/bin/g++','/usr/bin/python3')},operating_point=result['operating_point'],diagnostic=True,release_ready=False))
        save(output/'status.json',dict(state='calibration_waveform_assessed',requested_preset_verified_against_waveform=True,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),native_jobs_restarted_or_terminated=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.native.resolve(),a.output.resolve())
