# Yosys Capabilities & Command Reference Manual

- **Binary Version:** `Yosys 0.70+186 (git sha1 3718f7f13, Release, GNU /usr/bin/x86_64-w64-mingw32-g++ 15.2.1)`
- **Total Extracted Commands:** `304`
- **Total Internal Cell Models:** `254`

| Category | Command | Summary | Flags | Required State |
| :--- | :--- | :--- | ---: | :--- |
| `01_frontend_input` | **`read_aiger`** | read AIGER file | 4 | `ELABORATED` |
| `01_frontend_input` | **`read_blif`** | read BLIF file | 2 | `ELABORATED` |
| `01_frontend_input` | **`read_json`** | read JSON file | 0 | `ELABORATED` |
| `01_frontend_input` | **`read_liberty`** | read cells from liberty file | 10 | `ELABORATED` |
| `01_frontend_input` | **`read_rtlil`** | read modules from RTLIL file | 4 | `ELABORATED` |
| `01_frontend_input` | **`read_slang`** | read SystemVerilog (slang) | 94 | `ELABORATED` |
| `01_frontend_input` | **`read_verilog`** | read modules from Verilog file | 39 | `EMPTY` |
| `02_backend_export` | **`show`** | generate schematics using graphviz | 18 | `ELABORATED` |
| `02_backend_export` | **`write_aiger`** | write design to AIGER file | 9 | `ELABORATED` |
| `02_backend_export` | **`write_aiger2`** | (experimental) write design to AIGER file | 2 | `ELABORATED` |
| `02_backend_export` | **`write_blif`** | write design to BLIF file | 15 | `ELABORATED` |
| `02_backend_export` | **`write_btor`** | write design to BTOR file | 0 | `ELABORATED` |
| `02_backend_export` | **`write_cxxrtl`** | convert design to C++ RTL simulation | 20 | `ELABORATED` |
| `02_backend_export` | **`write_edif`** | write design to EDIF netlist file | 5 | `ELABORATED` |
| `02_backend_export` | **`write_file`** | write a text to a file | 1 | `ELABORATED` |
| `02_backend_export` | **`write_firrtl`** | write design to a FIRRTL file | 0 | `ELABORATED` |
| `02_backend_export` | **`write_intersynth`** | write design to InterSynth netlist file | 3 | `ELABORATED` |
| `02_backend_export` | **`write_jny`** | generate design metadata | 3 | `ELABORATED` |
| `02_backend_export` | **`write_json`** | write design to a JSON file | 4 | `ELABORATED` |
| `02_backend_export` | **`write_rtlil`** | write design to RTLIL file | 4 | `ELABORATED` |
| `02_backend_export` | **`write_simplec`** | convert design to simple C code | 1 | `ELABORATED` |
| `02_backend_export` | **`write_smt2`** | write design to SMT-LIBv2 file | 8 | `ELABORATED` |
| `02_backend_export` | **`write_smv`** | write design to SMV file | 2 | `ELABORATED` |
| `02_backend_export` | **`write_spice`** | write design to SPICE netlist file | 3 | `ELABORATED` |
| `02_backend_export` | **`write_table`** | write design as connectivity table | 0 | `ELABORATED` |
| `02_backend_export` | **`write_verilog`** | write design to Verilog file | 19 | `ELABORATED` |
| `02_backend_export` | **`write_xaiger`** | write design to XAIGER file | 4 | `ELABORATED` |
| `02_backend_export` | **`write_xaiger2`** | write module to XAIGER file | 4 | `ELABORATED` |
| `03_rtl_optimization` | **`alumacc`** | extract ALU and MACC cells | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`opt`** | perform simple optimizations | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_balance_tree`** | $and/$or/$xor/$add/$mul cascades to trees | 2 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_clean`** | remove unused cells and wires | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_demorgan`** | Optimize reductions with DeMorgan equivalents | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_dff`** | perform DFF optimizations | 5 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_expr`** | perform const folding and simple expression rewriting | 7 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_ffinv`** | push inverters through FFs | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_hier`** | perform cross-boundary optimization | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_lut`** | optimize LUT cells | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_lut_ins`** | discard unused LUT inputs | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_mem`** | optimize memories | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_mem_feedback`** | convert memory read-to-write port feedback paths to write enables | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_mem_priority`** | remove priority relations between write ports that can never collide | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_mem_widen`** | optimize memories where all ports are wide | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_merge`** | consolidate identical cells | 3 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_muxtree`** | eliminate dead trees in multiplexer trees | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_reduce`** | simplify large MUXes and AND/OR gates | 2 | `ELABORATED` |
| `03_rtl_optimization` | **`opt_share`** | merge mutually exclusive cells of the same type that share an input signal | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`optbarriers`** | (experimental) insert optimization barriers | 5 | `ELABORATED` |
| `03_rtl_optimization` | **`peepopt`** | collection of peephole optimizers | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc`** | translate processes to netlists | 5 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_arst`** | detect asynchronous resets | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_clean`** | remove empty parts of processes | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_dff`** | extract flip-flops from processes | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_dlatch`** | extract latches from processes | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_init`** | convert initial block to init attributes | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_memwr`** | extract memory writes from processes | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_mux`** | convert decision trees to multiplexers | 1 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_prune`** | remove redundant assignments | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_rmdead`** | eliminate dead trees in decision trees | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`proc_rom`** | convert switches to ROMs | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`share`** | perform sat-based resource sharing | 0 | `ELABORATED` |
| `03_rtl_optimization` | **`wreduce`** | reduce the word size of operations if possible | 3 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm`** | extract and optimize finite state machines | 1 | `RTL_NETLIST` |
| `04_fsm_and_memory` | **`fsm_detect`** | finding FSMs in design | 1 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_expand`** | expand FSM cells by merging logic into it | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_export`** | exporting FSMs to KISS2 files | 2 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_extract`** | extracting FSMs in design | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_info`** | print information on finite state machines | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_map`** | mapping FSMs to basic logic | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_opt`** | optimize finite state machines | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`fsm_recode`** | recoding finite state machines | 3 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory`** | translate memories to basic cells | 0 | `RTL_NETLIST` |
| `04_fsm_and_memory` | **`memory_bmux2rom`** | convert muxes to ROMs | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_bram`** | map memories to block rams | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_collect`** | creating multi-port memory cells | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_dff`** | merge input/output DFFs into memory read ports | 1 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_libmap`** | map memories to cells | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_map`** | translate multiport memories to basic cells | 4 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_memx`** | emulate vlog sim behavior for mem ports | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_narrow`** | split up wide memory ports | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_nordff`** | extract read port FFs from memories | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_share`** | consolidate memory ports | 0 | `ELABORATED` |
| `04_fsm_and_memory` | **`memory_unpack`** | unpack multi-port memory cells | 0 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`abc`** | use ABC for technology mapping | 16 | `GENERIC_GATES` |
| `05_gate_and_tech_mapping` | **`abc9`** | use ABC9 for technology mapping | 10 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`abc9_exe`** | use ABC9 for technology mapping | 12 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`abc9_ops`** | helper functions for ABC9 | 14 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`abc_new`** | (experimental) use ABC for SC technology mapping (new) | 7 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`abc_ops_reintegrate`** | reintegrate ABC mapped design into module | 3 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`dffinit`** | set INIT param on FF cells | 4 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`dfflegalize`** | convert FFs and LATCHes to types supported by the target | 3 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`dfflibmap`** | technology mapping of flip-flops and latches | 0 | `GENERIC_GATES` |
| `05_gate_and_tech_mapping` | **`dffunmap`** | unmap clock enable and synchronous reset from FFs | 2 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`hilomap`** | technology mapping of constant hi- and/or lo-drivers | 3 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`iopadmap`** | technology mapping of i/o pads (or buffers) | 3 | `ELABORATED` |
| `05_gate_and_tech_mapping` | **`simplemap`** | mapping simple coarse-grain cells | 0 | `RTL_NETLIST` |
| `05_gate_and_tech_mapping` | **`techmap`** | generic technology mapper | 8 | `RTL_NETLIST` |
| `06_fpga_asic_meta_flows` | **`synth`** | generic synthesis script | 16 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_achronix`** | synthesis for Achronix Speedster22i FPGAs. | 3 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_analogdevices`** | synthesis for Analog Devices FPGAs | 14 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_anlogic`** | synthesis for Anlogic FPGAs | 6 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_easic`** | synthesis for eASIC platform | 5 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_ecp5`** | synthesis for ECP5 FPGAs | 0 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_efinix`** | synthesis for Efinix FPGAs | 6 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_fabulous`** | FABulous synthesis script | 21 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_gatemate`** | synthesis for Cologne Chip GateMate FPGAs | 13 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_gowin`** | synthesis for Gowin FPGAs | 15 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_ice40`** | synthesis for iCE40 FPGAs | 17 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_intel`** | synthesis for Intel (Altera) FPGAs. | 9 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_intel_alm`** | synthesis for ALM-based Intel (Altera) FPGAs. | 9 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_lattice`** | synthesis for Lattice FPGAs | 19 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_microchip`** | synthesis for Microchip FPGAs | 13 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_nanoxplore`** | synthesis for NanoXplore FPGAs | 13 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_nexus`** | synthesis for Nexus FPGAs | 0 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_quicklogic`** | Synthesis for QuickLogic FPGAs | 9 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_sf2`** | synthesis for SmartFusion2 and IGLOO2 FPGAs | 8 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synth_xilinx`** | synthesis for Xilinx FPGAs | 18 | `ELABORATED` |
| `06_fpga_asic_meta_flows` | **`synthprop`** | synthesize SVA properties | 5 | `ELABORATED` |
| `07_formal_and_equivalence` | **`chformal`** | change formal constraints of the design | 16 | `ELABORATED` |
| `07_formal_and_equivalence` | **`equiv_make`** | prepare a circuit for equivalence checking | 4 | `ELABORATED` |
| `07_formal_and_equivalence` | **`equiv_simple`** | try proving simple $equiv instances | 7 | `ELABORATED` |
| `07_formal_and_equivalence` | **`equiv_status`** | print status of equivalent checking module | 1 | `ELABORATED` |
| `07_formal_and_equivalence` | **`freduce`** | perform functional reduction | 3 | `ELABORATED` |
| `07_formal_and_equivalence` | **`miter`** | automatically create a miter circuit | 9 | `ELABORATED` |
| `07_formal_and_equivalence` | **`sat`** | solve a SAT problem in the circuit | 45 | `ELABORATED` |
| `08_analysis_and_reports` | **`check`** | check for obvious problems in the design | 8 | `ELABORATED` |
| `08_analysis_and_reports` | **`dump`** | print parts of the design in RTLIL format | 6 | `ELABORATED` |
| `08_analysis_and_reports` | **`ltp`** | print longest topological path | 2 | `RTL_NETLIST` |
| `08_analysis_and_reports` | **`scc`** | detect strongly connected components (logic loops) | 7 | `ELABORATED` |
| `08_analysis_and_reports` | **`select`** | modify and view the list of selected objects | 11 | `ELABORATED` |
| `08_analysis_and_reports` | **`stat`** | print some statistics | 6 | `ELABORATED` |
| `08_analysis_and_reports` | **`tee`** | redirect command output to file | 1 | `ELABORATED` |
| `09_hierarchy_and_netlist_ops` | **`connect`** | create or remove connections | 0 | `ELABORATED` |
| `09_hierarchy_and_netlist_ops` | **`flatten`** | flatten design | 6 | `RTL_NETLIST` |
| `09_hierarchy_and_netlist_ops` | **`hierarchy`** | check, expand and clean up design hierarchy | 12 | `LOADED_AST` |
| `09_hierarchy_and_netlist_ops` | **`rename`** | rename object in the design | 0 | `ELABORATED` |
| `09_hierarchy_and_netlist_ops` | **`splitnets`** | split up multi-bit nets | 2 | `ELABORATED` |
| `09_hierarchy_and_netlist_ops` | **`submod`** | moving part of a module to a new submodule | 3 | `ELABORATED` |
| `09_hierarchy_and_netlist_ops` | **`uniquify`** | create unique copies of modules | 0 | `ELABORATED` |
| `10_specialized_passes` | **`abstract`** | replace signals with abstract values during formal verification | 8 | `ELABORATED` |
| `10_specialized_passes` | **`add`** | add objects to the design | 0 | `ELABORATED` |
| `10_specialized_passes` | **`aigmap`** | map logic to and-inverter-graph circuit | 2 | `ELABORATED` |
| `10_specialized_passes` | **`anlogic_eqn`** | Anlogic: Calculate equations for luts | 0 | `ELABORATED` |
| `10_specialized_passes` | **`anlogic_fixcarry`** | Anlogic: fix carry chain | 0 | `ELABORATED` |
| `10_specialized_passes` | **`arith_tree`** | convert add/sub/macc/alu chains to carry-save adder trees | 3 | `ELABORATED` |
| `10_specialized_passes` | **`assertpmux`** | adds asserts for parallel muxes | 2 | `ELABORATED` |
| `10_specialized_passes` | **`async2sync`** | convert async FF inputs to sync circuits | 1 | `ELABORATED` |
| `10_specialized_passes` | **`attrmap`** | renaming attributes | 3 | `ELABORATED` |
| `10_specialized_passes` | **`attrmvcp`** | move or copy attributes from wires to driving cells | 4 | `ELABORATED` |
| `10_specialized_passes` | **`autoname`** | automatically assign names to objects | 0 | `ELABORATED` |
| `10_specialized_passes` | **`blackbox`** | convert modules into blackbox modules | 0 | `ELABORATED` |
| `10_specialized_passes` | **`bmuxmap`** | transform $bmux cells to trees of $mux cells | 1 | `ELABORATED` |
| `10_specialized_passes` | **`booth`** | map $mul cells to Booth multipliers | 1 | `ELABORATED` |
| `10_specialized_passes` | **`box_derive`** | derive box modules | 3 | `ELABORATED` |
| `10_specialized_passes` | **`bufnorm`** | (experimental) convert design into buffered-normalized form | 15 | `ELABORATED` |
| `10_specialized_passes` | **`bugpoint`** | minimize testcases | 12 | `ELABORATED` |
| `10_specialized_passes` | **`bwmuxmap`** | replace $bwmux cells with equivalent logic | 0 | `ELABORATED` |
| `10_specialized_passes` | **`cd`** | a shortcut for 'select -module <name>' | 0 | `ELABORATED` |
| `10_specialized_passes` | **`cellmatch`** | match cells to their targets in cell library | 0 | `ELABORATED` |
| `10_specialized_passes` | **`check_mem`** | check for obvious memory problems in the design | 2 | `ELABORATED` |
| `10_specialized_passes` | **`chparam`** | re-evaluate modules with new parameters | 0 | `ELABORATED` |
| `10_specialized_passes` | **`chtype`** | change type of cells in the design | 3 | `ELABORATED` |
| `10_specialized_passes` | **`clean`** | remove unused cells and wires | 0 | `ELABORATED` |
| `10_specialized_passes` | **`clean_zerowidth`** | clean zero-width connections from the design | 0 | `ELABORATED` |
| `10_specialized_passes` | **`clk2fflogic`** | convert clocked FFs to generic $ff cells | 2 | `ELABORATED` |
| `10_specialized_passes` | **`clkbufmap`** | insert clock buffers on clock networks | 0 | `ELABORATED` |
| `10_specialized_passes` | **`clockgate`** | extract clock gating out of flip flops | 4 | `ELABORATED` |
| `10_specialized_passes` | **`connect_rpc`** | connect to RPC frontend | 2 | `ELABORATED` |
| `10_specialized_passes` | **`connwrappers`** | match width of input-output port pairs | 3 | `ELABORATED` |
| `10_specialized_passes` | **`constmap`** | technology mapping of coarse constant value | 1 | `ELABORATED` |
| `10_specialized_passes` | **`copy`** | copy modules in the design | 0 | `ELABORATED` |
| `10_specialized_passes` | **`cutpoint`** | adds formal cut points to the design | 2 | `ELABORATED` |
| `10_specialized_passes` | **`debug`** | run command with debug log messages enabled | 0 | `ELABORATED` |
| `10_specialized_passes` | **`delete`** | delete objects in the design | 0 | `ELABORATED` |
| `10_specialized_passes` | **`deminout`** | demote inout ports to input or output | 0 | `ELABORATED` |
| `10_specialized_passes` | **`demuxmap`** | transform $demux cells to $eq + $mux cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`design`** | save, restore and reset current design | 0 | `ELABORATED` |
| `10_specialized_passes` | **`design_equal`** | check if two designs are the same | 0 | `ELABORATED` |
| `10_specialized_passes` | **`dft_tag`** | create tagging logic for data flow tracking | 2 | `ELABORATED` |
| `10_specialized_passes` | **`echo`** | turning echoing back of commands on and off | 0 | `ELABORATED` |
| `10_specialized_passes` | **`edgetypes`** | list all types of edges in selection | 0 | `ELABORATED` |
| `10_specialized_passes` | **`efinix_fixcarry`** | Efinix: fix carry chain | 0 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_add`** | add a $equiv cell | 0 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_induct`** | proving $equiv cells using temporal induction | 4 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_mark`** | mark equivalence checking regions | 0 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_miter`** | extract miter from equiv circuit | 4 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_opt`** | prove equivalence for optimized circuit | 8 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_purge`** | purge equivalence checking module | 0 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_remove`** | remove $equiv cells | 2 | `ELABORATED` |
| `10_specialized_passes` | **`equiv_struct`** | structural equivalence checking | 4 | `ELABORATED` |
| `10_specialized_passes` | **`eval`** | evaluate the circuit given an input | 4 | `ELABORATED` |
| `10_specialized_passes` | **`example_dt`** | drivertools example | 0 | `ELABORATED` |
| `10_specialized_passes` | **`exec`** | execute commands in the operating system shell | 4 | `ELABORATED` |
| `10_specialized_passes` | **`expose`** | convert internal signals to module ports | 7 | `ELABORATED` |
| `10_specialized_passes` | **`extract`** | find subcircuits and replace them with cells | 14 | `ELABORATED` |
| `10_specialized_passes` | **`extract_counter`** | Extract GreenPak4 counter cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`extract_fa`** | find and extract full/half adders | 3 | `ELABORATED` |
| `10_specialized_passes` | **`extract_reduce`** | converts gate chains into $reduce_* cells | 1 | `ELABORATED` |
| `10_specialized_passes` | **`extractinv`** | extract explicit inverter cells for invertible cell pins | 0 | `ELABORATED` |
| `10_specialized_passes` | **`fmcombine`** | combine two instances of a cell into one | 5 | `ELABORATED` |
| `10_specialized_passes` | **`fminit`** | set init values/sequences for formal | 4 | `ELABORATED` |
| `10_specialized_passes` | **`formalff`** | prepare FFs for formal | 8 | `ELABORATED` |
| `10_specialized_passes` | **`fst2tb`** | generate testbench out of fst file | 8 | `ELABORATED` |
| `10_specialized_passes` | **`future`** | resolve future sampled value functions | 0 | `ELABORATED` |
| `10_specialized_passes` | **`gatemate_foldinv`** | fold inverters into Gatemate LUT trees | 0 | `ELABORATED` |
| `10_specialized_passes` | **`glift`** | create GLIFT models and optimization problems | 0 | `ELABORATED` |
| `10_specialized_passes` | **`help`** | display help messages | 0 | `ELABORATED` |
| `10_specialized_passes` | **`history`** | show last interactive commands | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ice40_braminit`** | iCE40: perform SB_RAM40_4K initialization from file | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ice40_dsp`** | iCE40: map multipliers | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ice40_opt`** | iCE40: perform simple optimizations | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ice40_wrapcarry`** | iCE40: wrap carries | 1 | `ELABORATED` |
| `10_specialized_passes` | **`icell_liberty`** | write Liberty interfaces for used internal cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`insbuf`** | insert buffer cells for connected wires | 2 | `ELABORATED` |
| `10_specialized_passes` | **`internal_stats`** | print internal statistics | 0 | `ELABORATED` |
| `10_specialized_passes` | **`jny`** | write design and metadata | 4 | `ELABORATED` |
| `10_specialized_passes` | **`json`** | write design in JSON format | 4 | `ELABORATED` |
| `10_specialized_passes` | **`keep_hierarchy`** | selectively add the keep_hierarchy attribute | 1 | `ELABORATED` |
| `10_specialized_passes` | **`lattice_dsp_nexus`** | Lattice Nexus DSP inference | 0 | `ELABORATED` |
| `10_specialized_passes` | **`lattice_gsr`** | Lattice: handle GSR | 0 | `ELABORATED` |
| `10_specialized_passes` | **`libcache`** | control caching of technology library data parsed from liberty files | 5 | `ELABORATED` |
| `10_specialized_passes` | **`license`** | print license terms | 0 | `ELABORATED` |
| `10_specialized_passes` | **`linecoverage`** | report coverage information | 1 | `ELABORATED` |
| `10_specialized_passes` | **`log`** | print text and log files | 7 | `ELABORATED` |
| `10_specialized_passes` | **`logger`** | set logger properties | 6 | `ELABORATED` |
| `10_specialized_passes` | **`ls`** | list modules or objects in modules | 0 | `ELABORATED` |
| `10_specialized_passes` | **`lut2bmux`** | convert $lut to $bmux | 0 | `ELABORATED` |
| `10_specialized_passes` | **`lut2mux`** | convert $lut to $mux/$_MUX_ | 1 | `ELABORATED` |
| `10_specialized_passes` | **`maccmap`** | mapping macc cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`mcm`** | replace constant multipliers with shared adder graphs | 6 | `ELABORATED` |
| `10_specialized_passes` | **`microchip_dffopt`** | MICROCHIP: optimize FF control signal usage | 0 | `ELABORATED` |
| `10_specialized_passes` | **`microchip_dsp`** | MICROCHIP: pack resources into DSPs | 0 | `ELABORATED` |
| `10_specialized_passes` | **`mutate`** | generate or apply design mutations | 1 | `ELABORATED` |
| `10_specialized_passes` | **`muxcover`** | cover trees of MUX cells with wider MUXes | 4 | `ELABORATED` |
| `10_specialized_passes` | **`muxpack`** | $mux/$pmux cascades to $pmux | 0 | `ELABORATED` |
| `10_specialized_passes` | **`nx_carry`** | NanoXplore: create carry cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`onehot`** | optimize $eq cells for onehot signals | 0 | `ELABORATED` |
| `10_specialized_passes` | **`opensta`** | run OpenSTA | 4 | `ELABORATED` |
| `10_specialized_passes` | **`paramap`** | renaming cell parameters | 2 | `ELABORATED` |
| `10_specialized_passes` | **`plugin`** | load and list loaded plugins | 3 | `ELABORATED` |
| `10_specialized_passes` | **`pmux2shiftx`** | transform $pmux cells to $shiftx cells | 3 | `ELABORATED` |
| `10_specialized_passes` | **`pmuxtree`** | transform $pmux cells to trees of $mux cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`portarcs`** | derive port arcs for propagation delay | 3 | `ELABORATED` |
| `10_specialized_passes` | **`portlist`** | list (top-level) ports | 0 | `ELABORATED` |
| `10_specialized_passes` | **`prep`** | generic synthesis script | 9 | `ELABORATED` |
| `10_specialized_passes` | **`printattrs`** | print attributes of selected objects | 0 | `ELABORATED` |
| `10_specialized_passes` | **`qbfsat`** | solve a 2QBF-SAT problem in the circuit | 15 | `ELABORATED` |
| `10_specialized_passes` | **`ql_bram_merge`** | Infers QuickLogic k6n10f BRAM pairs that can operate independently | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ql_bram_types`** | Change TDP36K type to subtypes | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ql_dsp_io_regs`** | change types of QL_DSP2 depending on configuration | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ql_dsp_macc`** | infer QuickLogic multiplier-accumulator DSP cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ql_dsp_simd`** | merge QuickLogic K6N10f DSP pairs to operate in SIMD mode | 0 | `ELABORATED` |
| `10_specialized_passes` | **`ql_ioff`** | Infer I/O FFs for qlf_k6n10f architecture | 0 | `ELABORATED` |
| `10_specialized_passes` | **`raise_error`** | raise errors from attributes | 2 | `ELABORATED` |
| `10_specialized_passes` | **`read`** | load HDL designs | 1 | `ELABORATED` |
| `10_specialized_passes` | **`recover_names`** | Execute a lossy mapping command and recover original netnames | 0 | `ELABORATED` |
| `10_specialized_passes` | **`rmports`** | remove module ports with no connections | 1 | `ELABORATED` |
| `10_specialized_passes` | **`scatter`** | add additional intermediate nets | 0 | `ELABORATED` |
| `10_specialized_passes` | **`scratchpad`** | get/set values in the scratchpad | 7 | `ELABORATED` |
| `10_specialized_passes` | **`script`** | execute commands from file or wire | 0 | `ELABORATED` |
| `10_specialized_passes` | **`sdc`** | Read an SDC file | 3 | `ELABORATED` |
| `10_specialized_passes` | **`sdc_expand`** | expand SDC design with opensta | 3 | `ELABORATED` |
| `10_specialized_passes` | **`setattr`** | set/unset attributes on objects | 0 | `ELABORATED` |
| `10_specialized_passes` | **`setenv`** | set an environment variable | 0 | `ELABORATED` |
| `10_specialized_passes` | **`setparam`** | set/unset parameters on objects | 0 | `ELABORATED` |
| `10_specialized_passes` | **`setundef`** | replace undef values with defined constants | 10 | `ELABORATED` |
| `10_specialized_passes` | **`shell`** | enter interactive command mode | 0 | `ELABORATED` |
| `10_specialized_passes` | **`shregmap`** | map shift registers | 3 | `ELABORATED` |
| `10_specialized_passes` | **`shuffle`** | deterministically reorder design objects | 1 | `ELABORATED` |
| `10_specialized_passes` | **`sim`** | simulate the circuit | 37 | `ELABORATED` |
| `10_specialized_passes` | **`slang_defaults`** | set default options for read_slang | 0 | `ELABORATED` |
| `10_specialized_passes` | **`slang_version`** | display revision of slang frontend | 0 | `ELABORATED` |
| `10_specialized_passes` | **`sort`** | sort the design objects | 0 | `ELABORATED` |
| `10_specialized_passes` | **`splice`** | create explicit splicing cells | 7 | `ELABORATED` |
| `10_specialized_passes` | **`splitcells`** | split up multi-bit cells | 0 | `ELABORATED` |
| `10_specialized_passes` | **`sta`** | perform static timing analysis | 0 | `ELABORATED` |
| `10_specialized_passes` | **`supercover`** | add hi/lo cover cells for each wire bit | 0 | `ELABORATED` |
| `10_specialized_passes` | **`symfpu`** | SymFPU based floating point netlist generator | 4 | `ELABORATED` |
| `10_specialized_passes` | **`symfpu_convert`** | SymFPU based floating point conversion netlist generator | 5 | `ELABORATED` |
| `10_specialized_passes` | **`tcl`** | execute a TCL script file | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_abcloop`** | automatically test handling of loops in abc command | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_autotb`** | generate simple test benches | 2 | `ELABORATED` |
| `10_specialized_passes` | **`test_cell`** | automatically test the implementation of a cell type | 10 | `ELABORATED` |
| `10_specialized_passes` | **`test_generic`** | test the generic compute graph | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_kogge_stone`** | build adders for Kogge-Stone equivalence testing | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_pmgen`** | test pass for pmgen | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_select`** | call internal selection methods on design for testing purposes | 8 | `ELABORATED` |
| `10_specialized_passes` | **`test_slangdiag`** | test diagnostics emission by the slang frontend | 0 | `ELABORATED` |
| `10_specialized_passes` | **`test_slangexpr`** | test expression evaluation within slang frontend | 0 | `ELABORATED` |
| `10_specialized_passes` | **`timeest`** | estimate timing | 2 | `ELABORATED` |
| `10_specialized_passes` | **`torder`** | print cells in topological order | 2 | `ELABORATED` |
| `10_specialized_passes` | **`trace`** | redirect command output to file | 0 | `ELABORATED` |
| `10_specialized_passes` | **`tribuf`** | infer tri-state buffers | 3 | `ELABORATED` |
| `10_specialized_passes` | **`verific`** | load Verilog and VHDL designs using Verific | 0 | `ELABORATED` |
| `10_specialized_passes` | **`verilog_defaults`** | set default options for read_verilog | 0 | `ELABORATED` |
| `10_specialized_passes` | **`verilog_defines`** | define and undefine verilog defines | 4 | `ELABORATED` |
| `10_specialized_passes` | **`viz`** | visualize data flow graph | 10 | `ELABORATED` |
| `10_specialized_passes` | **`wbflip`** | flip the whitebox attribute | 0 | `ELABORATED` |
| `10_specialized_passes` | **`wrapcell`** | wrap individual cells into new modules | 2 | `ELABORATED` |
| `10_specialized_passes` | **`xilinx_dffopt`** | Xilinx: optimize FF control signal usage | 1 | `ELABORATED` |
| `10_specialized_passes` | **`xilinx_dsp`** | Xilinx: pack resources into DSPs | 0 | `ELABORATED` |
| `10_specialized_passes` | **`xilinx_srl`** | Xilinx shift register extraction | 2 | `ELABORATED` |
| `10_specialized_passes` | **`xprop`** | formal x propagation | 10 | `ELABORATED` |
| `10_specialized_passes` | **`zinit`** | add inverters so all FF are zero-initialized | 1 | `ELABORATED` |
