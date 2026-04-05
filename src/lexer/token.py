from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    RW = auto()
    ID = auto()
    NUM10 = auto()
    NUM8 = auto()
    NUM16 = auto()
    FLOAT = auto()
    CS_STR = auto()
    CS_CHAR = auto()
    OP = auto()
    DL = auto()
    CM = auto()
    ERROR = auto()
    EOF = auto()


TYPE_CN = {
    TokenType.RW: "关键字",
    TokenType.ID: "标识符",
    TokenType.NUM10: "十进制数",
    TokenType.NUM8: "八进制数",
    TokenType.NUM16: "十六进制数",
    TokenType.FLOAT: "浮点数",
    TokenType.CS_STR: "字符串常量",
    TokenType.CS_CHAR: "字符常量",
    TokenType.OP: "运算符",
    TokenType.DL: "界符",
    TokenType.CM: "注释",
    TokenType.ERROR: "错误",
    TokenType.EOF: "EOF",
}


@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    col: int

    def __str__(self) -> str:
        return f"({self.line}, {self.col}, {self.type.name}, {self.lexeme})"


KEYWORDS = {
    "auto", "double", "int", "struct", "break", "else", "long", "switch", "case", "enum",
    "register", "typedef", "char", "extern", "return", "union", "const", "float", "short",
    "unsigned", "continue", "for", "signed", "void", "default", "goto", "sizeof", "volatile",
    "do", "if", "static", "while", "printf", "scanf", "include"
}

OPERATORS = [
    ">>=", "<<=", "==", "!=", ">=", "<=",
    "++", "--", "&&", "||",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "<<", ">>", "->",
    ".", "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "=", "<", ">", "?"
]

DELIMITERS = ["...", "(", ")", "[", "]", "{", "}", ";", ",", ":"]
