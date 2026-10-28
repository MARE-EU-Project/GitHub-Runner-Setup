"""Read-only policy tests; Docker responses are fixtures, never a live daemon."""
import importlib.util
from pathlib import Path
import tempfile
import copy
import io
import os
import pwd
import subprocess
import tarfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paths = load('roles/runner/filter_plugins/runner_paths.py')
guard = load('roles/tools/files/minikube_docker_guard.py')


class DirectoryTests(unittest.TestCase):
    def plan(self, install, work):
        return paths.runner_directory_plan({'user': 'gha-build', 'install_dir': install,
                                            'work_dir': work}, '/home')

    def test_home_install_and_deep_work_parents_are_private(self):
        plan = self.plan('/home/gha-build/actions-runner',
                         '/home/gha-build/actions-runner/build/jobs/_work')
        self.assertEqual(plan['shared'], ['/home'])
        self.assertEqual(plan['private'], ['/home/gha-build', '/home/gha-build/actions-runner',
                                          '/home/gha-build/actions-runner/build',
                                          '/home/gha-build/actions-runner/build/jobs'])

    def test_direct_child_work_does_not_classify_install_as_shared(self):
        plan = self.plan('/opt/actions-runner/build', '/opt/actions-runner/build/_work')
        self.assertNotIn('/opt/actions-runner/build', plan['shared'])
        self.assertIn('/opt/actions-runner/build', plan['private'])

    def test_shared_ancestors_are_complete_and_parent_first(self):
        plan = self.plan('/opt/actions-runner/team/build', '/var/lib/actions-runner/build')
        self.assertEqual(plan['shared'], ['/home', '/opt', '/var', '/opt/actions-runner',
                                         '/var/lib', '/opt/actions-runner/team',
                                         '/var/lib/actions-runner'])

    def test_sibling_prefix_is_not_a_private_tree(self):
        plan = self.plan('/opt/build', '/opt/build-other/jobs/_work')
        self.assertIn('/opt/build-other', plan['shared'])
        self.assertIn('/opt/build-other/jobs', plan['shared'])

    def test_publish_precedes_private_work_parent_creation(self):
        tasks = yaml.safe_load((ROOT / 'roles/runner/tasks/instance.yml').read_text())
        tasks = next(task['block'] for task in tasks if 'block' in task)
        names = [task['name'] for task in tasks]
        self.assertLess(names.index('Publish the complete fresh installation atomically'),
                        names.index('Create private nested parents only after publishing the installation'))
        self.assertLess(names.index('Create only missing root-owned shared runner ancestors'),
                        names.index('Create nonroot dedicated service account and optional tool groups'))


