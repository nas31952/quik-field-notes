"""
Quik Field Notes — Multi-Threaded Dual HTTPS/HTTP Mobile Field Server
Powered by Nasrullah Khan

Provides high-concurrency multi-threaded serving for iPhone Safari and Android Chrome,
preventing socket disconnect stalls and ensuring continuous GNSS satellite and Speech-to-Text performance.
"""

import os
import sys
import ssl
import socket
import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading

def get_local_ips():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    try:
        host_name = socket.gethostname()
        for ip in socket.gethostbyname_ex(host_name)[2]:
            if not ip.startswith('127.') and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        ips.append('127.0.0.1')
    return ips

def ensure_ssl_cert(cert_dir):
    cert_path = os.path.join(cert_dir, 'server_cert.pem')
    key_path = os.path.join(cert_dir, 'server_key.pem')

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    print("[*] Generating instant local SSL certificate for GNSS and Speech security...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Field Reconnaissance'),
            x509.NameAttribute(NameOID.COMMON_NAME, u'Quik Field Notes')
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow() - datetime.timedelta(days=1)
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=730)
        ).sign(key, hashes.SHA256())

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("[✓] Local SSL certificate successfully generated!")
        return cert_path, key_path
    except Exception as e:
        print(f"[!] Warning: Could not generate SSL certificate: {e}")
        return None, None

class RobustFieldHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Permissions-Policy', 'geolocation=(self), microphone=(self)')
        self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        # Handle Apple Touch Icons or missing Favicons gracefully to prevent Safari stalls
        if self.path in ('/apple-touch-icon.png', '/apple-touch-icon-precomposed.png'):
            ico_path = os.path.join(self.directory or '.', 'icon-192.png')
            if os.path.exists(ico_path):
                self.path = '/icon-192.png'
        super().do_GET()

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True
        except Exception:
            self.close_connection = True

    def log_message(self, format, *args):
        # Clean terminal logging
        msg = format % args
        if "404" in msg and "favicon" in msg:
            return
        sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {self.client_address[0]} - {msg}\n")

def run_https_server(cert_path, key_path, port=8443):
    server = ThreadingHTTPServer(('0.0.0.0', port), RobustFieldHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()

def run_http_server(port=8080):
    server = ThreadingHTTPServer(('0.0.0.0', port), RobustFieldHandler)
    server.serve_forever()

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    ips = get_local_ips()
    cert_path, key_path = ensure_ssl_cert(base_dir)

    print("=" * 76)
    print("  QUIK FIELD NOTES — MOBILE COMPANION SERVER")
    print("  Powered by Nasrullah Khan")
    print("=" * 76)
    print()
    print("  Connect your iPhone or Samsung Galaxy Note 8 to this Wi-Fi / Hotspot:")
    print()
    for ip in ips:
        print(f"    ⭐ SECURE HTTPS (Recommended for GPS & Mic): https://{ip}:8443")
        print(f"       STANDARD HTTP (Fallback):                 http://{ip}:8080")
    print()
    print("  ONE-TIME BROWSER ACCEPTANCE:")
    print("  • On iPhone Safari:  Tap 'Show Details' -> Tap 'visit this website'")
    print("  • On Android Chrome: Tap 'Advanced' -> Tap 'Proceed to ... (unsafe)'")
    print()
    print("=" * 76)
    print("  [✓] Multi-threaded server active. Press Ctrl+C in this window to stop.")
    print("=" * 76)

    # Start HTTP on 8080 in background thread
    t_http = threading.Thread(target=run_http_server, args=(8080,), daemon=True)
    t_http.start()

    # Start HTTPS on 8443 on main thread
    if cert_path and key_path:
        run_https_server(cert_path, key_path, 8443)
    else:
        print("[!] Running HTTP-only server on port 8080...")
        run_http_server(8080)
