#!/usr/bin/env python3
"""Trace observed DCO internal nodes to nominal static gate controls; not dynamic device proof."""
import argparse,hashlib,json,re
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['rcx','deck','prefix','output']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();assert not a.output.exists();parent={};devices=[]
 def root(n):
  n=n.lower();parent.setdefault(n,n)
  while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
  return n
 for line in a.rcx.read_text().splitlines():
  t=line.split()
  if not t or t[0].startswith('*'):continue
  if t[0][0].lower()=='r':parent[root(t[1])]=root(t[2])
  elif t[0][0].lower()=='x':devices.append((t[0],t[1:5],t[5]))
 supply=float(re.search(r'(?m)^\.param VDD=(\S+)',a.deck.read_text())[1]);fixed={}
 for line in a.deck.read_text().splitlines():
  t=line.split()
  if len(t)==4 and t[0].startswith('VCTRL') and t[2]=='0' and t[3] in ['0','{VDD}']:fixed[root(t[1])]={'port':t[1],'voltage_v':0.0 if t[3]=='0' else supply}
 rails={root('vpwr'):supply,root('vgnd'):0.0};prefix=json.loads(a.prefix.read_text());records={}
 targets=['a_14279_2767.t1','a_5263_22057.t0','a_11059_3087.t0']
 for target in targets:
  attached=[]
  for name,ns,model in devices:
   if root(target) not in [root(ns[0]),root(ns[2])]:continue
   gate=root(ns[1]);control=fixed.get(gate);inverter=[];nominal=control['voltage_v'] if control else None
   if control is None:
    for n2,x2,m2 in devices:
     ds=[root(x2[0]),root(x2[2])]
     if gate not in ds or root(x2[1]) not in fixed:continue
     other=ds[1] if ds[0]==gate else ds[0]
     if other in rails:inverter.append({'instance':n2,'model':m2,'control':fixed[root(x2[1])],'rail_voltage_v':rails[other]})
    if len(inverter)==2 and {d['rail_voltage_v'] for d in inverter}=={0.0,supply} and len({d['control']['port'] for d in inverter})==1 and any('pfet' in d['model'] for d in inverter) and any('nfet' in d['model'] for d in inverter):nominal=supply-inverter[0]['control']['voltage_v']
   off=nominal is not None and (('pfet' in model and nominal==supply) or ('nfet' in model and nominal==0))
   attached.append({'instance':name,'model':model,'nodes_D_G_S_B':ns,'direct_fixed_control':control,'nominal_inverter_driver_candidates':inverter,'inferred_nominal_gate_voltage_v':nominal,'nominal_static_control_disables_device':off})
  key='V(XDUT:'+target.upper()+')';assert key in prefix['last_minus_first_cycle_mean_voltage_v'];assert len(attached)>=2
  records[target]={'attached_channel_devices':attached,'last_minus_first_cycle_mean_voltage_v':prefix['last_minus_first_cycle_mean_voltage_v'][key],'nominally_disabled_rail_device_present':any(x['nominal_static_control_disables_device'] for x in attached)}
 files=[a.rcx,a.deck,a.prefix,Path(__file__)];report={'analysis_complete':True,'records':records,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'scope':'Resistor-component identity and MOS connectivity from the immutable extracted netlist. Static TE values and verified CMOS-inverter topology infer nominal gate drive; gate voltage/on-off conductance is not measured here. Observed complete-cycle means cover early5..20ns startup only. Disabled-branch internal charge relaxation is a supported hypothesis, not a proven cause of late frequency drift, a defect, or a qualified physical fix.','late_settling_cause_proven':False,'release_qualified':False,'selected':False};a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'nodes':list(records),'nominally_disabled_rail_devices':[k for k,v in records.items() if v['nominally_disabled_rail_device_present']],'scope':report['scope']}))
if __name__=='__main__':main()
