import json
from pathlib import Path
import subprocess
from yang import demo, jsonl

ROOT=Path(__file__).resolve().parents[1]


def test_encrypted_jsonl_roundtrip_both_languages(tmp_path):
    value=demo.state();password='synthetic-test-password'
    value['conf']={'models':[{'id':'synthetic','name':'Test','model':'test','key':'SYNTHETIC_ENCRYPTED_KEY'}]}
    source=tmp_path/'from-python.jsonl';source.write_text(jsonl.export(value,password),encoding='utf-8')
    output=tmp_path/'from-js.jsonl'
    script=tmp_path/'crypto.mjs'
    script.write_text('''import fs from 'node:fs';
await import(%s);
const result=await YD.parseJSONL(fs.readFileSync(%s,'utf8'),{pass:%s});
if(!result.ok) throw new Error(JSON.stringify(result.errors));
const state=JSON.parse(fs.readFileSync(%s,'utf8'));
const encoded=await YD.exportJSONL(state,{pass:%s});
fs.writeFileSync(%s,encoded.text);
'''%(json.dumps((ROOT/'web/src/yangdata.js').as_uri()),json.dumps(str(source)),json.dumps(password),
     json.dumps(str(tmp_path/'state.json')),json.dumps(password),json.dumps(str(output))),encoding='utf-8')
    (tmp_path/'state.json').write_text(json.dumps(value),encoding='utf-8')
    result=subprocess.run(['node',str(script)],capture_output=True,text=True,encoding="utf-8")
    assert result.returncode==0,result.stderr
    decoded=jsonl.parse(output.read_text(encoding='utf-8'),password)
    assert decoded['ok'],decoded.get('errors')
    assert jsonl.to_state(decoded['recs'])['conf']['models'][0]['key']=='SYNTHETIC_ENCRYPTED_KEY'
    assert not jsonl.parse(output.read_text(encoding='utf-8'),'wrong-password')['ok']


def test_local_model_and_graph_contracts():
    result=subprocess.run(['node',str(ROOT/'tests/local-unit.mjs')],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
