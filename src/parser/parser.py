from lexer.token import TokenType
from .token_stream import TokenStream
from .ast_nodes import (
    Program, Include, StructDef, Param, FunctionDef, Block, VarDecl, DeclStmt,
    Assign, IfStmt, WhileStmt, ForStmt, DoWhileStmt, BreakStmt, ContinueStmt,
    ReturnStmt, ExprStmt, EmptyStmt, CallExpr, BinaryExpr, UnaryExpr, Literal,
    Identifier, ArrayAccess, MemberAccess
)


TYPE_KEYWORDS = {"int", "char", "float", "void"}
BUILTIN_CALLS = {"printf", "scanf"}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%="}


class Parser:
    def __init__(self, tokens):
        self.ts = TokenStream(tokens)

    def parse(self):
        includes = []
        declarations = []
        while not self.ts.is_eof():
            if self.is_preprocessor_line():
                includes.append(self.parse_preprocessor_line())
                continue
            if self.is_struct_definition_start():
                declarations.append(self.parse_struct_def())
                continue
            declarations.append(self.parse_external_declaration())
        return Program(includes, declarations)

    def is_preprocessor_line(self):
        tok = self.ts.current()
        return tok.type == TokenType.DL and tok.lexeme == "#"

    def parse_preprocessor_line(self):
        line = self.ts.current().line
        parts = []
        while not self.ts.is_eof() and self.ts.current().line == line:
            parts.append(self.ts.advance().lexeme)
        text = "".join(parts)
        header = ""
        if len(parts) >= 5 and parts[0] == "#" and parts[1] == "include":
            header = "".join(parts[2:])
        return Include(text, header)

    def is_struct_definition_start(self):
        return (
            self.ts.current().type == TokenType.RW
            and self.ts.current().lexeme == "struct"
            and self.ts.peek(1).type == TokenType.ID
            and self.ts.peek(2).type == TokenType.DL
            and self.ts.peek(2).lexeme == "{"
        )

    def parse_struct_def(self):
        self.ts.expect(TokenType.RW, "struct", "缺少 struct")
        name = self.ts.expect(TokenType.ID, message="结构体名错误").lexeme
        self.ts.expect(TokenType.DL, "{", "结构体定义缺少 {")
        fields = []
        while not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "}"):
            field_decls = self.parse_var_decl_list()
            self.ts.expect(TokenType.DL, ";", "结构体字段后缺少 ;")
            fields.extend(field_decls)
        self.ts.expect(TokenType.DL, "}", "结构体定义缺少 }")
        self.ts.expect(TokenType.DL, ";", "结构体定义后缺少 ;")
        return StructDef(name, fields)

    def parse_external_declaration(self):
        base_type = self.parse_type_name()
        var_type, name, array_size, is_array = self.parse_named_declarator(base_type)
        if self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "(":
            params = self.parse_parameter_list()
            body = self.parse_block()
            return FunctionDef(var_type, name, params, body)
        init = None
        if self.ts.match(TokenType.OP, "="):
            init = self.parse_expression()
        decls = [VarDecl(var_type, name, init, array_size, is_array)]
        while self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ",":
            self.ts.advance()
            var_type, name, array_size, is_array = self.parse_named_declarator(base_type)
            init = None
            if self.ts.match(TokenType.OP, "="):
                init = self.parse_expression()
            decls.append(VarDecl(var_type, name, init, array_size, is_array))
        self.ts.expect(TokenType.DL, ";", "全局变量定义后缺少 ;")
        return decls[0] if len(decls) == 1 else DeclStmt(decls)

    def parse_type_name(self):
        tok = self.ts.current()
        if tok.type == TokenType.RW and tok.lexeme in TYPE_KEYWORDS:
            self.ts.advance()
            return tok.lexeme
        if tok.type == TokenType.RW and tok.lexeme == "struct":
            self.ts.advance()
            name = self.ts.expect(TokenType.ID, message="结构体类型名错误").lexeme
            return f"struct {name}"
        raise SyntaxError(f"类型说明符错误：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")

    def parse_pointer_depth(self):
        depth = 0
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme == "*":
            self.ts.advance()
            depth += 1
        return depth

    def make_type(self, base_type, pointer_depth):
        return base_type + ("*" * pointer_depth)

    def parse_named_declarator(self, base_type):
        pointer_depth = self.parse_pointer_depth()
        name = self.ts.expect(TokenType.ID, message="变量名错误").lexeme
        array_size = None
        is_array = False
        if self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "[":
            self.ts.advance()
            is_array = True
            if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "]"):
                array_size = self.parse_expression()
            self.ts.expect(TokenType.DL, "]", "数组声明缺少 ]")
        return self.make_type(base_type, pointer_depth), name, array_size, is_array

    def parse_parameter_list(self):
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        params = []
        if self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ")":
            self.ts.advance()
            return params
        if (
            self.ts.current().type == TokenType.RW
            and self.ts.current().lexeme == "void"
            and self.ts.peek(1).type == TokenType.DL
            and self.ts.peek(1).lexeme == ")"
        ):
            self.ts.advance()
            self.ts.advance()
            return params
        while True:
            base_type = self.parse_type_name()
            param_type, name, array_size, is_array = self.parse_named_declarator(base_type)
            params.append(Param(param_type, name, array_size, is_array))
            if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ","):
                break
            self.ts.advance()
        self.ts.expect(TokenType.DL, ")", "参数列表缺少 )")
        return params

    def parse_block(self):
        self.ts.expect(TokenType.DL, "{", "缺少 {")
        statements = []
        while not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "}"):
            statements.append(self.parse_statement())
        self.ts.expect(TokenType.DL, "}", "缺少 }")
        return Block(statements)

    def is_type_start(self):
        tok = self.ts.current()
        return (
            (tok.type == TokenType.RW and tok.lexeme in TYPE_KEYWORDS)
            or (tok.type == TokenType.RW and tok.lexeme == "struct")
        )

    def parse_statement(self):
        tok = self.ts.current()
        if tok.type == TokenType.DL and tok.lexeme == ";":
            self.ts.advance()
            return EmptyStmt()
        if tok.type == TokenType.DL and tok.lexeme == "{":
            return self.parse_block()
        if self.is_type_start():
            decls = self.parse_var_decl_list()
            self.ts.expect(TokenType.DL, ";", "变量定义后缺少 ;")
            return decls[0] if len(decls) == 1 else DeclStmt(decls)
        if tok.type == TokenType.RW and tok.lexeme == "if":
            return self.parse_if()
        if tok.type == TokenType.RW and tok.lexeme == "while":
            return self.parse_while()
        if tok.type == TokenType.RW and tok.lexeme == "do":
            return self.parse_do_while()
        if tok.type == TokenType.RW and tok.lexeme == "for":
            return self.parse_for()
        if tok.type == TokenType.RW and tok.lexeme == "break":
            self.ts.advance()
            self.ts.expect(TokenType.DL, ";", "break 后缺少 ;")
            return BreakStmt()
        if tok.type == TokenType.RW and tok.lexeme == "continue":
            self.ts.advance()
            self.ts.expect(TokenType.DL, ";", "continue 后缺少 ;")
            return ContinueStmt()
        if tok.type == TokenType.RW and tok.lexeme == "return":
            return self.parse_return()
        expr = self.parse_expression()
        self.ts.expect(TokenType.DL, ";", "语句后缺少 ;")
        return expr if isinstance(expr, Assign) else ExprStmt(expr)

    def parse_var_decl_list(self):
        base_type = self.parse_type_name()
        decls = []
        while True:
            var_type, name, array_size, is_array = self.parse_named_declarator(base_type)
            init = None
            if self.ts.match(TokenType.OP, "="):
                init = self.parse_expression()
            decls.append(VarDecl(var_type, name, init, array_size, is_array))
            if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ","):
                break
            self.ts.advance()
        return decls

    def parse_if(self):
        self.ts.expect(TokenType.RW, "if", "缺少 if")
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        condition = self.parse_expression()
        self.ts.expect(TokenType.DL, ")", "缺少 )")
        then_branch = self.parse_statement()
        else_branch = None
        if self.ts.current().type == TokenType.RW and self.ts.current().lexeme == "else":
            self.ts.advance()
            else_branch = self.parse_statement()
        return IfStmt(condition, then_branch, else_branch)

    def parse_while(self):
        self.ts.expect(TokenType.RW, "while", "缺少 while")
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        condition = self.parse_expression()
        self.ts.expect(TokenType.DL, ")", "缺少 )")
        body = self.parse_statement()
        return WhileStmt(condition, body)

    def parse_do_while(self):
        self.ts.expect(TokenType.RW, "do", "缺少 do")
        body = self.parse_statement()
        self.ts.expect(TokenType.RW, "while", "do-while 缺少 while")
        self.ts.expect(TokenType.DL, "(", "do-while 缺少 (")
        condition = self.parse_expression()
        self.ts.expect(TokenType.DL, ")", "do-while 缺少 )")
        self.ts.expect(TokenType.DL, ";", "do-while 后缺少 ;")
        return DoWhileStmt(body, condition)

    def parse_for(self):
        self.ts.expect(TokenType.RW, "for", "缺少 for")
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        init = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ";"):
            if self.is_type_start():
                decls = self.parse_var_decl_list()
                init = decls[0] if len(decls) == 1 else DeclStmt(decls)
            else:
                init = self.parse_expression()
        self.ts.expect(TokenType.DL, ";", "for 初始化后缺少 ;")
        condition = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ";"):
            condition = self.parse_expression()
        self.ts.expect(TokenType.DL, ";", "for 条件后缺少 ;")
        update = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ")"):
            update = self.parse_expression()
        self.ts.expect(TokenType.DL, ")", "缺少 )")
        body = self.parse_statement()
        return ForStmt(init, condition, update, body)

    def parse_return(self):
        self.ts.expect(TokenType.RW, "return", "缺少 return")
        if self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ";":
            self.ts.advance()
            return ReturnStmt(None)
        value = self.parse_expression()
        self.ts.expect(TokenType.DL, ";", "return 后缺少 ;")
        return ReturnStmt(value)

    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        expr = self.parse_logical_or()
        if self.ts.current().type == TokenType.OP and self.ts.current().lexeme in ASSIGN_OPS:
            op = self.ts.advance().lexeme
            value = self.parse_assignment()
            if op != "=":
                value = BinaryExpr(op[0], expr, value)
            return Assign(expr, value)
        return expr

    def parse_logical_or(self):
        expr = self.parse_logical_and()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme == "||":
            op = self.ts.advance().lexeme
            right = self.parse_logical_and()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_logical_and(self):
        expr = self.parse_equality()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme == "&&":
            op = self.ts.advance().lexeme
            right = self.parse_equality()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_equality(self):
        expr = self.parse_relational()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme in ("==", "!="):
            op = self.ts.advance().lexeme
            right = self.parse_relational()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_relational(self):
        expr = self.parse_additive()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme in ("<", "<=", ">", ">="):
            op = self.ts.advance().lexeme
            right = self.parse_additive()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_additive(self):
        expr = self.parse_term()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme in ("+", "-"):
            op = self.ts.advance().lexeme
            right = self.parse_term()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_term(self):
        expr = self.parse_unary()
        while self.ts.current().type == TokenType.OP and self.ts.current().lexeme in ("*", "/", "%"):
            op = self.ts.advance().lexeme
            right = self.parse_unary()
            expr = BinaryExpr(op, expr, right)
        return expr

    def parse_unary(self):
        tok = self.ts.current()
        if tok.type == TokenType.OP and tok.lexeme in ("+", "-", "!", "&", "*"):
            op = self.ts.advance().lexeme
            operand = self.parse_unary()
            return UnaryExpr(op, operand)
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            tok = self.ts.current()
            if tok.type == TokenType.DL and tok.lexeme == "(":
                if not isinstance(expr, Identifier):
                    raise SyntaxError(f"调用对象错误：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")
                args = self.parse_arguments()
                expr = CallExpr(expr.name, args)
                continue
            if tok.type == TokenType.DL and tok.lexeme == "[":
                self.ts.advance()
                index = self.parse_expression()
                self.ts.expect(TokenType.DL, "]", "数组访问缺少 ]")
                expr = ArrayAccess(expr, index)
                continue
            if tok.type == TokenType.OP and tok.lexeme == ".":
                self.ts.advance()
                member = self.ts.expect(TokenType.ID, message="成员名错误").lexeme
                expr = MemberAccess(expr, member, False)
                continue
            if tok.type == TokenType.OP and tok.lexeme == "->":
                self.ts.advance()
                member = self.ts.expect(TokenType.ID, message="成员名错误").lexeme
                expr = MemberAccess(expr, member, True)
                continue
            break
        return expr

    def parse_arguments(self):
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        args = []
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ")"):
            args.append(self.parse_expression())
            while self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ",":
                self.ts.advance()
                args.append(self.parse_expression())
        self.ts.expect(TokenType.DL, ")", "缺少 )")
        return args

    def parse_primary(self):
        tok = self.ts.current()
        if tok.type == TokenType.DL and tok.lexeme == "(":
            self.ts.advance()
            expr = self.parse_expression()
            self.ts.expect(TokenType.DL, ")", "缺少 )")
            return expr
        if tok.type == TokenType.ID or (tok.type == TokenType.RW and tok.lexeme in BUILTIN_CALLS):
            self.ts.advance()
            return Identifier(tok.lexeme)
        if tok.type in (TokenType.NUM10, TokenType.NUM8, TokenType.NUM16):
            self.ts.advance()
            return Literal(tok.lexeme, "int")
        if tok.type == TokenType.FLOAT:
            self.ts.advance()
            return Literal(tok.lexeme, "float")
        if tok.type == TokenType.CS_CHAR:
            self.ts.advance()
            return Literal(tok.lexeme, "char")
        if tok.type == TokenType.CS_STR:
            self.ts.advance()
            return Literal(tok.lexeme, "string")
        raise SyntaxError(f"无法解析的基本表达式：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")
