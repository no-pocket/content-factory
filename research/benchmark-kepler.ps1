param(
    [string]$OutputDirectory = 'research/benchmarks',
    [int]$Repetitions = 3
)

$ErrorActionPreference = 'Stop'
$models = @{
    '1.5b' = 'sha256-183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4'
    '3b' = 'sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6'
}
$out = (New-Item -ItemType Directory -Force -Path $OutputDirectory).FullName
$queue = docker exec content-factory-redis-1 redis-cli LLEN clips:queue
if ($LASTEXITCODE -ne 0 -or [int]$queue -ne 0) { throw 'A fila deve estar vazia antes do benchmark.' }
$processing = docker exec content-factory-redis-1 redis-cli LLEN clips:processing
if ($LASTEXITCODE -ne 0 -or [int]$processing -ne 0) { throw 'Nenhum job pode estar em processamento durante o benchmark.' }

docker compose -f compose.yaml -f compose.kepler.yaml stop kepler-engine
if ($LASTEXITCODE -ne 0) { throw 'Falha ao pausar o servidor GPU.' }
try {
    foreach ($name in @('1.5b', '3b')) {
        foreach ($layers in @(0, 99)) {
            $device = if ($layers -eq 0) { 'cpu' } else { 'gpu' }
            $model = "/models/models/blobs/$($models[$name])"
            $common = @('--rm', '--gpus', 'all', '--volumes-from', 'content-factory-kepler-engine-1',
                        '-e', 'LD_LIBRARY_PATH=/build/bin:/usr/local/cuda-10.2/lib64',
                        '--entrypoint', '/build/bin/llama-bench', 'content-factory-kepler-lab:cuda10.2',
                        '-m', $model, '-t', '4', '-b', '512', '-ub', '256', '-ngl', "$layers")
            Write-Host "Aquecimento: $name $device"
            & docker run @common -p 64 -n 16 -r 1 -o csv 1> $null
            if ($LASTEXITCODE -ne 0) { throw "Falha no aquecimento: $name $device" }
            $csv = Join-Path $out "$name-$device.csv"
            Write-Host "Medição: $name $device ($Repetitions repetições por caso) -> $csv"
            & docker run @common -p 128,1024 -n 32,64 -r $Repetitions -o csv 1> $csv
            if ($LASTEXITCODE -ne 0) { throw "Falha na medição: $name $device" }
        }
    }
}
finally {
    docker compose -f compose.yaml -f compose.kepler.yaml start kepler-engine
    if ($LASTEXITCODE -ne 0) { Write-Error 'Falha ao reiniciar o servidor GPU.' }
}
