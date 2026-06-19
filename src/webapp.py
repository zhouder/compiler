"""网页版编译器服务。

这是一个轻量级本地 HTTP 服务，前端页面通过接口提交源码，
后端复用 main.py 中的编译流程并返回各阶段结果。
"""

import json
import mimetypes
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
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

# 安全常量
MAX_SOURCE_SIZE = 1 << 20  # 1 MiB
MAX_COMPILE_SECONDS = 30
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

# 编译互斥锁，防止并发请求相互覆盖 output 文件
_compile_lock = threading.Lock()

# 全局线程池（单进程，复用线程避免频繁创建）
_executor = ThreadPoolExecutor(max_workers=4)


def guess_content_type(path: Path) -> str:
    """根据静态文件扩展名返回响应 Content-Type。"""

    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


def _sanitize_error(kind: str, message: str) -> str:
    """只向前端返回安全的错误信息，不泄露路径或异常细节。"""
    # 保留错误类型（lex/parse/semantic/ir/asm），抹掉行号和绝对路径
    safe = re.sub(r'([A-Za-z]:[\\]?|[/][^/]*[/])[^\s,]+', "<path>", message)
    safe = re.sub(r" line \d+| column \d+| at line \d+", "", safe)
    return f"[{kind}] {safe[:200]}"


class CompilerWebHandler(BaseHTTPRequestHandler):
    """处理静态页面、示例源码和在线编译接口。"""

    server_version = "CompilerWeb/1.0"
    protocol_version = "HTTP/1.1"

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
        """安全地读取 web 目录下的静态资源（防路径穿越）。"""
        target = (WEB_DIR / relative_path).resolve()
        if not target.is_relative_to(WEB_DIR.resolve()) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", guess_content_type(target))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_example(self):
        """返回示例源码。出错时返回 404，不泄露堆栈。"""
        example_path = PROJECT_ROOT / "examples" / "test.c"
        try:
            content = example_path.read_text(encoding="utf-8")
        except OSError:
            self.send_json({"ok": False, "error": "示例文件缺失"}, status=HTTPStatus.NOT_FOUND)
            return
        self.send_json({
            "filename": example_path.name,
            "source": content,
        })

    def handle_compile(self):
        """接收源码文本，运行编译流程，并返回 JSON 结果。

        安全策略：
        - body 大小不超过 MAX_SOURCE_SIZE
        - filename 必须匹配白名单正则
        - 编译过程有互斥锁 + 超时保护
        - 错误信息脱敏后返回，详细日志仅写本地文件
        """
        # 1. 读取 body（带大小上限）
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return

        if content_length <= 0 or content_length > MAX_SOURCE_SIZE:
            self.send_json(
                {"ok": False, "error": f"源码大小需在 1-{MAX_SOURCE_SIZE >> 20} MB 之间"},
                status=HTTPStatus.PAYLOAD_TOO_LARGE,
            )
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        source = payload.get("source", "")
        filename = payload.get("filename", "playground.c")

        # 2. 字段类型校验
        if not isinstance(source, str) or not isinstance(filename, str):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid request fields")
            return

        if not source.strip():
            self.send_json(
                {"ok": False, "error": "源代码为空，无法编译。"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        # 3. filename 白名单校验
        if not FILENAME_PATTERN.fullmatch(filename):
            self.send_json(
                {"ok": False, "error": "文件名只能包含字母、数字、下划线、点和短横线，最多 64 字符。"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        # 4. 编译（带锁 + 超时）
        virtual_name = Path(filename).name or "playground.c"
        try:
            future = _executor.submit(
                _compile_with_lock, source, virtual_name
            )
            result = future.result(timeout=MAX_COMPILE_SECONDS)
        except TimeoutError:
            self.send_json(
                {"ok": False, "error": "编译超时（30 秒），请减少代码量后重试。"},
                status=HTTPStatus.REQUEST_TIMEOUT,
            )
            return
        except Exception:
            # 未知异常不向上传播，只返回安全描述
            self.send_json(
                {"ok": False, "error": "编译服务内部错误，请稍后重试。"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        sections = {title: body for title, body in result.sections}
        self.send_json({
            "ok": result.ok,
            "filename": result.source_path.name,
            # 只返回相对路径，不暴露服务端绝对路径
            "outputDir": "output/",
            "sections": sections,
            "artifacts": {
                "tokens": f"{result.source_path.stem}.tokens.txt",
                "ast": f"{result.source_path.stem}.ast.txt",
                "semantic": f"{result.source_path.stem}.semantic.txt",
                "ir": f"{result.source_path.stem}.ir.txt",
                "asm": f"{result.source_path.stem}.asm",
                "log": f"{result.source_path.stem}.log.txt",
            },
        })

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _compile_with_lock(source: str, virtual_name: str):
    """在互斥锁保护下执行编译，防止并发请求互相覆盖文件。"""
    with _compile_lock:
        return compile_text_result(source, virtual_name=virtual_name)


def main():
    """启动本地 Web 服务。"""
    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
            if not (1024 <= port <= 65535):
                raise ValueError("out of range")
        except (ValueError, TypeError):
            print(f"端口号需在 1024-65535 之间，使用默认值 {DEFAULT_PORT}。")
            port = DEFAULT_PORT

    server = ThreadingHTTPServer(("127.0.0.1", port), CompilerWebHandler)
    print(f"Compiler Web 已启动: http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb 服务已停止。")
    finally:
        _executor.shutdown(wait=True)
        server.server_close()


if __name__ == "__main__":
    main()
