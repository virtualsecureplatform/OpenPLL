#!/usr/bin/env python3
"""Compare available HS corner tables; sampled ordering does not certify PVT enclosure."""
import argparse,hashlib,itertools,json,re
from bisect import bisect_right
from collections import Counter
from pathlib import Path

def tables(cell):
 result={}
 for name,pin in cell.items():
  if not name.startswith('pin,') or not isinstance(pin,dict):continue
  timing=pin.get('timing',[])
  if isinstance(timing,dict):timing=[timing]
  for arc in timing:
   identity=tuple(str(arc.get(k,'')) for k in ['related_pin','timing_type','timing_sense','when'])
   for key,value in arc.items():
    if key.split(',')[0] not in ['cell_rise','cell_fall','rise_transition','fall_transition','rise_constraint','fall_constraint']:continue
    target=(name,*identity,key);assert target not in result,target;result[target]=value
 return result

def flat(value):
 if isinstance(value,list):
  return [x for v in value for x in flat(v)]
 assert isinstance(value,(int,float));return [float(value)]

def interpolate(table, point):
 axes=[table[k] for k in sorted(table) if k.startswith('index_')]
 assert 1<=len(axes)<=2 and len(axes)==len(point)
 weights=[]
 for axis,x in zip(axes,point):
  assert all(a<b for a,b in zip(axis,axis[1:])) and axis[0]<=x<=axis[-1]
  lo=min(max(bisect_right(axis,x)-1,0),len(axis)-2);hi=lo+1
  fraction=(x-axis[lo])/(axis[hi]-axis[lo]);weights.append([(lo,1-fraction),(hi,fraction)])
 values=flat(table['values']);assert len(values)==len(axes[0])*(len(axes[1]) if len(axes)==2 else 1)
 result=0.0
 for combo in itertools.product(*weights):
  index=combo[0][0] if len(axes)==1 else combo[0][0]*len(axes[1])+combo[1][0]
  weight=1
  for _,w in combo:weight*=w
  result+=weight*values[index]
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['route','source','output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--reference',required=True);p.add_argument('--candidate',required=True);a=p.parse_args();assert not a.output.exists()
 used=sorted(set(re.findall(r'\bsky130_fd_sc_hs__\w+_[0-9]+\b',a.route.read_text())));pins={str(a.route):hashlib.sha256(a.route.read_bytes()).hexdigest(),str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};records={};counter=Counter();failures=[];missing=[];different_axes=0
 for cell in used:
  family=cell.split('__')[1].rsplit('_',1)[0];paths=[a.source/'cells'/family/(cell+'__'+suffix+'.lib.json') for suffix in [a.reference,a.candidate]]
  if not all(p.exists() for p in paths):missing.append(cell);continue
  for path in paths:pins[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
  gold,new=[tables(json.loads(p.read_text())) for p in paths];assert set(gold)==set(new),cell
  cellcounts=Counter()
  for identity,table in gold.items():
   other=new[identity];kind=identity[-1].split(',')[0]
   axes={k:v for k,v in table.items() if k.startswith('index_')};newaxes={k:v for k,v in other.items() if k.startswith('index_')};assert set(axes)==set(newaxes)
   different_axes+=axes!=newaxes;knots=[]
   for axis in sorted(axes):
    low=max(axes[axis][0],newaxes[axis][0]);high=min(axes[axis][-1],newaxes[axis][-1]);assert low<high
    knots.append(sorted({x for x in axes[axis]+newaxes[axis] if low<=x<=high}))
   for index,point in enumerate(itertools.product(*knots)):
    x,y=interpolate(table,point),interpolate(other,point)
    ordering='greater' if y>x+1e-9 else 'less' if y<x-1e-9 else 'equal';counter[kind+'_'+ordering]+=1;cellcounts[ordering]+=1
    if ordering=='less':failures.append({'cell':cell,'arc':identity,'entry':index,'slew_load_coordinates':point,'reference_ns':x,'candidate_ns':y,'difference_ns':y-x})
  records[cell]=dict(cellcounts)
 report={'analysis_complete':True,'reference_corner':a.reference,'candidate_corner':a.candidate,'used_cell_types':len(used),'compared_cell_types':len(records),'missing_cell_types':missing,'table_entry_orderings':dict(counter),'tables_with_different_axes':different_axes,'candidate_interpolant_not_less_in_common_domain':not missing and not failures,'candidate_smaller_entries':len(failures),'largest_smaller_entries':sorted(failures,key=lambda x:x['difference_ns'])[:30],'per_cell_orderings':records,'sha256':pins,'scope':'Actual used-cell source JSON LUTs compared by bilinear interpolation at the union of knots within each common slew/load rectangle; no extrapolation. Differences of the two bilinear interpolants attain extrema at these vertices within each shared grid cell, up to numerical comparison tolerance1e-9ns. This compares interpolants at two characterized corners, not true physical behavior between them. More delay or a larger setup/hold/recovery/removal constraint may be conservative for one check but not another; no operating-range enclosure, mixed-process corner dominance, interpolation monotonicity or release qualification is established.','operating_range_enclosure_proven':False,'release_qualified':False,'selected':False};a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['sha256','per_cell_orderings','largest_smaller_entries']}))
if __name__=='__main__':main()
