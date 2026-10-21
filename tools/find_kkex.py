file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"

with open(file_path, "rb") as f:
    data = f.read()

pos = 0
found = []
while True:
    idx = data.find(b"KKEx", pos)
    if idx == -1:
        break
    found.append(idx)
    pos = idx + 4

print("Found KKEx at offsets:", found)
for idx in found:
    print(f"Offset {idx}: {data[idx-10:idx+30]}")
