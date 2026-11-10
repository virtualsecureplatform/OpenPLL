"""Bind every negative native rnode to an original conductor using R and EXT aliases."""
import json,time
from runtime_common import ROOT,save,sha
from resources import lease

def run():
    b=ROOT/'build/signoff400';source=b/'selected_keeper_contact_corrected_full_R_1599';out=b/'selected_negative_R_cohort_1651';out.mkdir(exist_ok=False)
    ext=source/'IntegerPLL_400MHz_KeeperFlatC.ext';res=source/'IntegerPLL_400MHz_KeeperFlatC.res.ext';receipt=source/'assessment.json';r=json.loads(receipt.read_text())
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for p in [ext,res]:
            if sha(p)!=r['artifacts'][str(p)]:raise ValueError('native source changed')
        aliases={};parent={}
        def find(table,n):
            table.setdefault(n,n)
            while table[n]!=n:table[n]=table[table[n]];n=table[n]
            return n
        known=set()
        for line in ext.open():
            if line.startswith(('node ','substrate ','port ')):known.add(line.split('"')[1])
            elif line.startswith('equiv '):
                f=line.split('"');aliases[find(aliases,f[3])]=find(aliases,f[1])
        negative=[];killowners=[];owner=None
        for line in res.open():
            if line.startswith('killnode '):owner=line.split('"')[1]
            elif line.startswith('rnode '):
                f=line.split('"',2)
                if owner:killowners.append((f[1],owner))
                if f[2].split()[1].startswith('-'):negative.append(dict(node=f[1],raw_C=f[2].split()[1]))
            else:
                if line.strip():owner=None
                if line.startswith('resist '):
                    f=line.split('"');parent[find(parent,f[1])]=find(parent,f[3])
        owners={}
        for node in known:
            if node in parent:owners.setdefault(find(parent,node),set()).add(find(aliases,node))
        for node,owner in killowners:owners.setdefault(find(parent,node),set()).add(find(aliases,owner))
        conflicts=[]
        for row in negative:
            candidates=owners.get(find(parent,row['node']),set())
            if len(candidates)!=1:conflicts.append(dict(**row,candidates=sorted(candidates)))
            else:row['owner']=next(iter(candidates))
        save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [ext,res,receipt,__file__]},negative_records=negative,owner_conflicts=conflicts,requested_nets=sorted({r['owner'] for r in negative if 'owner' in r}),all_negative_native_rnodes_bound=not conflicts,release_ready=False))
        if conflicts:raise ValueError('negative rnode physical ownership unresolved')
if __name__=='__main__':run()
