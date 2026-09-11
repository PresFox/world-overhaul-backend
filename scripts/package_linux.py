"""Package only verified installer inputs from a draft release; never publish it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

MAKESELF_COMMIT = '3815292f7359a4ccab8e27bdbe8a844947c51e4c'
START_SCRIPT = '''#!/usr/bin/env bash
set -eu
bundle_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd -- "${USER_PWD:-$PWD}"
exec bash "$bundle_dir/install-linux.sh" "$@"
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_inputs(values):
    require(re.fullmatch(r'[a-f0-9]{32}', values['request_id']), 'Invalid packaging request ID')
    match = re.fullmatch(r'WorldOverhaul-(\d+\.\d+\.\d+)-win-x64\.msi', values['installer_name'])
    require(match, 'Invalid MSI filename')
    version = match[1]
    require(values['release_tag'] == 'launcher-v' + version or
            re.fullmatch(r'linux-package-test-[a-f0-9]{32}', values['release_tag']), 'Release tag does not match MSI')
    require(re.fullmatch(r'release-[0-9TZa-f-]+', values['release_marker']), 'Invalid release ownership marker')
    for key in ('msi_sha256', 'helper_sha256'):
        require(re.fullmatch(r'[a-f0-9]{64}', values[key]), 'Invalid ' + key)
    return 'WorldOverhaul-' + version + '-linux.run'


def validate_release(release, values):
    require(release['isDraft'], 'Only draft releases may receive Linux packaging assets')
    require('<!-- ' + values['release_marker'] + ' -->' in release['body'], 'Draft release belongs to another job')


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, text=True, capture_output=True, **kwargs).stdout


def manifest_for(values, bundle, msi, helper, environment):
    return {
        'schemaVersion': 1, 'requestId': values['request_id'], 'releaseTag': values['release_tag'],
        'workflowRunId': int(environment['GITHUB_RUN_ID']),
        'workflowRunAttempt': int(environment['GITHUB_RUN_ATTEMPT']),
        'workflowCommit': environment['GITHUB_SHA'], 'makeselfCommit': MAKESELF_COMMIT,
        'msi': {'name': msi.name, 'sha256': sha256(msi), 'size': msi.stat().st_size},
        'helper': {'name': helper.name, 'sha256': sha256(helper), 'size': helper.stat().st_size},
        'bundle': {'name': bundle.name, 'sha256': sha256(bundle), 'size': bundle.stat().st_size},
    }


def package(values, makeself):
    bundle_name = validate_inputs(values)
    repo = os.environ['GITHUB_REPOSITORY']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo), 'Invalid repository')
    def release():
        return json.loads(run('gh', 'release', 'view', values['release_tag'], '--repo', repo, '--json', 'body,isDraft'))
    validate_release(release(), values)
    # MSI is already compressed. A plain tar avoids another compression dependency.
    with tempfile.TemporaryDirectory(prefix='worldoverhaul-package-') as temporary:
        root = Path(temporary); payload = root / 'payload'; payload.mkdir()
        for name in (values['installer_name'], 'install-linux.sh'):
            run('gh', 'release', 'download', values['release_tag'], '--repo', repo, '--pattern', name, '--dir', payload)
        msi = payload / values['installer_name']; helper = payload / 'install-linux.sh'
        require(sha256(msi) == values['msi_sha256'], 'Downloaded MSI checksum mismatch')
        require(sha256(helper) == values['helper_sha256'], 'Downloaded helper checksum mismatch')
        text = helper.read_text(encoding='utf-8')
        require(values['installer_name'] in text and values['msi_sha256'] in text, 'Helper is not bound to this MSI')
        require('\r' not in helper.read_bytes().decode('utf-8') and not text.startswith('\ufeff'), 'Helper must use LF and no BOM')
        # Makeself changes cwd to extraction. Restore the user's original cwd
        # for relative --game/--msi arguments, retaining the absolute helper path.
        (payload / 'start.sh').write_text(START_SCRIPT, encoding='utf-8', newline='\n')
        bundle = root / bundle_name
        # Tests/extraction do not receive the token used to access release assets.
        clean_env = {key: value for key, value in os.environ.items()
                     if key not in ('GH_TOKEN', 'GITHUB_TOKEN') and not key.startswith('ACTIONS_')}
        print(run('bash', makeself, '--nocomp', '--sha256', '--nomd5', '--nocrc', '--nox11', '--nowait',
                  '--tar-format', 'ustar', payload, bundle, 'WorldOverhaul Linux setup', 'bash', './start.sh', env=clean_env))
        print(run('bash', bundle, '--check', env=clean_env))
        damaged = root / 'damaged.run'; shutil.copyfile(bundle, damaged)
        with damaged.open('r+b') as stream:
            stream.seek(-1, 2); byte = stream.read(1); stream.seek(-1, 2); stream.write(bytes([byte[0] ^ 1]))
        try:
            run('bash', damaged, '--check', env=clean_env)
        except subprocess.CalledProcessError:
            pass
        else:
            raise ValueError('Corrupted bundle unexpectedly passed its integrity check')
        extracted = root / 'extracted'
        run('bash', bundle, '--noexec', '--target', extracted, env=clean_env)
        require(sorted(p.name for p in extracted.iterdir()) == sorted((msi.name, helper.name, 'start.sh')), 'Unexpected bundle contents')
        require((extracted / 'start.sh').read_text(encoding='utf-8') == START_SCRIPT, 'Extracted startup script differs')
        for source in (msi, helper):
            require(sha256(extracted / source.name) == sha256(source), 'Extracted bytes differ: ' + source.name)
        # Exercise the real entry point/argument forwarding without setup, Steam or Wine.
        print(run('bash', bundle, '--', '--help', env=clean_env))
        receipt = root / (bundle_name + '.manifest.json')
        receipt.write_text(json.dumps(manifest_for(values, bundle, msi, helper, os.environ), indent=2) + '\n', encoding='utf-8')
        validate_release(release(), values)  # Refuse a release published while the job ran.
        run('gh', 'release', 'upload', values['release_tag'], bundle, receipt, '--repo', repo, '--clobber')
        print('Verified Linux bundle attached to draft: ' + bundle_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--makeself', type=Path, required=True)
    args = parser.parse_args()
    values = {key: os.environ['PACKAGE_' + key.upper()] for key in
              ('release_tag', 'installer_name', 'msi_sha256', 'helper_sha256', 'request_id', 'release_marker')}
    try:
        package(values, args.makeself.resolve())
    except subprocess.CalledProcessError as error:
        print(error.stdout or '')
        print(error.stderr or '')
        raise SystemExit('Linux packaging command failed (exit {}).'.format(error.returncode))
