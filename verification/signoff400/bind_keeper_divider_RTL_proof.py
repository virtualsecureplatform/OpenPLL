"""Bind an existing induction proof to keeper route RTL declarations; not routed equivalence."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify


def configuration(top,programmed,digital):
    clean=lambda s:re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
    top,programmed,digital=map(clean,[top,programmed,digital])
    patterns=[(top,r'IntegerPLL_ProgrammedCore\s+digital\s*\('),(programmed,r'localparam\s+\[4:0\]\s+FEEDBACK_DIVIDER\s*=\s*5\x27d16\s*;')]
    patterns += [(programmed,rf'\.MMD_{name}\s*\(\s*{value}\s*\)') for name,value in [('REGISTER_CONFIG',0),('RATIO_WIDTH',5),('COUNTDOWN',1),('CONFIG_PIPELINE',0)]]
    patterns += [(programmed,r"\.MMDCLKDIV_RATIO\s*\(\s*\{\s*3'b000\s*,\s*FEEDBACK_DIVIDER\s*\}\s*\)")]
    patterns += [(digital,rf'\.{name}\s*\(\s*{signal}\s*\)') for name,signal in [('RATIO_WIDTH','MMD_RATIO_WIDTH'),('REGISTER_CONFIG','MMD_REGISTER_CONFIG'),('COUNTDOWN','MMD_COUNTDOWN'),('CONFIG_PIPELINE','MMD_CONFIG_PIPELINE')]]
    patterns += [(digital,r'\.CLK_DIV_RATIO\s*\(\s*MMDCLKDIV_RATIO\s*\[\s*MMD_RATIO_WIDTH\s*-\s*1\s*:\s*0\s*\]\s*\)')]
    if any(len(re.findall(pattern,text))!=1 for text,pattern in patterns):raise ValueError('keeper source declarations differ from proved divider configuration')
    return dict(ratio=16,ratio_width=5,register_config=0,countdown=1,config_pipeline=0,binding_method='exact source hashes plus pinned-format source declaration checks; no new elaboration proof')


def run(route,proof,negative,output):
    receipts=[p/'assessment.json' for p in [route,proof,negative]];r,d,n=[json.loads(p.read_text()) for p in receipts]
    for a in [d,n]:verify(a['input_sha256']);verify(a['artifacts'])
    if not d['inductive_constant_divider_output_equivalence'] or d['ratio']!=16 or not n['incorrect_ratio15_rejected'] or n['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('matching induction and ratio-15 negative control required')
    if 'Induction step proven: SUCCESS!' not in (proof/'proof.log').read_text() or 'proof did fail!' not in (negative/'negative.log').read_text():raise ValueError('native positive and negative proof logs required')
    sources={Path(p).name:Path(p) for p in r['candidate_source_sha256'] if p.endswith('.v')}
    if len(sources)!=9:raise ValueError('complete nine-source keeper route declaration required')
    source_pins={str(p):r['candidate_source_sha256'][str(p)] for p in sources.values()}
    if any(r['input_sha256'].get(k)!=v for k,v in source_pins.items()):raise ValueError('route input source identity mismatch')
    verify(source_pins);mmd=sources['IntegerPLL_MMD_Retimer.v'];digest=sha(mmd)
    proved=[v for p,v in d['input_sha256'].items() if p.endswith('/IntegerPLL_MMD_Retimer.v')]
    if proved!=[digest]:raise ValueError('proved divider RTL differs from keeper route source')
    config=configuration(*[sources[name].read_text() for name in ['IntegerPLL_400MHz_PrototypeTop.v','IntegerPLL_ProgrammedCore.v','IntegerPLL_DigitalCore.v']])
    odb=route/'route.odb';verify({str(odb):r['artifacts'][str(odb)]});output.mkdir(parents=True,exist_ok=False)
    pins={**source_pins,**{str(p):sha(p) for p in [*receipts,odb,proof/'proof.log',negative/'negative.log',Path(__file__).resolve()]}}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**config,current_route_declared_RTL_matches_proved_divider=True,inductive_source_property_reused=True,new_formal_run_performed=False,negative_ratio15_control_verified=True,arbitrary_reset_sequences_at_RTL_level=d['arbitrary_reset_sequences'],physical_layout_formal_equivalence_qualified=False,propagated_clock_timing_qualified=False,CDC_and_reset_timing_qualified=False,digital_timing_gate_closed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['route','proof','negative','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.proof.resolve(),a.negative.resolve(),a.output.resolve())
