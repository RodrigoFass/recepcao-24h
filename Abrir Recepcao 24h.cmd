@echo off
rem Duplo clique: atualiza os dados com a data de hoje, liga o site e abre o navegador.
rem Para desligar, feche esta janela.
chcp 65001 >nul
cd /d "%~dp0"
title Recepção 24h

if not exist ".venv\Scripts\python.exe" (
  echo Preparando o ambiente pela primeira vez, aguarde...
  python -m venv .venv || goto erro
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto erro
)

echo Atualizando os dados com a data de hoje...
".venv\Scripts\python.exe" seed.py || goto erro

echo.
echo Recepção 24h no ar: http://127.0.0.1:8000
echo Para desligar, feche esta janela.
echo.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning
goto fim

:erro
echo.
echo Algo deu errado. Veja a mensagem acima.
pause
:fim
