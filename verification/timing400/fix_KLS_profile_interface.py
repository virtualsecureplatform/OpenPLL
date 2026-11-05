#!/usr/bin/env python3
"""Match optional upstream wrapper interface to symbols actually built."""
from pathlib import Path
import json,subprocess,time
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_detailed_profile_001';scratch=Path('/tmp/openpll-kls-detailed-20261025-001');source=scratch/'KLS';deadline=json.loads((out/'owner.json').read_text())['deadline_uptime']
includes=[source/'include',source/'src',source/'third_party/suitesparse/UFconfig',*list((source/'third_party/suitesparse').glob('*/Include'))]
command=['gcc','-O3','-g',*['-I'+str(p) for p in includes],'-c',str(source/'bench/kls_klu_phase_profile.c'),'-o',str(scratch/'phase_legacy.o')]
with (out/'compile_phase_legacy.log').open('x') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
old=json.loads((out/'build_assessment.json').read_text());old['input_sha256'][str(scratch/'phase_legacy.o')]=digest(scratch/'phase_legacy.o');old['input_sha256'][str(Path(__file__).resolve())]=digest(Path(__file__).resolve());old['optional_verdict_interface_present']=False
save(out/'build_assessment_v2.json',old)
