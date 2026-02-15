// Goal 1, Task 1: Discover gkmlpt API endpoints (v2)
// Fixed: use domcontentloaded instead of networkidle (Vue SPA never goes idle)
// Strategy: load page, capture all XHR/fetch traffic during initial load + interactions

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  const apiCalls = [];

  // Intercept all network requests
  page.on('request', request => {
    const url = request.url();
    const resourceType = request.resourceType();
    if (resourceType === 'xhr' || resourceType === 'fetch') {
      console.log(`\n>>> REQUEST [${request.method()}]: ${url}`);
      if (request.postData()) {
        console.log(`    POST DATA: ${request.postData().substring(0, 500)}`);
      }
    }
  });

  page.on('response', async response => {
    const request = response.request();
    const resourceType = request.resourceType();
    if (resourceType === 'xhr' || resourceType === 'fetch') {
      const url = response.url();
      const status = response.status();
      let body = '';
      try {
        body = await response.text();
      } catch (e) {
        body = `[Could not read body: ${e.message}]`;
      }

      const entry = {
        method: request.method(),
        url: url,
        status: status,
        postData: request.postData() || null,
        bodyLength: body.length,
        bodyPreview: body.substring(0, 1500)
      };
      apiCalls.push(entry);

      console.log(`\n<<< RESPONSE [${status}] (${body.length} bytes): ${url}`);
      // Show first 500 chars of response
      console.log(`    PREVIEW: ${body.substring(0, 500)}`);
    }
  });

  // ============================================
  // Target 1: Pingshan gkmlpt
  // ============================================
  const targets = [
    'http://www.szpsq.gov.cn/psozhzx/gkmlpt/index',
    'http://www.szpsq.gov.cn/gkmlpt/index',
  ];

  for (const targetUrl of targets) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`Navigating to: ${targetUrl}`);
    console.log(`${'='.repeat(60)}\n`);

    try {
      // Use domcontentloaded - don't wait for network idle
      await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });

      // Wait for Vue app to mount and make API calls
      console.log('Waiting 8s for Vue app to load data...');
      await page.waitForTimeout(8000);

      // Log what's visible on the page
      const pageText = await page.evaluate(() => document.body.innerText.substring(0, 1000));
      console.log(`\nVisible page text (first 1000 chars):\n${pageText}`);

      // Try to find and click pagination
      console.log('\n--- Attempting pagination interactions ---');

      // Common Vue pagination patterns
      const paginationSelectors = [
        '.el-pager li',
        '.el-pagination .btn-next',
        'button.btn-next',
        '.pagination a',
        'a.page-link',
        '.ant-pagination-next',
        'li.number',
        '.page-item',
        '[class*="pager"]',
        '[class*="pagination"]',
        'a:has-text("下一页")',
        'button:has-text("下一页")',
        'a:has-text("2")',
        'li:has-text("2")',
      ];

      for (const sel of paginationSelectors) {
        try {
          const count = await page.locator(sel).count();
          if (count > 0) {
            console.log(`\nFound ${count} elements: ${sel}`);
            const text = await page.locator(sel).first().innerText().catch(() => '');
            console.log(`  Text: "${text}"`);
            // Click to trigger API call
            await page.locator(sel).first().click({ timeout: 3000 });
            console.log(`  Clicked!`);
            await page.waitForTimeout(3000);
          }
        } catch (e) {
          // ignore click failures
        }
      }

      // Also try typing in the search box
      try {
        const searchInput = page.locator('input[type="text"], input[placeholder*="搜索"], input[placeholder*="search"]');
        const searchCount = await searchInput.count();
        if (searchCount > 0) {
          console.log(`\nFound ${searchCount} search inputs, typing test query...`);
          await searchInput.first().fill('政策');
          await page.keyboard.press('Enter');
          await page.waitForTimeout(3000);
        }
      } catch (e) {
        console.log(`Search interaction failed: ${e.message}`);
      }

    } catch (e) {
      console.log(`Navigation error: ${e.message}`);
    }
  }

  // ============================================
  // Try the main portal gkmlpt too
  // ============================================
  console.log(`\n${'='.repeat(60)}`);
  console.log('Navigating to main portal gkmlpt...');
  console.log(`${'='.repeat(60)}\n`);

  try {
    await page.goto('http://www.sz.gov.cn/gkmlpt/index', { waitUntil: 'domcontentloaded', timeout: 20000 });
    console.log('Waiting 8s for Vue app...');
    await page.waitForTimeout(8000);
    const pageText = await page.evaluate(() => document.body.innerText.substring(0, 1000));
    console.log(`Visible text:\n${pageText}`);
  } catch (e) {
    console.log(`Error: ${e.message}`);
  }

  // ============================================
  // Summary
  // ============================================
  console.log(`\n\n${'='.repeat(60)}`);
  console.log(`SUMMARY: ${apiCalls.length} API calls captured`);
  console.log(`${'='.repeat(60)}\n`);

  // Group by URL pattern
  const patterns = {};
  for (const call of apiCalls) {
    const urlObj = new URL(call.url);
    const key = `${call.method} ${urlObj.pathname}`;
    if (!patterns[key]) {
      patterns[key] = { count: 0, example: call };
    }
    patterns[key].count++;
  }

  console.log('\n--- Unique API endpoint patterns ---');
  for (const [pattern, info] of Object.entries(patterns)) {
    console.log(`\n${pattern} (${info.count} calls)`);
    console.log(`  Full URL: ${info.example.url}`);
    console.log(`  Status: ${info.example.status}`);
    console.log(`  Response size: ${info.example.bodyLength} bytes`);
    console.log(`  Response preview: ${info.example.bodyPreview.substring(0, 300)}`);
    if (info.example.postData) {
      console.log(`  POST data: ${info.example.postData.substring(0, 300)}`);
    }
  }

  // Also dump full details of all API calls
  console.log('\n\n--- Full API call details ---');
  console.log(JSON.stringify(apiCalls, null, 2));

  await browser.close();
})();
