"""目标汇编代码生成。

本模块把四元式翻译成 ML615/MASM 风格的 16 位 DOS 汇编。
为了让课程设计演示更直观，变量和结构体字段都放在数据段中管理。
"""


class CodeGenerator:
    """四元式到汇编文本的转换器。"""

    def __init__(self):
        self.reset()

    def reset(self):
        """清空所有缓存：元信息、数据段、代码段、临时状态。"""

        # 元信息（由 collect_metadata 填充）
        self.struct_fields = {}     # 结构体名 -> 字段列表
        self.func_params = {}       # 函数名 -> 形参列表
        self.func_returns = {}      # 函数名 -> 返回类型
        self.scoped_symbols = {}    # 函数名 -> 作用域符号集
        self.array_params = set()   # 形参是"数组指针"的名字
        # 数据段输出
        self.data_defs = []
        self.data_names = set()     # 已声明过的符号，避免重复
        self.string_defs = []
        self.string_id = 0
        # 代码段输出
        self.cmp_label_id = 0
        self.code_lines = []
        # 翻译过程上下文
        self.current_func = None
        self.pending_args = []      # (位置, 实参)，call 时按序赋给形参
        self.pending_printf = None  # 等下一个 print 把数值补上

    def generate(self, ir_list):
        """代码生成入口，返回完整 ASM 文本。"""

        self.reset()
        # 三遍扫：摸家底 → 挖坑 → 翻译
        self.collect_metadata(ir_list)
        self.collect_storage(ir_list)
        self.emit_code(ir_list)

        # 套上 MASM 模板：模式、栈、数据段、start 入口、退出中断
        out = [
            "; ML615 / MASM 16-bit DOS assembly",
            ".MODEL SMALL",
            ".STACK 100h",
            ".DATA",
        ]
        out.extend(self.data_defs or ["; no variables"])
        out.extend(self.string_defs)
        out.extend([
            ".CODE",
            "start:",
            "    MOV AX, @DATA",
            "    MOV DS, AX",
            "    CALL main",
            "    MOV AX, 4C00h",
            "    INT 21h",
        ])
        out.extend(self.code_lines)
        out.extend(self.runtime_library())
        out.append("END start")
        return "\n".join(out)

    # -------------------------------------------------------------------------
    # 第 1 遍：摸清结构体和函数家底
    # -------------------------------------------------------------------------

    def collect_metadata(self, ir_list):
        """预扫描结构体和函数信息，供后续分配存储和传参使用。"""

        current_struct = None
        current_func = None
        for q in ir_list:
            if q.op == "struct":
                current_struct = q.arg1
                self.struct_fields[current_struct] = []
            elif q.op == "structfield" and current_struct:
                self.struct_fields[current_struct].append({
                    "type": q.arg1,
                    "name": q.result,
                    "array_size": None if q.arg2 == "_" else q.arg2,
                })
            elif q.op == "endstruct":
                current_struct = None
            elif q.op == "func":
                current_func = q.arg1
                self.func_returns[current_func] = q.arg2
                self.func_params[current_func] = []
                self.scoped_symbols.setdefault(current_func, set())
            elif q.op == "param" and current_func:
                info = {"type": q.arg1, "name": q.result}
                self.func_params[current_func].append(info)
                self.scoped_symbols.setdefault(current_func, set()).add(q.result)
            elif q.op == "endfunc":
                current_func = None

    # -------------------------------------------------------------------------
    # 第 2 遍：数据段挖坑
    # -------------------------------------------------------------------------

    def collect_storage(self, ir_list):
        """根据声明和临时变量提前生成数据段定义。"""

        current_func = None
        for q in ir_list:
            if q.op == "func":
                current_func = q.arg1
            elif q.op == "endfunc":
                current_func = None
            elif q.op == "param" and current_func:
                self.declare_param(current_func, q.arg1, q.result)
            elif q.op == "decl":
                self.declare_variable(current_func, q.arg1, q.result)
            elif q.op == "declarr":
                self.scoped_symbols.setdefault(current_func, set()).add(q.result)
                if q.arg1.startswith("struct "):
                    # 结构体数组要为每个元素的每个字段各挖一个坑
                    self.declare_struct_array(current_func, q.arg1, q.result, q.arg2)
                else:
                    self.declare_array(self.scoped_name(current_func, q.result), q.arg2, q.arg1)

            # 临时变量 t1/t2/... 也提前登记
            for value in (q.arg1, q.arg2, q.result):
                if self.is_temp(value):
                    self.declare_word(self.safe(value), "temp")

    def declare_param(self, func, typ, name):
        """为形参挖坑；数组形参是 16 位指针，结构体形参拆成多个字段。"""

        self.scoped_symbols.setdefault(func, set()).add(name)
        if typ.endswith("[]"):
            scoped = self.scoped_name(func, name)
            self.array_params.add(scoped)
            self.declare_word(scoped, f"{typ} pointer")
            return
        if typ.startswith("struct "):
            self.declare_struct_object(func, typ, name)
            return
        self.declare_word(self.scoped_name(func, name), typ)

    def declare_variable(self, func, typ, name):
        """为普通变量或结构体变量挖坑。"""

        if name == "_":
            return
        self.scoped_symbols.setdefault(func, set()).add(name)
        if typ.startswith("struct "):
            self.declare_struct_object(func, typ, name)
            return
        self.declare_word(self.scoped_name(func, name), typ)

    def declare_struct_object(self, func, typ, name):
        """为结构体变量的每个字段挖独立坑（p.x、p.y 这种）。"""

        struct_name = typ.split(" ", 1)[1]
        fields = self.struct_fields.get(struct_name, [])
        if not fields:
            self.declare_word(self.scoped_name(func, name), typ)
            return
        for field in fields:
            self.declare_struct_field_storage(func, name, typ, field)

    def declare_struct_array(self, func, typ, name, size):
        """为结构体数组的每个元素字段分配独立存储。"""

        struct_name = typ.split(" ", 1)[1]
        fields = self.struct_fields.get(struct_name, [])
        size = int(self.integer_literal(size))
        if not fields:
            self.declare_array(self.scoped_name(func, name), size, typ)
            return
        for index in range(size):
            element = f"{name}[{index}]"
            for field in fields:
                self.declare_struct_field_storage(func, element, f"{typ}[{index}]", field)

    def declare_struct_field_storage(self, func, base_name, owner_desc, field):
        """为结构体的一个字段挖坑，数组字段用 DUP。"""

        symbol = self.field_symbol(func, base_name, field["name"])
        comment = f"{owner_desc}.{field['name']}"
        array_size = field.get("array_size")
        if array_size not in (None, "_"):
            self.declare_array(symbol, array_size, comment)
            return
        self.declare_word(symbol, comment)

    def declare_word(self, name, comment="word"):
        """挖一个 16 位 word 坑。"""

        name = self.safe(name)
        if name in self.data_names:
            return
        self.data_names.add(name)
        self.data_defs.append(f"{name} DW ? ; {comment}")

    def declare_array(self, name, size, comment="array"):
        """挖一个数组坑。"""

        name = self.safe(name)
        if name in self.data_names:
            return
        self.data_names.add(name)
        size = self.integer_literal(size)
        self.data_defs.append(f"{name} DW {size} DUP (?) ; {comment}[]")

    # -------------------------------------------------------------------------
    # 第 3 遍：一条四元式翻成若干条汇编
    # -------------------------------------------------------------------------

    def emit_code(self, ir_list):
        """逐条翻译四元式为汇编指令。"""

        self.current_func = None
        for q in ir_list:
            op, a1, a2, res = q.op, q.arg1, q.arg2, q.result
            if op == "include":
                self.line(f"; include {a1}")
            elif op in ("struct", "structfield", "endstruct"):
                self.line(f"; {op} {a1} {a2} {res}")
            elif op == "func":
                # 函数开始：起 PROC 标签
                self.current_func = a1
                self.pending_args = []
                self.pending_printf = None
                self.line("")
                self.line(f"{self.safe(a1)} PROC")
                self.line(f"    ; return {a2}, params {res}")
            elif op == "endfunc":
                self.line("    RET")
                self.line(f"{self.safe(a1)} ENDP")
                self.current_func = None
            elif op == "label":
                self.line(f"{res}:")
            elif op in ("decl", "declarr"):
                self.line(f"    ; var {res} : {a1}")
            elif op == "param":
                self.line(f"    ; param {res} : {a1}")
            elif op == "=":
                self.load_ax(a1)
                self.store_ax(res)
            elif op in ("+", "-", "*", "/", "%"):
                self.emit_arithmetic(op, a1, a2, res)
            elif op in ("<", "<=", ">", ">=", "==", "!="):
                self.emit_compare(op, a1, a2, res)
            elif op == "&&":
                self.emit_logical_and(a1, a2, res)
            elif op == "||":
                self.emit_logical_or(a1, a2, res)
            elif op == "u-":
                self.load_ax(a1)
                self.line("    NEG AX")
                self.store_ax(res)
            elif op == "u+":
                self.load_ax(a1)
                self.store_ax(res)
            elif op == "u!":
                self.emit_not(a1, res)
            elif op in ("u++", "u--"):
                # 自增/自减：先改原变量，再把结果存到 t
                self.load_ax(a1)
                self.line("    INC AX" if op == "u++" else "    DEC AX")
                self.store_ax(a1)
                self.store_ax(res)
            elif op == "addr":
                self.line(f"    LEA AX, {self.memory_ref(a1)}")
                self.store_ax(res)
            elif op == "=[]":
                self.load_array_element(a1, a2)
                self.store_ax(res)
            elif op == "[]=":
                self.load_ax(a1)
                self.store_array_element(res, a2)
            elif op == "field":
                self.load_ax(self.member_ref(a1, a2))
                self.store_ax(res)
            elif op == "field=":
                self.load_ax(a1)
                self.store_ax(self.member_ref(res, a2))
            elif op == "loadptr":
                self.load_ax(a1)
                self.line("    MOV SI, AX")
                self.line("    MOV AX, [SI]")
                self.store_ax(res)
            elif op == "storeptr":
                self.load_ax(res)
                self.line("    MOV SI, AX")
                self.load_ax(a1)
                self.line("    MOV [SI], AX")
            elif op == "jz":
                self.load_ax(a1)
                self.line("    CMP AX, 0")
                self.line(f"    JE {res}")
            elif op == "jnz":
                self.load_ax(a1)
                self.line("    CMP AX, 0")
                self.line(f"    JNE {res}")
            elif op == "jmp":
                self.line(f"    JMP {res}")
            elif op == "print":
                self.emit_print(a1)
            elif op == "read":
                self.emit_read(res)
            elif op == "arg":
                # 函数实参先攒起来，call 时按序赋给形参
                self.pending_args.append((int(res), a1))
            elif op == "call":
                self.emit_call(a1, a2, res)
            elif op == "ret":
                if a1 != "_":
                    self.load_ax(a1)
                self.line("    RET")
            else:
                self.line(f"    ; unsupported {op} {a1} {a2} {res}")

    def emit_arithmetic(self, op, left, right, result):
        """整数算术：load left → 运算 → store result。"""

        if op == "+":
            self.load_ax(left)
            self.line(f"    ADD AX, {self.source_ref(right)}")
            self.store_ax(result)
        elif op == "-":
            self.load_ax(left)
            self.line(f"    SUB AX, {self.source_ref(right)}")
            self.store_ax(result)
        elif op == "*":
            # 8086 乘法必须用 BX 乘 AX
            self.load_ax(left)
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IMUL BX")
            self.store_ax(result)
        elif op == "/":
            # CWD 把 AX 符号扩展到 DX，IDIV 后 AX=商 DX=余数
            self.load_ax(left)
            self.line("    CWD")
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IDIV BX")
            self.store_ax(result)
        elif op == "%":
            # 取余：除完后取 DX
            self.load_ax(left)
            self.line("    CWD")
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IDIV BX")
            self.line("    MOV AX, DX")
            self.store_ax(result)

    def emit_compare(self, op, left, right, result):
        """比较统一生成 0/1 结果：先置 0，为真再置 1。"""

        true_label = self.new_internal_label("CMP_TRUE")
        end_label = self.new_internal_label("CMP_END")
        jump_map = {
            "<": "JL", "<=": "JLE", ">": "JG", ">=": "JGE",
            "==": "JE", "!=": "JNE",
        }
        self.line("    MOV AX, 0")
        self.store_ax(result)
        self.load_ax(left)
        self.line(f"    CMP AX, {self.source_ref(right)}")
        self.line(f"    {jump_map[op]} {true_label}")
        self.line(f"    JMP {end_label}")
        self.line(f"{true_label}:")
        self.line("    MOV AX, 1")
        self.store_ax(result)
        self.line(f"{end_label}:")

    def emit_logical_and(self, left, right, result):
        """a && b：任一为 0 则结果 0。"""

        end_label = self.new_internal_label("AND_END")
        self.line("    MOV AX, 0")
        self.store_ax(result)
        self.load_ax(left)
        self.line("    CMP AX, 0")
        self.line(f"    JE {end_label}")
        self.load_ax(right)
        self.line("    CMP AX, 0")
        self.line(f"    JE {end_label}")
        self.line("    MOV AX, 1")
        self.store_ax(result)
        self.line(f"{end_label}:")

    def emit_logical_or(self, left, right, result):
        """a || b：任一非 0 则结果 1。"""

        true_label = self.new_internal_label("OR_TRUE")
        end_label = self.new_internal_label("OR_END")
        self.line("    MOV AX, 0")
        self.store_ax(result)
        self.load_ax(left)
        self.line("    CMP AX, 0")
        self.line(f"    JNE {true_label}")
        self.load_ax(right)
        self.line("    CMP AX, 0")
        self.line(f"    JNE {true_label}")
        self.line(f"    JMP {end_label}")
        self.line(f"{true_label}:")
        self.line("    MOV AX, 1")
        self.store_ax(result)
        self.line(f"{end_label}:")

    def emit_not(self, value, result):
        """u!x：x==0 返 1，否则返 0。"""

        true_label = self.new_internal_label("NOT_TRUE")
        end_label = self.new_internal_label("NOT_END")
        self.line("    MOV AX, 0")
        self.store_ax(result)
        self.load_ax(value)
        self.line("    CMP AX, 0")
        self.line(f"    JE {true_label}")
        self.line(f"    JMP {end_label}")
        self.line(f"{true_label}:")
        self.line("    MOV AX, 1")
        self.store_ax(result)
        self.line(f"{end_label}:")

    def load_array_element(self, array_name, index):
        """读 a[i]：普通数组 [a+BX]，数组形参 SI 间接寻址。"""

        self.emit_index_to_bx(index)
        base = self.memory_ref(array_name)
        if base in self.array_params:
            self.line(f"    MOV SI, {base}")
            self.line("    ADD SI, BX")
            self.line("    MOV AX, [SI]")
        else:
            self.line(f"    MOV AX, {base}[BX]")

    def store_array_element(self, array_name, index):
        """写 a[i] = t：先 PUSH 保住 AX，算好 BX 再 POP。"""

        self.line("    PUSH AX")
        self.emit_index_to_bx(index)
        base = self.memory_ref(array_name)
        self.line("    POP AX")
        if base in self.array_params:
            self.line(f"    MOV SI, {base}")
            self.line("    ADD SI, BX")
            self.line("    MOV [SI], AX")
        else:
            self.line(f"    MOV {base}[BX], AX")

    def emit_index_to_bx(self, index):
        """下标装 BX 并左移一位（*2 = 元素宽度）。"""

        self.load_ax(index)
        self.line("    MOV BX, AX")
        self.line("    SHL BX, 1")

    def emit_print(self, value):
        """处理 printf 的格式串和对应输出值。"""

        if self.is_string_literal(value):
            text = self.decode_string(value)
            segments = self.parse_format(text)
            if any(kind == "spec" for kind, _ in segments):
                # 有 %d 等格式符：挂起状态机，先打 % 之前的字面量
                self.pending_printf = {"segments": segments, "pos": 0}
                self.emit_pending_literals()
            else:
                self.emit_string(text)
            return

        if self.pending_printf:
            spec = self.next_printf_spec()
            self.emit_print_value(value, spec)
            self.emit_pending_literals()
            return

        self.emit_print_value(value, "d")

    def emit_pending_literals(self):
        """把 pending_printf 当前到下一个格式符之间的字面量都打完。"""

        while self.pending_printf and self.pending_printf["pos"] < len(self.pending_printf["segments"]):
            kind, value = self.pending_printf["segments"][self.pending_printf["pos"]]
            if kind != "lit":
                break
            if value:
                self.emit_string(value)
            self.pending_printf["pos"] += 1
        if self.pending_printf and self.pending_printf["pos"] >= len(self.pending_printf["segments"]):
            self.pending_printf = None

    def next_printf_spec(self):
        """取下一个待消费的格式符。"""

        if not self.pending_printf:
            return "d"
        segments = self.pending_printf["segments"]
        pos = self.pending_printf["pos"]
        if pos < len(segments) and segments[pos][0] == "spec":
            self.pending_printf["pos"] += 1
            return segments[pos][1]
        return "d"

    def emit_print_value(self, value, spec):
        """按格式符输出：d/i 走 PRINT_INT，c 走 PRINT_CHAR，s 走 PRINT_STR。"""

        if spec in ("d", "i", "f"):
            self.load_ax(value)
            self.line("    CALL PRINT_INT")
        elif spec == "c":
            self.load_ax(value)
            self.line("    MOV DL, AL")
            self.line("    CALL PRINT_CHAR")
        elif spec == "s" and self.is_string_literal(value):
            self.emit_string(self.decode_string(value))
        else:
            self.load_ax(value)
            self.line("    CALL PRINT_INT")

    def emit_string(self, text):
        """字符串挂到数据段（STR_n DB ...,'$'），用 DOS 09h 打印。"""

        if not text:
            return
        label = self.new_string_label(text)
        self.line(f"    LEA DX, {label}")
        self.line("    CALL PRINT_STR")

    def emit_read(self, target):
        """scanf("%d", &x)：CALL READ_INT 后 AX 就是读到的整数值。"""

        self.line("    CALL READ_INT")
        self.store_ax(target)

    def emit_call(self, callee, argc, result):
        """生成普通函数调用代码。

        本课程设计没有实现完整栈帧，参数通过函数对应的数据区变量传递。
        """

        args = [value for _, value in sorted(self.pending_args, key=lambda item: item[0])]
        params = self.func_params.get(callee, [])
        for param, arg in zip(params, args):
            ptype, pname = param["type"], param["name"]
            if ptype.endswith("[]"):
                # 数组实参传地址
                self.assign_array_param(callee, pname, arg)
            elif ptype.startswith("struct "):
                # 结构体实参逐字段拷贝
                self.copy_struct_argument(callee, ptype, pname, arg)
            else:
                self.load_ax(arg)
                self.store_ax(self.scoped_name(callee, pname), raw=True)
        self.line(f"    CALL {self.safe(callee)}")
        self.store_ax(result)
        self.pending_args = []

    def assign_array_param(self, callee, pname, arg):
        """数组形参赋值：实参是地址就直传，是变量名就 LEA 取地址。"""

        target = self.scoped_name(callee, pname)
        if self.is_array_pointer(arg):
            self.load_ax(arg)
        else:
            self.line(f"    LEA AX, {self.memory_ref(arg)}")
        self.store_ax(target, raw=True)

    def copy_struct_argument(self, callee, ptype, pname, arg):
        """结构体实参：逐字段把值拷贝到 callee 的形参字段。"""

        struct_name = ptype.split(" ", 1)[1]
        for field in self.struct_fields.get(struct_name, []):
            self.load_ax(self.member_ref(arg, field["name"]))
            self.store_ax(self.field_symbol(callee, pname, field["name"]), raw=True)

    def load_ax(self, value):
        """把任意 IR 值装进 AX。字符串字面量取地址，复合左值走专门路径。"""

        if self.is_string_literal(value):
            label = self.new_string_label(self.decode_string(value))
            self.line(f"    LEA AX, {label}")
            return
        if self.is_memory_lvalue(value):
            self.load_lvalue_to_ax(value)
            return
        self.line(f"    MOV AX, {self.source_ref(value)}")

    def store_ax(self, target, raw=False):
        """把 AX 存到目标。raw=True 时目标已经是带前缀的汇编符号。"""

        if target == "_":
            return
        if not raw and self.is_memory_lvalue(target):
            self.store_ax_to_lvalue(target)
            return
        self.line(f"    MOV {self.memory_ref(target) if not raw else self.safe(target)}, AX")

    def source_ref(self, value):
        """load 时的右值：立即数直接当数字，其他都当内存地址。"""

        if self.is_immediate(value):
            return self.integer_literal(value)
        return self.memory_ref(value)

    def memory_ref(self, value):
        """把 IR 名字翻译成汇编符号。"""

        if value == "_":
            return value
        if self.is_temp(value):
            return self.safe(value)
        if self.is_immediate(value):
            return self.integer_literal(value)
        if "." in value and not value.startswith("'"):
            base, member = value.split(".", 1)
            return self.field_symbol(self.current_func, base, member)
        if "->" in value:
            base, member = value.split("->", 1)
            return self.field_symbol(self.current_func, base, member)
        if self.current_func and value in self.scoped_symbols.get(self.current_func, set()):
            return self.scoped_name(self.current_func, value)
        return self.safe(value)

    def member_ref(self, base, member):
        """obj.member 或 obj->member 统一写成 obj.member。"""

        member = member[2:] if member.startswith("->") else member
        return f"{base}.{member}"

    def is_memory_lvalue(self, value):
        """带 [...]、.、-> 的复合左值，要走专门 load/store 路径。"""

        return isinstance(value, str) and ("[" in value or "." in value or "->" in value)

    def load_lvalue_to_ax(self, value):
        """复合左值 load：a[i] 走数组路径，a.x/.b 走普通 MOV。"""

        if "[" in value and value.endswith("]"):
            base, index = value[:-1].split("[", 1)
            self.load_array_element(base, index)
        else:
            self.line(f"    MOV AX, {self.memory_ref(value)}")

    def store_ax_to_lvalue(self, value):
        """复合左值 store：a[i] = t 走数组路径，a.x = t 走普通 MOV。"""

        if "[" in value and value.endswith("]"):
            base, index = value[:-1].split("[", 1)
            self.store_array_element(base, index)
        else:
            self.line(f"    MOV {self.memory_ref(value)}, AX")

    def is_array_pointer(self, name):
        """判断名字是否是数组形参（指针）。"""

        return self.memory_ref(name) in self.array_params

    def field_symbol(self, func, base, member):
        """结构体字段的汇编符号：func_base_member。"""

        return self.safe(f"{self.memory_ref_with_func(func, base)}_{member}")

    def memory_ref_with_func(self, func, value):
        """按指定函数查作用域生成符号。"""

        if self.is_temp(value):
            return self.safe(value)
        if "[" in value and value.endswith("]"):
            base, index = value[:-1].split("[", 1)
            if func and base in self.scoped_symbols.get(func, set()):
                return self.scoped_name(func, f"{base}_{self.safe(index)}")
            return self.safe(f"{base}_{self.safe(index)}")
        if func and value in self.scoped_symbols.get(func, set()):
            return self.scoped_name(func, value)
        return self.safe(value)

    def scoped_name(self, func, name):
        """局部符号加函数名前缀，避免撞名。"""

        if func is None:
            return self.safe(name)
        return self.safe(f"{func}_{name}")

    def safe(self, value):
        """IR 名字清洗成 MASM 合法标识符。"""

        text = str(value).replace("<", "").replace(">", "")
        out = []
        for ch in text:
            out.append(ch if ch.isalnum() or ch == "_" else "_")
        safe = "".join(out).strip("_") or "tmp"
        if safe[0].isdigit():
            safe = "v_" + safe
        return safe

    def new_internal_label(self, prefix):
        """短路求值/比较用内部标签。"""

        self.cmp_label_id += 1
        return f"{prefix}_{self.cmp_label_id}"

    def new_string_label(self, text):
        """给字符串字面量挂一个数据段标签，DOS 必须 '$' 结尾。"""

        self.string_id += 1
        label = f"STR_{self.string_id}"
        bytes_text = ", ".join(str(ord(ch)) for ch in text)
        if bytes_text:
            self.string_defs.append(f"{label} DB {bytes_text}, '$'")
        else:
            self.string_defs.append(f"{label} DB '$'")
        return label

    def parse_format(self, text):
        """把 printf 格式串切成 (lit, "...") 和 (spec, 'd') 交替的段。"""

        segments = []
        buf = []
        i = 0
        while i < len(text):
            if text[i] == "%" and i + 1 < len(text):
                if text[i + 1] == "%":
                    buf.append("%")
                    i += 2
                    continue
                if buf:
                    segments.append(("lit", "".join(buf)))
                    buf = []
                segments.append(("spec", text[i + 1]))
                i += 2
                continue
            buf.append(text[i])
            i += 1
        if buf:
            segments.append(("lit", "".join(buf)))
        return segments

    def decode_string(self, literal):
        """把字符串字面量（含转义）还原成纯文本。"""

        text = literal[1:-1] if len(literal) >= 2 and literal[0] == '"' else literal
        out = []
        i = 0
        escapes = {"n": "\r\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "0": "\0"}
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                out.append(escapes.get(text[i + 1], text[i + 1]))
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def is_string_literal(self, value):
        return isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"'

    def is_temp(self, value):
        return isinstance(value, str) and value.startswith("t") and value[1:].isdigit()

    def is_immediate(self, value):
        """数字字面量或字符字面量，字符串字面量不算。"""

        if not isinstance(value, str):
            return False
        if self.is_string_literal(value):
            return False
        if len(value) >= 3 and value[0] == "'" and value[-1] == "'":
            return True
        try:
            self.integer_literal(value)
            return True
        except ValueError:
            return False

    def integer_literal(self, value):
        """把 'A' / 0x1F / 077 / 42 / -3 / 1.5 统一成纯十进制数字字符串。"""

        text = str(value)
        if len(text) >= 3 and text[0] == "'" and text[1] == "'":
            return str(ord(text[1]))
        if "." in text:
            return str(int(float(text)))
        sign = -1 if text.startswith("-") else 1
        body = text[1:] if text.startswith("-") else text
        if body.lower().startswith("0x"):
            return str(sign * int(body, 16))
        if len(body) > 1 and body.startswith("0") and body.isdigit():
            return str(sign * int(body, 8))
        return str(int(text, 10))

    def line(self, text):
        """往代码段缓冲区追加一行。"""

        self.code_lines.append(text)

    def runtime_library(self):
        """内置的 DOS 输出/输入运行时过程。"""

        return [
            "",
            "PRINT_STR PROC",
            "    MOV AH, 09h",
            "    INT 21h",
            "    RET",
            "PRINT_STR ENDP",
            "",
            "PRINT_CHAR PROC",
            "    MOV AH, 02h",
            "    INT 21h",
            "    RET",
            "PRINT_CHAR ENDP",
            "",
            "PRINT_INT PROC",
            "    PUSH AX",
            "    PUSH BX",
            "    PUSH CX",
            "    PUSH DX",
            "    CMP AX, 0",
            "    JGE PRINT_INT_POS",
            "    PUSH AX",
            "    MOV DL, '-'",
            "    CALL PRINT_CHAR",
            "    POP AX",
            "    NEG AX",
            "PRINT_INT_POS:",
            "    CMP AX, 0",
            "    JNE PRINT_INT_LOOP_INIT",
            "    MOV DL, '0'",
            "    CALL PRINT_CHAR",
            "    JMP PRINT_INT_DONE",
            "PRINT_INT_LOOP_INIT:",
            "    XOR CX, CX",
            "    MOV BX, 10",
            "PRINT_INT_DIV_LOOP:",
            "    XOR DX, DX",
            "    DIV BX",
            "    PUSH DX",
            "    INC CX",
            "    CMP AX, 0",
            "    JNE PRINT_INT_DIV_LOOP",
            "PRINT_INT_OUT_LOOP:",
            "    POP DX",
            "    ADD DL, '0'",
            "    CALL PRINT_CHAR",
            "    LOOP PRINT_INT_OUT_LOOP",
            "PRINT_INT_DONE:",
            "    POP DX",
            "    POP CX",
            "    POP BX",
            "    POP AX",
            "    RET",
            "PRINT_INT ENDP",
            "",
            "READ_INT PROC",
            "    PUSH BX",
            "    PUSH CX",
            "    PUSH DX",
            "    XOR BX, BX",
            "    XOR CX, CX",
            "READ_INT_LOOP:",
            "    MOV AH, 01h",
            "    INT 21h",
            "    CMP AL, '-'",
            "    JNE READ_INT_CHECK_CR",
            "    MOV CX, 1",
            "    JMP READ_INT_LOOP",
            "READ_INT_CHECK_CR:",
            "    CMP AL, 13",
            "    JE READ_INT_DONE",
            "    CMP AL, '0'",
            "    JB READ_INT_LOOP",
            "    CMP AL, '9'",
            "    JA READ_INT_LOOP",
            "    SUB AL, '0'",
            "    MOV AH, 0",
            "    PUSH AX",
            "    MOV AX, BX",
            "    MOV DX, 10",
            "    MUL DX",
            "    MOV BX, AX",
            "    POP AX",
            "    ADD BX, AX",
            "    JMP READ_INT_LOOP",
            "READ_INT_DONE:",
            "    MOV AX, BX",
            "    CMP CX, 0",
            "    JE READ_INT_EXIT",
            "    NEG AX",
            "READ_INT_EXIT:",
            "    POP DX",
            "    POP CX",
            "    POP BX",
            "    RET",
            "READ_INT ENDP",
        ]
