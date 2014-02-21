import sys

pad_to = lambda w,list: list + [''] * max(0, w - len(list))

blocks = {}
block = None
offset = 0
for n, line in enumerate(sys.stdin):
	line = line.strip().split()
	if not line:
		block = None
		continue
	if block is None:
		block = tuple(line[:2])
		offset = n

	n -= offset
	this = blocks.setdefault(block, [])
	line = pad_to(6, line)
	try:
		this[n] += line
	except Exception:
		assert n == len(this)
		this.append(line)

for block in blocks:
	name = "-".join(("block",) + block) + ".csv"
	with open(name, "w") as fd:
		for line in blocks[block]:
			fd.write(",".join(line) + "\n")
