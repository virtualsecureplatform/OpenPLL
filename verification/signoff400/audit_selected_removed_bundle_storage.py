"""Prove omitted bundle storage has no mapped hardware consumers or drivers.

This component audit does not waive CDC paths or establish payload timing.
"""
import argparse,json,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins,BINDING
from compare_mapped_routed_CDC import identifier

def analyze(module,bundles):
    uses={}
    for name,cell in module['cells'].items():
        for pin,bits in cell['connections'].items():
            for bit in bits:
                if isinstance(bit,str)and bit.lower()in ('x','z'):raise ValueError('unknown value reaches active cell pin')
                if type(bit)is int:uses.setdefault(bit,[]).append(('cell',name,pin))
                elif bit not in ('0','1'):raise ValueError('invalid mapped cell connection bit')
    for name,port in module['ports'].items():
        for bit in port['bits']:
            if isinstance(bit,str)and bit.lower()in ('x','z'):raise ValueError('unknown value reaches module port')
            if type(bit)is int:uses.setdefault(bit,[]).append(('port',name))
            elif bit not in ('0','1'):raise ValueError('invalid mapped module port bit')
    cells={identifier(n):c for n,c in module['cells'].items()}
    if len(cells)!=len(module['cells']):raise ValueError('ambiguous mapped cell identities')
    records=[];seen=set()
    for bundle in bundles:
        alias=module['netnames'].get(bundle['id']);width=bundle['logical_width']
        if alias is None or len(alias['bits'])!=width or alias.get('offset',0)!=0:raise ValueError('complete logical bundle alias required')
        implemented={}
        for row in bundle['implemented_destination_registers']:
            bit=row['logical_bit'];name=identifier(row['mapped_cell'])
            if type(bit)is not int or not 0<=bit<width or bit in implemented or name in seen:
                raise ValueError('distinct implemented logical bits and storage required')
            seen.add(name);cell=cells[name]
            if not re.fullmatch(r'sky130_fd_sc_hs__df[rs]tp_[124]',cell['type']):raise ValueError('supported physical capture flip-flop required')
            if cell['port_directions'].get('Q')!='output'or cell['connections'].get('Q')!=[alias['bits'][bit]]:
                raise ValueError('retained logical bit not directly driven by declared capture Q')
            implemented[bit]=name
        removed=[]
        for index,net in enumerate(alias['bits']):
            if index in implemented:continue
            if type(net)is int:
                if uses.get(net):raise ValueError('removed logical bit still touches active hardware or a module port')
                kind='integer_alias_without_hardware_endpoints'
            elif net=='x':kind='optimized_unknown_alias_with_no_active_unknown_consumers'
            else:raise ValueError('unreviewed omitted literal requires separate provenance')
            removed.append(dict(logical_bit=index,mapped_alias_bit=net,classification=kind))
        records.append(dict(bundle=bundle['id'],logical_width=width,implemented_bits=sorted(implemented),removed_bits=removed,
            removed_storage_unobservable_in_mapped_hardware=True))
    return records

def run(output):
    if output.exists():raise FileExistsError(output)
    pins=source_pins();base=ROOT/'build/signoff400'
    obligations=base/'prototype_v3_selected_CDC_obligations_019/assessment.json'
    routed_receipt=base/'prototype_v3_selected_routed_CDC_019/assessment.json'
    a,r=[json.loads(p.read_text())for p in (obligations,routed_receipt)]
    for v in(a,r):verify(v['input_sha256']);verify(v['artifacts'])
    if r['state_source_cones_and_clock_roots_match']is not True:raise ValueError('matching mapped/routed state inventory required')
    mapped=[Path(p)for p in a['input_sha256']if p.endswith('/mapped.json')]
    routed=[Path(p)for p in a['input_sha256']if p.endswith('/routed.json')]
    if len(mapped)!=1 or len(routed)!=1:raise ValueError('unique mapped/routed module pair required')
    if r['input_sha256'].get(str(mapped[0]))!=sha(mapped[0])or r['artifacts'].get(str(routed[0]))!=sha(routed[0]):
        raise ValueError('obligations not bound to selected routed inventory')
    binding=json.loads(BINDING.read_text());layout=json.loads((ROOT/binding['physical_receipt']['path']).read_text())
    route=base/'prototype_v3_selected_route_019/assessment.json';rv=json.loads(route.read_text())
    if r['input_sha256'].get(str(route))!=sha(route):raise ValueError('routed inventory lacks selected route lineage')
    route_gds=base/'prototype_v3_selected_route_019/signoff/route.gds'
    signoff=route.parent/'signoff/assessment.json';sv=json.loads(signoff.read_text());verify(sv['sha256'])
    odb=route.parent/'route.odb'
    if layout['input_sha256'].get(str(signoff))!=sha(signoff)or layout['input_sha256'].get(str(route_gds))!=sha(route_gds):
        raise ValueError('parent layout must pin the digital signoff receipt and GDS')
    if sv['sha256'].get(str(route_gds))!=sha(route_gds)or sv['sha256'].get(str(odb))!=rv['artifacts'].get(str(odb))or sha(odb)!=sv['sha256'][str(odb)]:
        raise ValueError('same routed database and streamed digital GDS required')
    detail=obligations.parent/'obligations.json';v=json.loads(detail.read_text());bundles=v['bundles']
    module=json.loads(mapped[0].read_text())['modules']['IntegerPLL_ProgrammedCore']
    records=analyze(module,bundles)
    route_cells=json.loads(routed[0].read_text())['modules']['IntegerPLL_ProgrammedCore']['cells']
    for b in bundles:
        for row in b['implemented_destination_registers']:
            if route_cells[row['routed_cell']]['type']!=row['routed_master']:raise ValueError('retained routed capture master changed')
    if len(records)!=2 or any(x['logical_width']!=34 for x in records)or sorted(len(x['implemented_bits'])for x in records)!=[1,29]:
        raise ValueError('actual selected two-bundle storage inventory changed')
    paths=[obligations,routed_receipt,detail,*mapped,*routed,route,signoff,odb,route_gds,Path(__file__).with_name('common_v3.py'),Path(__file__).resolve(),Path(__file__).with_name('compare_mapped_routed_CDC.py')]
    pins.update({str(p):sha(p)for p in paths});verify(pins)
    save(output,dict(input_sha256=pins,records=records,retained_capture_registers=30,removed_logical_storage_bits=38,
        removed_storage_unobservable_in_mapped_hardware=True,retained_captures_bound_to_selected_routed_cells=True,
        scope='Logical constant-or-unused storage obligation: these omitted bits are proven unused, not assigned invented constant values. Does not prove protocol safety, initial static-input setup, payload arrival/hold or reset recovery.',
        all_crossings_reviewed=False,bundled_data_timing_qualified=False,digital_timing_and_CDC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
