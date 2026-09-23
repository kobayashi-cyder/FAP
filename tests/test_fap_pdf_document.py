from __future__ import annotations

import unittest

from fap_pdf_document import normalize_pdf_text
from fap_information_reasoner import InformationFundamentalsReasoner


class PDFDocumentTests(unittest.TestCase):
    def test_common_pdf_control_codes_are_normalized_to_digits(self) -> None:
        self.assertEqual(normalize_pdf_text("\x02 low \x03 mid \x0b high"), "0 low 1 mid 9 high")

    def test_information_rules_are_content_based(self) -> None:
        text = """
        主記憶装置と補助記憶装置を比較する。
        ア の解答群
        0 低速 1 同程度 2 高速
        イ の解答群
        0 容量が小さく、データの短期的な保存
        3 容量が大きく、データの長期的な保存

        情報セキュリティの可用性について考える。
        3 保有するデータをバックアップしておくことで、可用性を高めることができる。
        """
        answers, evidence = InformationFundamentalsReasoner().solve(text)
        self.assertEqual(answers.get("ア"), "0")
        self.assertEqual(answers.get("イ"), "3")
        self.assertEqual(answers.get("ウ"), "3")
        self.assertTrue(evidence)


if __name__ == "__main__":
    unittest.main()
