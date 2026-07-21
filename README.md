# OpenTubeX AUR packages

This repository is the source of truth for the
[`opentubex`](https://aur.archlinux.org/packages/opentubex) and
[`opentubex-bin`](https://aur.archlinux.org/packages/opentubex-bin) AUR
packages.

## How publishing works

After an OpenTubeX release finishes uploading its assets, the application
repository sends an `opentubex-release` repository dispatch containing the
release tag. The publish workflow then:

1. starts with the package files tracked in this repository;
2. updates only `pkgver`, release checksums, and the generated `.SRCINFO` files;
3. commits that release metadata back to this repository;
4. copies the resulting files to the two AUR repositories and publishes each
   package when its files changed.

This means package-specific changes, such as updating the system Electron
dependency and launcher in `opentubex`, can be developed here before a release.
The next release will retain those changes while refreshing its versioned
metadata.

The workflow can also be run manually with a release tag. If no tag is given,
it publishes the latest OpenTubeX release.

## Maintainer setup

Add the SSH private key authorized to publish both AUR packages as the
`AUR_SSH_PRIVATE_KEY` repository secret. The OpenTubeX application repository's
`PUSH_TOKEN` must also have write access to this repository so it can send the
cross-repository dispatch.
