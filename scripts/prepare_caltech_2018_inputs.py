#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path

import uproot


REDIRECTOR = "k8s-redir.ultralight.org:1094"
BASE = "/store/group/uerj/mabarros"
OUTDIR = Path("inputs/caltech")

SPS_SPECS = {
    "SPS-ccbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS_JPsiFilter_DstarFilter_TuneCP5_13TeV-bcvegpy2-pythia8-evtgen",
        "tag": "260829_133033",
    },
    "SPS-bbbar": {
        "base": BASE + "/SPS-JPsiDstar-D0ToKPI-3FS-BBBar_JPsiFilter_DstarFilter_TuneCP5_13TeV-HelacOnia-pythia8-evtgen",
        "tag": "260829_133611",
    },
}

DPS_CCBAR_BASES = {
    "9to30": BASE + "/DPS_D0ToKPi_JPsiPt-9To30_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen",
    "30to50": BASE + "/DPS_D0ToKPi_JPsiPt-30To50_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen",
    "50to100": BASE + "/DPS_D0ToKPi_JPsiPt-50To100_JPsiFilter_TuneCP5_13TeV-pythia8-evtgen",
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


def xrdfs_ls(base, recursive=True, allow_missing=False):
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
        if allow_missing:
            return []
        raise RuntimeError(
            "XRootD listing failed:\n"
            + " ".join(cmd)
            + "\n"
            + completed.stderr.strip()
        )

    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


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
    logical = set()
    for path in paths:
        if not path.endswith(".root"):
            continue
        if path.startswith("root://"):
            payload = path.split("://", 1)[1]
            slash = payload.find("/")
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
            raise RuntimeError(f"{label}: Events tree missing in {first}")
        tree = root_file["Events"]
        required = ("Dimu_pt", "Dstar_pt", "GenPart_pt")
        missing = [name for name in required if name not in tree.keys()]
        if missing:
            raise RuntimeError(f"{label}: required branches missing: {missing}")
        print(f"    entries={tree.num_entries}, branches={len(tree.keys())}")


def discover_sps(label, base, tag):
    listed = xrdfs_ls(base, recursive=True)
    files = unique_root_urls(
        path for path in listed
        if f"/{tag}/" in path and "/failed/" not in path
    )
    return require_nonempty(label, files)


def discover_dps_ccbar(slice_name, base):
    listed = xrdfs_ls(base, recursive=True)
    roots = unique_root_urls(listed)

    # The official DPS-ccbar NanoAODPlus inputs are named by the UL RECO
    # campaign. Require UL18 explicitly so files from another year can never
    # enter just because a numeric ROOT suffix happens to contain 2018.
    selected = [
        path for path in roots
        if "RunIISummer20UL18RECO" in path
        and "/failed/" not in path
    ]

    if not selected:
        # Some productions omit the RECO token but retain UL18 in the path.
        selected = [
            path for path in roots
            if "RunIISummer20UL18" in path
            and "/failed/" not in path
        ]

    return require_nonempty(f"DPS-ccbar {slice_name}", selected)


def find_bbbar_search_roots():
    top = xrdfs_ls(BASE, recursive=False)
    candidates = []

    for entry in top:
        name = entry.rstrip("/").split("/")[-1].lower()
        if "2018" not in name:
            continue
        if "dps" in name or "ccbarxbbbar" in name:
            candidates.append(entry)

    guessed = [
        BASE + "/CRAB_PrivateMC_RunII_UL_2018_ccbarxbbbar",
        BASE + "/CRAB_PrivateMC_RunII_UL_2018_DPS_bbbar",
        BASE + "/CRAB_PrivateMC_RunII_UL_2018_DPS_bbbar_xsec",
    ]

    for path in guessed:
        if path not in candidates and xrdfs_ls(path, recursive=False, allow_missing=True):
            candidates.append(path)

    return sorted(set(candidates))


def bbbar_match(path, slice_name):
    lower = path.lower()
    slice_token = slice_name.lower()

    if "dps" not in lower or "bbbar" not in lower or slice_token not in lower:
        return False

    # Strong year identification. This deliberately rejects the old 2017
    # production whose individual file names may end in *_2018.root.
    year_tokens = (
        "dps_bbbar_2018_13tev",
        "runii_ul_2018",
        "runiiul18",
        "summer20ul18",
    )
    if not any(token in lower for token in year_tokens):
        return False

    final_stage_tokens = (
        "nanoaodplus",
        "ul18reco",
    )
    return any(token in lower for token in final_stage_tokens)


def discover_dps_bbbar():
    search_roots = find_bbbar_search_roots()
    all_paths = []

    if search_roots:
        print("DPS-bbbar 2018 candidate top-level collections:")
        for root in search_roots:
            print(" ", root)
            all_paths.extend(xrdfs_ls(root, recursive=True))
    else:
        print(
            "No dedicated 2018 DPS-bbbar top-level collection was found; "
            "falling back to one recursive catalog scan under " + BASE
        )
        all_paths = xrdfs_ls(BASE, recursive=True)

    roots = unique_root_urls(all_paths)
    result = {}

    for slice_name in ("9to30", "30to50", "50to100"):
        selected = [path for path in roots if bbbar_match(path, slice_name)]
        result[slice_name] = require_nonempty(
            f"DPS-bbbar {slice_name}",
            selected,
        )

    return result


def write_filelist(path, label, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = [
        f"# {label}",
        f"# redirector={REDIRECTOR}",
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


def all_existing():
    return all(path.is_file() and read_filelist(path) for path in OUTPUTS.values())


def main():
    parser = argparse.ArgumentParser(
        description="Discover and freeze the complete 2018 Caltech efficiency inputs."
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse already frozen non-empty filelists instead of querying Caltech again.",
    )
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)

    if args.reuse_existing and all_existing():
        print("Reusing frozen 2018 Caltech input filelists:")
        for label, path in OUTPUTS.items():
            files = read_filelist(path)
            print(f"  {label:22s} {len(files):5d} ROOT files  {path}")
            validate_first(label, files)
        return

    resolved = {}

    for slice_name, base in DPS_CCBAR_BASES.items():
        label = f"DPS-ccbar-{slice_name}"
        print(f"Discovering {label} from {base}")
        resolved[label] = discover_dps_ccbar(slice_name, base)

    bbbar = discover_dps_bbbar()
    for slice_name, files in bbbar.items():
        resolved[f"DPS-bbbar-{slice_name}"] = files

    for label, spec in SPS_SPECS.items():
        print(f"Discovering {label} tag {spec['tag']} from {spec['base']}")
        resolved[label] = discover_sps(label, spec["base"], spec["tag"])

    print("\nResolved 2018 inputs:")
    for label in OUTPUTS:
        files = resolved[label]
        path = OUTPUTS[label]
        write_filelist(path, label, files)
        print(f"  {label:22s} {len(files):5d} unique ROOT files  -> {path}")
        validate_first(label, files)

    print("\nAll 2018 filelists were resolved, de-duplicated by logical file name, validated, and frozen.")


if __name__ == "__main__":
    main()
