import json
import traceback
from src.engine import oncology_rag_agent

try:
    print("Invoking agent...")
    result = oncology_rag_agent.invoke({'query': 'NCCN guidelines for HER2-LOW', 'retries': 0})
    print(json.dumps(result, indent=2))
except Exception as e:
    traceback.print_exc()
