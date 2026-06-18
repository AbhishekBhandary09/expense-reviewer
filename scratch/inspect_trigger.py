import os

search_dir = r"c:\Users\user\OneDrive\my-first-project\.venv\Lib\site-packages\google\adk"
query = "trigger"

for root, dirs, files in os.walk(search_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if query in content:
                        print(f"Found in {path}")
            except Exception:
                pass
