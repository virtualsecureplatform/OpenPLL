#!/usr/bin/env python3
"""Restore the copied executable's mode and record completed native checks."""
import json,shutil,subprocess
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];c=root/'build/timing400/release_001/KLS_detailed_profile_001';old=c/'native_build_001';out=c/'native_build_002'
assert digest(old/'bin/Xyce')==digest(out/'bin/Xyce');shutil.copymode(old/'bin/Xyce',out/'bin/Xyce')
assert 'KLS adapter regression passed' in (out/'adapter_test.log').read_text()
with (out/'version_fixed.log').open('x') as log:subprocess.run([str(out/'bin/Xyce'),'-v'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
manifest=json.loads((old/'input_manifest.json').read_text());pins=manifest['input_sha256'];pins[str(Path(__file__).resolve())]=digest(Path(__file__).resolve())
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'assessment.json',dict(input_sha256=pins,commit='56abf844fb07931370ef386ff724124dfa5d965c',binary=str(out/'bin/Xyce'),binary_sha256=digest(out/'bin/Xyce'),profile_binary=str(out/'bin/Xyce_profile'),profile_binary_sha256=digest(out/'bin/Xyce_profile'),adapter_regression_passed=True,copied_executable_mode_restored=True,unused_transpose_API_not_profiled=True,release_qualified=False,adopted=False))
save(out/'status.json',dict(state='completed_native_relink',release_qualified=False))
