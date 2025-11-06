/**
 * Puppeteer Service - Node.js service for browser automation
 * Provides HTTP API for Python crawler to request browser-based job extraction
 */

const express = require('express');
const cors = require('cors');
const puppeteer = require('puppeteer');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Browser instance for reuse
let browserInstance = null;

/**
 * Initialize or get browser instance
 */
async function getBrowser() {
  if (!browserInstance) {
    browserInstance = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--disable-gpu'
      ]
    });
    console.log('Browser instance initialized');
  }
  return browserInstance;
}

/**
 * Health check endpoint
 */
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'puppeteer-service' });
});

/**
 * Crawl endpoint - Extract jobs from a career page
 * POST /crawl
 * Body: {
 *   company_name: string,
 *   career_url: string,
 *   timeout?: number (ms),
 *   wait_for_selector?: string,
 *   wait_timeout?: number (ms)
 * }
 */
app.post('/crawl', async (req, res) => {
  const { company_name, career_url, timeout = 30000, wait_for_selector, wait_timeout = 30000 } = req.body;

  if (!company_name || !career_url) {
    return res.status(400).json({ error: 'company_name and career_url are required' });
  }

  let browser = null;
  let page = null;

  try {
    // Get browser instance and create a new context
    const browserInstance = await getBrowser();
    browser = await browserInstance.createBrowserContext();

    // Create page
    page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    console.log(`Crawling ${company_name}: ${career_url}`);

    // Navigate to page
    try {
      await page.goto(career_url, {
        waitUntil: 'networkidle',
        timeout: timeout
      });
    } catch (error) {
      console.warn(`Page load timeout for ${company_name}, continuing anyway`);
      // Continue even if timeout
    }

    // Wait for selector if provided
    if (wait_for_selector) {
      try {
        await page.waitForSelector(wait_for_selector, { timeout: wait_timeout });
        console.log(`Found selector ${wait_for_selector} for ${company_name}`);
      } catch (error) {
        console.warn(`Selector ${wait_for_selector} not found for ${company_name}`);
      }
    }

    // Wait for JavaScript to render
    await page.waitForTimeout(2000);

    // Extract jobs using multiple strategies
    const jobs = await extractJobs(page, company_name, career_url);

    res.json({
      success: true,
      jobs: jobs,
      count: jobs.length
    });

  } catch (error) {
    console.error(`Error crawling ${company_name}:`, error);
    res.status(500).json({
      success: false,
      error: error.message,
      jobs: []
    });
  } finally {
    // Cleanup
    if (page) {
      await page.close().catch(() => {});
    }
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
});

/**
 * Extract jobs from page using multiple strategies
 */
async function extractJobs(page, companyName, careerUrl) {
  const jobs = [];

  // Strategy 1: Extract JSON-LD structured data
  try {
    const jsonLdJobs = await extractJsonLd(page);
    if (jsonLdJobs.length > 0) {
      jobs.push(...jsonLdJobs);
      console.log(`Found ${jsonLdJobs.length} jobs via JSON-LD for ${companyName}`);
    }
  } catch (error) {
    console.debug(`JSON-LD extraction failed: ${error.message}`);
  }

  // Strategy 2: Extract via common selectors
  if (jobs.length === 0) {
    try {
      const selectorJobs = await extractViaSelectors(page, careerUrl);
      if (selectorJobs.length > 0) {
        jobs.push(...selectorJobs);
        console.log(`Found ${selectorJobs.length} jobs via selectors for ${companyName}`);
      }
    } catch (error) {
      console.debug(`Selector extraction failed: ${error.message}`);
    }
  }

  // Strategy 3: Execute JavaScript to extract jobs
  if (jobs.length === 0) {
    try {
      const jsJobs = await extractViaJavaScript(page);
      if (jsJobs.length > 0) {
        jobs.push(...jsJobs);
        console.log(`Found ${jsJobs.length} jobs via JavaScript for ${companyName}`);
      }
    } catch (error) {
      console.debug(`JavaScript extraction failed: ${error.message}`);
    }
  }

  return dedupeJobs(jobs);
}

/**
 * Extract jobs from JSON-LD structured data
 */
async function extractJsonLd(page) {
  const jobs = [];
  try {
    const scripts = await page.$$eval('script[type="application/ld+json"]', (scripts) => {
      return scripts.map(script => script.textContent);
    });

    for (const content of scripts) {
      if (!content) continue;
      try {
        const data = JSON.parse(content);
        const jobPostings = parseJsonLdJobPosting(data);
        jobs.push(...jobPostings);
      } catch (e) {
        // Not valid JSON, skip
      }
    }
  } catch (error) {
    console.debug(`JSON-LD extraction error: ${error.message}`);
  }
  return jobs;
}

/**
 * Recursively parse JSON-LD for JobPosting objects
 */
function parseJsonLdJobPosting(data) {
  const jobs = [];
  if (typeof data !== 'object' || data === null) return jobs;

  if (Array.isArray(data)) {
    for (const item of data) {
      jobs.push(...parseJsonLdJobPosting(item));
    }
  } else {
    if (data['@type'] === 'JobPosting') {
      const jobLocation = data.jobLocation || {};
      const address = (typeof jobLocation === 'object' && jobLocation.address) || {};
      jobs.push({
        title: data.title || null,
        location: (typeof address === 'object' && address.addressLocality) || null,
        url: data.url || (data.hiringOrganization && data.hiringOrganization.sameAs) || null,
        job_type: data.employmentType || null,
        description: data.description || null
      });
    }
    // Recursively search nested objects
    for (const value of Object.values(data)) {
      if (typeof value === 'object' && value !== null) {
        jobs.push(...parseJsonLdJobPosting(value));
      }
    }
  }
  return jobs;
}

/**
 * Extract jobs using common CSS selectors
 */
async function extractViaSelectors(page, baseUrl) {
  const jobs = [];
  const selectors = [
    '[data-job-id]',
    '.job-listing',
    '.job-item',
    '.job-card',
    '[class*="job"]',
    '[id*="job"]',
    'article[class*="job"]',
    'div[class*="position"]',
    'li[class*="job"]'
  ];

  for (const selector of selectors) {
    try {
      const elements = await page.$$(selector);
      if (elements.length > 0) {
        console.debug(`Found ${elements.length} elements with selector ${selector}`);
        for (let i = 0; i < Math.min(elements.length, 50); i++) {
          try {
            const job = await extractJobFromElement(elements[i], baseUrl);
            if (job && job.title) {
              jobs.push(job);
            }
          } catch (error) {
            console.debug(`Error extracting job from element: ${error.message}`);
          }
        }
        if (jobs.length > 0) {
          break; // Found jobs, stop trying other selectors
        }
      }
    } catch (error) {
      // Selector not found, continue
    }
  }

  return jobs;
}

/**
 * Extract job data from a DOM element
 */
async function extractJobFromElement(element, baseUrl) {
  try {
    const title = await element.$eval('h2, h3, .title, [class*="title"]', el => el.textContent).catch(() => null);
    const link = await element.$('a[href]').catch(() => null);
    let url = null;
    if (link) {
      url = await link.evaluate(el => el.href).catch(() => null);
      if (url && !url.startsWith('http')) {
        url = new URL(url, baseUrl).href;
      }
    }
    const location = await element.$eval('[class*="location"], [class*="city"]', el => el.textContent).catch(() => null);

    if (title) {
      return {
        title: title.trim(),
        url: url,
        location: location ? location.trim() : null
      };
    }
  } catch (error) {
    // Element doesn't have expected structure
  }
  return null;
}

/**
 * Extract jobs by executing JavaScript on the page
 */
async function extractViaJavaScript(page) {
  const jobs = [];
  try {
    const result = await page.evaluate(() => {
      const jobs = [];
      // Look for common job data patterns in JavaScript
      const scripts = Array.from(document.querySelectorAll('script'));
      for (const script of scripts) {
        const text = script.textContent || script.innerHTML;
        if (text && (text.includes('jobs') || text.includes('positions') || text.includes('openings'))) {
          try {
            // Try to extract JSON from script
            const jsonMatch = text.match(/\{[\s\S]*"jobs"[\s\S]*\}/);
            if (jsonMatch) {
              const data = JSON.parse(jsonMatch[0]);
              if (data.jobs && Array.isArray(data.jobs)) {
                return data.jobs;
              }
            }
          } catch (e) {
            // Not valid JSON
          }
        }
      }
      // Look for window/global job data
      if (window.jobs && Array.isArray(window.jobs)) {
        return window.jobs;
      }
      if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.jobs) {
        return window.__INITIAL_STATE__.jobs;
      }
      return [];
    });

    if (Array.isArray(result)) {
      jobs.push(...result.filter(item => item && typeof item === 'object'));
    }
  } catch (error) {
    console.debug(`JavaScript extraction error: ${error.message}`);
  }
  return jobs;
}

/**
 * Remove duplicate jobs
 */
function dedupeJobs(jobs) {
  const seen = new Set();
  const unique = [];
  for (const job of jobs) {
    const key = `${(job.url || '').toLowerCase().trim()}|${(job.title || '').toLowerCase().trim()}`;
    if (key && !seen.has(key) && job.title) {
      seen.add(key);
      unique.push(job);
    }
  }
  return unique;
}

// Start server
async function startServer() {
  try {
    // Initialize browser on startup (optional - can be lazy)
    // await getBrowser();
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`Puppeteer service listening on port ${PORT}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully');
  if (browserInstance) {
    await browserInstance.close();
  }
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully');
  if (browserInstance) {
    await browserInstance.close();
  }
  process.exit(0);
});

startServer();

