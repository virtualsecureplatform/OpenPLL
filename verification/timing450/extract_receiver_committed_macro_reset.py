#!/usr/bin/env python3
"""Extract actual mapped reset-release receiver with explicit committed fine-bundle and divided-clock boundaries."""
import argparse,collections,hashlib,json,re
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=Path(__file__).resolve().parents[2];out=args.output.resolve();out.mkdir(parents=True)
root=base/'build/timing450/hs/closure/handoff_candidate/build/timing450/hs/closure/iteration_026/variant_hot_electrical/build/timing450/hs'
netlist=root/'route.v';spef=root/'route.max.normalized.spef'
libroot=base/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs'
spice=libroot/'spice/sky130_fd_sc_hs.spice';liberty=libroot/'lib/sky130_fd_sc_hs__ss_100C_1v60.lib'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def semantic(x):return re.sub(r'\s+','',x).replace('\\','')

prior=base/'build/timing450/interface_characterization/receiver_fixture/extraction.json'
prior_evidence=json.loads(prior.read_text())
inputs={str(p):sha(p) for p in (netlist,spef,spice,liberty,prior,Path(__file__).resolve())}
for p in (netlist,spef,spice,liberty):
 matches=[h for name,h in prior_evidence['sha256'].items() if name.endswith('/'+str(p.relative_to(base)))]
 assert len(matches)==1 and sha(p)==matches[0],('Missing or stale checkpoint input',p)

cells={}
for typ,name,body in re.findall(r'^ (sky130_fd_sc_hs__\w+)\s+(\S+)\s+\((.*?)\);',netlist.read_text(),re.M|re.S):
 name=semantic(name);assert name not in cells
 cells[name]=(typ,{p:semantic(n) for p,n in re.findall(r'\.(\w+)\(([^)]*)\)',body)})
drivers={}
for name,(typ,ports) in cells.items():
 for port,net in ports.items():
  if port in ('X','Y','Q','Q_N'):
   assert net not in drivers;drivers[net]=(name,port)
selected=set();terminals={'BBPD[0]','BBPD[1]','PLLOUT','REFCLK','RESET_N','$abc$125535$new_n2254','handoff.APPLIED_COMMAND[13]','net','net469','net470'}
top_inputs=set()
for hi,lo,name in re.findall(r'^ input (?:\[(\d+):(\d+)\] )?(\w+);',netlist.read_text(),re.M):
 top_inputs.update([name] if not hi else [f'{name}[{i}]' for i in range(int(lo),int(hi)+1)])
assert {'REFCLK','PLLOUT','RESET_N','PLL_ENABLE'}<=top_inputs
terminals.update(top_inputs)
committed_boundaries = {'core.feedback_divider.CLKDIV_RETIMED': 'COMMITTED_FINE_CLOCK',
                        'gen_feedback_handoff.fine_handoff.APPLIED_COMMAND[13]': 'COMMITTED_FINE_RUN'}
for bit in range(6):
    committed_boundaries[f'acquisition.COARSE_CODE[{bit}]'] = f'COMMITTED_COARSE_{bit}'
    committed_boundaries[f'gen_feedback_handoff.fine_handoff.APPLIED_COMMAND[{28+bit}]'] = f'COMMITTED_FINE_COARSE_{bit}'
assert all(net in drivers for net in committed_boundaries)
terminals.update(committed_boundaries)

tie_sources={net:(name,pin) for name,(typ,ports) in cells.items() for pin,net in ports.items() if pin in ('HI','LO')}
terminals.update(tie_sources)
def visit(net):
 if net in terminals:return
 name,_=drivers[net]
 if name in selected:return
 selected.add(name);typ,ports=cells[name]
 for port,net in ports.items():
  if port not in ('X','Y','Q','Q_N'):visit(net)
for net in ('export_alias_0_out','core.bbpd_up_event_toggle','core.bbpd_dn_event_toggle','core.gen_event_cdc.up_pipe[1]','core.gen_event_cdc.dn_pipe[1]','core.gen_event_cdc.capture_pipe[1]'):visit(net)
assert len([n for n in selected if '__dfrtp_' in cells[n][0]])>=12
nets={net for n in selected for p,net in cells[n][1].items() }
# Include the actual attached antenna diodes rather than invent a Liberty input C.
connected_diodes={name for name,(typ,ports) in cells.items() if typ=='sky130_fd_sc_hs__diode_2' and ports.get('DIODE') in nets}
selected.update(connected_diodes)
nets={net for n in selected for p,net in cells[n][1].items() }
s=spef.read_text();assert '*C_UNIT 1 PF' in s and '*R_UNIT 1 OHM' in s and '"PIN_CAP NONE"' in s
names={int(i):n.replace('\\','') for i,n in re.findall(r'^\*(\d+) (\S+)$',s,re.M)}
def decode(token):
 m=re.fullmatch(r'\*(\d+)(:.*)?',token)
 return names[int(m[1])]+(m[2] or '') if m else token
