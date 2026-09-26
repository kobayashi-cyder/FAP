from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from fap_offline_bundle import BundleError, SSD1B_BUNDLE, prepare_bundle, verify_bundle


def tiny_plan(data: bytes):
    return replace(
        SSD1B_BUNDLE,
        checkpoint_size=len(data),
        checkpoint_sha256=sha256(data).hexdigest(),
    )


def fake_snapshot(repo_id, revision, patterns, dest):
    (dest / "model_index.json").write_text("{}", encoding="utf-8")
    (dest / "scheduler").mkdir()
    (dest / "scheduler" / "scheduler_config.json").write_text("{}", encoding="utf-8")
    return dest


def file_downloader(data):
    def download(repo_id, revision, filename, dest):
        path = dest / filename
        path.write_bytes(data)
        return path
    return download


def test_prepare_bundle_requires_explicit_license_acceptance(tmp_path):
    with pytest.raises(BundleError, match="license"):
        prepare_bundle(
            tmp_path / "bundle",
            plan=tiny_plan(b"x"),
            download_file=file_downloader(b"x"),
            download_snapshot=fake_snapshot,
            accept_license=False,
        )


def test_prepare_and_verify_bundle(tmp_path):
    data = b"PINNED-CHECKPOINT"
    plan = tiny_plan(data)
    root = tmp_path / "bundle"
    result = prepare_bundle(
        root,
        plan=plan,
        download_file=file_downloader(data),
        download_snapshot=fake_snapshot,
        accept_license=True,
    )
    assert result["offline_ready"] is True
    assert result["checkpoint_sha256"] == sha256(data).hexdigest()
    assert (root / "ssd1b-config" / "model_index.json").is_file()
    assert (root / plan.checkpoint_name).is_file()
    assert (root / (plan.checkpoint_name + ".fap.json")).is_file()
    assert verify_bundle(root, plan=plan)["offline_ready"] is True


def test_corrupted_checkpoint_is_rejected(tmp_path):
    data = b"GOOD"
    plan = tiny_plan(data)
    root = tmp_path / "bundle"
    prepare_bundle(
        root,
        plan=plan,
        download_file=file_downloader(data),
        download_snapshot=fake_snapshot,
        accept_license=True,
    )
    (root / plan.checkpoint_name).write_bytes(b"BAD!")
    with pytest.raises(BundleError, match="SHA|size"):
        verify_bundle(root, plan=plan)


def test_wrong_download_hash_never_activates_bundle(tmp_path):
    good = b"GOOD"
    wrong = b"EVIL"
    plan = tiny_plan(good)
    with pytest.raises(BundleError, match="SHA|size"):
        prepare_bundle(
            tmp_path / "bundle",
            plan=plan,
            download_file=file_downloader(wrong),
            download_snapshot=fake_snapshot,
            accept_license=True,
        )


def test_sidecar_records_license_and_source_checksum(tmp_path):
    data = b"MODEL"
    plan = tiny_plan(data)
    root = tmp_path / "bundle"
    prepare_bundle(
        root,
        plan=plan,
        download_file=file_downloader(data),
        download_snapshot=fake_snapshot,
        accept_license=True,
    )
    sidecar = json.loads(
        (root / (plan.checkpoint_name + ".fap.json")).read_text(encoding="utf-8")
    )
    assert sidecar["license_id"] == "apache-2.0"
    assert sidecar["source_checkpoint_sha256"] == sha256(data).hexdigest()
    assert sidecar["distilled"] is True
