from parser.ast_nodes import (
    Program, FunctionDef, Block, VarDecl, Assign, IfStmt, WhileStmt, ForStmt,
    ReturnStmt, ExprStmt, CallExpr, BinaryExpr, UnaryExpr, Literal, Identifier
)
from .symbol_table import SymbolTable, SemanticError


NUMERIC_TYPES = {"int", "char", "float"}


class SemanticAnalyzer:
    def __init__(self):
        self.symbols = SymbolTable()

    def analyze(self, node):
        self.visit(node)

    def visit(self, node):
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise SemanticError(f"未实现的语义分析节点：{type(node).__name__}")
        return method(node)

    def visit_Program(self, node: Program):
        for func in node.functions:
            self.visit(func)

    def visit_FunctionDef(self, node: FunctionDef):
        self.symbols.push()
        self.visit(node.body)
        self.symbols.pop()

    def visit_Block(self, node: Block):
        self.symbols.push()
        for stmt in node.statements:
            self.visit(stmt)
        self.symbols.pop()

    def visit_VarDecl(self, node: VarDecl):
        self.symbols.define(node.name, {"type": node.var_type})
        if node.init is not None:
            rhs_type = self.visit(node.init)
            self.ensure_assignable(node.var_type, rhs_type, node.name)

    def visit_Assign(self, node: Assign):
        symbol = self.symbols.lookup(node.target.name)
        if symbol is None:
            raise SemanticError(f"变量未定义：{node.target.name}")
        rhs_type = self.visit(node.value)
        self.ensure_assignable(symbol["type"], rhs_type, node.target.name)
        return symbol["type"]

    def visit_IfStmt(self, node: IfStmt):
        self.visit(node.condition)
        self.visit(node.then_branch)
        if node.else_branch is not None:
            self.visit(node.else_branch)

    def visit_WhileStmt(self, node: WhileStmt):
        self.visit(node.condition)
        self.visit(node.body)

    def visit_ForStmt(self, node: ForStmt):
        self.symbols.push()
        if node.init is not None:
            self.visit(node.init)
        if node.condition is not None:
            self.visit(node.condition)
        if node.update is not None:
            self.visit(node.update)
        self.visit(node.body)
        self.symbols.pop()

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value is not None:
            return self.visit(node.value)
        return "void"

    def visit_ExprStmt(self, node: ExprStmt):
        return self.visit(node.expr)

    def visit_CallExpr(self, node: CallExpr):
        if node.callee == "printf":
            for arg in node.args:
                self.visit(arg)
            return "int"
        if node.callee == "scanf":
            if not node.args or not isinstance(node.args[0], Literal) or node.args[0].literal_type != "string":
                raise SemanticError("scanf 的第一个参数必须是格式字符串")
            for arg in node.args[1:]:
                self.ensure_scanf_target(arg)
            return "int"
        raise SemanticError(f"当前版本不支持的函数调用：{node.callee}")

    def visit_BinaryExpr(self, node: BinaryExpr):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        if node.operator in ("<", "<=", ">", ">=", "==", "!=", "&&", "||"):
            return "int"
        if left_type == "float" or right_type == "float":
            return "float"
        if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
            return "int"
        raise SemanticError(f"不支持的二元表达式类型：{left_type} {node.operator} {right_type}")

    def visit_UnaryExpr(self, node: UnaryExpr):
        if node.operator == "&":
            if not isinstance(node.operand, Identifier):
                raise SemanticError("& 后面必须是变量名")
            operand_type = self.visit(node.operand)
            return f"{operand_type}*"
        operand_type = self.visit(node.operand)
        if node.operator == "!":
            return "int"
        return operand_type

    def visit_Literal(self, node: Literal):
        return node.literal_type

    def visit_Identifier(self, node: Identifier):
        symbol = self.symbols.lookup(node.name)
        if symbol is None:
            raise SemanticError(f"变量未定义：{node.name}")
        return symbol["type"]

    def ensure_assignable(self, lhs_type, rhs_type, name):
        if lhs_type == rhs_type:
            return
        if lhs_type == "float" and rhs_type in ("int", "char"):
            return
        if lhs_type == "int" and rhs_type == "char":
            return
        raise SemanticError(f"类型不匹配：不能把 {rhs_type} 赋值给 {lhs_type} 变量 {name}")

    def ensure_scanf_target(self, node):
        if isinstance(node, UnaryExpr) and node.operator == "&" and isinstance(node.operand, Identifier):
            if self.symbols.lookup(node.operand.name) is None:
                raise SemanticError(f"变量未定义：{node.operand.name}")
            return
        raise SemanticError("scanf 的输入参数必须是 &变量")
