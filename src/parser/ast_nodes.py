from dataclasses import dataclass, field
from typing import Any, List, Optional


class ASTNode:
    pass


@dataclass
class Program(ASTNode):
    includes: List["Include"]
    declarations: List[ASTNode]

    @property
    def functions(self):
        return [item for item in self.declarations if isinstance(item, FunctionDef)]


@dataclass
class Include(ASTNode):
    text: str
    header: str = ""


@dataclass
class StructDef(ASTNode):
    name: str
    fields: List["VarDecl"]


@dataclass
class Param(ASTNode):
    param_type: str
    name: str
    array_size: Optional[ASTNode] = None
    is_array: bool = False


@dataclass
class FunctionDef(ASTNode):
    return_type: str
    name: str
    params: List[Param]
    body: "Block"


@dataclass
class Block(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class VarDecl(ASTNode):
    var_type: str
    name: str
    init: Optional[ASTNode] = None
    array_size: Optional[ASTNode] = None
    is_array: bool = False


@dataclass
class DeclStmt(ASTNode):
    declarations: List[VarDecl]


@dataclass
class Assign(ASTNode):
    target: "Identifier"
    value: ASTNode


@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode


@dataclass
class ForStmt(ASTNode):
    init: Optional[ASTNode]
    condition: Optional[ASTNode]
    update: Optional[ASTNode]
    body: ASTNode


@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode
    condition: ASTNode


@dataclass
class BreakStmt(ASTNode):
    pass


@dataclass
class ContinueStmt(ASTNode):
    pass


@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None


@dataclass
class ExprStmt(ASTNode):
    expr: ASTNode


@dataclass
class EmptyStmt(ASTNode):
    pass


@dataclass
class CallExpr(ASTNode):
    callee: str
    args: List[ASTNode]


@dataclass
class BinaryExpr(ASTNode):
    operator: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryExpr(ASTNode):
    operator: str
    operand: ASTNode


@dataclass
class Literal(ASTNode):
    value: Any
    literal_type: str


@dataclass
class Identifier(ASTNode):
    name: str


@dataclass
class ArrayAccess(ASTNode):
    array: ASTNode
    index: ASTNode


@dataclass
class MemberAccess(ASTNode):
    obj: ASTNode
    member: str
    through_pointer: bool = False
