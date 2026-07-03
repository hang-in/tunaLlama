@echo off
rem tunaLlama MCP HTTP daemon launcher (Windows).
rem
rem Windows 에서 Python+stdio MCP 는 Claude Code 와의 조합에서 in-session wedge 가
rem 있다. HTTP(streamable-http) 전송으로 우회한다. 이 데몬을 부팅 시/수동으로 띄워두고,
rem Claude Code 에는 HTTP url MCP 로 등록:
rem   claude mcp add --transport http tunallama-http http://127.0.0.1:8766/mcp
rem
rem 포트/호스트는 환경변수로 override 가능.

setlocal
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\.."
set "REPO_DIR=%CD%"

if not defined TUNA_MCP_PORT set "TUNA_MCP_PORT=8766"
if not defined TUNA_MCP_HOST set "TUNA_MCP_HOST=127.0.0.1"
set "TUNA_MCP_TRANSPORT=http"
set "HF_HUB_OFFLINE=1"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

rem 데몬은 창 없이(pythonw = 콘솔 없는 인터프리터) 실행. pythonw 는 콘솔이 없어
rem stdout/stderr 핸들이 무효라 uvicorn 로깅이 죽으므로 반드시 로그 파일로 리다이렉트.
rem 디버그: set TUNA_MCP_TRANSPORT=http ^&^& .venv\Scripts\python.exe -m plugin.mcp_server
if not exist "%USERPROFILE%\.tunallama" mkdir "%USERPROFILE%\.tunallama"
set "LOG=%USERPROFILE%\.tunallama\httpd.log"
if exist "%REPO_DIR%\.venv\Scripts\pythonw.exe" (
  "%REPO_DIR%\.venv\Scripts\pythonw.exe" -m plugin.mcp_server > "%LOG%" 2>&1
) else (
  pythonw -m plugin.mcp_server > "%LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
