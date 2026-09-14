# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

from genlayer import *

class Hello(gl.Contract):
    def __init__(self):
        pass

    @gl.public.view
    def hello(self) -> str:
        return "world"
