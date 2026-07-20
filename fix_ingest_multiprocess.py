with open("ingest_nccn.py", "r") as f:
    code = f.read()

import_multiprocessing = """import concurrent.futures
"""

if "concurrent.futures" not in code:
    code = code.replace("import glob", "import glob\nimport concurrent.futures")

def_process_file = """
def process_file(file_path):
    import os
    from src.ingestion import AdvancedIngestionPipeline
    from src.retrieval import HybridRetriever
    parser = AdvancedIngestionPipeline()
    retriever = HybridRetriever()

    file_name = os.path.basename(file_path)
    print(f"\\n📄 Parsing: {file_name}...")
    try:
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
            formatted_payloads.append(
                {"text": chunk.text, "metadata": chunk.metadata.model_dump()}
            )
        if formatted_payloads:
            print(f"   -> Uploading embeddings to Qdrant Cloud cluster...")
            retriever.index_documents(formatted_payloads)
            print(f"   ✅ Completed processing for: {file_name}")
        else:
            print(f"   ⚠️ Warning: No valid context blocks passed filtering for {file_name}")
    except Exception as e:
        print(f"   ❌ Critical failure processing {file_name}: {str(e)}")
        print("   Skipping to next file...")
"""

if "def process_file" not in code:
    code = code.replace("def mass_ingest_nccn():", def_process_file + "\n\ndef mass_ingest_nccn():")

# Replace loop with ProcessPoolExecutor
loop_code = """
    # 3. Process and upload each PDF document sequentially
    for file_path in pdf_files:
        file_name = os.path.basename(file_path)
        print(f"\\n📄 Parsing: {file_name}...")

        try:
            # Dynamically extract a year for the metadata tracker
            # Defaults to 2023 if not matched in the filename
            pub_year = "2023"
            for word in ["2023", "2022", "2024"]:
                if word in file_name:
                    pub_year = word
                    break

            # Phase 1: Convert, filter out text noise, and aggregate tiny text blocks
            parsing_result = parser.process_docling(file_path, year=pub_year)
            chunks = parsing_result["chunks"]

            print(f"   -> Successfully extracted {len(chunks)} high-density chunks.")

            # Format the Pydantic chunks into the exact dict payloads Qdrant expects
            formatted_payloads = []
            for chunk in chunks:
                formatted_payloads.append(
                    {"text": chunk.text, "metadata": chunk.metadata.model_dump()}
                )

            # Phase 2/3: Compute BGE embeddings and push to Qdrant Cloud over the network
            if formatted_payloads:
                print(f"   -> Uploading embeddings to Qdrant Cloud cluster...")
                retriever.index_documents(formatted_payloads)
                print(f"   ✅ Completed processing for: {file_name}")
            else:
                print(
                    f"   ⚠️ Warning: No valid context blocks passed filtering for {file_name}"
                )

        except Exception as e:
            print(f"   ❌ Critical failure processing {file_name}: {str(e)}")
            print("   Skipping to next file...")
"""

new_loop = """
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        executor.map(process_file, pdf_files)
"""
code = code.replace(loop_code, new_loop)

with open("ingest_nccn.py", "w") as f:
    f.write(code)
print("Updated ingest_nccn.py")
