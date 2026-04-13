from parser.ast_nodes import (
    Program, FunctionDef, Block, VarDecl, Assign, IfStmt, WhileStmt, ForStmt,
    ReturnStmt, ExprStmt, CallExpr, BinaryExpr, UnaryExpr, Literal, Identifier
)
from .quadruple import Quadruple


class IRGenerator:
    def __init__(self):
        self.code = []
        self.temp_id = 0
        self.label_id = 0

    def new_temp(self):
        self.temp_id += 1
        return f"t{self.temp_id}"

    def new_label(self):
        self.label_id += 1
        return f"L{self.label_id}"

    def emit(self, op, arg1="_", arg2="_", result="_"):
        self.code.append(Quadruple(op, str(arg1), str(arg2), str(result)))

    def generate(self, node):
        self.visit(node)
        return self.code

    def visit(self, node):
        method = getattr(self, f"visit_{type(node).__name__}")
        return method(node)

    def visit_Program(self, node: Program):
        for func in node.functions:
            self.visit(func)

    def visit_FunctionDef(self, node: FunctionDef):
        self.emit("func", node.name, "_", "_")
        self.visit(node.body)
        self.emit("endfunc", node.name, "_", "_")

    def visit_Block(self, node: Block):
        for stmt in node.statements:
            self.visit(stmt)

    def visit_VarDecl(self, node: VarDecl):
        self.emit("decl", node.var_type, "_", node.name)
        if node.init is not None:
            value = self.eval_expr(node.init)
            self.emit("=", value, "_", node.name)

    def visit_Assign(self, node: Assign):
        value = self.eval_expr(node.value)
        self.emit("=", value, "_", node.target.name)

    def visit_IfStmt(self, node: IfStmt):
        cond = self.eval_expr(node.condition)
        else_label = self.new_label()
        if node.else_branch is None:
            self.emit("jz", cond, "_", else_label)
            self.visit(node.then_branch)
            self.emit("label", "_", "_", else_label)
            return

        end_label = self.new_label()
        self.emit("jz", cond, "_", else_label)
        self.visit(node.then_branch)
        self.emit("jmp", "_", "_", end_label)
        self.emit("label", "_", "_", else_label)
        self.visit(node.else_branch)
        self.emit("label", "_", "_", end_label)

    def visit_WhileStmt(self, node: WhileStmt):
        start = self.new_label()
        end = self.new_label()
        self.emit("label", "_", "_", start)
        cond = self.eval_expr(node.condition)
        self.emit("jz", cond, "_", end)
        self.visit(node.body)
        self.emit("jmp", "_", "_", start)
        self.emit("label", "_", "_", end)

    def visit_ForStmt(self, node: ForStmt):
        start = self.new_label()
        end = self.new_label()
        if node.init is not None:
            if isinstance(node.init, (Assign, VarDecl)):
                self.visit(node.init)
            else:
                self.eval_expr(node.init)
        self.emit("label", "_", "_", start)
        if node.condition is not None:
            cond = self.eval_expr(node.condition)
            self.emit("jz", cond, "_", end)
        self.visit(node.body)
        if node.update is not None:
            if isinstance(node.update, Assign):
                self.visit(node.update)
            else:
                self.eval_expr(node.update)
        self.emit("jmp", "_", "_", start)
        self.emit("label", "_", "_", end)

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value is None:
            self.emit("ret", "_", "_", "_")
        else:
            value = self.eval_expr(node.value)
            self.emit("ret", value, "_", "_")

    def visit_ExprStmt(self, node: ExprStmt):
        self.eval_expr(node.expr)

    def eval_expr(self, node):
        method = getattr(self, f"eval_{type(node).__name__}", None)
        if method is None:
            raise TypeError(f"IR 暂不支持表达式：{type(node).__name__}")
        return method(node)

    def eval_Literal(self, node: Literal):
        return node.value

    def eval_Identifier(self, node: Identifier):
        return node.name

    def eval_UnaryExpr(self, node: UnaryExpr):
        if node.operator == "&" and isinstance(node.operand, Identifier):
            temp = self.new_temp()
            self.emit("addr", node.operand.name, "_", temp)
            return temp
        operand = self.eval_expr(node.operand)
        temp = self.new_temp()
        self.emit(f"u{node.operator}", operand, "_", temp)
        return temp

    def eval_BinaryExpr(self, node: BinaryExpr):
        left = self.eval_expr(node.left)
        right = self.eval_expr(node.right)
        temp = self.new_temp()
        self.emit(node.operator, left, right, temp)
        return temp

    def eval_CallExpr(self, node: CallExpr):
        if node.callee == "printf":
            if node.args:
                self.emit("print", self.eval_expr(node.args[0]), "_", "_")
            for arg in node.args[1:]:
                self.emit("print", self.eval_expr(arg), "_", "_")
            return "0"
        if node.callee == "scanf":
            for arg in node.args[1:]:
                target = self.scanf_target(arg)
                self.emit("read", "_", "_", target)
            return "0"
        temp = self.new_temp()
        self.emit("call", node.callee, len(node.args), temp)
        return temp

    def scanf_target(self, node):
        if isinstance(node, UnaryExpr) and node.operator == "&" and isinstance(node.operand, Identifier):
            return node.operand.name
        return self.eval_expr(node)
