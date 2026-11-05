# GRT routes one top-level terminal per net. Give aliased output ports their
# own physical driver/net, preserving the logical value of each interface.
set block [ord::get_db_block]
set export_index 0
foreach net [$block getNets] {
    if {[$net getSigType] ne {SIGNAL}} {continue}
    set ports [$net getBTerms]
    if {[llength $ports] < 2} {continue}
    foreach port [lrange $ports 1 end] {
        if {[$port getIoType] ne {OUTPUT}} {error "unexpected shared input port"}
        set name export_alias_$export_index
        incr export_index
        set buffer [odb::dbInst_create $block [[ord::get_db] findMaster @SCL@__buf_4] $name]
        set output [odb::dbNet_create $block ${name}_out]
        [$buffer findITerm A] connect $net
        [$buffer findITerm X] connect $output
        $port disconnect
        $port connect $output
        set location [[$block getCoreArea] xMin]
        set bottom [[$block getCoreArea] yMin]
        $buffer setLocation $location $bottom
        $buffer setPlacementStatus PLACED
        puts "ISOLATED_EXPORT_ALIAS [$port getName] via $name"
    }
}
