# Placement ECOs address measured long-wire max paths. Existing clock branches
# and sequential cells stay fixed. Acceptance requires new routed extraction.
proc closure_localize {} {
    global closure_corners
    set block [ord::get_db_block]
    set candidates {}
    foreach corner $closure_corners {
        foreach path [find_timing_paths -corner $corner -path_delay max -group_path_count 30 -slack_max 0.10 -sort_by_slack] {
            foreach point [get_property $path points] {
                set inst [$block findInst [file dirname [get_full_name [get_property $point pin]]]]
                if {$inst eq {NULL} || [closure_protected $inst] || [$inst findITerm Q] ne {NULL} || [$inst findITerm CLK] ne {NULL}} {continue}
                dict set candidates [$inst getName] 1
            }
        }
    }
    set changed 0
    for {set pass 0} {$pass < 3} {incr pass} {
        set positions {}
        foreach name [dict keys $candidates] {
            set inst [$block findInst $name]
            set xs {}
            set ys {}
            foreach term [$inst getITerms] {
                if {[$term getSigType] ne {SIGNAL} || [$term getNet] eq {NULL}} {continue}
                foreach neighbor [[$term getNet] getITerms] {
                    set owner [$neighbor getInst]
                    if {$owner eq $inst} {continue}
                    lassign [$owner getLocation] x y
                    lappend xs $x
                    lappend ys $y
                }
            }
            if {![llength $xs]} {continue}
            set xs [lsort -integer $xs]
            set ys [lsort -integer $ys]
            set middle [expr {[llength $xs] / 2}]
            lassign [$inst getLocation] x y
            # Limit each pass to 50 um; detailed placement legalizes the sites.
            set nx [expr {$x + max(-50000, min(50000, [lindex $xs $middle] - $x))}]
            set ny [expr {$y + max(-50000, min(50000, [lindex $ys $middle] - $y))}]
            if {abs($nx-$x) + abs($ny-$y) >= 1000} {dict set positions $name [list $nx $ny]}
        }
        dict for {name location} $positions {
            set inst [$block findInst $name]
            closure_log [list move_data $name from [$inst getLocation] to $location]
            $inst setLocation {*}$location
            incr changed
        }
    }
    # Place first reset banks beside their FF source. Their stronger buffer
    # outputs, rather than the source Q, then drive the distant leaf wiring.
    foreach inst [$block getInsts] {
        if {![regexp {^closure_reset_[0-9]+_root(_[0-9]+)?$} [$inst getName]]} {continue}
        set net [[$inst findITerm A] getNet]
        foreach term [$net getITerms] {
            if {[$term getIoType] eq {OUTPUT} && [[$term getMTerm] getName] eq {Q}} {
                set target [[$term getInst] getLocation]
                if {[$inst getLocation] ne $target} {
                    closure_log [list move_reset_root [$inst getName] from [$inst getLocation] to $target]
                    $inst setLocation {*}$target
                    incr changed
                }
            }
        }
    }
    return $changed
}
