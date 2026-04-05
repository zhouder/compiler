class SemanticError(Exception):
    pass


class SymbolTable:
    def __init__(self):
        self.scopes = [{}]

    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def define(self, name, info):
        current = self.scopes[-1]
        if name in current:
            raise SemanticError(f"重复定义变量：{name}")
        current[name] = info

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None
