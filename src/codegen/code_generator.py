class CodeGenerator:
    def __init__(self):
        self._label_id = 0

    def new_label(self, prefix="CG"):
        self._label_id += 1
        return f"{prefix}{self._label_id}"

    def generate(self, ir_list):
        lines = []
        for q in ir_list:
            op, a1, a2, res = q.op, q.arg1, q.arg2, q.result
            if op == "func":
                lines.append(f"{a1}:")
            elif op == "endfunc":
                lines.append(f"; end {a1}")
            elif op == "label":
                lines.append(f"{res}:")
            elif op == "decl":
                lines.append(f"; var {res} : {a1}")
            elif op == "=":
                lines.append(f"MOV {res}, {a1}")
            elif op == "+":
                lines.extend([
                    f"MOV AX, {a1}",
                    f"ADD AX, {a2}",
                    f"MOV {res}, AX",
                ])
            elif op == "-":
                lines.extend([
                    f"MOV AX, {a1}",
                    f"SUB AX, {a2}",
                    f"MOV {res}, AX",
                ])
            elif op == "*":
                lines.extend([
                    f"MOV AX, {a1}",
                    f"MUL AX, {a2}",
                    f"MOV {res}, AX",
                ])
            elif op == "/":
                lines.extend([
                    f"MOV AX, {a1}",
                    f"DIV AX, {a2}",
                    f"MOV {res}, AX",
                ])
            elif op == "%":
                lines.extend([
                    f"MOV AX, {a1}",
                    f"MOD AX, {a2}",
                    f"MOV {res}, AX",
                ])
            elif op in ("<", "<=", ">", ">=", "==", "!="):
                true_label = self.new_label("TRUE")
                end_label = self.new_label("ENDCMP")
                jump_map = {
                    "<": "JL",
                    "<=": "JLE",
                    ">": "JG",
                    ">=": "JGE",
                    "==": "JE",
                    "!=": "JNE",
                }
                lines.extend([
                    f"MOV {res}, 0",
                    f"CMP {a1}, {a2}",
                    f"{jump_map[op]} {true_label}",
                    f"JMP {end_label}",
                    f"{true_label}:",
                    f"MOV {res}, 1",
                    f"{end_label}:",
                ])
            elif op == "&&":
                false_label = self.new_label("FALSE")
                end_label = self.new_label("ENDAND")
                lines.extend([
                    f"MOV {res}, 0",
                    f"CMP {a1}, 0",
                    f"JE {false_label}",
                    f"CMP {a2}, 0",
                    f"JE {false_label}",
                    f"MOV {res}, 1",
                    f"{false_label}:",
                    f"{end_label}:",
                ])
            elif op == "||":
                true_label = self.new_label("TRUE")
                end_label = self.new_label("ENDOR")
                lines.extend([
                    f"MOV {res}, 1",
                    f"CMP {a1}, 0",
                    f"JNE {true_label}",
                    f"CMP {a2}, 0",
                    f"JNE {true_label}",
                    f"MOV {res}, 0",
                    f"{true_label}:",
                    f"{end_label}:",
                ])
            elif op == "u-":
                lines.extend([
                    f"MOV AX, {a1}",
                    "NEG AX",
                    f"MOV {res}, AX",
                ])
            elif op == "u!":
                true_label = self.new_label("TRUE")
                end_label = self.new_label("ENDNOT")
                lines.extend([
                    f"MOV {res}, 0",
                    f"CMP {a1}, 0",
                    f"JE {true_label}",
                    f"JMP {end_label}",
                    f"{true_label}:",
                    f"MOV {res}, 1",
                    f"{end_label}:",
                ])
            elif op == "u+":
                lines.append(f"MOV {res}, {a1}")
            elif op == "addr":
                lines.append(f"LEA {res}, {a1}")
            elif op == "jz":
                lines.extend([
                    f"CMP {a1}, 0",
                    f"JE {res}",
                ])
            elif op == "jmp":
                lines.append(f"JMP {res}")
            elif op == "print":
                lines.append(f"PRINT {a1}")
            elif op == "read":
                lines.append(f"READ {res}")
            elif op == "ret":
                if a1 != "_":
                    lines.append(f"RET {a1}")
                else:
                    lines.append("RET")
            elif op == "call":
                lines.extend([
                    f"CALL {a1}",
                    f"MOV {res}, AX",
                ])
            else:
                lines.append(f"; unsupported {op} {a1} {a2} {res}")
        return "\n".join(lines)
