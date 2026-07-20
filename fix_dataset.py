import json
import uuid
import hashlib

with open("eval/golden_dataset.json", "r") as f:
    data = json.load(f)

for row in data:
    context = row["context"]
    row["expected_source_id"] = str(uuid.UUID(hashlib.md5(context.encode('utf-8')).hexdigest()))[:8]

with open("eval/golden_dataset.json", "w") as f:
    json.dump(data, f, indent=4)
print("Updated golden_dataset.json")
