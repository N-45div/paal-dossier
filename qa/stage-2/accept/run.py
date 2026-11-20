"""Run the acceptance suite without host pytest/httpx installations."""
import argparse
import pathlib
import re
import subprocess
import sys
import tempfile
import uuid


def call(command, timeout=600, check=True):
    return subprocess.run([str(part) for part in command], timeout=timeout, check=check)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service-root', required=True, help='worktree containing stage-2')
    parser.add_argument('--name-prefix', default='prover', help='Docker name prefix for this seat')
    parser.add_argument('--port-start', type=int, default=18200)
    parser.add_argument('--port-end', type=int, default=18299)
    parser.add_argument('--corpus', help='mock corpus directory; defaults to the sample')
    parser.add_argument('--stage1-root', help='worktree containing the frozen stage-1')
    parser.add_argument('--test-path', help='test file or directory; defaults to the full suite')
    parser.add_argument('--inside-lock', action='store_true', help=argparse.SUPPRESS)
    options, pytest_args = parser.parse_known_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,39}', options.name_prefix):
        parser.error('invalid Docker name prefix')
    if not 1 <= options.port_start < options.port_end <= 65535:
        parser.error('port range must contain at least two valid TCP ports')
    if not options.inside_lock:
        command = ['flock', '/tmp/factory-heavy.lock', sys.executable, pathlib.Path(__file__).resolve(),
                   '--inside-lock', *sys.argv[1:]]
        return call(command, timeout=1800, check=False).returncode

    suite = pathlib.Path(__file__).resolve().parent
    suffix = uuid.uuid4().hex[:12]
    image = f'{options.name_prefix}-accept-deps-{suffix}'
    container = f'{options.name_prefix}-accept-copy-{suffix}'
    with tempfile.TemporaryDirectory(prefix=f'{options.name_prefix}-accept-') as tmp:
        wheelhouse = pathlib.Path(tmp) / 'wheels'
        wheelhouse.mkdir()
        try:
            call(['docker', 'build', '-t', image, '-f', suite / 'runner.Dockerfile', suite], timeout=600)
            call(['docker', 'run', '--rm', '--name', container, '--network', 'none',
                  '-v', f'{wheelhouse}:/out', '--entrypoint', 'python', image, '-c',
                  "import shutil; shutil.copytree('/wheels', '/out', dirs_exist_ok=True)"], timeout=60)
            env_dir = pathlib.Path(tmp) / 'venv'
            call([sys.executable, '-m', 'venv', env_dir], timeout=120)
            python = env_dir / 'bin/python'
            call([python, '-m', 'pip', 'install', '--no-index', '--no-cache-dir', '--find-links', wheelhouse,
                  '-r', suite / 'requirements.txt'], timeout=120)
            test_path = pathlib.Path(options.test_path).resolve() if options.test_path else suite
            command = [python, '-m', 'pytest', test_path, '--service-root', pathlib.Path(options.service_root).resolve(),
                       '--name-prefix', options.name_prefix, '--port-start', options.port_start,
                       '--port-end', options.port_end]
            if options.corpus:
                command += ['--corpus', pathlib.Path(options.corpus).resolve()]
            if options.stage1_root:
                command += ['--stage1-root', pathlib.Path(options.stage1_root).resolve()]
            command += pytest_args
            return call(command, timeout=900, check=False).returncode
        finally:
            call(['docker', 'rm', '-f', container], timeout=20, check=False)
            call(['docker', 'image', 'rm', '-f', image], timeout=20, check=False)


if __name__ == '__main__':
    sys.exit(main())
