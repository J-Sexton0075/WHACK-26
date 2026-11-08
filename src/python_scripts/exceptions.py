class IncompatibleAttribute(Exception):
    def __init__(self, attr1, attr2, msg="Incompatible Attributes"):
        self.attr1 = attr1
        self.attr2 = attr2
        self.msg = msg
        super().__init__(self.msg)
    def __str__(self):
        return f"{self.attr1}, {self.attr2} -> {self.msg}"