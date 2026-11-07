"""Append four standard-cell keepers using only original external cell pins."""
import json
from pathlib import Path
from common_v3 import verify


def definitions(text):
    result={};current=None
    for line in text.splitlines(True):
        f=line.split()
        if f and f[0].lower()=='.subckt'and f[1].startswith('__openpll_literal_leaf_'):
            current=f[1];result[current]=[]
        if current is not None:
            result[current].append(line)
            if f and f[0].lower()=='.ends':current=None
    return result


def keeper_cards(text,cells,template):
    if len(cells)!=4 or len({c['cell']for c in cells})!=4:raise ValueError('four distinct history cells required')
    if '__history_external_'in text or 'Xhistorykeeper'in text or 'Xhistoryinv'in text:raise ValueError('new node/instance collision')
    proof=json.loads((template/'assessment.json').read_text());verify(proof['input_sha256']);verify(proof['artifacts'])
    if proof.get('internal_original_enable_complement_tapped')is not False or proof.get('external_inverter_master')!='sky130_fd_sc_hs__inv_2':raise ValueError('verified external-pin inverter proposal required')
    sample=(template/'cut.spice').read_text();olddefs=definitions(text);newdefs=definitions(sample)
    inv=[line.split()for line in sample.splitlines()if line.startswith('Xexternal_inv_0_')]
    if len(inv)!=4 or any(len(f)!=6 for f in inv):raise ValueError('four original inverter MOS cards required')
    oldY='__openpll_external_enb_0';foreign=set(n for f in inv for n in f[1:5])-{oldY,'VGND','VPWR'}
    if len(foreign)!=1:raise ValueError('unique external inverter input required')
    oldA=foreign.pop();calls={f[0]:f for line in text.splitlines()if (f:=line.split())and f[0].startswith('Xflat')}
    records=[];extra=[];needed=set()
    for i,cell in enumerate(cells):
        local=cell['local_to_native_nodes'];y='__history_external_%d_y'%i
        replacement={local['A']:local['VGND'],local['TE']:y,local['Z']:local['Z'],local['VPWR']:local['VPWR'],local['VGND']:local['VGND']}
        newnodes={label:'__history_external_%d_%s'%(i,suffix)for label,suffix in [('a_27_47#','enb'),('a_204_47#','n'),('a_276_297#','p')]}
        replacement.update({local[k]:v for k,v in newnodes.items()})
        originals=cell['flat_MOS_instances']
        if len(originals)!=6:raise ValueError('complete six-MOS original keeper geometry required')
        for j,name in enumerate(originals):
            f=calls[name]
            if len(f)!=6:raise ValueError('literal MOS card required')
            terminals=[replacement[n]for n in f[1:5]];instance='Xhistorykeeper%d_%d'%(i,j);records.append(dict(instance=instance,cell=cell['cell'],terminals=terminals,geometry_wrapper=f[5]));extra.append(instance+' '+' '.join(terminals)+' '+f[5]+'\n')
        for j,f in enumerate(inv):
            ports={oldY:y,oldA:local['TE'],'VPWR':local['VPWR'],'VGND':local['VGND']};terminals=[ports[n]for n in f[1:5]];leaf=f[5];needed.add(leaf);instance='Xhistoryinv%d_%d'%(i,j);records.append(dict(instance=instance,cell=cell['cell'],terminals=terminals,geometry_wrapper=leaf));extra.append(instance+' '+' '.join(terminals)+' '+leaf+'\n')
        allowed={local['Z'],local['TE'],local['VPWR'],local['VGND'],y,*newnodes.values()}
        if any(n not in allowed for r in records[-10:]for n in r['terminals']):raise ValueError('hidden original pin tap rejected')
    prefix=''
    for leaf in sorted(needed):
        block=newdefs[leaf]
        if len(block)!=3:raise ValueError('literal inverter wrapper required')
        if leaf in olddefs:
            if [x.split()for x in olddefs[leaf]]!=[x.split()for x in block]:raise ValueError('inverter wrapper identity mismatch')
        else:prefix+=''.join(block)
    if len(records)!=40:raise ValueError('four six-MOS keepers and four four-MOS inverters required')
    return prefix+''.join(extra),records
