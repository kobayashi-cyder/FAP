from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import html
import json
import re

from fap_builder import BuilderError
from fap_concept_builder import ConceptMechanismBuilder
from fap_generic_builder import ArtifactSpec


_COLOR = {
    "赤": "#ef5350", "赤い": "#ef5350", "red": "#ef5350",
    "緑": "#42d392", "緑の": "#42d392", "green": "#42d392",
    "青": "#42a5f5", "青い": "#42a5f5", "blue": "#42a5f5",
    "黄": "#ffd54f", "黄色": "#ffd54f", "yellow": "#ffd54f",
    "白": "#f5f5f5", "white": "#f5f5f5",
    "紫": "#ab7cff", "purple": "#ab7cff",
    "橙": "#ff9f43", "オレンジ": "#ff9f43", "orange": "#ff9f43",
}


@dataclass(frozen=True)
class CompiledGameSpec:
    kind: str = "single_html_game"
    family: str = "grid_collect_hazard"
    rows: int | None = None
    cols: int | None = None
    player_color: str | None = None
    movement: tuple[str, ...] = ()
    collectible_kind: str | None = None
    collectible_target: int | None = None
    hazard_kind: str | None = None
    hazard_color: str | None = None
    hazard_relocate_every: int | None = None
    lose_on_hazard_contact: bool | None = None
    controls: str | None = None
    restart: bool = False
    evidence: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


