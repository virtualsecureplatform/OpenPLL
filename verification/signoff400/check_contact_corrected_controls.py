"""Bind both physical endpoints of every tuning bit to a corrected native model."""
import math
from assess_keeper_physical_tuning import expected


def bind_observations(observations,nodes,ports):
    required={(bus,bit,endpoint) for bus,width in [('COARSETHERMAL_CODE',47),('DCO_THERM',255)]
              for bit in range(width) for endpoint in ['macro','DCO']}
    seen=set();roles={}
    for name,row in observations.items():
        key=(row['bus'],row['bit'],row['endpoint'])
        if key not in required or key in seen:raise ValueError('unique physical tuning endpoint required')
        seen.add(key);physical=row['physical_node']
        if physical not in nodes:raise ValueError('physical endpoint missing from corrected model')
        node=nodes[physical]
        roles[name]=node if node in ports else 'XDUT:'+node
    if seen!=required:raise ValueError('all 604 physical tuning endpoints required')
    return roles


def assess(rows,observations,coarse,fine,start_ns=280,stop_ns=340):
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-stop_ns*1e-9)>1e-18:
        raise ValueError('complete corrected capture required')
    if any(len(row)!=1+len(observations) or not all(math.isfinite(x) for x in row) for row in rows):
        raise ValueError('complete finite endpoint rows required')
    if any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise ValueError('strict time ordering required')
    window=[row for row in rows if row[0]>=start_ns*1e-9]
    if len(window)<2:raise ValueError('nonempty final observation interval required')
    checks=[]
    for i,(name,r) in enumerate(observations.items(),1):
        bit=expected(r['bus'],r['bit'],coarse,fine);low=min(row[i] for row in window);high=max(row[i] for row in window)
        checks.append(dict(role=name,expected_logic=bit,minimum_V=low,maximum_V=high,
                           passed=low>=1.44 if bit else high<=.36))
    return checks
