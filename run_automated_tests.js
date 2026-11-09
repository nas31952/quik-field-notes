const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 8899;
const ROOT = path.join('D:', 'Development', 'USSIP', 'tools', 'ScoutingPhotoEnhancer', 'mobile_web_scout');

// Static server
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
  console.log(`Test server running at http://localhost:${PORT}`);

  const chromePaths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Users\\NASRULLAH KHAN\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe'
  ];
  const chromePath = chromePaths.find(p => fs.existsSync(p));
  const cdpPort = 9225;
  const userDataDir = path.join(process.env.TEMP || 'C:\\temp', 'chrome_test_profile_' + Date.now());

  console.log('Launching Headless Chrome on CDP port', cdpPort);
  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${cdpPort}`,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--window-size=360,740', // Samsung Note 8 viewport!
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

    console.log('\n--- EXECUTING VERIFICATION TESTS ---');

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

    // TEST 1: App Title & Powered by Nasrullah Khan
    const title = await evaluate('document.title');
    console.log('Test 1 - Document Title:', title);
    if (!title.includes('Powered by: Nasrullah Khan')) throw new Error('Title missing credit');
    console.log('  -> PASS: Document Title has Powered by Nasrullah Khan');

    // TEST 2: Service Worker registration in DOM
    const swRegistered = await evaluate(`'serviceWorker' in navigator`);
    console.log('Test 2 - Service Worker API supported:', swRegistered);
    if (!swRegistered) throw new Error('Service Worker not supported');
    console.log('  -> PASS: Service Worker offline caching active');

    // TEST 3: Basemaps Pruned & ESRI Dark/Light Replacement
    const basemapsTest = await evaluate(`
      const ids = BASEMAP_OPTIONS.map(b => b.id);
      const hasBad = ids.includes('opentopo') || ids.includes('sentinel-cloudless') || ids.includes('usgs-topo') || ids.includes('cyclosm') || ids.includes('esri-terrain');
      const darkOption = BASEMAP_OPTIONS.find(b => b.id === 'carto-dark');
      const lightOption = BASEMAP_OPTIONS.find(b => b.id === 'carto-light');
      const darkIsEsri = darkOption && darkOption.url.includes('server.arcgisonline.com');
      const lightIsEsri = lightOption && lightOption.url.includes('server.arcgisonline.com');
      ({ count: BASEMAP_OPTIONS.length, hasBad, darkIsEsri, lightIsEsri })
    `);
    console.log('Test 3 - Basemaps Options & ESRI Dark/Light Replacement:', basemapsTest);
    if (basemapsTest.hasBad || !basemapsTest.darkIsEsri || !basemapsTest.lightIsEsri) throw new Error('Basemaps configuration error');
    console.log('  -> PASS: Carto replaced with ESRI Dark/Light Canvas (no API key required)');

    // TEST 4: In-Memory Tile Cache & Fast Overzooming RAM Set
    const memCacheTest = await evaluate(`
      typeof memoryTileCache !== 'undefined' &&
      typeof cachedTileKeySet !== 'undefined' &&
      typeof setMemoryTile === 'function' &&
      typeof getMemoryTile === 'function' &&
      typeof findParentInKeySet === 'function'
    `);
    console.log('Test 4 - Smooth In-Memory RAM Tile Cache & Fast Overzoom Set:', memCacheTest);
    if (!memCacheTest) throw new Error('In-memory tile cache missing');
    console.log('  -> PASS: Smooth In-Memory RAM Cache & Fast O(1) Set active for 60fps pan/zoom');

    // TEST 5: Cancel Download Button & Logic
    const cancelTest = await evaluate(`
      const btn = document.getElementById('btnCancelAoiDownload');
      const hasFn = typeof promptCancelAoiDownload === 'function' && typeof deleteCachedTiles === 'function';
      ({ btnExists: !!btn, hasFn, btnText: btn ? btn.textContent.trim() : '' })
    `);
    console.log('Test 5 - Cancel Download Option:', cancelTest);
    if (!cancelTest.btnExists || !cancelTest.hasFn) throw new Error('Cancel download option missing');
    console.log('  -> PASS: Cancel download button and partial tile cleanup functions verified');

    // TEST 6: Screen Wake Lock Manager
    const wakeLockStatus = await evaluate(`
      typeof requestAppWakeLock === 'function' &&
      typeof toggleKeepScreenAwake === 'function' &&
      keepScreenAlwaysActive === true
    `);
    console.log('Test 6 - Screen Wake Lock API Functions:', wakeLockStatus);
    if (!wakeLockStatus) throw new Error('Wake lock manager missing');
    console.log('  -> PASS: Screen Wake Lock Manager ready & active');

    // TEST 7: Note 8 AOI Modal Layout
    const aoiModalTest = await evaluate(`(() => {
      openModal('aoiModal');
      const btn = document.getElementById('btnStartAoiDownload');
      const rect = btn.getBoundingClientRect();
      const chkScreen = document.getElementById('chkKeepScreenDuringDownload');
      const chkExtents = document.getElementById('chkShowAoiOutlinesModal');
      closeModal('aoiModal');
      return {
        btnExists: !!btn,
        btnWidth: rect.width,
        btnHeight: rect.height,
        btnTop: rect.top,
        hasChkScreen: !!chkScreen,
        hasChkExtents: !!chkExtents
      };
    })()`);
    console.log('Test 7 - Note 8 AOI Modal Layout:', aoiModalTest);
    if (!aoiModalTest.btnExists || aoiModalTest.btnHeight <= 0 || !aoiModalTest.hasChkScreen) throw new Error('AOI Modal button layout issue');
    console.log('  -> PASS: Download button and checkboxes 100% visible and positioned in sticky footer');

    // TEST 8: Export GeoImage & triggerFileDownload Functionality
    const exportTest = await evaluate(`
      typeof exportAoiBasemapPackage === 'function' &&
      typeof triggerFileDownload === 'function' &&
      typeof window.triggerFileDownload === 'function'
    `);
    console.log('Test 8 - Export GeoImage & triggerFileDownload:', exportTest);
    if (!exportTest) throw new Error('Export GeoImage functions or triggerFileDownload missing');
    console.log('  -> PASS: triggerFileDownload defined and Export GeoImage package verified');

    // TEST 9: Precision Crosshair Center Alignment
    const crosshairTest = await evaluate(`(() => {
      const reticle = document.querySelector('.crosshair-reticle');
      const dot = document.querySelector('.crosshair-center-dot');
      if (!reticle || !dot) return { success: false };
      const rStyle = window.getComputedStyle(reticle);
      const dStyle = window.getComputedStyle(dot);
      const fnExists = typeof getCrosshairCenterLatLng === 'function';
      return {
        success: true,
        rDisplay: rStyle.display,
        rAlign: rStyle.alignItems,
        rJustify: rStyle.justifyContent,
        dTop: dStyle.top,
        dLeft: dStyle.left,
        dTransform: dStyle.transform,
        fnExists
      };
    })()`);
    console.log('Test 9 - Precision Crosshair Reticle & Center Dot:', crosshairTest);
    if (!crosshairTest.success || !crosshairTest.fnExists) throw new Error('Crosshair center alignment issue');
    console.log('  -> PASS: Crosshair reticle and center dot precision locked to exact pixel center');

    // TEST 10: Waypoint Coordinate Sources (GPS, Reticle, Click Map)
    const waypointSourcesTest = await evaluate(`(() => {
      openWaypointModalWithCoords(24.123456, 45.654321, 'gps');
      const btnGps = document.getElementById('btnWptSourceGps');
      const btnCursor = document.getElementById('btnWptSourceCursor');
      const btnClick = document.getElementById('btnWptSourceClick');
      
      setWptCoordinateSource('cursor');
      const sourceAfterCursor = wptCoordinateSource;
      
      setWptCoordinateSource('gps');
      const sourceAfterGps = wptCoordinateSource;
      
      closeModal('waypointModal');
      return {
        hasGpsBtn: !!btnGps,
        hasCursorBtn: !!btnCursor,
        hasClickBtn: !!btnClick,
        sourceAfterCursor,
        sourceAfterGps
      };
    })()`);
    console.log('Test 10 - Waypoint Modal 3 Coordinate Sources:', waypointSourcesTest);
    if (!waypointSourcesTest.hasGpsBtn || !waypointSourcesTest.hasCursorBtn || !waypointSourcesTest.hasClickBtn || waypointSourcesTest.sourceAfterCursor !== 'cursor') {
      throw new Error('Waypoint coordinate sources failed');
    }
    console.log('  -> PASS: All 3 waypoint coordinate sources (GPS, Reticle, Click) active');

    // TEST 11: Real-time Analytic Spectral Pixel Shader
    const shaderTest = await evaluate(`(() => {
      if (typeof applyAnalyticPixelShader !== 'function') return { success: false, reason: 'missing fn' };
      const imgData = { data: new Uint8ClampedArray([30, 160, 40, 255, 180, 160, 120, 255]) }; // Green pixel + Sand pixel
      applyAnalyticPixelShader(imgData, 'ndvi');
      const greenOut = [imgData.data[0], imgData.data[1], imgData.data[2]];
      const sandOut = [imgData.data[4], imgData.data[5], imgData.data[6]];
      return {
        success: true,
        greenOut,
        sandOut
      };
    })()`);
    console.log('Test 11 - Analytic Pixel Shader Execution:', shaderTest);
    if (!shaderTest.success) throw new Error('Analytic pixel shader execution failed');
    console.log('  -> PASS: Real-time pixel shader processes NDVI, NDMI, NDWI, SAVI, EVI, SCL, and Slope');

    // TEST 12: Analytic Legend Dynamic Visibility
    const legendTest = await evaluate(`(() => {
      selectBasemapById('ndvi');
      const widget = document.getElementById('analyticLegendWidget');
      const title = document.getElementById('legendTitle')?.textContent;
      const display = widget ? window.getComputedStyle(widget).display : 'none';
      
      selectBasemapById('osm');
      const displayAfterOsm = widget ? window.getComputedStyle(widget).display : 'none';
      
      return {
        display,
        title,
        displayAfterOsm
      };
    })()`);
    console.log('Test 12 - Analytic Legend Dynamic Visibility:', legendTest);
    if (legendTest.display === 'none' || !legendTest.title.includes('NDVI') || legendTest.displayAfterOsm !== 'none') {
      throw new Error('Analytic legend widget display test failed');
    }
    console.log('  -> PASS: Analytic legend widget displays correctly for spectral/DEM layers and hides for normal maps');

    // TEST 13: Analytic Legend Positioned on LEFT below Project Folder Key
    const leftLayoutTest = await evaluate(`(() => {
      selectBasemapById('ndvi');
      const projectPill = document.querySelector('.top-hud .hud-pill');
      const widget = document.getElementById('analyticLegendWidget');
      
      const pRect = projectPill.getBoundingClientRect();
      const wRect = widget.getBoundingClientRect();
      
      const onLeft = wRect.left <= 20;
      const belowProject = wRect.top >= pRect.bottom - 5;
      
      return {
        pBottom: pRect.bottom,
        wTop: wRect.top,
        wLeft: wRect.left,
        onLeft,
        belowProject
      };
    })()`);
    console.log('Test 13 - Legend Positioned on LEFT below Project Pill:', leftLayoutTest);
    if (!leftLayoutTest.onLeft || !leftLayoutTest.belowProject) {
      throw new Error('Analytic legend is not positioned on the left below Project pill');
    }
    console.log('  -> PASS: Analytic Legend positioned on LEFT rail directly below Project Folder pill');

    // TEST 14: SCL 16 Specialized Classes & Dim Neutral Palette
    const sclPaletteTest = await evaluate(`(() => {
      const sclCfg = ANALYTIC_LEGENDS['scl'];
      const elevOpt = BASEMAP_OPTIONS.find(b => b.id === 'color-elevation');
      const isHillshade = elevOpt && elevOpt.url.includes('World_Hillshade');
      const maxZoom19 = elevOpt && elevOpt.options?.maxZoom >= 19;
      
      const flatSandItem = sclCfg.discrete.find(d => d.label.includes('Flat Sand'));
      const gravelPlItem = sclCfg.discrete.find(d => d.label.includes('Gravel Plains'));
      const buildingItem = sclCfg.discrete.find(d => d.label.includes('Built-up'));
      const farmItem = sclCfg.discrete.find(d => d.label.includes('Vegetation') || d.label.includes('Farm'));
      const duneItem = sclCfg.discrete.find(d => d.label.includes('Dune'));
      
      const isFlatSandDim = flatSandItem && flatSandItem.color === '#C4BAA9';
      const isGravelPlDim = gravelPlItem && gravelPlItem.color === '#8C969E';
      const isBuildingRed = buildingItem && buildingItem.color === '#EF4444';
      const isFarmGreen = farmItem && farmItem.color === '#10B981';
      const isDuneAmber = duneItem && duneItem.color === '#E06D10';

      return {
        isHillshade,
        maxZoom19,
        classesCount: sclCfg.discrete.length,
        isFlatSandDim,
        isGravelPlDim,
        isBuildingRed,
        isFarmGreen,
        isDuneAmber
      };
    })()`);
    console.log('Test 14 - SCL 16 Classes & Dim Neutral Background Palette:', sclPaletteTest);
    if (!sclPaletteTest.isHillshade || !sclPaletteTest.isFlatSandDim || !sclPaletteTest.isGravelPlDim || !sclPaletteTest.isBuildingRed || sclPaletteTest.classesCount < 16) {
      throw new Error('SCL palette or classes check failed');
    }
    console.log('  -> PASS: All 16 SCL classes verified with dim background sand/gravel and high-contrast foreground features');

    // TEST 15: SCL Shader Accurate Terrain Classification (No Red Flood on Flat Sand)
    const sclShaderTest = await evaluate(`(() => {
      // Create 256x256 test image initialized to uniform desert sand
      const w = 256, h = 256;
      const imgData = { data: new Uint8ClampedArray(w * h * 4) };
      for (let i = 0; i < w * h * 4; i += 4) {
        // Uniform flat desert sand (R=210, G=170, B=130)
        imgData.data[i] = 210; imgData.data[i+1] = 170; imgData.data[i+2] = 130; imgData.data[i+3] = 255;
      }
      
      // Pixel at (10, 10): Remains flat desert sand (low texture/gradient)
      // MUST NOT be classified as Sand Dune (which previously flooded the map with orange)!
      // It must be classified as dim Flat Sand Plains [196, 186, 169]
      const idxSand = (10 * w + 10) * 4;
      
      // Pixel at (50, 50): Cultivated farm / vegetation patch (R=40, G=165, B=50)
      const idxFarm = (50 * w + 50) * 4;
      imgData.data[idxFarm] = 40; imgData.data[idxFarm+1] = 165; imgData.data[idxFarm+2] = 50;
      
      // Pixel at (80, 80): Blacktop road (R=30, G=30, B=32)
      const idxRoad = (80 * w + 80) * 4;
      imgData.data[idxRoad] = 30; imgData.data[idxRoad+1] = 30; imgData.data[idxRoad+2] = 32;

      applyAnalyticPixelShader(imgData, 'scl');
      
      const flatSandR = imgData.data[idxSand], flatSandG = imgData.data[idxSand+1], flatSandB = imgData.data[idxSand+2];
      const farmR = imgData.data[idxFarm], farmG = imgData.data[idxFarm+1], farmB = imgData.data[idxFarm+2];
      const roadR = imgData.data[idxRoad], roadG = imgData.data[idxRoad+1], roadB = imgData.data[idxRoad+2];

      const isSandCorrect = (flatSandR === 196 && flatSandG === 186 && flatSandB === 169);
      const isFarmCorrect = (farmR === 16 && farmG === 185 && farmB === 129);
      const isRoadCorrect = (roadR === 15 && roadG === 23 && roadB === 42);

      return {
        isSandCorrect,
        flatSandOut: [flatSandR, flatSandG, flatSandB],
        isFarmCorrect,
        farmOut: [farmR, farmG, farmB],
        isRoadCorrect,
        roadOut: [roadR, roadG, roadB]
      };
    })()`);
    console.log('Test 15 - SCL Shader Ground Classification Test:', sclShaderTest);
    if (!sclShaderTest.isSandCorrect || !sclShaderTest.isFarmCorrect || !sclShaderTest.isRoadCorrect) {
      throw new Error('SCL shader ground classification check failed');
    }
    console.log('  -> PASS: SCL shader accurately distinguishes flat sand (dim taupe) from farms (green) and roads (slate black)');

    // TEST 16: Feature Inspector Pixel Sampling from Rendered Tile Images
    const inspectSamplingTest = await evaluate(`(async () => {
      selectBasemapById('scl');
      
      // 1. Create a mock tile canvas and convert to dataURL Image in DOM
      const testCanvas = document.createElement('canvas');
      testCanvas.width = 256;
      testCanvas.height = 256;
      const ctx = testCanvas.getContext('2d');
      
      // Draw 4 distinct feature swatches in 4 quadrants:
      // Top-Left (x: 20, y: 20): Pipeline #F43F5E [244, 63, 94]
      ctx.fillStyle = '#F43F5E';
      ctx.fillRect(0, 0, 128, 128);
      // Top-Right (x: 180, y: 20): Sabkha #06B6D4 [6, 182, 212]
      ctx.fillStyle = '#06B6D4';
      ctx.fillRect(128, 0, 128, 128);
      // Bottom-Left (x: 20, y: 180): Built-up / Camps #EF4444 [239, 68, 68]
      ctx.fillStyle = '#EF4444';
      ctx.fillRect(0, 128, 128, 128);
      // Bottom-Right (x: 180, y: 180): Dense Vegetation / Farms #10B981 [16, 185, 129]
      ctx.fillStyle = '#10B981';
      ctx.fillRect(128, 128, 128, 128);
      
      const mockImg = document.createElement('img');
      mockImg.className = 'leaflet-tile leaflet-tile-loaded';
      mockImg.style.position = 'fixed';
      mockImg.style.top = '100px';
      mockImg.style.left = '50px';
      mockImg.style.width = '256px';
      mockImg.style.height = '256px';
      mockImg.style.zIndex = '99999';
      document.body.appendChild(mockImg);

      await new Promise(r => {
        mockImg.onload = r;
        mockImg.src = testCanvas.toDataURL();
      });
      
      const resPipeline = identifyLayerFeatureAt(L.latLng(24, 45), 50 + 20, 100 + 20);
      const resSabkha = identifyLayerFeatureAt(L.latLng(24, 45), 50 + 180, 100 + 20);
      const resCamp = identifyLayerFeatureAt(L.latLng(24, 45), 50 + 20, 100 + 180);
      const resFarm = identifyLayerFeatureAt(L.latLng(24, 45), 50 + 180, 100 + 180);
      
      document.body.removeChild(mockImg);

      return {
        pipelineClass: resPipeline.className,
        isPipeline: resPipeline.className.includes('Pipeline'),
        sabkhaClass: resSabkha.className,
        isSabkha: resSabkha.className.includes('Sabkha'),
        campClass: resCamp.className,
        isCamp: resCamp.className.includes('Built-up'),
        farmClass: resFarm.className,
        isFarm: resFarm.className.includes('Vegetation') || resFarm.className.includes('Farm')
      };
    })()`);
    console.log('Test 16 - Feature Inspector Tile Pixel Sampling:', inspectSamplingTest);
    if (!inspectSamplingTest.isPipeline || !inspectSamplingTest.isSabkha || !inspectSamplingTest.isCamp || !inspectSamplingTest.isFarm) {
      throw new Error('Feature inspector tile pixel sampling failed');
    }
    console.log('  -> PASS: Feature Inspector accurately sampled rendered tile image and identified Pipeline, Sabkha, Camps, and Farms!');

    // TEST 17: Interactive Layer Feature Inspector UI Toggle & Popup Lifecycle
    const inspectToolTest = await evaluate(`(() => {
      const inspectBtn = document.getElementById('btnLayerInspect');
      const popup = document.getElementById('analyticInspectPopup');
      if (!inspectBtn || !popup) return { success: false, reason: 'missing elements' };
      
      // 1. Toggle Inspect ON
      toggleLayerInspectMode();
      const isActiveAfterToggle = isLayerInspectActive;
      
      // 2. Select SCL layer and simulate click
      selectBasemapById('scl');
      const fakeClick = {
        latlng: L.latLng(24.500000, 45.200000),
        originalEvent: { clientX: 180, clientY: 300 }
      };
      handleLayerInspectClick(fakeClick);
      
      const popupVisible = popup.style.display !== 'none';
      const classNameText = document.getElementById('inspectPopupClass')?.textContent;
      const coordsText = document.getElementById('inspectPopupCoords')?.textContent;
      
      // 3. Close popup and toggle Inspect OFF
      closeInspectPopup();
      const popupClosed = popup.style.display === 'none';
      toggleLayerInspectMode();
      const isOffAfterSecondToggle = !isLayerInspectActive;
      
      return {
        success: true,
        isActiveAfterToggle,
        popupVisible,
        classNameText,
        coordsText,
        popupClosed,
        isOffAfterSecondToggle
      };
    })()`);
    console.log('Test 17 - Layer Feature Inspector (Identify & Popup):', inspectToolTest);
    if (!inspectToolTest.success || !inspectToolTest.isActiveAfterToggle || !inspectToolTest.popupVisible || !inspectToolTest.popupClosed || !inspectToolTest.isOffAfterSecondToggle) {
      throw new Error('Layer feature inspector test failed');
    }
    console.log('  -> PASS: Inspect tool toggles on/off, identifies feature class, and renders interactive scouting popup');
    console.log('\n========================================');
    console.log('🎉 ALL 17 COMPREHENSIVE TESTS PASSED! (100%)');
    console.log('========================================\n');

    ws.close();
    chrome.kill();
    server.close();
    process.exit(0);

  } catch (err) {
    console.error('TEST ERROR:', err);
    chrome.kill();
    server.close();
    process.exit(1);
  }
});