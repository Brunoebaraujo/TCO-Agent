@echo off
REM frontendreload.bat — atualiza e reinicia o frontend numa tacada só.
REM Roda de QUALQUER janela de terminal — nao precisa estar na janela
REM onde o npm run dev antigo esta rodando.

setlocal

set PATH=C:\Users\Bruno.Araujo\AppData\Local\Programs\Git\cmd;%PATH%
set PATH=C:\Users\Bruno.Araujo\OneDrive - Goodpack Limited\Documentos\Pessoal\Node;%PATH%

echo.
echo [1/3] Parando o servidor antigo (porta 5173), se houver...
set KILLED=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    set KILLED=1
)
if %KILLED%==1 (
    echo       Processo antigo encerrado.
) else (
    echo       Nenhum processo rodando na porta 5173.
)

echo.
echo [2/3] Atualizando do GitHub...
git pull
if errorlevel 1 (
    echo       ERRO no git pull - verifique mensagens acima antes de continuar.
    pause
    exit /b 1
)

echo.
echo [3/3] Subindo o servidor...
npm run dev