class SpecificationCompilerBuilder(ConceptMechanismBuilder):
    """V87.07 local Specification Compiler.

    It first preserves all V87.06 named/concept builders. For otherwise unknown
    game requests, it extracts explicit constraints from the user's natural
    language and compiles them into a structured grid-game specification.
    Complete specifications are built immediately; only genuinely missing
    fields cause targeted questions.
    """

    SPEC_PRIMITIVES = {
        "spec.compile", "grid.board", "player.gridmove", "collectible.spawn",
        "collectible.counter", "win.collect_target", "hazard.spawn",
        "hazard.random_relocate", "collision.lose", "input.touch_dpad",
        "restart", "state.counter",
    }
    PRIMITIVES = set(ConceptMechanismBuilder.PRIMITIVES) | SPEC_PRIMITIVES

    COLOR_PATTERN = r"(赤(?:い)?|緑(?:の)?|青(?:い)?|黄(?:色)?|白|紫|橙|オレンジ|red|green|blue|yellow|white|purple|orange)"

    def compile_spec(self, text: str) -> CompiledGameSpec:
        src = str(text or "").strip()
        low = src.lower()
        evidence: list[str] = []

        rows = cols = None
        m = re.search(r"(\d{1,2})\s*[×xX＊*]\s*(\d{1,2})\s*(?:の)?(?:盤面|グリッド|マス|board|grid)?", src, re.I)
        if m:
            rows, cols = int(m.group(1)), int(m.group(2))
            if 3 <= rows <= 20 and 3 <= cols <= 20:
                evidence.append(f"board={rows}x{cols}")
            else:
                rows = cols = None

        player_color = None
        m = re.search(self.COLOR_PATTERN + r"\s*(?:の)?\s*(?:駒|プレイヤー|キャラ(?:クター)?|自機)", src, re.I)
        if m:
            token = m.group(1).lower()
            player_color = _COLOR.get(token) or _COLOR.get(m.group(1))
            if player_color:
                evidence.append(f"player_color={m.group(1)}")

        movement: tuple[str, ...] = ()
        if re.search(r"上下左右|上[・,/ ]*下[・,/ ]*左[・,/ ]*右|4方向|四方向|up.{0,3}down.{0,3}left.{0,3}right", src, re.I):
            movement = ("up", "down", "left", "right")
            evidence.append("movement=cardinal4")

        collectible_kind = None
        collectible_target = None
        collect_words = {
            "星": "star", "スター": "star", "コイン": "coin", "宝物": "treasure",
            "宝": "treasure", "アイテム": "item", "gem": "gem", "star": "star", "coin": "coin",
        }
        for word, kind in collect_words.items():
            pat = rf"{re.escape(word)}\s*(?:を)?\s*(\d{{1,2}})\s*(?:個|つ|枚)?\s*(?:集め|取|獲得|回収)"
            m = re.search(pat, src, re.I)
            if not m:
                pat = rf"(\d{{1,2}})\s*(?:個|つ|枚)?\s*(?:の)?\s*{re.escape(word)}.*?(?:集め|取|獲得|回収)"
                m = re.search(pat, src, re.I)
            if m:
                collectible_kind = kind
                collectible_target = int(m.group(1))
                if 1 <= collectible_target <= 50:
                    evidence.append(f"collect={kind}:{collectible_target}")
                else:
                    collectible_kind = None
                    collectible_target = None
                break

        hazard_kind = None
        hazard_color = None
        hm = re.search(self.COLOR_PATTERN + r"\s*(?:い|の)?\s*(障害物|敵|トラップ|罠)", src, re.I)
        if hm:
            hazard_color = _COLOR.get(hm.group(1).lower()) or _COLOR.get(hm.group(1))
            hazard_kind = {"敵":"enemy", "障害物":"obstacle", "トラップ":"trap", "罠":"trap"}.get(hm.group(2), "hazard")
            evidence.append(f"hazard={hazard_kind}:{hm.group(1)}")
        elif re.search(r"障害物|敵|トラップ|罠", src):
            hazard_kind = "hazard"
            hazard_color = "#ef5350"
            evidence.append("hazard=generic")

        hazard_relocate_every = None
        patterns = [
            r"(\d{1,2})\s*回(?:動く|移動する)?\s*(?:たび|ごと)に.{0,30}?(?:ランダム|無作為).{0,20}?(?:位置|場所)?.{0,8}?(?:変|移動|入れ替)",
            r"(\d{1,2})\s*手(?:ごと|たび)に.{0,30}?(?:ランダム|無作為).{0,20}?(?:変|移動|入れ替)",
            r"(?:ランダム|無作為).{0,30}?(\d{1,2})\s*(?:回|手)(?:ごと|たび)",
        ]
        for pat in patterns:
            m = re.search(pat, src, re.I)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 99:
                    hazard_relocate_every = n
                    evidence.append(f"hazard_relocate_every={n}")
                    break

        lose_on_hazard_contact = None
        if re.search(r"(?:障害物|敵|トラップ|罠).{0,18}?(?:触れ|当た|ぶつか|衝突).{0,12}?(?:負け|失敗|ゲームオーバー)", src, re.I) or re.search(r"(?:触れ|当た|ぶつか|衝突).{0,12}?(?:負け|失敗|ゲームオーバー)", src, re.I):
            lose_on_hazard_contact = True
            evidence.append("lose=hazard_contact")

        controls = None
        if re.search(r"スマホ.{0,10}?(?:ボタン|操作)|(?:画面|タッチ).{0,8}?ボタン|タッチ.{0,8}?(?:上下左右|方向)", src, re.I):
            controls = "touch_dpad"
            evidence.append("controls=touch_dpad")
        elif re.search(r"(?:矢印キー|キーボード|キー操作)", src, re.I):
            controls = "keyboard"
            evidence.append("controls=keyboard")

        restart = bool(re.search(r"再スタート|リスタート|restart|やり直", src, re.I))
        if restart:
            evidence.append("restart=true")

        # The grid family is selected only when the text contains multiple
        # independent mechanics. This avoids forcing arbitrary unknown games
        # into this compiler.
        family_hits = sum([
            rows is not None,
            bool(movement),
            collectible_target is not None,
            hazard_kind is not None,
            hazard_relocate_every is not None,
            lose_on_hazard_contact is True,
            controls is not None,
        ])
        if family_hits < 3:
            return CompiledGameSpec(evidence=tuple(evidence), missing=("ゲーム機構を特定できる具体的なルール",))

        missing: list[str] = []
        if rows is None or cols is None:
            missing.append("盤面サイズ（例: 6×6）")
        if not movement:
            missing.append("プレイヤーの移動方法（例: 上下左右）")
        if collectible_target is None:
            missing.append("勝利条件（例: 星を5個集める）")
        if hazard_kind is None:
            missing.append("失敗要因・障害物")
        if lose_on_hazard_contact is not True:
            missing.append("失敗条件（例: 障害物に触れたら負け）")
        if controls is None:
            missing.append("操作方法（例: スマホの方向ボタン）")

        return CompiledGameSpec(
            rows=rows, cols=cols,
            player_color=player_color or "#42d392",
            movement=movement,
            collectible_kind=collectible_kind or ("star" if collectible_target else None),
            collectible_target=collectible_target,
            hazard_kind=hazard_kind,
            hazard_color=hazard_color or "#ef5350",
            hazard_relocate_every=hazard_relocate_every,
            lose_on_hazard_contact=lose_on_hazard_contact,
            controls=controls,
            restart=restart,
            evidence=tuple(evidence),
            missing=tuple(missing),
        )

    def infer(self, text: str) -> ArtifactSpec:
        # Preserve all known V87.06 concept/recipe behavior first.
        base = super().infer(text)
        if base.target != "unknown_game":
            return base

        compiled = self.compile_spec(text)
        if compiled.family == "grid_collect_hazard" and not compiled.missing:
            features = [
                "html.shell", "spec.compile", "grid.board", "player.gridmove",
                "collectible.spawn", "collectible.counter", "win.collect_target",
                "hazard.spawn", "collision.lose", "state.counter",
            ]
            if compiled.hazard_relocate_every:
                features.append("hazard.random_relocate")
            if compiled.controls == "touch_dpad":
                features.append("input.touch_dpad")
            if compiled.restart:
                features.append("restart")
            return ArtifactSpec(
                "single_html", "game", "compiled_grid_game", "fap_compiled_grid_game.html",
                tuple(features), (),
            )
        return ArtifactSpec(
            "single_html", "game", "unknown_game", "fap_build_candidate.html", (),
            compiled.missing or base.missing,
        )

    def build(self, text: str) -> dict:
        base = super().infer(text)
        if base.target != "unknown_game":
            return super().build(text)

        compiled = self.compile_spec(text)
        if compiled.missing:
            questions = [f"{i+1}. {x}" for i, x in enumerate(compiled.missing)]
            return {
                "ok": False,
                "reply": (
                    "Builderとして仕様抽出を行いました。すでに書かれている条件は再質問しません。"
                    "不足している項目だけ教えてください。\n" + "\n".join(questions)
                ),
                "confidence": 0.93,
                "compiled_spec": asdict(compiled),
                "artifacts": [],
            }

        content = self._compiled_grid_game_html(compiled)
        filename = "fap_compiled_grid_game.html"
        candidate = self.workspace_dir / filename
        candidate.write_text(content, encoding="utf-8")
        report = self.validate_compiled(compiled, candidate)
        if not report["ok"]:
            raise BuilderError("spec validation failed: " + "; ".join(report["errors"]))

        final = self.artifacts_dir / filename
        final.write_bytes(candidate.read_bytes())
        digest = sha256(final.read_bytes()).hexdigest()
        mechanics = self._mechanics(compiled)
        return {
            "ok": True,
            "reply": (
                "作成しました。文章中の条件をSpecification Compilerで構造化し、新規ゲームとして合成しました。\n"
                "BUILD: Constraint extraction → Spec compilation → Mechanism mapping → Primitive composition → Verification → Artifact\n"
                f"spec: {compiled.rows}×{compiled.cols}, movement=cardinal4, collect={compiled.collectible_kind}:{compiled.collectible_target}, "
                f"hazard_relocate_every={compiled.hazard_relocate_every or 'fixed'}, controls={compiled.controls}\n"
                f"mechanisms: {', '.join(mechanics)}\n"
                f"抽出根拠: {', '.join(compiled.evidence)}\n"
                f"検証: {', '.join(report['checks'])} / {report['bytes']} bytes\n"
                f"下の {filename} を開いてください。"
            ),
            "confidence": 0.985,
            "compiled_spec": asdict(compiled),
            "validation": report,
            "artifacts": [{
                "type": "file", "src": f"/artifacts/{filename}", "name": filename,
                "sha256": digest, "mime": "text/html",
            }],
        }

    @staticmethod
    def _mechanics(spec: CompiledGameSpec) -> list[str]:
        out = ["grid.board", "player.gridmove", "collectible.spawn", "collectible.counter", "win.collect_target", "hazard.spawn", "collision.lose"]
        if spec.hazard_relocate_every:
            out.append("hazard.random_relocate")
        if spec.controls == "touch_dpad":
            out.append("input.touch_dpad")
        if spec.restart:
            out.append("restart")
        return out

    def validate_compiled(self, spec: CompiledGameSpec, path: Path) -> dict:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        low = text.lower()
        checks: list[str] = []
        errors: list[str] = []
        if len(raw) <= 300_000: checks.append("size_limit")
        else: errors.append("artifact exceeds 300KB")
        if "<!doctype html>" in low and "</html>" in low and "<script" in low: checks.append("single_file_html")
        else: errors.append("HTML shell incomplete")
        if not re.search(r"<(?:script|link)[^>]+(?:src|href)\s*=\s*[\"']https?://", text, re.I): checks.append("offline")
        else: errors.append("external dependency detected")
        if text.count("<script") == text.count("</script>"): checks.append("script_structure")
        else: errors.append("script tag imbalance")
        required = ["const ROWS=", "const COLS=", "function move", "function relocateHazard", "function reset", "function checkWin", "data-dir"]
        missing = [x for x in required if x not in text]
        if missing: errors.append("missing mechanics: " + ", ".join(missing))
        else: checks.append("compiled_mechanics")
        if f"const ROWS={spec.rows}" in text and f"const COLS={spec.cols}" in text: checks.append("dimensions")
        else: errors.append("compiled dimensions mismatch")
        if f"const TARGET={spec.collectible_target}" in text: checks.append("win_target")
        else: errors.append("collect target mismatch")
        if spec.hazard_relocate_every and f"const RELOCATE_EVERY={spec.hazard_relocate_every}" in text: checks.append("dynamic_hazard")
        elif not spec.hazard_relocate_every: checks.append("static_hazard")
        else: errors.append("hazard cadence mismatch")
        return {"ok": not errors, "checks": checks, "errors": errors, "bytes": len(raw)}

    @staticmethod
    def _compiled_grid_game_html(spec: CompiledGameSpec) -> str:
        rows, cols = int(spec.rows), int(spec.cols)
        target = int(spec.collectible_target)
        relocate = int(spec.hazard_relocate_every or 0)
        player_color = html.escape(spec.player_color or "#42d392")
        hazard_color = html.escape(spec.hazard_color or "#ef5350")
        symbol = {"star":"★", "coin":"●", "treasure":"◆", "item":"✦", "gem":"◆"}.get(spec.collectible_kind or "star", "★")
        touch = spec.controls == "touch_dpad"
        restart = spec.restart
        controls = '''<div class="dpad"><span></span><button data-dir="up">▲</button><span></span><button data-dir="left">◀</button><button data-dir="down">▼</button><button data-dir="right">▶</button></div>''' if touch else '<div class="hint">矢印キーで操作</div>'
        restart_html = '<button id="restart" class="restart">再スタート</button>' if restart else ''
        return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>FAP Compiled Grid Game</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#06100e;color:#effff6;font-family:system-ui,-apple-system,sans-serif}}.app{{width:min(96vw,620px);padding:16px}}h1{{font-size:20px;margin:0 0 8px}}.bar{{display:flex;gap:10px;justify-content:space-between;align-items:center;flex-wrap:wrap;margin:8px 0}}#board{{display:grid;gap:5px;width:min(92vw,520px);margin:12px auto;touch-action:none}}.cell{{aspect-ratio:1;border-radius:8px;background:#113028;display:grid;place-items:center;font-weight:900;font-size:clamp(16px,5vw,28px);user-select:none}}.player{{background:{player_color};color:#04100c}}.hazard{{background:{hazard_color};color:white}}.collect{{color:#ffd54f;text-shadow:0 0 10px #ffd54f}}button{{border:1px solid #385e51;background:#10251f;color:#effff6;border-radius:12px;padding:12px;font-weight:800}}.dpad{{display:grid;grid-template-columns:repeat(3,64px);gap:8px;justify-content:center;margin-top:12px}}.dpad button{{font-size:20px;min-height:54px}}.restart{{display:block;margin:12px auto}}#msg{{min-height:1.5em;text-align:center;color:#ffd6a6;font-weight:800}}.hint{{text-align:center;opacity:.75}}
