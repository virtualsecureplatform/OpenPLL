"""Inventory linked digital pins, declared limits and propagated electrical values.

The supplied native timing/load models and external-port assumptions remain
conditional. This inventory cannot qualify physical electrical rules by itself.
"""
import argparse,csv,io,json,math,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from report_selected_electrical_margins_v2 import OPENROAD


def direct(text):
    depth=0;quoted=False;escaped=False;result=[]
    for ch in text:
        if ch=='"' and not escaped:quoted=not quoted
        if not quoted:
            if ch=='{':depth+=1
            elif ch=='}':depth-=1
        if depth<0:raise ValueError('unbalanced Liberty group')
        result.append(ch if depth==0 else ('\n'if ch=='\n'else ' '))
        escaped=(ch=='\\'and not escaped)
    if depth or quoted:raise ValueError('incomplete Liberty group')
    return ''.join(result)


def groups(text,kind):
    # This reader is deliberately limited to the rendered native-library format.
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    pattern=re.compile(r'^\s*'+re.escape(kind)+r'\s*\(\s*([^()]+?)\s*\)\s*\{',re.M)
    result=[];end=0
    for match in pattern.finditer(text):
        if match.start()<end:continue
        start=match.end();depth=1;quoted=False;escaped=False;at=start
        while at<len(text)and depth:
            ch=text[at]
            if ch=='"'and not escaped:quoted=not quoted
            if not quoted:
                if ch=='{':depth+=1
                elif ch=='}':depth-=1
            escaped=(ch=='\\'and not escaped);at+=1
        if depth or quoted:raise ValueError('incomplete Liberty group')
        name=match.group(1).strip().strip('"');result.append((name,text[start:at-1]));end=at
    return result


def scalar(text,key,required=False):
    values=re.findall(r'^\s*'+re.escape(key)+r'\s*:\s*([^;]+);',direct(text),re.M)
    if len(values)>1 or required and not values:raise ValueError('missing or duplicate '+key)
    return values[0].strip().strip('"')if values else None


def library(path):
    containers=groups(path.read_text(),'library')
    if len(containers)!=1:raise ValueError('one rendered library required')
    body=containers[0][1]
    if scalar(body,'time_unit',True)!='1ns' or not re.search(r'capacitive_load_unit\s*\(\s*1\s*,\s*pf\s*\)',direct(body)):
        raise ValueError('explicit ns and pF units required')
    default=float(scalar(body,'default_max_transition',True));cells={}
    if not math.isfinite(default)or default<=0:raise ValueError('positive inherited transition limit required')
    for name,block in groups(body,'cell'):
        if name in cells:raise ValueError('duplicate cell')
        pins={}
        for pin,definition in groups(block,'pin'):
            if pin in pins:raise ValueError('duplicate pin')
            direction=scalar(definition,'direction',True)
            if direction not in ['input','output','inout']:raise ValueError('supported pin direction required')
            fields={}
            for field in ['max_transition','max_capacitance']:
                value=scalar(definition,field)
                fields[field]=None if value is None else float(value)
                if fields[field]is not None and (not math.isfinite(fields[field])or fields[field]<0):raise ValueError('finite nonnegative electrical limit required')
            pins[pin]=dict(direction=direction,function=scalar(definition,'function'),**fields)
        cells[name]=pins
    if not cells:raise ValueError('rendered cells required')
    return dict(default_max_transition=default,cells=cells)


FIELDS=['kind','pin','master','port','power','driver','load','vertices','net_connected','rise_min_ns','rise_max_ns','fall_min_ns','fall_max_ns','cap_min_pf','cap_max_pf']


