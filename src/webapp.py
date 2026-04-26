import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main import PROJECT_ROOT, compile_text_result

WEB_DIR = CURRENT_DIR / "web"
DEFAULT_PORT = 8000


def guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


class CompilerWebHandler(BaseHTTPRequestHandler):
    server_version = "CompilerWeb/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.serve_static("index.html")
            return
        if parsed.path == "/api/example":
            self.serve_example()
            return
        if parsed.path.startswith("/assets/"):
            relative = parsed.path.removeprefix("/assets/")
            self.serve_static(relative)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/compile":
            self.handle_compile()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}")

    def serve_static(self, relative_path: str):
        target = (WEB_DIR / relative_path).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", guess_content_type(target))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_example(self):
        example_path = PROJECT_ROOT / "examples" / "test.c"
        content = example_path.read_text(encoding="utf-8")
        self.send_json(
            {
                "filename": example_path.name,
                "source": content,
            }
        )

    def handle_compile(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        source = payload.get("source", "")
        filename = payload.get("filename", "playground.c")
        if not isinstance(source, str) or not isinstance(filename, str):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid request fields")
            return
        if not source.strip():
            self.send_json(
                {
                    "ok": False,
                    "error": "源代码为空，无法编译。",
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        result = compile_text_result(source, virtual_name=Path(filename).name or "playground.c")
        sections = {title: body for title, body in result.sections}
        self.send_json(
            {
                "ok": result.ok,
                "filename": result.source_path.name,
                "outputDir": str(result.output_dir),
                "sections": sections,
                "artifacts": {
                    "tokens": f"{result.source_path.stem}.tokens.txt",
                    "ast": f"{result.source_path.stem}.ast.txt",
                    "semantic": f"{result.source_path.stem}.semantic.txt",
                    "ir": f"{result.source_path.stem}.ir.txt",
                    "asm": f"{result.source_path.stem}.asm",
                    "log": f"{result.source_path.stem}.log.txt",
                },
            }
        )

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("127.0.0.1", port), CompilerWebHandler)
    print(f"Compiler Web 已启动: http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb 服务已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
