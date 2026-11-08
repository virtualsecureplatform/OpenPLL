"""Read diagnostic static-subsystem measurements without relabeling their native window."""
import json,math,re
from pathlib import Path
from common_v3 import sha,verify


def measured_point(receipt):
    receipt=Path(receipt);record=json.loads(receipt.read_text())
    verify(record['input_sha256']);verify(record['artifacts'])
    if not all(record.get(k) is True for k in ('normal_native_completion','all_saved_values_finite','all_native_DCO_leaves_match')):
        raise ValueError('normal finite native capture with all tuning leaves required')
    inputs=receipt.with_name('inputs.json');domain=json.loads(inputs.read_text())
    if (domain.get('window_ns')!=[20,60] or domain.get('simulation_ns')!=60
            or domain.get('max_step_ps')!=10 or domain.get('receiver_load_fF')!=32
            or domain.get('programming_macro_inputs_ideal_static_truth_table') is not True
            or domain.get('capacitive_exterior_grounded') is not True
            or domain.get('voltage_histories_used') is not False):
        raise ValueError('declared static32 fF diagnostic subsystem scope required')
    deck=receipt.with_name('transient.spice')
    if record['input_sha256'].get(str(deck))!=sha(deck):raise ValueError('native deck must be pinned')
    lines=deck.read_text().splitlines()
    if ('VDD VDD 0 1.8' not in lines or '.options device temp=27' not in lines or '.tran 10p 60n 0 10p' not in lines
            or not any(line.startswith('.lib ') and line.endswith(' tt') for line in lines)):
        raise ValueError('TT27C1.8V static scope required')
    checks=receipt.with_name('leaf_checks.json')
    if record['artifacts'].get(str(checks))!=sha(checks):raise ValueError('native leaf checks must be pinned')
    bits={}
    for row in json.loads(checks.read_text()):
        match=re.fullmatch(r'(COARSETHERMAL_CODE|DCO_THERM)\[(\d+)\]\.DCO',row['name'])
        if not match:raise ValueError('physical DCO leaf identity required')
        key=(match[1],int(match[2]));bit=row['expected_logic']
        if key in bits or bit not in (0,1) or row['passed'] is not True:
            raise ValueError('unique matching native control observations required')
        low,high=row['minimum_V'],row['maximum_V']
        if not all(math.isfinite(v) for v in (low,high)) or low>high or (low<1.44 if bit else high>.36):
            raise ValueError('native voltage checks do not support declared logic')
        bits[key]=bit
    required={('COARSETHERMAL_CODE',i) for i in range(47)}|{('DCO_THERM',i) for i in range(255)}
    if set(bits)!=required:raise ValueError('all302 native leaves required')
    coarse=sum(bits['COARSETHERMAL_CODE',i] for i in range(47))
    fine=sum(1-bits['DCO_THERM',i] for i in range(255))
    if not 8<=fine<=247 or (domain['coarse'],domain['fine'])!=(coarse,fine):
        raise ValueError('input labels differ from observed thermometer code')
    if any(bits['COARSETHERMAL_CODE',i]!=int(i<coarse) for i in range(47)) or any(bits['DCO_THERM',i]!=int(i>=fine) for i in range(255)):
        raise ValueError('monotonic thermometer pattern required')
    f=record['frequency_diagnostic']
    if f['rising_edges']<3 or not math.isfinite(f['frequency_mhz']) or f['frequency_mhz']<=0:
        raise ValueError('measured finite frequency with at least three edges required')
    return coarse,fine,round(f['frequency_mhz']*1e9)


def point_pins(receipts):
    pins={str(Path(__file__).resolve()):sha(Path(__file__).resolve())};signatures=[]
    for receipt in receipts:
        receipt=Path(receipt);record=json.loads(receipt.read_text())
        measured_point(receipt)
        inputs=receipt.with_name('inputs.json');domain=json.loads(inputs.read_text())
        pins.update(record['input_sha256']);pins.update(record['artifacts'])
        pins.update({str(receipt):sha(receipt),str(inputs):sha(inputs)})
        signatures.append({p:d for p,d in record['input_sha256'].items() if p.endswith('/model.spice') or p.endswith('/Xyce')})
    if not signatures or len(signatures[0])!=2 or any(s!=signatures[0] for s in signatures):
        raise ValueError('same native subsystem and corrected simulator required')
    return pins
