import unittest
from inventory import reserve


class InventoryTests(unittest.TestCase):
    def test_partial_reservation(self):
        self.assertEqual(3, reserve(5, 2))

    def test_oversized_reservation(self):
        self.assertIsNone(reserve(5, 6))

    def test_zero_quantity(self):
        with self.assertRaises(ValueError):
            reserve(5, 0)


if __name__ == '__main__':
    unittest.main()
