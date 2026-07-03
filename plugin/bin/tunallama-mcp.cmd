@echo off
rem tunaLlama MCP server launcher (Windows).
rem Mirrors bin/tunallama-mcp (bash) but uses the Windows venv layout
rem (.venv\Scripts\python.exe) and cd's to the repo root so that
rem `python -m plugin.mcp_server` can resolve both `plugin` and `tunallama_core`.

setlocal
set "SCRIPT_DIR=%~dp0"
rem repo root = <script_dir>\..\..  (plugin\bin\ -> repo root)
pushd "%SCRIPT_DIR%..\.."
set "REPO_DIR=%CD%"

if exist "%REPO_DIR%\.venv\Scripts\python.exe" (
  "%REPO_DIR%\.venv\Scripts\python.exe" -m plugin.mcp_server %*
) else (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 (
    python -m plugin.mcp_server %*
  ) else (
    echo tunallama-mcp: no python found ^(.venv\Scripts\python.exe or python on PATH^) 1>&2
    popd
    exit /b 1
  )
)
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
