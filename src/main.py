import sys
from pathlib import Path
from pprint import pformat
from dataclasses import dataclass

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from lexer.lexer import Lexer
from lexer.token import TokenType
from parser.parser import Parser
from semantic.semantic_analyzer import SemanticAnalyzer
from semantic.symbol_table import SemanticError
from ir.ir_generator import IRGenerator
from codegen.code_generator import CodeGenerator

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


def write_outputs(source_path: Path, stage_outputs, sections):
    OUTPUT_DIR.mkdir(exist_ok=True)
    stem = source_path.stem
    for suffix, content in stage_outputs.items():
        (OUTPUT_DIR / f"{stem}.{suffix}").write_text(content, encoding="utf-8")
        if suffix == "asm":
            dos_stem = "".join(ch for ch in stem if ch.isalnum() or ch == "_")[:8] or "output"
            (OUTPUT_DIR / f"{dos_stem}.asm").write_text(content, encoding="utf-8")

    log_text = "\n\n".join(f"=== {title} ===\n{body}" for title, body in sections)
    (OUTPUT_DIR / f"{stem}.log.txt").write_text(log_text, encoding="utf-8")
    return log_text


def run_pipeline(path: str) -> CompileResult:
    source_path = resolve_source_path(path)
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    sections = []
    stage_outputs = {}

    lexer = Lexer(source)
    tokens = lexer.tokenize()

    token_text = "\n".join(str(token) for token in tokens)
    sections.append(("TOKENS", token_text))
    stage_outputs["tokens.txt"] = token_text

    lexical_errors = [t for t in tokens if t.type == TokenType.ERROR]
    if lexical_errors:
        error_text = "发现词法错误，停止编译。\n" + "\n".join(str(t) for t in lexical_errors)
        sections.append(("ERROR", error_text))
        log_text = write_outputs(source_path, stage_outputs, sections)
        return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)

    try:
        parser = Parser(tokens)
        ast = parser.parse()
    except SyntaxError as e:
        sections.append(("ERROR", f"语法错误：{e}"))
        log_text = write_outputs(source_path, stage_outputs, sections)
        return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)

    ast_text = pformat(ast)
    sections.append(("AST", ast_text))
    stage_outputs["ast.txt"] = ast_text

    try:
        SemanticAnalyzer().analyze(ast)
    except SemanticError as e:
        sections.append(("SEMANTIC", f"语义错误：{e}"))
        log_text = write_outputs(source_path, stage_outputs, sections)
        return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)

    sections.append(("SEMANTIC", "语义分析通过"))

    try:
        ir = IRGenerator().generate(ast)
    except TypeError as e:
        sections.append(("ERROR", f"中间代码生成错误：{e}"))
        log_text = write_outputs(source_path, stage_outputs, sections)
        return CompileResult(False, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)

    ir_text = "\n".join(str(item) for item in ir)
    sections.append(("IR", ir_text))
    stage_outputs["ir.txt"] = ir_text

    asm = CodeGenerator().generate(ir)
    sections.append(("ASM", asm))
    stage_outputs["asm"] = asm

    log_text = write_outputs(source_path, stage_outputs, sections)
    return CompileResult(True, source_path, sections, stage_outputs, log_text, OUTPUT_DIR)


def compile_file(path: str):
    result = run_pipeline(path)
    print(result.log_text)
    print(f"\n阶段输出已保存到：{result.output_dir}")
    return result.ok


def compile_file_result(path: str) -> CompileResult:
    return run_pipeline(path)
    print(log_text)
    print(f"\n阶段输出已保存到：{OUTPUT_DIR}")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python src/main.py examples/test.c")
        raise SystemExit(1)
    ok = compile_file(sys.argv[1])
    raise SystemExit(0 if ok else 1)