class AnsibleTests(unittest.TestCase):
    def execute(self, directory, tasks, variables, success=True):
        playbook = Path(directory) / 'test.yml'
        playbook.write_text(yaml.safe_dump([{'hosts': 'localhost', 'gather_facts': False,
                                             'vars': variables, 'tasks': tasks}]))
        environment = dict(os.environ, ANSIBLE_LOCAL_TEMP=directory + '/local',
                           ANSIBLE_REMOTE_TEMP=directory + '/remote',
                           ANSIBLE_FILTER_PLUGINS=str(ROOT / 'roles/runner/filter_plugins'),
                           ANSIBLE_NOCOLOR='1')
        result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local',
                                 str(playbook)], capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_duplicate_effective_profiles_fail_before_any_inspection(self):
        source = yaml.safe_load((ROOT / 'roles/tools/tasks/minikube.yml').read_text())
        tasks = source[1:4]
        for explicit, success in [(True, False), (False, True)]:
            instances = [{'name': name, **({'minikube_profile': 'shared'} if explicit else {})}
                         for name in ('first', 'second')]
            with tempfile.TemporaryDirectory() as directory:
                self.execute(directory, tasks, {'runner_instances': instances,
                                               'minikube_profile': 'minikube'}, success)

    def test_real_tasks_publish_home_install_before_nested_work_on_first_and_repeat_runs(self):
        source = yaml.safe_load((ROOT / 'roles/runner/tasks/instance.yml').read_text())
        source = next(task['block'] for task in source if 'block' in task)
        selected = ['Create private runner home directory',
                    'Create a private installation staging directory',
                    'Extract a fresh release into a private staging directory',
                    'Publish the complete fresh installation atomically',
                    'Restore private install permissions after archive extraction',
                    'Create private nested parents only after publishing the installation',
                    'Create private work directory']
        for suffix in ('_work', 'build/jobs/_work'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                user = pwd.getpwuid(os.getuid()).pw_name
                home = directory + '/homes/' + user
                instance = {'user': user, 'install_dir': home + '/actions-runner',
                            'work_dir': home + '/actions-runner/' + suffix}
                archive = Path(directory) / 'runner.tar'
                with tarfile.open(archive, 'w') as output:
                    content = b'complete installation'
                    entry = tarfile.TarInfo('sentinel')
                    entry.size = len(content)
                    output.addfile(entry, io.BytesIO(content))
                tasks = [copy.deepcopy(task) for task in source if task['name'] in selected]
                for task in tasks:
                    task.pop('become', None)
                    task.pop('become_user', None)
                tasks.insert(0, {'ansible.builtin.set_fact': {
                    'runner_directory_plan': '{{ runner_instance | runner_directory_plan(runner_home_root) }}'}})
                variables = {'runner_instance': instance, 'runner_home_root': directory + '/homes',
                             'runner_staging_dir': instance['install_dir'] + '.staging',
                             'runner_cache_dir': directory, 'runner_archive_name': 'runner.tar',
                             'runner_paths': {'results': [{'stat': {'exists': False}}]}}
                self.execute(directory, tasks, variables)
                self.assertTrue((Path(instance['install_dir']) / 'sentinel').is_file())
                self.assertTrue(Path(instance['work_dir']).is_dir())
                variables['runner_paths']['results'][0]['stat']['exists'] = True
                self.execute(directory, tasks, variables)
                self.assertEqual(Path(instance['work_dir']).stat().st_mode & 0o777, 0o700)


class DockerTests(unittest.TestCase):
    def test_foreign_running_or_stopped_container_rejected(self):
        for key in ('container:minikube', 'container:minikube-m02',
                    'network:minikube', 'volume:minikube'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                guard.verify({key: 'foreign'}, {})

    def test_replaced_id_rejected_even_with_same_profile_name(self):
        with self.assertRaises(ValueError):
            guard.verify({'container:minikube': 'new'}, {'container:minikube': 'owned'})

    def test_exact_owned_resources_and_missing_resources_are_safe(self):
        guard.verify({'container:minikube': 'owned'}, {'container:minikube': 'owned'})
        guard.verify({}, {'container:minikube': 'owned'})
        guard.verify({}, {})

    def test_daemon_scan_includes_stopped_nodes_and_profile_labels(self):
        calls = []
        def docker(*args):
            import json
            calls.append(args)
            if args[:2] == ('container', 'ls'):
                return 'foreign\nunrelated\n'
            if args[:2] == ('container', 'inspect'):
                name = 'renamed' if args[2] == 'foreign' else 'other'
                return json.dumps([{'Id': args[2], 'Name': '/' + name, 'Config': {'Labels':
                    {'name.minikube.sigs.k8s.io': 'minikube' if name == 'renamed' else 'other'}}}])
            return ''
        with patch.object(guard, 'docker', docker):
            current = guard.resources('minikube')
        self.assertEqual(current, {'container:renamed': 'foreign'})
        self.assertIn(('container', 'ls', '--all', '--quiet', '--no-trunc'), calls)
        with self.assertRaises(ValueError):
            guard.verify(current, {})

    def test_named_nodes_networks_and_volumes_are_scanned_without_prefix_confusion(self):
        import json
        def docker(*args):
            if args[:2] == ('container', 'ls'):
                return 'node\nmonitor\n'
            if args[:2] == ('container', 'inspect'):
                name = 'minikube-m02' if args[2] == 'node' else 'minikube-monitor'
                return json.dumps([{'Id': args[2], 'Name': '/' + name, 'Config': {'Labels': {}}}])
            if args[1] == 'ls':
                return 'minikube\nminikube-monitor\n'
            return json.dumps([{'Id': 'network-id', 'CreatedAt': 'volume-created'}])
        with patch.object(guard, 'docker', docker):
            self.assertEqual(guard.resources('minikube'), {
                'container:minikube-m02': 'node', 'network:minikube': 'network-id',
                'volume:minikube': 'volume-created'})

    def test_symlinked_record_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record'
            path.symlink_to(Path(directory) / 'missing')
            with self.assertRaises(ValueError):
                guard.read_record(path, {})


if __name__ == '__main__':
    unittest.main()
