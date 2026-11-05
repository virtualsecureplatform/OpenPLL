#!/usr/bin/env python3
"""Freeze a bounded live DCO prefix and report frequency evolution; never terminal qualification."""
import argparse,hashlib,json,math,re,statistics
from pathlib import Path
from audit_dco_completed_waveforms import crossings

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['wave','deck','source-validation','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--stop-ns',type=float,required=True);a=p.parse_args()
 assert not a.output.exists() and a.stop_ns>=390
 deck=a.deck.read_text();supply=float(re.search(r'(?im)^\.param VDD=(\S+)',deck)[1])
 rows=[];raw=[];beyond=False
 with a.wave.open('rb') as f:
  header=f.readline();assert header.decode().split()==['Index','TIME','V(PLLOUT)'];raw.append(header)
  for line in f:
   v=line.split()
   if not v or not v[0].isdigit():continue
   assert line.endswith(b'\n') and len(v)==3
   index,t,voltage=map(float,v);assert all(map(math.isfinite,[index,t,voltage])) and index==len(rows)
   if t>a.stop_ns*1e-9:beyond=True;break
   assert not rows or t>rows[-1][0]
   rows.append((t,voltage));raw.append(line)
 assert beyond and rows[0][0]==0 and rows[-1][0]>=(a.stop_ns-0.02)*1e-9
 windows=[]
 for start in [100,150,200,250,290,340]:
  end=start+50
  rises=[t for t in crossings(rows,supply/2,True,start*1e-9) if t<end*1e-9]
  periods=[b-a for a,b in zip(rises,rises[1:])];assert len(periods)>=3 and min(periods)>0
  windows.append({'start_ns':start,'end_ns':end,'complete_cycles':len(periods),'mean_frequency_hz':1/statistics.mean(periods)})
 assert windows[-1]['end_ns']<=a.stop_ns
 a.output.mkdir(parents=True);frozen=a.output/'wave.prefix.prn';frozen.write_bytes(b''.join(raw))
 pins=[frozen,a.deck,a.source_validation,Path(__file__),Path(__file__).with_name('audit_dco_completed_waveforms.py')]
 report={'prefix_validation_pass':True,'source_wave_growing_not_hashed':str(a.wave),'stop_ns':a.stop_ns,'last_sample_ns':rows[-1][0]*1e9,'samples':len(rows),'supply_v':supply,'windows':windows,'last_adjacent_50ns_difference_hz':abs(windows[-1]['mean_frequency_hz']-windows[-2]['mean_frequency_hz']),'sha256':{str(p):sha(p) for p in pins},'simulation_completed':False,'convergence_qualified':False,'release_qualified':False,'selected':False,'scope':'Exact raw finite monotonic bounded prefix, verified by observing a numeric sample beyond the bound. Only frozen prefix and static inputs are hashed. Frequency evolution diagnostic; no native completion, settled value, statistical noise, fullPVT or release claim. Windows250..300 and290..340 overlap; only290..340 and340..390 are the reported final adjacent pair.'}
 (a.output/'assessment.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sha256'}))
if __name__=='__main__':main()
