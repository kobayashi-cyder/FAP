from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_morphology import MorphologyEngine, MorphologyQualityCritic, parse_morphology_graph


def req(prompt: str):
    return GenerationRequest(
        prompt=prompt,
        media_type="image",
        width=192,
        height=256,
        max_attempts=1,
        min_score=0.99,
        constraints=(),
    )


def test_parser_marks_calico_and_hachiware():
    g = parse_morphology_graph("三毛の八割れ猫が立っている")
    cats = [n for n in g.nodes if n.kind == "cat"]
    assert len(cats) == 1
    attrs = cats[0].attr_dict()
    assert attrs["coat_pattern"] == "calico"
    assert attrs["face_pattern"] == "hachiware"


def test_calico_cat_generates_pattern_metadata_and_png(tmp_path: Path):
    e = MorphologyEngine(artifact_dir=tmp_path)
    r = req("三毛猫")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    assert Path(a.locator).is_file()
    assert Path(a.locator).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    cat = next(x for x in a.metadata["generated_nodes"] if x["kind"] == "cat")
    assert cat["coat_pattern_applied"] == "calico"


def test_hachiware_cat_generates_face_pattern(tmp_path: Path):
    e = MorphologyEngine(artifact_dir=tmp_path)
    r = req("八割れ猫")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    cat = next(x for x in a.metadata["generated_nodes"] if x["kind"] == "cat")
    assert cat["face_pattern_applied"] == "hachiware"


def test_combined_pattern_differs_from_plain_cat(tmp_path: Path):
    e = MorphologyEngine(artifact_dir=tmp_path)
    plain = e.generate(req("猫"), prompt="猫", previous=None, critique=None)
    combo = e.generate(
        req("三毛の八割れ猫"),
        prompt="三毛の八割れ猫",
        previous=None,
        critique=None,
    )
    assert plain.digest != combo.digest


def test_morphology_critic_passes_requested_cat_patterns(tmp_path: Path):
    e = MorphologyEngine(artifact_dir=tmp_path)
    r = req("三毛の八割れ猫")
    a = e.generate(r, prompt=r.prompt, previous=None, critique=None)
    c = MorphologyQualityCritic().critique(r, a)
    assert c.evidence["morphology_score"] == 1.0
    assert not any(i.code == "cat_pattern_unmet" for i in c.issues)


def test_other_cat_coats_parse():
    cases = {
        "キジトラ猫": "tabby",
        "サバトラ猫": "silver_tabby",
        "茶トラ猫": "orange_tabby",
        "サビ猫": "tortoiseshell",
    }
    for text, expected in cases.items():
        g = parse_morphology_graph(text)
        cat = next(n for n in g.nodes if n.kind == "cat")
        assert cat.attr_dict()["coat_pattern"] == expected
