#!/usr/bin/env python3
"""Exercise the publish workflow without downloading or publishing releases."""

import os
import gzip
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


def deb(changelog):
    """Build a minimal deb whose data archive contains a Debian changelog."""
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:xz') as archive:
        content = gzip.compress(changelog.encode())
        member = tarfile.TarInfo('./usr/share/doc/opentubex/changelog.gz')
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    output = b'!<arch>\n'
    for name, content in ((b'debian-binary', b'2.0\n'), (b'data.tar.xz', data.getvalue())):
        output += b'%-16s%-12s%-6s%-6s%-8s%-10d`\n' % (name, b'0', b'0', b'0', b'100644', len(content))
        output += content + (b'\n' if len(content) % 2 else b'')
    return output


def workflow_step(name):
    workflow = (ROOT / '.github/workflows/publish.yml').read_text()
    step = workflow.split(f'      - name: {name}\n', 1)[1]
    step = step.split('\n      - ', 1)[0]
    return textwrap.dedent(step.split('        run: |\n', 1)[1])


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for package in ('opentubex', 'opentubex-bin', 'opentubex-nightly-bin', 'opentubex-git'):
            shutil.copytree(ROOT / package, self.directory / package)
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, GITHUB_WORKSPACE=str(self.directory),
                        GITHUB_OUTPUT=str(self.directory / 'outputs'),
                        PATH=f'{self.bin}:{os.environ["PATH"]}')

    def stub(self, name, script):
        path = self.bin / name
        path.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + script)
        path.chmod(0o755)

    def run_step(self, name, **env):
        return subprocess.run(['bash', '-c', workflow_step(name)],
                              cwd=self.directory, env=self.env | env,
                              text=True, capture_output=True)

    def resolve(self, tag, event=''):
        result = self.run_step('Resolve release', INPUT_TAG=tag, EVENT_TYPE=event)
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(line.split('=', 1) for line in
                    (self.directory / 'outputs').read_text().splitlines())

    def metadata(self, release):
        files = self.directory / 'release-files'
        files.mkdir(exist_ok=True)
        for arch in ('amd64', 'arm64'):
            (files / f'opentubex_{release["asset_version"]}_{arch}.deb').write_bytes(deb(f'{arch} notes\n'))
        (files / 'source.tar.gz').write_text('source')
        self.stub('useradd', ':\n')
        self.stub('chown', ':\n')
        self.stub('runuser', 'shift 3\nexec "$@"\n')
        result = self.run_step('Update package metadata', PKGVER=release['pkgver'],
                               ASSET_VERSION=release['asset_version'],
                               PACKAGES=release['packages'])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stable_promotes_nightly_package(self):
        release = self.resolve('v0.36.0-beta', 'opentubex-release')
        self.assertEqual(release['packages'].split(),
                         ['opentubex-bin', 'opentubex', 'opentubex-nightly-bin', 'opentubex-git'])
        self.metadata(release)
        info = (self.directory / 'opentubex-nightly-bin/.SRCINFO').read_text()
        self.assertIn('epoch = 1', info)
        self.assertIn('pkgver = 0.36.0\n', info)
        for arch in ('amd64', 'arm64'):
            self.assertIn(f'/v0.36.0-beta/opentubex_0.36.0_beta_{arch}.deb', info)
        for package in ('opentubex', 'opentubex-bin'):
            self.assertNotIn('epoch = ', (self.directory / package / '.SRCINFO').read_text())

    def test_stable_packages_ship_the_release_changelog(self):
        release = self.resolve('v0.36.0-beta', 'opentubex-release')
        self.metadata(release)
        for package in ('opentubex', 'opentubex-bin'):
            self.assertEqual((self.directory / package / 'opentubex.changelog').read_text(), 'amd64 notes\n')
            self.assertIn('changelog = opentubex.changelog', (self.directory / package / '.SRCINFO').read_text())
        for package in ('opentubex-nightly-bin', 'opentubex-git'):
            self.assertFalse((self.directory / package / 'opentubex.changelog').exists())

    def test_nightly_only_updates_nightly_package(self):
        release = self.resolve('v0.36.1-nightly-2112', 'opentubex-nightly')
        self.assertEqual(release['packages'], 'opentubex-nightly-bin')
        self.assertEqual(release['pkgver'], '0.36.1.nightly.2112')
        original = (self.directory / 'opentubex-bin/.SRCINFO').read_bytes()
        self.metadata(release)
        info = (self.directory / 'opentubex-nightly-bin/.SRCINFO').read_text()
        self.assertIn('epoch = 1', info)
        self.assertIn('/v0.36.1-nightly-2112/opentubex_0.36.1-nightly-2112_amd64.deb', info)
        self.assertEqual((self.directory / 'opentubex-bin/.SRCINFO').read_bytes(), original)
        self.assertEqual((self.directory / 'opentubex-bin/opentubex.changelog').read_bytes(),
                         (ROOT / 'opentubex-bin/opentubex.changelog').read_bytes())

    def test_stable_downloads_source_archive(self):
        release = self.resolve('v0.36.1-beta')
        self.stub('gh', 'printf "%s\\n" "$*" >> "$GITHUB_WORKSPACE/downloads"\n')
        result = self.run_step('Download release files', RELEASE_TAG=release['tag'],
                               ASSET_VERSION=release['asset_version'],
                               PACKAGES=release['packages'])
        self.assertEqual(result.returncode, 0, result.stderr)
        downloads = (self.directory / 'downloads').read_text()
        self.assertIn('--archive tar.gz', downloads)
        self.assertIn('opentubex_0.36.1_beta_amd64.deb', downloads)

    def test_default_is_latest_stable(self):
        self.stub('gh', 'echo v0.36.1-beta\n')
        self.assertIn('opentubex-nightly-bin', self.resolve('')['packages'].split())

    def test_stable_publishes_git_recipe_without_rewriting_it(self):
        release = self.resolve('v0.36.1-beta', 'opentubex-release')
        self.assertIn('opentubex-git', release['packages'].split())
        recipe = self.directory / 'opentubex-git/PKGBUILD'
        original = recipe.read_bytes()
        self.metadata(release)
        self.assertEqual(recipe.read_bytes(), original)
        self.assertEqual((self.directory / 'opentubex-git/.SRCINFO').read_bytes(),
                         (ROOT / 'opentubex-git/.SRCINFO').read_bytes())

    def test_git_recipe_metadata_and_local_checksums(self):
        package = self.directory / 'opentubex-git'
        info = (package / '.SRCINFO').read_text()
        generated = subprocess.check_output(['makepkg', '--printsrcinfo'],
                                            cwd=package, text=True)
        self.assertEqual(generated, info)
        checksums = [line.split(' = ', 1)[1] for line in info.splitlines()
                     if line.strip().startswith('sha256sums = ')]
        self.assertEqual(checksums[0], 'SKIP')
        for filename, checksum in zip(('opentubex.desktop', 'opentubex.sh'), checksums[1:]):
            self.assertEqual(hashlib.sha256((package / filename).read_bytes()).hexdigest(),
                             checksum)

    def test_nightly_download_skips_source_archive(self):
        release = self.resolve('v0.36.1-nightly-2112')
        self.stub('gh', 'printf "%s\\n" "$*" >> "$GITHUB_WORKSPACE/downloads"\n')
        result = self.run_step('Download release files', RELEASE_TAG=release['tag'],
                               ASSET_VERSION=release['asset_version'],
                               PACKAGES=release['packages'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('--archive', (self.directory / 'downloads').read_text())

    def test_promotion_and_next_nightly_upgrade(self):
        # Nightlies are tagged after the release they are numbered after.
        # The first version is the previously published nightly format.
        versions = ['1:0.35.2nightly.1948-1']
        for tag in ('v0.36.0-beta', 'v0.36.0-nightly-2111',
                    'v0.36.1-beta', 'v0.36.1-nightly-2112'):
            release = self.resolve(tag)
            self.metadata(release)
            info = (self.directory / 'opentubex-nightly-bin/.SRCINFO').read_text()
            fields = dict(line.strip().split(' = ', 1) for line in info.splitlines()
                          if ' = ' in line)
            versions.append(f'{fields["epoch"]}:{fields["pkgver"]}-{fields["pkgrel"]}')
        for older, newer in zip(versions, versions[1:]):
            self.assertEqual(subprocess.check_output(['vercmp', newer, older],
                                                    text=True).strip(), '1')

    def test_invalid_tags_and_dispatch_mismatches(self):
        for tag, event in (('', 'opentubex-nightly'),
                           ('v0.36.1-beta', 'opentubex-nightly'),
                           ('v0.36.1-nightly-2112', 'opentubex-release'),
                           ('v0.36.1', ''), ('invalid', '')):
            with self.subTest(tag=tag, event=event):
                result = self.run_step('Resolve release', INPUT_TAG=tag, EVENT_TYPE=event)
                self.assertNotEqual(result.returncode, 0)

    def test_aur_network_operations_retry_twice(self):
        self.stub('sleep', 'printf "%s\\n" "$*" >> "$GITHUB_WORKSPACE/delays"\n')
        self.stub('git', '''
if [[ "$1" == -C ]]; then
  shift 2
fi
operation="$1"
printf '%s\\n' "$operation" >> "$GITHUB_WORKSPACE/git-calls"
if [[ "$operation" == clone || "$operation" == push ]]; then
  counter="$GITHUB_WORKSPACE/attempts-$operation"
  count=0
  if [[ -f "$counter" ]]; then
    read -r count < "$counter"
  fi
  count=$((count + 1))
  printf '%s\\n' "$count" > "$counter"
  if [[ "$operation" == "$FAIL_OPERATION" ]] && (( count <= FAILURES )); then
    echo 'Connection closed by AUR' >&2
    exit 128
  fi
fi
case "$operation" in
  clone) mkdir -p "$3" ;;
  diff) [[ "$3" != --quiet ]] ;;
  log) echo 'test release' ;;
  commit) cat > /dev/null ;;
esac
''')
        for operation in ('clone', 'push'):
            for failures in range(4):
                with self.subTest(operation=operation, failures=failures):
                    shutil.rmtree(self.directory / 'aur-packages', ignore_errors=True)
                    for name in ('attempts-clone', 'attempts-push', 'delays', 'git-calls'):
                        (self.directory / name).unlink(missing_ok=True)
                    result = self.run_step('Publish packages', VERSION='0.36.1',
                                           PACKAGES='opentubex-nightly-bin',
                                           FAIL_OPERATION=operation, FAILURES=str(failures))
                    self.assertEqual(result.returncode, 128 if failures == 3 else 0,
                                     result.stderr)
                    attempts = int((self.directory / f'attempts-{operation}').read_text())
                    self.assertEqual(attempts, min(failures + 1, 3))
                    delays = self.directory / 'delays'
                    self.assertEqual(delays.read_text().splitlines() if delays.exists() else [],
                                     ['10'] * min(failures, 2))
                    calls = (self.directory / 'git-calls').read_text().splitlines()
                    self.assertEqual(calls.count('commit'),
                                     0 if operation == 'clone' and failures == 3 else 1)

    def test_arch_upgrade_order(self):
        versions = ['0.36.0.nightly.2111', '1:0.36.0nightly.2111',
                    '1:0.36.0nightly.2112', '1:0.36.0',
                    '1:0.36.1nightly.2113', '1:0.36.1']
        for older, newer in zip(versions, versions[1:]):
            with self.subTest(older=older, newer=newer):
                result = subprocess.check_output(['vercmp', newer, older], text=True)
                self.assertEqual(result.strip(), '1')


if __name__ == '__main__':
    unittest.main()
