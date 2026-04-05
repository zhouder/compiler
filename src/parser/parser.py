from lexer.token import TokenType
from .token_stream import TokenStream
from .ast_nodes import (
    Program, FunctionDef, Block, VarDecl, Assign, IfStmt, WhileStmt, ForStmt,
    ReturnStmt, ExprStmt, CallExpr, BinaryExpr, UnaryExpr, Literal, Identifier
)


TYPE_KEYWORDS = {"int", "char", "float", "void"}


class Parser:
    def __init__(self, tokens):
        self.ts = TokenStream(tokens)

    def parse(self):
        functions = []
        while not self.ts.is_eof():
            functions.append(self.parse_function())
        return Program(functions)

    def parse_function(self):
        ret_type = self.parse_type_name()
        name = self.ts.expect(TokenType.ID, message="函数名错误").lexeme
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        self.ts.expect(TokenType.DL, ")", "当前版本仅支持无参函数")
        body = self.parse_block()
        return FunctionDef(ret_type, name, body)

    def parse_type_name(self):
        tok = self.ts.current()
        if tok.type == TokenType.RW and tok.lexeme in TYPE_KEYWORDS:
            self.ts.advance()
            return tok.lexeme
        raise SyntaxError(f"类型说明符错误：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")

    def parse_block(self):
        self.ts.expect(TokenType.DL, "{", "缺少 {")
        statements = []
        while not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == "}"):
            statements.append(self.parse_statement())
        self.ts.expect(TokenType.DL, "}", "缺少 }")
        return Block(statements)

    def parse_statement(self):
        tok = self.ts.current()
        if tok.type == TokenType.DL and tok.lexeme == "{":
            return self.parse_block()
        if tok.type == TokenType.RW and tok.lexeme in TYPE_KEYWORDS:
            stmt = self.parse_var_decl()
            self.ts.expect(TokenType.DL, ";", "变量定义后缺少 ;")
            return stmt
        if tok.type == TokenType.RW and tok.lexeme == "if":
            return self.parse_if()
        if tok.type == TokenType.RW and tok.lexeme == "while":
            return self.parse_while()
        if tok.type == TokenType.RW and tok.lexeme == "for":
            return self.parse_for()
        if tok.type == TokenType.RW and tok.lexeme == "return":
            return self.parse_return()
        expr = self.parse_expression_or_assignment()
        self.ts.expect(TokenType.DL, ";", "语句后缺少 ;")
        return ExprStmt(expr) if not isinstance(expr, Assign) else expr

    def parse_var_decl(self):
        var_type = self.parse_type_name()
        name = self.ts.expect(TokenType.ID, message="变量名错误").lexeme
        init = None
        if self.ts.match(TokenType.OP, "="):
            init = self.parse_expression()
        return VarDecl(var_type, name, init)

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

    def parse_for(self):
        self.ts.expect(TokenType.RW, "for", "缺少 for")
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        init = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ";"):
            if self.ts.current().type == TokenType.RW and self.ts.current().lexeme in TYPE_KEYWORDS:
                init = self.parse_var_decl()
            else:
                init = self.parse_expression_or_assignment()
        self.ts.expect(TokenType.DL, ";", "for 初始化后缺少 ;")
        condition = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ";"):
            condition = self.parse_expression()
        self.ts.expect(TokenType.DL, ";", "for 条件后缺少 ;")
        update = None
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ")"):
            update = self.parse_expression_or_assignment()
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

    def parse_expression_or_assignment(self):
        if self.ts.current().type == TokenType.ID and self.ts.peek(1).type == TokenType.OP and self.ts.peek(1).lexeme == "=":
            name = self.ts.advance().lexeme
            self.ts.advance()
            value = self.parse_expression()
            return Assign(Identifier(name), value)
        return self.parse_expression()

    def parse_expression(self):
        return self.parse_logical_or()

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
        if tok.type == TokenType.OP and tok.lexeme in ("+", "-", "!"):
            op = self.ts.advance().lexeme
            operand = self.parse_unary()
            return UnaryExpr(op, operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.ts.current()
        if tok.type == TokenType.DL and tok.lexeme == "(":
            self.ts.advance()
            expr = self.parse_expression()
            self.ts.expect(TokenType.DL, ")", "缺少 )")
            return expr
        if tok.type == TokenType.ID or (tok.type == TokenType.RW and tok.lexeme in ("printf", "scanf")):
            if self.ts.peek(1).type == TokenType.DL and self.ts.peek(1).lexeme == "(":
                return self.parse_call()
            if tok.type == TokenType.ID:
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

    def parse_call(self):
        tok = self.ts.current()
        if tok.type == TokenType.ID or (tok.type == TokenType.RW and tok.lexeme in ("printf", "scanf")):
            callee = tok.lexeme
            self.ts.advance()
        else:
            raise SyntaxError(f"调用名错误：第 {tok.line} 行第 {tok.col} 列，得到 {tok}")
        self.ts.expect(TokenType.DL, "(", "缺少 (")
        args = []
        if not (self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ")"):
            args.append(self.parse_expression())
            while self.ts.current().type == TokenType.DL and self.ts.current().lexeme == ",":
                self.ts.advance()
                args.append(self.parse_expression())
        self.ts.expect(TokenType.DL, ")", "缺少 )")
        return CallExpr(callee, args)
