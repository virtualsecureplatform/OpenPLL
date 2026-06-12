#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import os
import shlex
import shutil
import subprocess
from pathlib import Path


def default_xyce():
    return shutil.which("Xyce") or "Xyce"


def default_xyce_mpi_procs():
    text = os.environ.get("XYCE_MPI_PROCS", "1")
    try:
        return int(text)
    except ValueError:
        return 1


def add_xyce_arguments(parser, *, default=None):
    parser.add_argument("--xyce", default=default or default_xyce())
    parser.add_argument(
        "--xyce-mpi-procs",
        type=int,
        default=default_xyce_mpi_procs(),
        help=(
            "Run each Xyce deck under mpirun with this many MPI processes. "
            "Requires an MPI-enabled Xyce build; use --jobs for independent "
            "deck parallelism with a serial Xyce build."
        ),
    )
    parser.add_argument(
        "--xyce-mpi-launcher",
        default=os.environ.get("XYCE_MPI_LAUNCHER", "mpirun"),
        help="MPI launcher for --xyce-mpi-procs; must accept '-np N'.",
    )


def validate_xyce_arguments(args):
    if getattr(args, "xyce_mpi_procs", 1) < 1:
        raise ValueError("--xyce-mpi-procs must be positive")


def split_xyce_command(args):
    xyce_cmd = shlex.split(args.xyce)
    if not xyce_cmd:
        raise ValueError("--xyce command must not be empty")
    return xyce_cmd


def xyce_capabilities(xyce_cmd):
    try:
        proc = subprocess.run(
            xyce_cmd + ["-capabilities"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=15,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"cannot run Xyce command: {' '.join(xyce_cmd)}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"timed out probing Xyce capabilities: {' '.join(xyce_cmd)}"
        ) from exc
    return proc.stdout or ""


def xyce_supports_mpi(capabilities_text):
    lines = [
        line.strip().lower()
        for line in capabilities_text.splitlines()
        if line.strip()
    ]
    if lines and lines[0] == "serial":
        return False
    return any("mpi" in line or "parallel" in line for line in lines)


def xyce_run_command(args):
    xyce_cmd = split_xyce_command(args)
    mpi_procs = getattr(args, "xyce_mpi_procs", 1)
    if mpi_procs == 1:
        return xyce_cmd

    first = Path(xyce_cmd[0]).name
    if first in {"mpirun", "mpiexec", "srun"}:
        raise ValueError(
            "use either --xyce 'mpirun -np N Xyce' or --xyce-mpi-procs N, not both"
        )

    capabilities = xyce_capabilities(xyce_cmd)
    if not xyce_supports_mpi(capabilities):
        first_line = capabilities.strip().splitlines()[0] if capabilities.strip() else ""
        detail = f" ({first_line})" if first_line else ""
        raise ValueError(
            f"--xyce-mpi-procs={mpi_procs} requested, but "
            f"{' '.join(xyce_cmd)} -capabilities does not report MPI support{detail}. "
            "Install/select an MPI-enabled Xyce build, or use --jobs to run "
            "independent decks in parallel."
        )

    launcher = shlex.split(getattr(args, "xyce_mpi_launcher", "mpirun"))
    if not launcher:
        raise ValueError("--xyce-mpi-launcher must not be empty")
    return launcher + ["-np", str(mpi_procs)] + xyce_cmd


def xyce_simulator_command(args, netlist_path, output_base):
    return xyce_run_command(args) + [
        "-quiet",
        "-o",
        str(output_base),
        str(netlist_path),
    ]
