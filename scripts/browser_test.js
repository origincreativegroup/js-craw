/**
 * Browser Test Script - Test browser-based crawling (Puppeteer)
 * Usage: node scripts/browser_test.js [url]
 */

const puppeteer = require('puppeteer');

async function testBrowserCrawl(url = 'https://example.com/careers') {
  console.log(`Testing browser crawl for: ${url}`);
  
  let browser = null;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage'
      ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    console.log('Loading page...');
    await page.goto(url, {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    // Wait for content
    await page.waitForTimeout(2000);

    // Extract JSON-LD
    console.log('Extracting JSON-LD...');
    const jsonLdJobs = await page.$$eval('script[type="application/ld+json"]', (scripts) => {
      return scripts.map(script => {
        try {
          return JSON.parse(script.textContent || '{}');
        } catch (e) {
          return null;
        }
      }).filter(Boolean);
    });
    console.log(`Found ${jsonLdJobs.length} JSON-LD scripts`);

    // Extract job selectors
    console.log('Extracting jobs via selectors...');
    const selectors = [
      '[data-job-id]',
      '.job-listing',
      '.job-item',
      '.job-card',
      '[class*="job"]'
    ];

    let jobs = [];
    for (const selector of selectors) {
      try {
        const elements = await page.$$(selector);
        if (elements.length > 0) {
          console.log(`Found ${elements.length} elements with selector: ${selector}`);
          for (let i = 0; i < Math.min(elements.length, 10); i++) {
            try {
              const title = await elements[i].$eval('h2, h3, .title, [class*="title"]', el => el.textContent).catch(() => null);
              const link = await elements[i].$('a[href]').catch(() => null);
              const url = link ? await link.evaluate(el => el.href).catch(() => null) : null;
              
              if (title) {
                jobs.push({ title: title.trim(), url });
              }
            } catch (e) {
              // Skip this element
            }
          }
          if (jobs.length > 0) break;
        }
      } catch (e) {
        // Selector not found
      }
    }

    // Extract via JavaScript
    console.log('Extracting jobs via JavaScript...');
    const jsJobs = await page.evaluate(() => {
      const jobs = [];
      if (window.jobs && Array.isArray(window.jobs)) {
        return window.jobs;
      }
      if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.jobs) {
        return window.__INITIAL_STATE__.jobs;
      }
      return [];
    });

    if (jsJobs.length > 0) {
      console.log(`Found ${jsJobs.length} jobs via JavaScript`);
      jobs.push(...jsJobs);
    }

    console.log('\n=== Results ===');
    console.log(`Total jobs found: ${jobs.length}`);
    if (jobs.length > 0) {
      console.log('\nSample jobs:');
      jobs.slice(0, 5).forEach((job, i) => {
        console.log(`${i + 1}. ${job.title || 'No title'}`);
        if (job.url) console.log(`   URL: ${job.url}`);
      });
    }

    return jobs;

  } catch (error) {
    console.error('Error:', error.message);
    throw error;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// Run test
const url = process.argv[2] || 'https://example.com/careers';
testBrowserCrawl(url)
  .then(() => {
    console.log('\nTest completed successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\nTest failed:', error);
    process.exit(1);
  });

