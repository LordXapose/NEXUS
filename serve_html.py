# Simple HTTP Server for serving Nexus HTML
# This solves CORS issues when opening HTML from file://

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

class MyHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        # Serve Nexus.html as default
        if self.path == '/' or self.path == '':
            self.path = '/Nexus_v5_1.html'
        return super().do_GET()

def run_server(port=8000):
    # Change to the directory where Nexus HTML is located
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, MyHTTPRequestHandler)
    
    print(f"\n{'='*50}")
    print(f"🌐 Nexus Frontend Server")
    print(f"{'='*50}")
    print(f"Running on: http://localhost:{port}")
    print(f"Open in browser: http://localhost:{port}/")
    print(f"\nBackend should be running on: http://localhost:5000")
    print(f"Press CTRL+C to quit")
    print(f"{'='*50}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)

if __name__ == '__main__':
    port = int(os.getenv('HTML_PORT', 8000))
    run_server(port)
