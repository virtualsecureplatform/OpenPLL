"""Measure conditional-cut reproduction and timestep differences without invented gates."""
import argparse,bisect,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify


def read(path):
    with path.open()as f:
        reader=csv.reader(f);columns=next(reader);data=[]
        if len(set(c.lower()for c in columns))!=len(columns):raise ValueError('unique CSV columns required')
        for row in reader:
            if not row or row[0].startswith('End of Xyce'):continue
            if len(row)!=len(columns):raise ValueError('complete CSV rows required')
            values=[float(x)for x in row]
            if not all(math.isfinite(x)for x in values):raise ValueError('finite waveform required')
            if data and values[0]<=data[-1][0]:raise ValueError('strictly increasing times required')
            data.append(values)
    if len(data)<2 or abs(data[0][0])>1e-20 or abs(data[-1][0]-10e-9)>1e-19:raise ValueError('complete 0--10 ns waveform required')
    return columns,data


def compare(reference,observed,ri,oi,start):
    times=[r[0]for r in reference];errors=[];actual=[];predicted=[]
    for row in observed:
        t=row[0]
        if t<start:continue
        i=max(0,min(len(times)-2,bisect.bisect_right(times,t)-1));r0,r1=reference[i:i+2]
        if t<times[0]-1e-20 or t>times[-1]+1e-20:raise ValueError('interpolation outside recorded window')
        fraction=(t-r0[0])/(r1[0]-r0[0]);value=r0[ri]+fraction*(r1[ri]-r0[ri])
        errors.append(row[oi]-value);actual.append(value);predicted.append(row[oi])
    if not errors:raise ValueError('nonempty comparison window required')
    return dict(compared_samples=len(errors),maximum_absolute_error_V=max(abs(x)for x in errors),RMS_error_V=math.sqrt(sum(x*x for x in errors)/len(errors)),reference_range_V=[min(actual),max(actual)],replay_range_V=[min(predicted),max(predicted)])


def run(prepared,runs,output):
    if output.exists():raise FileExistsError(output)
    pp=prepared/'assessment.json';rp=runs/'assessment.json';p,r=[json.loads(x.read_text())for x in [pp,rp]]
    for a in [p,r]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    if not r['both_predeclared_runs_completed'] or r['input_sha256'].get(str(pp))!=sha(pp):raise ValueError('both normal runs of identical prepared decks required')
    rc,ref=read(prepared/'recorded.csv');datasets={label:read(prepared/(label+'.csv'))for label in ['base','refined']}
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique prepared cut receipt required')
    assessment=json.loads(cuts[0].read_text())
    nodes=assessment['internal_nodes'];results={}
    for node in nodes:
        ri=rc.index(node);item={}
        for label,(columns,data)in datasets.items():
            keys=[c.lower()for c in columns];oi=keys.index(('V(XCUT:'+node+')').lower())
            item[label]={window:compare(ref,data,ri,oi,start)for window,start in [('whole_window',0.),('after_first_cycle',2.5e-9)]}
        bc,base=datasets['base'];fc,fine=datasets['refined'];name=('V(XCUT:'+node+')').lower()
        item['timestep_difference_after_first_cycle']=compare(base,fine,[c.lower()for c in bc].index(name),[c.lower()for c in fc].index(name),2.5e-9)
        results[node]=item
    files=[pp,rp,prepared/'recorded.csv',prepared/'base.csv',prepared/'refined.csv',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py')]
    output.mkdir(parents=True);save(output/'assessment.json',dict(input_sha256={str(x):sha(x)for x in files},internal_node_results=results,comparison_window_ns=[200,210],post_initial_cycle_window_ns=[202.5,210],numerical_acceptance_threshold_applied=False,conditional_boundary_replay_only=True,causality_proven=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','runs','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.runs.resolve(),a.output.resolve())
