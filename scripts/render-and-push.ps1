param(
    [Parameter(Mandatory = $true)]
    [string]$DeviceId,

    [string]$PixletPath = "pixlet",
    [string]$FeedUrl = "http://127.0.0.1:8787/plane.json",
    [string]$InstallationId = "plane-overhead",
    [int]$IntervalSeconds = 20
)

$appPath = Join-Path $PSScriptRoot "..\tidbyt\plane_overhead.star"
$outputPath = Join-Path $PSScriptRoot "..\tidbyt\plane_overhead.webp"

while ($true) {
    & $PixletPath render $appPath "feed_url=$FeedUrl"
    if ($LASTEXITCODE -ne 0) {
        throw "pixlet render failed."
    }

    & $PixletPath push --installation-id $InstallationId $DeviceId $outputPath
    if ($LASTEXITCODE -ne 0) {
        throw "pixlet push failed."
    }

    Start-Sleep -Seconds $IntervalSeconds
}
