from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

from models import KnowledgeDocument, KnowledgeMatch
from services.openai_runtime_service import OpenAIRuntimeService

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - surfaced as a clear runtime message
    PdfReader = None  # type: ignore[assignment]


class KnowledgeService:
    """Indexes local knowledge documents and provides semantic-first retrieval with lexical fallback."""

    CLEANING_VERSION = "3"
    SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown"}
    TEXT_DOCUMENT_EXTENSIONS = {".md", ".markdown"}
    CATEGORY_KEYWORDS = {
        "สื่อสังคมออนไลน์": ("facebook", "tiktok"),
        "เครื่องมือดิจิทัล": ("line", "linktree", "blogger", "google form", "canva"),
        "การพัฒนาธุรกิจ": ("mlm", "module", "workplan", "5โมดูล"),
        "ความรู้ผลิตภัณฑ์": ("health", "supplement", "product", "storytelling"),
    }
    SOURCE_ALIASES = {
        "10-facebook page": "คู่มือ Facebook Page",
        "6-line+linktree": "คู่มือ LINE OA",
        "8-blogger": "คู่มือ Blogger",
        "9google form - linktree": "คู่มือ Google Form",
        "ebook_health_supplement_storytelling_formulas": "คู่มือการเล่าเรื่องผลิตภัณฑ์สุขภาพ",
        "tiktokสำหรับสอนออนไลน์": "คู่มือ TikTok",
        "workplanmlm": "คู่มือแผนงาน MLM",
        "คู่มือ canva พิมพ์": "คู่มือ Canva",
        "หนังสือ5โมดูล-ฉบับส่งพิมพ์ (1)": "หนังสือ 5 โมดูลธุรกิจ MLM",
    }
    SOURCE_INTENTS = {
        "คู่มือ TikTok": ("tiktok", "ติ๊กต็อก"),
        "คู่มือ LINE OA": ("line oa", "lineoa", "ไลน์โอเอ", "ไลน์ oa"),
        "คู่มือ Canva": ("canva", "แคนวา"),
        "คู่มือ Blogger": ("blogger", "บล็อกเกอร์"),
        "คู่มือ Facebook Page": ("facebook page", "facebook", "เฟซบุ๊ก", "เฟสบุค"),
        "คู่มือ Google Form": ("google form", "googleform", "กูเกิลฟอร์ม"),
        "คู่มือแผนงาน MLM": ("workplanmlm", "workplan mlm", "เวิร์คแพลน"),
        "คู่มือการเล่าเรื่องผลิตภัณฑ์สุขภาพ": ("storytelling", "อาหารเสริม", "ผลิตภัณฑ์สุขภาพ"),
    }
    QUERY_EXPANSIONS = {
        "สมาชิกใหม่": "เริ่มต้น 5 โมดูล แผนงาน MLM สร้างรายชื่อ เรียนรู้ ลงมือทำ",
        "เริ่มต้นอย่างไร": "เริ่มต้น 5 โมดูล แผนงาน MLM สร้างรายชื่อ เรียนรู้ ลงมือทำ",
        "คอนเทนต์": "content storytelling facebook tiktok canva การตลาดออนไลน์",
        "เนื้อหาออนไลน์": "content storytelling facebook tiktok canva การตลาดออนไลน์",
    }

    def __init__(
        self,
        knowledge_dir: Path,
        embedding_client: Any | None = None,
        embedding_model: str = "text-embedding-3-small",
        cache_path: Path | None = None,
        openai_runtime: OpenAIRuntimeService | None = None,
    ) -> None:
        self.knowledge_dir = knowledge_dir.resolve()
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.cache_path = cache_path or self.knowledge_dir.parent / ".cache" / "knowledge_embeddings.json"
        self.openai_runtime = openai_runtime
        self._chunks: list[KnowledgeMatch] = []
        self._embeddings: list[list[float]] = []
        self._query_embeddings: dict[str, list[float]] = {}
        self._indexed = False

    @property
    def semantic_enabled(self) -> bool:
        return self.embedding_client is not None

    def list_documents(self) -> list[KnowledgeDocument]:
        if not self.knowledge_dir.exists():
            return []
        documents = [self._to_document(path) for path in self._document_paths()]
        return sorted(documents, key=lambda item: (item.category.casefold(), item.name.casefold()))

    def search(
        self,
        documents: list[KnowledgeDocument],
        query: str = "",
        category: str = "ทุกหมวดหมู่",
    ) -> list[KnowledgeDocument]:
        normalized = query.strip().casefold()
        return [
            document
            for document in documents
            if (category == "ทุกหมวดหมู่" or document.category == category)
            and (not normalized or normalized in document.name.casefold() or normalized in document.category.casefold())
        ]

    def search_text(self, query: str, limit: int = 4) -> list[KnowledgeMatch]:
        normalized_query = self._normalize_text(self._expand_query(query))
        if len(normalized_query) < 2:
            return []
        self._ensure_text_index()
        if self.embedding_client is not None:
            try:
                return self._semantic_search(normalized_query, limit)
            except Exception:
                pass
        return self._lexical_search(normalized_query, limit)

    @classmethod
    def _expand_query(cls, query: str) -> str:
        normalized = query.casefold()
        additions = [expansion for phrase, expansion in cls.QUERY_EXPANSIONS.items() if phrase in normalized]
        return " ".join((query, *additions)).strip()

    def _semantic_search(self, query: str, limit: int) -> list[KnowledgeMatch]:
        self._ensure_embeddings()
        query_vector = self._query_embeddings.get(query)
        if query_vector is None:
            response = self._embedding_call([query])
            query_vector = list(response.data[0].embedding)
            self._query_embeddings[query] = query_vector

        intended_sources = self._intended_sources(query)
        ranked: list[KnowledgeMatch] = []
        for chunk, vector in zip(self._chunks, self._embeddings):
            if intended_sources and chunk.document_name not in intended_sources:
                continue
            semantic_score = self._cosine_similarity(query_vector, vector)
            lexical_score = self._lexical_score(query, chunk)
            score = (semantic_score * 0.88) + (min(1.0, lexical_score) * 0.12)
            if score >= 0.24:
                ranked.append(KnowledgeMatch(chunk.document_name, chunk.category, chunk.page_number, chunk.text, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return self._select_diverse_results(ranked, limit, relative_floor=0.72)

    def _lexical_search(self, query: str, limit: int) -> list[KnowledgeMatch]:
        intended_sources = self._intended_sources(query)
        ranked: list[KnowledgeMatch] = []
        for chunk in self._chunks:
            if intended_sources and chunk.document_name not in intended_sources:
                continue
            score = self._lexical_score(query, chunk)
            if score >= 0.16:
                ranked.append(KnowledgeMatch(chunk.document_name, chunk.category, chunk.page_number, chunk.text, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return self._select_diverse_results(ranked, limit, relative_floor=0.45)

    def _lexical_score(self, query: str, chunk: KnowledgeMatch) -> float:
        query_terms = self._terms(query)
        query_grams = self._character_grams(query)
        text_normalized = self._normalize_text(chunk.text)
        text_grams = self._character_grams(text_normalized)
        gram_score = len(query_grams & text_grams) / max(1, len(query_grams))
        term_score = sum(1 for term in query_terms if term in text_normalized) / max(1, len(query_terms))
        source_text = self._normalize_text(f"{chunk.document_name} {chunk.category}")
        source_boost = 0.25 if any(term in source_text for term in query_terms) else 0.0
        exact_boost = 0.3 if query in text_normalized else 0.0
        return (gram_score * 0.55) + (term_score * 0.45) + source_boost + exact_boost

    def _select_diverse_results(
        self,
        ranked: list[KnowledgeMatch],
        limit: int,
        relative_floor: float,
    ) -> list[KnowledgeMatch]:
        if not ranked:
            return []
        floor = ranked[0].score * relative_floor
        results: list[KnowledgeMatch] = []
        source_counts: dict[str, int] = {}
        for match in ranked:
            if match.score < floor or source_counts.get(match.document_name, 0) >= 2:
                continue
            if any(self._near_duplicate(match.text, existing.text) for existing in results):
                continue
            results.append(match)
            source_counts[match.document_name] = source_counts.get(match.document_name, 0) + 1
            if len(results) == limit:
                break
        return results

    @classmethod
    def _intended_sources(cls, query: str) -> set[str]:
        sources = {
            source
            for source, aliases in cls.SOURCE_INTENTS.items()
            if any(alias in query for alias in aliases)
        }
        if any(alias in query for alias in ("5 โมดูล", "5 module", "five module")):
            sources.update(("หนังสือ 5 โมดูลธุรกิจ MLM", "คู่มือแผนงาน MLM"))
        return sources

    def _ensure_text_index(self) -> None:
        if self._indexed:
            return
        if self.embedding_client is not None and self._load_cache():
            self._indexed = True
            return
        seen_passages: set[str] = set()
        for document in self.list_documents():
            try:
                for page_number, text in self._extract_document_text(document):
                    if len(text) < 40:
                        continue
                    for passage in self._split_passages(text):
                        key = self._normalize_text(passage)
                        if key in seen_passages:
                            continue
                        seen_passages.add(key)
                        self._chunks.append(
                            KnowledgeMatch(
                                self._display_source_name(document),
                                document.category,
                                page_number,
                                passage,
                                0.0,
                            )
                        )
            except Exception:
                continue
        self._indexed = True

    def _extract_document_text(self, document: KnowledgeDocument) -> list[tuple[int, str]]:
        if document.path.suffix.casefold() in self.TEXT_DOCUMENT_EXTENSIONS:
            text = self.clean_markdown_text(document.path.read_text(encoding="utf-8", errors="ignore"))
            return [(1, text)] if text else []
        if PdfReader is None:
            raise RuntimeError("ระบบค้นหาข้อความ PDF ต้องใช้ pypdf กรุณาติดตั้งแพ็กเกจตาม requirements.txt")
        reader = PdfReader(document.path)
        return [
            (page_number, self.clean_pdf_text(page.extract_text() or "", document.path.name))
            for page_number, page in enumerate(reader.pages, start=1)
        ]

    def _ensure_embeddings(self) -> None:
        if len(self._embeddings) == len(self._chunks) and self._embeddings:
            return
        self._embeddings = []
        texts = [chunk.text for chunk in self._chunks]
        for start in range(0, len(texts), 64):
            response = self._embedding_call(texts[start : start + 64])
            self._embeddings.extend(list(item.embedding) for item in response.data)
        if len(self._embeddings) != len(self._chunks):
            raise RuntimeError("จำนวน embeddings ไม่ตรงกับจำนวนข้อความในคลังความรู้")
        self._save_cache()

    def _embedding_call(self, texts: list[str]) -> Any:
        callback = lambda: self.embedding_client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        if self.openai_runtime:
            return self.openai_runtime.call("embeddings", callback)
        return callback()

    @classmethod
    def clean_pdf_text(cls, text: str, filename: str = "") -> str:
        # NFC preserves Thai SARA AM (ำ), which NFKC decomposes into less readable glyphs.
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\x00", "").replace("\ufeff", "").replace("�", "")
        text = "".join(character for character in text if unicodedata.category(character) not in {"Cc", "Co"} or character in "\n\t")
        filename_variants = {
            filename.casefold(),
            Path(filename).stem.casefold(),
            Path(filename).stem.replace("_", " ").casefold(),
        } - {""}
        cleaned_lines: list[str] = []
        seen_lines: set[str] = set()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            line = re.sub(r"(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])", "", line)
            line = re.sub(r"\b(?:[A-Za-z]\s+){2,}[A-Za-z]\b", lambda match: match.group(0).replace(" ", ""), line)
            line = re.sub(r"([!?.•\-_=])\1{2,}", r"\1", line)
            line = re.sub(r"\s+", " ", line).strip(" |•_-=")
            normalized_line = line.casefold()
            if not line or normalized_line in filename_variants or normalized_line.endswith(".pdf"):
                continue
            if re.fullmatch(r"(?:หน้า|page)?\s*\d{1,4}", normalized_line):
                continue
            if cls._is_ocr_noise(line):
                continue
            dedupe_key = re.sub(r"[^a-z0-9\u0E00-\u0E7F\u1000-\u109F]", "", normalized_line)
            if len(dedupe_key) >= 8 and dedupe_key in seen_lines:
                continue
            if dedupe_key:
                seen_lines.add(dedupe_key)
            cleaned_lines.append(line)

        cleaned = " ".join(cleaned_lines)
        for variant in sorted(filename_variants, key=len, reverse=True):
            if len(variant) >= 6:
                cleaned = re.sub(re.escape(variant), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b([^\s]{2,})(?:\s+\1){2,}\b", r"\1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"([\u0E00-\u0E7F]{4,40})(?:\s*\1){1,}", r"\1", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def clean_markdown_text(cls, text: str) -> str:
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"^---\s.*?\s---", " ", text, flags=re.DOTALL)
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s{0,3}\d+[.)]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_~>|#]", " ", text)
        return cls.clean_pdf_text(text)

    @staticmethod
    def _is_ocr_noise(line: str) -> bool:
        if len(line) < 3:
            return True
        useful = sum(
            character.isalnum()
            or "\u0E00" <= character <= "\u0E7F"
            or "\u1000" <= character <= "\u109F"
            or character.isspace()
            for character in line
        )
        return useful / len(line) < 0.55

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        return re.sub(r"\s+", " ", cls.clean_pdf_text(text).casefold()).strip()

    @staticmethod
    def _split_passages(text: str, size: int = 900, overlap: int = 120) -> list[str]:
        if len(text) <= size:
            return [text]
        passages: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                boundaries = [text.rfind(mark, start + size // 2, end) for mark in (" ", ".", "?", "!", "ฯ")]
                boundary = max(boundaries)
                if boundary > start:
                    end = boundary + 1
            passage = text[start:end].strip()
            if len(passage) >= 40:
                passages.append(passage)
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
        return passages

    @staticmethod
    def _terms(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]{2,}|[\u0E00-\u0E7F]{3,}|[\u1000-\u109F]{3,}", text))

    @staticmethod
    def _character_grams(text: str, width: int = 3) -> set[str]:
        compact = re.sub(r"[^a-z0-9\u0E00-\u0E7F\u1000-\u109F]", "", text)
        return {compact[index : index + width] for index in range(max(0, len(compact) - width + 1))}

    @classmethod
    def _near_duplicate(cls, first: str, second: str) -> bool:
        first_grams = cls._character_grams(first, 5)
        second_grams = cls._character_grams(second, 5)
        if not first_grams or not second_grams:
            return False
        return len(first_grams & second_grams) / len(first_grams | second_grams) >= 0.82

    @staticmethod
    def _cosine_similarity(first: list[float], second: list[float]) -> float:
        if not first or len(first) != len(second):
            return 0.0
        denominator = math.sqrt(sum(value * value for value in first)) * math.sqrt(sum(value * value for value in second))
        return sum(left * right for left, right in zip(first, second)) / denominator if denominator else 0.0

    def _cache_fingerprint(self) -> str:
        files = [
            (str(document.path.relative_to(self.knowledge_dir)), document.size_bytes, document.path.stat().st_mtime_ns)
            for document in self.list_documents()
        ]
        payload = json.dumps(
            {"files": files, "model": self.embedding_model, "cleaning": self.CLEANING_VERSION},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_cache(self) -> bool:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if data.get("fingerprint") != self._cache_fingerprint():
                return False
            chunks = data.get("chunks", [])
            embeddings = data.get("embeddings", [])
            if not chunks or len(chunks) != len(embeddings):
                return False
            self._chunks = [KnowledgeMatch(**chunk) for chunk in chunks]
            self._embeddings = embeddings
            return True
        except (OSError, ValueError, TypeError):
            return False

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fingerprint": self._cache_fingerprint(),
                "chunks": [
                    {
                        "document_name": chunk.document_name,
                        "category": chunk.category,
                        "page_number": chunk.page_number,
                        "text": chunk.text,
                        "score": 0.0,
                    }
                    for chunk in self._chunks
                ],
                "embeddings": self._embeddings,
            }
            self.cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _display_source_name(self, document: KnowledgeDocument) -> str:
        if document.path.suffix.casefold() in self.TEXT_DOCUMENT_EXTENSIONS:
            return document.path.name
        return self.SOURCE_ALIASES.get(document.path.stem.casefold(), document.name)

    def _to_document(self, path: Path) -> KnowledgeDocument:
        relative = path.resolve().relative_to(self.knowledge_dir)
        category = relative.parts[0] if len(relative.parts) > 1 else self._infer_category(path.stem)
        return KnowledgeDocument(path.stem, category, path.stat().st_size, path.resolve())

    def _document_paths(self) -> list[Path]:
        return [
            path
            for path in self.knowledge_dir.rglob("*")
            if path.is_file() and path.suffix.casefold() in self.SUPPORTED_EXTENSIONS
        ]

    def _infer_category(self, name: str) -> str:
        normalized = name.casefold().replace("_", " ").replace("+", " ")
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return "ทั่วไป"
