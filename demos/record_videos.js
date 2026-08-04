// Playwright 录制脚本：为 9 大页面生成操作视频
// 关键改进：通过 API 直接获取 JWT token，注入 localStorage，确保能访问所有受保护页面
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000';
const OUTPUT_DIR = path.join(__dirname, 'videos');

// 业务页面录制计划（不含登录页，登录页单独录）
const PAGES = [
  {
    name: '02_spatial_twin',
    url: '/spatial-twin',
    actions: async (page) => {
      // 等待 3D 场景加载完成
      await page.waitForTimeout(5000);
      // 用页面中心拖拽，不依赖 canvas 选择器
      const vp = page.viewportSize();
      const cx = vp.width / 2, cy = vp.height / 2;
      await page.mouse.move(cx, cy);
      await page.mouse.down();
      await page.mouse.move(cx - 120, cy + 60, { steps: 15 });
      await page.waitForTimeout(400);
      await page.mouse.move(cx + 80, cy - 40, { steps: 15 });
      await page.waitForTimeout(400);
      await page.mouse.move(cx - 60, cy + 80, { steps: 15 });
      await page.waitForTimeout(300);
      await page.mouse.up();
      await page.waitForTimeout(2500);
    }
  },
  {
    name: '03_dashboard',
    url: '/dashboard',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      const charts = page.locator('canvas, .echarts, [class*="chart"]');
      if (await charts.count() > 0) {
        const box = await charts.first().boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(1200);
        }
      }
      await page.mouse.wheel(0, 400);
      await page.waitForTimeout(2200);
    }
  },
  {
    name: '04_energy_analysis',
    url: '/energy',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      await page.click('button:has-text("周"), button:has-text("月"), [class*="tab"]', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1500);
      const chart = page.locator('canvas, .echarts').first();
      const box = await chart.boundingBox().catch(() => null);
      if (box) {
        await page.mouse.move(box.x + 100, box.y + 100);
        await page.mouse.move(box.x + 200, box.y + 150, { steps: 10 });
        await page.waitForTimeout(1500);
      }
    }
  },
  {
    name: '05_devices',
    url: '/devices',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      await page.click('[class*="category"], [class*="tab"], [class*="device-item"]', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1500);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '06_ai_agent',
    url: '/ai-agent',
    actions: async (page) => {
      await page.waitForTimeout(2500);
      const textarea = page.locator('textarea, input[type="text"][placeholder*="问"], [class*="chat-input"]');
      if (await textarea.count() > 0) {
        await textarea.first().click();
        await textarea.first().fill('帮我分析当前建筑的能耗状况');
        await page.waitForTimeout(500);
        await page.click('button:has-text("发送"), button[type="submit"], [class*="send"]', { timeout: 2000 }).catch(() => {});
        await page.waitForTimeout(4500);
      }
    }
  },
  {
    name: '07_admin_dashboard',
    url: '/admin',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(1500);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '08_frontier_hub',
    url: '/frontier/energy',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      const cards = page.locator('[class*="card"], [class*="feature"], [class*="item"]');
      const count = await cards.count();
      for (let i = 0; i < Math.min(count, 3); i++) {
        const box = await cards.nth(i).boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(600);
        }
      }
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '09_advanced_hub',
    url: '/advanced/esg',
    actions: async (page) => {
      await page.waitForTimeout(3500);
      const cards = page.locator('[class*="card"], [class*="feature"], [class*="item"]');
      const count = await cards.count();
      for (let i = 0; i < Math.min(count, 3); i++) {
        const box = await cards.nth(i).boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(600);
        }
      }
      await page.waitForTimeout(1500);
    }
  }
];

// 通过 API 获取 token（避免表单填写的各种坑）
async function fetchToken() {
  const resp = await fetch(`${API_URL}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  });
  if (!resp.ok) {
    throw new Error(`登录 API 失败: ${resp.status} ${await resp.text()}`);
  }
  const data = await resp.json();
  if (!data.token) {
    throw new Error('登录响应中缺少 token: ' + JSON.stringify(data));
  }
  return data;
}

(async () => {
  console.log('🎬 开始录制视频...');

  // 清理旧视频
  if (fs.existsSync(OUTPUT_DIR)) {
    fs.rmSync(OUTPUT_DIR, { recursive: true, force: true });
  }
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // 1. 通过 API 获取 token
  console.log('🔑 通过 API 获取 token...');
  const loginData = await fetchToken();
  console.log(`   ✅ 获取 token 成功 (用户: ${loginData.username || 'admin'})`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-gpu', '--no-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: {
      dir: OUTPUT_DIR,
      size: { width: 1440, height: 900 }
    }
  });

  // 2. 先录登录页（不注入 token，展示真实登录交互）
  console.log('📹 录制: 01_login (/login)');
  const loginPage = await context.newPage();
  try {
    await loginPage.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 15000 });
    await loginPage.waitForTimeout(1000);
    await loginPage.fill('input[type="text"], input[placeholder*="用户"], input[name="username"]', 'admin', { timeout: 5000 }).catch(() => {});
    await loginPage.waitForTimeout(400);
    await loginPage.fill('input[type="password"]', 'admin123', { timeout: 5000 }).catch(() => {});
    await loginPage.waitForTimeout(600);
    await loginPage.click('button:has-text("登录"), button[type="submit"]', { timeout: 5000 }).catch(() => {});
    await loginPage.waitForTimeout(2500);
    console.log('   ✅ 01_login 完成');
  } catch (err) {
    console.log(`   ⚠️ 01_login 出错: ${err.message}`);
  }
  await loginPage.close();
  await new Promise(r => setTimeout(r, 500));

  // 3. 录业务页面：每个页面打开后先注入 token，再导航
  for (const pageConfig of PAGES) {
    console.log(`📹 录制: ${pageConfig.name} (${pageConfig.url})`);

    const page = await context.newPage();
    try {
      // 先打开任意页面（让 origin 就绪），再注入 token
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      // 注入 token 到 localStorage
      await page.evaluate((token) => {
        localStorage.setItem('token', token);
        localStorage.setItem('username', 'admin');
      }, loginData.token);
      // 现在跳转到目标业务页面
      await page.goto(`${BASE_URL}${pageConfig.url}`, { waitUntil: 'networkidle', timeout: 20000 });
      await page.waitForTimeout(1500);

      // 验证是否真的进入了业务页面（URL 不应是 /login）
      const currentUrl = page.url();
      if (currentUrl.includes('/login')) {
        throw new Error('token 注入失败，被重定向回登录页');
      }

      await pageConfig.actions(page);
      console.log(`   ✅ ${pageConfig.name} 完成 (URL: ${currentUrl})`);
    } catch (err) {
      console.log(`   ⚠️ ${pageConfig.name} 出错: ${err.message}`);
    }
    await page.close();
    await new Promise(r => setTimeout(r, 500));
  }

  await browser.close();
  console.log('\n🎉 录制完成！视频保存在: ' + OUTPUT_DIR);

  // 列出生成的视频文件
  const files = fs.readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.webm'));
  console.log(`📁 共生成 ${files.length} 个视频文件:`);
  files.forEach(f => console.log(`   - ${f}`));
})();
