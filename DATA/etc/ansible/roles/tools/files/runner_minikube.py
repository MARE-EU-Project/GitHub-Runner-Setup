#!/usr/bin/python3
"""Resolve the job's default-profile alias without targeting another cluster."""

import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys


def profile_arguments(arguments, profile):
    result = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            result.extend(arguments[index:])
            break
        if argument in ("--profile", "-p") and index + 1 < len(arguments):
            value = arguments[index + 1]
            result.extend([argument, profile if value == "minikube" else value])
            index += 2
            continue
        if argument == "--profile=minikube":
            argument = "--profile=" + profile
        elif argument == "-pminikube":
            argument = "-p" + profile
        elif argument == "-p=minikube":
            argument = "-p=" + profile
        result.append(argument)
        index += 1
    return result


def main():
    arguments = sys.argv[1:]
    profile = os.environ.get("MINIKUBE_PROFILE", "minikube")
    mapped = profile_arguments(arguments, profile)
    if mapped != arguments:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", profile):
            raise ValueError("Invalid runner Minikube profile.")
        user = pwd.getpwuid(os.getuid()).pw_name
        marker = Path("/var/lib/runner-tools/minikube") / user / (profile + ".json")
        metadata = marker.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) not in (0o600, 0o644):
            raise ValueError("Untrusted runner Minikube ownership record.")
        identity = json.loads(marker.read_text())
        if identity.get("user") != user or identity.get("profile") != profile:
            raise ValueError("Minikube profile belongs to another runner identity.")
    os.execv("/usr/local/bin/minikube", ["/usr/local/bin/minikube", *mapped])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError):
        raise SystemExit("Refusing an invalid or unowned runner Minikube profile alias.")
