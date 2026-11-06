"""Measure four-rail supply power from a complete native Xyce CSV.

Positive power denotes energy drawn from external nominal 1.8 V supply/body
rails. This is characterization of the declared run, never a power-limit gate.
"""
import argparse,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify

RAILS=('VPWR','VPB','VGND','VNB')

def analyze(path,sources,start_ns,end_ns,required_end_ns):
    if not 0<=start_ns<end_ns<=required_end_ns or set(sources)!=set(RAILS)or len(set(sources.values()))!=4:raise ValueError('complete declared rails/window required')
    with path.open()as stream:
        reader=csv.reader(stream);header=[x.strip().upper()for x in next(reader)]
        names=['TIME',*[f'V({n})'for n in RAILS],*[f'I({sources[n]})'.upper()for n in RAILS]]
        if len(set(header))!=len(header)or any(header.count(n)!=1 for n in names):raise ValueError('unique time, rail voltage and source current columns required')
        indices=[header.index(n)for n in names];rows=[];footer=False
        for fields in reader:
            if not fields:continue
            if len(fields)==1 and fields[0].strip()=='End of Xyce(TM) Simulation':
                if footer:raise ValueError('duplicate simulation footer')
                footer=True;continue
            if footer or len(fields)!=len(header):raise ValueError('complete ordered native CSV rows required')
            values=list(map(float,fields))
            if not all(math.isfinite(v)for v in values):raise ValueError('finite native power observations required')
            row=[values[i]for i in indices]
            if rows and row[0]<=rows[-1][0]:raise ValueError('strict native power timestamps required')
            if any(abs(v-w)>1e-9 for v,w in zip(row[1:5],(1.8,1.8,0.,0.))):raise ValueError('declared nominal supply/body voltages required')
            rows.append(row)
    if len(rows)<2 or rows[0][0]!=0 or abs(rows[-1][0]-required_end_ns*1e-9)>1e-18:raise ValueError('complete native power horizon required')
    start,stop=start_ns*1e-9,end_ns*1e-9;energy=[0.]*4;duration=0.;powers=[]
    for a,b in zip(rows,rows[1:]):
        left,right=max(start,a[0]),min(stop,b[0])
        if right<=left:continue
        fractions=[(t-a[0])/(b[0]-a[0])for t in(left,right)]
        ends=[[a[i]+f*(b[i]-a[i])for i in range(1,9)]for f in fractions]
        instantaneous=[-sum(v[i]*v[i+4]for i in range(4))for v in ends];powers.extend(instantaneous)
        for i in range(4):
            v0,v1=ends[0][i],ends[1][i];j0,j1=ends[0][i+4],ends[1][i+4]
            energy[i]-=(right-left)*(2*v0*j0+v0*j1+v1*j0+2*v1*j1)/6
        duration+=right-left
    if abs(duration-(stop-start))>1e-18:raise ValueError('complete integration window coverage required')
    return dict(window_ns=[start_ns,end_ns],required_end_ns=required_end_ns,samples=len(rows),energy_J=sum(energy),mean_supply_power_W=sum(energy)/duration,
        mean_power_by_rail_W={n:e/duration for n,e in zip(RAILS,energy)},sampled_power_range_W=[min(powers),max(powers)],
        convention='negative sum of external rail voltage times voltage-source current',integration='exact product integral of piecewise-linear sampled rail voltages and currents',
        locked_loop_power_qualified=False,power_limit_applied=False,release_ready=False)


def run(native,output):
    if output.exists():raise FileExistsError(output)
    if json.loads((native/'status.json').read_text())['state']!='native_startup_completed_waveform_assessment_pending':raise ValueError('normally completed full-circuit native required')
    m=json.loads((native/'manifest.json').read_text());verify(m['input_sha256']);p=Path(m['supply_csv'])
    result=analyze(p,m['supply_current_sources'],200,260,260)
    paths=[p,native/'manifest.json',native/'status.json',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py')]
    result.update(input_sha256={str(x):sha(x)for x in paths},operating_point=m['operating_point'],scope=m['supply_characterization_scope'])
    save(output,result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.native.resolve(),a.output.resolve())
