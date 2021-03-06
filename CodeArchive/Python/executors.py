import os.path
import random
import time

import libcxx.test.executor

from libcxx.android import adb
from lit.util import executeCommand  # pylint: disable=import-error


class AdbExecutor(libcxx.test.executor.RemoteExecutor):
    def __init__(self, device_dir, serial=None):
        # TODO(danalbert): Should factor out the shared pieces of SSHExecutor
        # so we don't have this ugly parent constructor...
        super(AdbExecutor, self).__init__()
        self.device_dir = device_dir
        self.serial = serial
        self.local_run = executeCommand

    def _remote_temp(self, is_dir):
        # Android didn't have mktemp until M :(
        # Just use a random number generator and hope for no collisions. Should
        # be very unlikely for a 64-bit number.
        test_dir_name = 'test.{}'.format(random.randrange(2 ** 64))
        return os.path.join(self.device_dir, test_dir_name)

    def _copy_in_file(self, src, dst):  # pylint: disable=no-self-use
        adb.push(src, dst)

    def _execute_command_remote(self, cmd, remote_work_dir='.', env=None):
        adb_cmd = ['adb', 'shell']
        if self.serial:
            adb_cmd.extend(['-s', self.serial])

        delimiter = 'x'
        probe_cmd = ' '.join(cmd) + '; echo {}$?'.format(delimiter)

        env_cmd = []
        if env is not None:
            env_cmd = ['%s=%s' % (k, v) for k, v in env.items()]

        remote_cmd = ' '.join(env_cmd + [probe_cmd])
        if remote_work_dir != '.':
            remote_cmd = 'cd {} && {}'.format(remote_work_dir, remote_cmd)

        adb_cmd.append(remote_cmd)

        # Tests will commonly fail with ETXTBSY. Possibly related to this bug:
        # https://code.google.com/p/android/issues/detail?id=65857. Work around
        # it by just waiting a second and then retrying.
        for _ in range(10):
            out, err, exit_code = self.local_run(adb_cmd)
            if 'Text file busy' in out or 'text busy' in out:
                time.sleep(1)
            else:
                out, delim, rc_str = out.rpartition(delimiter)
                if delim == '':
                    continue

                out = out.strip()
                try:
                    exit_code = int(rc_str)
                    break
                except ValueError:
                    continue
        return adb_cmd, out, err, exit_code
