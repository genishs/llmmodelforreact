# llmchat.ps1 — halo-ubuntu llama-server 에 붙는 Windows 터미널 대화 클라이언트
#   PowerShell 5.1(윈도우 기본) / 7 둘 다 동작. 설치할 것 없음.
#
#   .\llmchat.ps1                                  # 대화 모드
#   .\llmchat.ps1 "한 줄 질문"                       # 한 번 묻고 끝
#   .\llmchat.ps1 "이 코드 리뷰해줘" -File .\App.tsx  # 파일을 붙여서 질문
#   .\llmchat.ps1 -Fast "빠르게 답해"                # 생각 모드 끄기(훨씬 빠름)
#
#   접속 정보: -Url / -Key  또는 환경변수 LLM_URL / LLM_KEY
#   대화 중 명령: /reset 초기화 · /fast 생각모드 토글 · /quit 종료
#
#   🔴 이 파일은 UTF-8 BOM 으로 저장돼 있어야 한다. BOM 이 없으면 PS 5.1 이 한글을 깨뜨려 파싱이 실패한다.
#   실행이 막히면 한 번만:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param(
  [Parameter(Position = 0)][string]$Prompt,
  [string]$File,
  [string]$Url = $(if ($env:LLM_URL) { $env:LLM_URL } else { "http://192.168.234.209:8080" }),
  [string]$Key = $env:LLM_KEY,
  [switch]$Fast
)
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$script:history = New-Object System.Collections.ArrayList
$script:fast = [bool]$Fast

function Invoke-Chat([string]$text) {
  [void]$script:history.Add(@{ role = "user"; content = $text })
  $body = @{ messages = $script:history; stream = $true; temperature = 0.3 }
  if ($script:fast) { $body.chat_template_kwargs = @{ enable_thinking = $false } }
  $bytes = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 10 -Compress))

  $req = [Net.HttpWebRequest]::Create($Url.TrimEnd('/') + "/v1/chat/completions")
  $req.Method = "POST"; $req.ContentType = "application/json"; $req.Timeout = 1800000; $req.ReadWriteTimeout = 1800000
  if ($Key) { $req.Headers.Add("Authorization", "Bearer $Key") }
  $answer = New-Object Text.StringBuilder; $n = 0; $sw = [Diagnostics.Stopwatch]::StartNew(); $thinking = $false
  try {
    $s = $req.GetRequestStream(); $s.Write($bytes, 0, $bytes.Length); $s.Close()
    $rd = New-Object IO.StreamReader($req.GetResponse().GetResponseStream(), [Text.Encoding]::UTF8)
    while (-not $rd.EndOfStream) {
      $line = $rd.ReadLine()
      if (-not $line.StartsWith("data:")) { continue }
      $data = $line.Substring(5).Trim()
      if ($data -eq "[DONE]") { break }
      $d = ($data | ConvertFrom-Json).choices[0].delta
      if ($d.reasoning_content) { $n++; if (-not $thinking) { Write-Host "(생각 중…)" -NoNewline -ForegroundColor DarkGray; $thinking = $true } }
      if ($d.content) {
        $n++
        if ($thinking -and $answer.Length -eq 0) { Write-Host "`r            `r" -NoNewline }
        [void]$answer.Append($d.content); Write-Host $d.content -NoNewline
      }
    }
    $rd.Close()
  } catch [Net.WebException] {
    [void]$script:history.RemoveAt($script:history.Count - 1)
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
    if ($code -eq 401) { Write-Host "`n🔴 HTTP 401: API 키가 없거나 틀렸습니다 (-Key 또는 `$env:LLM_KEY)" -ForegroundColor Red }
    elseif ($code) { Write-Host "`n🔴 HTTP ${code}: $($_.Exception.Message)" -ForegroundColor Red }
    else { Write-Host "`n🔴 접속 실패: $Url — 서버가 켜져 있는지, 방화벽(8080)이 열렸는지 확인하세요" -ForegroundColor Red }
    return
  }
  $t = $sw.Elapsed.TotalSeconds
  Write-Host ("`n— {0}토큰 · {1:N1}초 · {2:N1} t/s" -f $n, $t, ($(if ($t) { $n / $t } else { 0 }))) -ForegroundColor DarkGray
  [void]$script:history.Add(@{ role = "assistant"; content = $answer.ToString() })
}

if ($Prompt -or $File) {
  $q = $Prompt
  if ($File) { $q += "`n`n``````n" + (Get-Content -Raw -Encoding UTF8 $File) + "`n``````" }
  Invoke-Chat $q; return
}

Write-Host "$Url 에 연결 · /reset /fast /quit" -ForegroundColor White
while ($true) {
  Write-Host "`n두목> " -NoNewline -ForegroundColor Cyan
  $t = Read-Host
  if ($null -eq $t) { break }; $t = $t.Trim(); if (-not $t) { continue }
  switch ($t) {
    "/quit" { return }
    "/exit" { return }
    "/reset" { $script:history.Clear(); Write-Host "대화 초기화"; continue }
    "/fast" { $script:fast = -not $script:fast; Write-Host ("생각 모드: " + $(if ($script:fast) { "끔(빠름)" } else { "켬" })); continue }
    default { Invoke-Chat $t }
  }
}
