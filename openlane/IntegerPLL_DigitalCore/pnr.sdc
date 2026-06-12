create_clock -name PLLOUT -period 8.000 [get_ports PLLOUT]
set_clock_transition 0.150 [get_clocks PLLOUT]
set_clock_uncertainty 0.250 [get_clocks PLLOUT]

set bbpd_inputs [get_ports -quiet -regexp {BBPD\[.*\]}]
if {[llength $bbpd_inputs] > 0} {
    set_input_delay 0.500 -clock [get_clocks PLLOUT] $bbpd_inputs
}

set clkdiv_output [get_ports -quiet CLKDIV_RETIMED]
if {[llength $clkdiv_output] > 0} {
    set_output_delay 0.500 -clock [get_clocks PLLOUT] $clkdiv_output
}

set async_inputs [get_ports -quiet RESET_N]
if {[llength $async_inputs] > 0} {
    set_false_path -from $async_inputs
}

set slow_config_inputs [concat \
    [get_ports -quiet DLF_Clear] \
    [get_ports -quiet DLF_En] \
    [get_ports -quiet DLF_IN_POL] \
    [get_ports -quiet DLF_Ext_Override] \
    [get_ports -quiet -regexp {DLF_Ext_Data\[.*\]}] \
    [get_ports -quiet -regexp {DLF_KP\[.*\]}] \
    [get_ports -quiet -regexp {DLF_KI\[.*\]}] \
    [get_ports -quiet -regexp {COARSEBINARY_CODE\[.*\]}] \
    [get_ports -quiet -regexp {MMDCLKDIV_RATIO\[.*\]}]]
if {[llength $slow_config_inputs] > 0} {
    set_false_path -from $slow_config_inputs
}

set dco_control_outputs [concat \
    [get_ports -quiet -regexp {DCO_THERM\[.*\]}] \
    [get_ports -quiet -regexp {DCO_CODE\[.*\]}] \
    [get_ports -quiet -regexp {DLF_CODE\[.*\]}] \
    [get_ports -quiet -regexp {COARSETHERMAL_CODE\[.*\]}] \
    [get_ports -quiet -regexp {Medium_BINARY_CODE\[.*\]}] \
    [get_ports -quiet -regexp {Fine_BINARY_CODE\[.*\]}] \
    [get_ports -quiet -regexp {Medium_CAPS_CTRL\[.*\]}] \
    [get_ports -quiet -regexp {Fine_CAPS_CTRL\[.*\]}]]
if {[llength $dco_control_outputs] > 0} {
    set_false_path -to $dco_control_outputs
}
