import os
from http.server import BaseHTTPRequestHandler
from email.parser import BytesParser
from email.policy import default
import re


UPLOAD_DIR = 'map'
UPLOAD_MAP_NAME = 'custom_map.csv'


def parse_content_disposition(header_value):
    parts = header_value.split(';')
    disposition = parts[0].strip().lower()
    params = {}
    for part in parts[1:]:
        if '=' in part:
            key, val = part.strip().split('=', 1)
            params[key.lower()] = val.strip('"')
    return disposition, params


class FileRecieverServer(BaseHTTPRequestHandler):

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')  # Allow all origins
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)  # No content
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == '/activateRandomMap':
            self.send_response(200)
            self._set_cors_headers()
            self.end_headers()

            src = os.path.join(UPLOAD_DIR, "disabled_custom_map.csv")

            if os.path.exists(src):
                os.rename(src, "map/custom_map.csv")
                self.wfile.write(b"Map activated")
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"custom_map.csv not found")
            return

        elif self.path == '/deactivateRandomMap':
            active_map_path = os.path.join(UPLOAD_DIR, UPLOAD_MAP_NAME)
            if os.path.exists(active_map_path):
                os.rename(active_map_path, f"map/disabled_custom_map.csv")

            self.send_response(200)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b"Map deactivated")
            return

        elif self.path == '/upload':
            content_type = self.headers.get('Content-Type')
            if not content_type or not content_type.startswith('multipart/form-data'):
                self.send_response(400)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"Invalid content type")
                return

            match = re.search('boundary=(.*)', content_type)
            if not match:
                self.send_response(400)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"Missing boundary")
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            full_message = (
                f"Content-Type: {content_type}\r\n\r\n".encode() + body
            )
            msg = BytesParser(policy=default).parsebytes(full_message)

            for part in msg.iter_parts():
                disposition_header = part.get('Content-Disposition', '')
                disposition, params = parse_content_disposition(disposition_header)

                if disposition != 'form-data' or 'filename' not in params:
                    continue

                file_data = part.get_payload(decode=True)

                os.makedirs(UPLOAD_DIR, exist_ok=True)
                filepath = os.path.join(UPLOAD_DIR, UPLOAD_MAP_NAME)

                with open(filepath, 'wb') as f:
                    f.write(file_data)

                self.send_response(200)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"File uploaded successfully.")
                return

            self.send_response(400)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b"No valid file part found")

        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b"Endpoint not found")
   
   
    def do_GET(self):
        self.send_response(405)
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(b"Use POST for all operations")


