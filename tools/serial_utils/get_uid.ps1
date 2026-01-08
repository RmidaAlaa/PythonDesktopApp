param (
    [string]$PortName = "COM3"
)
try {
    Write-Host "Connecting to $PortName at 115200 baud..."
    $port = New-Object System.IO.Ports.SerialPort $PortName, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One
    $port.ReadTimeout = 1000
    $port.Open()
    if ($port.BytesToRead -gt 0) { $port.ReadExisting() | Out-Null }
    Write-Host "Sending command..."
    $port.Write("i")
    Start-Sleep -Milliseconds 500
    $response = $port.ReadExisting()
    $port.Close()
    Write-Host "`n--- Device Response ---"
    Write-Host $response
    Write-Host "-----------------------"
    if ($response -match "Serial \(UID hex\): ([0-9A-F]+)") {
        Write-Host "`nFOUND UID: $($matches[1])" -ForegroundColor Green
    }
}
catch {
    Write-Error "Failed to communicate: $_"
    if ($port -and $port.IsOpen) { $port.Close() }
}
