SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = tt_um_protocolEmulator.v uartTx.v progMem.v sram_bb.v

SRAM_MODEL = $(PWD)/sram_model/RM_IHPSG13_1P_256x16_c2_bm_bist.v $(PWD)/sram_model/RM_IHPSG13_1P_core_behavioral_bm_bist.v
VERILOG_SOURCES += $(SRAM_MODEL)
COMPILE_ARGS += -DFUNCTIONAL -DSIM

ifneq ($(GATES),yes)

SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_io/verilog/sg13cmos5l_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_stdcell.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_udp.v
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

COMPILE_ARGS 		+= -I$(SRC_DIR)

VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

COCOTB_TEST_MODULES = testUartTx,testProgMem

include $(shell cocotb-config --makefiles)/Makefile.sim
