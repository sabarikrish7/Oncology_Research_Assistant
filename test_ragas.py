from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings
from datasets import Dataset

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

eval_llm = ChatOllama(model="llama3")
eval_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5",
    model_kwargs={'device': 'cpu'}
)

ragas_llm = LangchainLLMWrapper(eval_llm)
ragas_emb = LangchainEmbeddingsWrapper(eval_embeddings)

data = {
    "question": ["What is 2+2?"],
    "answer": ["It is 4."],
    "contexts": [["2+2=4 is a well known math fact."]],
    "ground_truth": ["4"]
}
ds = Dataset.from_dict(data)

try:
    res = evaluate(ds, metrics=[faithfulness], llm=ragas_llm, embeddings=ragas_emb)
    print("Evaluate Option 1 success:", res)
except Exception as e:
    print("Option 1 Failed:", e)
