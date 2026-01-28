import json
import os

def filter_empty_titles(file_path):
    """
    Reads a JSONL file, filters out entries with an empty title,
    and overwrites the original file with the filtered content.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    filtered_lines = []
    removed_count = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("title") != "":
                    filtered_lines.append(json.dumps(data, ensure_ascii=False))
                else:
                    removed_count += 1
            except json.JSONDecodeError:
                print(f"Error decoding JSON on line in {file_path}")

    # Overwrite the original file
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in filtered_lines:
            f.write(line + '\n')
            
    print(f"Processed {file_path}: Removed {removed_count} lines. Remaining: {len(filtered_lines)}")

if __name__ == "__main__":
    base_dir = "/Users/backgold/WorkSpace/SKN20-FINAL-6TEAM"
    files_to_process = [
        os.path.join(base_dir, "data/preprocessed/finance/court_cases_tax.jsonl"),
        os.path.join(base_dir, "data/preprocessed/labor/court_cases_labor.jsonl")
    ]
    
    for file_path in files_to_process:
        filter_empty_titles(file_path)
