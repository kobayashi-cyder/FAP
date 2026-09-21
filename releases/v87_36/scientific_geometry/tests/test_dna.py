from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_scientific_geometry import (
    ScientificGeometryCritic,
    ScientificGeometryEngine,
    build_dna_mesh,
    parse_dna_request,
    reverse_complement,
)


def req(prompt: str):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=220,
        height=300,
        max_attempts=1,
        min_score=0.99,
        constraints=(),
    )


def test_parse_verified_b_dna_parameters():
    s = parse_dna_request("20塩基対のB-DNAを斜めから描く")
    assert s.form == "B-DNA"
    assert s.base_pairs == 20
    assert s.handedness == "right"
    assert abs(s.diameter_nm - 2.0) < 1e-9
    assert abs(s.rise_nm - 0.34) < 1e-9
    assert abs(s.bp_per_turn - 10.5) < 1e-9
    assert abs(s.pitch_nm - 3.57) < 1e-9


def test_sequence_and_complement_are_exact():
    s = parse_dna_request("B-DNA 配列: ATGCCGTA")
    assert s.sequence == "ATGCCGTA"
    assert s.complement == "TACGGCAT"
    assert reverse_complement(s.sequence) == "TACGGCAT"[::-1]


def test_dna_mesh_contains_two_backbones_and_all_pairs():
    s = parse_dna_request("12塩基対のB-DNA")
    mesh, positions, meta = build_dna_mesh(s)
    assert len(mesh.vertices) == len(positions)
    assert len(mesh.faces) > 500
    assert meta["backbone_strands"] == 2
    assert meta["antiparallel"] is True
    assert meta["base_pairs"] == 12


def test_engine_writes_real_dna_png(tmp_path: Path):
    e = ScientificGeometryEngine(artifact_dir=tmp_path)
    r = req("20塩基対のB-DNA、配列: ATGCCGTAGCTAACGTTGCA")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    p = Path(a.locator)
    assert p.is_file()
    assert p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    g = a.metadata["scientific_geometry"]
    assert g["base_pairs"] == 20
    assert g["form"] == "B-DNA"
    assert g["handedness"] == "right"


def test_b_dna_critic_passes_geometry_and_complementarity(tmp_path: Path):
    e = ScientificGeometryEngine(artifact_dir=tmp_path)
    r = req("16塩基対のB-DNA 配列: ATGCGTACATGCGTAC")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    c = ScientificGeometryCritic().critique(r, a)
    assert c.score == 1.0
    assert not c.has_fatal
    assert c.evidence["count_score"] == 1.0
    assert c.evidence["sequence_score"] == 1.0
    assert c.evidence["geometry_score"] == 1.0
    assert c.evidence["strand_score"] == 1.0


def test_non_b_dna_fails_closed_until_form_specific_validation(tmp_path: Path):
    e = ScientificGeometryEngine(artifact_dir=tmp_path)
    r = req("20塩基対のZ-DNA")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    c = ScientificGeometryCritic().critique(r, a)
    assert c.score == 0.0
    assert any(i.code == "dna_form_unverified" for i in c.issues)
