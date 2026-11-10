"""Verify a hierarchical NODESET is released before final native DC output."""
import csv,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute

def run():
    out=ROOT/'build/signoff400/selected_nodeset_release_control_1824';out.mkdir(exist_ok=False)
    binary=ROOT/'build/tools/xyce_metis_ordering_1790/Xyce';build=binary.parent/'assessment.json';r=json.loads(build.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    data=out/'dc.csv';deck=out/'control.spice'
    deck.write_text('* NODESET is a starting guess, not a physical clamp\n.subckt cell p\nR1 p b 1\nR2 b 0 1\n.ends cell\nV1 a 0 1\nXDUT a cell\n.nodeset v(xdut:b)=0.9\n.dc V1 1 1 1\n.print dc format=csv precision=17 file='+str(data)+' v(a) v(xdut:b)\n.end\n')
    pins={str(p):sha(p)for p in [binary,build,deck,Path(__file__).resolve()]};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+60
    with lease(1,4,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],out/'native.log',deadline,4)
    rows=list(csv.reader(data.read_text().splitlines()))
    if rows[0]!=['V(A)','V(XDUT:B)'] or list(map(float,rows[1]))!=[1.,.5]:raise ValueError('NODESET remained a clamp or hierarchy lookup failed')
    log=(out/'native.log').read_text()
    if any(t in log.lower()for t in ['ignoring nodes:','unrecognized .nodeset','ignored .nodeset']):raise ValueError('native NODESET was ignored')
    verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [data,out/'native.log']},hierarchical_nodeset_accepted=True,nodeset_released_before_final_DC=True,analytical_unclamped_DC_verified=True,full_RC_qualified=False,release_ready=False))
if __name__=='__main__':run()
