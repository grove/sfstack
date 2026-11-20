"""Build one distribution from canonical tools and contract resources.

No policy, schemas or skill copies are maintained inside the source package.
The build snapshots those files into the wheel at its pinned distribution version.
"""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class WithContracts(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        destination = Path(self.build_lib) / "sfstack_contracts_data"
        for name in ("schemas", "skills", "workflows"):
            shutil.copytree(root / name, destination / name, dirs_exist_ok=True)


setup(
    name="sfstack-contracts",
    version="1.0.0",
    description="Versioned offline sfstack contract, artifact and gate CLI",
    python_requires=">=3.11",
    install_requires=["jsonschema>=4.23,<5"],
    py_modules=["common", "factory", "contract_cli"],
    packages=["sfstack_contracts_data"],
    package_dir={"": "tools", "sfstack_contracts_data": "sfstack_contracts_data"},
    entry_points={"console_scripts": ["sfstack-contract=contract_cli:main"]},
    cmdclass={"build_py": WithContracts},
)
