<#
  tunaLlama Windows 셋업 — MCP 를 HTTP(streamable-http) 데몬으로 전환.

  Windows 에서 Python+stdio MCP 는 Claude Code 와의 조합에서 in-session tool 호출이
  무한 hang 한다(서버 정상, Claude Code 의 Windows stdio MCP 클라이언트 이슈).
  이 스크립트가 다음을 자동 수행한다 (idempotent — 몇 번 돌려도 안전):
    1) HTTP 데몬을 로그온 자동시작 스케줄 작업으로 등록 + 즉시 실행
    2) Claude Code 에 'tunallama' HTTP MCP 등록 (툴 = mcp__tunallama__tuna_*)
    3) 설치된 플러그인의 stdio MCP 비활성화 (중복 tuna_* + wedge 제거)

  사용:  powershell -ExecutionPolicy Bypass -File plugin\bin\tunallama-win-setup.ps1
  제거:  ...-File plugin\bin\tunallama-win-setup.ps1 -Uninstall
#>
param(
  [int]$Port = $(if ($env:TUNA_MCP_PORT) { [int]$env:TUNA_MCP_PORT } else { 8766 }),
  [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)  # plugin\bin -> repo root
$Httpd    = Join-Path $RepoRoot 'plugin\bin\tunallama-httpd.cmd'
$Vbs      = Join-Path $RepoRoot 'plugin\bin\tunallama-httpd.vbs'
$TaskName = 'tunaLlama-httpd'
$Url      = "http://127.0.0.1:$Port/mcp"

function Restore-PluginStdio([bool]$disable) {
  # 설치된 플러그인의 plugin\.mcp.json 을 비운다(=disable stdio MCP).
  # marketplaces/cache 아래만 얕게 탐색 (node_modules 등 깊은 재귀 회피).
  $bases = @(
    (Join-Path $env:USERPROFILE '.claude\plugins\marketplaces'),
    (Join-Path $env:USERPROFILE '.claude\plugins\cache')
  ) | Where-Object { Test-Path $_ }
  foreach ($b in $bases) {
    Get-ChildItem $b -Recurse -Depth 5 -Filter '.mcp.json' -File -ErrorAction SilentlyContinue | ForEach-Object {
      $raw = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
      if ($raw -and $raw -match 'plugin\.mcp_server' -and $disable) {
        '{ "mcpServers": {} }' | Set-Content $_.FullName -Encoding utf8
        Write-Host "  disabled plugin stdio MCP: $($_.FullName)"
      }
    }
  }
}

if ($Uninstall) {
  Write-Host 'tunaLlama Windows 셋업 제거...'
  schtasks /End  /TN $TaskName 2>$null | Out-Null
  schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
  & claude mcp remove tunallama --scope user 2>$null | Out-Null
  Write-Host '완료. (플러그인 stdio MCP 는 재설치 시 자동 복구됨)'
  return
}

Write-Host "tunaLlama Windows 셋업 (HTTP 데몬, port $Port)..."

# 1) 데몬 스케줄 작업 (로그온 자동시작) + 즉시 실행.
#    wscript + hidden VBS 로 창 없이 실행 (VBS -> cmd(숨김) -> pythonw(콘솔 없음)).
schtasks /Create /TN $TaskName /TR "wscript.exe `"$Vbs`"" /SC ONLOGON /RL LIMITED /F | Out-Null
schtasks /Run /TN $TaskName | Out-Null
Write-Host '  daemon scheduled task 등록 + 실행'
Start-Sleep -Seconds 6

# 2) Claude Code 에 HTTP MCP 등록 (tunallama)
& claude mcp remove tunallama --scope user 2>$null | Out-Null
& claude mcp add --transport http --scope user tunallama $Url | Out-Null
Write-Host "  claude mcp add tunallama -> $Url"

# 3) 플러그인 stdio MCP 비활성화
Restore-PluginStdio $true

Write-Host ''
Write-Host '완료. Claude Code 재시작 후 mcp__tunallama__* 툴 사용 (in-session 정상).'
Write-Host "데몬 상태 확인:  curl http://127.0.0.1:$Port/mcp"
