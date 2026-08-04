# 将 webm 按录制顺序重命名并转换为 GIF
$gifDir = "c:\Users\Administrator\Desktop\🔧 开发项目\Building Energy Intelligent Management System2\demos\gifs"
$ffmpeg = "C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

# 按修改时间排序的文件
$files = Get-ChildItem "$gifDir\*.webm" | Sort-Object LastWriteTime

# 页面名称（按录制顺序，第1个是登录页，第2个是登录后跳转页）
# 实际录制顺序：login, spatial_twin(失败但仍有视频), dashboard, energy, devices, ai_agent, admin, frontier, advanced
$pageNames = @(
    "01_login",
    "02_spatial_twin",
    "03_dashboard",
    "04_energy_analysis",
    "05_devices",
    "06_ai_agent",
    "07_admin_dashboard",
    "08_frontier_hub",
    "09_advanced_hub"
)

# 只取前 9 个文件（多余的丢弃）
$filesToConvert = $files | Select-Object -First 9

Write-Host "=== 开始转换为 GIF ===" -ForegroundColor Cyan

for ($i = 0; $i -lt $filesToConvert.Count; $i++) {
    $webmFile = $filesToConvert[$i]
    $gifName = "$($pageNames[$i]).gif"
    $gifPath = Join-Path $gifDir $gifName

    Write-Host "[$($i+1)/9] 转换 $($webmFile.Name) -> $gifName" -ForegroundColor Yellow

    # ffmpeg: webm -> gif，降帧率到 12fps，缩放到 960px 宽（减小体积），优化调色板
    & $ffmpeg -y -i $webmFile.FullName -vf "fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" -loop 0 $gifPath 2>&1 | Out-Null

    if (Test-Path $gifPath) {
        $size = (Get-Item $gifPath).Length / 1KB
        Write-Host "  ✅ $gifName ($([math]::Round($size,0)) KB)" -ForegroundColor Green
    } else {
        Write-Host "  ❌ 转换失败" -ForegroundColor Red
    }
}

# 清理 webm 文件
Write-Host "`n=== 清理 webm 源文件 ===" -ForegroundColor Cyan
Get-ChildItem "$gifDir\*.webm" | Remove-Item -Force
Write-Host "✅ 清理完成" -ForegroundColor Green

# 列出最终结果
Write-Host "`n=== 最终 GIF 文件 ===" -ForegroundColor Cyan
Get-ChildItem "$gifDir\*.gif" | Sort-Object Name | Format-Table Name, @{N='Size_KB';E={[math]::Round($_.Length/1KB,0)}} -AutoSize
