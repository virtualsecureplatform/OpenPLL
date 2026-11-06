"""Control every stock antenna conductor/contact rule with matched physical fixtures.

The parent extraction style and technology are unchanged. Only one exposed
conductor or contact array changes per negative case. This is engine capability
coverage, not parent antenna qualification or diode-protection validation.
"""
import argparse,json,math,os,re,resource,shlex,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from extract_prototype_analog_capacitance_v2 import PDK,MAGIC

CELL='sky130_fd_sc_hs__buf_8'
METALS=[(67,20),(68,20),(69,20),(70,20),(71,20),(72,20)]
CONTACTS=[('licon',(66,44),.17,.34,8),('mcon',(67,44),.17,.34,8),('via1',(68,44),.15,.32,8),('via2',(69,44),.2,.4,8),('via3',(70,44),.2,.4,8),('via4',(71,44),.8,1.6,2)]


def run(parent,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_antenna_layer_control_resources',release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        receipt=parent/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        tech=PDK/'libs.tech/magic/sky130A.tech'
        if r.get('extraction_style')!='ngspice(orig)' or r['input_sha256'].get(str(tech))!=sha(tech):raise ValueError('same actual parent MOS-only style and technology required')
        directory=ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs';gds=directory/'gds/sky130_fd_sc_hs.gds';lef=directory/'lef/sky130_fd_sc_hs.lef'
        files=[Path(__file__).resolve(),Path(sys.executable),receipt,tech,gds,lef,Path(MAGIC),ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).with_name('extract_prototype_analog_capacitance_v2.py'),Path(__file__).with_name('compiled_charge.py'),Path(__file__).with_name('resources.py')];pins={str(p):sha(p) for p in files}
        save(output/'inputs.json',dict(input_sha256=pins,extraction_style='ngspice(orig)',technology_mutated=False,release_ready=False));results=[];baseline=None
        with lease(1,4,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));import pya
            core=Path(sys.modules[pya.Layout.__module__].__file__);pins[str(core)]=sha(core)
            source=pya.Layout();source.read(str(gds));original=source.cell(CELL)
            if original is None:raise ValueError('known stock control cell required')
            block=re.search(r'^MACRO '+CELL+r'\s*\n(.*?)^END '+CELL+r'\s*$',lef.read_text(),re.M|re.S)
            pin=re.search(r'^\s*PIN A\s*\n(.*?)^\s*END A\s*$',block[1],re.M|re.S) if block else None
            rect=re.search(r'LAYER li1\s*;\s*RECT\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*;',pin[1]) if pin else None
            if rect is None:raise ValueError('actual input pin geometry required')
            area=pya.Box(*(round(float(v)/source.dbu) for v in rect.groups()));li=pya.Region(original.begin_shapes_rec(source.layer(67,20))).merged()
            if not (pya.Region(area)-li).is_empty() or not pya.Region(original.begin_shapes_rec(source.layer(70,20))).is_empty():raise ValueError('covered actual LI1 input and unused M3 routing layer required')
            cx,cy=area.center().x*source.dbu,area.center().y*source.dbu;gate_input_area=None
            def original_region(layer):return pya.Region(original.begin_shapes_rec(source.layer(*layer))).merged()
            all_poly=original_region((66,20));all_diff=original_region((65,20));all_tap=original_region((65,44));all_licon=original_region((66,44))
            input_li=pya.Region()
            for polygon in li.each():
                part=pya.Region(polygon)
                if not (part & pya.Region(area)).is_empty():input_li+=part
            poly_access=all_poly & all_licon & input_li
            if poly_access.is_empty():raise ValueError('physical A poly-contact access required for process-staged controls')
            def direct_route(layer,landing):
                whole=original_region(layer);starts=[]
                if layer==(66,20):
                    for access in poly_access.each():
                        q=access.bbox().center()
                        for polygon in whole.each():
                            part=pya.Region(polygon)
                            if not (part & pya.Region(pya.Box(q.x-1,q.y-1,q.x+1,q.y+1))).is_empty():starts.append((q,part))
                else:
                    q=pya.Point(round(cx/source.dbu),round(cy/source.dbu));part=pya.Region()
                    for polygon in whole.each():
                        r=pya.Region(polygon)
                        if not (r & pya.Region(pya.Box(q.x-1,q.y-1,q.x+1,q.y+1))).is_empty():part+=r
                    starts=[(q,part)]
                width=.15 if layer==(66,20) else .17 if layer==(67,20) else .3 if layer==(68,20) else .4
                half=round(width/source.dbu/2);clearance=round((landing/2+3)/source.dbu);bounds=original.bbox()
                for q,part in starts:
                    forbidden=(whole-part).sized(5)
                    if layer==(66,20):forbidden+=all_tap+all_licon-part
                    for direction,end in [('left',pya.Point(bounds.left-clearance,q.y)),('right',pya.Point(bounds.right+clearance,q.y)),('down',pya.Point(q.x,bounds.bottom-clearance)),('up',pya.Point(q.x,bounds.top+clearance))]:
                        wire=pya.Region(pya.Box(min(q.x,end.x)-half,min(q.y,end.y)-half,max(q.x,end.x)+half,max(q.y,end.y)+half))
                        if not (wire & forbidden).is_empty():continue
                        if layer==(66,20) and not (((all_poly|wire)&all_diff)^(all_poly&all_diff)).is_empty():continue
                        return wire,end.x*source.dbu,end.y*source.dbu,direction
                raise ValueError('no stage-correct straight route preserves stock geometry: '+str(layer))
            gate_region=pya.Region(original.begin_shapes_rec(source.layer(66,20))) & pya.Region(original.begin_shapes_rec(source.layer(65,20)));expected_gate_area=F(gate_region.area())*F(str(source.dbu))**2
            if expected_gate_area<=0:raise ValueError('physical MOS channels required')
            pads=[('poly',(66,20))]+[(name,layer) for name,layer in zip(['li1','metal1','metal2','metal3','metal4','metal5'],METALS)]
            cases=[('stock_baseline',None,None,False)]
            for label,layer in pads:cases.extend([('normal_'+label,layer,None,False),('pad_'+label,layer,None,True)])
            for label,*_ in CONTACTS:cases.extend([('normal_'+label,None,label,False),('array_'+label,None,label,True)])
            for name,pad,mutant,negative in cases:
                folder=output/name;folder.mkdir();layout=pya.Layout();layout.dbu=source.dbu;leaf=layout.create_cell(CELL);leaf.copy_tree(original);top=layout.create_cell('AntennaLayerControl');top.insert(pya.CellInstArray(leaf.cell_index(),pya.Trans()))
                def box(layer,x0,y0,x1,y1):top.shapes(layout.layer(*layer)).insert(pya.Box(*(round(v/source.dbu) for v in [x0,y0,x1,y1])))
                def square(layer,x,y,width):box(layer,x-width/2,y-width/2,x+width/2,y+width/2)
                array_count=1;grow=[];landing=0.0
                if mutant:
                    index=next(i for i,c in enumerate(CONTACTS) if c[0]==mutant)
                    _,_,size,pitch,_=CONTACTS[index];ratio=3 if index<=2 else 6
                    array_count=math.ceil(math.sqrt(float(2*ratio*gate_input_area/F(str(size))**2)))
                    if array_count**2*F(str(size))**2<2*ratio*gate_input_area:raise ValueError('contact negative-control margin insufficient')
                    landing=(array_count-1)*pitch+size+.4
                    grow=[(66,20),METALS[0]] if index==0 else [METALS[index-1],METALS[index]]
                routing=None
                if name!='stock_baseline':
                    route_layer=(66,20) if pad==(66,20) or mutant=='licon' else METALS[0] if pad==METALS[0] or mutant=='mcon' else METALS[1] if pad==METALS[1] or mutant=='via1' else METALS[2] if pad==METALS[2] or mutant=='via2' else METALS[3]
                    route_index=-1 if route_layer==(66,20) else METALS.index(route_layer)
                    local=[((67,44),.17),((68,20),.3),((68,44),.15),((69,20),.4),((69,44),.2),((70,20),.6)]
                    for layer,width in local[:max(0,route_index)*2]:square(layer,cx,cy,width)
                    wire,outside,oy,direction=direct_route(route_layer,max(landing,.4));routing=dict(layer=list(route_layer),direction=direction)
                    top.shapes(layout.layer(*route_layer)).insert(wire)
                    high=5 if pad==METALS[5] or mutant=='via4' else 4 if pad==METALS[4] or mutant=='via3' else CONTACTS.index(next(c for c in CONTACTS if c[0]==mutant)) if mutant else route_index
                    low=route_index
                    for i in range(max(0,low),high+1):
                        layer=METALS[i];square(layer,outside,oy,landing if layer in grow else [.4,.3,.4,.6,1.6,1.6][i])
                    if low==-1:square((66,20),outside,oy,landing if (66,20) in grow else .4)
                    for index,(contact,layer,size,pitch,_) in enumerate(CONTACTS):
                        if index<=low or index>high:continue
                        n=array_count if contact==mutant and negative else 1
                        for i in range(n):
                            for j in range(n):square(layer,outside+(i-(n-1)/2)*pitch,oy+(j-(n-1)/2)*pitch,size)
                    if pad and negative:
                        if direction=='left':box(pad,outside-1000,oy-50,outside+.2,oy+50)
                        elif direction=='right':box(pad,outside-.2,oy-50,outside+1000,oy+50)
                        elif direction=='down':box(pad,outside-50,oy-1000,outside+50,oy+.2)
                        else:box(pad,outside-50,oy-.2,outside+50,oy+1000)
                fixture=folder/'fixture.gds';layout.write(str(fixture));rc=folder/'minimal.magicrc';rc.write_text('tech load {'+str(tech)+'}\n');script=folder/'control.tcl'
                script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{fixture}}}
