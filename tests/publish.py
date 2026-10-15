#!/usr/bin/env python3
"""Exercise the publish workflow without downloading or publishing releases."""

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
            (files / f'opentubex_{release["asset_version"]}_{arch}.deb').write_text(arch)
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

    def test_nightly_only_updates_nightly_package(self):
        release = self.resolve('v0.36.1-nightly-2112', 'opentubex-nightly')
        self.assertEqual(release['packages'], 'opentubex-nightly-bin')
        self.assertEqual(release['pkgver'], '0.36.1nightly.2112')
        original = (self.directory / 'opentubex-bin/.SRCINFO').read_bytes()
        self.metadata(release)
        info = (self.directory / 'opentubex-nightly-bin/.SRCINFO').read_text()
        self.assertIn('epoch = 1', info)
        self.assertIn('/v0.36.1-nightly-2112/opentubex_0.36.1-nightly-2112_amd64.deb', info)
        self.assertEqual((self.directory / 'opentubex-bin/.SRCINFO').read_bytes(), original)

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
        versions = []
        for tag in ('v0.36.0-nightly-2111', 'v0.36.0-beta',
                    'v0.36.1-nightly-2112'):
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
