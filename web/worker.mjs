import {loadPyodide} from './runtime/pyodide.mjs';
let runtime;
async function initialize(){
 self.postMessage({progress:'Loading calculation components for the first run. Inputs are not uploaded.'});
 const build=await fetch('./build.json').then(r=>{if(!r.ok)throw Error('Unable to read component version');return r.json()});
 const bytes=new Uint8Array(await fetch('./engine.zip').then(r=>{if(!r.ok)throw Error('Calculation component download failed');return r.arrayBuffer()}));
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==build.engine_sha256)throw Error('Component version mismatch. Refresh the page.');
 const py=await loadPyodide({indexURL:new URL('./runtime/',self.location.href).href});
 py.unpackArchive(bytes,'zip',{extractDir:'/app'});
 py.runPython("import sys; sys.path.insert(0,'/app'); import json; from options_risk.scenarios import analyse; from options_risk.report import render");
 return py;
}
self.onmessage=async({data})=>{try{
 runtime ||= initialize().catch(e=>{runtime=null;throw e});const py=await runtime;
 self.postMessage({progress:'Revaluing positions and scenarios…'});
 py.globals.set('input_json',JSON.stringify(data.request));
 const response=py.runPython("result = analyse(json.loads(input_json))\njson.dumps({'result':result, 'html':render(result, json.loads(input_json))}, allow_nan=False)");
 self.postMessage({id:data.id,...JSON.parse(response)});
}catch(e){self.postMessage({id:data.id,error:String(e.message||e).trim().split('\n').at(-1)})}};
