import os
import json
from typing import List

def generate_manifest(jobs_folder: str = 'jobs') -> None:
    """Generate a manifest JSON file listing all job JSONs in the jobs_folder."""
    manifest_file = os.path.join(jobs_folder, 'job_manifest.json')
    if not os.path.exists(jobs_folder):
        print(f"Error: Folder '{jobs_folder}' not found.")
        return
    try:
        json_files: List[str] = [
            filename for filename in os.listdir(jobs_folder)
            if filename.endswith('.json') and filename != 'job_manifest.json'
        ]
        json_files.sort()
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(json_files, f, indent=2)
        print(f"Generated {manifest_file} with {len(json_files)} job files.")
    except Exception as e:
        print(f"Failed to generate manifest: {e}")

if __name__ == "__main__":
    generate_manifest()
