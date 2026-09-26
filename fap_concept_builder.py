from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import re

from fap_builder import BuilderError
from fap_generic_builder import ArtifactSpec, GenericCompositionBuilder


@dataclass(frozen=True)
class ConceptRule:
    target: str
    label: str
    aliases: tuple[str, ...]
    mechanics: tuple[str, ...]
    features: tuple[str, ...]
    filename: str


class ConceptMechanismBuilder(GenericCompositionBuilder):
    """FAP V87.06 Concept-to-Mechanism Builder.

    The builder resolves a requested artifact into a compact concept rule, then
    decomposes that concept into mechanics/primitives. It remains local-first:
    no external LLM is required. Unknown build requests stay inside Builder and
    return a question plan instead of silently falling back to chat.
    """

    EXTRA_PRIMITIVES = {
        "grid.cells", "hazard.random", "neighbor.count", "reveal.flood",
        "flag.mode", "winlose", "tile.compress", "tile.merge", "tile.spawn",
        "input.swipe", "card.deck", "card.flip", "pair.match", "turn.lock",
    }
    PRIMITIVES = set(GenericCompositionBuilder.PRIMITIVES) | EXTRA_PRIMITIVES

    CONCEPTS = (
        ConceptRule(
            target="minesweeper",
            label="マインスイーパー",
            aliases=("マインスイーパー", "minesweeper", "mine sweeper"),
            mechanics=("地雷", "周囲", "数字", "マス", "開け", "旗", "mine", "neighbor", "flag"),
            features=(
                "html.shell", "grid.cells", "hazard.random", "neighbor.count",
                "reveal.flood", "flag.mode", "winlose", "restart", "input.touch",
            ),
            filename="fap_minesweeper.html",
        ),
        ConceptRule(
            target="2048",
            label="2048",
            aliases=("2048", "にせんよんじゅうはち"),
            mechanics=("同じ数字", "タイル", "スライド", "合体", "結合", "4x4", "4×4", "swipe", "merge"),
            features=(
                "html.shell", "grid.cells", "tile.compress", "tile.merge",
                "tile.spawn", "input.keyboard", "input.swipe", "score", "restart", "winlose",
            ),
            filename="fap_2048.html",
        ),
        ConceptRule(
            target="memory_match",
            label="神経衰弱",
            aliases=("神経衰弱", "memory game", "memory match", "絵合わせ"),
            mechanics=("カード", "ペア", "めく", "一致", "同じ絵", "記憶", "card", "pair", "match"),
            features=(
                "html.shell", "grid.cells", "card.deck", "card.flip", "pair.match",
                "turn.lock", "score", "restart", "input.touch", "winlose",
            ),
            filename="fap_memory_match.html",
        ),
    )

    def _score_concepts(self, text: str) -> list[tuple[float, ConceptRule, list[str]]]:
        t = str(text or "").lower()
        ranked: list[tuple[float, ConceptRule, list[str]]] = []
        for rule in self.CONCEPTS:
            score = 0.0
            hits: list[str] = []
            for alias in rule.aliases:
                if alias.lower() in t:
                    score += 6.0
                    hits.append(alias)
            for mech in rule.mechanics:
                if mech.lower() in t:
                    score += 1.0
                    hits.append(mech)
            if score:
                ranked.append((score, rule, hits))
        ranked.sort(key=lambda x: (-x[0], x[1].target))
        return ranked

    def resolve_concept(self, text: str) -> dict:
        ranked = self._score_concepts(text)
        if not ranked:
            return {"resolved": False, "target": None, "score": 0.0, "hits": []}
        score, rule, hits = ranked[0]
        # Named aliases resolve immediately. Mechanic-only requests require >=3 hits.
        named = any(a.lower() in str(text).lower() for a in rule.aliases)
        resolved = named or len(set(hits)) >= 3
        return {
            "resolved": resolved,
            "target": rule.target if resolved else None,
            "score": score,
            "hits": hits,
            "candidates": [
                {"target": r.target, "score": s, "hits": h}
                for s, r, h in ranked[:3]
            ],
        }

    def infer(self, text: str) -> ArtifactSpec:
        resolved = self.resolve_concept(text)
        if resolved["resolved"]:
            rule = next(r for r in self.CONCEPTS if r.target == resolved["target"])
            return ArtifactSpec(
                "single_html", "game", rule.target, rule.filename, rule.features
            )

        base = super().infer(text)
        if base.target == "unknown_game":
            return ArtifactSpec(
                "single_html", "game", "unknown_game", base.filename, (),
                (
                    "盤面・フィールドの形（例: グリッド/自由移動）",
                    "プレイヤーが行う操作（タップ/スワイプ/キー等）",
                    "勝利・失敗・終了条件",
                ),
            )
        return base

    def build(self, text: str) -> dict:
        spec = self.infer(text)
        concept = self.resolve_concept(text)

        if spec.missing:
            questions = [f"{i+1}. {x}" for i, x in enumerate(spec.missing)]
            return {
                "ok": False,
                "reply": (
                    "Builderとして要求を保持しています。概念を安全に機構へ分解するため、次の最小情報が必要です。\n"
                    + "\n".join(questions)
                    + "\n回答後は同じBuilder計画を継続します。chatへは戻しません。"
                ),
                "confidence": 0.92,
                "build_spec": asdict(spec),
                "concept_resolution": concept,
                "artifacts": [],
            }

        if spec.target not in {"minesweeper", "2048", "memory_match"}:
            out = super().build(text)
            out["concept_resolution"] = concept
            return out

        missing_primitives = [p for p in spec.features if p not in self.PRIMITIVES]
        if missing_primitives:
            raise BuilderError("missing primitives: " + ", ".join(missing_primitives))

        if spec.target == "minesweeper":
            content = self._minesweeper_html()
        elif spec.target == "2048":
            content = self._game2048_html()
        else:
            content = self._memory_match_html()

        candidate = self.workspace_dir / spec.filename
        candidate.write_text(content, encoding="utf-8")
        report = self.validate_concept(spec, candidate)
        if not report["ok"]:
            raise BuilderError("validation failed: " + "; ".join(report["errors"]))

        final = self.artifacts_dir / spec.filename
        final.write_bytes(candidate.read_bytes())
        digest = sha256(final.read_bytes()).hexdigest()
        label = next(r.label for r in self.CONCEPTS if r.target == spec.target)
        return {
            "ok": True,
            "reply": (
                f"作成しました。{label}を概念→機構→Primitiveへ分解して構成しました。\n"
                "BUILD: Concept Resolver → Mechanism decomposition → Primitive selection → Composition → Verification → Artifact\n"
                f"mechanisms: {', '.join(spec.features)}\n"
                f"concept hits: {', '.join(concept.get('hits', [])) or 'mechanic inference'}\n"
                f"検証: {', '.join(report['checks'])} / {report['bytes']} bytes\n"
                f"下の {spec.filename} を開いてください。"
            ),
            "confidence": 0.98,
            "build_spec": asdict(spec),
            "concept_resolution": concept,
            "validation": report,
            "artifacts": [{
                "type": "file",
                "src": f"/artifacts/{spec.filename}",
                "name": spec.filename,
                "sha256": digest,
                "mime": "text/html",
            }],
        }

    def validate_concept(self, spec: ArtifactSpec, path: Path) -> dict:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        low = text.lower()
        checks: list[str] = []
        errors: list[str] = []
        if len(raw) <= 300_000:
            checks.append("size_limit")
        else:
            errors.append("artifact exceeds 300KB")
        if "<!doctype html>" in low and "</html>" in low and "<script" in low:
            checks.append("single_file_html")
        else:
            errors.append("HTML shell incomplete")
        if not re.search(r"<(?:script|link)[^>]+(?:src|href)\s*=\s*[\"']https?://", text, re.I):
            checks.append("offline")
        else:
            errors.append("external dependency detected")
        if text.count("<script") == text.count("</script>"):
            checks.append("script_structure")
        else:
            errors.append("script tag imbalance")
        required = {
            "minesweeper": ["MINES", "function reveal", "function neighbors", "flagMode", "function reset"],
            "2048": ["function slide", "function spawn", "function mergeLine", "function reset", "touchstart"],
            "memory_match": ["function flip", "matched", "lock", "function reset", "cards"],
        }[spec.target]
        missing = [x for x in required if x not in text]
        if missing:
            errors.append("missing mechanics: " + ", ".join(missing))
        else:
            checks.append("mechanics")
        return {"ok": not errors, "checks": checks, "errors": errors, "bytes": len(raw)}

    @staticmethod
    def _base_style() -> str:
        return """
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#07110f;color:#effff6;font-family:system-ui,-apple-system,sans-serif;min-height:100vh;display:grid;place-items:center}.app{width:min(96vw,560px);padding:16px}h1{font-size:20px;margin:0 0 10px}.bar{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:8px 0}button{border:1px solid #34544d;background:#10251f;color:#effff6;border-radius:12px;padding:10px 14px;font-weight:700}.small{opacity:.75;font-size:13px}.msg{min-height:24px;margin:8px 0;font-weight:700}
"""

    @classmethod
    def _minesweeper_html(cls) -> str:
        return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>FAP Minesweeper</title><style>{cls._base_style()}
