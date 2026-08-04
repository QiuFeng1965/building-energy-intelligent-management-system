// 子内容录制脚本：录制各模块内部 tab/弹窗/子功能的具体内容
// 使用 context.addInitScript 注入 token，每个新 page 自动携带登录态
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000';
const OUTPUT_DIR = path.join(__dirname, 'videos_sub');

// 通用：等待页面就绪
async function ready(page, ms = 2500) {
  await page.waitForTimeout(ms);
}

// 点击 el-tabs 的 tab（按文本匹配）
async function clickTab(page, text) {
  await page.click(`.el-tabs__item:has-text("${text}")`, { timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

// 悬停元素展示 tooltip/交互
async function hover(page, selector, idx = 0) {
  const loc = page.locator(selector);
  if (await loc.count() > idx) {
    const box = await loc.nth(idx).boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(800);
    }
  }
}

// 悬停 canvas 图表
async function hoverChart(page) {
  const charts = page.locator('canvas, .echarts, [_echarts_instance_]');
  if (await charts.count() > 0) {
    const box = await charts.first().boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(1000);
      // 在图表上滑动
      await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5, { steps: 8 });
      await page.waitForTimeout(500);
      await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.4, { steps: 8 });
      await page.waitForTimeout(800);
    }
  }
}

