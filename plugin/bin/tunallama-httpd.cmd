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

rem 창은 tunallama-httpd.vbs 가 이 cmd 를 hidden(SW_HIDE)으로 띄워 숨긴다. 그래서
rem 일반 python.exe(단일 프로세스)를 써도 콘솔이 숨겨져 화면에 창이 안 뜬다.
rem (pythonw 는 자식 python.exe 를 스폰해 오히려 창이 뜰 수 있어 쓰지 않는다.)
rem 출력은 로그 파일로.  디버그: 이 cmd 를 직접 실행하면 콘솔에 출력이 보인다.
if not exist "%USERPROFILE%\.tunallama" mkdir "%USERPROFILE%\.tunallama"
set "LOG=%USERPROFILE%\.tunallama\httpd.log"
if exist "%REPO_DIR%\.venv\Scripts\python.exe" (
  "%REPO_DIR%\.venv\Scripts\python.exe" -m plugin.mcp_server > "%LOG%" 2>&1
) else (
  python -m plugin.mcp_server > "%LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
