import re
import ollama

class CitationFormattingLayer:
    """Phase 7 Deliverable: Formats input evidence and builds reference bibliographies."""
    
    @staticmethod
    def format_context(retrieved_chunks: list) -> str:
        """Formats the retrieved chunks so the LLM knows the exact Source IDs."""
        context = ""
        for chunk in retrieved_chunks:
            source_id = chunk.get("id", "Unknown")
            text = chunk.get("text", "")
            context += f"[{source_id}] {text}\n"
        return context

    @staticmethod
    def build_reference_list(retrieved_chunks: list, generated_text: str) -> str:
        """Builds a formatted 'Supporting References' list based ONLY on citations the LLM actually used."""
        used_sources = []
        for chunk in retrieved_chunks:
            source_id = chunk.get("id", "")
            # Only include the source in the bibliography if the LLM cited it inline
            if f"[{source_id}]" in generated_text:
                source_name = chunk.get('source', 'Unknown Source')
                title = chunk.get('title', 'Extracted Medical Context')
                used_sources.append(f"• [{source_id}] {source_name}: {title}")
        
        if not used_sources:
            return "No explicit references cited from the provided context."
            
        return "\n".join(used_sources)


class GroundedResponseGenerator:
    """Phase 7 Deliverable: Generates answers and calculates confidence scores."""
    
    def __init__(self, model_name: str = 'llama3'):
        self.model_name = model_name
        self.formatter = CitationFormattingLayer()
        self.system_prompt = """You are a strict clinical oncology assistant.
Your task is to answer the user's question using ONLY the provided evidence.

RULES:
1. Every factual claim MUST end with the exact inline citation from the evidence. 
   Example: "Osimertinib is recommended for EGFR mutations [NCCN_v3]."
2. If the evidence does not contain the answer, say exactly: "I cannot answer this based on the retrieved evidence."
3. Do NOT use external knowledge. Do NOT invent source IDs. Do not add a bibliography, the system will do that."""

    def calculate_confidence_score(self, answer: str) -> str:
        """Calculates a confidence score based on citation density per sentence."""
        if "I cannot answer this" in answer:
            return "0% - Insufficient Context"
        
        # Split into sentences to check citation density
        sentences = [s for s in answer.split('.') if s.strip() and len(s.strip()) > 5]
        if not sentences:
            return "0% - Empty Response"
            
        cited_sentences = sum(1 for s in sentences if '[' in s and ']' in s)
        ratio = cited_sentences / len(sentences)
        
        if ratio >= 0.8:
            return f"High ({int(ratio*100)}%) - Strongly Grounded"
        elif ratio >= 0.4:
            return f"Medium ({int(ratio*100)}%) - Partially Grounded"
        else:
            return f"Low ({int(ratio*100)}%) - High Risk of Hallucination"

    def generate(self, query: str, retrieved_chunks: list) -> dict:
        """The main execution pipeline for Phase 7."""
        # 1. Format Evidence via the Formatting Layer
        context = self.formatter.format_context(retrieved_chunks)
        
        # 2. Generate Prompt
        user_prompt = f"EVIDENCE:\n{context}\n\nQUESTION: {query}\n\nANSWER WITH INLINE CITATIONS:"
        
        # 3. Call LLM
        print(f"Synthesizing strictly grounded response via {self.model_name}...\n")
        try:
            response = ollama.chat(model=self.model_name, messages=[
                {'role': 'system', 'content': self.system_prompt},
                {'role': 'user', 'content': user_prompt}
            ])
            raw_answer = response['message']['content'].strip()
        except Exception as e:
            return {"error": str(e)}
        
        # 4. Calculate Confidence Score
        confidence = self.calculate_confidence_score(raw_answer)
        
        # 5. Build Reference List
        references = self.formatter.build_reference_list(retrieved_chunks, raw_answer)
        
        return {
            "answer": raw_answer,
            "confidence_score": confidence,
            "references": references
        }

# --- Execution Test Block ---
if __name__ == "__main__":
    generator = GroundedResponseGenerator()
    
    # Simulating data arriving from our Phase 3/5 Retrievers
    simulated_chunks = [
        {
            "id": "NCCN_v2023",
            "source": "NCCN Guidelines",
            "title": "Breast Cancer Guidelines Version 4",
            "text": "Trastuzumab deruxtecan is designated for patients with HER2-low unresectable or metastatic breast cancer who have received a prior chemotherapy regimen in the metastatic setting."
        },
        {
            "id": "PMID_356535",
            "source": "PubMed",
            "title": "DESTINY-Breast04 Trial Results",
            "text": "In the DESTINY-Breast04 trial, trastuzumab deruxtecan significantly prolonged progression-free and overall survival compared to standard chemotherapy in HER2-low metastatic breast cancer."
        }
    ]
    
    test_query = "What is the role of trastuzumab deruxtecan in HER2-low metastatic breast cancer and what trial supports it?"
    
    result = generator.generate(test_query, simulated_chunks)
    
    print("=======================================================")
    print("PHASE 7: FULLY GROUNDED OUTPUT")
    print("=======================================================\n")
    print(f"{result.get('answer')}\n")
    print("-" * 55)
    print(f"Confidence Score: {result.get('confidence_score')}")
    print("-" * 55)
    print("Supporting References:")
    print(result.get('references'))
    print("\n=======================================================")