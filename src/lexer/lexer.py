from .token import Token, TokenType


class Lexer:
    def __init__(self, text: str):
        self.text = text

    def tokenize(self):
        # 这里先留一个最小可运行版本
        return [Token(TokenType.EOF, "", 1, 1)]
