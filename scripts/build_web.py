"""Package the exact Python core, with a pinned, self-hosted browser runtime."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'out'
RUNTIME = ROOT/'node_modules/pyodide'
FILES = ['pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json']
if json.loads((RUNTIME/'package.json').read_text())['version'] != '314.0.6':
    raise ValueError('Run npm ci for the pinned runtime')
OUT.mkdir(exist_ok=True)
(OUT/'runtime').mkdir(exist_ok=True)
for name in FILES:
    shutil.copyfile(RUNTIME/name,OUT/'runtime'/name)
for name in ['index.html','styles.css','app.js','worker.mjs','quotes.html','quotes-app.js']:
    shutil.copyfile(ROOT/'web'/name,OUT/name)
engine=io.BytesIO()
with zipfile.ZipFile(engine,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in ['__init__.py','pricing.py','scenarios.py','report.py','quotes.py','diagnostics.py','grid.py']:
        source=ROOT/'options_risk'/name
        if source.is_symlink(): raise ValueError('No symlink sources')
        info=zipfile.ZipInfo('options_risk/'+name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,source.read_bytes())
(OUT/'engine.zip').write_bytes(engine.getvalue())
(OUT/'build.json').write_text(json.dumps({'engine_sha256':hashlib.sha256(engine.getvalue()).hexdigest(),'pyodide':'314.0.6','input_processing':'browser-local'},indent=2))
shutil.copyfile(ROOT/'web/THIRD_PARTY_NOTICES.txt',OUT/'THIRD_PARTY_NOTICES.txt')
print(json.dumps({'directory':str(OUT),'bytes':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())}))
