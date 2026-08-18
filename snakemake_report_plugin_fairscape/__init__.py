"""Snakemake report plugin emitting a FAIRSCAPE EVI RO-Crate.

Usage, after a completed run in the working directory:

    snakemake --reporter fairscape

writes ro-crate-metadata.json describing the run: one EVI Computation per
executed job (command, inputs, outputs from Snakemake's persistence metadata),
one EVI Software per rule plus the Snakefile and the Snakemake engine, and one
EVI Dataset per unique file.

Interface tiers this relies on (flagged per the port ground rules):
- declared: ReporterBase constructor contract (rules/results/configfiles/jobs/
  settings/dag), JobRecordInterface.output/starttime/endtime,
  RuleRecordInterface.source/container_img_url/conda_env.
- undeclared but load-bearing: ``dag.workflow.persistence`` and
  ``dag.workflow.main_snakefile`` (the DAGReportInterface declares neither);
  ``persistence.metadata(f)`` -> MetadataRecord (input/shellcmd/params, an
  internal record format, version 6 at time of writing);
  ``job_record.job.wildcards_dict`` (the live Job object; only ``.rule`` is
  declared). Each is wrapped so absence degrades the crate instead of failing.
"""

import getpass
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from snakemake_interface_report_plugins.reporter import ReporterBase
from snakemake_interface_report_plugins.settings import ReportSettingsBase

__version__ = "0.1.0"


@dataclass
class ReportSettings(ReportSettingsBase):
    path: Optional[Path] = field(
        default=None,
        metadata={
            "help": "Path of the RO-Crate metadata file to write "
            "(default: ro-crate-metadata.json in the working directory).",
            "env_var": False,
            "required": False,
        },
    )
    naan: Optional[str] = field(
        default="59853",
        metadata={
            "help": "ARK Name Assigning Authority Number used when minting identifiers.",
            "env_var": False,
            "required": False,
        },
    )
    name: Optional[str] = field(
        default=None,
        metadata={
            "help": "Name of the crate (default: derived from the Snakefile).",
            "env_var": False,
            "required": False,
        },
    )
    description: Optional[str] = field(
        default=None,
        metadata={
            "help": "Description of the crate (min 10 characters).",
            "env_var": False,
            "required": False,
        },
    )
    author: Optional[str] = field(
        default=None,
        metadata={
            "help": "Author recorded on the crate and its entities "
            "(default: the current user name).",
            "env_var": False,
            "required": False,
        },
    )
    keywords: Optional[str] = field(
        default=None,
        metadata={
            "help": "Comma-separated keywords (default: snakemake,workflow).",
            "env_var": False,
            "required": False,
        },
    )
    license: Optional[str] = field(
        default="https://spdx.org/licenses/CC-BY-4.0",
        metadata={
            "help": "License URL recorded on the crate root.",
            "env_var": False,
            "required": False,
        },
    )
    version: Optional[str] = field(
        default="1.0",
        metadata={
            "help": "Version recorded on the crate root.",
            "env_var": False,
            "required": False,
        },
    )
    expand_directories: bool = field(
        default=False,
        metadata={
            "help": "Walk each directory output and register one Dataset per "
            "file inside it (isPartOf the directory, generatedBy its producer). "
            "Off by default: costs one walk per directory output.",
            "env_var": False,
            "required": False,
        },
    )
    expand_max_files: Optional[int] = field(
        default=1000,
        metadata={
            "help": "Cap on files registered per expanded directory output "
            "(the walk is sorted, so the cap is deterministic).",
            "env_var": False,
            "required": False,
        },
    )
    schemas: bool = field(
        default=False,
        metadata={
            "help": "Infer an EVI Schema for every described data file with a "
            "supported extension (csv/tsv/parquet/h5/hdf5/hea/dcm) and link it "
            "from its Dataset. Off by default: reads the data files.",
            "env_var": False,
            "required": False,
        },
    )
    no_datasheet: bool = field(
        default=False,
        metadata={
            "help": "Skip generating ro-crate-datasheet.html and "
            "ai_ready_score.json (on by default; reads the crate JSON only).",
            "env_var": False,
            "required": False,
        },
    )
    no_evidence_graph: bool = field(
        default=False,
        metadata={
            "help": "Skip generating ro-crate-prov-graph.json/.html (on by "
            "default; reads the crate JSON only).",
            "env_var": False,
            "required": False,
        },
    )
    no_linkml: bool = field(
        default=False,
        metadata={
            "help": "Skip generating the D4D/LinkML export "
            "ro-crate-linkml.yaml (on by default; reads the crate JSON only).",
            "env_var": False,
            "required": False,
        },
    )
    no_link_inverses: bool = field(
        default=False,
        metadata={
            "help": "Skip completing the crate against EVI's owl:inverseOf "
            "pairs (on by default; rewrites the crate JSON in place).",
            "env_var": False,
            "required": False,
        },
    )
    preview: bool = field(
        default=False,
        metadata={
            "help": "Also generate ro-crate-preview.html.",
            "env_var": False,
            "required": False,
        },
    )
    croissant: bool = field(
        default=False,
        metadata={
            "help": "Also generate a Croissant JSON-LD export.",
            "env_var": False,
            "required": False,
        },
    )
    merkle: bool = field(
        default=False,
        metadata={
            "help": "Also generate a SHA-256 Merkle tree over the crate's "
            "files (reads every file).",
            "env_var": False,
            "required": False,
        },
    )


