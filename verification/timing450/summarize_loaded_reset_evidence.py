#!/usr/bin/env python3
"""Map independent reset receipts to required coverage and observed timing envelopes."""
import argparse,hashlib,itertools,json,re
from collections import Counter
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def host(p):return Path(p.replace('/work/OpenPLL/',str(Path.cwd())+'/'))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--engineering',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 spec=json.loads(a.engineering.read_text());assert spec['modes_mhz']==[100,250,300,400,450]
 a.output.mkdir();pins={str(a.engineering):sha(a.engineering),str(Path(__file__).resolve()):sha(Path(__file__))};records={};retained=[]
 for label,directory in [('450','receiver_loaded_reset_campaign_independent_terminals_001'),('lower','receiver_loaded_reset_remaining_modes_native_001')]:
  raw=(a.root/directory/'status.json').read_bytes();f=a.output/(label+'_discovery_snapshot.json');f.write_bytes(raw);pins[str(f)]=sha(f);status=json.loads(raw)
  for key,case in status['cases'].items():
   if not case.get('terminal'):continue
   if not case.get('independent_verification_pass'):
    retained.append({'case':key,'reason':'terminal without positive independent verification','source':label});continue
   if label=='450' and case['mode_mhz']!=450:continue
   if 'reused_regression' in case:
    path=host(case['reused_regression']);assert sha(path)==case['regression_sha256'];j=json.loads(path.read_text());assert j['pass']
    assert key in ['450MHz_ss_1.62V_125C_-250ps_20ps','450MHz_ss_1.62V_125C_+250ps_20ps']
    direction='DN' if '_-250ps_' in key else 'UP';r=j['records'][direction]
    assert r['pass'] and r['direction_control_rejected'] and r['fresh_events']==[[direction,300.1]]
    pins[str(path)]=sha(path);records[key]={'receipt':str(path),'mode_mhz':450,'corner':'ss','supply_v':1.62,'temperature_c':125,'phase_ps':-250 if direction=='DN' else 250,'edge_ps':20,'timing_metrics_available':False,'scope':'Previously independent full-clock regression; timing-envelope fields not present in this receipt.'}
    continue
   path=host(case.get('independent_assessment',case.get('independent_receipt',case.get('directory','')+'_independent.json')));assert path.is_file(),(key,path)
   digest=sha(path);assert digest==case['independent_assessment_sha256'],key;j=json.loads(path.read_text());assert j['pass'];pins[str(path)]=digest
   match=re.fullmatch(r'(100|250|300|400|450)MHz_(tt|ff|ss|sf|fs)_(1\.62|1\.8|1\.95)V_(-40|27|125)C_([+-]250)ps_(20|200)ps',key);assert match,key
   mode,corner,vdd,temp,phase,edge=match.groups();mode=int(mode);vdd=float(vdd);temp=int(temp);phase=int(phase);edge=int(edge);c=j['consumption']
   assert j['mode_mhz']==mode and j['pvt']=={'corner':corner,'supply_v':vdd,'temperature_c':temp}
   withdraw=j.get('withdrawal_start_ns',187.05);assert withdraw==(207.05 if mode==100 else 187.05)
   assert c['pass'] and c['physical_storage_loaded_before_withdrawal'] and len(c['pre_withdrawal_consumed_events'])==len(c['fresh_events'])==1
   assert not c['stale_events_after_reset_before_next_ref'] and not c['opposite_events']
   assert key not in records
   records[key]={'receipt':str(path),'mode_mhz':mode,'corner':corner,'supply_v':vdd,'temperature_c':temp,'phase_ps':phase,'edge_ps':edge,'event_reset_assert_delay_from_withdrawal_start_ns':c['event_reset_assert_ns']-withdraw,'macro_reset_assert_delay_from_event_ns':c['macro_reset_assert_ns']-c['event_reset_assert_ns'],'macro_reset_hold_ns':c['macro_reset_release_ns']-c['macro_reset_assert_ns'],'macro_release_to_next_ref_ns':c['next_ref_opportunity_ns']-c['macro_reset_release_ns'],'fresh_consumption_after_next_ref_ns':c['fresh_events'][0][1]-c['next_ref_opportunity_ns']}
 expected={f'{m}MHz_{c}_{v:g}V_{t}C_{phase:+d}ps_{edge}ps' for m,c,v,t,phase,edge in itertools.product(spec['modes_mhz'],spec['corners'],spec['voltages'],spec['temperatures_c'],[-250,250],[20,200])};assert len(expected)==900 and set(records)<=expected
 metrics=sorted({k for r in records.values() for k in r if k.endswith('_ns')});envelopes={}
 for metric in metrics:
  ordered=sorted((k for k in records if metric in records[k]),key=lambda k:records[k][metric]);envelopes[metric]={'minimum_ns':records[ordered[0]][metric],'minimum_case':ordered[0],'maximum_ns':records[ordered[-1]][metric],'maximum_case':ordered[-1]}
 coverage={str(m):{'passing_cases':sum(r['mode_mhz']==m for r in records.values()),'fully_covered_pvt_points':sum(all(f'{m}MHz_{c}_{v:g}V_{t}C_{phase:+d}ps_{edge}ps' in records for phase,edge in itertools.product([-250,250],[20,200])) for c,v,t in itertools.product(spec['corners'],spec['voltages'],spec['temperatures_c'])),'required_pvt_points':45} for m in spec['modes_mhz']}
 report={'receipt_level_aggregation_pass':True,'passing_cases':len(records),'expected_cartesian_cases':900,'coverage_by_mode':coverage,'observed_envelopes':envelopes,'cases':records,'missing_cases':sorted(expected-set(records)),'retained_terminal_without_positive_verification':retained,'sha256':pins,'all_nested_receipt_evidence_reverified_here':False,'scope':'Receipt-level aggregation with hash identity against frozen discovery snapshots; prior independent verifiers checked nested artifacts. Observed finite-sample extrema are not conservative PVT/phase/RC/metastability bounds. No unmeasured case is waived or inferred to pass. Fixed RC/ideal-control fixture limitations remain. Requires independently validated bounds and full digital invariant proofs before replacing native cases.','replacement_coverage_proven':False,'release_qualified':False,'selected':False}
 (a.output/'assessment.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passing_cases','coverage_by_mode','observed_envelopes']}))
if __name__=='__main__':main()
