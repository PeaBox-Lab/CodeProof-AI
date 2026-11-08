from codeproof.core import grade


def test_grade():
    assert grade(90) == "A" and grade(70) == "C" and grade(59) == "F"
