// Synthetic end-to-end acceptance. Run by CI against the built browser package.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn,execFileSync}=require('node:child_process');
(async()=>{
 const output=fs.mkdtempSync('/tmp/options-flow-');
 const server=spawn('python3',['-u','-m','http.server','0','--bind','127.0.0.1','--directory',path.resolve('out')]);
 let browser;
 try{
  const url=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Server timeout')),10000);server.stdout.on('data',d=>{const m=String(d).match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0]);}});server.on('error',reject);});
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(90000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.doesNotMatch(await page.locator('body').innerText(), /\p{Script=Han}/u);
  await page.getByRole('button',{name:'Try an example',exact:true}).click();
  await page.locator('#results').waitFor({state:'visible'});
  assert.equal(await page.locator('#value').innerText(),'571.52');
  assert.equal(await page.locator('#greek-rows tr').count(),5);
  await page.getByRole('combobox',{name:'Example',exact:true}).selectOption('counterexample');
  await page.getByRole('button',{name:'Try an example',exact:true}).click();
  await page.locator('#results').waitFor({state:'visible'});
  assert.match(await page.locator('#approx-note').innerText(),/295.00.*-487.35.*782.35/);
  async function save(selector,name){const pending=page.waitForEvent('download');await page.locator(selector).click();const d=await pending;const file=path.join(output,name);await d.saveAs(file);assert.equal(await d.failure(),null);return file;}
  const file=await save('#download-json','counterexample.json');
  const report=await save('#download-html','report.html');
  const exported=JSON.parse(fs.readFileSync(file));
  const py="import json,sys; from options_risk.scenarios import analyse; q=json.load(open(sys.argv[1])); print(json.dumps(analyse(q['request'])))";
  const expected=JSON.parse(execFileSync('python3',['-c',py,file],{encoding:'utf8'}));
  let numeric=0;
  function parity(a,b){if(typeof a==='number'){assert(Math.abs(a-b)<=1e-10+1e-8*Math.abs(b));numeric++;}else if(a&&typeof a==='object'){assert.deepEqual(Object.keys(a),Object.keys(b));Object.keys(a).forEach(k=>parity(a[k],b[k]));}else assert.equal(a,b);}
  parity(exported.result,expected);
  const html=fs.readFileSync(report,'utf8');assert.doesNotMatch(html,/\p{Script=Han}/u);assert.match(html,/Annual vol/);assert.match(html,/1.0000%/);assert.match(html,/currency per 1 vol percentage point/);assert.match(html,/not VaR/);
  const reportPage=await browser.newPage();await reportPage.goto('file://'+report);assert(await reportPage.getByRole('heading',{name:'Portfolio sensitivities'}).isVisible());await reportPage.close();
  await page.getByRole('spinbutton',{name:'Spot price',exact:true}).fill('101');assert(await page.locator('#results').isHidden());assert.equal(await page.locator('#download-json').getAttribute('href'),null);assert.match(await page.locator('#case-note').innerText(),/changed/);
  await page.getByRole('button',{name:'Enter your positions',exact:true}).click();assert.equal(await page.locator('[name=spot]').inputValue(),'');assert.equal(await page.locator('#positions tbody tr').count(),1);
  const bad=path.join(output,'bad.json');fs.writeFileSync(bad,'{"positions":[]}');await page.locator('#file').setInputFiles(bad);assert(await page.locator('#error').isVisible());
  // Imported file is generated separately from the UI fixture.
  const custom={...exported.request,underlying:'CUSTOM_SYNTHETIC',spot:100,positions:[{id:'external-call',kind:'call',style:'european',strike:100,expiry:'2026-10-29',quantity:2,multiplier:100,volatility:.2}],scenarios:[{name:'unchanged',days:0,spot_return:0,vol_change:0},{name:'up 1%',days:0,spot_return:.01,vol_change:0}]};
  const customPath=path.join(output,'custom.json');fs.writeFileSync(customPath,JSON.stringify(custom));await page.locator('#file').setInputFiles(customPath);assert.match(await page.locator('#case-note').innerText(),/Custom/);assert(await page.locator('#error').isHidden());
  await page.getByRole('button',{name:'Calculate portfolio',exact:true}).click();await page.locator('#results').waitFor({state:'visible'});const customExport=await save('#download-json','custom-result.json');const c=JSON.parse(fs.readFileSync(customExport));parity(c.result,JSON.parse(execFileSync('python3',['-c',py,customExport],{encoding:'utf8'})));
  await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify({numeric_fields_compared:numeric,example:true,counterexample:true,custom_import:true,invalid_recovery:true,report_saved_and_read:true,stale_export_revoked:true,desktop:true,mobile:true,errors},null,2));
  fs.mkdirSync('outputs',{recursive:true});fs.cpSync(output,'outputs/browser-flow',{recursive:true});console.log('Browser flow passed:',numeric,'numeric fields');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1});
