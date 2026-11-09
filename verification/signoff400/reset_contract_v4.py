"""Versioned prototype reset contract; digital validation is not physical qualification."""
import json,math
from fractions import Fraction
from pathlib import Path
from runtime_common import sha

PROFILE=Path(__file__).with_name('requirements_v4.json')

def spec():
    parent=PROFILE.with_name('requirements_v3.json')
    old=json.loads(parent.read_text());new=json.loads(PROFILE.read_text())
    if new['schema_version']!=4 or new['parent_profile_sha256']!=sha(parent):
        raise ValueError('versioned parent identity required')
    allowed={'schema_version','parent_profile_sha256','reset_contract','repair_cycle'}
    if {k:v for k,v in new.items() if k not in allowed}!={k:v for k,v in old.items() if k not in allowed}:
        raise ValueError('functional limits or release scope changed')
    contract=new['reset_contract']
    if contract!={'active_level':0,'minimum_assertion_ns':80,'reference_clock_running_required':True,
                  'programming_static_until_next_reset':True,'physical_timing_qualified':False}:
        raise ValueError('approved 80 ns integration contract required')
    return new


def validate_assertion(start_ns,release_ns,*,reference_running,programming_static):
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [start_ns,release_ns]):
        raise ValueError('finite reset interval required')
    if start_ns<0 or Fraction(str(release_ns))-Fraction(str(start_ns))<spec()['reset_contract']['minimum_assertion_ns']:
        raise ValueError('at least 80 ns reset assertion required')
    if reference_running is not True or programming_static is not True:
        raise ValueError('running reference and static programming required')
    return dict(reset_interval_matches_contract=True,physical_reset_timing_qualified=False,release_ready=False)
