"""Require snapshot and sender curves from the identical full-native corner run."""
import json
from common_v3 import sha, verify
from capture_selected_native_initial_snapshot import fingerprint
from selected_spice_device_conditions import read


def validate(native, snapshot, waveforms, corner):
    manifest = native / 'manifest.json'
    raw = native / 'profile.raw'
    sr = snapshot / 'assessment.json'
    wr = waveforms / 'assessment.json'
    s = json.loads(sr.read_text()); w = json.loads(wr.read_text())
    if json.loads((snapshot / 'status.json').read_text()).get('state') != 'full_initial_voltage_snapshot_captured':
        raise ValueError('completed full-native snapshot required')
    if json.loads((waveforms / 'status.json').read_text()).get('state') != 'native_clock_driver_waveforms_captured':
        raise ValueError('completed sender waveform capture required')
    conditions = read(native / 'profile.spice')
    if conditions['corner'] != corner or s.get('source_device_conditions') != conditions:
        raise ValueError('sender, initialization and requested corners must match')
    for receipt in [s, w]:
        if receipt['input_sha256'].get(str(manifest)) != sha(manifest):
            raise ValueError('same full-native source manifest required')
        verify(receipt['artifacts'])
        verify({p:d for p,d in receipt['input_sha256'].items() if p != str(raw)})
    digest = s['input_sha256'].get(str(raw))
    if not digest or w['input_sha256'].get(str(raw)) != digest:
        raise ValueError('same full-native RAW identity required')
    if w['input_sha256'].get(str(sr)) != sha(sr):
        raise ValueError('waveforms must bind the identical initial snapshot receipt')
    if fingerprint(raw) != s.get('source_file_fingerprint'):
        raise ValueError('source RAW changed after capture')
    if not w.get('exact_saved_knots_preserved') or not w.get('source_complete_and_all_values_finite'):
        raise ValueError('exact finite native waveforms required')
    m = json.loads(manifest.read_text())
    return dict(**conditions, supply_v=1.8, fine=m['startup_fine']), {
        str(p):sha(p) for p in [sr, wr, native / 'profile.spice',
                              snapshot / 'status.json', waveforms / 'status.json']}
