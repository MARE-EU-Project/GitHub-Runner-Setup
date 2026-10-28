"""Split directory ancestors at the boundary of an instance's private trees."""
from pathlib import PurePosixPath


def runner_directory_plan(instance, home_root):
    home = PurePosixPath(home_root) / instance['user']
    install = PurePosixPath(instance['install_dir'])
    work = PurePosixPath(instance['work_dir'])
    shared, private = set(), set()
    for target in (home, install, work):
        for parent in target.parents:
            if parent == PurePosixPath('/'):
                continue
            if parent == home or home in parent.parents or parent == install or install in parent.parents:
                private.add(str(parent))
            else:
                shared.add(str(parent))
    return {key: sorted(paths, key=lambda p: (len(PurePosixPath(p).parts), p))
            for key, paths in [('shared', shared), ('private', private)]}


class FilterModule:
    def filters(self):
        return {'runner_directory_plan': runner_directory_plan}
