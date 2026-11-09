"""Exact native R contraction with explicit zero-ohm reference port aliases."""
from audit_keeper_native_R_contraction import parse,compare


def compare_with_aliases(reference,candidate):
    base=parse(reference);other=parse(candidate);parent={}
    if base['ports']!=other['ports']:raise ValueError('external port ordering or names changed')
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    for a,b,value in base['resistors']:
        if value!=0:raise ValueError('reference may contain only explicit ideal aliases')
        a,b=find(a),find(b);parent[max(a,b)]=min(a,b)
    def rewrite(text,reference=False):
        result=[]
        for line in text.splitlines():
            f=line.split()
            if not f or f[0].startswith('*'):result.append(line);continue
            kind=f[0][0].upper();indices=[]
            if f[0].lower()=='.subckt':indices=range(2,len(f))
            elif f[0]=='+':indices=range(1,len(f))
            elif kind in ['R','C']:
                if reference and kind=='R':continue
                indices=range(1,3)
            elif kind=='X':
                model=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
                indices=range(1,model)
            for i in indices:f[i]=find(f[i].lower())
            result.append(' '.join(f))
        return '\n'.join(result)+'\n'
    result=compare(rewrite(reference,True),rewrite(candidate))
    result['explicit_reference_zero_R_aliases']=len(base['resistors'])
    result['original_external_port_names_and_order_preserved']=True
    result['release_ready']=False
    return result
