from lexer.lexer import Lexer


def compile_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    lexer = Lexer(source)
    tokens = lexer.tokenize()

    print("=== TOKENS ===")
    for token in tokens:
        print(token)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("用法: python src/main.py examples/test1.c")
        raise SystemExit(1)

    compile_file(sys.argv[1])
