# ==============================================================================
# FPGA Studio — Automated Xilinx Vivado Project & Bitstream Script
# Target FPGA: Digilent Nexys A7-100T (xc7a100tcsg324-1)
# Usage in Vivado Tcl Console:
#   cd {C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/build_soc_openmips}
#   source build_vivado_project.tcl
# ==============================================================================
set proj_name "fpga_studio_nexys_a7"
create_project -force $proj_name ./vivado_proj -part xc7a100tcsg324-1

add_files -norecurse [glob -nocomplain ./rtl_cpu/*.v]
add_files -norecurse ./uart_prog_loader.v
add_files -norecurse ./nexys_a7_soc_top.v
add_files -norecurse ./program.hex
add_files -norecurse ./dmem_init.hex
add_files -fileset constrs_1 -norecurse ./Nexys-A7-100T-Master.xdc

set_property include_dirs [list ./rtl_cpu] [current_fileset]
set_property verilog_define [list SYNTHESIS=1] [current_fileset]
set_property top nexys_a7_soc_top [current_fileset]
update_compile_order -fileset sources_1

puts "=================================================================="
puts "Vivado project '$proj_name' created! Run 'launch_runs impl_1 -to_step write_bitstream' to build bitstream."
puts "=================================================================="
