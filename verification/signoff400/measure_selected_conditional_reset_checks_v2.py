"""Measure worst enabled recovery/removal/pulse checks; external reset stays excluded."""
import argparse,json,math,os,re,time,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def parse(text,kind):
    if re.search(r'\[ERROR|Error:|invalid command',text):raise ValueError('native timing query failed')
    hits=re.findall(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',text)
    if len(hits)!=1:raise ValueError('exactly one worst enabled check required')
    slack=float(hits[0][0])
    if not math.isfinite(slack) or (slack>=0)!=(hits[0][1]=='MET'):raise ValueError('inconsistent timing slack')
    if kind=='min_pulse_width':
        if 'Check: sequential_clock_pulse_width' not in text:raise ValueError('clock pulse check required')
        pin=re.search(r'^Pin: (\S+)',text,re.M)
    else:
        if f'({kind} check against ' not in text:raise ValueError('reset check type differs')
        pin=re.search(r'^Endpoint: (\S+)',text,re.M)
    if not pin:raise ValueError('explicit endpoint required')
    return dict(check=kind,endpoint=pin[1],slack_ns=slack,passed=slack>=0)


def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;pins=source_pins();rows=[];artifacts={}
    for p in(image,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','screen_prototype_decision_hold_phase_v5.py'))):pins[str(p)]=sha(p)
    foreign={}
    def verify_baseline(inputs):
        for path,digest in inputs.items():
            if Path(path).exists():verify({path:digest})
            elif path==OPENROAD:
                actual=subprocess.check_output(['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),'sha256sum',path],text=True).split()[0]
                if actual!=digest:raise ValueError('container timing tool differs from baseline')
                foreign[path]=digest
            else:raise FileNotFoundError(path)
    route=ROOT/'build/signoff400/prototype_v3_selected_route_019/route.odb'
    for corner in ('tt','ff','ss','sf','fs'):
        baseline=ROOT/f'build/signoff400/prototype_v3_selected_402p1_endpoints_{corner}_019'
        receipt=baseline/'assessment.json';a=json.loads(receipt.read_text());verify_baseline(a['input_sha256']);verify(a['artifacts'])
        original=baseline/'inventory.tcl';text=original.read_text().split('report_parasitic_annotation')[0]
        if text.count(str(route))!=1 or text.count('read_spef')!=2:raise ValueError('selected route and min/max parasitics required')
        sdc=re.search(r'^source (\S+)',text,re.M)
        if not sdc or 'set_false_path -from [get_ports RESET_N]' not in Path(sdc[1]).read_text():raise ValueError('expected external reset exception missing')
        for token in text.split():
            if token.startswith('/'):
                p=Path(token);pins[str(p)]=sha(p)
        pins[str(receipt)]=sha(receipt);pins[str(original)]=sha(original)
        folder=output/corner;folder.mkdir();script=folder/'checks.tcl'
        for kind in ('recovery','removal','min_pulse_width'):
            text+=f'puts OPENPLL_{kind}_BEGIN\nreport_check_types -{kind} -verbose -digits 6\nputs OPENPLL_{kind}_END\n'
        script.write_text(text+'exit\n');pins[str(script)]=sha(script);verify(pins)
        save(output/'status.json',dict(state='measuring_conditional_reset_checks',corner=corner,release_ready=False))
        log=folder/'native.log';os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with lease(1,4,deadline):execute(['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,OPENROAD,'-exit',script],log,deadline,4)
        text=log.read_text();artifacts[str(log)]=sha(log)
        for kind in ('recovery','removal','min_pulse_width'):
            begin=f'OPENPLL_{kind}_BEGIN';end=f'OPENPLL_{kind}_END'
            if text.count(begin)!=1 or text.count(end)!=1:raise ValueError('unique complete query markers required')
            rows.append(dict(corner=corner,**parse(text.split(begin)[1].split(end)[0],kind)))
    verify(pins);detail=output/'checks.json';save(detail,rows);artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,container_tool_sha256=foreign,artifacts=artifacts,checks=15,all_reported_worst_checks_pass=all(r['passed'] for r in rows),minimum_slack_ns={k:min(r['slack_ns'] for r in rows if r['check']==k) for k in ('recovery','removal','min_pulse_width')},scope='Worst enabled asynchronous-group recovery/removal and sequential clock pulse checks in existing five-corner 402.1MHz capacity views; not an exhaustive reset endpoint inventory.',external_reset_paths_excluded=True,existing_timing_exceptions_preserved=True,startup_and_reset_transition_modes_qualified=False,external_reset_minimum_pulse_qualified=False,reset_recovery_removal_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_reset_checks_assessed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
