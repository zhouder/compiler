import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat

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
    ok: bool
    source_path: Path
    sections: list
    stage_outputs: dict
    log_text: str
    output_dir: Path


def resolve_source_path(path: str) -> Path:
    source_path = Path(path)
    if source_path.is_absolute():
        return source_path

    cwd_path = Path.cwd() / source_path
    if cwd_path.exists():
        return cwd_path

    return PROJECT_ROOT / source_path


def sanitize_output_stem(stem: str) -> str:
    safe = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-")).strip("._-")
    return safe or "playground"


def write_outputs(source_path: Path, stage_outputs, sections):
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


def run_pipeline_from_text(source: str, source_path: Path) -> CompileResult:
    sections = []
    stage_outputs = {}

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

    ast_text = pformat(ast)
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
