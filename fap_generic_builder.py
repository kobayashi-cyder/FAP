from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import html
import json
import re

from fap_builder import ArtifactBuilder as Stage1Builder, BuilderError


@dataclass(frozen=True)
class ArtifactSpec:
    kind: str
    family: str
    target: str
    filename: str
    features: tuple[str, ...]
    missing: tuple[str, ...] = ()


class GenericCompositionBuilder:
    """FAP V87.05 local-first compositional builder.

    Natural-language create intent is kept inside Builder. Known mechanics are
    decomposed into reusable primitive features. Unknown requests fail closed as
    a Builder planning result instead of falling back to generic chat.
    """

    CREATE_RE = re.compile(r"(作って|作成(?:して|できますか|できる)?|生成(?:して)?|構築(?:して)?|build|create|make)", re.I)

    PRIMITIVES = {
        "html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
        "score", "restart", "collision.aabb", "collision.grid", "velocity",
        "paddle", "ball", "brick.grid", "snake.body", "food", "ai.follow",
        "tetris.pieces", "tetris.rotate", "tetris.clear", "json.document",
    }

    def __init__(self, artifacts_dir: Path, workspace_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self.workspace_dir = Path(workspace_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.stage1 = Stage1Builder(self.artifacts_dir, self.workspace_dir)

    @classmethod
    def is_build_request(cls, text: str) -> bool:
        return bool(cls.CREATE_RE.search(str(text or "")))

    def infer(self, text: str) -> ArtifactSpec:
        t = str(text or "").strip()
        low = t.lower()

        if re.search(r"(テトリス|tetris)", t, re.I):
            return ArtifactSpec(
                "single_html", "game", "tetris", "fap_tetris.html",
                ("html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
                 "score", "restart", "collision.grid", "tetris.pieces", "tetris.rotate", "tetris.clear"),
            )

        if re.search(r"(ブロック崩し|ブロックくずし|breakout|brick\s*breaker)", t, re.I):
            return ArtifactSpec(
                "single_html", "game", "breakout", "fap_breakout.html",
                ("html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
                 "score", "restart", "collision.aabb", "velocity", "paddle", "ball", "brick.grid"),
            )

        if re.search(r"(pong|ポン|ピンポン)", low, re.I):
            return ArtifactSpec(
                "single_html", "game", "pong", "fap_pong.html",
                ("html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
                 "score", "restart", "collision.aabb", "velocity", "paddle", "ball", "ai.follow"),
            )

        if re.search(r"(snake|スネーク|へびゲーム|蛇ゲーム)", t, re.I):
            return ArtifactSpec(
                "single_html", "game", "snake", "fap_snake.html",
                ("html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
                 "score", "restart", "collision.grid", "snake.body", "food"),
            )

        # Mechanic-first inference: no game-name template is required if mechanics are explicit.
        has_ball = bool(re.search(r"(ボール|ball)", t, re.I))
        has_paddle = bool(re.search(r"(パドル|バー|paddle)", t, re.I))
        has_bricks = bool(re.search(r"(ブロック|brick)", t, re.I))
        if has_ball and has_paddle and has_bricks:
            return ArtifactSpec(
                "single_html", "game", "breakout", "fap_composed_breakout.html",
                ("html.shell", "canvas", "game.loop", "input.keyboard", "input.touch",
                 "score", "restart", "collision.aabb", "velocity", "paddle", "ball", "brick.grid"),
            )

        if re.search(r"\bjson\b|設定ファイル", t, re.I):
            return ArtifactSpec("json", "data", "config", "fap_config.json", ("json.document",))

        if re.search(r"(html|web|ウェブ|ページ|サイト)", t, re.I):
            return ArtifactSpec("single_html", "page", "generic_page", "fap_page.html", ("html.shell",))

        if re.search(r"(ゲーム|game)", t, re.I):
            return ArtifactSpec(
                "single_html", "game", "unknown_game", "fap_game_candidate.html", (),
                ("ゲームの基本ルール", "操作方法", "勝敗または終了条件"),
            )

        # Create intent stays Builder even when the artifact family is not yet inferable.
        return ArtifactSpec(
            "unknown", "unknown", "unknown", "artifact.pending", (),
            ("成果物タイプ（HTML/JSON/ゲーム等）", "必須機能"),
        )

    def build(self, text: str) -> dict:
        spec = self.infer(text)
        if spec.missing:
            return {
                "ok": False,
                "reply": (
                    "Builderとして要求を受け取りましたが、まだ安全に成果物を確定生成できません。\n"
                    f"BUILD PLAN: target={spec.target} / family={spec.family}\n"
                    "不足: " + "、".join(spec.missing) + "\n"
                    "chatへは戻さず、このBuilder計画を保持します。"
                ),
                "confidence": 0.90,
                "build_spec": asdict(spec),
                "artifacts": [],
            }

        missing_primitives = [p for p in spec.features if p not in self.PRIMITIVES]
        if missing_primitives:
            raise BuilderError("missing primitives: " + ", ".join(missing_primitives))

        if spec.target == "tetris":
            out = self.stage1.build(text)
            out["build_spec"] = asdict(spec)
            out["reply"] = out["reply"].replace("V87.04", "V87.05")
            return out
        if spec.target == "config":
            out = self.stage1.build(text)
            out["build_spec"] = asdict(spec)
            return out
        if spec.target == "generic_page":
            out = self.stage1.build(text)
            out["build_spec"] = asdict(spec)
            return out

        if spec.target == "breakout":
            content = self._breakout_html()
        elif spec.target == "pong":
            content = self._pong_html()
        elif spec.target == "snake":
            content = self._snake_html()
        else:
            raise BuilderError("unsupported composition target")

        candidate = self.workspace_dir / spec.filename
        candidate.write_text(content, encoding="utf-8")
        report = self.validate(spec, candidate)
        if not report["ok"]:
            raise BuilderError("validation failed: " + "; ".join(report["errors"]))

        final = self.artifacts_dir / spec.filename
        final.write_bytes(candidate.read_bytes())
        digest = sha256(final.read_bytes()).hexdigest()
        return {
            "ok": True,
            "reply": (
                f"作成しました。{self._label(spec.target)}をPrimitiveから構成した単一HTMLです。\n"
                "BUILD: 意図 → Feature分解 → Primitive選択 → Composition → 構造検証 → 成果物昇格\n"
                f"features: {', '.join(spec.features)}\n"
                f"検証: {', '.join(report['checks'])} / {report['bytes']} bytes\n"
                f"下の {spec.filename} を開いてください。"
            ),
            "confidence": 0.97,
            "build_spec": asdict(spec),
            "validation": report,
            "artifacts": [{
                "type": "file",
                "src": f"/artifacts/{spec.filename}",
                "name": spec.filename,
                "sha256": digest,
                "mime": "text/html",
            }],
        }

    @staticmethod
    def _label(target: str) -> str:
        return {"breakout": "ブロック崩し", "pong": "PONG", "snake": "Snake"}.get(target, target)

    def validate(self, spec: ArtifactSpec, path: Path) -> dict:
        errors: list[str] = []
        checks: list[str] = []
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        low = text.lower()

        if len(raw) > 300_000:
            errors.append("artifact exceeds 300KB")
        else:
            checks.append("size_limit")
        if "<!doctype html>" not in low or "<canvas" not in low or "</html>" not in low:
            errors.append("HTML/canvas shell incomplete")
        else:
            checks.append("single_file_canvas")
        if re.search(r"<(?:script|link)[^>]+(?:src|href)\s*=\s*[\"']https?://", text, re.I):
            errors.append("external dependency detected")
        else:
            checks.append("offline")
        if text.count("<script") != text.count("</script>"):
            errors.append("script tag imbalance")
        else:
            checks.append("script_structure")

        required = {
            "breakout": ["const bricks", "function resetBall", "function update", "function draw", "paddle", "score"],
            "pong": ["function resetBall", "function update", "function draw", "leftPaddle", "rightPaddle", "s1.textContent"],
            "snake": ["let snake", "food", "function update", "function draw", "score", "keydown"],
        }.get(spec.target, [])
        missing = [needle for needle in required if needle not in text]
        if missing:
            errors.append("missing mechanics: " + ", ".join(missing))
        else:
            checks.append("mechanics")

        return {"ok": not errors, "checks": checks, "errors": errors, "bytes": len(raw)}

    @staticmethod
    def _shell(title: str, body: str, script: str) -> str:
        title_e = html.escape(title)
        return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title_e}</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#07110f;color:#effff6;font-family:system-ui,-apple-system,sans-serif;min-height:100vh;display:grid;place-items:center}}.app{{width:min(96vw,520px);padding:16px}}h1{{font-size:18px;margin:0 0 10px}}.stats{{display:flex;justify-content:space-between;margin:8px 0;font-variant-numeric:tabular-nums}}canvas{{display:block;background:#020807;border:1px solid #34594c;border-radius:12px;width:min(92vw,420px);height:auto;margin:auto;touch-action:none}}.controls{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px auto 0;width:min(92vw,420px)}}button{{min-height:48px;border:1px solid #426b5b;border-radius:12px;background:#10241e;color:#effff6;font-size:18px;font-weight:700}}.msg{{min-height:1.5em;text-align:center;color:#ffd7a8;margin-top:8px}}.hint{{font-size:12px;color:#b9d7c8;text-align:center;margin-top:10px}}</style></head>
<body><main class="app"><h1>{title_e}</h1>{body}</main><script>{script}</script></body></html>'''

    @classmethod
    def _breakout_html(cls) -> str:
        body = '''<div class="stats"><span>SCORE <b id="score">0</b></span><span>LIVES <b id="lives">3</b></span></div><canvas id="game" width="420" height="560"></canvas><div class="msg" id="msg"></div><div class="controls"><button id="left">◀</button><button id="right">▶</button><button id="start">START</button><button id="restart">↻</button></div><div class="hint">← → / 画面ボタンで移動。ブロックを全て消すとクリア。</div>'''
        script = r'''
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
const scoreEl=document.getElementById('score'),livesEl=document.getElementById('lives'),msg=document.getElementById('msg');
const paddle={x:160,y:520,w:100,h:14,speed:7};
const ball={x:210,y:490,r:8,vx:4,vy:-4};
const bricks=[]; const ROWS=6,COLS=7,BW=50,BH=18,GAP=6,OX=17,OY=55;
let score=0,lives=3,running=false,left=false,right=false;
function makeBricks(){bricks.length=0;for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++)bricks.push({x:OX+c*(BW+GAP),y:OY+r*(BH+GAP),w:BW,h:BH,alive:true});}
function resetBall(){ball.x=canvas.width/2;ball.y=490;ball.vx=(Math.random()>.5?1:-1)*4;ball.vy=-4;paddle.x=(canvas.width-paddle.w)/2;}
function restartGame(){score=0;lives=3;scoreEl.textContent=score;livesEl.textContent=lives;msg.textContent='';makeBricks();resetBall();running=false;draw();}
function hitRectCircle(o,b){return b.x+b.r>o.x&&b.x-b.r<o.x+o.w&&b.y+b.r>o.y&&b.y-b.r<o.y+o.h;}
function update(){if(!running)return;if(left)paddle.x-=paddle.speed;if(right)paddle.x+=paddle.speed;paddle.x=Math.max(0,Math.min(canvas.width-paddle.w,paddle.x));ball.x+=ball.vx;ball.y+=ball.vy;if(ball.x-ball.r<0||ball.x+ball.r>canvas.width)ball.vx*=-1;if(ball.y-ball.r<0)ball.vy*=-1;if(hitRectCircle(paddle,ball)&&ball.vy>0){ball.vy=-Math.abs(ball.vy);ball.vx+=(ball.x-(paddle.x+paddle.w/2))*0.025;}for(const b of bricks){if(b.alive&&hitRectCircle(b,ball)){b.alive=false;ball.vy*=-1;score+=10;scoreEl.textContent=score;break;}}if(bricks.every(b=>!b.alive)){running=false;msg.textContent='CLEAR!';}if(ball.y-ball.r>canvas.height){lives--;livesEl.textContent=lives;if(lives<=0){running=false;msg.textContent='GAME OVER';}else resetBall();}}
function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#98f5c3';ctx.fillRect(paddle.x,paddle.y,paddle.w,paddle.h);ctx.beginPath();ctx.arc(ball.x,ball.y,ball.r,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();for(const b of bricks){if(!b.alive)continue;ctx.fillStyle=`hsl(${140+(b.y-OY)*1.2} 70% 58%)`;ctx.fillRect(b.x,b.y,b.w,b.h);} }
function loop(){update();draw();requestAnimationFrame(loop);}loop();restartGame();
addEventListener('keydown',e=>{if(e.key==='ArrowLeft')left=true;if(e.key==='ArrowRight')right=true;if(e.key===' '){running=true;msg.textContent='';}});addEventListener('keyup',e=>{if(e.key==='ArrowLeft')left=false;if(e.key==='ArrowRight')right=false;});
function bindHold(id,key){const el=document.getElementById(id);const on=e=>{e.preventDefault();if(key==='left')left=true;else right=true;};const off=e=>{e.preventDefault();if(key==='left')left=false;else right=false;};el.addEventListener('pointerdown',on);el.addEventListener('pointerup',off);el.addEventListener('pointercancel',off);el.addEventListener('pointerleave',off);}bindHold('left','left');bindHold('right','right');
document.getElementById('start').onclick=()=>{running=true;msg.textContent='';};document.getElementById('restart').onclick=restartGame;
canvas.addEventListener('pointermove',e=>{const r=canvas.getBoundingClientRect();paddle.x=(e.clientX-r.left)*canvas.width/r.width-paddle.w/2;});
'''
        return cls._shell("FAP BLOCK BREAKER", body, script)

    @classmethod
    def _pong_html(cls) -> str:
        body = '''<div class="stats"><span>YOU <b id="s1">0</b></span><span>CPU <b id="s2">0</b></span></div><canvas id="game" width="420" height="560"></canvas><div class="msg" id="msg"></div><div class="controls"><button id="up">▲</button><button id="down">▼</button><button id="start">START</button><button id="restart">↻</button></div><div class="hint">↑ ↓ で左パドル。右はFAP簡易AI。</div>'''
        script = r'''
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d'),s1=document.getElementById('s1'),s2=document.getElementById('s2'),msg=document.getElementById('msg');
const leftPaddle={x:20,y:230,w:14,h:100},rightPaddle={x:386,y:230,w:14,h:100};const ball={x:210,y:280,r:8,vx:4,vy:3};let a=0,b=0,up=false,down=false,running=false;
function resetBall(dir=1){ball.x=210;ball.y=280;ball.vx=4*dir;ball.vy=(Math.random()*4-2)||2;}
function restartGame(){a=b=0;s1.textContent=a;s2.textContent=b;leftPaddle.y=rightPaddle.y=230;resetBall();running=false;msg.textContent='';draw();}
function hit(p){return ball.x+ball.r>p.x&&ball.x-ball.r<p.x+p.w&&ball.y+ball.r>p.y&&ball.y-ball.r<p.y+p.h;}
function update(){if(!running)return;if(up)leftPaddle.y-=7;if(down)leftPaddle.y+=7;leftPaddle.y=Math.max(0,Math.min(canvas.height-leftPaddle.h,leftPaddle.y));rightPaddle.y+=(ball.y-(rightPaddle.y+rightPaddle.h/2))*.055;rightPaddle.y=Math.max(0,Math.min(canvas.height-rightPaddle.h,rightPaddle.y));ball.x+=ball.vx;ball.y+=ball.vy;if(ball.y-ball.r<0||ball.y+ball.r>canvas.height)ball.vy*=-1;if(hit(leftPaddle)&&ball.vx<0)ball.vx=Math.abs(ball.vx);if(hit(rightPaddle)&&ball.vx>0)ball.vx=-Math.abs(ball.vx);if(ball.x<0){b++;s2.textContent=b;resetBall(1);}if(ball.x>canvas.width){a++;s1.textContent=a;resetBall(-1);}if(a>=7||b>=7){running=false;msg.textContent=a>b?'YOU WIN':'CPU WIN';}}
function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#34594c';ctx.setLineDash([8,8]);ctx.beginPath();ctx.moveTo(210,0);ctx.lineTo(210,560);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#98f5c3';ctx.fillRect(leftPaddle.x,leftPaddle.y,leftPaddle.w,leftPaddle.h);ctx.fillRect(rightPaddle.x,rightPaddle.y,rightPaddle.w,rightPaddle.h);ctx.beginPath();ctx.arc(ball.x,ball.y,ball.r,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();}
function loop(){update();draw();requestAnimationFrame(loop)}loop();restartGame();addEventListener('keydown',e=>{if(e.key==='ArrowUp')up=true;if(e.key==='ArrowDown')down=true;if(e.key===' ')running=true});addEventListener('keyup',e=>{if(e.key==='ArrowUp')up=false;if(e.key==='ArrowDown')down=false});
function bind(id,key){const el=document.getElementById(id);el.onpointerdown=e=>{e.preventDefault();key==='up'?up=true:down=true};el.onpointerup=el.onpointercancel=()=>{key==='up'?up=false:down=false}}bind('up','up');bind('down','down');document.getElementById('start').onclick=()=>running=true;document.getElementById('restart').onclick=restartGame;
'''
        return cls._shell("FAP PONG", body, script)

    @classmethod
    def _snake_html(cls) -> str:
        body = '''<div class="stats"><span>SCORE <b id="score">0</b></span><span>BEST <b id="best">0</b></span></div><canvas id="game" width="400" height="400"></canvas><div class="msg" id="msg"></div><div class="controls"><button id="up">▲</button><button id="left">◀</button><button id="right">▶</button><button id="down">▼</button></div><div class="controls"><button id="restart" style="grid-column:1/5">RESTART</button></div><div class="hint">矢印キーまたはボタンで操作。</div>'''
        script = r'''
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d'),scoreEl=document.getElementById('score'),bestEl=document.getElementById('best'),msg=document.getElementById('msg');const N=20,S=20;let snake,food,dir,next,score,best=0,timer;
function spawn(){do{food={x:Math.floor(Math.random()*N),y:Math.floor(Math.random()*N)}}while(snake.some(p=>p.x===food.x&&p.y===food.y));}
function restart(){snake=[{x:10,y:10},{x:9,y:10},{x:8,y:10}];dir={x:1,y:0};next=dir;score=0;scoreEl.textContent=0;msg.textContent='';spawn();clearInterval(timer);timer=setInterval(update,110);draw();}
function setDir(x,y){if(x===-dir.x&&y===-dir.y)return;next={x,y};}
function update(){dir=next;const h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};if(h.x<0||h.x>=N||h.y<0||h.y>=N||snake.some(p=>p.x===h.x&&p.y===h.y)){clearInterval(timer);msg.textContent='GAME OVER';best=Math.max(best,score);bestEl.textContent=best;return;}snake.unshift(h);if(h.x===food.x&&h.y===food.y){score++;scoreEl.textContent=score;spawn();}else snake.pop();draw();}
function draw(){ctx.clearRect(0,0,400,400);ctx.fillStyle='#98f5c3';for(const p of snake)ctx.fillRect(p.x*S+1,p.y*S+1,S-2,S-2);ctx.fillStyle='#ffb3a7';ctx.fillRect(food.x*S+2,food.y*S+2,S-4,S-4);}
addEventListener('keydown',e=>{if(e.key==='ArrowUp')setDir(0,-1);if(e.key==='ArrowDown')setDir(0,1);if(e.key==='ArrowLeft')setDir(-1,0);if(e.key==='ArrowRight')setDir(1,0)});for(const [id,x,y] of [['up',0,-1],['down',0,1],['left',-1,0],['right',1,0]])document.getElementById(id).onclick=()=>setDir(x,y);document.getElementById('restart').onclick=restart;restart();
'''
        return cls._shell("FAP SNAKE", body, script)
