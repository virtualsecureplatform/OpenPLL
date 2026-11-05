"""Native unit control for raw-extraction versus effective diode geometry on ngspice47."""
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run():
    out=ROOT/'build/signoff400/prototype_v3_ng47_diode_units_control_001';out.mkdir(exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4))
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    paths=[image,ng,Path(__file__).resolve(),ROOT/'scripts/sky130_diode_translation_probe.py',ROOT/'build/signoff400/prototype_v3_resistor_wrapper_review_001/pinned_PDK_r_c_wrapper.spice']
    pins={str(p):sha(p) for p in paths};results=[];artifacts={}
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    for name,area,perim in (('raw_extraction','4.347e11','2.64e6'),('effective_geometry','.4347','2.64')):
        folder=out/name;folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
        deck=folder/'diode.cir';deck.write_text(f'''* Native ngspice47 HD antenna diode geometry control
.lib "{pdk}" tt
.temp 27
.option klu scale=1u reltol=1e-7 abstol=1e-15 num_threads=1
Vbias bias 0 DC 0.9 AC 1
XD 0 bias sky130_fd_pr__diode_pw2nd_05v5 area={area} perim={perim}
.ac lin 1 1meg 1meg
.print ac real(vbias#branch) imag(vbias#branch)
.end
''')
        log=folder/'native.log';save(out/'status.json',dict(state='native_diode_units_control_running',case=name,release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+120),4)
        rows=[]
        for line in log.read_text().splitlines():
            f=line.split()
            if f and f[0].isdigit():
                if len(f)!=4:raise ValueError('unexpected native AC table')
                rows.append(list(map(float,f[1:])))
        if len(rows)!=1 or not all(math.isfinite(x) for x in rows[0]) or rows[0][0]!=1e6:raise ValueError('one finite 1 MHz native AC point required')
        freq,real,imag=rows[0];results.append(dict(case=name,capacitance_F=abs(imag)/(2*math.pi*freq),real_source_current_A=real,imag_source_current_A=imag))
        artifacts.update({str(p):sha(p) for p in (deck,init,log)})
    raw,effective=[r['capacitance_F'] for r in results]
    if not 0<effective<1e-13 or raw/effective<1e9:raise ValueError('native geometry unit mismatch not established')
    detail=out/'observations.json';save(detail,dict(results=results,raw_to_effective_capacitance_ratio=raw/effective));artifacts[str(detail)]=sha(detail);verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,ng47_raw_geometry_mismatch_confirmed=True,
        effective_geometry_area_um2=.4347,effective_geometry_perimeter_um=2.64,raw_to_effective_capacitance_ratio=raw/effective,
        full_geometry_electrical_qualification=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(out/'status.json',dict(state='native_diode_units_control_complete',release_ready=False))
    print('Raw/effective capacitance ratio:',raw/effective)


if __name__=='__main__':run()
