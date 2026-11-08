"""Separate explicit input-capacitor charge using observed terminal voltages."""
import numpy as np
from audit_keeper_DCO_driver_C_cut import capacitance
from measure_keeper_clock_buffer_input_charge import integral


def deembed(t,vin,current,vout,vmid,capacitors,ramp_ps):
    arrays=(t,vin,current,vout,vmid)
    if (any(np.ndim(v)!=1 or len(v)!=len(t) or not np.isfinite(v).all() for v in arrays)
            or len(t)<2 or not np.all(np.diff(t)>0)):
        raise ValueError('finite ordered aligned observations required')
    voltages={'A':vin,'X':vout,'a_114_74#':vmid,
              'VPWR':np.full(len(t),1.8),'VPB':np.full(len(t),1.8),
              'VGND':np.zeros(len(t)),'VNB':np.zeros(len(t)),'0':np.zeros(len(t))}
    qexplicit=np.zeros(len(t))
    seen=set()
    for row in capacitors:
        if row['name'] in seen or len(row['nodes'])!=2 or 'A' not in row['nodes']:
            raise ValueError('unique explicit input capacitors required')
        seen.add(row['name'])
        c=capacitance(row['literal'])
        if c<0 or str(c)!=row['value_F_exact']:
            raise ValueError('unchanged nonnegative literal capacitance required')
        other=row['nodes'][1] if row['nodes'][0]=='A' else row['nodes'][0]
        if other not in voltages:
            raise ValueError('every other input-capacitor terminal must be observed or a fixed rail')
        qexplicit+=float(c)*(vin-voltages[other])
    ramp=ramp_ps*1e-12
    windows=[('rising_20_80',10e-9-.3*ramp,10e-9+.3*ramp,1),
             ('falling_80_20',22e-9-.3*ramp,22e-9+.3*ramp,-1),
             ('rising_full',8e-9,20e-9,1),('falling_full',20e-9,33e-9,-1)]
    results={}
    for name,start,stop,direction in windows:
        port_charge=-integral(t,current,start,stop)
        explicit_charge=float(np.interp(stop,t,qexplicit)-np.interp(start,t,qexplicit))
        dv=float(np.interp(stop,t,vin)-np.interp(start,t,vin))
        if direction*dv<=0:
            raise ValueError('expected input transition direction required')
        intrinsic=port_charge-explicit_charge
        results[name]=dict(port_charge_C=port_charge,explicit_capacitor_charge_C=explicit_charge,
                           intrinsic_gate_charge_C=intrinsic,input_voltage_change_V=dv,
                           port_effective_capacitance_F=port_charge/dv,
                           explicit_effective_capacitance_F=explicit_charge/dv,
                           intrinsic_effective_capacitance_F=intrinsic/dv)
    return results
