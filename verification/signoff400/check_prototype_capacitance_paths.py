"""Exact sufficient energy certificate using positive-capacitance paths; no model alteration."""
import argparse,heapq,json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common import save,sha,verify


def certify(pairs):
 graph=defaultdict(list);positive={};negative=[]
 for (a,b),value in pairs.items():
  if value>0:
   edge=tuple(sorted((a,b)));positive[edge]=value
   graph[a].append((b,1/value,edge));graph[b].append((a,1/value,edge))
  elif value<0:negative.append((a,b,-value))
 loads=defaultdict(F);witnesses=[]
 for a,b,magnitude in sorted(negative):
  distances={a:F(0)};previous={};queue=[(F(0),a)]
  while queue:
   distance,node=heapq.heappop(queue)
   if distance!=distances[node]:continue
   if node==b:break
   for other,resistance,edge in graph[node]:
    new=distance+resistance
    if other not in distances or new<distances[other]:
     distances[other]=new;previous[other]=(node,edge);heapq.heappush(queue,(new,other))
  if b not in distances:return dict(passivity_certified=False,reason='negative edge has no positive path',failed_pair=[a,b])
  path=[];node=b
  while node!=a:
   node,edge=previous[node];path.append(edge)
  ratio=magnitude*distances[b]
  for edge in path:loads[edge]+=ratio
  witnesses.append(dict(negative_pair=[a,b],negative_magnitude_F=str(magnitude),positive_path=[list(e) for e in reversed(path)],allocated_fraction=str(ratio)))
 worst=max(loads.values(),default=F(0));over=[dict(pair=list(e),allocated_fraction=str(v)) for e,v in loads.items() if v>1]
 return dict(passivity_certified=not over,method='exact weighted Cauchy inequality for each positive path; summed allocations <= 1 on every positive edge',
     maximum_positive_edge_allocation=str(worst),overallocated_edges=over,witnesses=witnesses,
     negative_pairs=len(negative),positive_pairs=len(positive),strict_positive_definiteness_claimed=False)


def run(source,output):
 output.mkdir(parents=True,exist_ok=False);receipt=source/'assessment.json';a=json.loads(receipt.read_text());files=sorted(source.glob('*.pairs.jsonl'))
 paths=[receipt,*files,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};results=[];artifacts={}
 for file in files:
  if pins[str(file)]!=a['artifacts'][str(file)]:raise ValueError('aggregated capacitance changed')
  pairs={}
  for line in file.open():
   r=json.loads(line);key=tuple(r['nodes'])
   if key in pairs:raise ValueError('duplicate aggregated capacitance')
   pairs[key]=F(r['farads'])
  result=certify(pairs);report=output/(file.stem+'.proof.json');save(report,result);artifacts[str(report)]=sha(report)
  results.append(dict(top=file.name.split('.pairs')[0],passivity_certified=result['passivity_certified'],negative_pairs=result.get('negative_pairs'),maximum_positive_edge_allocation=result.get('maximum_positive_edge_allocation')))
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
   extracted_capacitor_networks_passive=bool(results) and all(r['passivity_certified'] for r in results),
   capacitances_modified=False,scope='isolated conventional hierarchical capacitor networks only; parent loading, R and device models remain separate',validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('source','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(a.source.resolve(),a.output.resolve())