</style></head><body><main class="app"><h1>FAP Compiled Grid Game</h1><div class="bar"><span>★ <b id="score">0</b> / {target}</span><span>MOVES <b id="moves">0</b></span></div><div id="msg"></div><div id="board"></div>{controls}{restart_html}</main><script>
const ROWS={rows};const COLS={cols};const TARGET={target};const RELOCATE_EVERY={relocate};
const board=document.getElementById('board'),scoreEl=document.getElementById('score'),movesEl=document.getElementById('moves'),msg=document.getElementById('msg');
board.style.gridTemplateColumns=`repeat(${{COLS}},1fr)`;
let player, hazard, stars, score, moves, ended;
const key=(p)=>p.r+','+p.c; const same=(a,b)=>a.r===b.r&&a.c===b.c;
function randomFree(blocked){{let p;do{{p={{r:Math.floor(Math.random()*ROWS),c:Math.floor(Math.random()*COLS)}}}}while(blocked.has(key(p)));return p}}
function reset(){{player={{r:0,c:0}};score=0;moves=0;ended=false;stars=[];const used=new Set([key(player)]);hazard=randomFree(used);used.add(key(hazard));for(let i=0;i<TARGET;i++){{const p=randomFree(used);stars.push(p);used.add(key(p));}}scoreEl.textContent=0;movesEl.textContent=0;msg.textContent='';render();}}
function relocateHazard(){{const used=new Set([key(player),...stars.map(key)]);hazard=randomFree(used);}}
function checkWin(){{if(score>=TARGET){{ended=true;msg.textContent='CLEAR! 星を'+TARGET+'個集めました。';}}}}
function move(dr,dc){{if(ended)return;const nr=Math.max(0,Math.min(ROWS-1,player.r+dr)),nc=Math.max(0,Math.min(COLS-1,player.c+dc));if(nr===player.r&&nc===player.c)return;player={{r:nr,c:nc}};moves++;if(same(player,hazard)){{ended=true;msg.textContent='GAME OVER: 障害物に触れました。';render();return;}}const i=stars.findIndex(s=>same(s,player));if(i>=0){{stars.splice(i,1);score++;scoreEl.textContent=score;checkWin();}}if(!ended&&RELOCATE_EVERY>0&&moves%RELOCATE_EVERY===0){{relocateHazard();if(same(player,hazard)){{ended=true;msg.textContent='GAME OVER: 障害物が移動してきました。';}}}}movesEl.textContent=moves;render();}}
function render(){{board.innerHTML='';for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){{const d=document.createElement('div');d.className='cell';const p={{r,c}};if(same(p,player)){{d.classList.add('player');d.textContent='●';}}else if(same(p,hazard)){{d.classList.add('hazard');d.textContent='×';}}else if(stars.some(s=>same(s,p))){{d.classList.add('collect');d.textContent='{symbol}';}}board.appendChild(d);}}}}
const DIR={{up:[-1,0],down:[1,0],left:[0,-1],right:[0,1]}};document.querySelectorAll('[data-dir]').forEach(b=>b.addEventListener('click',()=>move(...DIR[b.dataset.dir])));addEventListener('keydown',e=>{{const m={{ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'}}[e.key];if(m){{e.preventDefault();move(...DIR[m]);}}}});const rb=document.getElementById('restart');if(rb)rb.onclick=reset;reset();
</script></body></html>'''
