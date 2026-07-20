import os
import time
import uuid
import hashlib
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import fitz  # PyMuPDF
from docling.document_converter import DocumentConverter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import CHUNK_SIZE, CHUNK_OVERLAP


class OncologyChunkMetadata(BaseModel):
    """Upgraded schema to support multiple oncology guideline publishers."""

    source: str = Field(..., description="File path or URL of the guideline")
    publisher: str = Field(default="Unknown", description="NCCN, ESMO, ASCO, etc.")
    page: int = Field(..., description="Page number of the chunk")
    document_type: str = Field(
        default="Clinical Guideline", description="Type of document"
    )
    publication_date: str = Field(..., description="Year of publication")
    section: Optional[str] = Field(None, description="Guideline section/heading")
    chunk_id: str = Field(default="", description="Unique identifier")


class DocumentChunk(BaseModel):
    text: str
    metadata: OncologyChunkMetadata


class AdvancedIngestionPipeline:
    def __init__(self):
        self.docling_converter = DocumentConverter()

    def determine_publisher(self, file_path: str) -> str:
        path_lower = file_path.lower()
        if "nccn" in path_lower:
            return "NCCN"
        if "esmo" in path_lower:
            return "ESMO"
        if "asco" in path_lower:
            return "ASCO"
        return "General Oncology"

    def process_docling(
        self,
        file_path: str,
        year: str,
        target_chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> Dict[str, Any]:
        start_time = time.time()
        result = self.docling_converter.convert(file_path)
        publisher = self.determine_publisher(file_path)
        raw_chunks = []

        # Extract Tables
        for table in result.document.tables:
            meta = OncologyChunkMetadata(
                source=file_path,
                publisher=publisher,
                page=table.prov[0].page_no if table.prov else 0,
                publication_date=year,
                section="Tabular Data",
            )
            table_text = table.export_to_markdown(doc=result.document)
            meta.chunk_id = str(uuid.UUID(hashlib.md5(table_text.encode('utf-8')).hexdigest()))
            raw_chunks.append(
                DocumentChunk(
                    text=table_text, metadata=meta
                )
            )

        # Extract Text
        noise_filters = [
            "nccn.org",
            "esmo.org",
            "asco.org",
            "continue",
            "table of contents",
            "discussion",
            "index",
            "all rights reserved",
        ]

        page_texts = {}
        for item in result.document.texts:
            text_snippet = item.text.strip()
            if not text_snippet or any(
                noise in text_snippet.lower() for noise in noise_filters
            ):
                continue

            item_page = item.prov[0].page_no if item.prov else 1
            if item_page not in page_texts:
                page_texts[item_page] = []
            page_texts[item_page].append(text_snippet)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=target_chunk_size, chunk_overlap=overlap
        )

        for page_num, texts in page_texts.items():
            combined_text = " ".join(texts)
            if len(combined_text) > 120:
                chunks = text_splitter.split_text(combined_text)
                for chunk in chunks:
                    meta = OncologyChunkMetadata(
                        source=file_path,
                        publisher=publisher,
                        page=page_num,
                        publication_date=year,
                        section="Aggregated Clinical Prose",
                    )
                    meta.chunk_id = str(uuid.UUID(hashlib.md5(chunk.encode('utf-8')).hexdigest()))
                    raw_chunks.append(DocumentChunk(text=chunk, metadata=meta))

        return {
            "method": "Docling (Aggregated)",
            "time_seconds": time.time() - start_time,
            "chunks": raw_chunks,
        }
