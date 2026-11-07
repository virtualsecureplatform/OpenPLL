"""Compare native flat signed/default exports of unchanged hierarchical EXT data."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease,identity
from audit_hierarchical_capacitance import number
MAGIC=Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
TECH=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech')


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    native=next(source.glob('*/capacitance.spice')).parent;top=native.name;ext=native/(top+'.ext')
    if r['artifacts'].get(str(ext))!=sha(ext):raise ValueError('native hierarchy EXT differs')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600;save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    script=output/'replay.tcl';lines=[f'cd {{{native}}}','ext2spice lvs','ext2spice hierarchy off','ext2spice short resistor','ext2spice subcircuit top on']
    for name,threshold in [('default_threshold','0'),('signed_threshold','-1e100')]:lines.extend([f'ext2spice cthresh {threshold}',f'ext2spice -y 9 -o {{{output/(name+".spice")}}} {top}.ext'])
    lines.append('quit -noprompt');script.write_text('\n'.join(lines)+'\n');files=[receipt,ext,rc,script,MAGIC,TECH,Path(__file__).resolve()];pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins,source_EXT_directory_mounted_read_only=True,signed_diagnostic_threshold_fF='-1e100'))
    try:
        save(output/'status.json',dict(state='native_flat_signed_export_running',release_ready=False))
        with lease(1,8,deadline):execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,8)
        artifacts={};results=[]
        for name in ['default_threshold','signed_threshold']:
            path=output/(name+'.spice');values=[]
            for line in path.read_text().splitlines():
                f=line.split()
                if f and f[0][0].upper()=='C':
                    if len(f)!=4:raise ValueError('constant flat capacitor expected')
                    values.append(number(f[-1]))
            if not values:raise ValueError('native flat export empty')
            artifacts[str(path)]=sha(path);results.append(dict(export=name,capacitor_cards=len(values),negative_capacitor_cards=sum(v<0 for v in values),zero_capacitor_cards=sum(v==0 for v in values)))
        verify(pins);verify(r['input_sha256']);verify(r['artifacts']);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,geometry_reextracted=False,source_EXT_artifacts_unchanged=True,coefficient_equivalence_qualified=False,passivity_qualified=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='native_flat_signed_exports_complete_comparison_pending',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
