#!/usr/bin/env python3
"""Derive measured reset-to-rearm contracts from independently verified native audit receipts."""
import argparse,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def host(p):return Path(p.replace('/work/OpenPLL/',str(Path.cwd())+'/'))
def state_at(signal,t,threshold):
 events=sorted([(x,1) for x in signal['rising_ns']]+[(x,0) for x in signal['falling_ns']])
 if events:state=1-events[0][1]
 elif signal['maximum_v']<threshold:state=0
 elif signal['minimum_v']>threshold:state=1
 else:raise AssertionError('No crossing sequence or constant-level evidence')
 for when,value in events:
  if when>t:break
  state=value
 return state

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--coverage',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();coverage=json.loads(a.coverage.read_text());assert coverage['receipt_level_aggregation_pass']
 pins={str(a.coverage):sha(a.coverage),str(Path(__file__).resolve()):sha(Path(__file__))};records={};unavailable={}
 for case,record in coverage['cases'].items():
  receipt=Path(record['receipt']);assert sha(receipt)==coverage['sha256'][str(receipt)];j=json.loads(receipt.read_text());pins[str(receipt)]=sha(receipt)
  if 'terminal_directory' not in j:unavailable[case]='Legacy regression lacks native audit reference';continue
  native=host(j['terminal_directory'])/'native_audit.json';nested={str(host(k)):v for k,v in j['sha256'].items()};assert str(native) in nested and sha(native)==nested[str(native)];pins[str(native)]=sha(native);n=json.loads(native.read_text());assert n['native_complete_wave_audit_pass'];s=n['signals'];c=j['consumption'];threshold=c['supply_v']/2;start=j.get('withdrawal_start_ns',187.05);asserted=c['event_reset_assert_ns'];nextref=c['next_ref_opportunity_ns']
  falls=[t for t in s['READY2']['falling_ns'] if start<=t<nextref];rises=[t for t in s['READY2']['rising_ns'] if asserted<t<nextref];track=[t for t in s['TRACK_ACTIVE']['rising_ns'] if asserted<t<nextref];assert falls and rises and track,case;rearm=max(rises[0],track[0]);assert falls[0]<rearm
  clears={};quiet={}
  for name in ['UPQ','DNQ','UP1','DN1','UP2','DN2']:
   if state_at(s[name],asserted,threshold)==0:clear=asserted
   else:
    possible=[t for t in s[name]['falling_ns'] if asserted<=t<rearm];clear=min(possible) if possible else None
   clears[name]=clear
   quiet[name]=clear is not None and state_at(s[name],rearm,threshold)==0 and not any(clear<t<nextref for t in s[name]['rising_ns'])
  known=[t for t in clears.values() if t is not None];margin=rearm-max(known) if len(known)==6 else None
  records[case]={'measured_rearm_contract_pass':all(quiet.values()) and margin is not None and margin>0,'event_reset_assert_ns':asserted,'ready2_fall_ns':falls[0],'ready2_rearm_ns':rises[0],'tracking_rearm_ns':track[0],'effective_receiver_rearm_ns':rearm,'storage_clear_ns':clears,'storage_remains_low_until_next_ref':quiet,'all_storage_clear_before_rearm_margin_ns':margin,'raw_storage_clear_delay_from_event_reset_ns':max(clears[k]-asserted for k in ['UPQ','DNQ'] if clears[k] is not None),'next_ref_opportunity_ns':nextref,'native_audit':str(native)}
 passed=[k for k,r in records.items() if r['measured_rearm_contract_pass']];failed=[k for k,r in records.items() if not r['measured_rearm_contract_pass']];limiting=min(passed,key=lambda k:records[k]['all_storage_clear_before_rearm_margin_ns']) if passed else None
 report={'analysis_complete':True,'audited_cases':len(records),'measured_contract_passing_cases':len(passed),'measured_contract_failing_cases':failed,'unavailable_cases':unavailable,'minimum_observed_clear_to_rearm_margin_ns':records[limiting]['all_storage_clear_before_rearm_margin_ns'] if limiting else None,'minimum_margin_case':limiting,'records':records,'sha256':pins,'scope':'Measured half-supply crossing contracts from completed native audit receipts whose hashes match prior independent terminal receipts. Six receiver storage nodes must clear before tracking/ready rearm and stay low until first post-macro-release REF. Constant-low nodes are handled explicitly. This is finite measured-case coverage at fixedRC/ideal committed controls, not a conservative unmeasuredPVT/phase/delay or metastability bound. No native case waiver or full analog-to-formal refinement.','replacement_coverage_proven':False,'release_qualified':False,'selected':False};a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['records','sha256']}))
if __name__=='__main__':main()
