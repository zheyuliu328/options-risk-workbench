// Original synthetic browser task, with native replay and independent expiry payoff.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process');
(async()=>{
 const output=fs.mkdtempSync('/tmp/options-grid-flow-');
 const server=spawn('python3',['-u','-m','http.server','0','--bind','127.0.0.1','--directory',path.resolve('out')]);
 let browser;
 try{
 const url=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Server timeout')),10000);server.stdout.on('data',d=>{const m=String(d).match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0])}});server.on('error',reject)});
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(90000);
 const errors=[],external=[],uploads=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(url))external.push(r.url());if(r.method()==='POST')uploads.push(r.url())});
 await page.goto(url);await page.locator('#grid-open').click();
 await page.locator('#grid-example').click();await page.locator('#grid-results').waitFor({state:'visible'});
 assert.equal(await page.locator('#grid-rows tr').count(),21);
 async function save(selector,name){const pending=page.waitForEvent('download');await page.locator(selector).click();const d=await pending;const file=path.join(output,name);await d.saveAs(file);assert.equal(await d.failure(),null);return file}
 const request=await save('#grid-request','request.json'),result=await save('#grid-json','results.json'),report=await save('#grid-html','report.html');
 const native=JSON.parse(execFileSync('python3',['-c',"import json,sys;from options_risk.grid import review_grid;print(json.dumps(review_grid(json.load(open(sys.argv[1])))))",request],{encoding:'utf8'}));
 let numbers=0;function parity(a,b){if(typeof a==='number'){assert(Math.abs(a-b)<=1e-10+1e-8*Math.abs(b));numbers++}else if(a&&typeof a==='object'){assert.deepEqual(Object.keys(a),Object.keys(b));Object.keys(a).forEach(k=>parity(a[k],b[k]))}else assert.equal(a,b)}
 parity(JSON.parse(fs.readFileSync(result)),native);assert.match(fs.readFileSync(report,'utf8'),/Sampled extremes/);
 // A custom scenario is outside this task; it must not contaminate the grid.
 await page.getByLabel('Elapsed calendar days',{exact:true}).fill('-1');assert(await page.locator('#grid-results').isHidden());assert.equal(await page.locator('#grid-json').getAttribute('href'),null);
 await page.locator('#grid-run').click();await page.locator('#grid-results').waitFor({state:'visible'});
 await page.locator('#grid-days').fill('31');assert(await page.locator('#grid-results').isHidden());await page.locator('#grid-run').click();await page.locator('#error').waitFor({state:'visible'});assert.match(await page.locator('#error').innerText(),/expiry/);assert.equal(await page.locator('#grid-html').getAttribute('href'),null);
 await page.locator('#grid-expiry').click();await page.locator('#grid-results').waitFor({state:'visible'});
 const expired=JSON.parse(fs.readFileSync(await save('#grid-json','expiry.json')));for(const row of expired.rows)assert(Math.abs(row.value-100*Math.abs(row.spot-100))<1e-8);
 assert(expired.rows.find(r=>r.spot_return===0).change<0);assert(expired.largest_abs_residual>1);
 // Fresh own-input file, asymmetric range and negative quantity.
 const own=JSON.parse(fs.readFileSync(request));own.portfolio.positions[0].quantity=-3;own.grid.lower_return=-.13;own.grid.upper_return=1/3;own.portfolio.rate=1/30;own.portfolio.positions[0].volatility=1/3;own.source_note='<script>Original invented own-input case</script>';
 const ownPath=path.join(output,'own.json');fs.writeFileSync(ownPath,JSON.stringify(own));await page.locator('#grid-file').setInputFiles(ownPath);await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Range request imported'));
 assert.equal(await page.locator('#positions [data-key=quantity]').first().inputValue(),'-3');assert.equal(await page.locator('#scenarios tbody tr').count(),1);
 await page.locator('#grid-run').click();await page.locator('#grid-results').waitFor({state:'visible'});assert.equal(await page.locator('#grid-rows tr').count(),22);
 const ownResult=JSON.parse(fs.readFileSync(await save('#grid-json','own-results.json')));assert.deepEqual(ownResult.request,own);const ownNative=JSON.parse(execFileSync('python3',['-c',"import json,sys;from options_risk.grid import review_grid;print(json.dumps(review_grid(json.load(open(sys.argv[1])))))",ownPath],{encoding:'utf8'}));parity(ownResult,ownNative);
 assert.match(fs.readFileSync(await save('#grid-html','own-report.html'),'utf8'),/&lt;script&gt;/);
 // Importing a malformed request must preserve inputs but clear conclusions.
 const bad=path.join(output,'bad.json');fs.writeFileSync(bad,fs.readFileSync(ownPath,'utf8').replace('"schema_version":1','"schema_version":1,"schema_version":1'));
 await page.locator('#grid-file').setInputFiles(bad);await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Range import failed'));
 assert.match(await page.locator('#error').innerText(),/Duplicate/);assert(await page.locator('#grid-results').isHidden());assert.equal(await page.locator('#grid-json').getAttribute('href'),null);assert.equal(await page.locator('#positions [data-key=quantity]').first().inputValue(),'-3');
 await page.locator('#grid-file').setInputFiles(request);await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Range request imported'));await page.locator('#grid-run').click();await page.locator('#grid-results').waitFor({state:'visible'});
 const replay=JSON.parse(fs.readFileSync(await save('#grid-json','replayed.json')));parity(replay,native);
 await page.screenshot({path:path.join(output,'desktop.png'),fullPage:false});await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await page.locator('#grid-chart').evaluate(e=>e.scrollWidth>e.clientWidth));await page.screenshot({path:path.join(output,'narrow.png'),fullPage:false});
 // Cancel a fresh runtime before it completes, then recover.
 await page.reload();await page.locator('#grid-open').click();await page.locator('#grid-example').click();await page.locator('#cancel').click();assert(await page.locator('#grid-results').isHidden());assert(await page.locator('#grid-inputs').isEnabled());await page.locator('#grid-run').click();await page.locator('#grid-results').waitFor({state:'visible'});
 await page.locator('#grid-points').fill('');await page.locator('#diagnostic-panel summary').click();await page.locator('#diagnostic-position').selectOption('long-call');await page.locator('#diagnostic-run').click();await page.locator('#diagnostic-results').waitFor({state:'visible'});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(uploads,[]);
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({numbers,external,uploads,errors,nativeParity:true,expiryPayoff:true,importRecovery:true,cancelRecovery:true}));fs.mkdirSync('outputs/browser-grid',{recursive:true});fs.cpSync(output,'outputs/browser-grid',{recursive:true});console.log(JSON.stringify({output,numbers,status:'passed'}));
 }finally{if(browser)await browser.close();server.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
