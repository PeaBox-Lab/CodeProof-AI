from codeproof.config import DEFAULT


def test_weights():
    assert sum(x.weight for x in DEFAULT.checks.values()) == 100
