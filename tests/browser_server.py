"""Static app and explicit synthetic CORS model for browser acceptance."""
import functools
import json
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler,SimpleHTTPRequestHandler,ThreadingHTTPServer

class Model(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(204);self.end_headers()
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.headers.get('Authorization')!='Bearer SYNTHETIC_LOCAL_KEY':
            self.send_response(401);self.end_headers();return
        if body.get('stream'):
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            try:
                for text in ['你的模型在追问：','谁最需要这个想法？']:
                    self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{'content':text}}]})+'\n\n').encode());self.wfile.flush();time.sleep(.15)
                self.wfile.write(b'data: [DONE]\n\n')
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
            return
        text='自己的模型起的名字'
        if body.get('response_format'):
            prompt=body['messages'][-1]['content']
            text=json.dumps({'dirs':[{'title':'换一个方向','why':'从更小的需求出发'}]} if 'dirs' in prompt else {'title':text,'seed':'本机念头','first':'你的第一个用户是谁？'},ensure_ascii=False)
        raw=json.dumps({'choices':[{'message':{'content':text}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

upstream=ThreadingHTTPServer(('127.0.0.1',0),Model)
threading.Thread(target=upstream.serve_forever,daemon=True).start()
class Static(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
app=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Static,directory=str(Path(__file__).resolve().parents[1]/'dist')))
print(json.dumps({'url':f'http://127.0.0.1:{app.server_port}','model_url':f'http://127.0.0.1:{upstream.server_port}/v1'}),flush=True)
app.serve_forever()
