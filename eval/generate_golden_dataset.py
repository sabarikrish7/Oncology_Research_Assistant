import os
import json
import random
import ollama
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

# We need the Qdrant Cloud connection
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
COLLECTION_NAME = "oncology_guidelines"
OLLAMA_MODEL = "llama3"
DATASET_SIZE = 50

def generate_golden_dataset():
    print("Fetching chunks from Qdrant...")
    # Scroll to get chunks
    records, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=500,  # fetch 500 to sample from
        with_payload=True,
        with_vectors=False,
    )
    
    # Filter out very short chunks
    valid_chunks = [r for r in records if r.payload and len(r.payload.get("text", "")) > 200]
    
    # Sample random chunks
    sampled = random.sample(valid_chunks, min(DATASET_SIZE, len(valid_chunks)))
    print(f"Sampled {len(sampled)} chunks for generation.")
    
    dataset = []
    
    for i, record in enumerate(sampled):
        chunk_text = record.payload.get("text", "")
        metadata = record.payload.get("metadata", {})
        chunk_id = metadata.get("chunk_id", f"ID_{record.id}")[:8]
        
        print(f"[{i+1}/{len(sampled)}] Generating query for chunk {chunk_id}...")
        
        prompt = f"""
You are an expert oncologist creating an evaluation dataset.
Read the following text chunk from clinical guidelines:
---
{chunk_text}
---
Generate a realistic clinical question that can be answered EXACTLY and ONLY by this chunk.
Then provide the concise ground truth answer (key facts).
Respond strictly in JSON format with keys "query" and "ground_truth". No other text.
"""
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json"
            )
            data = json.loads(response["message"]["content"].strip())
            
            # Ensure keys exist
            if "query" in data and "ground_truth" in data:
                dataset.append({
                    "id": f"q_synth_{i+1}",
                    "query": data["query"],
                    "ground_truth": data["ground_truth"],
                    "expected_source_id": chunk_id,
                    "context": chunk_text
                })
        except Exception as e:
            print(f"Failed to generate for chunk {chunk_id}: {e}")
            
    out_path = Path(__file__).parent / "golden_dataset.json"
    with open(out_path, "w") as f:
        json.dump(dataset, f, indent=2)
        
    print(f"\nSuccessfully generated {len(dataset)} queries. Saved to {out_path}")

if __name__ == "__main__":
    generate_golden_dataset()
