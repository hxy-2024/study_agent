param(
    [switch]$SkipInstall,
    [switch]$SkipInfra,
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [string]$HostName = "127.0.0.1",
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$argsList = @("dev", "--host", $HostName, "--api-port", "$ApiPort", "--web-port", "$WebPort")
if ($SkipInstall) { $argsList += "--skip-install" }
if ($SkipInfra) { $argsList += "--skip-infra" }
if ($ApiOnly) { $argsList += "--api-only" }
if ($WebOnly) { $argsList += "--web-only" }

python main.py @argsList
