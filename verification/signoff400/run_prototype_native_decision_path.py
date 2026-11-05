"""Native path holdout with formally permitted high-phase source updates."""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from prepare_prototype_BBPD_receiver_v3 import header
from prepare_prototype_analog_reference import subcircuits
from assess_prototype_native_waveform import crossings


def run(source,proof,corner,output):
    sr=source/'assessment.json';pr=proof/'assessment.json';r,p=[json.loads(f.read_text()) for f in (sr,pr)]
    verify(r['artifacts']);verify(p['artifacts'])
    if not p.get('decision_changes_only_during_sampled_divided_clock_high_phase_proved') or not p.get('decision_update_enable_negative_control_rejected'):raise ValueError('controlled actual-divider phase proof required')
    model=source/'receiver_RC.spice';metadata=source/'model.json';m=json.loads(metadata.read_text());ports=header(subcircuits(model.read_text())['prototype_BBPD_receiver_RC'])
    required={'n_6','n_12','n_608','n_3081','n_3383','n_3454','n_3408','n_3078','n_567','n_3455','n_668','VPWR','VGND','VPB','VNB'}
    if set(ports)!=(required|{a['port'] for a in m['off_network_aggressors']}):raise ValueError('frozen path interface differs')
    binding={pin:pin for pin in required};binding.update(VPWR='VDD',VPB='VDD',VGND='0',VNB='0')
    binding.update({a['port']:'0' for a in m['off_network_aggressors']})
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    image=ROOT/'build/apptainer/openpll-release-modern.sif';tool='/opt/xyce/bin/Xyce'
    bank=ROOT/f'build/signoff400/prototype_v3_final_cell_C_grid_{corner}_001/assessment.json';native=json.loads(bank.read_text())
    paths=[sr,pr,model,metadata,image,bank,Path(__file__).resolve()]
    pins={str(f):sha(f) for f in paths};pins[tool]=native['input_sha256'][tool]
    pins.update({name:digest for name,digest in native['input_sha256'].items() if name.startswith('/opt/pdk/')})
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    deck=output/'path.cir';deck.write_text(f'''* Selected data and clock paths; TT conditional outside pin loads, quiet coupling
.lib "{pdk}" {corner}
.include "{model}"
.options device temp=27
.options timeint reltol=1e-5 abstol=1e-10
VSUP VDD 0 1.8
VFAST n_6 0 PULSE(0 1.8 1.9n 200p 200p 800p 2n)
VDIV n_12 0 PULSE(1.8 0 15.9n 200p 200p 15.8n 32n)
VDATA n_3081 0 PWL(0 0 2.9n 0 3.1n 1.8 34.9n 1.8 35.1n 0 64n 0)
VSIDE n_608 0 0
VRSTA n_3383 0 PWL(0 0 1n 0 1.2n 1.8)
VRSTB n_3454 0 PWL(0 0 1n 0 1.2n 1.8)
XPATH {' '.join(binding[pin] for pin in ports)} prototype_BBPD_receiver_RC
.tran 2p 64n 0 2p
.print tran V(n_6) V(n_12) V(n_3408) V(n_3078) V(n_567) V(n_3455) V(n_668)
.end
''')
    pins[str(deck)]=sha(deck);plan=output/'plan.json';save(plan,dict(input_sha256=pins,corner=corner,
        generated_clock_root_phase_assumed=True,root_full_ramp_ps=200,clock_capacity_mhz=500,
        source_updates='capture at fast edges4ns and36ns; divided-clock high phases',
        outside_receiver_load_scope='supplied TT25 conditional pin capacitances',quiet_off_network_aggressors=True,release_ready=False))
    prefix=['apptainer','exec','--bind','/home:/home',image]
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    with lease(1,4,deadline):
        execute([*prefix,'/usr/bin/python3',Path(__file__).resolve(),'--verify-inputs',plan],output/'verification.log',deadline,4)
        execute([*prefix,tool,'-linsolv','KLU','-quiet','-o',output/'wave',deck],output/'native.log',deadline,4)
    wave=output/'wave.prn';data=[];terminal=False
    with wave.open() as stream:
        expected=['Index','TIME']+[f'V(N_{n})' for n in (6,12,3408,3078,567,3455,668)]
        if stream.readline().split()!=expected:raise ValueError('native path waveform columns differ')
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:terminal=True;continue
            f=line.split()
            if not f:continue
            if terminal or len(f)!=9 or int(f[0])!=len(data):raise ValueError('native waveform rows differ')
            row=list(map(float,f[1:]))
            if not all(map(math.isfinite,row)) or (data and row[0]<=data[-1][0]):raise ValueError('invalid native path samples')
            data.append(row)
    if not terminal or not data or data[-1][0]<64e-9-1e-15:raise ValueError('incomplete native path waveform')
    events={name:dict(zip(('rising_s','falling_s'),crossings([(row[0],row[index]) for row in data],.9))) for name,index in (('fast_root',1),('divided_root',2),('source_clock',3),('source_Q',4),('destination_clock',5),('destination_D',6),('destination_Q',7))}
    detail=output/'events.json';save(detail,events)
    verify({name:digest for name,digest in pins.items() if not name.startswith('/opt/')})
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in (deck,wave,output/'native.log',plan,detail)},
        corner=corner,native_path_waveform_complete=True,all_crossings_retained=True,
        physically_extracted_clock_and_data_cones_simulated=True,supplied_TT_conditional_outside_pin_loads=True,
        native_generated_clock_source_latency_included=False,all_reachable_updates_covered=False,
        native_path_correlation_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','proof','output','verify-inputs'):p.add_argument('--'+n,type=Path)
    p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'))
    a=p.parse_args()
    if a.verify_inputs:verify(json.loads(a.verify_inputs.read_text())['input_sha256'])
    elif all((a.source,a.proof,a.corner,a.output)):run(a.source.resolve(),a.proof.resolve(),a.corner,a.output.resolve())
    else:p.error('source, proof, corner, output required')
