from genlayer import *
class Test2(gl.contract.Contract):
    t: str
    def __init__(self, tenant: str):
        self.t = tenant
