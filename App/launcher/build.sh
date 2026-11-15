#!/usr/bin/env sh
# Gera ../../Musical Training.exe (precisa do mingw-w64 e do Python com Pillow).
# No Linux: sudo apt install gcc-mingw-w64-x86-64 && pip install pillow
set -e
cd "$(dirname "$0")"
python3 -c "
from PIL import Image
im=Image.open('../MSC.ico'); im.load(); im=im.convert('RGBA')
im.save('icon.ico', sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(96,96),(128,128),(256,256)])"
x86_64-w64-mingw32-windres launcher.rc -O coff -o launcher.res
x86_64-w64-mingw32-gcc -O2 -s -municode -mwindows launcher.c launcher.res -o "../../Musical Training.exe" -lshell32
rm -f launcher.res icon.ico
echo "ok: Musical Training.exe"
