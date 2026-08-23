param(
  [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Version = "1.1.0"
$Venv = Join-Path $Root ".win-build-venv"

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
  $BasePython = $null
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $Candidate = & py -3.12 -c "import struct,sys; assert struct.calcsize('P') == 8; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $Candidate) {
      $BasePython = ($Candidate | Select-Object -Last 1).Trim()
    }
  }
  if (-not $BasePython -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $Candidate = & python -c "import struct,sys; assert sys.version_info >= (3, 10) and struct.calcsize('P') == 8; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $Candidate) {
      $BasePython = ($Candidate | Select-Object -Last 1).Trim()
    }
  }
  if (-not $BasePython) { throw "需要 64 位 Python 3.10 或更高版本" }
  & $BasePython -m venv $Venv
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements-webview.txt")

& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "douyin-index-tool-v$Version-windows-x64" `
  --paths (Join-Path $Root "src") `
  --hidden-import webview.platforms.edgechromium `
  --icon (Join-Path $Root "assets\douyin-index-icon.ico") `
  --add-data "$(Join-Path $Root 'src\douyin_index_tool\webview_ui');douyin_index_tool\webview_ui" `
  --exclude-module cefpython3 `
  (Join-Path $Root "run_webview_gui.py")

$Exe = Join-Path $Root "dist\douyin-index-tool-v$Version-windows-x64.exe"
if (-not (Test-Path $Exe)) { throw "EXE output missing: $Exe" }

if (-not $SkipSmokeTest) {
  $UiResult = Join-Path $env:TEMP "douyin-index-ui-self-test.json"
  if (Test-Path $UiResult) { Remove-Item -Force $UiResult }
  $Process = Start-Process -FilePath $Exe -ArgumentList "--demo", "--ui-self-test-output", $UiResult -Wait -PassThru
  if ($Process.ExitCode -ne 0) { throw "GUI smoke test failed, exit $($Process.ExitCode)" }
  if (-not (Test-Path $UiResult)) { throw "GUI self-test result missing: $UiResult" }
  $Ui = Get-Content -Raw -Encoding UTF8 $UiResult | ConvertFrom-Json
  if (-not $Ui.allPass) { throw "GUI self-test failed: $(Get-Content -Raw -Encoding UTF8 $UiResult)" }
  $CheckCount = ($Ui.checks.PSObject.Properties | Measure-Object).Count
  Write-Host "Windows GUI self-test: $CheckCount/$CheckCount"
}

Get-FileHash -Algorithm SHA256 $Exe | Format-List
Write-Host "Windows executable: $Exe"
