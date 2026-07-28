"""B0.0 smoke test — proves the toolchain runs. Real tests arrive with their tasks."""


def test_skeleton_imports() -> None:
    import cli  # noqa: F401
    import kernel  # noqa: F401
    import runtime  # noqa: F401

    assert True
