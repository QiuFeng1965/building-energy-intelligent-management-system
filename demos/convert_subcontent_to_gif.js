// 将子内容 webm 视频按录制顺序转换为优化 GIF
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const VIDEOS_DIR = path.join(__dirname, 'videos_sub');
const GIFS_DIR = path.join(__dirname, 'gifs');

// 子内容输出文件名（与录制顺序严格对应）
const OUTPUT_NAMES = [
  '10_dashboard_realtime',
  '11_dashboard_health',
  '12_energy_predict',
  '13_energy_rul',
  '14_devices_filter',
  '15_devices_detail',
  '16_ai_dialog',
  '17_admin_overview',
  '18_admin_kb',
  '19_admin_audit',
  '20_frontier_anomaly',
  '21_frontier_carbon',
  '22_frontier_ai',
  '23_frontier_twin3d',
  '24_advanced_rul',
  '25_advanced_benchmark',
  '26_advanced_alert',
  '27_advanced_esg'
];

if (!fs.existsSync(GIFS_DIR)) {
  fs.mkdirSync(GIFS_DIR, { recursive: true });
}

// 按修改时间排序 webm 文件
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

for (let i = 0; i < webmFiles.length; i++) {
  const input = webmFiles[i].path;
  const outputName = OUTPUT_NAMES[i];
  const output = path.join(GIFS_DIR, `${outputName}.gif`);
  const palette = path.join(VIDEOS_DIR, `palette_${i}.png`);

  console.log(`\n🔄 转换 ${outputName}.gif ...`);

  // 生成调色板
  execSync(
    `ffmpeg.exe -y -i "${input}" -vf "fps=10,scale=960:-1:flags=lanczos,palettegen=max_colors=128" "${palette}"`,
    { stdio: 'pipe' }
  );

  // 用调色板生成 GIF
  execSync(
    `ffmpeg.exe -y -i "${input}" -i "${palette}" -filter_complex "fps=10,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" "${output}"`,
    { stdio: 'pipe' }
  );

  fs.unlinkSync(palette);

  const sizeKB = (fs.statSync(output).size / 1024).toFixed(1);
  console.log(`   ✅ ${outputName}.gif (${sizeKB} KB)`);
}

console.log('\n🎉 全部子内容 GIF 转换完成！');
console.log(`📁 保存在: ${GIFS_DIR}`);

const gifs = fs.readdirSync(GIFS_DIR).filter(f => f.endsWith('.gif') && f.startsWith(/1[0-9]|2[0-9]/));
gifs.forEach(f => {
  const sizeKB = (fs.statSync(path.join(GIFS_DIR, f)).size / 1024).toFixed(1);
  console.log(`   - ${f} (${sizeKB} KB)`);
});
