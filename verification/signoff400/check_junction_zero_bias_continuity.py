"""Check the signed-perimeter junction discontinuity against the observed body gap."""
import argparse
from decimal import Decimal as D, localcontext
import json
from pathlib import Path
import re
from common import ROOT, save, sha, verify


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=ROOT/'build/signoff400'
    native=ROOT/'build/timing400/release_001/wire_preconditioned_Xyce_001/source/src/DeviceModelPKG/OpenModels/N_DEV_MOSFET_B4p61.C'
    reference=ROOT/'build/tools/ngspice47/tmpsndfibtf/src/spicelib/devices/bsim4v5/b4v5ld.c'
    temperature=reference.with_name('b4v5temp.c')
    model=base/'startup_timing_MOS_gate_default_probe_003/openpll_gate_default_1_pfet_.spice'
    probe=base/'startup_timing_body_zero_VDS_001/assessment.json'
    op=base/'startup_timing_body_operating_parameters_001/assessment.json'
    paths=[native,reference,temperature,model,probe,op,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};a=json.loads(probe.read_text());o=json.loads(op.read_text())
    verify(a['artifacts']);verify(o['artifacts'])
    text=model.read_text();ng=reference.read_text();xy=native.read_text();temp=temperature.read_text()
    required_ng=['if (vbs_jct == 0.0)','else if (vbs_jct < 0.0)','if (czbssw > 0.0)',
                 'here->BSIM4v5capbs = czbs + czbssw + czbsswg;']
    required_xy=['if (vbs_jct == 0.0)','else if (vbs_jct < 0.0)','if (czbssw > 0.0)',
                 'capbs = czbs + czbssw + czbsswg;']
    if any(token not in ng for token in required_ng) or any(token not in xy for token in required_xy):
        raise ValueError('audited junction source branches changed')
    if 'here->BSIM4v5sourcePerimeter' not in temp or '- pParam->BSIM4v5weffCJ' not in temp:
        raise ValueError('audited effective-perimeter equation changed')
    fixtures=json.loads((base/'startup_timing_body_zero_VDS_001/fixtures.json').read_text())
    p=next(f['profile']['parameters'] for f in fixtures if f['profile']['profile_id']==1002)
    bins=[]
    for block in re.split(r'(?im)(?=^\.model\s+)',text):
        if not block.lower().startswith('.model'):continue
        values=dict((k.lower(),v) for k,v in re.findall(r'\b([a-z0-9_]+)\s*=\s*(\S+)',block,re.I))
        if (D(values['lmin'])<=D(p['l'])*D('1e-6')<=D(values['lmax'])
                and D(values['wmin'])<=D(p['w'])*D('1e-6')<=D(values['wmax'])):bins.append((block,values))
    if len(bins)!=1:raise ValueError('unique exact physical L/W model bin required')
    selected,values=bins[0]
    def parameter(name):return D(values[name])
    if parameter('xl')!=0 or parameter('xw')!=0 or parameter('binunit')!=2:
        raise ValueError('selected bin coordinate convention differs')
    if parameter('permod')!=1 or parameter('dwc')!=0 or parameter('tcjsw')!=0:
        raise ValueError('audited perimeter/temperature setting differs')
    if re.search(r'\bdwj\s*=',selected,re.I):raise ValueError('explicit junction width needs separate review')
    if D(p['ps'])!=0 or D(p['as'])!=0:raise ValueError('audited zero source geometry differs')
    with localcontext() as context:
        context.prec=90
        width=D(p['w'])*D('1e-6');perimeter=D(p['ps'])*D('1e-6')
        sidewall=parameter('cjsws')*(perimeter-width)
        if sidewall>=0:raise ValueError('negative sidewall component required for this causal check')
        jump=-sidewall
        # The reverse-bias branch retains only positive component coefficients.
        # At zero and forward bias it retains their signed sum.
        gate_sidewall=parameter('cjswgs')*width*(1+parameter('tcjswg')*(D(-40)-parameter('tnom')))
        components=[D(0),sidewall,gate_sidewall]
        zero=sum(components);reverse_limit=sum(c for c in components if c>0)
        if reverse_limit-zero!=jump:raise ValueError('exact branch-limit identity failed')
        rows=[r for r in a['results'] if r['frequency_hz']==1000]
        residuals=[]
        for row in rows:
            found=D(str(row['terminals']['source']['imaginary_gap_over_omega_F']))
            error=abs(found+jump);residuals.append(str(error))
            if error>D('1e-8')*jump+D('1e-25'):
                raise ValueError('observed low-frequency capacitance gap is not explained')
        result=dict(selected_model_bin=selected.splitlines()[0],source_width_m=str(width),effective_source_sidewall_perimeter_m=str(perimeter-width),
             signed_source_sidewall_capacitance_F=str(sidewall),zero_bias_capacitance_F=str(zero),
             infinitesimal_reverse_bias_capacitance_F=str(reverse_limit),
             zero_to_reverse_capacitance_jump_F=str(jump),
             maximum_observed_gap_prediction_error_F=str(max(map(D,residuals))),
             observed_signed_drain_biases_checked=len(rows),
             agreement_screen=dict(relative='1e-8',absolute_F='1e-25',diagnostic_only=True))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},results=result,
         signed_effective_source_perimeter_negative=True,
         both_retained_sources_have_the_same_discontinuous_negative_component_branch=True,
         predicted_branch_jump_matches_observed_body_enabled_gap=True,
         source_bound_to_installed_Xyce_binary=False,
         body_network_stamping_proven_cause=False,
         physical_junction_geometry_allocation_qualified=False,
         simulator_or_foundry_models_changed=False,diagnostic=True,
         MOS_backend_compatibility_qualified=False,release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);run(parser.parse_args().output.resolve())
