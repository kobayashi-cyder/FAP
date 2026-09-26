from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import html
import json
import re
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BuildPlan:
    kind: str
    recipe: str
    filename: str
    goal: str
    components: tuple[str, ...]
    checks: tuple[str, ...]


class BuilderError(RuntimeError):
    pass


def _safe_filename(name: str, default: str = "artifact.html") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]", "_", str(name or ""))[:80]
    value = value.strip("._")
    return value or default


class ArtifactBuilder:
    """Constrained local artifact builder for FAP V87.04.

    Stage 1 intentionally uses deterministic recipes and a small primitive registry.
    It does not claim arbitrary natural-language programming.
    """

    PRIMITIVES = {
        "html.shell",
        "canvas.grid",
        "input.keyboard",
        "game.loop",
        "piece.rotate",
        "collision.grid",
        "line.clear",
        "score.counter",
        "ui.restart",
        "json.document",
    }

    def __init__(self, artifacts_dir: Path, workspace_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self.workspace_dir = Path(workspace_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_build_request(text: str) -> bool:
        t = str(text or "")
        create = bool(re.search(r"(作って|作成|生成|構築|build|create|make)", t, re.I))
        target = bool(re.search(
            r"(テトリス|tetris|html|web|ウェブ|ゲーム|game|python|py(?:thon)?|json|設定ファイル|スクリプト|script|ファイル|tool|ツール)",
            t,
            re.I,
        ))
        return create and target

    def plan(self, text: str) -> BuildPlan:
        t = str(text or "").strip()
        if re.search(r"(テトリス|tetris)", t, re.I):
            return BuildPlan(
                kind="single_html",
                recipe="tetris",
                filename="fap_tetris.html",
                goal=t,
                components=(
                    "html.shell", "canvas.grid", "input.keyboard", "game.loop",
                    "piece.rotate", "collision.grid", "line.clear", "score.counter", "ui.restart",
                ),
                checks=("single_file", "offline", "syntax", "tetris_features", "size_limit"),
            )
        if re.search(r"\bjson\b|設定ファイル", t, re.I):
            return BuildPlan(
                kind="json",
                recipe="generic_config",
                filename="fap_config.json",
                goal=t,
                components=("json.document",),
                checks=("json_parse", "size_limit"),
            )
        if re.search(r"html|web|ウェブ", t, re.I):
            return BuildPlan(
                kind="single_html",
                recipe="generic_page",
                filename="fap_page.html",
                goal=t,
                components=("html.shell",),
                checks=("single_file", "offline", "syntax", "size_limit"),
            )
        raise BuilderError("現在のBuilder Stage 1では、この成果物タイプの確定生成レシピがありません。")

    def build(self, text: str) -> dict:
        plan = self.plan(text)
        missing = [x for x in plan.components if x not in self.PRIMITIVES]
        if missing:
            raise BuilderError("missing primitives: " + ", ".join(missing))

        if plan.recipe == "tetris":
            content = self._tetris_html()
        elif plan.recipe == "generic_page":
            content = self._generic_html(plan.goal)
        elif plan.recipe == "generic_config":
            content = json.dumps({
                "created_by": "FAP V87.04 Builder Organ",
                "goal": plan.goal,
                "status": "candidate",
                "notes": "Stage 1 deterministic local artifact",
            }, ensure_ascii=False, indent=2) + "\n"
        else:
            raise BuilderError("unknown recipe")

        filename = _safe_filename(plan.filename)
        candidate = self.workspace_dir / filename
        candidate.write_text(content, encoding="utf-8")
        report = self.validate(plan, candidate)
        if not report["ok"]:
            raise BuilderError("validation failed: " + "; ".join(report["errors"]))

        final = self.artifacts_dir / filename
        final.write_bytes(candidate.read_bytes())
        digest = sha256(final.read_bytes()).hexdigest()
        artifact_type = "file"
        return {
            "ok": True,
            "reply": self._reply(plan, report),
            "confidence": 0.96,
            "build_plan": asdict(plan),
            "validation": report,
            "artifacts": [{
                "type": artifact_type,
                "src": f"/artifacts/{filename}",
                "name": filename,
                "sha256": digest,
                "mime": "text/html" if final.suffix == ".html" else "application/json",
            }],
        }

    def validate(self, plan: BuildPlan, path: Path) -> dict:
        errors: list[str] = []
        checks: list[str] = []
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        if len(raw) > 300_000:
            errors.append("artifact exceeds 300KB Stage-1 limit")
        else:
            checks.append("size_limit")

        if plan.kind == "json":
            try:
                obj = json.loads(text)
                if not isinstance(obj, dict):
                    errors.append("JSON root must be object")
                else:
                    checks.append("json_parse")
            except json.JSONDecodeError as exc:
                errors.append(f"JSON parse failed: {exc}")
        elif plan.kind == "single_html":
            lower = text.lower()
            if "<!doctype html>" not in lower or "<html" not in lower or "</html>" not in lower:
                errors.append("HTML shell incomplete")
            else:
                checks.append("single_file")
            # Stage 1 HTML must remain offline/self-contained.
            if re.search(r"<(?:script|link)[^>]+(?:src|href)\s*=\s*[\"']https?://", text, re.I):
                errors.append("external script/style dependency detected")
            else:
                checks.append("offline")
            if text.count("<script") != text.count("</script>"):
                errors.append("script tag imbalance")
            else:
                checks.append("syntax_structure")

        if plan.recipe == "tetris":
            required = {
                "canvas": "<canvas",
                "seven_pieces": "I:'",
                "rotation": "function rotate",
                "collision": "function collide",
                "line_clear": "function sweep",
                "score": "score",
                "keyboard": "keydown",
                "restart": "restart",
            }
            missing = [name for name, needle in required.items() if needle not in text]
            if missing:
                errors.append("missing tetris features: " + ", ".join(missing))
            else:
                checks.append("tetris_features")

        return {"ok": not errors, "checks": checks, "errors": errors, "bytes": len(raw)}

    @staticmethod
    def _reply(plan: BuildPlan, report: dict) -> str:
        if plan.recipe == "tetris":
            return (
                "作成しました。Pixelのブラウザだけで動く単一HTML版テトリスです。\n"
                "BUILD: 要求分解 → 部品構成 → HTML/JS生成 → オフライン性検証 → 機能検証 → 成果物昇格\n"
                f"検証: {', '.join(report['checks'])} / {report['bytes']} bytes\n"
                "下の fap_tetris.html を開いてください。"
            )
        return (
            "作成しました。\n"
            f"BUILD: {plan.recipe} → 検証 → 成果物昇格\n"
            f"検証: {', '.join(report['checks'])}"
        )

    @staticmethod
    def _generic_html(goal: str) -> str:
        safe = html.escape(goal[:400])
        return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FAP Artifact</title><style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 18px;line-height:1.7}}main{{border:1px solid #aaa;border-radius:16px;padding:20px}}</style></head>
<body><main><h1>FAP Generated Artifact</h1><p>{safe}</p><p>V87.04 Builder Stage 1 / offline single HTML</p></main></body></html>'''

    @staticmethod
    def _tetris_html() -> str:
        # Fully offline deterministic single-file implementation.
        return r'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>FAP Tetris</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#07110f;color:#effff6;font-family:system-ui,-apple-system,sans-serif;min-height:100vh;display:grid;place-items:center}.app{width:min(96vw,520px);padding:18px}.top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}.brand{font-weight:800;letter-spacing:.08em}.stats{display:flex;gap:12px;font-variant-numeric:tabular-nums}.board{display:grid;grid-template-columns:1fr;justify-items:center;gap:12px}canvas{background:#020807;border:1px solid #34594c;border-radius:12px;width:min(92vw,360px);height:auto;image-rendering:pixelated;box-shadow:0 14px 50px #0008}.help{font-size:13px;color:#b9d7c8;text-align:center;line-height:1.5}.controls{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;width:min(92vw,360px)}button{min-height:48px;border:1px solid #426b5b;border-radius:12px;background:#10241e;color:#effff6;font-size:18px;font-weight:700}.wide{grid-column:span 2}.gameover{color:#ffd4d4;font-weight:800;min-height:1.4em;text-align:center}</style>
</head>
<body>
<div class="app">
  <div class="top"><div class="brand">FAP TETRIS</div><div class="stats"><span>SCORE <b id="score">0</b></span><span>LINES <b id="lines">0</b></span></div></div>
  <div class="board">
    <canvas id="game" width="240" height="480" aria-label="Tetris board"></canvas>
    <div class="gameover" id="message"></div>
    <div class="controls">
      <button data-act="left">◀</button><button data-act="rotate">↻</button><button data-act="right">▶</button><button data-act="down">▼</button><button data-act="drop">⤓</button>
      <button class="wide" id="restart">RESTART</button><button class="wide" id="pause">PAUSE</button><button id="mute">♪</button>
    </div>
    <div class="help">キー: ← → 移動 / ↑ 回転 / ↓ 落下 / Space ハードドロップ / P 一時停止</div>
  </div>
</div>
<script>
'use strict';
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
const scoreEl=document.getElementById('score'),linesEl=document.getElementById('lines'),msg=document.getElementById('message');
const COLS=10,ROWS=20,SIZE=24;
const COLORS={I:'#55ddec',J:'#5477ff',L:'#ff9d3b',O:'#ffe05a',S:'#67dc79',T:'#bd6bff',Z:'#ff6262'};
const SHAPES={
 I:['....','IIII','....','....'],
 J:['J...','JJJ.','....','....'],
 L:['..L.','LLL.','....','....'],
 O:['.OO.','.OO.','....','....'],
 S:['.SS.','SS..','....','....'],
 T:['.T..','TTT.','....','....'],
 Z:['ZZ..','.ZZ.','....','....']
};
let arena,piece,score,lines,last=0,dropCounter=0,dropInterval=650,paused=false,over=false;
function matrixFor(type){return SHAPES[type].map(row=>[...row].map(c=>c==='.'?0:type))}
function newArena(){return Array.from({length:ROWS},()=>Array(COLS).fill(0))}
function randomPiece(){const keys=Object.keys(SHAPES);const type=keys[Math.floor(Math.random()*keys.length)];return {type,m:matrixFor(type),x:3,y:-1}}
function collide(a,p){for(let y=0;y<p.m.length;y++)for(let x=0;x<p.m[y].length;x++){if(!p.m[y][x])continue;const ax=x+p.x,ay=y+p.y;if(ax<0||ax>=COLS||ay>=ROWS)return true;if(ay>=0&&a[ay][ax])return true}return false}
function merge(a,p){p.m.forEach((row,y)=>row.forEach((v,x)=>{if(v&&y+p.y>=0)a[y+p.y][x+p.x]=v}))}
function rotate(m){return m[0].map((_,i)=>m.map(row=>row[i]).reverse())}
function playerRotate(){const old=piece.m,oldX=piece.x;piece.m=rotate(piece.m);for(const off of [0,-1,1,-2,2]){piece.x=oldX+off;if(!collide(arena,piece))return}piece.m=old;piece.x=oldX}
function sweep(){let gained=0,count=0;outer:for(let y=ROWS-1;y>=0;y--){for(let x=0;x<COLS;x++)if(!arena[y][x])continue outer;arena.splice(y,1);arena.unshift(Array(COLS).fill(0));y++;count++;gained+=100*Math.pow(2,count-1)}if(count){score+=gained;lines+=count;dropInterval=Math.max(120,650-lines*15);updateStats()}}
function spawn(){piece=randomPiece();if(collide(arena,piece)){over=true;msg.textContent='GAME OVER — RESTARTで再開'}}
function drop(){if(paused||over)return;piece.y++;if(collide(arena,piece)){piece.y--;merge(arena,piece);sweep();spawn()}dropCounter=0}
function hardDrop(){if(paused||over)return;let moved=0;while(!collide(arena,{...piece,y:piece.y+1})){piece.y++;moved++}score+=moved*2;updateStats();drop()}
function move(dx){if(paused||over)return;piece.x+=dx;if(collide(arena,piece))piece.x-=dx}
function updateStats(){scoreEl.textContent=score;linesEl.textContent=lines}
function drawCell(x,y,c){ctx.fillStyle=COLORS[c]||'#9cb';ctx.fillRect(x*SIZE+1,y*SIZE+1,SIZE-2,SIZE-2);ctx.fillStyle='#ffffff22';ctx.fillRect(x*SIZE+2,y*SIZE+2,SIZE-4,3)}
function draw(){ctx.fillStyle='#020807';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#18352c';ctx.lineWidth=1;for(let x=0;x<=COLS;x++){ctx.beginPath();ctx.moveTo(x*SIZE,0);ctx.lineTo(x*SIZE,ROWS*SIZE);ctx.stroke()}for(let y=0;y<=ROWS;y++){ctx.beginPath();ctx.moveTo(0,y*SIZE);ctx.lineTo(COLS*SIZE,y*SIZE);ctx.stroke()}arena.forEach((row,y)=>row.forEach((v,x)=>{if(v)drawCell(x,y,v)}));piece.m.forEach((row,y)=>row.forEach((v,x)=>{if(v&&y+piece.y>=0)drawCell(x+piece.x,y+piece.y,v)}));if(paused&&!over){ctx.fillStyle='#000a';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#fff';ctx.font='700 26px system-ui';ctx.textAlign='center';ctx.fillText('PAUSED',canvas.width/2,canvas.height/2)}}
function update(t=0){const dt=t-last;last=t;if(!paused&&!over){dropCounter+=dt;if(dropCounter>dropInterval)drop()}draw();requestAnimationFrame(update)}
function restart(){arena=newArena();score=0;lines=0;dropInterval=650;paused=false;over=false;msg.textContent='';updateStats();spawn()}
function togglePause(){if(over)return;paused=!paused;document.getElementById('pause').textContent=paused?'RESUME':'PAUSE'}
function act(name){if(name==='left')move(-1);else if(name==='right')move(1);else if(name==='rotate')playerRotate();else if(name==='down')drop();else if(name==='drop')hardDrop();draw()}
document.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' ','p','P'].includes(e.key))e.preventDefault();if(e.key==='ArrowLeft')act('left');else if(e.key==='ArrowRight')act('right');else if(e.key==='ArrowUp')act('rotate');else if(e.key==='ArrowDown')act('down');else if(e.key===' ')act('drop');else if(e.key.toLowerCase()==='p')togglePause()},{passive:false});
document.querySelectorAll('[data-act]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.act)));
document.getElementById('restart').addEventListener('click',restart);document.getElementById('pause').addEventListener('click',togglePause);document.getElementById('mute').addEventListener('click',e=>{e.currentTarget.textContent=e.currentTarget.textContent==='♪'?'×♪':'♪'});
restart();requestAnimationFrame(update);
</script>
</body>
</html>'''
