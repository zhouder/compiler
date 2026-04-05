from lexer.token import TokenType


class TokenStream:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def current(self):
        return self.tokens[self.index]

    def peek(self, offset=0):
        idx = self.index + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self):
        tok = self.current()
        if self.index < len(self.tokens) - 1:
            self.index += 1
        return tok

    def match(self, token_type=None, lexeme=None):
        tok = self.current()
        if token_type is not None and tok.type != token_type:
            return False
        if lexeme is not None and tok.lexeme != lexeme:
            return False
        self.advance()
        return True

    def expect(self, token_type=None, lexeme=None, message="语法错误"):
        tok = self.current()
        if token_type is not None and tok.type != token_type:
            raise SyntaxError(f"{message}：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")
        if lexeme is not None and tok.lexeme != lexeme:
            raise SyntaxError(f"{message}：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")
        self.advance()
        return tok

    def is_eof(self):
        return self.current().type == TokenType.EOF
