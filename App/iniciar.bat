@echo off
title Treino de Letras
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/ ^(marque "Add to PATH"^).
  pause
  exit /b
)
%PY% -c "import yt_dlp" >nul 2>nul || (
  echo Instalando o yt-dlp, usado para ler as legendas do YouTube ^(so na primeira vez^)...
  %PY% -m pip install --user --quiet --disable-pip-version-check yt-dlp
)
%PY% server.py
