"""Serve the existing game and PINN adapter locally, with correct JS MIME types."""
import argparse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--port', type=int, default=8137)
p.add_argument('--open', action='store_true', help='Open the game after binding the server')
args = p.parse_args()
root = Path(__file__).resolve().parent
handler = partial(SimpleHTTPRequestHandler, directory=str(root))
server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
print(f'Watch/play: http://127.0.0.1:{args.port}/', flush=True)
if args.open:
    webbrowser.open(f'http://127.0.0.1:{args.port}/')
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.server_close()