blocks={names[int(i)]:b for i,b in re.findall(r'^\*D_NET \*(\d+) ([\s\S]*?)^\*END',s,re.M)}
assert nets<=blocks.keys()
subcircuits={name:(ports,body) for name,ports,body in re.findall(r'^\.subckt (\S+) ([^\n]+)\n([\s\S]*?)^\.ends(?:[^\n]*)$',spice.read_text(),re.M)}
# Read directly nested Liberty cell/pin blocks; do not infer pin capacitance from total wire C.
def block(text,pattern):
 m=re.search(pattern,text);assert m is not None,pattern
 start=m.end();depth=1;i=start
 while depth:
  depth+= (text[i]=='{')-(text[i]=='}');i+=1
 return text[start:i-1]
lib=liberty.read_text()
def pin_cap(typ,pin):
 c=block(lib,r'cell\s*\("?'+re.escape(typ)+r'"?\)\s*\{')
 p=block(c,r'pin\s*\("?'+re.escape(pin)+r'"?\)\s*\{')
 m=re.search(r'\bcapacitance\s*:\s*([\d.eE+-]+)',p);assert m, (typ,pin)
 return float(m[1])
resistors=[];caps=collections.Counter();outside=[];conn={};coupling={};alllocal=set()
for net in sorted(nets):
 b=blocks[net];con=b.split('*CONN\n')[1].split('*CAP\n')[0];rtext=b.split('*RES\n')[1]
 local=set()
 for line in con.splitlines():
  f=line.split()
  if f[0] in ('*I','*P'):
   node=decode(f[1]);local.add(node)
   if f[0]=='*I':
    instance,pin=node.rsplit(':',1);conn[instance,pin]=node
    if instance not in selected and f[2]=='I':
     typ=f[-1];assert cells[instance][0]==typ
     value=pin_cap(typ,pin);outside.append({'instance':instance,'pin':pin,'capacitance_pf':value});caps[node]+=value
 for line in rtext.splitlines():
  if not line.strip():continue
  f=line.split();assert len(f)==4
  a,z=map(decode,f[1:3]);value=float(f[3]);assert value>0
  resistors.append((a,z,value));local.update((a,z))
 alllocal.update(local)
 coupling[net]=(local,b.split('*CAP\n')[1].split('*RES\n')[0])
# Ground capacitances to omitted, static aggressors; retain in-cone coupling once.
counts=[]
for net,(local,ctext) in coupling.items():
 counter=collections.Counter()
 for line in ctext.splitlines():
  f=line.split()
  if not f:continue
  assert len(f) in (3,4)
  value=float(f[-1]);assert value>=0
  if value==0:continue
  if len(f)==3:caps[decode(f[1])]+=value;continue
  a,z=map(decode,f[1:3]);assert a in local or z in local
  if a in alllocal and z in alllocal:counter[tuple(sorted((a,z)))+(value,)]+=1
  else:caps[a if a in local else z]+=value
 counts.append(counter)
merged=collections.Counter()
for counter in counts:merged|=counter
node_names={'BBPD[0]':'BBPD0','BBPD[1]':'BBPD1','PLLOUT':'PLLOUT','REFCLK':'REFCLK','RESET_N':'RESET_N','BBPD_RESET_N':'BBPD_RESET_N'}
for net,port in [('core.bbpd_up_event_toggle','UPQ'),('core.bbpd_dn_event_toggle','DNQ'),('core.gen_event_cdc.up_pipe[0]','UP1'),('core.gen_event_cdc.up_pipe[1]','UP2'),('core.gen_event_cdc.dn_pipe[0]','DN1'),('core.gen_event_cdc.dn_pipe[1]','DN2'),('core.gen_event_cdc.capture_pipe[0]','READY1'),('core.gen_event_cdc.capture_pipe[1]','READY2'),('core.bbpd_event_reset_n','EVENT_RESET_N'),('net473','PIPE_RESET_N'),('track_pipe[1]','TRACK_ACTIVE')]:
 name,pin=drivers[net];node_names[conn[name,pin]]=port
for net,clock,data in [('core.gen_event_cdc.up_pipe[0]','CLKUP1','DATAUP1'),('core.gen_event_cdc.dn_pipe[0]','CLKDN1','DATADN1')]:
 name,_=drivers[net]
 node_names[conn[name,'CLK']]=clock
 node_names[conn[name,'D']]=data
