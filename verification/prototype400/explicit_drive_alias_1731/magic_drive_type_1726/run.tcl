cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_drive_alias_type_1731/magic_drive_type_1726}
gds read {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_drive_type_RC_controls_1729/rotation0.gds}
load RotatedCrop
select top cell
extract style ngspice()
extresist simplify off
extresist threshold 0
extresist include ALIAS_DRIVE
extresist all
quit -noprompt
