"""Inventory current PDK body-resistance settings relevant to unresolved dummy devices."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import time
from common import save,sha
from resources import identity,lease


def statements(text):
    rows=[]
    for line in text.splitlines():
        text=line.strip()
        if not text or text.startswith('*'):continue
        if text.startswith('+'):
            if not rows:raise ValueError('orphan model continuation')
            rows[-1]+=' '+text[1:].strip()
        else:rows.append(text)
    return rows


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd()
    parent=root/'build/signoff400/startup_timing_native_device_provenance_001/assessment.json'
    failed=root/'build/signoff400/startup_timing_native_junction_alias_probe_002/failure.json'
    prior=root/'build/signoff400/startup_timing_native_junction_alias_failure_analysis_001/assessment.json'
    image=root/'build/apptainer/openpll-release-modern.sif';binary=Path('/opt/xyce/bin/Xyce')
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_pr/spice')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=2,deadline_uptime=deadline,native_simulation_launched=False))
    with lease(1,2,deadline):
        a=json.loads(parent.read_text());changes=a['unresolved_parameter_differences']
        if set(changes)!={'X14','X52'}:raise ValueError('expected unresolved native source-junction devices')
        models=sorted({r['model'] for r in changes.values()});paths=[parent,failed,prior,image,binary,Path(__file__).resolve()];results=[]
        for model in models:
            for corner in ('tt','ff','ss','sf','fs'):
                corner_path=pdk/(model+'__'+corner+'.corner.spice');paths.append(corner_path)
                includes=[]
                for line in statements(corner_path.read_text()):
                    tokens=shlex.split(line)
                    if tokens[0].lower() in ('.include','.inc'):includes.append((corner_path.parent/tokens[1]).resolve())
                if len(includes)!=1:raise ValueError('one active per-model corner include required')
                source=includes[0];paths.append(source);rows=statements(source.read_text());bins=[];instances=[]
                for line in rows:
                    if re.match(r'^m\S*\s',line,re.I):
                        if model+'__model' in line:instances.append(line)
                    if line.lower().startswith('.model '):
                        tokens=line.split();name=tokens[1]
                        if not name.startswith(model+'__model.'):continue
                        values={}
                        for key in ('rbodymod','rbpb','rbpd','rbps','rbdb','rbsb'):
                            found=re.findall(r'\b'+key+r'\s*=\s*([^\s]+)',line,re.I)
                            if len(found)!=1:raise ValueError('unique model body parameter '+key)
                            values[key]=found[0]
                        if float(values['rbodymod'])!=1 or any(float(values[k])!=50 for k in values if k!='rbodymod'):raise ValueError('current body-network defaults differ')
                        bins.append(dict(model_bin=name,body_parameters=values))
                if not bins or len(instances)!=1:raise ValueError('complete standard MOS wrapper and binned models required')
                if re.search(r'\b(rbodymod|rbpb|rbpd|rbps|rbdb|rbsb)\s*=',instances[0],re.I):raise ValueError('unexpected instance-level body-network override')
                results.append(dict(model=model,corner=corner,corner_file=str(corner_path),model_file=str(source),model_bins=len(bins),
                     instance_statement=instances[0],body_resistance_model_selector=1,five_model_body_resistance_parameters=50,bins=bins))
        pins={str(p):sha(p) for p in paths};details=output/'model_body_parameters.json';save(details,results)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('current model source changed during inventory')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(details):sha(details)},
             current_relevant_model_corners=10,current_relevant_model_bins=sum(r['model_bins'] for r in results),
             all_reviewed_bins_enable_body_resistance_model=True,five_body_resistance_parameters_all_50=True,
             no_wrapper_instance_override_of_body_network=True,
             documentation_reference='https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.6.pdf',
             inference='External D/S/B aliasing alone does not establish an internal junction short when the distributed body-resistance model is enabled.',
             causal_isolation_simulation_performed=False,old_failed_probe_pre_run_model_hashes_recovered=False,
             old_strict_alias_failure_preserved=True,body_resistance_parameters_changed=False,
             physical_parameter_set_selected=False,spatial_junction_allocation_qualified=False,
             runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
