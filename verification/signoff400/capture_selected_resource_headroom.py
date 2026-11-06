"""Record actual live serial-worker memory peaks; never infer future memory bounds."""
import argparse,datetime,json,os
from pathlib import Path
from common_v3 import save,sha
from resources import identity


def run(cases,output):
    if output.exists():raise FileExistsError(output)
    records=[];files=[Path(__file__).resolve(),Path(__file__).with_name('resources.py')]
    for case in cases:
        native=case/'native' if (case/'native').is_dir() else case
        handle=native/'native.process.json';manifest=native/'manifest.json';h=json.loads(handle.read_text());m=json.loads(manifest.read_text());pid=h['pid'];birth=str(h['birth'])
        if m.get('MPI_ranks',1)!=1 or identity(pid)!=birth:raise ValueError('original live serial worker required')
        executable=os.readlink(f'/proc/{pid}/exe');expected=m['input_sha256'].get(executable)
        if expected is None or sha(Path(f'/proc/{pid}/exe'))!=expected:raise ValueError('actual executable does not match native manifest')
        fields={}
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            f=line.split()
            if f and f[0] in ['VmPeak:','VmSize:','VmHWM:','VmRSS:']:
                if len(f)!=3 or f[2]!='kB':raise ValueError('explicit kernel memory units required')
                fields[f[0][:-1]+'_bytes']=int(f[1])*1024
        if len(fields)!=4 or identity(pid)!=birth:raise ValueError('complete consistent live memory observation required')
        records.append(dict(case=str(case),native=str(native),worker=h,executable=executable,executable_sha256=expected,CPU_affinity=sorted(os.sched_getaffinity(pid)),**fields));files.extend([handle,manifest])
    save(output,dict(input_sha256={str(p):sha(p) for p in files},observed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),records=records,observed_peak_is_not_future_bound=True,live_jobs_modified=False,resource_limits_qualified=False,release_ready=False))
    print('observed serial workers',len(records))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([x.resolve() for x in a.case],a.output.resolve())
