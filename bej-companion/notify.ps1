param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadBase64
)
$ErrorActionPreference = 'Stop'
$icon = $null
try {
    $payload = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($PayloadBase64)) | ConvertFrom-Json
    if (-not ($payload.title -is [string]) -or -not ($payload.message -is [string]) -or
        [string]::IsNullOrWhiteSpace($payload.title) -or [string]::IsNullOrWhiteSpace($payload.message) -or
        $payload.title.Length -gt 63 -or $payload.message.Length -gt 1000) {
        throw 'Invalid notification payload.'
    }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $icon = New-Object System.Windows.Forms.NotifyIcon
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    $icon.Text = 'Bej Secretary'
    $icon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
    $icon.BalloonTipTitle = $payload.title
    $icon.BalloonTipText = $payload.message
    $icon.Visible = $true
    $icon.ShowBalloonTip(8000)
    $until = [DateTime]::UtcNow.AddSeconds(8)
    while ([DateTime]::UtcNow -lt $until) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 100
    }
} catch {
    exit 1
} finally {
    if ($null -ne $icon) {
        $icon.Visible = $false
        $icon.Dispose()
    }
}
exit 0
