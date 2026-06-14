# ==============================================================
# PDF标注工具 v7.3 — Windows 11 一键构建脚本
# ==============================================================
# 前置条件: 需要手动安装以下工具（脚本会检查）
#   1. Python 3.11+ (加入 PATH)
#   2. Rust toolchain (https://rustup.rs)
#   3. Node.js 18+ + pnpm (https://nodejs.org)
#   4. Microsoft C++ Build Tools (MSVC)
#
# 用法:
#   cd pdf-label-tool-tauri
#   powershell -ExecutionPolicy Bypass -File win11/build.ps1
#
# 构建流程:
#   Step 1: 安装 Python 依赖
#   Step 2: PyInstaller 打包 sidecar → pdf-label-backend.exe
#   Step 3: 拷贝 frontend + sidecar exe 到 Tauri 资源目录
#   Step 4: cargo tauri build → 生成 .exe / .msi
#   Step 5: 收集最终产物
# ==============================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WinDir = $PSScriptRoot

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  PDF标注工具 v7.3 — Windows 构建" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# === 环境检查 ===
Write-Host "[0/5] 检查构建环境..." -ForegroundColor Yellow

$checks = @(
    @{ Name = "Python";  Cmd = "python --version" },
    @{ Name = "Rust";    Cmd = "rustc --version" },
    @{ Name = "Node.js"; Cmd = "node --version" },
    @{ Name = "Cargo";   Cmd = "cargo --version" }
)

$failed = $false
foreach ($c in $checks) {
    try {
        $ver = Invoke-Expression $c.Cmd 2>&1
        Write-Host "  ✓ $($c.Name): $ver" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ $($c.Name) 未安装" -ForegroundColor Red
        $failed = $true
    }
}

if ($failed) {
    Write-Host "`n请先安装缺失的工具。" -ForegroundColor Red
    Write-Host "Python:  https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Rust:    https://rustup.rs" -ForegroundColor Yellow
    Write-Host "Node.js: https://nodejs.org" -ForegroundColor Yellow
    Write-Host "MSVC:    'Desktop development with C++ workload' in VS Installer" -ForegroundColor Yellow
    exit 1
}

# === Step 1: Python 依赖 ===
Write-Host "`n[1/5] 安装 Python 依赖..." -ForegroundColor Yellow

python -m pip install --upgrade pip
python -m pip install -r "$WinDir\requirements.txt"
python -m pip install pyinstaller

if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 依赖安装失败" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Python 依赖安装完成" -ForegroundColor Green

# === Step 2: PyInstaller 打包 sidecar ===
Write-Host "`n[2/5] PyInstaller 打包 sidecar..." -ForegroundColor Yellow

Push-Location $WinDir
pyinstaller pdf-label-backend.spec --noconfirm
Pop-Location

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller 打包失败" -ForegroundColor Red
    exit 1
}

$sidecarExe = "$WinDir\dist\pdf-label-backend.exe"
if (-not (Test-Path $sidecarExe)) {
    Write-Host "pdf-label-backend.exe 未生成" -ForegroundColor Red
    exit 1
}

$exeSize = [math]::Round((Get-Item $sidecarExe).Length / 1MB, 0)
Write-Host "  ✓ pdf-label-backend.exe ($exeSize MB)" -ForegroundColor Green

# === Step 3: 拷贝资源到 Tauri 目录 ===
Write-Host "`n[3/5] 拷贝资源..." -ForegroundColor Yellow

# 确保 Tauri resources 目录存在
$tauriDir = "$ProjectRoot\src-tauri"

# 拷贝 sidecar exe — Tauri 会在 build 时将其打包进 resources
Copy-Item $sidecarExe -Destination "$tauriDir\pdf-label-backend.exe" -Force
Write-Host "  ✓ pdf-label-backend.exe → src-tauri/" -ForegroundColor Green

# frontend/index.html 已在项目目录，Tauri 自动打包

# === Step 4: Tauri 构建 ===
Write-Host "`n[4/5] Tauri 构建 (可能需要 5-10 分钟)..." -ForegroundColor Yellow

Push-Location $ProjectRoot
cargo tauri build 2>&1 | ForEach-Object { Write-Host "  $_" }
Pop-Location

if ($LASTEXITCODE -ne 0) {
    Write-Host "Tauri 构建失败" -ForegroundColor Red
    Write-Host "如果报 webview2 错误，请安装: https://developer.microsoft.com/microsoft-edge/webview2/" -ForegroundColor Yellow
    exit 1
}

# === Step 5: 收集产物 ===
Write-Host "`n[5/5] 收集构建产物..." -ForegroundColor Yellow

$releaseDir = "$tauriDir\target\release\bundle"
$outputDir = "$ProjectRoot\win11\output"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

# 复制 exe 安装包
Get-ChildItem "$releaseDir\*\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName -Destination $outputDir -Force
    $size = [math]::Round($_.Length / 1MB, 0)
    Write-Host "  ✓ $($_.Name) ($size MB)" -ForegroundColor Green
}

# 复制 msi 安装包
Get-ChildItem "$releaseDir\*\*.msi" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName -Destination $outputDir -Force
    $size = [math]::Round($_.Length / 1MB, 0)
    Write-Host "  ✓ $($_.Name) ($size MB)" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  构建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n产物位置: $outputDir" -ForegroundColor White
Write-Host "`n注意事项:" -ForegroundColor Yellow
Write-Host "  1. PaddleOCR 首次运行自动下载模型 (~50MB)" -ForegroundColor Yellow
Write-Host "  2. 如需完全离线: 在有网机器运行一次, 拷贝 C:\Users\<user>\.paddleocr\" -ForegroundColor Yellow
Write-Host "  3. 安装后 pdf-label-backend.exe 在主程序同目录" -ForegroundColor Yellow
