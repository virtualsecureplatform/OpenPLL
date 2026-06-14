set_units -time ns

set_false_path -from [get_ports REF]
set_false_path -from [get_ports RESET_N]
set_false_path -from [get_ports PLL_ENABLE]
set_false_path -from [get_ports MODE_SELECT[*]]

set_false_path -to [get_ports PLLOUT]
set_false_path -to [get_ports PLLOUT_DIV]
set_false_path -to [get_ports CLKDIV_RETIMED]
set_false_path -to [get_ports BBPD_CODE[*]]
set_false_path -to [get_ports DCO_CODE[*]]
set_false_path -to [get_ports DLF_CODE[*]]
set_false_path -to [get_ports CONFIG_BUSY]
set_false_path -to [get_ports TRACKING]
set_false_path -to [get_ports TARGET_MHZ[*]]
set_false_path -to [get_ports TARGET_DCO_CODE[*]]
