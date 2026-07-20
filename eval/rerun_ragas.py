import json
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

def rerun_ragas():
    print("Loading checkpoint...")
    with open("eval/ragas_data_checkpoint.json", "r") as f:
        ragas_data = json.load(f)

    # Convert to dataset
    ragas_dataset = Dataset.from_dict(ragas_data)

    print("Initializing LLM and Embeddings...")
    eval_llm = ChatOllama(model="llama3")
    eval_embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-en-v1.5",
        model_kwargs={'device': 'cpu'}
    )
    ragas_llm = LangchainLLMWrapper(eval_llm)
    ragas_emb = LangchainEmbeddingsWrapper(eval_embeddings)

    print("Running RAGAS Evaluation...")
    try:
        # NOTE: RAGAS 0.4+ requires metrics to be instantiated!
        ragas_results = evaluate(
            ragas_dataset,
            metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
            llm=ragas_llm,
            embeddings=ragas_emb
        )
        print("\nRAGAS Results:", ragas_results)

        print("\nUpdating snapshot_report.md...")
        # We need to append the RAGAS results to the report
        with open("eval/snapshot_report.md", "a") as f:
            f.write("\n## RAGAS Metrics\n\n")
            for metric, value in ragas_results.items():
                f.write(f"- **{metric}**: {value:.4f}\n")
        
        print("Success!")
    except Exception as e:
        print("RAGAS evaluation failed:", e)

if __name__ == "__main__":
    rerun_ragas()
