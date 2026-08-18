import os

os.makedirs(snakemake.output[0], exist_ok=True)
for i in range(7):
    with open(os.path.join(snakemake.output[0], f"plot_{i}.txt"), "w") as f:
        f.write(f"plot {i}\n")
