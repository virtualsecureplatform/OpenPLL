"""Predict publication delivery from detector pulses and a reset-zero Q model."""
import math


def deliver(role,edges,parameters):
    result=[];predictions=[];ordinal=0;active_delay=0.;last=-math.inf
    for t,value in edges:
        if value:
            direction='rise' if ordinal%2==0 else 'fall'
            if direction not in parameters.get(role,{}):
                raise ValueError(f'needs_native_publication_direction role={role} Q_edge={direction}')
            active_delay=parameters[role][direction]['nominal_ns']
            if not isinstance(active_delay,(int,float)) or isinstance(active_delay,bool) or not math.isfinite(active_delay) or active_delay<=0:
                raise ValueError('finite positive measured publication delay required')
            predictions.append(dict(role=role,event_index=ordinal,Q_edge=direction,detector_rise_ns=t,
                                    publication_delay_ns=active_delay,predicted_delivery_ns=t+active_delay))
            ordinal+=1
        delivered=t+active_delay
        if delivered<=last:raise ValueError('publication model reordered pulse edges')
        result.append((delivered,value));last=delivered
    return result,predictions
