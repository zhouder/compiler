"""作用域符号表。

语义分析通过栈式作用域管理变量、参数和函数名。进入代码块时 push，
退出代码块时 pop，查找时从内层作用域向外层作用域查。
"""

class SemanticError(Exception):
    """语义分析阶段统一抛出的错误类型。"""

    pass


class SymbolTable:
    """简单的嵌套作用域符号表。"""

    def __init__(self):
        self.scopes = [{}]

    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def current_scope(self):
        return self.scopes[-1]

    def define(self, name, info):
        """在当前作用域定义符号，并检查重复定义。"""

        current = self.scopes[-1]
        if name in current:
            raise SemanticError(f"重复定义变量：{name}")
        current[name] = info

    def define_global(self, name, info):
        current = self.scopes[0]
        if name in current:
            raise SemanticError(f"重复定义符号：{name}")
        current[name] = info

    def lookup(self, name):
        """从当前作用域向外查找符号。"""

        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup_current(self, name):
        return self.scopes[-1].get(name)
