import unittest

from caption_index import CaptionIndex


class CaptionIndexBasicTests(unittest.TestCase):
    def test_one_caption(self):
        index = CaptionIndex()
        index.apply({"op": "put", "id": "a", "revision": 1, "locale": "en", "start": 10, "end": 20, "text": "Ready"})
        self.assertEqual(index.visible(12, "en"), [("a", "Ready")])


if __name__ == "__main__":
    unittest.main()
