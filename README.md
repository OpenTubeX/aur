# OpenTubeX AUR packages

This repository is the source of truth for the
[`opentubex`](https://aur.archlinux.org/packages/opentubex) and
[`opentubex-bin`](https://aur.archlinux.org/packages/opentubex-bin) AUR
packages, and the `opentubex-nightly-bin` package.

`opentubex-nightly-bin` installs the published nightly binaries for x86_64
and aarch64. It replaces the stable package and uses the same application
data. Install it with `paru -S opentubex-nightly-bin` once it is published.

## How publishing works

After an OpenTubeX release finishes uploading its assets, the application
repository sends an `opentubex-release` repository dispatch containing the
release tag. Nightly releases send `opentubex-nightly` after both supported
DEB assets are publicly available. The publish workflow then:

1. starts with the package files tracked in this repository;
2. updates `pkgver`, resets `pkgrel` to 1 when the version changes, and refreshes release checksums and
   the generated `.SRCINFO` files;
3. commits that release metadata back to this repository;
4. copies the resulting files to AUR and publishes each package when its
   files changed.

Stable releases update `opentubex` and `opentubex-bin`. Nightly releases
update only `opentubex-nightly-bin`. For example, release tag
`v0.36.0-nightly-2111` becomes Arch package version `0.36.0.nightly.2111`.

This means package-specific changes, such as updating the system Electron
dependency and launcher in `opentubex`, can be developed here before a release.
The next release will retain those changes while refreshing its versioned
metadata.

The workflow can also be run manually with a beta or nightly release tag.
If no tag is given, it publishes the latest stable OpenTubeX release.

## Maintainer setup

Add the SSH private key authorized to publish all three AUR packages as the
`AUR_SSH_PRIVATE_KEY` repository secret. The OpenTubeX application repository's
`PUSH_TOKEN` must also have write access to this repository so it can send the
cross-repository dispatch.

The first nightly publish creates the AUR package if the key's account can
register `opentubex-nightly-bin`. If it already exists, that account must be
its maintainer or co-maintainer.
