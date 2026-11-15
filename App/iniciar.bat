@echo off
title Musical Training
cd /d "%~dp0"

rem ---- acha o Python (py = lancador oficial; pyw/pythonw = versao sem janela) ----
set "PY="
set "PYW="
where py >nul 2>nul && set "PY=py"
where pyw >nul 2>nul && set "PYW=pyw"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PYW (where pythonw >nul 2>nul && set "PYW=pythonw")
if not defined PY (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/ ^(marque "Add to PATH"^).
  pause
  exit /b
)

rem ---- primeira vez: instala o yt-dlp (le as legendas do YouTube) ----
%PY% -c "import yt_dlp" >nul 2>nul || (
  echo Instalando o yt-dlp, usado para ler as legendas do YouTube ^(so na primeira vez^)...
  %PY% -m pip install --user --quiet --disable-pip-version-check yt-dlp
)

rem ---- "iniciar.bat --janela" mostra o servidor numa janela (para ver mensagens/erros) ----
if /i "%~1"=="--janela" goto janela
if not defined PYW goto janela

rem ---- normal: abre o servidor sem janela; ele fecha sozinho quando a aba do app e fechada ----
start "" %PYW% server.py
exit /b

:janela
%PY% server.py
