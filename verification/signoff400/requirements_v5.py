"""User-approved ppm policy; all other prototype requirements retain v4 scope."""
import json
from pathlib import Path
from runtime_common import sha
from reset_contract_v4 import spec as parent_spec
PROFILE=Path(__file__).with_name('requirements_v5.json')

def spec():
    old=parent_spec();new=json.loads(PROFILE.read_text())
    parent=PROFILE.with_name('requirements_v4.json')
    if new['schema_version']!=5 or new['parent_profile_sha256']!=sha(parent):raise ValueError('v4 parent identity required')
    allowed={'schema_version','parent_profile_sha256','frequency_error_ppm','sample_settling_screen_ppm'}
    if {k:v for k,v in new.items() if k not in allowed}!={k:v for k,v in old.items() if k not in allowed}:
        raise ValueError('unapproved release scope or non-frequency limits changed')
    if new['frequency_error_ppm']!=3000 or new['sample_settling_screen_ppm']!=300:
        raise ValueError('approved 3000 ppm lock and 300 ppm settling limits required')
    return new