def table_rows(path):
    lines=path.read_text().splitlines()
    if not lines or len(lines[0].split('\t'))!=3 or not lines[0].startswith('COUNT\t')or not lines[-1].startswith('DONE\t'):
        raise ValueError('complete native inventory markers required')
    pins,ports=map(int,lines[0].split('\t')[1:]);expected=pins+ports
    reader=csv.DictReader(io.StringIO('\n'.join(lines[1:-1])),delimiter='\t')
    if reader.fieldnames!=FIELDS:raise ValueError('exact native inventory columns required')
    rows=list(reader)
    if len(rows)!=expected or int(lines[-1].split('\t')[1])!=expected:raise ValueError('complete native pin count required')
    if len({(r['kind'],r['pin'])for r in rows})!=len(rows):raise ValueError('duplicate native pin')
    if sum(r['kind']=='cell'for r in rows)!=pins or sum(r['kind']=='port'for r in rows)!=ports:raise ValueError('native cell/port counts differ')
    for row in rows:
        if None in row or any(row[f]not in ['0','1']for f in ['power','driver','load','net_connected']):raise ValueError('invalid native row')
        row['vertices']=int(row['vertices'])
        row['native_nonfinite_fields']=[]
        for field in FIELDS[9:]:
            value=None if row[field]=='NA'else float(row[field])
            if value is not None and not math.isfinite(value):row['native_nonfinite_fields'].append(field);value=None
            row[field]=value
    return rows


def summarize(rows,lib):
    issues=[];details=[];slew_margins=[];cap_margins=[];zero=[];unconnected=[];ties=[]
    for row in rows:
        if row['kind']=='port' or row['power']=='1':continue
        definition=lib['cells'].get(row['master'],{}).get(row['port'])
        reasons=[]
        if definition is None:reasons.append('missing_library_pin')
        slew=[row[f]for f in FIELDS[9:13]]
        if not row['vertices']or any(v is None or not math.isfinite(v)or v<0 for v in slew):reasons.append('missing_or_nonfinite_propagated_slew')
        elif min(slew)==0:zero.append(row['pin'])
        limit=definition['max_transition']if definition else None
        if limit is None and definition:limit=lib['default_max_transition']
        if limit is not None and not any(v is None or not math.isfinite(v)for v in slew):slew_margins.append(dict(pin=row['pin'],limit_ns=limit,measured_max_ns=max(slew),margin_ns=limit-max(slew)))
        cap=definition['max_capacitance']if definition else None
        if row['driver']=='1':
            connected=row['net_connected']=='1'
            if not connected:unconnected.append(row['pin'])
            if definition and definition['function']in ['0','1']:
                ties.append(dict(pin=row['pin'],net_connected=connected,modeled_connected_net_load_pf=row['cap_max_pf']))
            if connected and cap is None:reasons.append('missing_output_capacitance_limit')
            value=row['cap_max_pf']if connected else 0.0
            if connected and (value is None or not math.isfinite(value)or value<0):reasons.append('missing_or_nonfinite_total_net_capacitance')
            elif cap is not None:cap_margins.append(dict(pin=row['pin'],limit_pf=cap,modeled_connected_net_load_pf=value,margin_pf=cap-value))
        detail=dict(**row,transition_limit_ns=limit,capacitance_limit_pf=cap,coverage_issues=reasons);details.append(detail)
        if reasons:issues.append(dict(pin=row['pin'],master=row['master'],reasons=reasons))
    return dict(native_cell_pins=sum(r['kind']=='cell'for r in rows),native_top_ports=sum(r['kind']=='port'for r in rows),
        digital_signal_pins_reviewed=len(details),coverage_issue_count=len(issues),coverage_issues=issues,
        zero_slew_signal_pins=zero,zero_slew_signal_pin_count=len(zero),
        unconnected_output_pins=unconnected,unconnected_output_pin_count=len(unconnected),constant_tie_outputs=ties,
        worst_inventory_slew_margin=min(slew_margins,key=lambda r:r['margin_ns'])if slew_margins else None,
        worst_inventory_capacitance_margin=min(cap_margins,key=lambda r:r['margin_pf'])if cap_margins else None),details