load AntennaLayerControl -dereference
select top cell
flatten AntennaLayerFlat
load AntennaLayerFlat
cd {{{folder}}}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck debug
antennacheck
puts "ANTENNA_LAYER_FEEDBACK=[feedback count]"
feedback save {{{folder}/antenna.feedback}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
                pins.update({str(p):sha(p) for p in [fixture,rc,script]});save(output/'status.json',dict(state='native_antenna_layer_control_running',case=name,completed_cases=len(results),release_ready=False))
                execute([MAGIC,'-dnull','-noconsole','-rcfile',rc,script],folder/'magic.log',deadline,4)
                log=(folder/'magic.log').read_text();counts=re.findall(r'^ANTENNA_LAYER_FEEDBACK=(\d+)\s*$',log,re.M);ext=folder/'AntennaLayerFlat.ext'
                if len(counts)!=1 or not ext.exists():raise ValueError('complete native control output required')
                rows=sorted(line for line in ext.read_text().splitlines() if line.startswith('device '));mos=[shlex.split(line) for line in rows]
                if not mos or any(f[:2]!=['device','mosfet'] for f in mos):raise ValueError('same parent MOS-only primitive class required')
                gate_area=sum((F(f[7])*F(f[8])*F(1,200)**2 for f in mos),F(0));feedback=int(counts[0])
                if gate_area!=expected_gate_area or (baseline is not None and rows!=baseline):raise ValueError('MOS geometry/connectivity changed in antenna control')
                if baseline is None:
                    baseline=rows
                    gate_input_area=sum((F(f[7])*F(f[8])*F(1,200)**2 for f in mos if f[10]=='A' or f[10].endswith('.A')),F(0))
                    if gate_input_area<=0:raise ValueError('native input gate area required for contact control sizing')
                text=(folder/'antenna.feedback').read_text();planes=sorted(set(re.findall(r'Antenna error at plane ([^\n]+)',text)))
                result=dict(case=name,process_stage_routing=routing,negative_control=negative,contact_array_count=array_count if mutant and negative else 1,input_gate_area_um2=str(gate_input_area),changed_conductor=list(pad) if pad else None,changed_contact=mutant,feedback_entries=feedback,feedback_planes=planes,MOS_instances=len(rows),gate_area_um2=str(gate_area));results.append(result);save(output/'results.json',results)
                # Keep missed controls visible and characterize later layers;
                # this never converts a missed rule into qualification.
                results[-1]['expected_feedback_behavior_matches']=(feedback>0)==negative
                save(output/'results.json',results)
            verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ['assessment.json','status.json']},extraction_style='ngspice(orig)',technology_mutated=False,baseline_has_zero_feedback=results[0]['feedback_entries']==0,all_matched_baselines_have_zero_feedback=all(r['feedback_entries']==0 for r in results if not r['negative_control']),process_stage_appropriate_routes=True,conductor_negative_controls=len(pads),contact_negative_controls=len(CONTACTS),all_targeted_negative_controls_detected=all(r['feedback_entries']>0 for r in results if r['negative_control']),missed_or_invalid_controls=[r['case'] for r in results if not r['expected_feedback_behavior_matches']],MOS_geometry_connectivity_and_gate_area_preserved=True,diode_protection_control_complete=False,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='antenna_layer_capability_controls_characterized',release_ready=False));print('completed antenna cases',len(results))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),completed_cases=len(results) if 'results' in locals() else 0,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.parent.resolve(),a.output.resolve())
