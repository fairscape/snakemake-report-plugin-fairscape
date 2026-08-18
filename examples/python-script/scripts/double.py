with open(snakemake.input[0]) as f:
    nums = [int(line) for line in f]

with open(snakemake.output[0], "w") as f:
    for n in nums:
        f.write(f"{n * 2}\n")
