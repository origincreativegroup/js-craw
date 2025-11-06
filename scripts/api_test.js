/**
 * API Test Script - Test API-based job fetching
 * Usage: node scripts/api_test.js [url]
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');

async function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const client = parsedUrl.protocol === 'https:' ? https : http;
    
    const req = client.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        resolve({ statusCode: res.statusCode, data });
      });
    });
    
    req.on('error', (error) => {
      reject(error);
    });
    
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

async function testApiDetection(url = 'https://example.com/careers') {
  console.log(`Testing API detection for: ${url}`);
  console.log('');

  try {
    // Fetch HTML
    console.log('1. Fetching HTML...');
    const response = await fetchUrl(url);
    if (response.statusCode !== 200) {
      console.log(`   Status: ${response.statusCode}`);
      return;
    }
    const html = response.data;
    console.log(`   ✓ HTML fetched (${html.length} bytes)`);

    // Check for Greenhouse
    console.log('\n2. Checking for Greenhouse API...');
    if (html.includes('greenhouse.io') || html.includes('boards-api.greenhouse.io')) {
      console.log('   ✓ Greenhouse detected');
      const match = html.match(/greenhouse\.io\/([^/"']+)/);
      if (match) {
        const slug = match[1];
        console.log(`   ✓ Company slug: ${slug}`);
        const apiUrl = `https://boards-api.greenhouse.io/v1/boards/${slug}/jobs`;
        console.log(`   API URL: ${apiUrl}`);
        try {
          const apiResponse = await fetchUrl(apiUrl);
          if (apiResponse.statusCode === 200) {
            const jobs = JSON.parse(apiResponse.data);
            console.log(`   ✓ API accessible, found ${jobs.jobs?.length || 0} jobs`);
          }
        } catch (e) {
          console.log(`   ✗ API not accessible: ${e.message}`);
        }
      }
    } else {
      console.log('   ✗ Greenhouse not detected');
    }

    // Check for Lever
    console.log('\n3. Checking for Lever API...');
    if (html.includes('api.lever.co') || html.includes('lever.co/v0/postings')) {
      console.log('   ✓ Lever detected');
      const match = html.match(/lever\.co\/v0\/postings\/([^/"']+)/) || 
                    html.match(/jobs\.lever\.co\/([^/"']+)/);
      if (match) {
        const slug = match[1];
        console.log(`   ✓ Company slug: ${slug}`);
        const apiUrl = `https://api.lever.co/v0/postings/${slug}?mode=json`;
        console.log(`   API URL: ${apiUrl}`);
        try {
          const apiResponse = await fetchUrl(apiUrl);
          if (apiResponse.statusCode === 200) {
            const jobs = JSON.parse(apiResponse.data);
            console.log(`   ✓ API accessible, found ${Array.isArray(jobs) ? jobs.length : 0} jobs`);
          }
        } catch (e) {
          console.log(`   ✗ API not accessible: ${e.message}`);
        }
      }
    } else {
      console.log('   ✗ Lever not detected');
    }

    // Check for JSON-LD
    console.log('\n4. Checking for JSON-LD structured data...');
    const jsonLdMatches = html.match(/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi);
    if (jsonLdMatches) {
      console.log(`   ✓ Found ${jsonLdMatches.length} JSON-LD script(s)`);
      let jobPostingCount = 0;
      for (const match of jsonLdMatches) {
        const content = match.replace(/<script[^>]*>/, '').replace(/<\/script>/, '');
        try {
          const data = JSON.parse(content);
          if (hasJobPosting(data)) {
            jobPostingCount++;
          }
        } catch (e) {
          // Not valid JSON
        }
      }
      if (jobPostingCount > 0) {
        console.log(`   ✓ Found ${jobPostingCount} JSON-LD script(s) with JobPosting`);
      }
    } else {
      console.log('   ✗ No JSON-LD found');
    }

    // Check for custom JSON endpoints
    console.log('\n5. Checking for custom JSON endpoints...');
    const jsonPatterns = [
      /["']([^"']*api[^"']*jobs[^"']*\.json)["']/gi,
      /["']([^"']*jobs[^"']*api[^"']*\.json)["']/gi,
    ];
    const endpoints = new Set();
    for (const pattern of jsonPatterns) {
      const matches = html.matchAll(pattern);
      for (const match of matches) {
        if (match[1]) {
          endpoints.add(match[1]);
        }
      }
    }
    if (endpoints.size > 0) {
      console.log(`   ✓ Found ${endpoints.size} potential JSON endpoint(s):`);
      Array.from(endpoints).slice(0, 5).forEach(endpoint => {
        console.log(`     - ${endpoint}`);
      });
    } else {
      console.log('   ✗ No custom JSON endpoints found');
    }

    console.log('\n=== Summary ===');
    console.log('API detection test completed');

  } catch (error) {
    console.error('Error:', error.message);
    throw error;
  }
}

function hasJobPosting(data) {
  if (typeof data !== 'object' || data === null) return false;
  if (Array.isArray(data)) {
    return data.some(item => hasJobPosting(item));
  }
  if (data['@type'] === 'JobPosting') return true;
  return Object.values(data).some(value => 
    typeof value === 'object' && hasJobPosting(value)
  );
}

// Run test
const url = process.argv[2] || 'https://example.com/careers';
testApiDetection(url)
  .then(() => {
    console.log('\nTest completed successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\nTest failed:', error);
    process.exit(1);
  });

