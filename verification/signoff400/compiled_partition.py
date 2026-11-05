"""Existing aligned stream boundaries, using the compiled parallel event index."""
import json
from pathlib import Path
import sys
from common import ROOT, save
from compiled_charge import execute
sys.path.append(str(ROOT/'verification/timing400'))
from parallel_C_trace_ranges import find_record, lower_bound


def partition(trace, workers, deadline, binary, output, index_workers=8):
    trace,output=Path(trace),Path(output)
    path=trace/'kernels.log';size=path.stat().st_size
    end,footer=find_record(path,max(0,size-1024),b'END ')
    _,event_total,kernel_total=footer.split();event_total,kernel_total=int(event_total),int(kernel_total)
    _,surface_footer=find_record(trace/'surfaces.log',max(0,(trace/'surfaces.log').stat().st_size-1024),b'END ')
    _,owner_footer=find_record(trace/'owners.log',max(0,(trace/'owners.log').stat().st_size-1024),b'END ')
    if surface_footer.split()!=['END',str(event_total)] or int(owner_footer.split()[2])!=kernel_total:
        raise ValueError('native stream footer mismatch')
    boundaries=[]
    for i in range(workers):
        offset,row=find_record(path,size*i//workers,b'KERNEL ')
        if row is None:raise ValueError('missing kernel partition')
        _,event=find_record(path,offset,b'EVENT ')
        boundaries.append((offset,int(row.split()[1]),int(event.split()[1])-1 if event else event_total))
    boundaries.append((end,kernel_total+1,event_total))
    if boundaries[0][1:]!=(1,0) or not all(a[1]<b[1] and a[2]<=b[2] for a,b in zip(boundaries,boundaries[1:])):
        raise ValueError('invalid kernel/event partition order')
    config=output/'native_index.config.json';index_path=output/'native_index.json'
    save(config,dict(path=str(trace/'contributions.log'),output=str(index_path),workers=index_workers,
                    ranks=sorted({b[2] for b in boundaries}),deadline_uptime=deadline))
    execute([binary,'index',config],output/'native_index.log',deadline,memory_gib=4)
    index=json.loads(index_path.read_text());offsets={int(k):v for k,v in index['offsets'].items()}
    if index['events']!=event_total:raise ValueError('native event count mismatch')
    spans=[]
    for a,b in zip(boundaries,boundaries[1:]):
        spans.append(dict(kernel_start=a[1],kernel_end=b[1],event_start=a[2],event_end=b[2],
             kernels=[a[0],b[0]],contributions=[offsets[a[2]],offsets[b[2]]],
             owners=[lower_bound(trace/'owners.log',b'OWNER',k) for k in (a[1],b[1])],
             surfaces=[lower_bound(trace/'surfaces.log',b'SURFACE',e+1) for e in (a[2],b[2])]))
    spans[-1]['expected_owner_total']=int(owner_footer.split()[1])
    return spans
