# Copyright 2024 Lawrence Livermore National Security, LLC
# see: ${repository}/LICENSE
#
# SPDX-License-Identifier: MIT

import json
import tarfile
from pathlib import PurePosixPath
from typing import IO, Any, Union

import surfactant.plugin
from surfactant.sbomtypes import SBOM, Software


def get_manifest_file_from_tarball(tarball: tarfile.TarFile) -> IO[bytes] | None:
    return tarball.extractfile(
        {tarinfo.name: tarinfo for tarinfo in tarball.getmembers()}["manifest.json"]
    )


def get_config_file_from_tarball(tarball: tarfile.TarFile, path: str) -> Union[IO[bytes], None]:
    return tarball.extractfile({tarinfo.name: tarinfo for tarinfo in tarball.getmembers()}[path])


def get_config_path_from_manifest(manifest: list[dict[str, Any]]) -> list[str]:
    path = "Config"
    return [entry[path] for entry in manifest]


def get_repo_tags_from_manifest(manifest: list[dict[str, Any]]) -> list[str]:
    path = "RepoTags"
    return [entry[path] for entry in manifest]


def portable_path_list(*paths: str):
    """Convert paths to a portable format acknowledged by"""
    return tuple(str(PurePosixPath(path_str)) for path_str in paths)


def supports_file(filename: str, filetype: str) -> bool:
    EXPECTED_FILETYPE = "DOCKER_TAR"

    expected_members = portable_path_list(
        "index.json",
        "manifest.json",
        "oci-layout",
        "repositories",
        "blobs/sha256",
    )

    if filetype != EXPECTED_FILETYPE:
        return False

    with tarfile.open(filename) as this_tarfile:
        found_members = portable_path_list(*[member.name for member in this_tarfile.getmembers()])

    return all(expected_member in found_members for expected_member in expected_members)


@surfactant.plugin.hookimpl
def extract_file_info(sbom: SBOM, software: Software, filename: str, filetype: str) -> object:
    if not supports_file(filename, filetype):
        return None
    return extract_image_info(filename)


def extract_image_info(filename: str):
    """Return image configuration objects mapped by their paths."""
    root_key = "dockerImageConfigs"
    image_info: dict[str, list[dict[str, Any]]] = {root_key: []}
    with tarfile.open(filename) as tarball:
        # we know the manifest file is present or we wouldn't be this far
        assert (manifest_file := get_manifest_file_from_tarball(tarball))
        manifest = json.load(manifest_file)
        for config_path in manifest.get_config_path_from_manifest(manifest):
            assert (config_file := get_config_file_from_tarball(tarball, config_path))
            config = json.load(config_file)
            image_info[root_key].append(config)
    return image_info
