"""四元式数据结构。

四元式统一表示为 (op, arg1, arg2, result)，后端汇编生成器只需要
顺序读取这个列表即可。
"""

from dataclasses import dataclass


@dataclass
class Quadruple:
    """一条中间代码指令。"""

    op: str
    arg1: str
    arg2: str
    result: str

    def __str__(self):
        return f"({self.op}, {self.arg1}, {self.arg2}, {self.result})"
