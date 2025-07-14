import os
import json

jobs_folder = 'jobs'
manifest_file = os.path.join(jobs_folder, 'job_manifest.json')

if not os.path.exists(jobs_folder):
    print(f"Error: Folder '{jobs_folder}' not found.")
    exit()

json_files = []
for filename in os.listdir(jobs_folder):
    # Ensure we only pick .json files and not the manifest file itself
    if filename.endswith('.json') and filename != 'job_manifest.json':
        json_files.append(filename)

# Sort for consistent order (important for Git diff and avoiding unnecessary commits)
json_files.sort()

with open(manifest_file, 'w') as f:
    json.dump(json_files, f, indent=2)

print(f"Generated {manifest_file} with {len(json_files)} job files.")
