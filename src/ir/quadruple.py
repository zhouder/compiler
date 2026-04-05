from dataclasses import dataclass


@dataclass
class Quadruple:
    op: str
    arg1: str
    arg2: str
    result: str

    def __str__(self):
        return f"({self.op}, {self.arg1}, {self.arg2}, {self.result})"
