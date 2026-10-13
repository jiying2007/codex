"""Load only the repository tools package in an isolated Python process."""
import importlib.util
import pathlib
import runpy
import sys
import tempfile
import types


def main():
    root = pathlib.Path(sys.argv[1]).resolve()
    module = sys.argv[2]
    if not sys.flags.isolated or not module.startswith("tools."):
        raise SystemExit("isolated tools runtime required")
    sys.argv = [module] + sys.argv[3:]
    with tempfile.TemporaryDirectory(prefix="tools-bytecode-") as cache:
        sys.pycache_prefix = cache
        initializer = root / "tools/__init__.py"
        if initializer.is_file():
            specification = importlib.util.spec_from_file_location(
                "tools", initializer,
                submodule_search_locations=[str(root / "tools")])
            package = importlib.util.module_from_spec(specification)
            sys.modules["tools"] = package
            specification.loader.exec_module(package)
        else:
            package = types.ModuleType("tools")
            package.__path__ = [str(root / "tools")]
            sys.modules["tools"] = package
        runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
