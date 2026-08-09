@echo off
if not exist "C:\AlbatrosEdge" mkdir C:\AlbatrosEdge
cd C:\AlbatrosEdge

echo Extrayendo paquete...
tar -xzf C:\Users\jvalor\deploy.tar.gz

echo Configurando .env...
move /y C:\Users\jvalor\.env.deploy .\.env

echo Descargando WinSW...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe' -OutFile 'winsw.exe'"

echo Configurando Python venv e instalando dependencias...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt

echo Despliegue completado.
