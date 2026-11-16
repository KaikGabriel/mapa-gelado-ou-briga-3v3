@echo off
rem Gera dist\MayhemBuild.exe (um arquivo so, sem janela de console, com icone).
cd /d "%~dp0"

py -m pip install --upgrade pyinstaller || goto erro

py -m PyInstaller --noconfirm --onefile --windowed --name MayhemBuild ^
  --icon mayhembuild.ico ^
  --add-data "metasrc_para_painel.user.js;." ^
  --add-data "mayhembuild.ico;." ^
  --add-data "combos_arena.json;." ^
  mayhem_build.pyw || goto erro

echo.
echo Pronto: dist\MayhemBuild.exe
pause
exit /b 0

:erro
echo.
echo Deu erro ao gerar o .exe. Veja as mensagens acima.
pause
exit /b 1
