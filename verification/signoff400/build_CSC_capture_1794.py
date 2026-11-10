"""Build a separate diagnostic CSC producer interposer; no numerical solve claimed."""
import time
from pathlib import Path
from common_v3 import ROOT,save,sha
from resources import lease
from compiled_charge_v2 import execute

def run():
    out=ROOT/'build/tools/xyce_CSC_capture_1794';out.mkdir(exist_ok=False)
    source=ROOT/'tools/xyce_umfpack/matrix_capture/capture_symbolic.c';binary=out/'capture_symbolic.so'
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+60
    with lease(1,2,deadline):execute(['/usr/bin/cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-shared','-fPIC',source,'-ldl','-o',binary],out/'build.log',deadline,2)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p)for p in [source,Path(__file__).resolve()]},artifacts={str(binary):sha(binary)},diagnostic_capture_only=True,simulation_qualification=False))
if __name__=='__main__':run()
