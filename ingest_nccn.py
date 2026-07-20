import os
import glob
import json
from src.ingestion import AdvancedIngestionPipeline
from src.retrieval import HybridRetriever

def mass_ingest_nccn():
    print("=======================================================")
    print("🚀 Initializing Qdrant Cloud Mass Ingestion Pipeline...")
    print("=======================================================\n")

    parser = AdvancedIngestionPipeline()
    retriever = HybridRetriever()

    pdf_pattern = os.path.join("NCCN_Guidelines_dataset", "guidelines", "*.pdf")
    pdf_files = glob.glob(pdf_pattern)

    if not pdf_files:
        print("❌ Error: No NCCN PDFs found. Verify the path matches your dataset directory.")
        return

    print(f"📁 Found {len(pdf_files)} PDF files to process.")

    for file_path in pdf_files:
        file_name = os.path.basename(file_path)
        print(f"\n📄 Parsing: {file_name}...")
        
        try:
            cache_file = f"chunks_{file_name}.json"
            if os.path.exists(cache_file):
                print(f"   -> Loading from cache: {cache_file}")
                with open(cache_file, "r") as f:
                    formatted_payloads = json.load(f)
            else:
                pub_year = "2023"
                for word in ["2023", "2022", "2024"]:
                    if word in file_name:
                        pub_year = word
                        break
                parsing_result = parser.process_docling(file_path, year=pub_year)
                chunks = parsing_result["chunks"]
                print(f"   -> Successfully extracted {len(chunks)} high-density chunks.")
                formatted_payloads = []
                for chunk in chunks:
                    formatted_payloads.append({"text": chunk.text, "metadata": chunk.metadata.model_dump()})
                with open(cache_file, "w") as f:
                    json.dump(formatted_payloads, f)
            
            if formatted_payloads:
                print(f"   -> Uploading embeddings to Qdrant Cloud cluster...")
                retriever.index_documents(formatted_payloads)
                print(f"   ✅ Completed processing for: {file_name}")
            else:
                print(f"   ⚠️ Warning: No valid context blocks passed filtering for {file_name}")

        except Exception as e:
            print(f"   ❌ Critical failure processing {file_name}: {str(e)}")
            print("   Skipping to next file...")

    print("\n=======================================================")
    print("🎉 NCCN Dataset successfully indexed to Qdrant Cloud!")
    print("=======================================================")

if __name__ == "__main__":
    mass_ingest_nccn()
