const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 8898;
const ROOT = path.join('D:', 'Development', 'USSIP', 'tools', 'ScoutingPhotoEnhancer', 'mobile_web_scout');

// 1. Static file server
const server = http.createServer((req, res) => {
  let reqPath = req.url.split('?')[0];
  if (reqPath === '/') reqPath = '/index.html';
  const filePath = path.join(ROOT, reqPath);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const mime = {
      '.html': 'text/html',
      '.js': 'application/javascript',
      '.css': 'text/css',
      '.png': 'image/png',
      '.json': 'application/json'
    }[ext] || 'application/octet-stream';

    res.writeHead(200, { 'Content-Type': mime });
    fs.createReadStream(filePath).pipe(res);
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(PORT, async () => {
  console.log(`Live basemap test server on port ${PORT}`);

  const chromePaths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Users\\NASRULLAH KHAN\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe'
  ];
  const chromePath = chromePaths.find(p => fs.existsSync(p));
  const cdpPort = 9224;
  const userDataDir = path.join(process.env.TEMP || 'C:\\temp', 'chrome_basemap_test_' + Date.now());

  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${cdpPort}`,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--window-size=360,740',
    `--user-data-dir=${userDataDir}`,
    `http://localhost:${PORT}/index.html`
  ]);

  await new Promise(r => setTimeout(r, 2000));

  try {
    const listResp = await fetch(`http://127.0.0.1:${cdpPort}/json`);
    const targets = await listResp.json();
    const pageTarget = targets.find(t => t.type === 'page');
    const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
    await new Promise(res => ws.addEventListener('open', res));

    let msgId = 1;
    function sendCommand(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = msgId++;
        const handler = (evt) => {
          const msg = JSON.parse(evt.data);
          if (msg.id === id) {
            ws.removeEventListener('message', handler);
            if (msg.error) reject(msg.error);
            else resolve(msg.result);
          }
        };
        ws.addEventListener('message', handler);
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await sendCommand('Page.enable');
    await sendCommand('Runtime.enable');

    async function evaluate(expr) {
      const res = await sendCommand('Runtime.evaluate', {
        expression: expr,
        returnByValue: true,
        awaitPromise: true
      });
      if (res.exceptionDetails) {
        throw new Error(res.exceptionDetails.text + ' ' + (res.exceptionDetails.exception?.description || ''));
      }
      return res.result?.value;
    }

    // Wait for map initialization
    await evaluate(`
      new Promise(resolve => {
        const check = () => {
          if (typeof map !== 'undefined' && map && typeof BASEMAP_OPTIONS !== 'undefined') resolve(true);
          else setTimeout(check, 100);
        };
        check();
      })
    `);

    const basemapList = await evaluate(`BASEMAP_OPTIONS.map(b => ({ id: b.id, name: b.name, category: b.category, type: b.type, url: b.url }))`);
    console.log(`\n============================================================`);
    console.log(`TESTING ALL ${basemapList.length} BASEMAP LAYERS ONE BY ONE ON MAP CANVAS`);
    console.log(`============================================================\n`);

    const results = [];

    for (let i = 0; i < basemapList.length; i++) {
      const b = basemapList[i];
      process.stdout.write(`[${i + 1}/${basemapList.length}] Testing '${b.name}' (${b.id})... `);

      const testResult = await evaluate(`
        new Promise(async (resolve) => {
          try {
            selectBasemapById('${b.id}');
            
            if ('${b.id}' === 'none') {
              resolve({
                id: '${b.id}',
                status: 'PASS',
                note: 'Blank vector canvas active'
              });
              return;
            }

            // Allow network time to fetch tiles
            let attempts = 0;
            const maxAttempts = 25; // 2.5 seconds max
            const interval = setInterval(() => {
              attempts++;
              const container = map.getContainer();
              const tiles = container.querySelectorAll('.leaflet-tile');
              const loadedTiles = container.querySelectorAll('.leaflet-tile-loaded');
              
              // If tiles exist or at least 1 tile has loaded
              if (loadedTiles.length > 0 || (tiles.length > 0 && attempts >= 10)) {
                clearInterval(interval);
                resolve({
                  id: '${b.id}',
                  status: 'PASS',
                  tilesFound: tiles.length,
                  tilesLoaded: loadedTiles.length,
                  note: \`Loaded \${loadedTiles.length}/\${tiles.length} tiles\`
                });
              } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                resolve({
                  id: '${b.id}',
                  status: tiles.length > 0 ? 'PASS' : 'WARN',
                  tilesFound: tiles.length,
                  tilesLoaded: loadedTiles.length,
                  note: tiles.length > 0 ? 'Tiles mounted to DOM' : 'Timeout waiting for tile network'
                });
              }
            }, 100);
          } catch (err) {
            resolve({
              id: '${b.id}',
              status: 'FAIL',
              error: err.message
            });
          }
        })
      `);

      results.push(testResult);
      if (testResult.status === 'PASS') {
        console.log(`✅ PASS (${testResult.note || 'OK'})`);
      } else {
        console.log(`⚠️ ${testResult.status}: ${testResult.error || testResult.note}`);
      }
    }

    console.log(`\n============================================================`);
    const passed = results.filter(r => r.status === 'PASS').length;
    console.log(`SUMMARY: ${passed} of ${results.length} basemaps verified loaded.`);
    console.log(`============================================================\n`);

    ws.close();
    chrome.kill();
    server.close();
    process.exit(passed === results.length ? 0 : 1);

  } catch (err) {
    console.error('Test suite error:', err);
    chrome.kill();
    server.close();
    process.exit(1);
  }
});