def _rule_definition(rule, crate_dir):
    """Resolve the file that defines a rule's action.

    Returns (kind, ref) where kind is "script" | "notebook" | "wrapper" and ref
    is how the crate should reference the file: crate-relative when the file is
    a local file under the crate directory, otherwise the resolved path or URL.
    (None, None) for shell/run rules, wildcard-parameterized definitions, or on
    any resolution failure — the caller falls back to the Snakefile.

    Relies on the live rule object's script/notebook/wrapper/basedir attributes
    (undeclared interface) and snakemake.sourcecache.infer_source_file — the
    same resolution snakemake's own report machinery performs in
    RuleRecord.init_source (snakemake/report/__init__.py).
    """
    try:
        from snakemake.sourcecache import LocalSourceFile, infer_source_file

        for kind in ("script", "notebook"):
            path = getattr(rule, kind, None)
            if not path or "{" in str(path):
                continue
            basedir = getattr(rule, "basedir", None)
            sf = infer_source_file(path, infer_source_file(basedir) if basedir else None)
            uri = sf.get_path_or_uri(secret_free=False)
            if isinstance(sf, LocalSourceFile):
                abs_p = os.path.abspath(uri)
                try:
                    inside = os.path.commonpath([abs_p, str(crate_dir)]) == str(crate_dir)
                except ValueError:
                    inside = False
                uri = os.path.relpath(abs_p, crate_dir) if inside else abs_p
            return kind, str(uri)

        wrapper_spec = getattr(rule, "wrapper", None)
        if wrapper_spec and "{" not in str(wrapper_spec):
            from snakemake import wrapper as wrapper_mod

            sf = wrapper_mod.get_script(
                wrapper_spec,
                rule.workflow.sourcecache,
                prefix=rule.workflow.workflow_settings.wrapper_prefix,
            )
            if sf is not None and not isinstance(sf, dict):
                return "wrapper", str(sf.get_path_or_uri(secret_free=False))
    except Exception:
        pass
    return None, None


def _iso(epoch):
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(epoch).astimezone().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


