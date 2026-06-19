"""词法分析器。

输入源码字符串，输出 Token 序列。这里采用手写扫描方式，按当前位置
尝试匹配字符串、数字、标识符、运算符和界符。
"""

from .matcher import (
    Trie,
    is_id_continue,
    match_dec_int,
    match_float,
    match_hex_int,
    match_identifier,
    match_oct_int,
    match_string_or_char,
    match_whitespace,
)
from .token import DELIMITERS, KEYWORDS, OPERATORS, Token, TokenType


class Lexer:
    """逐字符扫描源码并生成 Token。"""

    def __init__(self, text: str):
        self.text = text
        self.n = len(text)
        # 扫描游标
        self.pos = 0
        # 行列号，输出 Token 时带着
        self.line = 1
        self.col = 1

        # 把运算符和界符统一塞进 Trie，方便做最长匹配
        self.trie = Trie()
        for op in OPERATORS:
            self.trie.add(op, "OP")
        for dl in DELIMITERS:
            self.trie.add(dl, "DL")

    def _advance(self, s: str):
        """移动扫描位置，同时维护当前行号和列号。"""

        # 逐字符推进，遇到换行时行号+1、列号重置
        for ch in s:
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        self.pos += len(s)

    def _peek(self, k=1) -> str:
        """看 pos 起 k 个字符但不消费。"""

        return self.text[self.pos:self.pos + k]

    def _skip_ws(self) -> bool:
        """跳过一段空白；返回是否真的跳过了。"""

        n = match_whitespace(self.text, self.pos)
        if n > 0:
            self._advance(self.text[self.pos:self.pos + n])
            return True
        return False

    def _skip_comments(self):
        """跳过 // 和 /* */ 注释；未闭合块注释会返回错误 Token。"""

        if self._peek(2) == "/*":
            end = self.text.find("*/", self.pos + 2)
            if end == -1:
                # 没找到 */，把整段当 ERROR 返回
                lex = self.text[self.pos:]
                tok = Token(TokenType.ERROR, lex, self.line, self.col)
                self._advance(lex)
                return tok
            self._advance(self.text[self.pos:end + 2])
            return True
        if self._peek(2) == "//":
            # 注释到行尾为止
            j = self.text.find("\n", self.pos)
            if j == -1:
                self._advance(self.text[self.pos:])
            else:
                self._advance(self.text[self.pos:j])
            return True
        return False

    def _try_string_or_char(self):
        """尝试匹配字符串/字符字面量；返回 Token 或 None。"""

        length, is_string, is_error = match_string_or_char(self.text, self.pos)
        if length == 0:
            return None
        ttype = TokenType.CS_STR if is_string else TokenType.CS_CHAR
        lex = self.text[self.pos:self.pos + length]
        tok = Token(TokenType.ERROR, lex, self.line, self.col) if is_error else Token(ttype, lex, self.line, self.col)
        self._advance(lex)
        return tok

    def next_token(self) -> Token:
        """读取下一个 Token，是词法分析的主逻辑。"""

        # 循环跳过空白/注释，直到停在有意义的字符上
        progressed = True
        while progressed:
            progressed = False
            if self._skip_ws():
                progressed = True
            cm = self._skip_comments()
            if cm is True:
                progressed = True
            elif isinstance(cm, Token):  # 块注释未闭合，直接报 ERROR
                return cm

        if self.pos >= self.n:
            return Token(TokenType.EOF, "", self.line, self.col)

        sc = self._try_string_or_char()
        if sc is not None:
            return sc

        # 单独的 # 视作界符，简化 #include 的处理
        if self._peek(1) == '#':
            tok = Token(TokenType.DL, '#', self.line, self.col)
            self._advance('#')
            return tok

        candidates = []  # 同一位置可能有多种匹配结果，后面按"最长优先"选择
        start = self.pos

        Lf = match_float(self.text, start)
        if Lf > 0:
            candidates.append((Lf, TokenType.FLOAT))
        L16 = match_hex_int(self.text, start)
        if L16 > 0:
            candidates.append((L16, TokenType.NUM16))
        L8 = match_oct_int(self.text, start)
        if L8 > 0:
            candidates.append((L8, TokenType.NUM8))
        L10 = match_dec_int(self.text, start)
        if L10 > 0:
            candidates.append((L10, TokenType.NUM10))

        op_lex, op_tag = self.trie.match_longest(self.text, start)
        if op_lex is not None:
            ttype = TokenType.OP if op_tag == "OP" else TokenType.DL
            candidates.append((len(op_lex), ttype))

        Lid = match_identifier(self.text, start)
        if Lid > 0:
            candidates.append((Lid, None))  # None 等会儿在 ID/RW 之间二选一

        if not candidates:
            # 当前位置不匹配任何规则，单字符 ERROR
            bad = self.text[self.pos]
            tok = Token(TokenType.ERROR, bad, self.line, self.col)
            self._advance(bad)
            return tok

        # 长度优先：等长时按 数字 > 运算符/界符 > 标识符 的优先级裁决
        def pri(entry):
            l, tt = entry
            if tt in (TokenType.FLOAT, TokenType.NUM16, TokenType.NUM8, TokenType.NUM10):
                p = 3
            elif tt in (TokenType.OP, TokenType.DL):
                p = 2
            else:
                p = 1
            return (l, p)

        L, ttype = max(candidates, key=pri)
        lex = self.text[self.pos:self.pos + L]

        # 对 0x、八进制和数字后接字母的情况做额外错误识别
        if ttype == TokenType.NUM10 and lex == '0':
            j = self.pos + 1
            if j < self.n and self.text[j] in ('x', 'X'):
                # 0x 必须是 hex_int；不是则报 ERROR
                L16_try = match_hex_int(self.text, self.pos)
                if L16_try > 0:
                    L = L16_try
                    ttype = TokenType.NUM16
                    lex = self.text[self.pos:self.pos + L]
                else:
                    k = j + 1
                    while k < self.n and is_id_continue(self.text[k]):
                        k += 1
                    bad_lex = self.text[self.pos:k] if k > j + 1 else self.text[self.pos:j + 1]
                    tok = Token(TokenType.ERROR, bad_lex, self.line, self.col)
                    self._advance(bad_lex)
                    return tok
            elif j < self.n and self.text[j] in '01234567':
                # 0 后面跟八进制数字 → 升级为 NUM8
                L8_try = match_oct_int(self.text, self.pos)
                if L8_try > 0:
                    L = L8_try
                    ttype = TokenType.NUM8
                    lex = self.text[self.pos:self.pos + L]
            elif j < self.n and self.text[j] in '89':
                # 0 后面跟 8/9 是非法的十进制
                k = j + 1
                while k < self.n and is_id_continue(self.text[k]):
                    k += 1
                bad_lex = self.text[self.pos:k]
                tok = Token(TokenType.ERROR, bad_lex, self.line, self.col)
                self._advance(bad_lex)
                return tok

        # 数字后不能直接接标识符字符，否则整体当 ERROR
        if ttype in (TokenType.FLOAT, TokenType.NUM16, TokenType.NUM8, TokenType.NUM10):
            j = self.pos + L
            if j < self.n and is_id_continue(self.text[j]):
                k = j
                while k < self.n and is_id_continue(self.text[k]):
                    k += 1
                bad_lex = self.text[self.pos:k]
                tok = Token(TokenType.ERROR, bad_lex, self.line, self.col)
                self._advance(bad_lex)
                return tok

        # 标识符的 ttype 此时是 None，根据是否在关键字表里决定 RW/ID
        if ttype is None:
            ttype = TokenType.RW if lex in KEYWORDS else TokenType.ID

        tok = Token(ttype, lex, self.line, self.col)
        self._advance(lex)
        return tok

    def tokenize(self):
        """反复调 next_token 直到拿到 EOF，返回 Token 列表。"""

        out = []
        while True:
            t = self.next_token()
            out.append(t)
            if t.type == TokenType.EOF:
                break
        return out
