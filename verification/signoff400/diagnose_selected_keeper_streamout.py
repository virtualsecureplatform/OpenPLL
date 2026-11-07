"""Replay completed keeper stream-out with explicit cell replacement, without rerouting."""
import argparse,json,shlex,subprocess
from pathlib import Path
from common_v3 import ROOT,sha,save


def run(flow,output):
    output.mkdir(parents=True,exist_ok=False)
    command_file=flow/'48-klayout-streamout/COMMANDS'
    command=shlex.split(command_file.read_text())
    if command[command.index('--conflict-resolution')+1]!='RenameCell':
        raise ValueError('expected original RenameCell stream-out')
    original=Path(command[command.index('--output')+1])
    source=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells/inv/sky130_fd_sc_hs__inv_2.gds'
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),command_file,original,source,image]}
    candidate=output/'overwrite.gds'
    command[command.index('--output')+1]=str(candidate)
    command[command.index('--conflict-resolution')+1]='OverwriteCell'
    with (output/'streamout.log').open('x') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    # Execute this script inside the pinned image to use its KLayout Python module.
    import klayout.db as k
    def load(path):
        layout=k.Layout();layout.read(str(path));return layout
    before,after,library=map(load,[original,candidate,source])
    name='sky130_fd_sc_hs__inv_2'
    differences=[]
    for info in library.layer_infos():
        a=k.Region(after.cell(name).begin_shapes_rec(after.layer(info)))
        b=k.Region(library.cell(name).begin_shapes_rec(library.layer(info)))
        differences.append({'layer':str(info),'xor_area_dbu2':(a^b).area()})
    def li_stats(layout):
        li=layout.find_layer(67,20)
        cell=k.Region(layout.cell(name).begin_shapes_rec(li));cell.merge()
        top=k.Region(layout.top_cell().begin_shapes_rec(li));top.merge()
        return dict(cell_li_area_dbu2=cell.area(),cell_li_polygons=cell.count(),
                    top_li_polygons_below_0056_um2=sum(p.area()*layout.dbu**2<0.056 for p in top.each()))
    assessment=dict(input_sha256=pins,command=command,original=li_stats(before),candidate=li_stats(after),
        source_cell_layer_comparison=differences,source_geometry_restored=all(x['xor_area_dbu2']==0 for x in differences),
        candidate_gds_sha256=sha(candidate),power_connectivity_qualified=False,DRC_LVS_qualified=False,
        selected=False,release_ready=False)
    if before.dbu!=after.dbu or after.dbu!=library.dbu:raise ValueError('DBU mismatch')
    if not assessment['source_geometry_restored'] or not assessment['candidate']['cell_li_area_dbu2']:
        raise ValueError('HS source geometry was not restored')
    from common_v3 import verify
    verify(pins);save(output/'assessment.json',assessment)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--flow',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.flow.resolve(),a.output.resolve())
