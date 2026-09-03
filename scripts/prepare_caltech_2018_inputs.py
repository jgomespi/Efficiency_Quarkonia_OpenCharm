#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path

import uproot


REDIRECTOR = "k8s-redir.ultralight.org:1094"
BASE = "/store/group/uerj/mabarros"
OUTDIR = Path("inputs/caltech")
REQUIRED_BRANCHES = ("Dimu_pt", "Dstar_pt", "GenPart_pt")

# Exact 2018 Caltech CRAB productions.
#
# Mapse's get_files_xrootd.py defines which production timestamp and which
# terminal CRAB folders (0000, 0001, ...) belong to each input.  Those are the
# provenance contract.  The number of ROOT files is discovered at runtime and
# is deliberately NOT hard-coded: an old bookkeeping/file-count value is not
# a safe substitute for the actual contents of the configured CRAB folders.
DPS_SPECS = {
    "DPS-ccbar-9to30": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-9To30_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-9To30_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/230516_020037",
        "n_folders": 2,
    },
    "DPS-ccbar-30to50": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-30To50_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-30To50_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/230124_190421",
        "n_folders": 1,
    },
    "DPS-ccbar-50to100": {
        "base": BASE + "/DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen/DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/220823_052048",
        "n_folders": 1,
    },
    # These are the bbbar DPS inputs used by the analysis. Their production
    # names are HardQCD and therefore do not contain either "DPS" or "bbbar".
    "DPS-bbbar-9to30": {
        "base": BASE + "/D0ToKPi_Jpsi9to30_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi9to30_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/241216_185612",
        "n_folders": 1,
    },
    "DPS-bbbar-30to50": {
        "base": BASE + "/D0ToKPi_Jpsi30to50_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi30to50_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/250122_185754",
        "n_folders": 1,
    },
    "DPS-bbbar-50to100": {
        "base": BASE + "/D0ToKPi_Jpsi50to100_HardQCD_TuneCP5_13TeV-pythia8-evtgen/D0ToKPi_Jpsi50to100_HardQCD_TuneCP5_13TeV-pythia8-evtgenRunIISummer20UL18RECO/250122_185738",
        "n_folders": 1,
    },
}

# Recent SPS productions supplied by Mapse.  They use the same terminal CRAB
# folder convention.  Their exact production timestamps are fixed here; their
# file multiplicities are discovered from storage, not guessed in advance.
SPS_SPECS = {
    "SPS-ccbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS_JPsiFilter_DstarFilter_TuneCP5_13TeV-bcvegpy2-pythia8-evtgen/SPS-JPsiDstar-D0ToKPI-3FS_JPsiFilter_DstarFilter_TuneCP5_13TeV-bcvegpy2-pythia8-evtgenRunIISummer20U/260829_133033",
        "n_folders": 1,
    },
    "SPS-bbbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS-BBBar_JPsiFilter_DstarFilter_TuneCP5_13TeV-HelacOnia-pythia8-evtgen/SPS-JPsiDstar-D0ToKPI-3FS-BBBar_JPsiFilter_DstarFilter_TuneCP5_13TeV-HelacOnia-pythia8-evtgenRunIISu/260829_133611",
        "n_folders": 1,
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


def xrdfs_ls(path):
    """List one configured terminal XRootD directory, without recursion."""
    cmd = ["xrdfs", REDIRECTOR, "ls", path]
    completed = subprocess.run(cmd, text=True, capture_output=True)

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
    """Route a logical /store path through the stable Caltech redirector."""
    if path.startswith("root://"):
        payload = path.split("://", 1)[1]
        slash = payload.find("/")
        if slash < 0:
            raise ValueError(f"Malformed ROOT URL: {path}")
        path = payload[slash:]

    logical = "/" + path.lstrip("/")
    return f"root://{REDIRECTOR}//{logical.lstrip('/')}"


def unique_root_urls(paths):
    """Keep unique logical ROOT files and discard physical replica identity."""
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


