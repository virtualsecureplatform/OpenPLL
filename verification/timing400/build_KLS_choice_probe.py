from pathlib import Path
import json,subprocess
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_detailed_profile_001';scratch=Path('/tmp/openpll-kls-detailed-20261025-001')
subprocess.run(['gcc','-O3','-g','-I'+str(scratch/'KLS/include'),'-c',str(scratch/'stats_choice.c'),'-o',str(scratch/'stats_choice.o')],check=True,timeout=30)
original=json.loads((out/'refined_build_assessment.json').read_text());cmd=json.loads((out/'refined_build_assessment.json').read_text()).get('link_command')
# Recreate the known refined link from its pinned original CMake command.
import shlex
cmd=shlex.split((scratch/'probe_build_v2/CMakeFiles/compare_coarse_matrix.dir/link.txt').read_text())
cmd=[str(scratch/'libkls_refined.a') if x==str(scratch/'libkls_coarse.a') else x for x in cmd]
cmd[cmd.index('-o')+1]=str(scratch/'compare_choice_matrix')
for i,x in enumerate(cmd):
 if x.endswith('.o') and not Path(x).is_absolute():cmd[i]=str(scratch/'probe_build_v2'/x)
cmd.extend([str(scratch/'stats_choice.o'),'-Wl,--wrap=kls_get_stats'])
with (out/'link_choice.log').open('x') as log:subprocess.run(cmd,cwd=scratch/'probe_build_v2',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
original.update(binary=str(scratch/'compare_choice_matrix'),binary_sha256=digest(scratch/'compare_choice_matrix'))
original['input_sha256'].update({str(scratch/'stats_choice.c'):digest(scratch/'stats_choice.c'),str(Path(__file__).resolve()):digest(Path(__file__).resolve())})
save(out/'choice_build_assessment.json',original)
