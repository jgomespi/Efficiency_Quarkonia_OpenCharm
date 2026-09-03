#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path

import uproot


REDIRECTOR = "k8s-redir.ultralight.org:1094"
BASE = "/store/group/uerj/mabarros"
OUTDIR = Path("inputs/caltech")

# Exact 2018 Caltech production directories from Control_Monte_Carlo.xlsx.
# Using exact production timestamps is intentional: do not infer the year from
# ROOT filenames and do not recursively scan the whole /store/group area.
DPS_SPECS = {
    "DPS-ccbar-9to30": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-9To30_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-9To30_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/230516_020037",
        "control_count": 63,
        "strict_count": True,
    },
    "DPS-ccbar-30to50": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-30To50_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-30To50_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/230124_190421",
        "control_count": 18,
        "strict_count": True,
    },
    "DPS-ccbar-50to100": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/220823_052048",
        "control_count": 8,
        "strict_count": True,
    },
    # These are the bbbar DPS inputs used by the analysis. Their production
    # names are HardQCD and therefore do NOT contain either "DPS" or "bbbar".
    # This is why heuristic catalog matching failed previously.
    "DPS-bbbar-9to30": {
        "base": BASE + "/D0ToKPi_Jpsi9to30_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi9to30_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/241216_185612",
        "control_count": 8,
        "strict_count": True,
    },
    "DPS-bbbar-30to50": {
        "base": BASE + "/D0ToKPi_Jpsi30to50_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi30to50_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/250122_185754",
        "control_count": 2,
        "strict_count": True,
    },
    "DPS-bbbar-50to100": {
        "base": BASE + "/D0ToKPi_Jpsi50to100_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi50to100_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/250122_185738",
        "control_count": 1,
        "strict_count": True,
    },
}

SPS_SPECS = {
    "SPS-ccbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS_JPsiFilter_DstarFilter_TuneCP5_13TeV-bcvegpy2-pythia8-evtgen/SPS-JPsiDstar-D0ToKPI-3FS_JPsiFilter_DstarFilter_TuneCP5_13TeV-bcvegpy2-pythia8-evtgenRunIISummer20U/260829_133033",
        "control_count": 3,
        # The control-sheet count for SPS is kept as an audit note. The exact
        # recent Caltech production path plus NanoAODPlus branch validation is
        # the hard requirement because the production can be sharded.
        "strict_count": False,
    },
    "SPS-bbbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS-BBBar_JPsiFilter_DstarFilter_TuneCP5_13TeV-HelacOnia-pythia8-evtgen/SPS-JPsiDstar-D0ToKPI-3FS-BBBar_JPsiFilter_DstarFilter_TuneCP5_13TeV-HelacOnia-pythia8-evtgenRunIISu/260829_133611",
        "control_count": 2,
        "strict_count": False,
    },
}

OUTPUTS = {
    "DPS-ccbar-9to30": OUTDIR / "DPS-ccbar_2018_9to30.txt",
    "DPS-ccbar-30to50": OUTDIR / "DPS-ccbar_2018_30to50.txt",
    "DPS-ccbar-50to100": OUTDIR / "DPS-ccbar_2018_50to100.txt",
    "DPS-bbbar-9to30": OUTDIR / "DPS-bbbar_2018_9to30.txt",
    "DPS-bbbar-30to50": OUTDIR / "DPS-bbbar_2018_30to50.txt",
    "DPS-bbbar-50to100": OUTDIR / "DPS-bbbar_2018_50to100.txt",
    "SPS-ccbar": OUTDIR / "SPS-ccbar_2018.txt",
    "SPS-bbbar": OUTDIR / "SPS-bbbar_2018.txt",
}


