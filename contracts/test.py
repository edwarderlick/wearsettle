from genlayer import *
class Test(gl.contract.Contract):
    t: Address
    def __init__(self, tenant: Address):
        self.t = tenant
