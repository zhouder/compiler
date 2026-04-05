from dataclasses import dataclass, field
from typing import Any, List, Optional


class ASTNode:
    pass


@dataclass
class Program(ASTNode):
    functions: List["FunctionDef"]


@dataclass
class FunctionDef(ASTNode):
    return_type: str
    name: str
    body: "Block"


@dataclass
class Block(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class VarDecl(ASTNode):
    var_type: str
    name: str
    init: Optional[ASTNode] = None


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
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None


@dataclass
class ExprStmt(ASTNode):
    expr: ASTNode


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
