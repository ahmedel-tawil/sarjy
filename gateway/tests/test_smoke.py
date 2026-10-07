import importlib.util


def test_package_is_installed() -> None:
    assert importlib.util.find_spec("sarjy_gateway") is not None
