"""Measure native DAC/PWL equivalence for four initialization controls."""
import argparse,csv,hashlib,json,os,resource,subprocess,time
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();probe=a.probe.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{24})
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    pins={str(x):sha(x) for x in (probe,Path(__file__).resolve(),Path(__file__).with_name('dac_replay_probe.cpp'))}
    records=[]
    for shape in ('ramp','plateau'):
        for mode in ('naive','stream'):
            directory=out/(shape+'_'+mode);directory.mkdir()
            deck=directory/'control.spice';wave=directory/'wave.csv'
            plateau='100p 0 ' if shape=='plateau' else ''
            deck.write_text(f'''DAC replay initialization diagnostic
Vref reference 0 PWL(0 0 {plateau}500p 1 1n 0 1.5n 1 2n 0)
YDAC drive streamed 0 dacmod
.model dacmod DAC(tr=0 tf=0)
YADC readback streamed 0 adcmod R=1T WIDTH=1
.model adcmod ADC(settlingtime=1p uppervoltagelimit=1 lowervoltagelimit=0)
Rref reference 0 1k
Rstream streamed 0 1k
.options timeint reltol=1e-8 abstol=1e-12
.tran 1p 2n 0 10p
.print tran format=csv file={wave} v(reference) v(streamed)
.end
''')
            start=time.monotonic()
            with (directory/'native.log').open('x') as log:
                result=subprocess.run([str(probe),str(deck),mode,shape],cwd=directory,
                    stdout=log,stderr=subprocess.STDOUT,timeout=60,preexec_fn=limits)
            if result.returncode or 'PROBE_COMPLETE' not in (directory/'native.log').read_text():
                raise RuntimeError(f'{shape}/{mode} native control did not complete')
            with wave.open() as f:
                rows=list(csv.DictReader(f))
            # Xyce appends a textual end marker, which is not a numeric sample.
            samples=[]
            for row in rows:
                if str(row.get('TIME','')).startswith('End of') or str(row.get('TIME','')).startswith('End of Xyce'):
                    continue
                if row.get('V(REFERENCE)') is None:continue
                samples.append(tuple(float(row[k]) for k in ('TIME','V(REFERENCE)','V(STREAMED)')))
            import math
            if not samples or any(not all(map(math.isfinite,r)) for r in samples):raise ValueError('finite samples required')
            if abs(samples[-1][0]-2e-9)>1e-18:raise ValueError('complete observation required')
            error=max(abs(ref-stream) for _,ref,stream in samples)
            records.append(dict(shape=shape,mode=mode,native_exit=result.returncode,
                elapsed_s=time.monotonic()-start,samples=len(samples),maximum_voltage_difference_V=error,
                input_sha256={str(deck):sha(deck)},artifacts={str(wave):sha(wave)}))
    if any(sha(Path(path))!=digest for path,digest in pins.items()):raise ValueError('input changed')
    report=dict(records=records,input_sha256=pins,diagnostic=True,
        selected_boundary_replay_qualified=False,physical_models_qualified=False,release_ready=False)
    (out/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(records))