// 子内容录制清单（18 个核心子内容）
const SUB_PAGES = [
  // ===== 模块3：能源态势总览 =====
  {
    name: '10_dashboard_realtime',
    url: '/dashboard',
    actions: async (page) => {
      await ready(page, 3000);
      // 悬停实时功率曲线
      await hoverChart(page);
      // 悬停饼图
      const charts = page.locator('canvas, .echarts, [_echarts_instance_]');
      if (await charts.count() > 1) {
        const box = await charts.nth(1).boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(1000);
        }
      }
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '11_dashboard_health',
    url: '/dashboard',
    actions: async (page) => {
      await ready(page, 3000);
      // 滚动到底部展示设备健康度雷达图
      await page.mouse.wheel(0, 600);
      await page.waitForTimeout(1000);
      // 悬停雷达图（最后一个 canvas）
      const charts = page.locator('canvas, .echarts, [_echarts_instance_]');
      const count = await charts.count();
      if (count > 2) {
        const box = await charts.nth(count - 1).boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.waitForTimeout(1500);
        }
      }
      await page.waitForTimeout(1000);
    }
  },
  // ===== 模块4：能效诊断分析 =====
  {
    name: '12_energy_predict',
    url: '/energy',
    actions: async (page) => {
      await ready(page, 3500);
      // 切换时间范围到 48 小时
      await page.click('.el-radio-button:has-text("48")', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(2500);
      // 悬停预测图表
      await hoverChart(page);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '13_energy_rul',
    url: '/energy',
    actions: async (page) => {
      await ready(page, 3500);
      // 滚动到 RUL 预测性维护面板
      await page.mouse.wheel(0, 500);
      await page.waitForTimeout(1500);
      // 点击 COP 能效分析按钮（link 按钮）
      await page.click('button:has-text("COP"), .el-button:has-text("COP")', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(2000);
      // 关闭弹窗
      await page.click('.el-dialog__close, .el-button:has-text("关闭")', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1000);
    }
  },
  // ===== 模块5：能耗设备监测 =====
  {
    name: '14_devices_filter',
    url: '/devices',
    actions: async (page) => {
      await ready(page, 3000);
      // 点击设备类型筛选
      await page.click('.el-select, [class*="filter"], [class*="type"]', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(1000);
      // 选择一个类型
      await page.click('.el-select-dropdown__item:has-text("暖通"), .el-select-dropdown__item:has-text("HVAC")', { timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(2000);
      // 表格悬停
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1000);
    }
  },
  {
    name: '15_devices_detail',
    url: '/devices',
    actions: async (page) => {
      await ready(page, 3000);
      // 点击第一行的"详情"或"档案"按钮
      await page.click('.el-table__row:first-child button:has-text("详情"), .el-table__row:first-child button:has-text("档案"), .el-table__row:first-child [class*="detail"]', { timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(2500);
      // 展示弹窗内容
      const dialog = page.locator('.el-dialog');
      if (await dialog.count() > 0) {
        const box = await dialog.first().boundingBox();
        if (box) {
          await page.mouse.move(box.x + box.width / 2, box.y + 100);
          await page.waitForTimeout(1500);
        }
      }
      await page.waitForTimeout(1000);
    }
  },
  // ===== 模块6：AI 策略寻优 =====
  {
    name: '16_ai_dialog',
    url: '/ai-agent',
    actions: async (page) => {
      await ready(page, 2500);
      // 输入更具体的指令
      const textarea = page.locator('textarea, [class*="chat-input"]');
      if (await textarea.count() > 0) {
        await textarea.first().click();
        await textarea.first().fill('查询今天第一教学楼的异常能耗设备，并给出优化建议');
        await page.waitForTimeout(600);
        await page.click('button:has-text("发送"), button[type="submit"]', { timeout: 2000 }).catch(() => {});
        await page.waitForTimeout(5000);
      }
    }
  },
  // ===== 模块7：全局数据驾驶舱（5 个 tab）=====
  {
    name: '17_admin_overview',
    url: '/admin',
    actions: async (page) => {
      await ready(page, 3500);
      // 已默认在 overview tab，展示数据
      await hoverChart(page);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '18_admin_kb',
    url: '/admin',
    actions: async (page) => {
      await ready(page, 2500);
      await clickTab(page, '知识库');
      await page.waitForTimeout(2000);
      // 悬停知识库表格
      await hover(page, '.el-table__row', 0);
      await page.mouse.wheel(0, 200);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '19_admin_audit',
    url: '/admin',
    actions: async (page) => {
      await ready(page, 2500);
      await clickTab(page, '审计');
      await page.waitForTimeout(2000);
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1000);
      // 再切到告警/工具箱
      await clickTab(page, '告警');
      await page.waitForTimeout(1500);
    }
  },
  // ===== 模块8：前沿能力中心 =====
  {
    name: '20_frontier_anomaly',
    url: '/frontier/energy',
    actions: async (page) => {
      await ready(page, 3500);
      // 默认就在异常检测 tab，展示表格
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1000);
      await page.mouse.wheel(0, 200);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '21_frontier_carbon',
    url: '/frontier/energy',
    actions: async (page) => {
      await ready(page, 3000);
      await clickTab(page, '碳中和');
      await page.waitForTimeout(2500);
      await hoverChart(page);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '22_frontier_ai',
    url: '/frontier/ai',
    actions: async (page) => {
      await ready(page, 3500);
      // 多智能体协作 tab
      await hover(page, '[class*="card"], [class*="agent"]', 0);
      await page.waitForTimeout(1000);
      // 切到知识图谱
      await clickTab(page, '知识图谱');
      await page.waitForTimeout(2500);
      await hoverChart(page);
      await page.waitForTimeout(1000);
    }
  },
  {
    name: '23_frontier_twin3d',
    url: '/frontier/ops',
    actions: async (page) => {
      await ready(page, 4000);
      // 3D 实时数字孪生 tab
      const vp = page.viewportSize();
      const cx = vp.width / 2, cy = vp.height / 2;
      await page.mouse.move(cx, cy);
      await page.mouse.down();
      await page.mouse.move(cx - 80, cy + 40, { steps: 12 });
      await page.waitForTimeout(400);
      await page.mouse.move(cx + 60, cy - 30, { steps: 12 });
      await page.waitForTimeout(400);
      await page.mouse.up();
      await page.waitForTimeout(1500);
    }
  },
  // ===== 模块9：进阶能力中心 =====
  {
    name: '24_advanced_rul',
    url: '/advanced/diagnose',
    actions: async (page) => {
      await ready(page, 3500);
      // 设备健康度 & RUL 预测
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1000);
      await page.mouse.wheel(0, 200);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '25_advanced_benchmark',
    url: '/advanced/diagnose',
    actions: async (page) => {
      await ready(page, 3000);
      await clickTab(page, '能耗基准对标');
      await page.waitForTimeout(2500);
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1500);
    }
  },
  {
    name: '26_advanced_alert',
    url: '/advanced/ops',
    actions: async (page) => {
      await ready(page, 3500);
      // 智能告警中心
      await hover(page, '.el-table__row', 0);
      await page.waitForTimeout(1000);
      // 切到工单全生命周期
      await clickTab(page, '工单');
      await page.waitForTimeout(2000);
      await page.mouse.wheel(0, 200);
      await page.waitForTimeout(1000);
    }
  },
  {
    name: '27_advanced_esg',
    url: '/advanced/esg',
    actions: async (page) => {
      await ready(page, 3500);
      // ESG 报告
      await hoverChart(page);
      await page.waitForTimeout(1000);
      // 切到 ROI 测算
      await clickTab(page, 'ROI');
      await page.waitForTimeout(2500);
      await page.mouse.wheel(0, 200);
      await page.waitForTimeout(1500);
    }
  }
];

// 通过 API 获取 token
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
  return data.token;
}

(async () => {
  console.log('🎬 开始录制子内容视频...');

  // 清理旧视频
  if (fs.existsSync(OUTPUT_DIR)) {
    fs.rmSync(OUTPUT_DIR, { recursive: true, force: true });
  }
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // 1. 获取 token
  console.log('🔑 获取 token...');
  const token = await fetchToken();
  console.log('   ✅ token 获取成功');

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

  // 2. 用 addInitScript 注入 token，每个新 page 自动携带
  await context.addInitScript((t) => {
    localStorage.setItem('token', t);
    localStorage.setItem('username', 'admin');
  }, token);

  // 3. 逐个录制子内容
  for (const cfg of SUB_PAGES) {
    console.log(`📹 录制: ${cfg.name} (${cfg.url})`);
    const page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}${cfg.url}`, { waitUntil: 'networkidle', timeout: 20000 });
      await page.waitForTimeout(1500);

      const currentUrl = page.url();
      if (currentUrl.includes('/login')) {
        throw new Error('被重定向回登录页');
      }

      await cfg.actions(page);
      console.log(`   ✅ ${cfg.name} 完成 (URL: ${currentUrl})`);
    } catch (err) {
      console.log(`   ⚠️ ${cfg.name} 出错: ${err.message}`);
    }
    await page.close();
    await new Promise(r => setTimeout(r, 400));
  }

  await browser.close();
  console.log('\n🎉 子内容录制完成！视频保存在: ' + OUTPUT_DIR);

  const files = fs.readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.webm'));
  console.log(`📁 共生成 ${files.length} 个视频文件`);
})();
