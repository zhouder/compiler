from parser.ast_nodes import (
    Program, Include, StructDef, Param, FunctionDef, Block, VarDecl, DeclStmt,
    Assign, IfStmt, WhileStmt, ForStmt, DoWhileStmt, BreakStmt, ContinueStmt,
    ReturnStmt, ExprStmt, EmptyStmt, CallExpr, BinaryExpr, UnaryExpr, Literal,
    Identifier, ArrayAccess, MemberAccess
)
from .symbol_table import SymbolTable, SemanticError


NUMERIC_TYPES = {"int", "char", "float"}
BUILTIN_TYPES = NUMERIC_TYPES | {"void"}


class SemanticAnalyzer:
    def __init__(self):
        self.symbols = SymbolTable()
        self.structs = {}
        self.functions = {}
        self.current_return_type = None
        self.loop_depth = 0

    def analyze(self, node):
        self.visit(node)
        return self.symbols

    def visit(self, node):
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise SemanticError(f"未实现的语义分析节点：{type(node).__name__}")
        return method(node)

    def visit_Program(self, node: Program):
        for item in node.declarations:
            if isinstance(item, StructDef):
                self.register_struct(item)
        for item in node.declarations:
            if isinstance(item, FunctionDef):
                self.register_function(item)
        for item in node.declarations:
            if not isinstance(item, (StructDef, FunctionDef)):
                self.visit(item)
        for item in node.declarations:
            if isinstance(item, FunctionDef):
                self.visit(item)

    def visit_Include(self, node: Include):
        return None

    def register_struct(self, node: StructDef):
        if node.name in self.structs:
            raise SemanticError(f"重复定义结构体：{node.name}")
        fields = {}
        for field in node.fields:
            if field.name in fields:
                raise SemanticError(f"结构体 {node.name} 中字段重复定义：{field.name}")
            self.ensure_valid_decl_type(field.var_type, field.name)
            fields[field.name] = self.make_symbol_info(field, kind="field")
        self.structs[node.name] = {"kind": "struct", "fields": fields}

    def register_function(self, node: FunctionDef):
        if node.name in self.functions:
            raise SemanticError(f"重复定义函数：{node.name}")
        self.ensure_valid_return_type(node.return_type, node.name)
        params = []
        names = set()
        for param in node.params:
            if param.name in names:
                raise SemanticError(f"函数 {node.name} 参数重复定义：{param.name}")
            names.add(param.name)
            self.ensure_valid_decl_type(param.param_type, param.name)
            params.append({
                "name": param.name,
                "type": self.decay_array_type(param.param_type, param.is_array),
                "is_array": param.is_array,
                "array_size": param.array_size,
            })
        info = {"kind": "function", "return_type": node.return_type, "params": params}
        self.functions[node.name] = info
        self.symbols.define_global(node.name, info)

    def visit_StructDef(self, node: StructDef):
        return None

    def visit_FunctionDef(self, node: FunctionDef):
        previous_return_type = self.current_return_type
        self.current_return_type = node.return_type
        self.symbols.push()
        for param in node.params:
            param_type = self.decay_array_type(param.param_type, param.is_array)
            self.symbols.define(param.name, {
                "kind": "param",
                "type": param_type,
                "declared_type": param.param_type,
                "is_array": False,
                "array_size": param.array_size,
            })
        self.visit(node.body)
        self.symbols.pop()
        self.current_return_type = previous_return_type

    def visit_Block(self, node: Block):
        self.symbols.push()
        for stmt in node.statements:
            self.visit(stmt)
        self.symbols.pop()

    def visit_DeclStmt(self, node: DeclStmt):
        for decl in node.declarations:
            self.visit(decl)

    def visit_VarDecl(self, node: VarDecl):
        self.ensure_valid_decl_type(node.var_type, node.name)
        if node.var_type == "void":
            raise SemanticError(f"变量不能声明为 void：{node.name}")
        if node.is_array:
            self.ensure_array_size(node)
            if node.init is not None:
                raise SemanticError(f"当前版本暂不支持数组初始化：{node.name}")
        self.symbols.define(node.name, self.make_symbol_info(node, kind="var"))
        if node.init is not None:
            rhs_type = self.visit(node.init)
            self.ensure_assignable(node.var_type, rhs_type, node.name)

    def visit_Assign(self, node: Assign):
        lhs_type = self.lvalue_type(node.target)
        rhs_type = self.visit(node.value)
        self.ensure_assignable(lhs_type, rhs_type, self.describe_lvalue(node.target))
        return lhs_type

    def visit_IfStmt(self, node: IfStmt):
        self.ensure_condition(node.condition, "if")
        self.visit(node.then_branch)
        if node.else_branch is not None:
            self.visit(node.else_branch)

    def visit_WhileStmt(self, node: WhileStmt):
        self.ensure_condition(node.condition, "while")
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1

    def visit_DoWhileStmt(self, node: DoWhileStmt):
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1
        self.ensure_condition(node.condition, "do-while")

    def visit_ForStmt(self, node: ForStmt):
        self.symbols.push()
        if node.init is not None:
            self.visit(node.init)
        if node.condition is not None:
            self.ensure_condition(node.condition, "for")
        if node.update is not None:
            self.visit(node.update)
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1
        self.symbols.pop()

    def visit_BreakStmt(self, node: BreakStmt):
        if self.loop_depth <= 0:
            raise SemanticError("break 只能出现在循环语句中")

    def visit_ContinueStmt(self, node: ContinueStmt):
        if self.loop_depth <= 0:
            raise SemanticError("continue 只能出现在循环语句中")

    def visit_ReturnStmt(self, node: ReturnStmt):
        if self.current_return_type is None:
            raise SemanticError("return 不能出现在函数外")
        if node.value is None:
            if self.current_return_type != "void":
                raise SemanticError(f"非 void 函数必须返回 {self.current_return_type} 类型的值")
            return "void"
        value_type = self.visit(node.value)
        if self.current_return_type == "void":
            raise SemanticError("void 函数不能返回值")
        self.ensure_assignable(self.current_return_type, value_type, "return")
        return self.current_return_type

    def visit_ExprStmt(self, node: ExprStmt):
        return self.visit(node.expr)

    def visit_EmptyStmt(self, node: EmptyStmt):
        return "void"

    def visit_CallExpr(self, node: CallExpr):
        if node.callee == "printf":
            if not node.args:
                raise SemanticError("printf 至少需要一个格式字符串参数")
            for arg in node.args:
                self.visit(arg)
            return "int"
        if node.callee == "scanf":
            if not node.args or not isinstance(node.args[0], Literal) or node.args[0].literal_type != "string":
                raise SemanticError("scanf 的第一个参数必须是格式字符串")
            for arg in node.args[1:]:
                self.ensure_scanf_target(arg)
            return "int"
        info = self.symbols.lookup(node.callee)
        if info is None or info.get("kind") != "function":
            raise SemanticError(f"函数未定义：{node.callee}")
        params = info["params"]
        if len(params) != len(node.args):
            raise SemanticError(f"函数 {node.callee} 参数数量不匹配：需要 {len(params)} 个，得到 {len(node.args)} 个")
        for param, arg in zip(params, node.args):
            arg_type = self.visit(arg)
            self.ensure_assignable(param["type"], arg_type, f"参数 {param['name']}")
        return info["return_type"]

    def visit_BinaryExpr(self, node: BinaryExpr):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        if node.operator in ("<", "<=", ">", ">=", "==", "!="):
            if self.compatible_for_compare(left_type, right_type):
                return "int"
            raise SemanticError(f"关系表达式类型不兼容：{left_type} {node.operator} {right_type}")
        if node.operator in ("&&", "||"):
            self.ensure_scalar(left_type, "逻辑表达式左操作数")
            self.ensure_scalar(right_type, "逻辑表达式右操作数")
            return "int"
        if node.operator in ("+", "-") and self.is_pointer(left_type) and right_type in NUMERIC_TYPES:
            return left_type
        if node.operator == "+" and self.is_pointer(right_type) and left_type in NUMERIC_TYPES:
            return right_type
        if left_type == "float" or right_type == "float":
            if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
                return "float"
        if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
            return "int"
        raise SemanticError(f"不支持的二元表达式类型：{left_type} {node.operator} {right_type}")

    def visit_UnaryExpr(self, node: UnaryExpr):
        if node.operator == "&":
            operand_type = self.lvalue_type(node.operand, allow_array_name=True)
            return f"{operand_type}*"
        if node.operator == "*":
            operand_type = self.visit(node.operand)
            if not self.is_pointer(operand_type):
                raise SemanticError(f"* 只能作用于指针类型，得到 {operand_type}")
            return self.strip_pointer(operand_type)
        operand_type = self.visit(node.operand)
        if node.operator == "!":
            self.ensure_scalar(operand_type, "! 操作数")
            return "int"
        if node.operator in ("+", "-"):
            if operand_type not in NUMERIC_TYPES:
                raise SemanticError(f"一元 {node.operator} 只能作用于数值类型，得到 {operand_type}")
            return operand_type
        return operand_type

    def visit_Literal(self, node: Literal):
        return node.literal_type

    def visit_Identifier(self, node: Identifier):
        symbol = self.require_value_symbol(node.name)
        if symbol.get("is_array"):
            return self.decay_array_type(symbol["type"], True)
        return symbol["type"]

    def visit_ArrayAccess(self, node: ArrayAccess):
        array_type = self.visit(node.array)
        index_type = self.visit(node.index)
        if index_type not in ("int", "char"):
            raise SemanticError(f"数组下标必须是整数类型，得到 {index_type}")
        if not self.is_pointer(array_type):
            raise SemanticError(f"数组访问对象必须是数组或指针类型，得到 {array_type}")
        return self.strip_pointer(array_type)

    def visit_MemberAccess(self, node: MemberAccess):
        struct_name = self.member_struct_name(node)
        fields = self.structs[struct_name]["fields"]
        if node.member not in fields:
            raise SemanticError(f"结构体 {struct_name} 没有字段：{node.member}")
        field = fields[node.member]
        if field.get("is_array"):
            return self.decay_array_type(field["type"], True)
        return field["type"]

    def lvalue_type(self, node, allow_array_name=False):
        if isinstance(node, Identifier):
            symbol = self.require_value_symbol(node.name)
            if symbol.get("is_array") and not allow_array_name:
                raise SemanticError(f"不能给数组名整体赋值：{node.name}")
            return symbol["type"]
        if isinstance(node, ArrayAccess):
            return self.visit_ArrayAccess(node)
        if isinstance(node, MemberAccess):
            return self.member_lvalue_type(node, allow_array_name)
        if isinstance(node, UnaryExpr) and node.operator == "*":
            typ = self.visit(node.operand)
            if not self.is_pointer(typ):
                raise SemanticError(f"* 赋值目标必须是指针类型，得到 {typ}")
            return self.strip_pointer(typ)
        raise SemanticError(f"非法赋值目标：{type(node).__name__}")

    def member_lvalue_type(self, node, allow_array_name=False):
        struct_name = self.member_struct_name(node)
        fields = self.structs[struct_name]["fields"]
        if node.member not in fields:
            raise SemanticError(f"结构体 {struct_name} 没有字段：{node.member}")
        field = fields[node.member]
        if field.get("is_array") and not allow_array_name:
            raise SemanticError(f"不能给数组字段整体赋值：{node.member}")
        return field["type"]

    def member_struct_name(self, node):
        obj_type = self.visit(node.obj)
        if node.through_pointer:
            if not self.is_pointer(obj_type):
                raise SemanticError(f"-> 左侧必须是结构体指针，得到 {obj_type}")
            obj_type = self.strip_pointer(obj_type)
        if not obj_type.startswith("struct "):
            raise SemanticError(f"成员访问左侧必须是结构体类型，得到 {obj_type}")
        struct_name = obj_type.split(" ", 1)[1]
        if struct_name not in self.structs:
            raise SemanticError(f"结构体未定义：{struct_name}")
        return struct_name

    def require_value_symbol(self, name):
        symbol = self.symbols.lookup(name)
        if symbol is None:
            raise SemanticError(f"变量未定义：{name}")
        if symbol.get("kind") == "function":
            raise SemanticError(f"函数名不能作为变量使用：{name}")
        return symbol

    def make_symbol_info(self, node, kind):
        return {
            "kind": kind,
            "type": node.var_type,
            "is_array": node.is_array,
            "array_size": node.array_size,
        }

    def ensure_array_size(self, node: VarDecl):
        if node.array_size is None:
            raise SemanticError(f"数组必须声明长度：{node.name}")
        size_type = self.visit(node.array_size)
        if size_type != "int":
            raise SemanticError(f"数组长度必须是整数常量或整数表达式：{node.name}")
        if isinstance(node.array_size, Literal):
            try:
                if int(node.array_size.value, 0) <= 0:
                    raise SemanticError(f"数组长度必须大于 0：{node.name}")
            except ValueError as exc:
                raise SemanticError(f"数组长度非法：{node.name}") from exc

    def ensure_valid_decl_type(self, typ, name):
        base = self.base_non_pointer_type(typ)
        if base in BUILTIN_TYPES:
            return
        if base.startswith("struct "):
            struct_name = base.split(" ", 1)[1]
            if struct_name in self.structs:
                return
        raise SemanticError(f"未知类型 {typ}：{name}")

    def ensure_valid_return_type(self, typ, name):
        self.ensure_valid_decl_type(typ, name)

    def ensure_condition(self, expr, context):
        typ = self.visit(expr)
        self.ensure_scalar(typ, f"{context} 条件")

    def ensure_scalar(self, typ, name):
        if typ in NUMERIC_TYPES or self.is_pointer(typ):
            return
        raise SemanticError(f"{name} 必须是标量类型，得到 {typ}")

    def ensure_assignable(self, lhs_type, rhs_type, name):
        if lhs_type == rhs_type:
            return
        if lhs_type == "float" and rhs_type in ("int", "char"):
            return
        if lhs_type == "int" and rhs_type == "char":
            return
        if self.is_pointer(lhs_type) and rhs_type == "int":
            return
        raise SemanticError(f"类型不匹配：不能把 {rhs_type} 赋值给 {lhs_type}：{name}")

    def ensure_scanf_target(self, node):
        if isinstance(node, UnaryExpr) and node.operator == "&":
            self.lvalue_type(node.operand, allow_array_name=True)
            return
        raise SemanticError("scanf 的输入参数必须是 &变量、&数组元素或 &结构体字段")

    def compatible_for_compare(self, left_type, right_type):
        if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
            return True
        if self.is_pointer(left_type) and self.is_pointer(right_type):
            return True
        return left_type == right_type

    def is_pointer(self, typ):
        return typ.endswith("*")

    def strip_pointer(self, typ):
        return typ[:-1] if self.is_pointer(typ) else typ

    def base_non_pointer_type(self, typ):
        while typ.endswith("*"):
            typ = typ[:-1]
        return typ

    def decay_array_type(self, typ, is_array):
        return f"{typ}*" if is_array else typ

    def describe_lvalue(self, node):
        if isinstance(node, Identifier):
            return node.name
        if isinstance(node, ArrayAccess):
            return "数组元素"
        if isinstance(node, MemberAccess):
            return f"成员 {node.member}"
        if isinstance(node, UnaryExpr) and node.operator == "*":
            return "指针解引用"
        return type(node).__name__
