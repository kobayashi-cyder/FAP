from __future__ import annotations

import fap_v87_32_unified_chat_gateway as latest


def test_status_reports_current_mainline_and_preserves_reasoning_stack():
    core = latest.FAPV8732Unified()
    status = core.status()
    assert status["version"] == "87.32-unified-chat"
    assert status["mainline_version"] == "87.32"
    assert status["chat_stack"]["general_chat"].startswith("V87.12")
    assert status["chat_stack"]["structured_reasoning"] == "V87.25-V87.28"
    assert status["chat_stack"]["media"] == "V87.32 photo-look-native"
    assert "latest-mainline-chat:v87.32" in core.capabilities()


def test_non_image_route_keeps_existing_calculator_behavior():
    core = latest.FAPV8732Unified()
    intent = latest.base.Intent("calculator", 0.99, [("calculator", 0.99)])
    out = core.route(intent, "1+2", [])
    assert out["ok"] is True
    assert "= 3" in out["reply"]


def test_image_capability_uses_native_v8732_not_external_api():
    core = latest.FAPV8732Unified()
    intent = latest.base.Intent("image_capability", 0.99, [("image_capability", 0.99)])
    out = core.route(intent, "画像生成できますか？", [])
    assert out["ok"] is True
    assert "V87.32" in out["reply"]
    assert "外部画像APIは不要" in out["reply"]


def test_rejected_photo_candidate_is_visible_but_not_claimed_accepted():
    core = latest.FAPV8732Unified()
    core.photo_runtime.generate = lambda payload: {
        "accepted": False,
        "status": "rejected",
        "artifact": {
            "url": "/artifacts/demo.png",
            "filename": "demo.png",
            "verification_score": 0.58,
            "issues": [
                {
                    "code": "photorealism_not_yet_verified",
                    "severity": "fatal",
                    "detail": "not yet verified",
                }
            ],
        },
    }
    intent = latest.base.Intent("image_generate", 0.99, [("image_generate", 0.99)])
    out = core.route(intent, "人と犬の写真風画像を生成して", [])
    assert out["ok"] is False
    assert "NOT ACCEPTED" in out["reply"]
    assert "photorealism_not_yet_verified" in out["reply"]
    assert out["artifacts"][0]["src"] == "/artifacts/demo.png"
