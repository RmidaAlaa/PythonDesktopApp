## How to Get UID via Serial (PowerShell)
### Manual Steps
1. Identify your COM port (e.g., COM3, COM4).
2. Open PowerShell.
3. Run the following commands (replace `COM3` with your actual port):
```powershell
$portName = "COM3"
$port = New-Object System.IO.Ports.SerialPort $portName, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One
$port.Open()
$port.Write("i")
Start-Sleep -Milliseconds 500
$response = $port.ReadExisting()
$port.Close()
Write-Host $response
```
### Protocol
- Baud Rate: 115200
- Command: Send character `i` (or `I`)
- Response: The board will print MCU info including the UID.
