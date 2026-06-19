"""Token 定义。

词法分析阶段只产出 Token，不关心后续语法结构。本文件集中维护
Token 类型、关键字表、运算符表和界符表。
"""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """词法单元分类。输出时使用枚举名，便于和课程设计表格对应。"""

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
    TokenType.ERROR: "错误",
    TokenType.EOF: "EOF",
}


@dataclass
class Token:
    """源码中的一个词法单元，记录类型、原始文本和行列位置。"""

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
