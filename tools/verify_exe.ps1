param(
    [Parameter(Mandatory = $true)]
    [string] $ExePath
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Error "Missing: $ExePath"
    exit 1
}
$p = Start-Process -FilePath $ExePath -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited -and $p.ExitCode -ne 0) {
    exit $p.ExitCode
}
if (-not $p.HasExited) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}
exit 0
