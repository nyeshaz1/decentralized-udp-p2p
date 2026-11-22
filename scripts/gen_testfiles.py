import os
os.makedirs("shared_files", exist_ok=True)
for name, mb in [("fileA.bin", 3), ("fileB.bin", 5)]:
    with open(os.path.join("shared_files", name), "wb") as f:
        f.write(os.urandom(mb * 1024 * 1024))
print("created fileA.bin (3 MB), fileB.bin (5 MB)")
