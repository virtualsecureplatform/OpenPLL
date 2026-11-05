create_clock -name REFCLK -period 40 [get_ports REFCLK]
create_clock -name PLLOUT -period 2.222222 [get_ports PLLOUT]
create_generated_clock -name FINECLK -source [get_ports PLLOUT] -divide_by 18 [get_pins {@CLOCK_PIN@}]
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
# Diagnostic domain-capacity screen only. CDC/bundle skew is not qualified.
set_false_path -from [get_ports RESET_N]
set_input_delay 0.5 -clock REFCLK [get_ports {PLL_ENABLE FEEDBACK_DIVIDER* KI* KP*}]
set bbpd_ports {}
foreach port [get_ports *] {
    if {[string range [get_full_name $port] 0 4] eq {BBPD[}} {lappend bbpd_ports $port}
}
# BBPD events are asynchronous pulse clocks. This 25 MHz cadence is a
# diagnostic timing assumption, not a measured pulse-width/CDC signoff.
foreach port $bbpd_ports {
    set name [get_full_name $port]
    create_clock -name EVENT_$name -period 40 -waveform {0 1.111} $port
    set_clock_transition 0.1 [get_clocks EVENT_$name]
    set_clock_uncertainty 0.15 [get_clocks EVENT_$name]
}
set_output_delay 0.5 -clock PLLOUT [get_ports CLKDIV_RETIMED]
set_output_delay 0.5 -clock FINECLK [get_ports {DCO_CODE* DLF_CODE* DCO_THERM*}]
set_output_delay 0.5 -clock REFCLK [get_ports {COARSE_CODE* COARSETHERMAL_CODE* TRACKING CONFIG_BUSY FAILED BBPD_RESET_N}]

source [file join [file dirname [info script]] cdc.tcl]
source [file join [file dirname [info script]] receiver_resets.tcl]
