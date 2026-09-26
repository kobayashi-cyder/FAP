$ErrorActionPreference = 'Stop'
$LatestVersion = '1.0.01-unified-chat'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Starting FAP $LatestVersion"
python (Join-Path $Root 'fap_v1_0_01_dynamic_sparse_routing_gateway.py')
