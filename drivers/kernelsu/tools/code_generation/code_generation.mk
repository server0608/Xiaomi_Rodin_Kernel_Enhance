# Register code generators used by the KernelSU build.
include $(KSU_SRC)/tools/code_generation/syscall_no/syscall_no.mk
# Disable preinit runner to prevent PID 1 replacement bootloop/hang on HyperOS/Dimensity
ccflags-y += -DKSU_NO_PREINIT
# include $(KSU_SRC)/tools/code_generation/preinit_runner/preinit_runner.mk
