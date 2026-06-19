"""抽象语法树节点定义。

语法分析阶段把 Token 组织成这些节点；语义检查、IR 生成和代码生成
都以 AST 为输入继续处理。
"""

from dataclasses import dataclass, field
from typing import Any, Optional


class ASTNode:
    """所有 AST 节点的公共基类，方便 isinstance 判别。"""

    pass


@dataclass
class Program(ASTNode):
    """整个翻译单元：includes + 顶层声明（函数/全局变量/结构体）。"""

    includes: list["Include"]
    declarations: list[ASTNode]

    @property
    def functions(self):
        """从 declarations 中筛出所有函数定义。"""

        return [item for item in self.declarations if isinstance(item, FunctionDef)]


@dataclass
class Include(ASTNode):
    """#include 指令。"""

    text: str
    header: str = ""


@dataclass
class StructDef(ASTNode):
    """结构体类型定义。"""

    name: str
    fields: list["VarDecl"]


@dataclass
class Param(ASTNode):
    """函数形参。"""

    param_type: str
    name: str
    array_size: Optional[ASTNode] = None
    is_array: bool = False


@dataclass
class FunctionDef(ASTNode):
    """函数定义。"""

    return_type: str
    name: str
    params: list[Param]
    body: "Block"


@dataclass
class Block(ASTNode):
    """用 { } 包裹的复合语句/函数体。"""

    statements: list[ASTNode] = field(default_factory=list)


@dataclass
class VarDecl(ASTNode):
    """单条变量声明。"""

    var_type: str
    name: str
    init: Optional[ASTNode] = None
    array_size: Optional[ASTNode] = None
    is_array: bool = False


@dataclass
class DeclStmt(ASTNode):
    """一行声明多个变量，如 `int a, b, c;`。"""

    declarations: list[VarDecl]


@dataclass
class InitializerList(ASTNode):
    """花括号初始化列表，如 `{1, 2, 3}` 或 `{{1,2}, {3,4}}`。"""

    values: list[ASTNode]


@dataclass
class Assign(ASTNode):
    """赋值表达式 `target = value`。"""

    target: "Identifier"
    value: ASTNode


@dataclass
class IfStmt(ASTNode):
    """if / else 语句。"""

    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileStmt(ASTNode):
    """while 循环：先判条件再执行。"""

    condition: ASTNode
    body: ASTNode


@dataclass
class ForStmt(ASTNode):
    """for 循环 `for (init; condition; update) body`。"""

    init: Optional[ASTNode]
    condition: Optional[ASTNode]
    update: Optional[ASTNode]
    body: ASTNode


@dataclass
class DoWhileStmt(ASTNode):
    """do-while 循环：先执行体再判条件。"""

    body: ASTNode
    condition: ASTNode


@dataclass
class BreakStmt(ASTNode):
    """break 语句。"""

    pass


@dataclass
class ContinueStmt(ASTNode):
    """continue 语句。"""

    pass


@dataclass
class ReturnStmt(ASTNode):
    """return 语句。"""

    value: Optional[ASTNode] = None


@dataclass
class ExprStmt(ASTNode):
    """表达式语句，如 `x++;` `foo(1);`。"""

    expr: ASTNode


@dataclass
class EmptyStmt(ASTNode):
    """空语句，对应单独一个 `;`。"""

    pass


@dataclass
class CallExpr(ASTNode):
    """函数调用表达式。"""

    callee: str
    args: list[ASTNode]


@dataclass
class BinaryExpr(ASTNode):
    """二元运算表达式，如 `a + b`、`x < y`。"""

    operator: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryExpr(ASTNode):
    """一元运算表达式，如 `-x`、`!flag`、`*ptr`、`i++`。"""

    operator: str
    operand: ASTNode


@dataclass
class Literal(ASTNode):
    """字面常量：数字 / 字符 / 字符串。"""

    value: Any
    literal_type: str


@dataclass
class Identifier(ASTNode):
    """标识符：源码里出现的名字。"""

    name: str


@dataclass
class ArrayAccess(ASTNode):
    """数组下标访问，如 `a[i]`。"""

    array: ASTNode
    index: ASTNode


@dataclass
class MemberAccess(ASTNode):
    """结构体成员访问，`.` 或 `->`。"""

    obj: ASTNode
    member: str
    through_pointer: bool = False
