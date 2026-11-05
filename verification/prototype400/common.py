"""Identity and scope helpers for the separately qualified prototype."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'verification/prototype_400mhz.json'
DEPS = ROOT / 'rtl/prototype400'
RTL = [ROOT / name for name in json.loads((DEPS / 'sources.json').read_text())['files']]
RTL += [ROOT / 'rtl/IntegerPLL_ProgrammedStartup.v', ROOT / 'rtl/IntegerPLL_ProgrammedCore.v']
TOP = ROOT / 'rtl/IntegerPLL_400MHz_PrototypeTop.v'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def spec():
    value = json.loads(PROFILE.read_text())
    if (value['profile'] != 'programmed_400mhz_prototype' or value['modes_mhz'] != [400]
            or value['reference_mhz'] != 25 or value['feedback_divider'] != 16
            or value['corners'] != ['tt','ff','ss','sf','fs']
            or value['temperatures_c'] != [27] or value['voltages'] != [1.8]):
        raise ValueError('Prototype scope mismatch')
    return value


def source_pins():
    for path, digest in json.loads((DEPS / 'sources.json').read_text())['files'].items():
        if sha(ROOT / path) != digest:
            raise ValueError('Frozen digital dependency changed: ' + path)
    return {str(path): sha(path) for path in [PROFILE, DEPS / 'sources.json', *RTL, TOP]}


def verify(pins):
    for path, digest in pins.items():
        if sha(path) != digest:
            raise ValueError('Input changed: ' + path)


def cases():
    value = spec()
    return [dict(id=f'{corner}_{scenario}_phase{phase}', corner=corner, temperature_c=27,
                 supply_v=1.8, mode_mhz=400, divider=16, scenario=scenario,
                 phase_offset_ns=phase, execution_eligible=False, passed=False)
            for corner in value['corners'] for scenario in value['scenarios']
            for phase in value['reference_phase_offsets_ns']]


def lock_summary(result):
    """Trace evidence cannot by itself establish physical qualification."""
    return dict(trace_passed=bool(result.get('passed')),
                whole_pll_qualification_pass=False, prototype_handoff_qualified=False)
