// 将 webm 视频按录制顺序转换为优化 GIF
// 使用 FFmpeg 调色板优化，12fps，960px 宽
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const VIDEOS_DIR = path.join(__dirname, 'videos');
const GIFS_DIR = path.join(__dirname, 'gifs');

// 录制顺序对应的输出文件名
const OUTPUT_NAMES = [
  '01_login',
  '02_spatial_twin',
  '03_dashboard',
  '04_energy_analysis',
  '05_devices',
  '06_ai_agent',
  '07_admin_dashboard',
  '08_frontier_hub',
  '09_advanced_hub'
];

if (!fs.existsSync(GIFS_DIR)) {
  fs.mkdirSync(GIFS_DIR, { recursive: true });
}

// 按修改时间排序 webm 文件（最旧的对应 01_login）
const webmFiles = fs.readdirSync(VIDEOS_DIR)
  .filter(f => f.endsWith('.webm'))
  .map(f => ({
    name: f,
    path: path.join(VIDEOS_DIR, f),
    mtime: fs.statSync(path.join(VIDEOS_DIR, f)).mtimeMs
  }))
  .sort((a, b) => a.mtime - b.mtime);

console.log(`📁 找到 ${webmFiles.length} 个 webm 文件，按修改时间排序：`);
webmFiles.forEach((f, i) => {
  console.log(`   ${i + 1}. ${f.name} -> ${OUTPUT_NAMES[i] || '未命名'}.gif`);
});

if (webmFiles.length !== OUTPUT_NAMES.length) {
  console.error(`❌ 文件数不匹配: ${webmFiles.length} != ${OUTPUT_NAMES.length}`);
  process.exit(1);
}

// 逐个转换
for (let i = 0; i < webmFiles.length; i++) {
  const input = webmFiles[i].path;
  const outputName = OUTPUT_NAMES[i];
  const output = path.join(GIFS_DIR, `${outputName}.gif`);
  const palette = path.join(VIDEOS_DIR, `palette_${i}.png`);

  console.log(`\n🔄 转换 ${outputName}.gif ...`);

  // 步骤 1: 生成调色板
  execSync(
    `ffmpeg.exe -y -i "${input}" -vf "fps=12,scale=960:-1:flags=lanczos,palettegen=max_colors=128" "${palette}"`,
    { stdio: 'pipe' }
  );

  // 步骤 2: 用调色板生成 GIF
  execSync(
    `ffmpeg.exe -y -i "${input}" -i "${palette}" -filter_complex "fps=12,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" "${output}"`,
    { stdio: 'pipe' }
  );

  // 清理调色板
  fs.unlinkSync(palette);

  const sizeKB = (fs.statSync(output).size / 1024).toFixed(1);
  console.log(`   ✅ ${outputName}.gif (${sizeKB} KB)`);
}

console.log('\n🎉 全部 GIF 转换完成！');
console.log(`📁 保存在: ${GIFS_DIR}`);

// 列出所有 GIF
const gifs = fs.readdirSync(GIFS_DIR).filter(f => f.endsWith('.gif'));
gifs.forEach(f => {
  const sizeKB = (fs.statSync(path.join(GIFS_DIR, f)).size / 1024).toFixed(1);
  console.log(`   - ${f} (${sizeKB} KB)`);
});
