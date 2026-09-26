package jp.fap.runtime;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

public final class FapTimelineView extends ScrollView {
    public interface ReplyListener {
        void onReplyRequested(ChatLogStore.Entry entry);
    }

    public interface ThreadListener {
        void onThreadRequested(ChatLogStore.Entry entry);
    }

    private final LinearLayout feed;
    private ReplyListener replyListener;
    private ThreadListener threadListener;

    public FapTimelineView(Context context) {
        super(context);
        setFillViewport(true);
        setBackgroundColor(Color.WHITE);
        setVerticalScrollBarEnabled(true);

        feed = new LinearLayout(context);
        feed.setOrientation(LinearLayout.VERTICAL);
        feed.setBackgroundColor(Color.WHITE);
        addView(feed, new ScrollView.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT));
    }

    public void setReplyListener(ReplyListener listener) {
        replyListener = listener;
    }

    public void setThreadListener(ThreadListener listener) {
        threadListener = listener;
    }

    public void render(List<ChatLogStore.Entry> entries) {
        feed.removeAllViews();
        if (entries == null || entries.isEmpty()) {
            TextView empty = new TextView(getContext());
            empty.setText("まだ投稿はありません。");
            empty.setTextSize(16f);
            empty.setTextColor(Color.rgb(83, 100, 113));
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(24), dp(72), dp(24), dp(72));
            feed.addView(empty, new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    LayoutParams.WRAP_CONTENT));
            return;
        }

        for (ChatLogStore.Entry entry : entries) {
            feed.addView(post(entry), new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    LayoutParams.WRAP_CONTENT));
        }
        post(() -> fullScroll(FOCUS_DOWN));
    }

    private View post(ChatLogStore.Entry entry) {
        LinearLayout outer = new LinearLayout(getContext());
        outer.setOrientation(LinearLayout.HORIZONTAL);
        outer.setPadding(dp(14), dp(12), dp(14), dp(12));
        outer.setBackgroundColor(
                ChatLogStore.SURFACE_BACK.equals(entry.surface)
                        ? Color.rgb(247, 249, 249)
                        : Color.WHITE);

        TextView avatar = new TextView(getContext());
        avatar.setText(avatarText(entry));
        avatar.setGravity(Gravity.CENTER);
        avatar.setTextSize(16f);
        avatar.setTypeface(Typeface.DEFAULT_BOLD);
        avatar.setTextColor(avatarTextColor(entry));
        avatar.setBackground(circle(avatarBackground(entry)));
        LinearLayout.LayoutParams avatarParams = new LinearLayout.LayoutParams(dp(42), dp(42));
        avatarParams.setMargins(0, 0, dp(10), 0);
        outer.addView(avatar, avatarParams);

        LinearLayout body = new LinearLayout(getContext());
        body.setOrientation(LinearLayout.VERTICAL);
        outer.addView(body, new LinearLayout.LayoutParams(
                0,
                LayoutParams.WRAP_CONTENT,
                1f));

        LinearLayout meta = new LinearLayout(getContext());
        meta.setOrientation(LinearLayout.HORIZONTAL);
        meta.setGravity(Gravity.CENTER_VERTICAL);

        TextView name = new TextView(getContext());
        name.setText(actorName(entry));
        name.setTextSize(15f);
        name.setTextColor(Color.rgb(15, 20, 25));
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setSingleLine(true);
        meta.addView(name, new LinearLayout.LayoutParams(
                LayoutParams.WRAP_CONTENT,
                LayoutParams.WRAP_CONTENT));

        TextView handle = new TextView(getContext());
        handle.setText("  " + actorHandle(entry) + " · " + relativeTime(entry.timestampMs));
        handle.setTextSize(13f);
        handle.setTextColor(Color.rgb(83, 100, 113));
        handle.setSingleLine(true);
        handle.setEllipsize(TextUtils.TruncateAt.END);
        meta.addView(handle, new LinearLayout.LayoutParams(
                0,
                LayoutParams.WRAP_CONTENT,
                1f));

        if (ChatLogStore.SURFACE_BACK.equals(entry.surface)) {
            TextView back = new TextView(getContext());
            back.setText(" 裏 ");
            back.setTextSize(11f);
            back.setTextColor(Color.rgb(83, 100, 113));
            back.setGravity(Gravity.CENTER);
            GradientDrawable badge = new GradientDrawable();
            badge.setColor(Color.rgb(239, 243, 244));
            badge.setCornerRadius(dp(999));
            back.setBackground(badge);
            meta.addView(back, new LinearLayout.LayoutParams(
                    LayoutParams.WRAP_CONTENT,
                    dp(24)));
        }

        body.addView(meta);

        if (entry.replyToId > 0L) {
            TextView replyContext = new TextView(getContext());
            replyContext.setText("↪ #" + entry.replyToId + " への返信"
                    + (entry.threadRootId > 0L
                        ? " · thread #" + entry.threadRootId
                        : ""));
            replyContext.setTextSize(12f);
            replyContext.setTextColor(Color.rgb(83, 100, 113));
            replyContext.setPadding(0, dp(4), 0, 0);
            body.addView(replyContext);
        }

        TextView text = new TextView(getContext());
        text.setText(entry.text);
        text.setTextSize(16f);
        text.setTextColor(Color.rgb(15, 20, 25));
        text.setLineSpacing(0f, 1.08f);
        text.setTextIsSelectable(true);
        text.setAutoLinkMask(Linkify.WEB_URLS);
        text.setLinksClickable(true);
        text.setMovementMethod(LinkMovementMethod.getInstance());
        text.setPadding(0, dp(4), 0, dp(8));
        body.addView(text, new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT));

        LinearLayout actions = new LinearLayout(getContext());
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);

        TextView channel = new TextView(getContext());
        channel.setText(channelLabel(entry));
        channel.setTextSize(11f);
        channel.setTextColor(Color.rgb(83, 100, 113));
        channel.setSingleLine(true);
        actions.addView(channel, new LinearLayout.LayoutParams(
                0,
                LayoutParams.WRAP_CONTENT,
                1f));

        if (ChatLogStore.SURFACE_FRONT.equals(entry.surface)
                && ("user".equals(entry.role) || "assistant".equals(entry.role))) {
            TextView reply = new TextView(getContext());
            reply.setText("↩ 返信");
            reply.setTextSize(12f);
            reply.setTextColor(Color.rgb(29, 155, 240));
            reply.setGravity(Gravity.CENTER);
            reply.setPadding(dp(10), dp(5), dp(10), dp(5));
            reply.setContentDescription("投稿 #" + entry.id + " に返信");
            reply.setOnClickListener(v -> {
                ReplyListener listener = replyListener;
                if (listener != null) listener.onReplyRequested(entry);
            });
            actions.addView(reply, new LinearLayout.LayoutParams(
                    LayoutParams.WRAP_CONTENT,
                    dp(30)));

            TextView thread = new TextView(getContext());
            thread.setText("🧵 スレッド");
            thread.setTextSize(12f);
            thread.setTextColor(Color.rgb(83, 100, 113));
            thread.setGravity(Gravity.CENTER);
            thread.setPadding(dp(10), dp(5), dp(10), dp(5));
            thread.setContentDescription("投稿 #" + entry.id + " のスレッドを開く");
            thread.setOnClickListener(v -> {
                ThreadListener listener = threadListener;
                if (listener != null) listener.onThreadRequested(entry);
            });
            actions.addView(thread, new LinearLayout.LayoutParams(
                    LayoutParams.WRAP_CONTENT,
                    dp(30)));
        }

        body.addView(actions);

        LinearLayout wrapper = new LinearLayout(getContext());
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.addView(outer, new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT));

        View divider = new View(getContext());
        divider.setBackgroundColor(Color.rgb(239, 243, 244));
        wrapper.addView(divider, new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                dp(1)));

        return wrapper;
    }

    private String actorName(ChatLogStore.Entry entry) {
        String c = entry.channel == null ? "" : entry.channel;
        if ("user".equals(entry.role)) return "あなた";
        if ("assistant".equals(entry.role)) return "FAP";
        if (c.startsWith("git")) return "Git";
        if (c.startsWith("browser")) return "Browser";
        if (c.startsWith("voice")) return "Voice";
        if (c.startsWith("agent")) return "FAP Agent";
        return "FAP System";
    }

    private String actorHandle(ChatLogStore.Entry entry) {
        String c = entry.channel == null ? "" : entry.channel;
        if ("user".equals(entry.role)) return "@you";
        if ("assistant".equals(entry.role)) return "@fap";
        if (c.startsWith("git")) return "@git";
        if (c.startsWith("browser")) return "@browser";
        if (c.startsWith("voice")) return "@voice";
        if (c.startsWith("agent")) return "@agent";
        return "@system";
    }

    private String avatarText(ChatLogStore.Entry entry) {
        String name = actorName(entry);
        if ("あなた".equals(name)) return "あ";
        if ("FAP".equals(name)) return "F";
        if ("Git".equals(name)) return "G";
        if ("Browser".equals(name)) return "B";
        if ("Voice".equals(name)) return "V";
        if ("FAP Agent".equals(name)) return "A";
        return "S";
    }

    private int avatarBackground(ChatLogStore.Entry entry) {
        String name = actorName(entry);
        if ("FAP".equals(name)) return Color.BLACK;
        if ("Git".equals(name)) return Color.rgb(36, 41, 47);
        if ("Browser".equals(name)) return Color.rgb(29, 155, 240);
        if ("FAP Agent".equals(name)) return Color.rgb(239, 243, 244);
        if ("Voice".equals(name)) return Color.rgb(224, 247, 250);
        return Color.rgb(239, 243, 244);
    }

    private int avatarTextColor(ChatLogStore.Entry entry) {
        String name = actorName(entry);
        if ("FAP".equals(name) || "Git".equals(name) || "Browser".equals(name)) {
            return Color.WHITE;
        }
        return Color.rgb(15, 20, 25);
    }

    private String channelLabel(ChatLogStore.Entry entry) {
        String c = entry.channel == null ? "unknown" : entry.channel;
        String surface = ChatLogStore.SURFACE_BACK.equals(entry.surface) ? "裏側" : "会話";
        return surface + " · " + c + " · #" + entry.id;
    }

    private String relativeTime(long timestampMs) {
        long now = System.currentTimeMillis();
        long delta = Math.max(0L, now - timestampMs);
        long seconds = delta / 1000L;
        if (seconds < 60L) return seconds + "秒";
        long minutes = seconds / 60L;
        if (minutes < 60L) return minutes + "分";
        long hours = minutes / 60L;
        if (hours < 24L) return hours + "時間";

        SimpleDateFormat format = new SimpleDateFormat("M/d", Locale.JAPAN);
        format.setTimeZone(TimeZone.getDefault());
        return format.format(new Date(timestampMs));
    }

    private GradientDrawable circle(int color) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.OVAL);
        drawable.setColor(color);
        return drawable;
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
