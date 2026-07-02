import re
import json
import ollama


class NumericValidator:
    """Extracts and verifies clinical numbers, percentages, and dosages."""

    def __init__(self):
        # Regex to catch standard numbers, percentages, and clinical units (mg, months, kg)
        self.numeric_pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:%|mg|g|kg|mL|months|years)?\b", re.IGNORECASE
        )

    def validate(self, generated_text: str, context: str) -> dict:
        # Extract all numbers from the generated response
        generated_numbers = set(self.numeric_pattern.findall(generated_text))

        if not generated_numbers:
            return {
                "status": "NO_NUMBERS",
                "matched": [],
                "hallucinated": [],
                "score": 1.0,
            }

        matched = []
        hallucinated = []

        # Check if those exact numbers exist in the source context
        for num in generated_numbers:
            if num.lower() in context.lower():
                matched.append(num)
            else:
                hallucinated.append(num)

        # Calculate numeric accuracy score
        score = len(matched) / len(generated_numbers) if generated_numbers else 1.0

        return {
            "status": "PASS" if score == 1.0 else "FAIL",
            "matched": matched,
            "hallucinated": hallucinated,
            "score": score,
        }


class EvidenceVerifier:
    """Uses a secondary LLM call to grade the claim against the context."""

    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name
        self.system_prompt = """You are a strict Medical Fact-Checker. 
Evaluate if the GENERATED CLAIM is supported by the SOURCE EVIDENCE.
Output ONLY a JSON object with two keys:
1. "status": Must be exactly "SUPPORTED", "PARTIALLY SUPPORTED", or "UNSUPPORTED".
2. "reasoning": A one-sentence explanation."""

    def verify(self, claim: str, evidence: str) -> dict:
        prompt = f"SOURCE EVIDENCE:\n{evidence}\n\nGENERATED CLAIM:\n{claim}"

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            # Parse the text response into a JSON dictionary
            result_text = response["message"]["content"].strip()

            # Simple cleanup in case the LLM wrapped it in markdown codeblocks
            if result_text.startswith("```json"):
                result_text = (
                    result_text.replace("```json", "").replace("```", "").strip()
                )

            # Robust JSON extraction: Find the first { and the last }
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                clean_json_string = match.group(0)
                return json.loads(clean_json_string)
            else:
                return {
                    "status": "ERROR",
                    "reasoning": "Could not find valid JSON block in LLM response.",
                }

        except json.JSONDecodeError as e:
            return {
                "status": "ERROR",
                "reasoning": f"JSON Parsing Failed: {str(e)}. Raw Output: {result_text}",
            }
        except Exception as e:
            return {"status": "ERROR", "reasoning": str(e)}


class ConfidenceScorer:
    """Combines metrics into a final Confidence Score."""

    def calculate_final_score(
        self,
        reranker_score: float,
        numeric_validation: dict,
        llm_verification: dict,
        sources: list,
    ) -> dict:
        # 1. Base Score from Reranker (0.0 to 1.0 scale assumed here)
        score = reranker_score * 20  # Base 20%

        # 2. Source Quality Bonus (Max 20%)
        source_score = 0
        for source in sources:
            if "NCCN" in source or "ClinicalTrials" in source:
                source_score += 10  # High tier
            elif "PubMed" in source:
                source_score += 5  # Mid tier
        score += min(source_score, 20)

        # 3. Numeric Validation (Max 30%)
        score += numeric_validation.get("score", 0.0) * 30

        # 4. LLM Verification (Max 30%)
        llm_status = llm_verification.get("status", "UNSUPPORTED")
        if llm_status == "SUPPORTED":
            score += 30
        elif llm_status == "PARTIALLY SUPPORTED":
            score += 15

        final_percentage = round(min(score, 100))

        # Determine safety threshold (lowered to 80 to accommodate accurate PubMed responses)
        is_safe = final_percentage >= 80 and not numeric_validation.get("hallucinated")

        return {
            "final_score": final_percentage,
            "is_safe_to_display": is_safe,
            "breakdown": {
                "reranker_base": round(reranker_score * 20, 1),
                "source_quality": min(source_score, 20),
                "numeric_match": round(numeric_validation.get("score", 0.0) * 30, 1),
                "llm_verification": llm_status,
            },
        }


class ValidationPipeline:
    """Phase 8 Deliverable: The Master Validation Pipeline"""

    def __init__(self):
        self.num_validator = NumericValidator()
        self.evidence_verifier = EvidenceVerifier()
        self.scorer = ConfidenceScorer()

    def run_validation(
        self, generated_text: str, context: str, reranker_score: float, sources: list
    ) -> dict:
        print("Running Numeric Validation...")
        num_result = self.num_validator.validate(generated_text, context)

        print("Running Independent LLM Verification...")
        ver_result = self.evidence_verifier.verify(generated_text, context)

        print("Calculating Composite Confidence Score...")
        final_score = self.scorer.calculate_final_score(
            reranker_score, num_result, ver_result, sources
        )

        return {
            "numeric_check": num_result,
            "llm_check": ver_result,
            "confidence_score": final_score,
        }


# --- Execution Test Block ---
if __name__ == "__main__":
    pipeline = ValidationPipeline()

    # Simulating a scenario where Phase 7 generated an answer based on context
    source_context = "Sotorasib showed a 37.1% objective response rate in the phase 2 trial. The median progression-free survival was 6.8 months."
    sources_used = ["PubMed"]
    retrieval_reranker_score = 0.95  # Highly relevant document

    print("=======================================================")
    print("TEST CASE 1: ACCURATE RESPONSE")
    print("=======================================================")
    good_generation = "Sotorasib achieved a 37.1% objective response rate with a progression-free survival of 6.8 months."

    good_result = pipeline.run_validation(
        good_generation, source_context, retrieval_reranker_score, sources_used
    )
    print(json.dumps(good_result, indent=2))

    print("\n=======================================================")
    print("TEST CASE 2: HALLUCINATED NUMBER & EXAGGERATED CLAIM")
    print("=======================================================")
    bad_generation = "Sotorasib achieved a massive 99.9% objective response rate and cures the cancer completely within 12 months."

    bad_result = pipeline.run_validation(
        bad_generation, source_context, retrieval_reranker_score, sources_used
    )
    print(json.dumps(bad_result, indent=2))