class Reporter(ReporterBase):
    def render(self):
        import snakemake

        crate_path = Path(self.settings.path or "ro-crate-metadata.json")
        crate_dir = crate_path.resolve().parent

        workflow = getattr(self.dag, "workflow", None)
        persistence = getattr(workflow, "persistence", None)
        snakefile_abs = getattr(workflow, "main_snakefile", None) or "Snakefile"

        run_name = (
            self.settings.name
            or f"Snakemake workflow '{os.path.basename(snakefile_abs)}'"
        )
        author = self.settings.author or getpass.getuser()
        keywords = [
            k.strip() for k in (self.settings.keywords or "snakemake,workflow").split(",")
            if k.strip()
        ]
        settings = {
            "naan": self.settings.naan or "59853",
            "name": run_name,
            "description": self.settings.description
            or f"FAIRSCAPE EVI RO-Crate describing a run of the Snakemake workflow "
            f"'{os.path.basename(snakefile_abs)}'",
            "author": author,
            "keywords": keywords or ["snakemake", "workflow"],
            "license": self.settings.license,
            "version": self.settings.version or "1.0",
            "date_published": datetime.now().astimezone().isoformat(),
        }

        # resolve script/notebook/wrapper definitions per rule from the live
        # rule objects (only .rule is declared on the report job record)
        definitions = {}
        for rec in self.jobs:
            rule_name = str(rec.rule)
            if rule_name in definitions:
                continue
            try:
                live_rule = rec.job.rule
            except Exception:
                continue
            definitions[rule_name] = _rule_definition(live_rule, crate_dir)

        jobs = []
        for rec in self.jobs:
            meta = None
            if persistence is not None and rec.output:
                try:
                    meta = persistence.metadata(rec.output[0])
                except Exception:
                    meta = None
            wildcards = {}
            try:
                wildcards = {
                    str(k): str(v)
                    for k, v in dict(rec.job.wildcards_dict).items()
                }
            except Exception:
                pass
            # script/notebook/wrapper jobs record no shellcmd; say what ran
            shellcmd = meta.shellcmd if meta else None
            def_kind, def_ref = definitions.get(str(rec.rule), (None, None))
            if not shellcmd and def_kind:
                shellcmd = f"{def_kind}: {def_ref}"
            jobs.append({
                "rule": str(rec.rule),
                "wildcards": wildcards,
                "shellcmd": shellcmd,
                "params": (meta.params if meta else None) or [],
                "inputs": [str(p) for p in (meta.input if meta else None) or []],
                "outputs": [str(f) for f in rec.output],
                "starttime": _iso(rec.starttime),
                "endtime": _iso(rec.endtime),
                "container_img_url": getattr(rec, "container_img_url", None),
                "conda_env": getattr(rec, "conda_env", None),
            })

        rules = {}
        for rule_name, rule_rec in self.rules.items():
            def_kind, def_ref = definitions.get(str(rule_name), (None, None))
            rules[str(rule_name)] = {
                "source": getattr(rule_rec, "source", None),
                "language": getattr(rule_rec, "language", None),
                "container_img_url": getattr(rule_rec, "container_img_url", None),
                "conda_env": getattr(rule_rec, "conda_env", None),
                "definition_kind": def_kind,
                "definition_ref": def_ref,
            }

        configfile_paths = []
        for cf in self.configfiles:
            configfile_paths.append(str(getattr(cf, "path", cf)))

        files = {}

        def register(path, parent=None):
            if path in files:
                return
            abs_p = os.path.abspath(path)
            info = {"size": None, "parent": parent, "is_dir": os.path.isdir(abs_p)}
            if os.path.isfile(abs_p):
                info["size"] = os.path.getsize(abs_p)
            try:
                inside = os.path.commonpath([abs_p, str(crate_dir)]) == str(crate_dir)
            except ValueError:
                inside = False
            # a relative contentUrl is a promise the file is at that path
            # inside the crate; a file already deleted (temp() intermediates)
            # gets localPath — "was here when this ran" — instead
            if inside and os.path.exists(abs_p):
                info["locator"] = "contentUrl"
                info["locator_value"] = os.path.relpath(abs_p, crate_dir)
            else:
                info["locator"] = "localPath"
                info["locator_value"] = path
            files[path] = info

        for job in jobs:
            for p in job["inputs"] + job["outputs"]:
                register(p)
        for p in configfile_paths:
            register(p)

        if getattr(self.settings, "expand_directories", False):
            max_files = int(getattr(self.settings, "expand_max_files", None) or 1000)
            for dir_path in [p for p, i in list(files.items()) if i["is_dir"]]:
                abs_dir = os.path.abspath(dir_path)
                children, total_size = [], 0
                for walk_root, walk_dirs, walk_files in os.walk(abs_dir):
                    walk_dirs.sort()
                    for name in sorted(walk_files):
                        if name == ".snakemake_timestamp":
                            continue
                        child = os.path.join(walk_root, name)
                        total_size += os.path.getsize(child)
                        children.append(child)
                if len(children) > max_files:
                    print(
                        f"WARNING: directory output '{dir_path}' holds "
                        f"{len(children)} files; registering the first "
                        f"{max_files} (--report-fairscape-expand-max-files)."
                    )
                    children = children[:max_files]
                for child in children:
                    register(os.path.relpath(child, os.getcwd()), parent=dir_path)
                files[dir_path]["size"] = total_size

        # the Snakefile as referenced from the crate directory
        try:
            snakefile_ref = os.path.relpath(snakefile_abs, crate_dir)
            if snakefile_ref.startswith(".."):
                snakefile_ref = str(snakefile_abs)
        except ValueError:
            snakefile_ref = str(snakefile_abs)

        starttimes = [j["starttime"] for j in jobs if j["starttime"]]
        endtimes = [j["endtime"] for j in jobs if j["endtime"]]
        run_info = {
            "name": run_name,
            "snakefile": snakefile_ref,
            "snakefile_key": os.path.normpath(str(snakefile_abs)),
            "engine_version": snakemake.__version__,
            "starttime": min(starttimes) if starttimes else None,
            "endtime": max(endtimes) if endtimes else None,
        }

        schemas = {}
        if getattr(self.settings, "schemas", False):
            schemas = self._infer_schemas(files, settings["naan"])

        # the interchange document: everything the conversion needs, as plain
        # data. The conversion itself lives in fairscape_conversion (the shared
        # converter engine), plugins/snakemake — not here.
        records = {
            "settings": settings,
            "run": run_info,
            "jobs": jobs,
            "rules": rules,
            "files": files,
            "configfiles": configfile_paths,
            "schemas": schemas,
        }
        dump_path = os.environ.get("SNAKEMAKE_FAIRSCAPE_DUMP_RECORDS")
        if dump_path:
            with open(dump_path, "w") as f:
                json.dump(records, f, indent=2, default=str)
            print(f"Run records dumped to {dump_path}")

        try:
            from fairscape_conversion.plugins.snakemake import convert
        except ImportError:
            print("ERROR: fairscape-conversion is not importable; cannot "
                  "build the crate (pip install fairscape-conversion).")
            return
        crate = convert("import", records)
        with open(crate_path, "w") as f:
            json.dump(crate, f, indent=4)
            f.write("\n")
        print(f"FAIRSCAPE RO-Crate written to {crate_path}")

        self._derive_artifacts(crate_path)

    def _infer_schemas(self, files, naan):
        """Infer an EVI Schema per data file with a supported extension.

        Delegates to fairscape_cli.models.schema.infer_schema (which dispatches
        on extension: csv/tsv/parquet/h5/hdf5/hea/dcm), overriding the CLI's
        random-uuid guid with a deterministic ARK hashed from the Dataset's ARK
        so crates stay reproducible across report re-runs.
        """
        try:
            from fairscape_cli.models.schema import infer_schema
            from fairscape_models.schema.registry import EXTENSION_MAP
        except ImportError:
            print("NOTE: fairscape-cli not installed; skipping schema "
                  "inference (pip install "
                  "'snakemake-report-plugin-fairscape[artifacts]')")
            return {}

        from fairscape_conversion.core.arks import mint_ark

        schemas = {}
        for path in files:
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext not in EXTENSION_MAP or not os.path.isfile(path):
                continue
            basename = os.path.basename(path)
            dataset_ark = mint_ark(naan, "dataset", basename, os.path.normpath(path))
            schema_ark = mint_ark(naan, "schema", basename, dataset_ark)
            try:
                model = infer_schema(
                    path,
                    name=f"Schema for {basename}",
                    description=f"Schema inferred from the {ext} file '{path}' "
                    "by snakemake-report-plugin-fairscape",
                    guid=schema_ark,
                )
                schemas[path] = model.model_dump(by_alias=True, exclude_none=True)
            except Exception as e:
                print(f"WARNING: schema inference failed for '{path}': {e}")
        return schemas

    def _derive_artifacts(self, crate_path):
        """Generate the derived artifacts by delegating to fairscape-cli.

        Everything downstream of the crate (inverse linking, EVI:inputs/
        outputs, evidence graph, LinkML/D4D export, datasheet + AI-Ready
        score) already exists in fairscape-cli as importable process_*
        functions; nothing is reimplemented here.
        """
        s = self.settings
        steps_on = [
            not getattr(s, "no_link_inverses", False),
            not getattr(s, "no_evidence_graph", False),
            not getattr(s, "no_linkml", False),
            not getattr(s, "no_datasheet", False),
            getattr(s, "preview", False),
            getattr(s, "croissant", False),
            getattr(s, "merkle", False),
        ]
        if not any(steps_on):
            return
        if crate_path.name != "ro-crate-metadata.json":
            print("WARNING: derived artifacts require the crate to be named "
                  "ro-crate-metadata.json; skipping them for "
                  f"'{crate_path.name}'")
            return
        try:
            from fairscape_cli.utils.build_utils import process_crate
        except ImportError:
            print("NOTE: fairscape-cli not installed; skipping derived "
                  "artifacts (pip install "
                  "'snakemake-report-plugin-fairscape[artifacts]')")
            return

        results = process_crate(
            crate_path.resolve().parent,
            link_inverses=not s.no_link_inverses,
            add_io=True,
            evidence_graph=not s.no_evidence_graph,
            linkml=not s.no_linkml,
            datasheet=not s.no_datasheet,
            preview=s.preview,
            croissant=s.croissant,
            merkle=s.merkle,
            force=True,
        )
        for err in results.get("errors", []):
            print(f"WARNING: {err}")
