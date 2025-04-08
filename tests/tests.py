def foo(a: int, b: int) -> int:
    return a + b


def bar(a: int, b: int) -> int:
    return a - b


def baz(a: int, *, b: int) -> int:
    return a * b


baz(
    1,
    aasdf=2,
    foo=3,
)
