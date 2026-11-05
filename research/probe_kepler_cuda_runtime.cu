#include <cstdio>
#include <cuda_runtime.h>

__global__ void write_answer(int *output) { *output = 42; }

int main() {
    int *device_value = nullptr;
    int host_value = 0;
    cudaError_t status = cudaMalloc(&device_value, sizeof(int));
    if (status != cudaSuccess) {
        std::fprintf(stderr, "cudaMalloc: %s\n", cudaGetErrorString(status));
        return 1;
    }
    write_answer<<<1, 1>>>(device_value);
    status = cudaDeviceSynchronize();
    if (status != cudaSuccess) {
        std::fprintf(stderr, "kernel: %s\n", cudaGetErrorString(status));
        return 1;
    }
    status = cudaMemcpy(&host_value, device_value, sizeof(int), cudaMemcpyDeviceToHost);
    if (status != cudaSuccess) {
        std::fprintf(stderr, "cudaMemcpy: %s\n", cudaGetErrorString(status));
        return 1;
    }
    cudaFree(device_value);
    std::printf("cuda_10_2_kernel_result=%d\n", host_value);
    return host_value == 42 ? 0 : 1;
}
