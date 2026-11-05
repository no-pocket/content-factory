"""Run one PTX kernel through the CUDA driver API in an isolated GPU container."""

import ctypes


PTX = b""".version 3.2
.target sm_30
.address_size 64
.visible .entry write_answer(.param .u64 output) {
    .reg .b64 %ptr;
    .reg .b32 %value;
    ld.param.u64 %ptr, [output];
    mov.u32 %value, 42;
    st.global.u32 [%ptr], %value;
    ret;
}
"""


def check(name, result):
    if result != 0:
        raise RuntimeError(f"{name}: CUDA error {result}")


cuda = ctypes.CDLL("libcuda.so.1")
device = ctypes.c_int()
context = ctypes.c_void_p()
module = ctypes.c_void_p()
function = ctypes.c_void_p()
gpu_buffer = ctypes.c_void_p()
host_value = ctypes.c_uint32(0)

check("cuInit", cuda.cuInit(0))
check("cuDeviceGet", cuda.cuDeviceGet(ctypes.byref(device), 0))
check("cuCtxCreate", cuda.cuCtxCreate_v2(ctypes.byref(context), 0, device))
check("cuMemAlloc", cuda.cuMemAlloc_v2(ctypes.byref(gpu_buffer), 4))
check("cuModuleLoadData", cuda.cuModuleLoadData(ctypes.byref(module), PTX))
check("cuModuleGetFunction", cuda.cuModuleGetFunction(ctypes.byref(function), module, b"write_answer"))
parameters = (ctypes.c_void_p * 1)(ctypes.addressof(gpu_buffer))
check("cuLaunchKernel", cuda.cuLaunchKernel(function, 1, 1, 1, 1, 1, 1, 0, None, parameters, None))
check("cuCtxSynchronize", cuda.cuCtxSynchronize())
check("cuMemcpyDtoH", cuda.cuMemcpyDtoH_v2(ctypes.byref(host_value), gpu_buffer, 4))
print(f"kernel_result={host_value.value}")
assert host_value.value == 42
check("cuMemFree", cuda.cuMemFree_v2(gpu_buffer))
check("cuModuleUnload", cuda.cuModuleUnload(module))
check("cuCtxDestroy", cuda.cuCtxDestroy_v2(context))
