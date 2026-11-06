"""Wait for an isolated logging build, then replay retained antenna fixtures.

No release binary, rules, or original control artifacts are changed.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def run(build,controls,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    owner=json.loads((build/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),build/'owner.json',build/'inputs.json',controls/'assessment.json']}
    save(output/'inputs.json',dict(input_sha256=pins,original_build_owner=owner,release_tool_replaced=False,release_ready=False))
    try:
        while True:
            status=build/'status.json';s=json.loads(status.read_text()) if status.exists() else {}
            if s.get('state')=='isolated_diagnostic_build_complete':break
            if s.get('state')=='stopped_without_qualification' or identity(owner['pid'])!=str(owner['birth']):raise RuntimeError('original diagnostic build stopped: '+str(s))
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer limit; original build unchanged')
            save(output/'status.json',dict(state='waiting_for_original_isolated_build',release_ready=False));time.sleep(10)
        r=json.loads((controls/'assessment.json').read_text());verify(r['input_sha256']);verify(r['artifacts']);verify(pins)
        binary=build/'install/bin/magic'
        if not binary.exists():raise ValueError('installed isolated executable required')
        pins[str(binary)]=sha(binary);pins[str(build/'instrumentation.json')]=sha(build/'instrumentation.json')
        results=[]
        with lease(1,4,deadline):
            for layer in ['licon','mcon','via1','via2','via3','via4']:
                for prefix in ['normal','array']:
                    name=prefix+'_'+layer;original=controls/name;dest=output/name;dest.mkdir()
                    fixture=original/'fixture.gds';rc=dest/'minimal.magicrc';rc.write_bytes((original/'minimal.magicrc').read_bytes())
                    script=dest/'control.tcl'
                    text=(original/'control.tcl').read_text().replace(str(original),str(dest)).replace(str(dest/'fixture.gds'),str(fixture))
                    script.write_text(text)
                    pins.update({str(p):sha(p) for p in [fixture,rc,script,original/'AntennaLayerFlat.ext']})
                    save(output/'status.json',dict(state='isolated_contact_diagnostic_running',case=name,release_ready=False))
                    execute([binary,'-dnull','-noconsole','-rcfile',rc,script],dest/'magic.log',deadline,4)
                    old=sorted(l for l in (original/'AntennaLayerFlat.ext').read_text().splitlines() if l.startswith('device '))
                    new=sorted(l for l in (dest/'AntennaLayerFlat.ext').read_text().splitlines() if l.startswith('device '))
                    if not old or old!=new:raise ValueError('diagnostic changed MOS extraction: '+name)
                    log=(dest/'magic.log').read_text();counts=re.findall(r'^ANTENNA_LAYER_FEEDBACK=(\d+)\s*$',log,re.M)
                    if len(counts)!=1:raise ValueError('complete feedback count required')
                    results.append(dict(case=name,feedback_entries=int(counts[0]),contact_calculation_lines=[l for l in log.splitlines() if l.startswith('OPENPLL_CONTACT ')],stage_lines=[l for l in log.splitlines() if l.startswith('OPENPLL_STAGE ')],contact_total_lines=[l for l in log.splitlines() if l.startswith('OPENPLL_CONTACT_TOTAL ')],MOS_geometry_and_connectivity_unchanged=True))
                    save(output/'results.json',results)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ['assessment.json','status.json']},cases=len(results),logging_build_only=True,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='isolated_antenna_diagnostic_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['build','controls','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.build.resolve(),a.controls.resolve(),a.output.resolve())
