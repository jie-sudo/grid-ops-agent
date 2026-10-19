// 临时截图脚本：用 playwright-core + agent-browser 下载的 Chrome 验证前端渲染
import { chromium } from 'playwright-core';

const CHROME = 'C:/Users/Administrator/.agent-browser/browsers/chrome-155.0.8059.84/chrome.exe';
const OUT = 'D:/通用agent/grid-ops-agent-main/web/screenshots';

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 1. 登录页
  await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/01-login.png` });
  console.log('已截图：登录页');

  // 2. 登录（admin）
  await page.fill('input#username', 'admin');
  await page.fill('input#password', 'admin123');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/02-workbench.png` });
  console.log('已截图：对话工作台');

  // 3. 发送一条消息（触发 mock SSE 流式）
  await page.fill('input[placeholder*="输入问题"]', '诊断变压器的油温');
  await page.press('input[placeholder*="输入问题"]', 'Enter');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/03-chat.png` });
  console.log('已截图：对话流式');

  // 4. 设备管理
  await page.click('text=设备管理');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/04-devices.png` });
  console.log('已截图：设备管理');

  // 5. 工单管理
  await page.click('text=工单管理');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/05-workorders.png` });
  console.log('已截图：工单管理');

  await browser.close();
  console.log('完成');
}

main().catch((e) => {
  console.error('截图失败：', e.message);
  process.exit(1);
});
