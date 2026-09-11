"""Synthetic local fixture. Never reads the operator's DB or API keys."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from yang import auth,db,demo,server,store

class Model(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if body.get('stream'):
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            try:
                for text in ['具体说说，','谁会第一个用它？']:
                    self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{'content':text}}]})+'\n\n').encode());self.wfile.flush();time.sleep(.2)
                self.wfile.write(b'data: [DONE]\n\n')
            except (BrokenPipeError,ConnectionResetError):pass
            return
        text='浏览器验收想法'
        if body.get('response_format'):
            prompt=body['messages'][-1]['content']
            text=json.dumps({'dirs':[{'title':'分叉方向','seed':'新的角度'}]} if 'dirs' in prompt else {'title':text,'seed':'测试念头','first':'谁会用它？'},ensure_ascii=False)
        raw=json.dumps({'choices':[{'message':{'content':text}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

with tempfile.TemporaryDirectory(prefix='yang-browser-') as directory:
    upstream=ThreadingHTTPServer(('127.0.0.1',0),Model)
    threading.Thread(target=upstream.serve_forever,daemon=True).start()
    file=Path(directory)/'browser.db';c=db.connect(file);st=demo.state();st['ideas'][0]['title']='OWNER_PRIVATE'
    st['conf']={'models':[{'id':'mock','name':'Synthetic fixture','base':f'http://127.0.0.1:{upstream.server_port}/v1','model':'test','key':'SYNTHETIC_KEY_ONLY'}],'route':{}}
    store.load_state(c,st);c.close()
    policy=auth.AuthPolicy(token='BROWSER_SYNTHETIC_TOKEN_0123456789abcdef',production=False,public_origin=None,secure_cookie=False)
    handler=server.make(file,Path(__file__).resolve().parents[1]/'dist',policy=policy)
    app=ThreadingHTTPServer(('127.0.0.1',0),handler)
    print(json.dumps({'url':f'http://127.0.0.1:{app.server_port}'}),flush=True)
    app.serve_forever()
