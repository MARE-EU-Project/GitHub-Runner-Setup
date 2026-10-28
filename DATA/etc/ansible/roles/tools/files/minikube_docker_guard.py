#!/usr/bin/python3
"""Refuse shared-daemon collisions; never mutate Docker resources."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


def docker(*args):
    result = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', *args],
                            capture_output=True, text=True, check=True, timeout=60)
    return result.stdout


def resources(profile):
    found = {}
    node_name = re.compile(re.escape(profile) + r'-m[0-9]+')
    # Inspect stopped containers too. Match node suffixes as well as the profile.
    ids = docker('container', 'ls', '--all', '--quiet', '--no-trunc').split()
    for container_id in ids:
        data = json.loads(docker('container', 'inspect', container_id))[0]
        name = data['Name'].lstrip('/')
        labels = data['Config'].get('Labels') or {}
        if (name == profile or node_name.fullmatch(name) or
                labels.get('name.minikube.sigs.k8s.io') == profile):
            found['container:' + name] = data['Id']
    for kind in ('network', 'volume'):
        names = docker(kind, 'ls', '--format', '{{.Name}}').splitlines()
        for name in names:
            if name == profile or node_name.fullmatch(name):
                data = json.loads(docker(kind, 'inspect', name))[0]
                found[kind + ':' + name] = (data['Id'] if kind == 'network'
                                          else data['CreatedAt'])
    return found


def verify(current, previous):
    if any(previous.get(key) != value for key, value in current.items()):
        raise ValueError('Unowned or replaced Docker resources conflict with the requested Minikube profile.')


def read_record(path, identity):
    if not path.exists() and not path.is_symlink():
        return {}
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('Untrusted Minikube Docker resource record.')
    record = json.loads(path.read_text())
    if record['identity'] != identity or not isinstance(record['resources'], dict):
        raise ValueError('Minikube Docker resource identity mismatch.')
    return record['resources']


def main():
    mode, profile, user, runner, filename = sys.argv[1:]
    if mode not in ('check', 'record') or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', profile):
        raise ValueError('Invalid Docker guard arguments.')
    path = Path(filename)
    identity = {'profile': profile, 'user': user, 'runner': runner}
    previous = read_record(path, identity)
    current = resources(profile)
    if mode == 'check':
        verify(current, previous)
        return
    # Only called after the pre-start check and successful Minikube health checks.
    # New IDs may be created by this invocation's authorized startup.
    if 'container:' + profile not in current:
        raise ValueError('Expected Minikube container is missing.')
    fd, temporary = tempfile.mkstemp(prefix='.docker-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump({'identity': identity, 'resources': current}, output, sort_keys=True)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        sys.exit('Minikube Docker ownership verification failed. Preserve existing resources; inspect ownership privately or choose a fresh profile.')
