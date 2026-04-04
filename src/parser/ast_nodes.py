class ASTNode:
    pass


class Program(ASTNode):
    def __init__(self, statements):
        self.statements = statements
