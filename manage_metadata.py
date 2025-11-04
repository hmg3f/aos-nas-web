#!/usr/bin/env python3
import sys
import os
sys.path.append('app')
from module.metadata import UserMetadata

def sync_metadata(store_path):
    """Sync filesystem with metadata database"""
    metadata = UserMetadata(store_path)
    stage_path = os.path.join(store_path, 'stage')
    
    if not os.path.exists(stage_path):
        print(f"Stage path {stage_path} does not exist")
        return
    
    # Get files from filesystem
    fs_files = [f for f in os.listdir(stage_path) if f != '_meta.db']
    
    # Get files from metadata
    db_files = {f[0]: f for f in metadata.get_files()}
    
    # Add missing files to metadata
    for filename in fs_files:
        if filename not in db_files:
            filepath = os.path.join(stage_path, filename)
            size = os.path.getsize(filepath)
            metadata.add_file(filename, size)
            print(f"Added {filename} to metadata")
    
    # Remove deleted files from metadata
    for filename in db_files:
        if filename not in fs_files:
            metadata.remove_file(filename)
            print(f"Removed {filename} from metadata")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python manage_metadata.py sync <user_store_path>")
        sys.exit(1)
    
    cmd, store_path = sys.argv[1], sys.argv[2]
    
    if cmd == "sync":
        sync_metadata(store_path)
    else:
        print("Unknown command. Use 'sync'")