#grid{{display:grid;grid-template-columns:repeat(10,1fr);gap:3px;touch-action:manipulation}}.cell{{aspect-ratio:1;border:0;border-radius:6px;background:#17352d;color:#fff;padding:0;font-size:clamp(12px,4vw,20px)}}.cell.open{{background:#dcebe5;color:#08251d}}.cell.mine{{background:#7b2424}}.cell.flag{{background:#5b4b16}}
</style></head><body><main class="app"><h1>FAP Minesweeper</h1><div class="bar"><span id="stats"></span><button id="flagBtn">🚩 FLAG: OFF</button><button id="resetBtn">再スタート</button></div><div id="msg" class="msg"></div><div id="grid"></div><p class="small">タップで開く。FLAGをONにすると旗を置けます。</p></main><script>
const W=10,H=10,MINES=15;let board=[],opened=0,flagMode=false,over=false,first=true;const grid=document.getElementById('grid'),msg=document.getElementById('msg'),stats=document.getElementById('stats'),flagBtn=document.getElementById('flagBtn');
function neighbors(i){{const x=i%W,y=Math.floor(i/W),a=[];for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){{if(!dx&&!dy)continue;const nx=x+dx,ny=y+dy;if(nx>=0&&nx<W&&ny>=0&&ny<H)a.push(ny*W+nx)}}return a}}
function plant(safe){{let n=0;while(n<MINES){{const i=Math.floor(Math.random()*W*H);if(i===safe||neighbors(safe).includes(i)||board[i].mine)continue;board[i].mine=true;n++}}for(let i=0;i<board.length;i++)board[i].count=neighbors(i).filter(j=>board[j].mine).length}}
function render(){{grid.innerHTML='';board.forEach((c,i)=>{{const b=document.createElement('button');b.className='cell'+(c.open?' open':'')+(c.flag?' flag':'')+(c.open&&c.mine?' mine':'');b.textContent=c.flag?'🚩':c.open?(c.mine?'💣':(c.count||'')):'';b.onclick=()=>tap(i);grid.appendChild(b)}});stats.textContent=`OPEN ${{opened}}/${{W*H-MINES}}`;flagBtn.textContent=`🚩 FLAG: ${{flagMode?'ON':'OFF'}}`}}
function reveal(start){{const q=[start],seen=new Set;while(q.length){{const i=q.shift();if(seen.has(i))continue;seen.add(i);const c=board[i];if(c.open||c.flag)continue;c.open=true;opened++;if(c.count===0&&!c.mine)neighbors(i).forEach(j=>q.push(j))}}}}
function tap(i){{if(over)return;const c=board[i];if(flagMode){{if(!c.open)c.flag=!c.flag;render();return}}if(c.flag)return;if(first){{plant(i);first=false}}if(c.mine){{c.open=true;over=true;board.forEach(x=>{{if(x.mine)x.open=true}});msg.textContent='GAME OVER';render();return}}reveal(i);if(opened>=W*H-MINES){{over=true;msg.textContent='CLEAR!'}}render()}}
function reset(){{board=Array.from({{length:W*H}},()=>({{mine:false,count:0,open:false,flag:false}}));opened=0;over=false;first=true;msg.textContent='';render()}}
flagBtn.onclick=()=>{{flagMode=!flagMode;render()}};document.getElementById('resetBtn').onclick=reset;reset();
</script></body></html>'''

    @classmethod
    def _game2048_html(cls) -> str:
        return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>FAP 2048</title><style>{cls._base_style()}
#grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:#10251f;padding:8px;border-radius:16px;touch-action:none}}.tile{{aspect-ratio:1;display:grid;place-items:center;background:#17352d;border-radius:12px;font-size:clamp(20px,8vw,34px);font-weight:900}}.keys{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}}.keys button{{font-size:22px}}
</style></head><body><main class="app"><h1>FAP 2048</h1><div class="bar"><span id="score"></span><button id="resetBtn">再スタート</button></div><div id="msg" class="msg"></div><div id="grid"></div><div class="keys"><span></span><button data-d="up">↑</button><span></span><button data-d="left">←</button><button data-d="down">↓</button><button data-d="right">→</button></div></main><script>
let cells=[],score=0;const grid=document.getElementById('grid'),scoreEl=document.getElementById('score'),msg=document.getElementById('msg');
function spawn(){{const empty=cells.map((v,i)=>v?null:i).filter(v=>v!==null);if(!empty.length)return;const i=empty[Math.floor(Math.random()*empty.length)];cells[i]=Math.random()<.9?2:4}}
function mergeLine(a){{let x=a.filter(Boolean),out=[];for(let i=0;i<x.length;i++){{if(x[i]===x[i+1]){{out.push(x[i]*2);score+=x[i]*2;i++}}else out.push(x[i])}}while(out.length<4)out.push(0);return out}}
function getLine(n,dir){{let a=[];for(let k=0;k<4;k++){{let r,c;if(dir==='left'){{r=n;c=k}}if(dir==='right'){{r=n;c=3-k}}if(dir==='up'){{r=k;c=n}}if(dir==='down'){{r=3-k;c=n}}a.push(cells[r*4+c])}}return a}}
function setLine(n,dir,a){{for(let k=0;k<4;k++){{let r,c;if(dir==='left'){{r=n;c=k}}if(dir==='right'){{r=n;c=3-k}}if(dir==='up'){{r=k;c=n}}if(dir==='down'){{r=3-k;c=n}}cells[r*4+c]=a[k]}}}}
function slide(dir){{const before=cells.join(',');for(let n=0;n<4;n++)setLine(n,dir,mergeLine(getLine(n,dir)));if(cells.join(',')!==before)spawn();render();check()}}
function check(){{if(cells.some(v=>v>=2048))msg.textContent='2048!';else if(!cells.includes(0)&&!['left','right','up','down'].some(d=>{{const save=[...cells],s=score;for(let n=0;n<4;n++)setLine(n,d,mergeLine(getLine(n,d)));const changed=cells.join(',')!==save.join(',');cells=save;score=s;return changed}}))msg.textContent='GAME OVER'}}
function render(){{grid.innerHTML='';cells.forEach(v=>{{const d=document.createElement('div');d.className='tile';d.textContent=v||'';if(v)d.style.filter=`brightness(${{1+Math.min(1.2,Math.log2(v)/14)}})`;grid.appendChild(d)}});scoreEl.textContent='SCORE '+score}}
function reset(){{cells=Array(16).fill(0);score=0;msg.textContent='';spawn();spawn();render()}}
document.addEventListener('keydown',e=>{{const m={{ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down'}}[e.key];if(m){{e.preventDefault();slide(m)}}}});document.querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>slide(b.dataset.d));let sx=0,sy=0;grid.addEventListener('touchstart',e=>{{sx=e.touches[0].clientX;sy=e.touches[0].clientY}},{{passive:true}});grid.addEventListener('touchend',e=>{{const dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.max(Math.abs(dx),Math.abs(dy))<20)return;slide(Math.abs(dx)>Math.abs(dy)?(dx>0?'right':'left'):(dy>0?'down':'up'))}},{{passive:true}});document.getElementById('resetBtn').onclick=reset;reset();
</script></body></html>'''

    @classmethod
    def _memory_match_html(cls) -> str:
        return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>FAP Memory Match</title><style>{cls._base_style()}
#grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}.card{{aspect-ratio:1;border:0;border-radius:12px;background:#17352d;color:white;font-size:clamp(24px,9vw,42px)}}.card.matched{{background:#184d35}}
</style></head><body><main class="app"><h1>FAP 神経衰弱</h1><div class="bar"><span id="score"></span><button id="resetBtn">再スタート</button></div><div id="msg" class="msg"></div><div id="grid"></div></main><script>
const icons=['🍎','🍋','🍇','🍒','⭐','🌙','🐶','🐱'];let cards=[],open=[],matched=new Set(),lock=false,turns=0;const grid=document.getElementById('grid'),score=document.getElementById('score'),msg=document.getElementById('msg');
function shuffle(a){{for(let i=a.length-1;i>0;i--){{const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}}return a}}
function render(){{grid.innerHTML='';cards.forEach((v,i)=>{{const b=document.createElement('button');b.className='card'+(matched.has(i)?' matched':'');b.textContent=open.includes(i)||matched.has(i)?v:'?';b.onclick=()=>flip(i);grid.appendChild(b)}});score.textContent='TURNS '+turns}}
function flip(i){{if(lock||matched.has(i)||open.includes(i))return;open.push(i);render();if(open.length===2){{turns++;const [a,b]=open;if(cards[a]===cards[b]){{matched.add(a);matched.add(b);open=[];if(matched.size===cards.length)msg.textContent='CLEAR!';render()}}else{{lock=true;setTimeout(()=>{{open=[];lock=false;render()}},650)}}}}}}
function reset(){{cards=shuffle([...icons,...icons]);open=[];matched=new Set();lock=false;turns=0;msg.textContent='';render()}}
document.getElementById('resetBtn').onclick=reset;reset();
</script></body></html>'''