def xrdfs_ls(base, recursive=True):
    cmd = ["xrdfs", REDIRECTOR, "ls"]
    if recursive:
        cmd.append("-R")
    cmd.append(base)

    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "XRootD listing failed:\n"
            + " ".join(cmd)
            + "\n"
            + completed.stderr.strip()
        )

    return [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def canonical_url(path):
    if path.startswith("root://"):
        payload = path.split("://", 1)[1]
        slash = payload.find("/")
        if slash < 0:
            raise ValueError(f"Malformed ROOT URL: {path}")
        path = payload[slash:]

    logical = "/" + path.lstrip("/")
    return f"root://{REDIRECTOR}//{logical.lstrip('/')}"


def unique_root_urls(paths):
    """Deduplicate physical replicas by logical /store path."""
    logical = set()

    for path in paths:
        if not path.endswith(".root"):
            continue

        if path.startswith("root://"):
            payload = path.split("://", 1)[1]
            slash = payload.find("/")
            if slash < 0:
                continue
            path = payload[slash:]

        logical.add("/" + path.lstrip("/"))

    return [canonical_url(path) for path in sorted(logical)]


def require_nonempty(label, files):
    if not files:
        raise RuntimeError(f"No 2018 ROOT files resolved for {label}")
    return files


def validate_first(label, files):
    first = files[0]
    print(f"  validating {label}: {first}")

    with uproot.open(first) as root_file:
        if "Events" not in root_file:
            raise RuntimeError(
                f"{label}: Events tree missing in {first}"
            )

        tree = root_file["Events"]
        required = ("Dimu_pt", "Dstar_pt", "GenPart_pt")
        missing = [
            name for name in required
            if name not in tree.keys()
        ]

        if missing:
            raise RuntimeError(
                f"{label}: required NanoAODPlus branches missing: {missing}. "
                "This Caltech directory is not the final efficiency input "
                "stage and must not be processed."
            )

        print(
            f"    entries={tree.num_entries}, "
            f"branches={len(tree.keys())}"
        )


def discover_exact(label, spec):
    base = spec["base"]
    print(f"Discovering {label} from exact production:")
    print(f"  {base}")

    listed = xrdfs_ls(base, recursive=True)
    files = require_nonempty(
        label,
        unique_root_urls(
            path for path in listed
            if "/failed/" not in path
        ),
    )

    expected = spec.get("control_count")
    strict_count = bool(spec.get("strict_count", False))

    if expected is not None and len(files) != expected:
        message = (
            f"{label}: resolved {len(files)} unique ROOT files; "
            f"Control_Monte_Carlo.xlsx records {expected}."
        )
        if strict_count:
            raise RuntimeError(
                message
                + " Refusing to start the efficiency job until this DPS "
                "input-contract mismatch is understood."
            )
        print("  WARNING: " + message)
    elif expected is not None:
        print(
            f"  count check: {len(files)} ROOT files "
            f"(matches Control_Monte_Carlo.xlsx)"
        )

    return files


def write_filelist(path, label, spec, files):
    path.parent.mkdir(parents=True, exist_ok=True)

    text = [
        f"# {label}",
        f"# redirector={REDIRECTOR}",
        f"# production={spec['base']}",
        f"# n_files={len(files)}",
    ]

    if spec.get("control_count") is not None:
        text.append(
            f"# control_monte_carlo_count={spec['control_count']}"
        )

    text.extend(files)
    path.write_text("\n".join(text) + "\n")


def read_filelist(path):
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
    ]


def all_existing():
    return all(
        path.is_file() and read_filelist(path)
        for path in OUTPUTS.values()
    )


def combined_specs():
    result = {}
    result.update(DPS_SPECS)
    result.update(SPS_SPECS)
    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve and freeze the exact 2018 Caltech efficiency inputs "
            "listed in Control_Monte_Carlo.xlsx."
        )
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help=(
            "Reuse already frozen non-empty filelists instead of querying "
            "Caltech again."
        ),
    )
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    specs = combined_specs()

    if args.reuse_existing and all_existing():
        print("Reusing frozen 2018 Caltech input filelists:")

        for label, path in OUTPUTS.items():
            files = read_filelist(path)
            print(
                f"  {label:22s} {len(files):5d} ROOT files  {path}"
            )
            validate_first(label, files)

        return

    resolved = {}

    # Preflight every source before writing any frozen list or starting Coffea.
    for label in OUTPUTS:
        files = discover_exact(label, specs[label])
        validate_first(label, files)
        resolved[label] = files

    print("\nResolved 2018 inputs:")

    for label, path in OUTPUTS.items():
        files = resolved[label]
        spec = specs[label]

        write_filelist(path, label, spec, files)

        print(
            f"  {label:22s} {len(files):5d} unique ROOT files  -> {path}"
        )

    print(
        "\nAll 2018 filelists were resolved from exact Caltech production "
        "paths, de-duplicated by logical file name, validated, and frozen."
    )


if __name__ == "__main__":
    main()
