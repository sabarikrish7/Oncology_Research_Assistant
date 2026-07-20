import json
import os
from qdrant_client import QdrantClient

# Load the current golden dataset
with open("eval/golden_dataset.json", "r") as f:
    golden_data = json.load(f)

# Connect to Qdrant
from dotenv import load_dotenv
load_dotenv()

qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

# Scroll all chunks in oncology_guidelines_medcpt
collection_name = "oncology_guidelines_medcpt"

print(f"Scrolling collection {collection_name} to map texts to new IDs...")
text_to_id = {}
next_page_offset = None
while True:
    records, next_page_offset = client.scroll(
        collection_name=collection_name,
        limit=500,
        with_payload=True,
        with_vectors=False,
        offset=next_page_offset
    )
    for record in records:
        payload = record.payload or {}
        text = payload.get("text", "")
        if text:
            # chunk_id from payload, fallback to record.id
            chunk_id = payload.get("metadata", {}).get("chunk_id", str(record.id))[:8]
            text_to_id[text.strip()] = chunk_id
            
    if next_page_offset is None:
        break

print(f"Loaded {len(text_to_id)} chunks from Qdrant.")

# Map the golden dataset
mapped = 0
for entry in golden_data:
    context = entry["context"].strip()
    if context in text_to_id:
        entry["expected_source_id"] = text_to_id[context]
        mapped += 1
    else:
        print(f"Warning: context not found in Qdrant for question: {entry['question']}")

print(f"Mapped {mapped}/{len(golden_data)} entries.")

with open("eval/golden_dataset_medcpt.json", "w") as f:
    json.dump(golden_data, f, indent=4)
print("Saved to eval/golden_dataset_medcpt.json")
