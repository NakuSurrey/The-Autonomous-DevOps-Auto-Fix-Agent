"""
test_calculator.py — PyTest Tests for the Calculator

WHAT THIS FILE DOES:
    Tests every function in calculator.py.
    Each test defines the EXPECTED correct behavior.

WHY IT EXISTS:
    These tests are the "source of truth" that tells the agent
    what the code SHOULD do. When a test fails, the agent reads
    the error and uses it to figure out what is wrong.

TEST RESULTS WITH THE CURRENT BUGS:
    test_add              → PASS  (add() is correct)
    test_subtract         → FAIL  (subtract uses + instead of -)
    test_multiply         → FAIL  (multiply adds 1 to result)
    test_divide           → PASS  (5 / 2 = 2.5 works fine)
    test_divide_by_zero   → FAIL  (no zero check — crashes)
"""

import pytest
from calculator import add, subtract, multiply, divide


# ---- TEST: add() ----
# add(2, 3) should return 5
# This test PASSES because add() is correct.
class TestAdd:
    def test_add_positive_numbers(self):
        assert add(2, 3) == 5

    def test_add_negative_numbers(self):
        assert add(-1, -1) == -2

    def test_add_zero(self):
        assert add(0, 5) == 5


# ---- TEST: subtract() ----
# subtract(10, 4) should return 6
# This test FAILS because subtract() uses + instead of -
# The agent will see: AssertionError: assert 14 == 6
class TestSubtract:
    def test_subtract_positive_numbers(self):
        assert subtract(10, 4) == 6

    def test_subtract_negative_result(self):
        assert subtract(3, 7) == -4

    def test_subtract_zero(self):
        assert subtract(5, 0) == 5


# ---- TEST: multiply() ----
# multiply(3, 4) should return 12
# This test FAILS because multiply() returns 13 (adds 1)
# The agent will see: AssertionError: assert 13 == 12
class TestMultiply:
    def test_multiply_positive_numbers(self):
        assert multiply(3, 4) == 12

    def test_multiply_by_zero(self):
        assert multiply(5, 0) == 0

    def test_multiply_negative_numbers(self):
        assert multiply(-2, 3) == -6


# ---- TEST: divide() ----
# divide(10, 2) should return 5.0
# This test PASSES because 10 / 2 works fine.
# But test_divide_by_zero FAILS because there is no zero check.
class TestDivide:
    def test_divide_positive_numbers(self):
        assert divide(10, 2) == 5.0

    def test_divide_returns_float(self):
        assert divide(7, 2) == 3.5

    def test_divide_by_zero(self):
        """
        divide(10, 0) should raise a ValueError with a clear message.
        Right now, it raises ZeroDivisionError instead — this is the bug.
        """
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)