def native_script(prefix,destination):
    body=r'''
report_check_types -max_slew -max_capacitance
set corner [sta::cmd_corner]
set f [open {@DEST@} w]
set cells [get_pins -hierarchical *]
set ports [get_ports *]
puts $f "COUNT\t[llength $cells]\t[llength $ports]"
puts $f "@FIELDS@"
set count 0
foreach kind {cell port} {
 set objects [expr {$kind eq "cell" ? $cells : $ports}]
 foreach object $objects {
  set pin [sta::get_port_pin_error pin $object]
  set lp [$pin liberty_port]
  set master NA
  set port NA
  if {$lp ne "NULL"} {set master [[$lp cell] name];set port [get_full_name $lp]}
  set vertices [$pin vertices]
  set values {}
  foreach rf {rise fall} {
   foreach mode {min max} {
    set observed {}
    foreach vertex $vertices {lappend observed [string trim [sta::format_time [$vertex slew $rf $mode] 12]]}
    if {[llength $observed]} {
     set ordered [lsort -real $observed]
     lappend values [expr {$mode eq "min" ? [lindex $ordered 0] : [lindex $ordered end]}]
    } else {lappend values NA}
   }
  }
  set net [$pin net]
  if {$kind eq "port" && $net eq "NULL"} {
   set term [$pin term]
   if {$term ne "NULL"} {set net [$term net]}
  }
  set caps {NA NA}
  if {$net ne "NULL"} {
   set caps {}
   foreach mode {min max} {lappend caps [string trim [sta::format_capacitance [$net capacitance $corner $mode] 12]]}
  }
  puts $f [join [concat [list $kind [get_full_name $pin] $master $port [$pin is_pwr_gnd] [$pin is_driver] [$pin is_load] [llength $vertices] [expr {$net ne "NULL"}]] $values $caps] "\t"]
  incr count
 }
}
puts $f "DONE\t$count"
close $f
exit
'''
    return prefix+body.replace('@DEST@',str(destination)).replace('@FIELDS@',chr(9).join(FIELDS))


def run(source,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    receipt=source/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    pins={str(p):sha(p)for p in [receipt,image,Path(OPENROAD),Path(__file__).resolve(),Path(__file__).with_name('report_selected_electrical_margins_v2.py')]};pins.update(a['input_sha256'])
    artifacts={};results={};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    for corner in ['tt','ff','ss','sf','fs']:
        old=source/(corner+'.tcl')
        if a['input_sha256'].get(str(old))!=sha(old):raise ValueError('bound original native script required')
        prefix=old.read_text().split('puts OPENPLL_ELECTRICAL_MARGIN_BEGIN')[0]
        paths=re.findall(r'^read_liberty -(?:min|max) (\S+)$',prefix,re.M)
        if len(paths)!=2:raise ValueError('one early/late library pair required')
        libs=[library(Path(p))for p in paths]
        if libs[0]!=libs[1]:raise ValueError('identical early/late electrical constraints required')
        sdcs=re.findall(r'^source (\S+)$',prefix,re.M)
        if len(sdcs)!=1 or re.search(r'\bset_max_(transition|capacitance)\b',Path(sdcs[0]).read_text()):raise ValueError('unmodified library-derived limits required')
        table=output/(corner+'.tsv');script=output/(corner+'.tcl');log=output/(corner+'.log')
        script.write_text(native_script(prefix,table));pins[str(script)]=sha(script)
        save(output/'status.json',dict(state='inventorying_digital_pin_electrical_coverage',corner=corner,release_ready=False))
        with lease(1,4,deadline):execute([OPENROAD,'-no_init','-exit',script],log,deadline,4)
        rows=table_rows(table)
        for name in ['REFCLK','PLLOUT','RESET_N','PLL_ENABLE']:
            bound=[r for r in rows if r['kind']=='port'and r['pin']==name]
            if len(bound)!=1 or bound[0]['net_connected']!='1':raise ValueError('critical port internal-net binding missing: '+name)
        result,details=summarize(rows,libs[0]);results[corner]=result
        detail=output/(corner+'_pins.json');save(detail,details)
        artifacts.update({str(p):sha(p)for p in [table,log,detail]})
    verify(pins);verify(artifacts)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_five_corner_linked_digital_pin_inventories_completed=True,
        top_port_net_scope='internal terminal net when no outer net exists',critical_port_internal_connections_verified=True,external_port_contracts_qualified=False,zero_slew_sources_reviewed=False,native_timing_views_qualified=False,load_models_qualified=False,
        startup_frequency_range_qualified=False,parent_analog_macros_covered=False,electrical_rules_qualified=False,physical_integrity_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='digital_pin_electrical_inventory_completed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['source','image','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.image.resolve(),a.output.resolve())
