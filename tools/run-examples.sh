#!/usr/bin/env bash
# Run every example workflow, generate its FAIRSCAPE crate, validate it, and
# assert ARK stability across a second report invocation.
set -euo pipefail

cd "$(dirname "$0")/.."
root=$(pwd)
snakemake=${SNAKEMAKE:-snakemake}
# check the crates with the same interpreter that runs the reporter, so a
# snakemake from one environment is never validated against another's packages
python=${PYTHON:-"$(dirname "$(command -v "$snakemake")")/python"}
[ -x "$python" ] || python=python3

artifacts=(ro-crate-datasheet.html ai_ready_score.json ro-crate-linkml.yaml
           ro-crate-prov-graph.json ro-crate-prov-graph.html)

# The derived artifacts are produced by fairscape-cli's process_crate, which
# exists from fairscape-cli 1.2.10. Against an older one the plugin writes the
# crate and skips them with a note, so assert them only when they are possible.
if "$python" -c "from fairscape_cli.utils.build_utils import process_crate" 2>/dev/null; then
    check_artifacts=1
else
    check_artifacts=0
    echo "NOTE: installed fairscape-cli cannot import process_crate (needs >= 1.2.10);"
    echo "      crates are still built and validated, derived artifacts are not asserted."
fi

arks() { "$python" -c "import json,sys; [print(n['@id']) for n in json.load(open(sys.argv[1]))['@graph']]" "$1"; }

for example in examples/*/; do
    name=$(basename "$example")
    echo "=== $name"
    (
        cd "$example"
        flags=""
        [ -f reporter-flags ] && flags=$(cat reporter-flags)
        # never let a previous run's output stand in for this one's
        rm -f ro-crate-metadata.json "${artifacts[@]}"
        $snakemake --cores 2 --quiet all >/dev/null
        log=$(mktemp)
        $snakemake --reporter fairscape $flags >"$log" 2>&1 || { cat "$log"; exit 1; }
        grep -E "^(NOTE|WARNING|ERROR):" "$log" | sed 's/^/  /' || true
        rm -f "$log"
        "$python" "$root/tools/validate_crate.py" ro-crate-metadata.json
        if [ "$check_artifacts" = 1 ]; then
            for artifact in "${artifacts[@]}"; do
                if [ ! -f "$artifact" ]; then
                    echo "  MISSING derived artifact: $artifact" >&2
                    exit 1
                fi
            done
            echo "  derived artifacts present (datasheet, ai-ready, linkml, prov-graph)"
        else
            echo "  derived artifacts not asserted (fairscape-cli too old)"
        fi
        arks ro-crate-metadata.json > /tmp/arks-before.$$
        $snakemake --reporter fairscape $flags >/dev/null 2>&1
        arks ro-crate-metadata.json > /tmp/arks-after.$$
        if diff -q /tmp/arks-before.$$ /tmp/arks-after.$$ >/dev/null; then
            echo "  ARKs stable across report re-run"
        else
            echo "  ARKs CHANGED across report re-run" >&2
            diff /tmp/arks-before.$$ /tmp/arks-after.$$ >&2 || true
            exit 1
        fi
        rm -f /tmp/arks-before.$$ /tmp/arks-after.$$
    )
done
echo "ALL EXAMPLES PASS"
