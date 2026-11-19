"""Run only after the agent returns, in a sandbox suitable for candidate code."""
import importlib.util
import os
from pathlib import Path
import unittest

candidate = Path(os.environ['SFSTACK_CANDIDATE_DIR']).resolve() / 'inventory.py'
spec = importlib.util.spec_from_file_location('candidate_inventory', candidate)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryContract(unittest.TestCase):
    def test_partial(self):
        self.assertEqual(3, module.reserve(5, 2))

    def test_exact(self):
        self.assertEqual(0, module.reserve(5, 5))

    def test_excess(self):
        self.assertIsNone(module.reserve(5, 6))

    def test_empty(self):
        self.assertIsNone(module.reserve(0, 1))

    def test_zero(self):
        with self.assertRaises(ValueError):
            module.reserve(5, 0)

    def test_negative(self):
        with self.assertRaises(ValueError):
            module.reserve(5, -1)


if __name__ == '__main__':
    unittest.main()
