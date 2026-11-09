import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from scanner import FuturesScanner

ROOT=Path(__file__).resolve().parent
scanner=FuturesScanner()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  route=urlparse(self.path).path
  if route=='/api/scan':
   body=json.dumps(scanner.get(),ensure_ascii=False,allow_nan=False).encode('utf-8'); mime='application/json; charset=utf-8'
  else:
   files={'/':'index.html','/style.css':'style.css','/app.js':'app.js'}
   if route not in files: self.send_error(404); return
   file=ROOT/'static'/files[route]; body=file.read_bytes(); mime={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'text/javascript; charset=utf-8'}[file.suffix[1:]]
  self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)

if __name__=='__main__':
 scanner.start(); port=int(os.getenv('PORT','8765')); print(f'Futures intelligence: http://127.0.0.1:{port}',flush=True)
 try: ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
 finally: scanner.stop()
