class CodeGenerator:
    WORD_SIZE = 2

    def __init__(self):
        self.reset()

    def reset(self):
        self.struct_fields = {}
        self.func_params = {}
        self.func_returns = {}
        self.scoped_symbols = {}
        self.array_params = set()
        self.data_defs = []
        self.data_names = set()
        self.string_defs = []
        self.string_id = 0
        self.cmp_label_id = 0
        self.code_lines = []
        self.current_func = None
        self.pending_args = []
        self.pending_printf = None

    def generate(self, ir_list):
        self.reset()
        self.collect_metadata(ir_list)
        self.collect_storage(ir_list)
        self.emit_code(ir_list)

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

    def collect_metadata(self, ir_list):
        current_struct = None
        current_func = None
        for q in ir_list:
            if q.op == "struct":
                current_struct = q.arg1
                self.struct_fields[current_struct] = []
            elif q.op == "structfield" and current_struct:
                self.struct_fields[current_struct].append({"type": q.arg1, "name": q.result})
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

    def collect_storage(self, ir_list):
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
                self.declare_array(self.scoped_name(current_func, q.result), q.arg2, q.arg1)

            for value in (q.arg1, q.arg2, q.result):
                if self.is_temp(value):
                    self.declare_word(self.safe(value), "temp")

    def declare_param(self, func, typ, name):
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
        if name == "_":
            return
        self.scoped_symbols.setdefault(func, set()).add(name)
        if typ.startswith("struct "):
            self.declare_struct_object(func, typ, name)
            return
        self.declare_word(self.scoped_name(func, name), typ)

    def declare_struct_object(self, func, typ, name):
        struct_name = typ.split(" ", 1)[1]
        fields = self.struct_fields.get(struct_name, [])
        if not fields:
            self.declare_word(self.scoped_name(func, name), typ)
            return
        for field in fields:
            self.declare_word(self.field_symbol(func, name, field["name"]), f"{typ}.{field['name']}")

    def declare_word(self, name, comment="word"):
        name = self.safe(name)
        if name in self.data_names:
            return
        self.data_names.add(name)
        self.data_defs.append(f"{name} DW ? ; {comment}")

    def declare_array(self, name, size, comment="array"):
        name = self.safe(name)
        if name in self.data_names:
            return
        self.data_names.add(name)
        size = self.integer_literal(size)
        self.data_defs.append(f"{name} DW {size} DUP (?) ; {comment}[]")

    def emit_code(self, ir_list):
        self.current_func = None
        for q in ir_list:
            op, a1, a2, res = q.op, q.arg1, q.arg2, q.result
            if op == "include":
                self.line(f"; include {a1}")
            elif op in ("struct", "structfield", "endstruct"):
                self.line(f"; {op} {a1} {a2} {res}")
            elif op == "func":
                self.current_func = a1
                self.pending_args = []
                self.pending_printf = None
                self.line("")
                self.line(f"{self.safe(a1)} PROC")
                self.line(f"    ; return {a2}, params {res}")
            elif op == "endfunc":
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
        if op == "+":
            self.load_ax(left)
            self.line(f"    ADD AX, {self.source_ref(right)}")
            self.store_ax(result)
        elif op == "-":
            self.load_ax(left)
            self.line(f"    SUB AX, {self.source_ref(right)}")
            self.store_ax(result)
        elif op == "*":
            self.load_ax(left)
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IMUL BX")
            self.store_ax(result)
        elif op == "/":
            self.load_ax(left)
            self.line("    CWD")
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IDIV BX")
            self.store_ax(result)
        elif op == "%":
            self.load_ax(left)
            self.line("    CWD")
            self.line(f"    MOV BX, {self.source_ref(right)}")
            self.line("    IDIV BX")
            self.line("    MOV AX, DX")
            self.store_ax(result)

    def emit_compare(self, op, left, right, result):
        true_label = self.new_internal_label("CMP_TRUE")
        end_label = self.new_internal_label("CMP_END")
        jump_map = {
            "<": "JL",
            "<=": "JLE",
            ">": "JG",
            ">=": "JGE",
            "==": "JE",
            "!=": "JNE",
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
        self.emit_index_to_bx(index)
        base = self.memory_ref(array_name)
        if base in self.array_params:
            self.line(f"    MOV SI, {base}")
            self.line("    ADD SI, BX")
            self.line("    MOV AX, [SI]")
        else:
            self.line(f"    MOV AX, {base}[BX]")

    def store_array_element(self, array_name, index):
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
        self.load_ax(index)
        self.line("    MOV BX, AX")
        self.line("    SHL BX, 1")

    def emit_print(self, value):
        if self.is_string_literal(value):
            text = self.decode_string(value)
            segments = self.parse_format(text)
            if any(kind == "spec" for kind, _ in segments):
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
        if not self.pending_printf:
            return "d"
        segments = self.pending_printf["segments"]
        pos = self.pending_printf["pos"]
        if pos < len(segments) and segments[pos][0] == "spec":
            self.pending_printf["pos"] += 1
            return segments[pos][1]
        return "d"

    def emit_print_value(self, value, spec):
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
        if not text:
            return
        label = self.new_string_label(text)
        self.line(f"    LEA DX, {label}")
        self.line("    CALL PRINT_STR")

    def emit_read(self, target):
        self.line("    CALL READ_INT")
        self.store_ax(target)

    def emit_call(self, callee, argc, result):
        args = [value for _, value in sorted(self.pending_args, key=lambda item: item[0])]
        params = self.func_params.get(callee, [])
        for param, arg in zip(params, args):
            ptype, pname = param["type"], param["name"]
            if ptype.endswith("[]"):
                self.assign_array_param(callee, pname, arg)
            elif ptype.startswith("struct "):
                self.copy_struct_argument(callee, ptype, pname, arg)
            else:
                self.load_ax(arg)
                self.store_ax(self.scoped_name(callee, pname), raw=True)
        self.line(f"    CALL {self.safe(callee)}")
        self.store_ax(result)
        self.pending_args = []

    def assign_array_param(self, callee, pname, arg):
        target = self.scoped_name(callee, pname)
        if self.is_array_pointer(arg):
            self.load_ax(arg)
        else:
            self.line(f"    LEA AX, {self.memory_ref(arg)}")
        self.store_ax(target, raw=True)

    def copy_struct_argument(self, callee, ptype, pname, arg):
        struct_name = ptype.split(" ", 1)[1]
        for field in self.struct_fields.get(struct_name, []):
            self.load_ax(self.member_ref(arg, field["name"]))
            self.store_ax(self.field_symbol(callee, pname, field["name"]), raw=True)

    def load_ax(self, value):
        if self.is_memory_lvalue(value):
            self.load_lvalue_to_ax(value)
            return
        self.line(f"    MOV AX, {self.source_ref(value)}")

    def store_ax(self, target, raw=False):
        if target == "_":
            return
        if not raw and self.is_memory_lvalue(target):
            self.store_ax_to_lvalue(target)
            return
        self.line(f"    MOV {self.memory_ref(target) if not raw else self.safe(target)}, AX")

    def source_ref(self, value):
        if self.is_immediate(value):
            return self.integer_literal(value)
        return self.memory_ref(value)

    def memory_ref(self, value):
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
        member = member[2:] if member.startswith("->") else member
        return f"{base}.{member}"

    def is_memory_lvalue(self, value):
        return isinstance(value, str) and ("[" in value or "." in value or "->" in value)

    def load_lvalue_to_ax(self, value):
        if "[" in value and value.endswith("]"):
            base, index = value[:-1].split("[", 1)
            self.load_array_element(base, index)
        else:
            self.line(f"    MOV AX, {self.memory_ref(value)}")

    def store_ax_to_lvalue(self, value):
        if "[" in value and value.endswith("]"):
            base, index = value[:-1].split("[", 1)
            self.store_array_element(base, index)
        else:
            self.line(f"    MOV {self.memory_ref(value)}, AX")

    def is_array_pointer(self, name):
        return self.memory_ref(name) in self.array_params

    def field_symbol(self, func, base, member):
        return self.safe(f"{self.memory_ref_with_func(func, base)}_{member}")

    def memory_ref_with_func(self, func, value):
        if self.is_temp(value):
            return self.safe(value)
        if func and value in self.scoped_symbols.get(func, set()):
            return self.scoped_name(func, value)
        return self.safe(value)

    def scoped_name(self, func, name):
        if func is None:
            return self.safe(name)
        return self.safe(f"{func}_{name}")

    def safe(self, value):
        text = str(value).replace("<", "").replace(">", "")
        out = []
        for ch in text:
            out.append(ch if ch.isalnum() or ch == "_" else "_")
        safe = "".join(out).strip("_") or "tmp"
        if safe[0].isdigit():
            safe = "v_" + safe
        return safe

    def new_internal_label(self, prefix):
        self.cmp_label_id += 1
        return f"{prefix}_{self.cmp_label_id}"

    def new_string_label(self, text):
        self.string_id += 1
        label = f"STR_{self.string_id}"
        bytes_text = ", ".join(str(ord(ch)) for ch in text)
        if bytes_text:
            self.string_defs.append(f"{label} DB {bytes_text}, '$'")
        else:
            self.string_defs.append(f"{label} DB '$'")
        return label

    def parse_format(self, text):
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
        text = str(value)
        if len(text) >= 3 and text[0] == "'" and text[-1] == "'":
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
        self.code_lines.append(text)

    def runtime_library(self):
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
