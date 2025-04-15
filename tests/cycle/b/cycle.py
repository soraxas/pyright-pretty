from ..a.cycle import a_func


def b_func():
    return a_func()


print(b_func())
