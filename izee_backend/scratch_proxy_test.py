import sys
from types import ModuleType

def foo():
    return "original foo"

def bar():
    return foo()

foo = None

class Proxy(ModuleType):
    def __getattribute__(self, name):
        if name == "foo":
            return lambda: "proxied foo"
        return super().__getattribute__(name)

sys.modules[__name__].__class__ = Proxy

print("module.foo:", sys.modules[__name__].foo())
try:
    print("bar calling foo:", bar())
except Exception as e:
    print("Error calling bar:", e)
