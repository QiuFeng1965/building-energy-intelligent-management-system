// Playwright 录制脚本：为 9 大页面生成操作动图
// 使用方法：node demos/record_gifs.js

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:5173';
const OUTPUT_DIR = path.join(__dirname, 'gifs');

// 页面录制计划：每个页面录制 8 秒，包含关键交互
const PAGES = [
  {
    name: '01_login',
    url: '/login',
    actions: async (page) => {
      // 输入账号密码
      await page.fill('input[type="text"], input[placeholder*="用户"], input[name="username"]', 'admin', { timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(300);
      await page.fill('input[type="password"]', 'admin123', { timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(500);
      // 点击登录
      await page.click('button:has-text("登录"), button[type="submit"]', { timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '02_spatial_twin',
    url: '/spatial-twin',
    actions: async (page) => {
      // 等待 3D 加载
      await page.waitForTimeout(3000);
      // 鼠标拖拽旋转 3D 场景
      const canvas = await page.locator('canvas').first();
      const box = await canvas.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width / 2 - 150, box.y + box.height / 2 + 80, { steps: 20 });
        await page.waitForTimeout(500);
        await page.mouse.move(box.x + box.width / 2 + 100, box.y + box.height / 2 - 60, { steps: 20 });
        await page.waitForTimeout(500);
        await page.mouse.up();
      }
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '03_dashboard',
    url: '/dashboard',
    actions: async (page) => {
      await page.waitForTimeout(3000);
      // 鼠标悬停图表
      const charts = page.locator('canvas, .echarts, [class*="chart"]');
      const count = await charts.count();
      if (count > 0) {
        const box = await charts.first().boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(1000);
        }
      }
      // 滚动展示更多内容
      await page.mouse.wheel(0, 400);
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '04_energy_analysis',
    url: '/energy',
    actions: async (page) => {
      await page.waitForTimeout(3000);
      // 点击时间范围切换
      await page.click('button:has-text("周"), button:has-text("月"), [class*="tab"]', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1500);
      // 悬停图表
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
      await page.waitForTimeout(3000);
      // 点击设备分类
      await page.click('[class*="category"], [class*="tab"], [class*="device-item"]', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1500);
      // 滚动
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '06_ai_agent',
    url: '/ai-agent',
    actions: async (page) => {
      await page.waitForTimeout(2000);
      // 输入对话
      const textarea = page.locator('textarea, input[type="text"][placeholder*="问"], [class*="chat-input"]');
      if (await textarea.count() > 0) {
        await textarea.first().click();
        await textarea.first().fill('帮我分析当前建筑的能耗状况');
        await page.waitForTimeout(500);
        // 发送
        await page.click('button:has-text("发送"), button[type="submit"], [class*="send"]', { timeout: 2000 }).catch(() => {});
        await page.waitForTimeout(4000); // 等待 AI 流式回复
      }
    }
  },
  {
    name: '07_admin_dashboard',
    url: '/admin',
    actions: async (page) => {
      await page.waitForTimeout(3000);
      // 滚动展示数据
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(1500);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(2000);
    }
  },
  {
    name: '08_frontier_hub',
    url: '/frontier',
    actions: async (page) => {
      await page.waitForTimeout(3000);
      // 悬停卡片
      const cards = page.locator('[class*="card"], [class*="feature"], [class*="item"]');
      const count = await cards.count();
      if (count > 0) {
        for (let i = 0; i < Math.min(count, 3); i++) {
          const box = await cards.nth(i).boundingBox();
          if (box) {
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
            await page.waitForTimeout(600);
          }
        }
      }
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '09_advanced_hub',
    url: '/advanced',
    actions: async (page) => {
      await page.waitForTimeout(3000);
      // 悬停卡片
      const cards = page.locator('[class*="card"], [class*="feature"], [class*="item"]');
      const count = await cards.count();
      if (count > 0) {
        for (let i = 0; i < Math.min(count, 3); i++) {
          const box = await cards.nth(i).boundingBox();
          if (box) {
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
            await page.waitForTimeout(600);
          }
        }
      }
      await page.waitForTimeout(1500);
    }
  }
];

(async () => {
  console.log('🎬 开始录制动图...');

  // 确保输出目录存在
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

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

  // 先登录获取 token
  console.log('📝 正在登录...');
  const loginPage = await context.newPage();
  await loginPage.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 15000 });
  await loginPage.waitForTimeout(1000);
  await loginPage.fill('input[type="text"], input[placeholder*="用户"], input[name="username"]', 'admin', { timeout: 5000 }).catch(() => {});
  await loginPage.fill('input[type="password"]', 'admin123', { timeout: 5000 }).catch(() => {});
  await loginPage.click('button:has-text("登录"), button[type="submit"]', { timeout: 5000 }).catch(() => {});
  await loginPage.waitForTimeout(3000);
  // 登录后关闭这个页面
  await loginPage.close();
  console.log('✅ 登录完成');

  // 逐页录制
  for (const pageConfig of PAGES) {
    console.log(`📹 录制: ${pageConfig.name} (${pageConfig.url})`);

    const page = await context.newPage();

    try {
      await page.goto(`${BASE_URL}${pageConfig.url}`, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1500);

      // 执行交互动作
      await pageConfig.actions(page);

      console.log(`   ✅ ${pageConfig.name} 录制完成`);
    } catch (err) {
      console.log(`   ⚠️ ${pageConfig.name} 录制出错: ${err.message}`);
    }

    // 关闭页面，触发视频保存
    await page.close();
    await new Promise(r => setTimeout(r, 500));
  }

  await browser.close();
  console.log('\n🎉 所有页面录制完成！');
  console.log(`📁 视频文件保存在: ${OUTPUT_DIR}`);
})();
