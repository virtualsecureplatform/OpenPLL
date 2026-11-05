# Reuse the six isolated receivers; do not insert a second reset-buffer layer.
set block [ord::get_db_block]
set source [$block findNet RESET_N]
if {$source eq {NULL}} {error "missing external reset net"}
set expected {}
for {set i 0} {$i < 6} {incr i} {
    set leaf [$block findInst external_reset_leaf_$i]
    if {$leaf eq {NULL}} {error "missing isolated reset leaf"}
    if {[[$leaf findITerm A] getNet] ne $source} {error "reset leaf input disconnected"}
    set out [[$leaf findITerm X] getNet]
    if {$out eq {NULL}} {error "reset leaf output disconnected"}
    set receivers 0
    foreach term [$out getITerms] {
        if {[$term getIoType] ne {INPUT}} {continue}
        if {[[$term getMTerm] getName] ni {RESET_B SET_B}} {error "unexpected reset leaf sink"}
        incr receivers
    }
    if {$receivers != 1 || [llength [$out getBTerms]] != 0} {error "reset leaf is not private"}
    lappend expected [$leaf findITerm A]
}
if {[lsort [$source getITerms]] ne [lsort $expected]} {error "unexpected external reset load"}
puts "VALIDATED_EXTERNAL_RESET_LEAVES count=6"
