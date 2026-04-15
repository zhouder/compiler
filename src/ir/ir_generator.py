from parser.ast_nodes import (
    Program, Include, StructDef, FunctionDef, Block, VarDecl, DeclStmt,
    Assign, IfStmt, WhileStmt, ForStmt, DoWhileStmt, BreakStmt, ContinueStmt,
    ReturnStmt, ExprStmt, EmptyStmt, CallExpr, BinaryExpr, UnaryExpr, Literal,
    Identifier, ArrayAccess, MemberAccess
)
from .quadruple import Quadruple


class IRGenerator:
    def __init__(self):
        self.code = []
        self.temp_id = 0
        self.label_id = 0
        self.loop_stack = []

    def new_temp(self):
        self.temp_id += 1
        return f"t{self.temp_id}"

    def new_label(self):
        self.label_id += 1
        return f"L{self.label_id}"

    def emit(self, op, arg1="_", arg2="_", result="_"):
        self.code.append(Quadruple(op, str(arg1), str(arg2), str(result)))
        return len(self.code) - 1

    def backpatch(self, indices, label):
        for idx in indices:
            self.code[idx].result = str(label)

    def generate(self, node):
        self.visit(node)
        return self.code

    def visit(self, node):
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise TypeError(f"IR 暂不支持节点：{type(node).__name__}")
        return method(node)

    def visit_Program(self, node: Program):
        for include in node.includes:
            self.visit(include)
        for item in node.declarations:
            self.visit(item)

    def visit_Include(self, node: Include):
        self.emit("include", node.header or node.text, "_", "_")

    def visit_StructDef(self, node: StructDef):
        self.emit("struct", node.name, "_", "_")
        for field in node.fields:
            self.emit("structfield", field.var_type, self.array_size_value(field), field.name)
        self.emit("endstruct", node.name, "_", "_")

    def visit_FunctionDef(self, node: FunctionDef):
        self.emit("func", node.name, node.return_type, len(node.params))
        for param in node.params:
            param_type = f"{param.param_type}[]" if param.is_array else param.param_type
            self.emit("param", param_type, "_", param.name)
        self.visit(node.body)
        self.emit("endfunc", node.name, "_", "_")

    def visit_Block(self, node: Block):
        for stmt in node.statements:
            self.visit(stmt)

    def visit_DeclStmt(self, node: DeclStmt):
        for decl in node.declarations:
            self.visit(decl)

    def visit_VarDecl(self, node: VarDecl):
        if node.is_array:
            self.emit("declarr", node.var_type, self.array_size_value(node), node.name)
        else:
            self.emit("decl", node.var_type, "_", node.name)
        if node.init is not None:
            value = self.eval_expr(node.init)
            self.emit("=", value, "_", node.name)

    def visit_Assign(self, node: Assign):
        value = self.eval_expr(node.value)
        self.store_lvalue(node.target, value)

    def visit_IfStmt(self, node: IfStmt):
        cond = self.eval_expr(node.condition)
        false_jump = self.emit("jz", cond, "_", "_")
        if node.else_branch is None:
            self.visit(node.then_branch)
            end_label = self.new_label()
            self.emit("label", "_", "_", end_label)
            self.backpatch([false_jump], end_label)
            return
        self.visit(node.then_branch)
        end_jump = self.emit("jmp", "_", "_", "_")
        else_label = self.new_label()
        self.emit("label", "_", "_", else_label)
        self.backpatch([false_jump], else_label)
        self.visit(node.else_branch)
        end_label = self.new_label()
        self.emit("label", "_", "_", end_label)
        self.backpatch([end_jump], end_label)

    def visit_WhileStmt(self, node: WhileStmt):
        start = self.new_label()
        end = self.new_label()
        self.emit("label", "_", "_", start)
        cond = self.eval_expr(node.condition)
        false_jump = self.emit("jz", cond, "_", "_")
        self.loop_stack.append({"break": end, "continue": start})
        self.visit(node.body)
        self.loop_stack.pop()
        self.emit("jmp", "_", "_", start)
        self.emit("label", "_", "_", end)
        self.backpatch([false_jump], end)

    def visit_DoWhileStmt(self, node: DoWhileStmt):
        start = self.new_label()
        cond_label = self.new_label()
        end = self.new_label()
        self.emit("label", "_", "_", start)
        self.loop_stack.append({"break": end, "continue": cond_label})
        self.visit(node.body)
        self.loop_stack.pop()
        self.emit("label", "_", "_", cond_label)
        cond = self.eval_expr(node.condition)
        self.emit("jnz", cond, "_", start)
        self.emit("label", "_", "_", end)

    def visit_ForStmt(self, node: ForStmt):
        start = self.new_label()
        update_label = self.new_label()
        end = self.new_label()
        if node.init is not None:
            self.visit_statement_or_expr(node.init)
        self.emit("label", "_", "_", start)
        false_jump = None
        if node.condition is not None:
            cond = self.eval_expr(node.condition)
            false_jump = self.emit("jz", cond, "_", "_")
        self.loop_stack.append({"break": end, "continue": update_label})
        self.visit(node.body)
        self.loop_stack.pop()
        self.emit("label", "_", "_", update_label)
        if node.update is not None:
            self.visit_statement_or_expr(node.update)
        self.emit("jmp", "_", "_", start)
        self.emit("label", "_", "_", end)
        if false_jump is not None:
            self.backpatch([false_jump], end)

    def visit_BreakStmt(self, node: BreakStmt):
        self.emit("jmp", "_", "_", self.loop_stack[-1]["break"])

    def visit_ContinueStmt(self, node: ContinueStmt):
        self.emit("jmp", "_", "_", self.loop_stack[-1]["continue"])

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value is None:
            self.emit("ret", "_", "_", "_")
        else:
            value = self.eval_expr(node.value)
            self.emit("ret", value, "_", "_")

    def visit_ExprStmt(self, node: ExprStmt):
        self.eval_expr(node.expr)

    def visit_EmptyStmt(self, node: EmptyStmt):
        return None

    def visit_statement_or_expr(self, node):
        if isinstance(node, (Assign, VarDecl, DeclStmt)):
            self.visit(node)
        else:
            self.eval_expr(node)

    def eval_expr(self, node):
        if isinstance(node, Assign):
            self.visit_Assign(node)
            return self.lvalue_ref(node.target)
        method = getattr(self, f"eval_{type(node).__name__}", None)
        if method is None:
            raise TypeError(f"IR 暂不支持表达式：{type(node).__name__}")
        return method(node)

    def eval_Literal(self, node: Literal):
        return node.value

    def eval_Identifier(self, node: Identifier):
        return node.name

    def eval_ArrayAccess(self, node: ArrayAccess):
        array_ref = self.lvalue_ref(node.array)
        index = self.eval_expr(node.index)
        temp = self.new_temp()
        self.emit("=[]", array_ref, index, temp)
        return temp

    def eval_MemberAccess(self, node: MemberAccess):
        obj_ref = self.lvalue_ref(node.obj)
        member = f"->{node.member}" if node.through_pointer else node.member
        temp = self.new_temp()
        self.emit("field", obj_ref, member, temp)
        return temp

    def eval_UnaryExpr(self, node: UnaryExpr):
        if node.operator == "&":
            temp = self.new_temp()
            self.emit("addr", self.lvalue_ref(node.operand), "_", temp)
            return temp
        if node.operator == "*":
            pointer = self.eval_expr(node.operand)
            temp = self.new_temp()
            self.emit("loadptr", pointer, "_", temp)
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
            for arg in node.args:
                self.emit("print", self.eval_expr(arg), "_", "_")
            return "0"
        if node.callee == "scanf":
            for arg in node.args[1:]:
                target = self.scanf_target(arg)
                self.emit("read", "_", "_", target)
            return "0"
        for index, arg in enumerate(node.args):
            self.emit("arg", self.eval_expr(arg), "_", index)
        temp = self.new_temp()
        self.emit("call", node.callee, len(node.args), temp)
        return temp

    def store_lvalue(self, target, value):
        if isinstance(target, Identifier):
            self.emit("=", value, "_", target.name)
            return
        if isinstance(target, ArrayAccess):
            array_ref = self.lvalue_ref(target.array)
            index = self.eval_expr(target.index)
            self.emit("[]=", value, index, array_ref)
            return
        if isinstance(target, MemberAccess):
            obj_ref = self.lvalue_ref(target.obj)
            member = f"->{target.member}" if target.through_pointer else target.member
            self.emit("field=", value, member, obj_ref)
            return
        if isinstance(target, UnaryExpr) and target.operator == "*":
            pointer = self.eval_expr(target.operand)
            self.emit("storeptr", value, "_", pointer)
            return
        raise TypeError(f"IR 不支持的赋值目标：{type(target).__name__}")

    def lvalue_ref(self, node):
        if isinstance(node, Identifier):
            return node.name
        if isinstance(node, ArrayAccess):
            array_ref = self.lvalue_ref(node.array)
            index = self.eval_expr(node.index)
            return f"{array_ref}[{index}]"
        if isinstance(node, MemberAccess):
            obj_ref = self.lvalue_ref(node.obj)
            op = "->" if node.through_pointer else "."
            return f"{obj_ref}{op}{node.member}"
        if isinstance(node, UnaryExpr) and node.operator == "*":
            return f"*{self.eval_expr(node.operand)}"
        raise TypeError(f"IR 不支持的左值：{type(node).__name__}")

    def scanf_target(self, node):
        if isinstance(node, UnaryExpr) and node.operator == "&":
            return self.lvalue_ref(node.operand)
        return self.eval_expr(node)

    def array_size_value(self, node):
        if not node.is_array:
            return "_"
        if node.array_size is None:
            return "_"
        if isinstance(node.array_size, Literal):
            return node.array_size.value
        return self.eval_expr(node.array_size)
