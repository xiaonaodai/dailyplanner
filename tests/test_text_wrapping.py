import unittest

from glass_text import font, wrapped_lines


class TextWrappingTests(unittest.TestCase):
    def setUp(self):
        self.face = font(24, False, "Segoe UI")
        self.width = 180

    def assert_wrapped(self, text):
        lines = wrapped_lines(text, self.face, self.width)
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join(lines), text.replace("\n", ""))
        for line in lines:
            self.assertLessEqual(self.face.getlength(line), self.width)
        return lines

    def test_unspaced_chinese(self):
        self.assert_wrapped("\u5de5\u4f5c\u5185\u5bb9" * 30)

    def test_english_sentence_and_long_word(self):
        self.assert_wrapped("Review the project notes " * 12)
        self.assert_wrapped("SuperLongTaskName" * 20)

    def test_manual_and_blank_lines(self):
        self.assertEqual(
            wrapped_lines("one\n\ntwo\n", self.face, self.width),
            ["one", "", "two", ""],
        )

    def test_narrow_and_wide_layouts(self):
        text = "Review the project notes " * 10
        narrow = wrapped_lines(text, self.face, 180)
        wide = wrapped_lines(text, self.face, 360)
        self.assertGreater(len(narrow), len(wide))

