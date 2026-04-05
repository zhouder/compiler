import sys
from pathlib import Path
from pprint import pprint

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


def compile_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    lexer = Lexer(source)
    tokens = lexer.tokenize()

    print("=== TOKENS ===")
    for token in tokens:
        print(token)

    lexical_errors = [t for t in tokens if t.type == TokenType.ERROR]
    if lexical_errors:
        print("\n发现词法错误，停止编译。")
        return

    parser = Parser(tokens)
    ast = parser.parse()

    print("\n=== AST ===")
    pprint(ast)

    print("\n=== SEMANTIC ===")
    try:
        SemanticAnalyzer().analyze(ast)
        print("语义分析通过")
    except SemanticError as e:
        print(f"语义错误：{e}")
        return

    ir = IRGenerator().generate(ast)
    print("\n=== IR ===")
    for item in ir:
        print(item)

    asm = CodeGenerator().generate(ir)
    print("\n=== ASM ===")
    print(asm)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python src/main.py examples/test1.c")
        raise SystemExit(1)
    compile_file(sys.argv[1])
