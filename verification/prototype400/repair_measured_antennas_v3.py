"""Place local diodes by partitioning existing filler footprints without moving logic."""
import re
from repair_measured_antennas_v2 import tcl_word, violation_targets


def filler_segments(width,offset):
    if width not in (2,4,8) or offset not in range(0,width,2):
        raise ValueError('aligned two-site diode in a supported filler required')
    segments=[]
    def fillers(start,count):
        for size in (8,4,2):
            while count>=size:
                segments.append((start,f'sky130_fd_sc_hs__fill_{size}'));start+=size;count-=size
        if count:raise ValueError('filler partition is not exact')
    fillers(0,offset)
    segments.append((offset,'sky130_fd_sc_hs__diode_2'))
    fillers(offset+2,width-offset-2)
    return sorted(segments)


def repair_tcl(targets,prefix='measured_partitioned_diode'):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',prefix):raise ValueError('unsafe diode prefix')
    chunks=[f'''set {prefix}_patterns [dict create]
proc {prefix}_place_bbox {{inst orient xmin ymin width height}} {{
 $inst setOrient $orient
 $inst setLocation 0 0
 set box [$inst getBBox]
 set dx [$box xMin];set dy [$box yMin]
 $inst setLocation [expr {{$xmin-$dx}}] [expr {{$ymin-$dy}}]
 $inst setPlacementStatus PLACED
 set box [$inst getBBox]
 if {{[list [$box xMin] [$box yMin] [$box xMax] [$box yMax]] ne [list $xmin $ymin [expr {{$xmin+$width}}] [expr {{$ymin+$height}}]]}} {{error "replacement footprint differs"}}
}}
set {prefix}_site_width [[[ord::get_db] findMaster sky130_fd_sc_hs__fill_1] getWidth]
set {prefix}_diode_width [[[ord::get_db] findMaster sky130_fd_sc_hs__diode_2] getWidth]
if {{${prefix}_diode_width != 2*${prefix}_site_width}} {{error "diode/site geometry differs"}}
''']
    for width in (2,4,8):
        for offset in range(0,width,2):
            segments=' '.join('{'+str(start)+' '+master+'}' for start,master in filler_segments(width,offset))
            chunks.append(f'dict set {prefix}_patterns {width}_{offset} {{{segments}}}')
    for index,(net,inst,pin) in enumerate(targets):
        chunks.append(r'''set target [$block findNet @NET@]
set sink_inst [$block findInst @INST@]
if {$target eq {NULL} || $sink_inst eq {NULL}} {error "missing measured antenna target"}
set sink_pin [$sink_inst findITerm @PIN@]
if {$sink_pin eq {NULL} || [$sink_pin getNet] ne $target} {error "antenna sink connectivity changed"}
lassign [$sink_inst getLocation] sx sy
set victim {};set best 2147483647;set best_width 2147483647;set best_offset -1
foreach donor [$block getInsts] {
 set master [[$donor getMaster] getName]
 if {$master ni {sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_8}} {continue}
 set sites [lindex [split $master _] end]
 set orient [$donor getOrient]
 if {$orient ni {R0 MX MY R180}} {error "unsupported standard-cell orientation"}
 set box [$donor getBBox]
 set xmin [$box xMin]
 if {[$box xMax]-$xmin != $sites*$@PREFIX@_site_width} {error "donor width differs"}
 lassign [$donor getLocation] x y
 for {set offset 0} {$offset<$sites} {incr offset 2} {
  set anchor [expr {$xmin+$offset*$@PREFIX@_site_width}]
  if {$orient in {MY R180}} {incr anchor $@PREFIX@_diode_width}
  set distance [expr {abs($anchor-$sx)+abs($y-$sy)}]
  if {$distance<$best || ($distance==$best && $sites<$best_width)} {
   set victim $donor;set best $distance;set best_width $sites;set best_offset $offset
  }
 }
}
if {$victim eq {} || $best>20000} {error "no compatible filler partition within 20um"}
set orient [$victim getOrient];set box [$victim getBBox]
set xmin [$box xMin];set ymin [$box yMin];set xmax [$box xMax];set ymax [$box yMax]
set height [expr {$ymax-$ymin}]
set donor_name [$victim getName]
set segments [dict get $@PREFIX@_patterns ${best_width}_${best_offset}]
odb::dbInst_destroy $victim
set cursor $xmin;set segment_index 0;set diode_count 0
foreach segment $segments {
 lassign $segment offset master
 set left [expr {$xmin+$offset*$@PREFIX@_site_width}]
 set model [[ord::get_db] findMaster $master]
 set width [$model getWidth]
 if {$left!=$cursor} {error "gap or overlap in filler partition"}
 if {$master eq {sky130_fd_sc_hs__diode_2}} {
  set name @PREFIX@_@INDEX@
 } else {set name @PREFIX@_@INDEX@_filler_$segment_index}
 if {[$block findInst $name] ne {NULL}} {error "fresh diode/filler names required"}
 set piece [odb::dbInst_create $block $model $name]
 @PREFIX@_place_bbox $piece $orient $left $ymin $width $height
 foreach pg {VPWR VPB} {[$piece findITerm $pg] connect [$block findNet VDD]}
 foreach pg {VGND VNB} {[$piece findITerm $pg] connect [$block findNet VSS]}
 if {$master eq {sky130_fd_sc_hs__diode_2}} {
  incr diode_count
  [$piece findITerm DIODE] connect $target
  lassign [$piece getLocation] x y
  set actual_distance [expr {abs($x-$sx)+abs($y-$sy)}]
  if {$actual_distance>20000} {error "actual diode placement exceeds 20um"}
  puts "LOCAL_DIODE_PARTITION donor=$donor_name sites=$best_width location=$x,$y distance_dbu=$actual_distance sink=[$sink_inst getName]"
 }
 incr cursor $width;incr segment_index
}
if {$cursor!=$xmax || $diode_count!=1} {error "donor footprint not preserved exactly"}
if {[$target getWire] ne {NULL}} {odb::dbWire_destroy [$target getWire]}
'''.replace('@PREFIX@',prefix).replace('@INDEX@',str(index)).replace('@NET@',tcl_word(net))
            .replace('@INST@',tcl_word(inst)).replace('@PIN@',tcl_word(pin)))
    return '\n'.join(chunks)
