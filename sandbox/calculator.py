"""
calculator.py — A Simple Calculator with INTENTIONAL BUGS

WHAT THIS FILE DOES:
    Provides basic math operations: add, subtract, multiply, divide.

WHY IT EXISTS:
    This is the "broken toy" the agent will fix. It contains
    intentional bugs so that when pytest runs, tests FAIL.
    The agent's job is to read the error, find the bug, and
    write the correct code.

INTENTIONAL BUGS IN THIS FILE:
    Bug 1: subtract() adds instead of subtracting
    Bug 2: multiply() has an off-by-one error (adds 1 to result)
    Bug 3: divide() does not handle division by zero
"""


def add(a: float, b: float) -> float:
    """
    Returns the sum of a and b.
    This function is CORRECT — no bug here.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """
    Should return a minus b.
    BUG: Uses + instead of -
    """
    return a + b  # BUG: should be a - b


def multiply(a: float, b: float) -> float:
    """
    Should return a times b.
    BUG: Adds 1 to the result.
    """
    return a * b + 1  # BUG: the "+ 1" should not be here


def divide(a: float, b: float) -> float:
    """
    Should return a divided by b.
    Should raise ValueError if b is zero.
    BUG: No check for division by zero — will crash with ZeroDivisionError.
    """
    return a / b  # BUG: missing zero check
