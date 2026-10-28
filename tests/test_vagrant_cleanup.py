"""Exercise production cleanup tasks against a fixture virsh, never libvirt."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class VagrantCleanupTests(unittest.TestCase):
    def exercise(self, owned, success):
        source = yaml.safe_load((ROOT / 'roles/verification/tasks/functional_account.yml').read_text())
        cleanup = next(task['always'] for task in source if 'always' in task)
        names = ['Inspect domains after destroying the private Vagrant environment',
                 'Inspect networks after destroying the private Vagrant environment',
                 'Inspect volumes only in the approved storage pool',
                 "Remove only this test's uniquely aliased imported base images",
                 'Verify the approved pool contains no remaining test volumes',
                 'Preserve recovery metadata if runtime cleanup failed']
        tasks = [task for task in cleanup if task['name'] in names]
        unrelated = 'other_vagrant_box_image_4.3.12_box.img'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state.json'
            state.write_text(json.dumps({'volumes': [owned, unrelated], 'deleted': []}))
            executable = root / 'virsh'
            executable.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
state = Path(os.environ['VIRSH_TEST_STATE'])
data = json.loads(state.read_text())
args = sys.argv[1:]
command = args[2] if args[0] == '--connect' else args[0]
if command == 'vol-list':
    if '--name' in args:
        sys.exit(2)
    print(' Name                         Path')
    print('-----------------------------------------')
    for name in data['volumes']:
        print(' ' + name + '   /var/lib/libvirt/images/' + name)
elif command == 'vol-delete':
    name = args[-1]
    data['volumes'].remove(name)
    data['deleted'].append(name)
    state.write_text(json.dumps(data))
elif command == 'net-list':
    print('default')
elif command != 'list':
    sys.exit(3)
''')
            executable.chmod(0o755)
            variables = dict(functional_vagrant_attempted=True, functional_resource_name='acceptance',
                             functional_vagrant_box_alias='acceptance-box',
                             functional_vagrant_storage_pool='default', functional_vagrant_cleanup={'rc': 0},
                             functional_docker_created=False, functional_compose_attempted=False,
                             functional_helm_attempted=False, functional_namespace_created=False)
            play = [{'hosts': 'localhost', 'gather_facts': False, 'vars': variables,
                     'environment': {'PATH': directory + ':' + os.environ['PATH'],
                                     'VIRSH_TEST_STATE': str(state)}, 'tasks': tasks}]
            playbook = root / 'test.yml'
            playbook.write_text(yaml.safe_dump(play))
            environment = dict(os.environ, ANSIBLE_LOCAL_TEMP=directory + '/local',
                               ANSIBLE_REMOTE_TEMP=directory + '/remote', ANSIBLE_NOCOLOR='1')
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(playbook)],
                                    capture_output=True, text=True, env=environment, timeout=90)
            self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
            after = json.loads(state.read_text())
            self.assertIn(unrelated, after['volumes'])
            return after

    def test_supported_volume_listing_deletes_only_exact_test_alias(self):
        owned = 'acceptance-box_vagrant_box_image_4.3.12_box.img'
        after = self.exercise(owned, True)
        self.assertEqual(after['deleted'], [owned])

    def test_ambiguous_test_volume_name_is_preserved_and_cleanup_fails(self):
        owned = 'acceptance-box_vagrant_box_image_bad name.img'
        after = self.exercise(owned, False)
        self.assertIn(owned, after['volumes'])
        self.assertEqual(after['deleted'], [])


if __name__ == '__main__':
    unittest.main()
