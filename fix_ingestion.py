with open("src/ingestion.py", "r") as f:
    code = f.read()

code = code.replace("import uuid", "import uuid\nimport hashlib")
code = code.replace(
    "chunk_id: str = Field(\n        default_factory=lambda: str(uuid.uuid4()), description=\"Unique identifier\"\n    )",
    "chunk_id: str = Field(default=\"\", description=\"Unique identifier\")"
)

# Then in process_docling, we need to assign chunk_id
code = code.replace(
    "metadata=meta",
    "metadata=meta\n                    meta.chunk_id = str(uuid.UUID(hashlib.md5(chunk.encode('utf-8')).hexdigest()))"
)
code = code.replace(
    "text=table.export_to_markdown(doc=result.document), metadata=meta",
    "text=table.export_to_markdown(doc=result.document), metadata=meta\n                meta.chunk_id = str(uuid.UUID(hashlib.md5(table.export_to_markdown(doc=result.document).encode('utf-8')).hexdigest()))"
)

with open("src/ingestion.py", "w") as f:
    f.write(code)

print("ingestion.py updated.")
