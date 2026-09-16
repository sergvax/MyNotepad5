#!/usr/bin/env python3
"""Локальный HTTPS-сервер для установки PWA на iPhone.

- Автогенерирует самоподписанный сертификат под текущий IP-адрес Mac.
- При смене IP сертификат пересоздаётся автоматически.
- Биндится на 0.0.0.0, порт 8443 (переопределяется через env PORT).
"""
import hashlib
import http.server
import os
import re
import socket
import socketserver
import ssl
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CERT_DIR = os.path.join(ROOT, ".cert")
CERT = os.path.join(CERT_DIR, "cert.pem")
KEY = os.path.join(CERT_DIR, "key.pem")
MARKER = os.path.join(CERT_DIR, ".ipmarker")
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8443"))


def local_ips():
    ips = set()
    try:
        out = subprocess.check_output(["ifconfig"], text=True, errors="ignore")
        for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out):
            ip = m.group(1)
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips)


def ensure_cert(ips):
    os.makedirs(CERT_DIR, exist_ok=True)
    marker = hashlib.sha256(",".join(ips).encode()).hexdigest()
    old = None
    if os.path.exists(MARKER):
        try:
            old = open(MARKER).read().strip()
        except Exception:
            pass
    if os.path.exists(CERT) and old == marker:
        return
    san = ",".join("IP:" + ip for ip in ips)
    cfg = "[req]\ndistinguished_name=dn\nx509_extensions=reqext\nprompt=no\n[dn]\nCN=MacBook PWA\n[reqext]\n" + "subjectAltName=" + san + "\n"
    cfg_path = os.path.join(CERT_DIR, "openssl.cnf")
    with open(cfg_path, "w") as f:
        f.write(cfg)
    subprocess.check_call(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", KEY, "-out", CERT,
            "-days", "825", "-nodes", "-config", cfg_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(MARKER, "w") as f:
        f.write(marker)
    print(f"  Сертификат пересоздан для IP: {', '.join(ips)}")


class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


def main():
    ips = local_ips()
    if not ips:
        print("Не удалось определить IP-адреса интерфейсов")
        sys.exit(1)
    ensure_cert(ips)
    os.chdir(ROOT)

    httpd = ThreadingHTTPServer((HOST, PORT), http.server.SimpleHTTPRequestHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print("=" * 60)
    print("  ЛЁГКИЙ БЛОКНОТ — локальный HTTPS-сервер запущен")
    print("=" * 60)
    for ip in ips:
        print(f"  На iPhone откройте:  https://{ip}:{PORT}/MyNotepad5.html")
    print(f"  Сертификат самоподписанный — при первом заходе в Safari")
    print("  нажмите «Показать подробности» → «Перейти на сайт».")
    print("  Ctrl+C — остановить.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()