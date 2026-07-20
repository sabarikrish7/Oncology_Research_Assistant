from datasets import Dataset
from ragas import evaluate
from ragas.metrics.collections import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

data = {
    "question": ["What is the capital of France?"],
    "answer": ["Paris is the capital."],
    "contexts": [["Paris is the capital and most populous city of France."]],
    "ground_truth": ["Paris"]
}
dataset = Dataset.from_dict(data)

eval_llm = ChatOllama(model="llama3")
eval_embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5", model_kwargs={'device': 'cpu'})
ragas_llm = LangchainLLMWrapper(eval_llm)
ragas_emb = LangchainEmbeddingsWrapper(eval_embeddings)

print("Evaluating...")
res = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall], llm=ragas_llm, embeddings=ragas_emb)
print(res)
