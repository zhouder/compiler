"""编译流程入口。

本文件负责把词法、语法、语义、中间代码和目标代码几个阶段串起来，
同时把每个阶段的结果保存到 output 目录，便于调试和答辩展示。
"""

import sys
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from codegen.code_generator import CodeGenerator
from ir.ir_generator import IRGenerator
from lexer.lexer import Lexer
from lexer.token import TokenType
from parser.parser import Parser
from semantic.semantic_analyzer import SemanticAnalyzer
from semantic.symbol_table import SemanticError

PROJECT_ROOT = CURRENT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


@dataclass
class CompileResult:
    """一次编译运行的汇总结果，供命令行、GUI 和 Web 入口复用。"""

    ok: bool
    source_path: Path
    sections: list
    stage_outputs: dict
    log_text: str
    output_dir: Path


def resolve_source_path(path: str) -> Path:
    """把用户输入的相对路径转换为实际源码路径。"""

    source_path = Path(path)
    if source_path.is_absolute():
        return source_path

    cwd_path = Path.cwd() / source_path
    if cwd_path.exists():
        return cwd_path

    return PROJECT_ROOT / source_path


def sanitize_output_stem(stem: str) -> str:
    """生成安全的输出文件名前缀，避免特殊字符影响 DOS 工具。"""

    safe = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-")).strip("._-")
    return safe or "playground"


def write_outputs(source_path: Path, stage_outputs, sections):
    """把各阶段输出写入 output，并额外生成完整日志文件。"""

    OUTPUT_DIR.mkdir(exist_ok=True)
    stem = sanitize_output_stem(source_path.stem)
    for suffix, content in stage_outputs.items():
        (OUTPUT_DIR / f"{stem}.{suffix}").write_text(content, encoding="utf-8")
        if suffix == "asm":
            dos_stem = "".join(ch for ch in stem if ch.isalnum() or ch == "_")[:8] or "output"
            (OUTPUT_DIR / f"{dos_stem}.asm").write_text(content, encoding="utf-8")

    log_text = "\n\n".join(f"=== {title} ===\n{body}" for title, body in sections)
    (OUTPUT_DIR / f"{stem}.log.txt").write_text(log_text, encoding="utf-8")
    return log_text


def _fail_result(source_path: Path, stage_outputs, sections, title: str, message: str) -> CompileResult:
    sections.append((title, message))
    log_text = write_outputs(source_path, stage_outputs, sections)
    return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)


def format_ast(ast) -> str:
    """Render dataclass AST like pformat, but hide empty noise fields."""

    def visible_items(node):
        items = []
        for field_info in fields(node):
            value = getattr(node, field_info.name)
            if value is None or value is False:
                continue
            items.append((field_info.name, value))
        return items

    def inline_value(value, depth=0):
        if isinstance(value, str):
            return repr(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return repr(value)
        if isinstance(value, list):
            if not value:
                return "[]"
            if len(value) <= 6:
                parts = []
                for item in value:
                    item_text = inline_value(item, depth + 1)
                    if item_text is None:
                        return None
                    parts.append(item_text)
                text = "[" + ", ".join(parts) + "]"
                if "\n" not in text and len(text) <= 96:
                    return text
            return None
        if is_dataclass(value):
            items = visible_items(value)
            parts = []
            for name, child in items:
                child_text = inline_value(child, depth + 1)
                if child_text is None or "\n" in child_text:
                    return None
                parts.append(f"{name}={child_text}")
            text = f"{type(value).__name__}(" + ", ".join(parts) + ")"
            return text if len(text) <= 96 or depth > 0 else None
        return repr(value)

    def render(value, level=0, name=None):
        indent = "    " * level
        prefix = f"{name}=" if name else ""
        inline = inline_value(value)
        if inline is not None:
            return f"{indent}{prefix}{inline}"
        if isinstance(value, list):
            lines = [f"{indent}{prefix}["]
            for item in value:
                lines.append(render(item, level + 1) + ",")
            lines.append(f"{indent}]")
            return "\n".join(lines)
        if is_dataclass(value):
            lines = [f"{indent}{prefix}{type(value).__name__}("]
            for field_name, child in visible_items(value):
                lines.append(render(child, level + 1, field_name) + ",")
            lines.append(f"{indent})")
            return "\n".join(lines)
        return f"{indent}{prefix}{repr(value)}"

    return render(ast)


def run_pipeline_from_text(source: str, source_path: Path) -> CompileResult:
    """对一段源码文本执行完整编译流程。"""

    sections = []
    stage_outputs = {}

    # 词法阶段只负责切分 Token；发现 ERROR Token 后不再继续向后分析。
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    token_text = "\n".join(str(token) for token in tokens)
    sections.append(("TOKENS", token_text))
    stage_outputs["tokens.txt"] = token_text

    lexical_errors = [token for token in tokens if token.type == TokenType.ERROR]
    if lexical_errors:
        error_text = "发现词法错误，停止编译。\n" + "\n".join(str(token) for token in lexical_errors)
        return _fail_result(source_path, stage_outputs, sections, "ERROR", error_text)

    try:
        parser = Parser(tokens)
        ast = parser.parse()
    except SyntaxError as exc:
        return _fail_result(source_path, stage_outputs, sections, "ERROR", f"语法错误：{exc}")

    ast_text = format_ast(ast)
    sections.append(("AST", ast_text))
    stage_outputs["ast.txt"] = ast_text

    try:
        SemanticAnalyzer().analyze(ast)
    except SemanticError as exc:
        semantic_text = f"语义错误：{exc}"
        sections.append(("SEMANTIC", semantic_text))
        log_text = write_outputs(source_path, stage_outputs, sections)
        return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)

    semantic_text = "语义分析通过"
    sections.append(("SEMANTIC", semantic_text))
    stage_outputs["semantic.txt"] = semantic_text

    try:
        ir = IRGenerator().generate(ast)
    except TypeError as exc:
        return _fail_result(source_path, stage_outputs, sections, "ERROR", f"中间代码生成错误：{exc}")

    ir_text = "\n".join(str(item) for item in ir)
    sections.append(("IR", ir_text))
    stage_outputs["ir.txt"] = ir_text

    asm = CodeGenerator().generate(ir)
    sections.append(("ASM", asm))
    stage_outputs["asm"] = asm

    log_text = write_outputs(source_path, stage_outputs, sections)
    return CompileResult(True, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)


def run_pipeline(path: str) -> CompileResult:
    source_path = resolve_source_path(path)
    source = source_path.read_text(encoding="utf-8")
    return run_pipeline_from_text(source, source_path)


def compile_text_result(source: str, virtual_name: str = "playground.c") -> CompileResult:
    source_path = OUTPUT_DIR / virtual_name
    return run_pipeline_from_text(source, source_path)


def compile_file(path: str):
    result = run_pipeline(path)
    print(result.log_text)
    print(f"\n阶段输出已保存到：{result.output_dir}")
    return result.ok


def compile_file_result(path: str) -> CompileResult:
    return run_pipeline(path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python src/main.py examples/test.c")
        raise SystemExit(1)
    ok = compile_file(sys.argv[1])
    raise SystemExit(0 if ok else 1)
