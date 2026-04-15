class SemanticError(Exception):
    pass


class SymbolTable:
    def __init__(self):
        self.scopes = [{}]

    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def current_scope(self):
        return self.scopes[-1]

    def define(self, name, info):
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
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup_current(self, name):
        return self.scopes[-1].get(name)
