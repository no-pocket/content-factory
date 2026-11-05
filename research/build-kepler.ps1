$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$source = Join-Path $PSScriptRoot 'upstream\llama-b4300'
$image = 'content-factory-kepler-lab:cuda10.2'
$volume = 'cf_kepler_b4300'

if (-not (Test-Path (Join-Path $source 'CMakeLists.txt'))) {
    git clone --depth 1 --branch b4300 https://github.com/ggml-org/llama.cpp.git $source
    if ($LASTEXITCODE -ne 0) { throw 'Could not clone llama.cpp b4300' }
}
docker image inspect $image --format '{{.Id}}' *> $null
if ($LASTEXITCODE -ne 0) {
    docker build -f (Join-Path $PSScriptRoot 'Dockerfile.kepler-lab') -t $image $project
    if ($LASTEXITCODE -ne 0) { throw 'Could not build CUDA 10.2 lab image' }
}
docker volume create $volume | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not create build volume' }
$sourceMount = "type=bind,source=$source,target=/src"
$buildMount = "type=volume,source=$volume,target=/build"
docker run --rm --mount $sourceMount --mount $buildMount --entrypoint cmake $image `
    -S /src -B /build -G Ninja `
    -DCMAKE_C_COMPILER=clang-14 -DCMAKE_CXX_COMPILER=clang++-14 `
    -DCMAKE_CUDA_COMPILER=clang++-14 -DCMAKE_CUDA_ARCHITECTURES=30 `
    -DGGML_CUDA=ON -DGGML_CUDA_GRAPHS=OFF -DGGML_NATIVE=OFF `
    -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TESTS=OFF
if ($LASTEXITCODE -ne 0) { throw 'Could not configure llama.cpp for sm_30' }
docker run --rm --mount $sourceMount --mount $buildMount --entrypoint cmake $image `
    --build /build --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Could not compile llama.cpp for sm_30' }
Write-Output 'Built /build/bin/llama-server in cf_kepler_b4300'
