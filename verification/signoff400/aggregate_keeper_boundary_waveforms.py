"""Construct weighted forcing samples with exact, samplewise roundoff auditing.

This helper does not authorize native replay or qualify its dynamic error.
"""
import math
from fractions import Fraction as F
import numpy as np


def aggregate(array, columns, bindings, certificate):
    order=columns['ordered_physical_ports'];roles=columns['bindings']
    if len(set(order))!=len(order) or set(order)!=set(roles):
        raise ValueError('unique complete physical columns required')
    if array.shape!=(columns['samples'],len(order)+1) or len(array)<2:
        raise ValueError('complete waveform array required')
    if not np.isfinite(array).all() or array[0,0]!=0 or not np.all(np.diff(array[:,0])>0):
        raise ValueError('finite samples and increasing time from zero required')
    if [k for k in order if roles[k]['role']=='observation_only']!=['PLLOUT']:
        raise ValueError('unforced PLLOUT observation required')
    if any(roles[k]['role'] not in ['observation_only','externally_driven'] for k in order):
        raise ValueError('unknown source role')
    index={k:i+1 for i,k in enumerate(order)}
    groups=certificate['groups'];synthetic=bindings['synthetic_forcing_nodes']
    if len(groups)!=len(synthetic) or {g['aggregate_physical_key'] for g in groups}!=set(synthetic):
        raise ValueError('complete unique aggregate certificates required')
    driven=bindings['externally_driven_ports'];observed=bindings['observation_only_ports']
    if observed.keys()!= {'PLLOUT'} or set(driven)&set(observed) or not set(synthetic)<=set(driven):
        raise ValueError('complete disjoint reduced interface required')
    result_order=list(driven)+['PLLOUT'];result=np.empty((len(array),len(result_order)+1));result[:,0]=array[:,0]
    destination={k:i+1 for i,k in enumerate(result_order)};audits=[]
    for key in result_order:
        if key in synthetic:continue
        if key not in index or roles[key]['conditional_formal_port']!=(driven|observed)[key]:
            raise ValueError('literal direct port binding mismatch')
        result[:,destination[key]]=array[:,index[key]]
    for group in groups:
        key=group['aggregate_physical_key'];weights={k:F(v) for k,v in group['boundary_weights_exact'].items()};total=F(group['total_capacitance_F_exact'])
        original={k:F(v) for k,v in group['original_boundary_C_F_exact'].items()}
        if not weights or total<=0 or set(weights)!=set(original) or any(w<=0 for w in weights.values()) or sum(weights.values(),F(0))!=1 or any(total*weights[k]!=original[k] for k in weights):
            raise ValueError('exact positive charge coefficients required')
        if synthetic[key]!=group['aggregate_native_port'] or driven[key]!=synthetic[key]:
            raise ValueError('aggregate port binding mismatch')
        if any(k not in index or roles[k]['role']!='externally_driven' for k in weights):
            raise ValueError('aggregate may use only captured driven boundaries')
        maximum=F(0)
        for row in range(len(array)):
            values={k:float(array[row,index[k]]) for k in weights}
            value=math.fsum(float(w)*values[k] for k,w in weights.items())
            exact=sum((w*F.from_float(values[k]) for k,w in weights.items()),F(0))
            error=abs(F.from_float(value)-exact);maximum=max(maximum,error)
            if not math.isfinite(value):raise ValueError('nonfinite aggregate')
            result[row,destination[key]]=value
        audits.append(dict(aggregate_physical_key=key,maximum_sample_absolute_voltage_error_exact=str(maximum),samples=len(array)))
    new_columns=dict(samples=len(array),ordered_physical_ports=result_order,bindings={k:dict(role='observation_only' if k=='PLLOUT' else 'externally_driven',conditional_formal_port=(driven|observed)[k]) for k in result_order})
    return result,new_columns,dict(groups=audits,all_input_time_knots_preserved=True,direct_samples_bitwise_copied=True,aggregation_error_computed_exactly_at_every_sample=True,error_between_knots_bounded_by_endpoint_errors_for_PWL=True,native_simulation_allowed=False,native_equivalence_verified=False,dynamic_error_qualified=False,model_qualified=False,release_ready=False)