for net,alias in [('net','TIE_HIGH'),('net469','TIE_HIGH1'),('net470','TIE_HIGH2')]:
 tie_drivers=[name for name,(typ,ports) in cells.items() if ports.get('HI')==net]
 assert len(tie_drivers)==1
 node_names[conn[tie_drivers[0],'HI']]=alias
for net,alias in [('$abc$125535$new_n2254','ACQ_INACTIVE'),('handoff.APPLIED_COMMAND[13]','COMMAND_RUN')]:
 name,pin=drivers[net];assert name not in selected
 node_names[conn[name,pin]]=alias
for net, alias in committed_boundaries.items():
 name,pin=drivers[net];assert name not in selected
 node_names[conn[name,pin]]=alias
extra_ties=sorted(net for net in nets if net in tie_sources and net not in ('net','net469','net470'))
for index,net in enumerate(extra_ties):
 name,pin=tie_sources[net];node_names[conn[name,pin]]='EXTRA_TIE_'+str(index)
config_inputs=sorted(net for net in nets if net in top_inputs and net not in ('BBPD[0]','BBPD[1]','PLLOUT','REFCLK','RESET_N'))
for net in config_inputs:node_names[net]='CONFIG_'+re.sub(r'[^A-Za-z0-9_]','_',net)
for node in sorted(alllocal):node_names.setdefault(node,'n'+str(len(node_names)))
lines=['* Diagnostic mapped receiver cone: SS maximum routed RC, static omitted aggressors.',
 '.subckt bbpd_receiver_cdc BBPD0 BBPD1 PLLOUT REFCLK RESET_N ACQ_INACTIVE COMMAND_RUN VGND VNB VPB VPWR UPQ DNQ UP1 UP2 DN1 DN2 CLKUP1 DATAUP1 CLKDN1 DATADN1 TIE_HIGH TIE_HIGH1 TIE_HIGH2 READY1 READY2 EVENT_RESET_N PIPE_RESET_N TRACK_ACTIVE BBPD_RESET_N'+' '+ ' '.join(committed_boundaries.values())+' '+ ' '.join(node_names[n] for n in config_inputs)+' '+' '.join(node_names[conn[tie_sources[n]]] for n in extra_ties)]
for i,name in enumerate(sorted(selected)):
 typ,ports=cells[name];ordered=subcircuits[typ][0].split();actual=[]
 for pin in ordered:
  if pin in ('VGND','VNB','VPB','VPWR'):actual.append(pin)
  else:
   assert pin in ports,(name,pin)
   actual.append(node_names[conn[name,pin]])
 lines.append('Xcell'+str(i)+' '+' '.join(actual)+' '+typ)
for i,(a,z,value) in enumerate(resistors):lines.append(f'Rwire{i} {node_names[a]} {node_names[z]} {value:.12g}')
for i,(node,value) in enumerate(sorted(caps.items())):lines.append(f'Cground{i} {node_names[node]} VGND {value:.12g}p')
i=0
for (a,z,value),count in sorted(merged.items()):
 for _ in range(count):lines.append(f'Ccoupled{i} {node_names[a]} {node_names[z]} {value:.12g}p');i+=1
lines.append('.ends bbpd_receiver_cdc')
for typ in sorted({cells[n][0] for n in selected}):
 ports,body=subcircuits[typ];lines.extend(['.subckt '+typ+' '+ports,body,'.ends '+typ])
output=out/'receiver.spice';output.write_text('\n'.join(lines)+'\n')
receipt={'included_bbpd_reset_export':True,'committed_boundaries':committed_boundaries,'additional_tie_ports':{node_names[conn[tie_sources[n]]]:int(tie_sources[n][1]=='HI') for n in extra_ties},'external_configuration_ports':{n:node_names[n] for n in config_inputs},'selected_cells':{name:{'type':cells[name][0],'ports':cells[name][1]} for name in sorted(selected)},
 'routed_net_count':len(nets),'resistors':len(resistors),'ground_caps':len(caps),'coupling_caps':i,
 'excluded_receiver_pin_capacitance':outside,'release_qualified':False,'selected':False,
 'limitations':['SS max-RC network, omitted aggressors held static at ground','Both tracking synchronizer stages and their clock paths are nonlinear; omitted output loads use linear Liberty input capacitance','External reset and committed fast/fine RUN/coarse/divided-clock sources are ideal; preserves physical reset-release logic, fine reset synchronizer, comparator, clock paths and macro-reset export; does not qualify acquisition/handoff generation'],
 'sha256':{str(p):sha(p) for p in (netlist,spef,spice,liberty,output,Path(__file__).resolve())}}
for path,digest in inputs.items():assert sha(Path(path))==digest,('Changed extraction input',path)
receipt['sha256'].update(inputs)
(out/'extraction.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('selected_cells','sha256','excluded_receiver_pin_capacitance')},indent=2))
