#!/usr/bin/env python3
"""Run exactly one observation-only DCO diagnostic, preserving its reference inputs."""
import argparse,hashlib,json,math,subprocess
from pathlib import Path
from datetime import datetime,timezone

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,j):p.write_text(json.dumps(j,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();b=a.directory.resolve();assert not (b/'launch.json').exists()
 prep=json.loads((b/'preparation.json').read_text());deck=b/'probe.spice';ref=Path(prep['reference_deck']);provenance=Path(prep['reference_provenance']);saved=json.loads(provenance.read_text());assert saved['completed']
 assert sha(deck)==prep['prepared_deck_sha256'] and sha(ref)==prep['reference_deck_sha256'] and sha(provenance)==prep['reference_provenance_sha256']
 source=ref.read_text();text=deck.read_text();old=[l for l in source.splitlines() if l.startswith('.print ')];new=[l for l in text.splitlines() if l.startswith('.print ')];assert len(old)==len(new)==1 and new[0].startswith(old[0]+' ');assert text.replace(new[0],old[0])==source
 pins=dict(saved['files'])
 for f,wanted in pins.items():assert sha(f)==wanted,f
 for f in [ref,provenance,deck,b/'preparation.json',b/'topology_check.log',Path(__file__).resolve()]:pins[str(f)]=sha(f)
 topology=(b/'topology_check.log').read_text();assert 'Netlist error' not in topology and 'Fatal' not in topology
 argv=['/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',str(b/'probe'),str(deck)]
 with (b/'run.log').open('wb') as out:
  child=subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT)
  save(b/'launch.json',{'observed_utc':datetime.now(timezone.utc).isoformat(),'native_pid':child.pid,'argv':argv,'sha256':pins,'scope':prep['scope'],'release_qualified':False,'selected':False})
  code=child.wait()
 result={'exit_code':code,'simulation_completed':False,'scope':prep['scope'],'release_qualified':False,'selected':False,'sha256':pins}
 if code==0:
  wave=b/'probe.prn';header=None;count=0;last=-1;finite=True
  with wave.open() as stream:
   header=stream.readline().split();assert len(header)==17 and header[:3]==['Index','TIME','V(PLLOUT)']
   for line in stream:
    x=line.split()
    if not x or not x[0].isdigit():continue
    values=list(map(float,x));assert len(values)==len(header) and int(values[0])==count and all(map(math.isfinite,values)) and values[1]>last
    count+=1;last=values[1]
  assert last>=299.999e-9 and 'End of Xyce(TM) Simulation' in (b/'run.log').read_text()
  for f in [wave,b/'run.log']:result['sha256'][str(f)]=sha(f)
  result.update(simulation_completed=True,finite_monotonic_observations=True,columns=header,samples=count,last_sample_ns=last*1e9,interpretation_pending=True)
 save(b/'assessment.json',result)
if __name__=='__main__':main()
