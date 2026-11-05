"""Versioned signoff scope; historical prototype scripts and receipts stay frozen."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'verification/signoff400/requirements_v2.json'
DEPS = ROOT / 'rtl/prototype400'
RTL = [ROOT / name for name in json.loads((DEPS / 'sources.json').read_text())['files']]
RTL += [ROOT / 'rtl/IntegerPLL_ProgrammedStartup.v', ROOT / 'rtl/IntegerPLL_ProgrammedCore.v']
TOP = ROOT / 'rtl/IntegerPLL_400MHz_PrototypeTop.v'


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify(pins):
    for path, digest in pins.items():
        if sha(path) != digest:
            raise ValueError('Input changed: ' + path)


def spec():
    value = json.loads(PROFILE.read_text())
    if (value['schema_version'] != 2
            or value['parent_profile_sha256'] != sha(ROOT/'verification/signoff400/requirements.json')
            or value['cdc_reliability']['aggregate_max_fit'] != 1.0
            or value['cdc_reliability']['scope'] != 'command_and_reset_synchronizers'
            or value['profile'] != 'programmed_400mhz_temperature_signoff'
            or value['modes_mhz'] != [400] or value['reference_mhz'] != 25
            or value['feedback_divider'] != 16 or value['voltages'] != [1.8]
            or value['corners'] != ['tt', 'ff', 'ss', 'sf', 'fs']
            or value['temperatures_c'] != [-40, 27, 125]):
        raise ValueError('400 MHz temperature signoff scope mismatch')
    return value


def cases():
    value = spec()
    return [dict(id=f'{corner}_{temp}C_{scenario}_phase{phase}', corner=corner,
                 temperature_c=temp, supply_v=1.8, mode_mhz=400, divider=16,
                 scenario=scenario, phase_offset_ns=phase,
                 execution_eligible=False, passed=False)
            for corner in value['corners'] for temp in value['temperatures_c']
            for scenario in value['scenarios'] for phase in value['reference_phase_offsets_ns']]


def source_pins():
    deps = ROOT / 'rtl/prototype400/sources.json'
    frozen = json.loads(deps.read_text())['files']
    verify({str(ROOT / name): digest for name, digest in frozen.items()})
    paths = [PROFILE, deps, *(ROOT / name for name in frozen),
             ROOT / 'rtl/IntegerPLL_ProgrammedStartup.v',
             ROOT / 'rtl/IntegerPLL_ProgrammedCore.v',
             ROOT / 'rtl/IntegerPLL_400MHz_PrototypeTop.v']
    return {str(p): sha(p) for p in paths}
