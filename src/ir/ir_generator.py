"""四元式中间代码生成。

IR 生成器遍历 AST，把表达式、声明和控制流翻译成四元式。
条件和循环通过 label、jz、jnz、jmp 表示，便于后续生成汇编。
"""

from parser.ast_nodes import (
    Program, Include, StructDef, FunctionDef, Block, VarDecl, DeclStmt,
    InitializerList, Assign, IfStmt, WhileStmt, ForStmt, DoWhileStmt, BreakStmt, ContinueStmt,
    ReturnStmt, ExprStmt, EmptyStmt, CallExpr, BinaryExpr, UnaryExpr, Literal,
    Identifier, ArrayAccess, MemberAccess
)
from .quadruple import Quadruple


class IRGenerator:
    """AST 到四元式的转换器。"""

    def __init__(self):
        self.code = []           # 顺序存放所有四元式
        self.temp_id = 0         # 临时变量计数器
        self.label_id = 0        # 控制流标签计数器
        self.loop_stack = []     # 循环标签栈，break/continue 用
        self.struct_fields = {}  # 结构体名 -> 字段列表

    def new_temp(self):
        """生成临时变量名，如 t1、t2。"""

        self.temp_id += 1
        return f"t{self.temp_id}"

    def new_label(self):
        """生成控制流标签，如 L1、L2。"""

        self.label_id += 1
        return f"L{self.label_id}"

    def emit(self, op, arg1="_", arg2="_", result="_"):
        """追加一条四元式，并返回它在列表中的位置。"""

        self.code.append(Quadruple(op, str(arg1), str(arg2), str(result)))
        return len(self.code) - 1

    def backpatch(self, indices, label):
        """把之前暂缺的跳转目标补成真实标签。"""

        for idx in indices:
            self.code[idx].result = str(label)

    def generate(self, node):
        """入口：遍历 AST，返回四元式列表。"""

        self.visit(node)
        return self.code

    def visit(self, node):
        """按节点类型分派到对应的 visit_xxx。"""

        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise TypeError(f"IR 暂不支持节点：{type(node).__name__}")
        return method(node)

    # -------------------------------------------------------------------------
    # 程序级：include / 结构体 / 函数
    # -------------------------------------------------------------------------

    def visit_Program(self, node: Program):
        for include in node.includes:
            self.visit(include)
        for item in node.declarations:
            self.visit(item)

    def visit_Include(self, node: Include):
        self.emit("include", node.header or node.text, "_", "_")

    def visit_StructDef(self, node: StructDef):
        """发射结构体定义，结构体名存到 self.struct_fields 供初始化用。"""

        self.struct_fields[node.name] = node.fields
        self.emit("struct", node.name, "_", "_")
        for field in node.fields:
            self.emit("structfield", field.var_type, self.array_size_value(field), field.name)
        self.emit("endstruct", node.name, "_", "_")

    def visit_FunctionDef(self, node: FunctionDef):
        """函数入口：标记函数边界、逐个登记形参、翻译函数体。"""

        self.emit("func", node.name, node.return_type, len(node.params))
        for param in node.params:
            param_type = f"{param.param_type}[]" if param.is_array else param.param_type
            self.emit("param", param_type, "_", param.name)
        self.visit(node.body)
        self.emit("endfunc", node.name, "_", "_")

    # -------------------------------------------------------------------------
    # 块 / 声明
    # -------------------------------------------------------------------------

    def visit_Block(self, node: Block):
        for stmt in node.statements:
            self.visit(stmt)

    def visit_DeclStmt(self, node: DeclStmt):
        for decl in node.declarations:
            self.visit(decl)

    def visit_VarDecl(self, node: VarDecl):
        """生成变量声明四元式，并处理声明时的初始化。"""

        if node.is_array:
            self.emit("declarr", node.var_type, self.array_size_value(node), node.name)
        else:
            self.emit("decl", node.var_type, "_", node.name)
        if node.init is not None:
            self.emit_initializer(Identifier(node.name), node.var_type, node.is_array, node.init)

    def emit_initializer(self, target, target_type, is_array, init):
        """把初始化列表展开成普通赋值四元式。"""

        # 数组初始化 {1,2,3} → 逐元素赋给 target[0], target[1]...
        if is_array and isinstance(init, InitializerList):
            for index, value in enumerate(init.values):
                element = ArrayAccess(target, Literal(str(index), "int"))
                self.emit_initializer(element, target_type, False, value)
            return
        # 结构体初始化 {a, b, c} → 按字段名逐个赋值
        if isinstance(init, InitializerList):
            if not target_type.startswith("struct "):
                raise TypeError(f"IR 不支持的初始化列表目标：{target_type}")
            struct_name = target_type.split(" ", 1)[1]
            for field, value in zip(self.struct_fields.get(struct_name, []), init.values):
                self.emit_initializer(MemberAccess(target, field.name, False), field.var_type, field.is_array, value)
            return
        # 普通表达式：算出值再 store
        value = self.eval_expr(init)
        self.store_lvalue(target, value)

    # -------------------------------------------------------------------------
    # 赋值 / 控制流
    # -------------------------------------------------------------------------

    def visit_Assign(self, node: Assign):
        """普通赋值：先求右侧值，再写回左侧变量。"""

        value = self.eval_expr(node.value)
        self.store_lvalue(node.target, value)

    def visit_IfStmt(self, node: IfStmt):
        """if-else 用 jz 跳到 else / 结束标签，末尾 jmp 跳过 else 分支。"""

        cond = self.eval_expr(node.condition)
        false_jump = self.emit("jz", cond, "_", "_")
        if node.else_branch is None:
            self.visit(node.then_branch)
            end_label = self.new_label()
            self.emit("label", "_", "_", end_label)
            self.backpatch([false_jump], end_label)
            return
        # 有 else：then 完了要跳过 else
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
        """while 循环：start 标签 → 判条件 → 体 → jmp 回 start。"""

        start = self.new_label()
        end = self.new_label()
        self.emit("label", "_", "_", start)
        cond = self.eval_expr(node.condition)
        false_jump = self.emit("jz", cond, "_", "_")
        # 压栈让 break/continue 能找到对应出口
        self.loop_stack.append({"break": end, "continue": start})
        self.visit(node.body)
        self.loop_stack.pop()
        self.emit("jmp", "_", "_", start)
        self.emit("label", "_", "_", end)
        self.backpatch([false_jump], end)

    def visit_DoWhileStmt(self, node: DoWhileStmt):
        """do-while：先执行体，再判条件，jmp 回 start 而不是 cond_label。"""

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
        """for 循环拆成初始化 / 条件 / 循环体 / 更新四段。

        continue 跳到 update_label（不是 start），保证 continue 后
        先执行 i++ 再判条件。
        """

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
        """break 跳到最近一层循环的 end 标签。"""

        self.emit("jmp", "_", "_", self.loop_stack[-1]["break"])

    def visit_ContinueStmt(self, node: ContinueStmt):
        """continue 跳到最近一层循环的 continue 标签（while 是 start，for 是 update）。"""

        self.emit("jmp", "_", "_", self.loop_stack[-1]["continue"])

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value is None:
            self.emit("ret", "_", "_", "_")
        else:
            value = self.eval_expr(node.value)
            self.emit("ret", value, "_", "_")

    def visit_ExprStmt(self, node: ExprStmt):
        """表达式语句：求值但结果丢弃（可能产生副作用，如 i++）。"""

        self.eval_expr(node.expr)

    def visit_EmptyStmt(self, node: EmptyStmt):
        return None

    def visit_statement_or_expr(self, node):
        """for 头里的 init/update 既可能是声明也可能是表达式，分别处理。"""

        if isinstance(node, (Assign, VarDecl, DeclStmt)):
            self.visit(node)
        else:
            self.eval_expr(node)

    # -------------------------------------------------------------------------
    # 表达式求值：每条返回"代表这个值的名字"（变量名 / 常量 / 临时变量）
    # -------------------------------------------------------------------------

    def eval_expr(self, node):
        """表达式求值入口：返回变量名、常量或临时变量名。"""

        # 赋值表达式 `a = b` 当作表达式时返回左侧变量的引用
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
        """a[i] → 用 =[] 读出元素到临时变量。"""

        array_ref = self.lvalue_ref(node.array)
        index = self.eval_expr(node.index)
        temp = self.new_temp()
        self.emit("=[]", array_ref, index, temp)
        return temp

    def eval_MemberAccess(self, node: MemberAccess):
        """obj.member 或 obj->member → 用 field 读出到临时变量。"""

        obj_ref = self.lvalue_ref(node.obj)
        member = f"->{node.member}" if node.through_pointer else node.member
        temp = self.new_temp()
        self.emit("field", obj_ref, member, temp)
        return temp

    def eval_UnaryExpr(self, node: UnaryExpr):
        """一元运算：& 取地址、* 解引用、u++/u- 等带 u 前缀。"""

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
        # ++/-- 转成 u++/u-- 让 CodeGen 能识别副作用
        self.emit(f"u{node.operator}", operand, "_", temp)
        return temp

    def eval_BinaryExpr(self, node: BinaryExpr):
        """a OP b：先求两边得到名字，再发 (OP, a, b, t)。"""

        left = self.eval_expr(node.left)
        right = self.eval_expr(node.right)
        temp = self.new_temp()
        self.emit(node.operator, left, right, temp)
        return temp

    def eval_CallExpr(self, node: CallExpr):
        """函数调用：printf/scanf 特殊处理，其他按 arg/call 模板。"""

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

    # -------------------------------------------------------------------------
    # 存储 / 引用辅助
    # -------------------------------------------------------------------------

    def store_lvalue(self, target, value):
        """把计算结果写入左值，支持变量、数组、结构体字段和指针。"""

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
        """把左值节点变成可读/可写的字符串引用：a / a[i] / a.x / a->x / *p。"""

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
        """scanf 的参数要么是 &变量、要么是普通值（数组名等会 decay 成指针）。"""

        if isinstance(node, UnaryExpr) and node.operator == "&":
            return self.lvalue_ref(node.operand)
        return self.eval_expr(node)

    def array_size_value(self, node):
        """把数组大小节点转成字符串；非数组或未指定都返回 _。"""

        if not node.is_array:
            return "_"
        if node.array_size is None:
            return "_"
        if isinstance(node.array_size, Literal):
            return node.array_size.value
        return self.eval_expr(node.array_size)
