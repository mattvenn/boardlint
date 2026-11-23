"""Minimal, fast S-expression reader for KiCad files.

Lists become Python lists, quoted strings become ``QStr`` (a str subclass, so
callers can tell `"GND"` from the bare token `GND` when it matters), bare
tokens stay plain ``str``.  Numbers are left as strings and converted on use:
KiCad files contain things like pad numbers and UUIDs that look numeric.
"""
from __future__ import annotations
import re

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
_ESC = re.compile(r'\\(.)')


class QStr(str):
    """A token that was double-quoted in the source."""


def loads(text: str) -> list:
    stack: list[list] = [[]]
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t == '(':
            new: list = []
            stack[-1].append(new)
            stack.append(new)
        elif t == ')':
            stack.pop()
            if not stack:
                raise ValueError("unbalanced ')' at offset %d" % m.start())
        elif t[0] == '"':
            s = t[1:-1]
            if '\\' in s:
                s = _ESC.sub(lambda e: {'n': '\n', 't': '\t'}.get(e.group(1), e.group(1)), s)
            stack[-1].append(QStr(s))
        else:
            stack[-1].append(t)
    if len(stack) != 1:
        raise ValueError("unbalanced '(' : %d unclosed" % (len(stack) - 1))
    return stack[0][0] if stack[0] else []


def load(path) -> list:
    with open(path, encoding='utf-8') as f:
        return loads(f.read())


def children(node: list, tag: str):
    """All direct child lists whose head is ``tag``."""
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def child(node: list, tag: str):
    for c in node:
        if isinstance(c, list) and c and c[0] == tag:
            return c
    return None


def value(node: list, tag: str, default=None):
    """First atom after the head of the first child called ``tag``."""
    c = child(node, tag)
    if c is None or len(c) < 2:
        return default
    return c[1]


def fnum(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
