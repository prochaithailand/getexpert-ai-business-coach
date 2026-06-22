import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from models import KnowledgeMatch
from services.knowledge_service import KnowledgeService


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def create(self, *, model: str, input: list[str]):
        self.calls.append(input)
        data = []
        for text in input:
            if any(word in text for word in ("ผู้มุ่งหวัง", "ลูกค้า", "รายชื่อ")):
                vector = [1.0, 0.0]
            elif any(word in text for word in ("สุขภาพ", "อาหารเสริม")):
                vector = [0.0, 1.0]
            else:
                vector = [0.5, 0.5]
            data.append(SimpleNamespace(embedding=vector))
        return SimpleNamespace(data=data)


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddings()


class KnowledgeServiceTests(unittest.TestCase):
    def test_discovers_pdf_files_and_ignores_other_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Facebook Guide.pdf").write_bytes(b"pdf-data")
            (root / "notes.txt").write_text("ignore me", encoding="utf-8")

            documents = KnowledgeService(root).list_documents()

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0].name, "Facebook Guide")
            self.assertEqual(documents[0].category, "สื่อสังคมออนไลน์")
            self.assertEqual(documents[0].display_size, "8 B")

    def test_subfolder_name_becomes_category(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            category = root / "Leadership"
            category.mkdir()
            (category / "Team Coaching.pdf").write_bytes(b"content")

            document = KnowledgeService(root).list_documents()[0]

            self.assertEqual(document.category, "Leadership")

    def test_search_matches_name_and_category_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Facebook Guide.pdf").write_bytes(b"a")
            (root / "WorkplanMLM.pdf").write_bytes(b"b")
            service = KnowledgeService(root)
            documents = service.list_documents()

            self.assertEqual(len(service.search(documents, "FACEBOOK")), 1)
            self.assertEqual(len(service.search(documents, "", "การพัฒนาธุรกิจ")), 1)

    def test_explicit_platform_query_limits_results_to_that_source(self) -> None:
        service = KnowledgeService(Path("knowledge"))
        service._indexed = True
        service._chunks = [
            KnowledgeMatch("คู่มือ TikTok", "สื่อสังคมออนไลน์", 1, "tiktok สำหรับผู้เริ่มต้นและการสร้างวิดีโอ", 0),
            KnowledgeMatch("คู่มือการเล่าเรื่องผลิตภัณฑ์สุขภาพ", "ความรู้ผลิตภัณฑ์", 1, "การสร้างเนื้อหาสำหรับผู้เริ่มต้น", 0),
        ]

        results = service.search_text("เริ่มทำ TikTok สำหรับมือใหม่")

        self.assertTrue(results)
        self.assertEqual({result.document_name for result in results}, {"คู่มือ TikTok"})

    def test_semantic_retrieval_prefers_meaningfully_related_passage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeEmbeddingClient()
            service = KnowledgeService(
                Path("knowledge"),
                embedding_client=client,
                cache_path=Path(directory) / "embeddings.json",
            )
            service._indexed = True
            service._chunks = [
                KnowledgeMatch("คู่มือสร้างทีม", "การพัฒนาธุรกิจ", 3, "วางระบบรายชื่อผู้มุ่งหวังและติดตามลูกค้า", 0),
                KnowledgeMatch("คู่มือสุขภาพ", "ความรู้ผลิตภัณฑ์", 8, "ความรู้เรื่องอาหารเสริมและสุขภาพ", 0),
            ]

            results = service.search_text("ฉันควรหาลูกค้าใหม่อย่างไร")

            self.assertTrue(service.semantic_enabled)
            self.assertEqual(results[0].document_name, "คู่มือสร้างทีม")
            self.assertGreaterEqual(len(client.embeddings.calls), 2)

    def test_pdf_cleaning_removes_filename_noise_and_duplicate_lines(self) -> None:
        raw = """
        WorkplanMLM.pdf
        หน้า 1
        การสร้างรายชื่อผู้มุ่งหวังเป็นกิจกรรมสำคัญ
        การสร้างรายชื่อผู้มุ่งหวังเป็นกิจกรรมสำคัญ
        @@@@ ####
        """

        cleaned = KnowledgeService.clean_pdf_text(raw, "WorkplanMLM.pdf")

        self.assertNotIn("WorkplanMLM", cleaned)
        self.assertNotIn("หน้า 1", cleaned)
        self.assertNotIn("@@@@", cleaned)
        self.assertEqual(cleaned.count("การสร้างรายชื่อผู้มุ่งหวังเป็นกิจกรรมสำคัญ"), 1)

    def test_pdf_cleaning_collapses_adjacent_thai_phrase_duplicates(self) -> None:
        cleaned = KnowledgeService.clean_pdf_text("เพิ่มยอดขายเพิ่มยอดขายเพิ่มยอดขาย ด้วยคอนเทนต์")
        self.assertEqual(cleaned.count("เพิ่มยอดขาย"), 1)

    def test_near_duplicate_fragments_are_detected(self) -> None:
        first = "การสร้างรายชื่อผู้มุ่งหวังและติดตามผลอย่างสม่ำเสมอช่วยพัฒนาธุรกิจให้เติบโต"
        second = "การสร้างรายชื่อผู้มุ่งหวังและติดตามผลอย่างสม่ำเสมอช่วยพัฒนาธุรกิจให้เติบโตได้"
        self.assertTrue(KnowledgeService._near_duplicate(first, second))

    def test_thai_query_expansion_improves_common_coaching_questions(self) -> None:
        member_query = KnowledgeService._expand_query("สมาชิกใหม่ควรเริ่มต้นอย่างไร")
        content_query = KnowledgeService._expand_query("จะสร้างคอนเทนต์อย่างไร")
        self.assertIn("5 โมดูล", member_query)
        self.assertIn("สร้างรายชื่อ", member_query)
        self.assertIn("storytelling", content_query)
        self.assertIn("การตลาดออนไลน์", content_query)


if __name__ == "__main__":
    unittest.main()
