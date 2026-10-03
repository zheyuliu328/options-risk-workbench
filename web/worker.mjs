import {loadPyodide} from './runtime/pyodide.mjs';
let runtime;
async function initialize(id){
 self.postMessage({id,progress:'Loading calculation components for the first run. Inputs are not uploaded.'});
 const build=await fetch('./build.json').then(r=>{if(!r.ok)throw Error('Unable to read component version');return r.json()});
 const bytes=new Uint8Array(await fetch('./engine.zip').then(r=>{if(!r.ok)throw Error('Calculation component download failed');return r.arrayBuffer()}));
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==build.engine_sha256)throw Error('Component version mismatch. Refresh the page.');
 const py=await loadPyodide({indexURL:new URL('./runtime/',self.location.href).href});
 py.unpackArchive(bytes,'zip',{extractDir:'/app'});
 py.runPython("import sys; sys.path.insert(0,'/app'); import json; from options_risk.scenarios import analyse; from options_risk.report import render; from options_risk.quotes import review_quotes, render_quote_review; from options_risk.diagnostics import diagnose, render as render_diagnostics; from options_risk.grid import review_grid, render_grid, plot_svg");
 return py;
}
self.onmessage=async({data})=>{try{
 runtime ||= initialize(data.id).catch(e=>{runtime=null;throw e});const py=await runtime;
 if(data.action && !['quotes','diagnostics','grid'].includes(data.action))throw Error('Unsupported calculation task');
 self.postMessage({id:data.id,progress:data.action==='grid'?'Revaluing the portfolio across sampled spot prices…':data.action==='diagnostics'?'Inspecting six fixed resolutions and perturbation checks…':data.action==='quotes'?'Checking quote-implied volatility and tree sensitivity…':'Revaluing positions and scenarios…'});
 py.globals.set('input_json',JSON.stringify(data.request));
 py.globals.set('source_note',typeof data.source_note==='string'?data.source_note.slice(0,4000):'');
 py.globals.set('selected_position_id',data.position_id??null);
 const response=py.runPython(data.action==='grid'?"result = review_grid(json.loads(input_json))\njson.dumps({'result':result, 'html':render_grid(result), 'svg':plot_svg(result)}, allow_nan=False)":data.action==='diagnostics'?"result = diagnose(json.loads(input_json), selected_position_id)\njson.dumps({'result':result, 'html':render_diagnostics(result)}, allow_nan=False)":data.action==='quotes'?"result = review_quotes(json.loads(input_json))\njson.dumps({'result':result, 'html':render_quote_review(result)}, allow_nan=False)":"result = analyse(json.loads(input_json))\njson.dumps({'result':result, 'html':render(result, json.loads(input_json), source_note)}, allow_nan=False)");
 self.postMessage({id:data.id,...JSON.parse(response)});
}catch(e){self.postMessage({id:data.id,error:String(e.message||e).trim().split('\n').at(-1)})}};