def validate_root(label, path, position):
    print(f"  validating {label} [{position}]: {path}")

    with uproot.open(path) as root_file:
        if "Events" not in root_file:
            raise RuntimeError(
                f"{label}: Events tree missing in {path}. The selected "
                "Caltech ROOT is not a NanoAODPlus efficiency input."
            )

        tree = root_file["Events"]
        branches = set(tree.keys())
        missing = [name for name in REQUIRED_BRANCHES if name not in branches]

        if missing:
            raise RuntimeError(
                f"{label}: required NanoAODPlus branches missing in {path}: "
                f"{missing}. This file must not enter the efficiency job."
            )

        print(f"    entries={tree.num_entries}, branches={len(branches)}")


def validate_sample(label, files):
    """Schema-check first, middle and last files of a resolved sample."""
    if not files:
        raise RuntimeError(f"No 2018 ROOT files resolved for {label}")

    indices = sorted(set((0, len(files) // 2, len(files) - 1)))
    for index in indices:
        validate_root(label, files[index], f"{index + 1}/{len(files)}")


def discover_exact(label, spec):
    """Resolve every ROOT directly listed in the configured CRAB folders."""
    base = spec["base"]
    n_folders = int(spec["n_folders"])

    print(f"Discovering {label} from exact CRAB production:")
    print(f"  {base}")
    print(f"  terminal folders: {n_folders}")

    listed = []
    per_folder = []

    for index in range(n_folders):
        terminal = f"{base}/{index:04d}"
        roots = unique_root_urls(xrdfs_ls(terminal))

        if not roots:
            raise RuntimeError(
                f"{label}: no ROOT files found in expected terminal folder "
                f"{terminal}"
            )

        listed.extend(roots)
        per_folder.append((terminal, len(roots)))

    files = unique_root_urls(listed)
    if not files:
        raise RuntimeError(f"No 2018 ROOT files resolved for {label}")

    for terminal, count in per_folder:
        print(f"    {count:5d} ROOT files | {terminal}")

    print(f"  resolved total: {len(files)} unique ROOT files")
    validate_sample(label, files)
    return files


def write_filelist(path, label, spec, files):
    path.parent.mkdir(parents=True, exist_ok=True)

    text = [
        f"# {label}",
        f"# redirector={REDIRECTOR}",
        f"# production={spec['base']}",
        f"# terminal_folders={spec['n_folders']}",
        f"# n_files={len(files)}",
    ]
    text.extend(files)
    path.write_text("\n".join(text) + "\n")


def read_filelist(path):
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def read_filelist_metadata(path):
    metadata = {}
    for line in path.read_text().splitlines():
        if not line.startswith("# ") or "=" not in line:
            continue
        key, value = line[2:].split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def combined_specs():
    result = {}
    result.update(DPS_SPECS)
    result.update(SPS_SPECS)
    return result


def filelist_matches_spec(path, spec):
    """Check that a cached list was frozen from the current source contract."""
    if not path.is_file():
        return False

    files = read_filelist(path)
    if not files:
        return False

    metadata = read_filelist_metadata(path)
    return (
        metadata.get("production") == spec["base"]
        and metadata.get("terminal_folders") == str(spec["n_folders"])
        and metadata.get("n_files") == str(len(files))
    )


def all_existing(specs):
    return all(
        filelist_matches_spec(path, specs[label])
        for label, path in OUTPUTS.items()
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve and freeze the exact 2018 Caltech NanoAODPlus inputs "
            "from the CRAB production folders configured by Mapse."
        )
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse frozen filelists only when their source metadata matches.",
    )
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    specs = combined_specs()

    if args.reuse_existing and all_existing(specs):
        print("Reusing frozen 2018 Caltech input filelists:")
        for label, path in OUTPUTS.items():
            files = read_filelist(path)
            print(f"  {label:22s} {len(files):5d} ROOT files  {path}")
            validate_sample(label, files)
        return

    resolved = {}

    # Preflight all eight sources before writing any new frozen list or
    # starting the expensive Coffea processing.
    for label in OUTPUTS:
        resolved[label] = discover_exact(label, specs[label])

    print("\nResolved 2018 inputs:")
    for label, path in OUTPUTS.items():
        files = resolved[label]
        write_filelist(path, label, specs[label], files)
        print(
            f"  {label:22s} {len(files):5d} unique ROOT files  -> {path}"
        )

    print(
        "\nAll 2018 filelists were resolved from the configured CRAB "
        "terminal folders, schema-validated, and frozen."
    )


if __name__ == "__main__":
    main()
