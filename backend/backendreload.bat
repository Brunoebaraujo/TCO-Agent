@echo off
REM backendreload.bat — atualiza e reinicia o backend numa tacada só.
REM Roda de QUALQUER janela de terminal — nao precisa estar na janela
REM onde o uvicorn antigo esta rodando. Equivalente a: Ctrl+C na janela
REM antiga + git pull + uvicorn --reload, mas sem precisar trocar de janela.

setlocal

set PATH=C:\Users\Bruno.Araujo\AppData\Local\Programs\Git\cmd;%PATH%

echo.
echo [1/3] Parando o servidor antigo (porta 8000), se houver...
set KILLED=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    set KILLED=1
)
if %KILLED%==1 (
    echo       Processo antigo encerrado.
) else (
    echo       Nenhum processo rodando na porta 8000.
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
echo [3/3] Ativando ambiente virtual e subindo o servidor...
call venv\Scripts\activate
uvicorn app.main:app --reload
