[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$Dest = "$env:TEMP\python-installer.exe"
Write-Host "Descargando Python..."
Invoke-WebRequest -Uri $Url -OutFile $Dest
Write-Host "Instalando Python..."
Start-Process -FilePath $Dest -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -NoNewWindow
Write-Host "Instalacion finalizada."
