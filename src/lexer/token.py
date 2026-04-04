from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    EOF = auto()
    ERROR = auto()


@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    col: int

    def __str__(self) -> str:
        return f"({self.line}, {self.col}, {self.type.name}, {self.lexeme})"
