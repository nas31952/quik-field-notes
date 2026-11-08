const fs = require('fs');

const content = fs.readFileSync('D:/Development/USSIP/tools/ScoutingPhotoEnhancer/mobile_web_scout/index.html', 'utf8');
const match = content.match(/const BASEMAP_OPTIONS = (\[[\s\S]*?\]);/);
const options = eval(match[1]);

// Test tile coordinate in Saudi Arabia / universal scouting area (Lat ~24.7, Lon ~46.7, Zoom 8)
// Tile XY at z=8: x=161, y=107
const z = 8, x = 161, y = 107;

async function checkAllTileEndpoints() {
  console.log(`Checking direct tile network endpoints for all 27 basemap layers...\n`);
  let successCount = 0;

  for (let i = 0; i < options.length; i++) {
    const opt = options[i];
    if (opt.id === 'none') {
      console.log(`[${i + 1}/${options.length}] ${opt.id}: Blank Vector Canvas (N/A) -> OK`);
      successCount++;
      continue;
    }

    let url = opt.url || opt.baseLayerUrl;
    if (url.includes('{s}')) url = url.replace('{s}', 'a');
    if (url.includes('{r}')) url = url.replace('{r}', '');
    url = url.replace('{z}', z).replace('{x}', x).replace('{y}', y);

    try {
      const resp = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      });
      const contentType = resp.headers.get('content-type') || '';
      const isImg = contentType.includes('image') || contentType.includes('octet-stream');
      if (resp.ok && isImg) {
        console.log(`[${i + 1}/${options.length}] ✅ ${opt.id}: HTTP ${resp.status} (${contentType}) -> SUCCESS`);
        successCount++;
      } else {
        console.log(`[${i + 1}/${options.length}] ⚠️ ${opt.id}: HTTP ${resp.status} (${contentType}) [${url}]`);
      }
    } catch (err) {
      console.log(`[${i + 1}/${options.length}] ❌ ${opt.id}: ${err.message}`);
    }
  }

  console.log(`\n============================================================`);
  console.log(`TILE NETWORK VERIFICATION: ${successCount} of ${options.length} OK.`);
  console.log(`============================================================`);
}

checkAllTileEndpoints();
