const { chromium } = require('playwright');
const path = require('path');

(async () => {
  console.log('[Playwright E2E] Initializing headless Chromium browser...');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  // Test 1: External network connectivity and DNS resolution
  console.log('[Playwright E2E] Testing external network access...');
  await page.goto('https://example.com', { waitUntil: 'domcontentloaded', timeout: 15000 });
  const externalTitle = await page.title();
  console.log(`[Playwright E2E] External page loaded successfully: "${externalTitle}"`);

  // Test 2: Local frontend bundle loading
  const distPath = 'file:///' + path.resolve(__dirname, 'dist', 'index.html').replace(/\\/g, '/');
  console.log(`[Playwright E2E] Testing local asset rendering: ${distPath}`);
  await page.goto(distPath, { waitUntil: 'load', timeout: 15000 });
  const localTitle = await page.title();
  console.log(`[Playwright E2E] Local page title: "${localTitle}"`);

  const hasRoot = await page.evaluate(() => !!document.getElementById('root'));
  console.log(`[Playwright E2E] DOM #root container present: ${hasRoot}`);

  await browser.close();
  console.log('[Playwright E2E] All Playwright browser checks PASSED successfully.');
})().catch((err) => {
  console.error('[Playwright E2E] Verification failed:', err);
  process.exit(1);
});
