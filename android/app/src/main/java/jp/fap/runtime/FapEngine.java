package jp.fap.runtime;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.util.*;
import java.util.regex.*;

public final class FapEngine {
    public static final class Result {
        public final String query, answer, skill;
        public final double confidence;
        Result(String q, String a, String s, double c){query=q;answer=a;skill=s;confidence=c;}
    }

    private final SharedPreferences prefs;
    private final SkillGraph graph;
    private int turns;

    public FapEngine(Context c){
        prefs=c.getSharedPreferences("fap_v59", Context.MODE_PRIVATE);
        graph=new SkillGraph(prefs.getString("graph","{}"));
        turns=prefs.getInt("turns",0);
    }

    public Result process(String q){
        turns++;
        prefs.edit().putInt("turns",turns).apply();
        String lower=q.toLowerCase(Locale.ROOT).trim();
        if(lower.matches("^(true|false|not|and|or|\\(|\\)|\\s)+$")){
            try { boolean v=new BoolParser(lower).parse(); return new Result(q, String.valueOf(v), "formal_logic", .99); }
            catch(Exception ignored){}
        }
        Double ar=Arithmetic.tryEval(lower);
        if(ar!=null) return new Result(q, format(ar), "arithmetic", .98);
        if(lower.contains("fap") && (lower.contains("とは") || lower.contains("what"))){
            return new Result(q,"FAP 1.x Androidは、必要なSkillだけを選び、検証済みの成功/失敗からSkill Graphを局所更新する軽量ローカル実装です。未検証の会話は恒久学習に使いません。","knowledge_local",.90);
        }
        if(q.matches(".*(こんにちは|こんばんは|おはよう|hello|hi).*")){
            return new Result(q,"こんにちは。FAP 1.x Androidでローカル処理しています。","dialogue",.90);
        }
        String skill=graph.select(q);
        return new Result(q,"現時点の端末内Skillだけでは確定回答できません。候補Skill: "+skill+"。事実を作らず、外部Teacher/Knowledge接続待ちとして扱います。",skill,.35);
    }

    public void verify(Result r, boolean success){
        graph.record(r.query,r.skill,success);
        prefs.edit().putString("graph",graph.toJson()).apply();
    }

    public String status(){return "READY · 1.x · turns="+turns+" · learnedEdges="+graph.edgeCount();}
    public void clear(){ turns=0; graph.clear(); prefs.edit().clear().apply(); }

    private static String format(double v){ if(Math.rint(v)==v) return Long.toString((long)v); return Double.toString(v); }

    static final class SkillGraph {
        private final Map<String,int[]> stats=new HashMap<>();
        SkillGraph(String json){
            try { JSONObject o=new JSONObject(json); Iterator<String> it=o.keys(); while(it.hasNext()){String k=it.next(); JSONObject s=o.getJSONObject(k); stats.put(k,new int[]{s.optInt("ok"),s.optInt("ng")});} } catch(Exception ignored){}
        }
        String select(String q){
            String l=q.toLowerCase(Locale.ROOT);
            if(l.matches(".*[0-9].*")) return best("math","arithmetic");
            if(l.contains("code")||l.contains("java")||l.contains("python")||l.contains("バグ")) return best("coding","verification");
            if(l.contains("画像")||l.contains("screen")||l.contains("ui")) return best("vision","tool_use");
            return best("semantic","reasoning");
        }
        private String best(String a,String b){ return score(a)>=score(b)?a:b; }
        private double score(String k){int[] s=stats.get(k); if(s==null)return .5; return (s[0]+1.0)/(s[0]+s[1]+2.0);}
        void record(String q,String skill,boolean ok){
            String intent=intent(q); String edge=intent+"->"+skill; int[] s=stats.computeIfAbsent(edge,k->new int[2]); if(ok)s[0]++;else s[1]++;
            int[] ss=stats.computeIfAbsent(skill,k->new int[2]); if(ok)ss[0]++;else ss[1]++;
        }
        private String intent(String q){String l=q.toLowerCase(Locale.ROOT); if(l.matches(".*[0-9].*"))return "quant"; if(l.contains("code")||l.contains("バグ"))return "code"; if(l.contains("画像")||l.contains("ui"))return "vision"; return "general";}
        String toJson(){ JSONObject o=new JSONObject(); try{ for(Map.Entry<String,int[]>e:stats.entrySet()){JSONObject s=new JSONObject();s.put("ok",e.getValue()[0]);s.put("ng",e.getValue()[1]);o.put(e.getKey(),s);} }catch(Exception ignored){} return o.toString(); }
        int edgeCount(){return stats.size();}
        void clear(){stats.clear();}
    }

    static final class Arithmetic {
        private static final Pattern P=Pattern.compile("^\\s*(-?\\d+(?:\\.\\d+)?)\\s*([+\\-*/×÷])\\s*(-?\\d+(?:\\.\\d+)?)\\s*$");
        static Double tryEval(String s){ Matcher m=P.matcher(s); if(!m.matches())return null; double a=Double.parseDouble(m.group(1)),b=Double.parseDouble(m.group(3)); return switch(m.group(2)){case "+"->a+b;case "-"->a-b;case "*", "×"->a*b;case "/", "÷"->b==0?null:a/b;default->null;}; }
    }

    static final class BoolParser {
        private final List<String> t=new ArrayList<>(); private int p;
        BoolParser(String s){Matcher m=Pattern.compile("true|false|not|and|or|\\(|\\)").matcher(s);while(m.find())t.add(m.group());}
        boolean parse(){boolean v=or(); if(p!=t.size())throw new IllegalArgumentException();return v;}
        private boolean or(){boolean v=and();while(match("or")){boolean r=and();v=v||r;}return v;}
        private boolean and(){boolean v=unary();while(match("and")){boolean r=unary();v=v&&r;}return v;}
        private boolean unary(){if(match("not"))return !unary();if(match("(")){boolean v=or();if(!match(")"))throw new IllegalArgumentException();return v;}if(match("true"))return true;if(match("false"))return false;throw new IllegalArgumentException();}
        private boolean match(String x){if(p<t.size()&&t.get(p).equals(x)){p++;return true;}return false;}
    }
}
