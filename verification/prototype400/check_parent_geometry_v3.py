#!/usr/bin/env python3
"""Measure parent RC and both antenna methods plus stock PDK density.

Raw RC excludes macro internal parasitics and fill and cannot qualify a model.
All CAD stages share a 12h budget. Nonpass geometry is retained for repair.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha,verify,source_pins
from klayout_compat import pya
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD
from run_candidate_layout_checks_v2 import MAGIC
TOP='IntegerPLL_400MHz_PrototypeTop'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--layout',required=True,type=Path);p.add_argument('--route',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();layout=a.layout.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.monotonic()+43200
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    pins={}
    def status(state,**kw):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw))
    def run(label,cmd,cwd=None,stdin=None,env=None):
        verify(pins)
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,cmd)),stdin=stdin,stdout=log,stderr=subprocess.STDOUT,cwd=cwd or out,env=env,start_new_session=True)
            status(label+'_running',native_pid=child.pid)
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
        verify(pins);return code
    try:
        while not (layout/'stream_assessment.json').exists():
            if (layout/'status.json').exists():assert json.loads((layout/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;status('waiting_for_stream_checks');time.sleep(10)
        receipt=json.loads((layout/'stream_assessment.json').read_text());verify(receipt['input_sha256'])
        gds=layout/'assembly.gds';assert sha(gds)==receipt['assembly_gds_sha256']
        private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc'
        rules=private/'libs.tech/librelane';density=private/'libs.tech/magic/check_density.py'
        antenna=ROOT/'verification/timing400/check_forming_antenna_geometry_v2.py'
        pins=source_pins()
        wrapper=Path(__file__).with_name('run_klayout_script.py')
        for helper in (wrapper,Path(__file__).with_name('klayout_compat.py'),Path(sys.modules[pya.Layout.__module__].__file__)):
            pins[str(helper)]=sha(helper)
        for path in [Path(__file__).resolve(),Path(sys.executable),Path(OPENROAD),MAGIC,gds,
                     layout/'stream_assessment.json',route/'assessment.json',route/'route.odb',
                     startup,private/'libs.tech/magic/sky130A.tech',density,antenna,
                     *[rules/f'rules.openrcx.sky130A.{v}.magic' for v in ('min','nom','max')]]:
            pins[str(path)]=sha(path)
        save(out/'input_manifest.json',dict(input_sha256=pins))
        for view in ('min','nom','max'):
            task=out/f'rcx_{view}.tcl';task.write_text(f'''read_db {route}/route.odb
set_thread_count 2
define_process_corner -ext_model_index 0 RCX_{view.upper()}
extract_parasitics -ext_model_file {rules}/rules.openrcx.sky130A.{view}.magic -corner 0
write_spef -coordinates {out}/parent.{view}.spef
puts "PARENT_RCX_COMPLETE"
''')
            assert run('rcx_'+view,[OPENROAD,'-no_init','-exit',task])==0
            assert 'PARENT_RCX_COMPLETE' in (out/f'rcx_{view}.log').read_text()
            assert '*RES' in (out/f'parent.{view}.spef').read_text()
        save(out/'rcx_assessment.json',dict(input_sha256=pins,parent_wire_rc_extracted=True,
             macro_internal_parasitics_included=False,fill_included=False,pin_capacitance_included=False,
             complete_physical_domain=False,release_qualified=False,
             artifacts={str(p):sha(p) for p in out.glob('parent.*.spef')}))
        assert run('forming_antenna',[sys.executable,wrapper,antenna,'--gds',gds,'--top',TOP,'--output',out/'forming_antenna'])==0
        (out/'native_antenna_extraction').mkdir()
        task=out/'native_antenna.tcl';task.write_text(f'''crashbackups stop
locking disable
drc off
snap internal
gds read {gds}
load {TOP} -dereference
select top cell
expand
cd {out}/native_antenna_extraction
extract do local
extract no all
extract all
puts "ASSEMBLED_ANTENNA_EXTRACTION_COMPLETE"
feedback save {out}/extraction_feedback.txt
feedback clear
puts "ASSEMBLED_ANTENNA_BEGIN"
antennacheck
puts "ASSEMBLED_ANTENNA_FEEDBACK=[feedback count]"
feedback save {out}/antenna_feedback.txt
puts "ASSEMBLED_ANTENNA_END"
quit -noprompt
''')
        env=dict(os.environ,PDK_ROOT=str(private.parent),PDK='sky130A',PATH=str(MAGIC.parent)+os.pathsep+os.environ.get('PATH',''))
        with task.open() as commands:assert run('native_antenna',[MAGIC,'-dnull','-noconsole','-rcfile',startup],stdin=commands,env=env)==0
        den=out/'density';den.mkdir();(den/(TOP+'.gds')).symlink_to(gds)
        code=run('density',['/usr/bin/python3',density,TOP+'.gds'],cwd=den,env=env)
        verify(pins)
        save(out/'native_completion.json',dict(input_sha256=pins,exit_code=code,
             artifacts={str(out/'density.log'):sha(out/'density.log')},scope='PDK density native execution receipt',release_qualified=False))
        save(out/'assessment.json',dict(input_sha256=pins,density_native_exit=code,
             raw_checks_completed=True,antenna_qualified=False,density_qualified=False,
             complete_physical_model=False,release_qualified=False,
             artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='status.json'}))
        status('parent_geometry_measurements_terminal',density_native_exit=code)
    except BaseException as e:status('failed',reason=str(e));raise


if __name__=='__main__':main()
