import re
import json
import ollama
from typing import List, Dict, Any
from src.config import RERANK_BASE_MULTIPLIER, RERANK_BASE_OFFSET, RERANK_BASE_MAX, OLLAMA_MODEL



class NumericValidator:
    @staticmethod
    def validate(generation: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        num_pattern = r"\b\d+(?:\.\d+)?(?:\s?%|\s?months?|\s?weeks?|\s?mg)?\b"
        gen_numbers = set(re.findall(num_pattern, generation.lower()))
        source_text = " ".join([f"{doc.get('id', '')} {doc.get('source', '')} {doc.get('text', '')}".lower() for doc in documents])
        source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", source_text))

        matched = []
        hallucinated = []

        for num in gen_numbers:
            clean_num = re.sub(r"[^\d.]", "", num)
            if clean_num in source_numbers:
                matched.append(num)
            else:
                if clean_num and float(clean_num) > 5.0:
                    hallucinated.append(num)

        status = "FAIL" if hallucinated else "PASS"
        score = 1.0 if status == "PASS" else max(0.0, 1.0 - (len(hallucinated) * 0.5))

        return {
            "status": status,
            "matched": matched,
            "hallucinated": hallucinated,
            "score": score,
        }


class EvidenceVerifier:
    @staticmethod
    def verify(generation: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        context = "\n".join(
            [f"Source: {d.get('source')} - Context: {d.get('text')}" for d in documents]
        )
        prompt = f"""You are an unbiased medical peer reviewer. Evaluate if the generated clinical response is fully supported by the available source context.
CONTEXT:
{context}
GENERATED RESPONSE:
{generation}
Output your analysis strictly in JSON format with keys "status" and "reasoning".
The "status" value must be exactly one of: "SUPPORTED", "PARTIALLY SUPPORTED", or "UNSUPPORTED". Output ONLY valid JSON."""

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}], format="json"
            )
            raw_text = response["message"]["content"].strip()
            return json.loads(raw_text)
        except Exception as e:
            return {
                "status": "ERROR",
                "reasoning": f"Validation parsing crash: {str(e)}",
            }


class ConfidenceScorer:
    @staticmethod
    def calculate(
        numeric_report: Dict[str, Any],
        llm_report: Dict[str, Any],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        max_rerank = (
            max([doc.get("rerank_score", 0.0) for doc in documents])
            if documents
            else 0.0
        )
        rerank_base = min(RERANK_BASE_MAX, max(0.0, (max_rerank + RERANK_BASE_OFFSET) * RERANK_BASE_MULTIPLIER))

        sources = [d.get("source", "").lower() for d in documents]
        # Updated to prioritize all clinical literature endpoints
        source_points = (
            10
            if any(pub in s for s in sources for pub in ["nccn", "esmo", "asco", "pubmed", "clinicaltrials"])
            else 5
        )

        numeric_points = numeric_report["score"] * 30.0
        llm_status = llm_report.get("status", "UNSUPPORTED")
        llm_points = (
            40.0
            if llm_status == "SUPPORTED"
            else (20.0 if llm_status == "PARTIALLY SUPPORTED" else 0.0)
        )

        final_score = int(rerank_base + source_points + numeric_points + llm_points)
        is_safe = (
            final_score >= 80
            and llm_status in ["SUPPORTED", "PARTIALLY SUPPORTED"]
            and numeric_report["status"] == "PASS"
        )

        return {
            "final_score": final_score,
            "is_safe_to_display": is_safe,
            "breakdown": {
                "reranker_base": round(rerank_base, 1),
                "source_quality": source_points,
                "numeric_match": numeric_points,
                "llm_verification": llm_status,
            },
        }
