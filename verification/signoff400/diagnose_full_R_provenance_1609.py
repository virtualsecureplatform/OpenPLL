"""Classify full-R terminal differences without changing or accepting the export."""
import json,time,resource,shlex
from collections import Counter
from runtime_common import ROOT,save,sha
from resources import lease
from audit_keeper_native_R_contraction import parse

def run():
    b=ROOT/'build/signoff400';source=b/'selected_keeper_contact_corrected_full_R_1599';out=b/'selected_keeper_full_R_provenance_diagnosis_1609';out.mkdir(exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    with lease(1,12,deadline):
        resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
        record=json.loads((source/'assessment.json').read_text())
        if not record['native_process_completed']:raise ValueError('completed export required')
        for name in ['before.spice','after.spice']:
            if record['artifacts'][str(source/name)]!=sha(source/name):raise ValueError('export digest changed')
        before=parse((source/'before.spice').read_text());after=parse((source/'after.spice').read_text());parent={}
        def find(n):
            parent.setdefault(n,n)
            while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
            return n
        for a,z,value in after['resistors']:parent[find(a)]=find(z)
        known={n for _,nodes,_ in before['devices'] for n in nodes}|set(before['ports'])
        groups={}
        for n in known:groups.setdefault(find(n),set()).add(n)
        provenance={};owner=None;conflicts=[]
        for line in (source/'IntegerPLL_400MHz_KeeperFlatC.res.ext').open():
            if line.startswith('killnode '):
                owner=shlex.split(line)[1].lower()
            elif line.startswith('rnode ') and owner is not None:
                node=shlex.split(line)[1].lower();component=find(node)
                if component in provenance and provenance[component]!=owner:
                    conflicts.append([provenance[component],owner])
                provenance[component]=owner
            elif line.strip():owner=None
        def original(n):
            component=find(n)
            return provenance.get(component,next(iter(groups.get(component,{n}))))
        counts=Counter();examples=[]

        if len(before['devices'])!=len(after['devices']):raise ValueError('primitive sequence counts differ')
        for index,(a,z) in enumerate(zip(before['devices'],after['devices'])):
            if index%1000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('diagnosis deadline')
            if a[0]!=z[0] or a[2]!=z[2]:counts['model_or_parameter_changes']+=1;examples.append(dict(parameter_change_index=index,reference=str(a),candidate=str(z)))
            changed=[]
            for terminal,(old,new) in enumerate(zip(a[1],z[1])):
                if old!=original(new):
                    counts[f'terminal_{terminal}_mismatch']+=1;changed.append(dict(terminal=terminal,reference=old,candidate=new,candidate_component_reference_nodes=sorted(groups.get(find(new),set()))))
            if changed and len(examples)<12:examples.append(dict(sequence_index=index,model=a[0],differences=changed))
        negative=[dict(a=a,b=z,value_F=str(v)) for a,z,v in after['caps'] if v<0]
        save(out/'assessment.json',dict(input_sha256={str(source/'assessment.json'):sha(source/'assessment.json'),str(__file__):sha(__file__)},ordered_sequence_diagnostic_only=True,counts=dict(counts),provenance_components=len(provenance),conflicting_native_owners=conflicts,examples=examples,negative_C_count=len(negative),negative_C_examples=negative[:12],export_modified=False,RC_export_fixed=False,release_ready=False))

if __name__=='__main__':run()
