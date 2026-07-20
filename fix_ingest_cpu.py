with open("ingest_nccn.py", "r") as f:
    code = f.read()

if "os.environ['CUDA_VISIBLE_DEVICES']" not in code:
    code = code.replace("import os", "import os\nos.environ['CUDA_VISIBLE_DEVICES'] = ''")
    with open("ingest_nccn.py", "w") as f:
        f.write(code)
    print("Added CUDA_VISIBLE_DEVICES=''")
