"""词法匹配辅助函数。

Lexer 会反复从当前位置尝试匹配数字、标识符、字符串、运算符等。
这些函数只返回匹配长度，不直接创建 Token。
"""


WHITESPACE = set(" \t\r\n\f\v")  # C 源码里被当作"空白"的字符


def is_alpha(c: str) -> bool:
    """是否为英文字母。"""

    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')


def is_digit(c: str) -> bool:
    """是否为十进制数字。"""

    return '0' <= c <= '9'


def is_hex(c: str) -> bool:
    """是否为十六进制数字（含 a-f / A-F）。"""

    return is_digit(c) or ('a' <= c <= 'f') or ('A' <= c <= 'F')


def is_oct(c: str) -> bool:
    """是否为八进制数字（0-7）。"""

    return '0' <= c <= '7'


def is_id_start(c: str) -> bool:
    """标识符首字符：字母或下划线。"""

    return is_alpha(c) or c == '_'


def is_id_continue(c: str) -> bool:
    """标识符后续字符：首字符规则 + 数字。"""

    return is_id_start(c) or is_digit(c)


def match_while(text: str, pos: int, pred) -> int:
    """从 pos 起连续匹配 pred，返回匹配长度。"""

    i, n = pos, len(text)
    while i < n and pred(text[i]):
        i += 1
    return i - pos


def match_whitespace(text: str, pos: int) -> int:
    """匹配一段空白字符。"""

    return match_while(text, pos, lambda ch: ch in WHITESPACE)


def match_identifier(text: str, pos: int) -> int:
    """匹配标识符长度；不是标识符首字符则返回 0。"""

    n = len(text)
    if pos >= n or not is_id_start(text[pos]):
        return 0
    i = pos + 1
    while i < n and is_id_continue(text[i]):
        i += 1
    return i - pos


def match_float(text: str, pos: int) -> int:
    """匹配形如 12.3 或 12.3e-2 的浮点常量。"""

    n = len(text)
    i = pos
    if i >= n or not is_digit(text[i]):
        return 0
    i += match_while(text, i, is_digit)
    # 必须有小数点和至少一位小数位
    if i >= n or text[i] != '.':
        return 0
    i += 1
    if i >= n or not is_digit(text[i]):
        return 0
    i += match_while(text, i, is_digit)
    # 可选的科学计数法
    if i < n and text[i] in ('e', 'E'):
        j = i + 1
        if j < n and text[j] in ('+', '-'):
            j += 1
        k = j + match_while(text, j, is_digit)
        if k == j:
            return 0
        i = k
    return i - pos


def match_hex_int(text: str, pos: int) -> int:
    """匹配 0x... 十六进制整数。"""

    n = len(text)
    if pos + 1 < n and text[pos] == '0' and text[pos + 1] in ('x', 'X'):
        j = pos + 2
        if j < n and is_hex(text[j]):
            while j < n and is_hex(text[j]):
                j += 1
            return j - pos
        return 0
    return 0


def match_oct_int(text: str, pos: int) -> int:
    """匹配 0 后接八进制数字的八进制整数；单 '0' 留给十进制分支。"""

    n = len(text)
    if pos < n and text[pos] == '0':
        j = pos + 1
        if j < n and is_oct(text[j]):
            while j < n and is_oct(text[j]):
                j += 1
            return j - pos
    return 0


def match_dec_int(text: str, pos: int) -> int:
    """匹配十进制整数；前导 0 单独算一个 token（避免抢八进制）。"""

    n = len(text)
    if pos >= n or not is_digit(text[pos]):
        return 0
    if text[pos] == '0':
        return 1
    j = pos + 1
    j += match_while(text, j, is_digit)
    return j - pos


def match_string_or_char(text: str, pos: int) -> tuple[int, bool, bool]:
    """匹配 "..." 字符串或 'x' 字符常量。

    返回 (长度, 是否字符串, 是否出错)。
    """

    n = len(text)
    if pos >= n or text[pos] not in ("'", '"'):
        return (0, False, False)
    quote = text[pos]
    i = pos + 1
    while i < n:
        c = text[i]
        # 转义符吃掉下一字符（避免误判被转义的引号/换行）
        if c == '\\':
            i += 2
            continue
        if c == quote:
            return (i - pos + 1, quote == '"', False)
        # 字符串里裸换行是非法的，作为错误返回
        if c == '\n' and quote == '"':
            break
        i += 1
    return (max(1, i - pos), quote == '"', True)


class Trie:
    """用于运算符和界符的最长匹配。

    例如先读到 '<' 时，还需要继续判断是不是 '<=' 或 '<<='。
    """

    def __init__(self):
        self.root = {"next": {}}

    def add(self, s: str, tag: str):
        """插入一个串，tag 用来区分是 OP 还是 DL。"""

        node = self.root
        for ch in s:
            node = node["next"].setdefault(ch, {"next": {}})
        node["end"] = True
        node["tag"] = tag

    def match_longest(self, text: str, pos: int):
        """从 pos 起在 Trie 中走最长前缀，命中返回 (串, tag)，未命中返回 (None, None)。"""

        node = self.root
        i, n = pos, len(text)
        last_hit = None
        while i < n:
            ch = text[i]
            nxt = node["next"].get(ch)
            if nxt is None:
                break
            node = nxt
            i += 1
            if node.get("end"):
                last_hit = (i, node.get("tag"))
        if last_hit is None:
            return (None, None)
        end_i, tag = last_hit
        return (text[pos:end_i], tag)
