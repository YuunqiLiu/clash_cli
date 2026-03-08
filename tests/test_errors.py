"""Tests for clash_cli.errors."""

from clash_cli.errors import ClashError


def test_clash_error_attributes():
    e = ClashError("SOME_CODE", "Something went wrong")
    assert e.code == "SOME_CODE"
    assert e.message == "Something went wrong"
    assert "Something went wrong" in str(e)


def test_clash_error_is_exception():
    e = ClashError("X", "Y")
    assert isinstance(e, Exception)
