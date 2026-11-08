#!/usr/bin/env python3
"""Pin each single-host OpenMPI rank to one selected CPU before exec."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpus', required=True, help='Ordered CPU IDs within 0..31')
    parser.add_argument('--root-extra-cpus', default='', help='Additional disjoint CPUs for rank zero solver threads')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cpus = [int(value) for value in args.cpus.split(',')]
    if not cpus or len(set(cpus)) != len(cpus) or not set(cpus) <= set(range(32)):
        parser.error('unique CPU IDs within 0..31 required')
    extra = [int(value) for value in args.root_extra_cpus.split(',') if value]
    if len(set(extra)) != len(extra) or set(extra) & set(cpus) or not set(extra) <= set(range(32)):
        parser.error('root extra CPUs must be unique, disjoint, and within 0..31')
    try:
        rank = int(os.environ['OMPI_COMM_WORLD_LOCAL_RANK'])
        size = int(os.environ['OMPI_COMM_WORLD_LOCAL_SIZE'])
        global_rank = int(os.environ['OMPI_COMM_WORLD_RANK'])
        global_size = int(os.environ['OMPI_COMM_WORLD_SIZE'])
    except (KeyError, ValueError):
        parser.error('single-host OpenMPI rank environment required')
    if not 0 <= rank < size <= len(cpus) or rank != global_rank or size != global_size:
        parser.error('single-host rank inventory within the selected CPU list required')
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command or not Path(command[0]).is_file():
        parser.error('existing executable path required after --')
    os.sched_setaffinity(0, {cpus[rank], *extra} if rank == 0 else {cpus[rank]})
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
