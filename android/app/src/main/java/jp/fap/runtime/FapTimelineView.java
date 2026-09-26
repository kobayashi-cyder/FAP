package jp.fap.runtime;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.Html;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.regex.Pattern;

/**
 * Conversation-first renderer.
 *
 * Normal user/assistant turns intentionally hide transport, channel, confidence,
 * handle and other runtime metadata. Those details remain preserved in the
 * durable log and are visible through the diagnostics views.
 */
public final class FapTimelineView extends ScrollView {
    private static final int TEXT = Color.rgb(28, 28, 30);
    private static final int MUTED = Color.rgb(99, 99, 102);
    private static final int BORDER = Color.rgb(229, 229, 234);
    private static final int USER_BUBBLE = Color.rgb(242, 242, 247);
    private static final int LOG_BG = Color.rgb(248, 248, 250);

    private final LinearLayout feed;

    public FapTimelineView(Context context) {
        super(context);
        setFillViewport(true);
        setBackgroundColor(Color.WHITE);
        setVerticalScrollBarEnabled(true);

        feed = new LinearLayout(context);
        feed.setOrientation(LinearLayout.VERTICAL);
        feed.setPadding(0, dp(4), 0, dp(8));
        feed.setBackgroundColor(Color.WHITE);
        addView(feed, new ScrollView.LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.WRAP_CONTENT));
    }

    public void render(List<ChatLogStore.Entry> entries) {
        feed.removeAllViews();
        if (entries == null || entries.isEmpty()) {
            TextView empty = new TextView(getContext());
            empty.setText("メッセージを送ると、ここに会話が表示されます。");
            empty.setTextSize(15f);
            empty.setTextColor(MUTED);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(28), dp(88), dp(28), dp(88));
            feed.addView(empty, new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    LayoutParams.WRAP_CONTENT));
            return;
        }

        for (ChatLogStore.Entry entry : entries) {
            View row = ChatLogStore.SURFACE_BACK.equals(entry.surface)
                    ? technicalPost(entry)
                    : conversationPost(entry);
            feed.addView(row, new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    LayoutParams.WRAP_CONTENT));
        }
        post(() -> fullScroll(FOCUS_DOWN));
    }

    private View conversationPost(ChatLogStore.Entry entry) {
        boolean user = "user".equals(entry.role);

        LinearLayout wrapper = new LinearLayout(getContext());
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(dp(14), dp(9), dp(14), dp(9));
        wrapper.setGravity(user ? Gravity.END : Gravity.START);

        if (!user) {
            TextView name = new TextView(getContext());
            name.setText("FAP");
            name.setTextSize(13f);
            name.setTypeface(Typeface.DEFAULT_BOLD);
            name.setTextColor(MUTED);
            name.setPadding(dp(2), 0, 0, dp(5));
            wrapper.addView(name);
        }

        TextView text = new TextView(getContext());
        text.setText(renderMarkdown(entry.text));
        text.setTextSize(16f);
        text.setTextColor(TEXT);
        text.setLineSpacing(0f, 1.10f);
        text.setTextIsSelectable(true);
        text.setLinksClickable(true);
        text.setMovementMethod(LinkMovementMethod.getInstance());
        Linkify.addLinks(text, Linkify.WEB_URLS);
        text.setPadding(
                user ? dp(14) : dp(2),
                user ? dp(10) : dp(4),
                user ? dp(14) : dp(2),
                user ? dp(10) : dp(6));
        text.setMaxWidth((int) (getResources().getDisplayMetrics().widthPixels * 0.88f));
        if (user) {
            text.setBackground(roundRect(USER_BUBBLE, 18, 0, 0));
        }
        installCopyAction(text, entry.text);

        wrapper.addView(text, new LinearLayout.LayoutParams(
                LayoutParams.WRAP_CONTENT,
                LayoutParams.WRAP_CONTENT));

        if (!user) {
            TextView hint = new TextView(getContext());
            hint.setText("長押しでコピー");
            hint.setTextSize(10f);
            hint.setTextColor(Color.rgb(142, 142, 147));
            hint.setPadding(dp(2), 0, 0, 0);
            wrapper.addView(hint);
        }

        return wrapper;
    }

    private View technicalPost(ChatLogStore.Entry entry) {
        LinearLayout wrapper = new LinearLayout(getContext());
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(dp(14), dp(7), dp(14), dp(7));
        wrapper.setBackgroundColor(LOG_BG);

        TextView meta = new TextView(getContext());
        meta.setText(actorName(entry) + " · " + relativeTime(entry.timestampMs)
                + " · " + entry.channel + " · #" + entry.id);
        meta.setTextSize(11f);
        meta.setTextColor(MUTED);
        meta.setSingleLine(true);
        meta.setEllipsize(TextUtils.TruncateAt.END);
        wrapper.addView(meta);

        TextView text = new TextView(getContext());
        text.setText(entry.text);
        text.setTextSize(13f);
        text.setTextColor(TEXT);
        text.setTextIsSelectable(true);
        text.setAutoLinkMask(Linkify.WEB_URLS);
        text.setLinksClickable(true);
        text.setMovementMethod(LinkMovementMethod.getInstance());
        text.setPadding(0, dp(3), 0, dp(5));
        installCopyAction(text, entry.text);
        wrapper.addView(text);

        View divider = new View(getContext());
        divider.setBackgroundColor(BORDER);
        wrapper.addView(divider, new LinearLayout.LayoutParams(
                LayoutParams.MATCH_PARENT,
                dp(1)));

        return wrapper;
    }

    private CharSequence renderMarkdown(String raw) {
        String value = raw == null ? "" : raw;
        String html = TextUtils.htmlEncode(value);

        html = Pattern.compile("(?s)```(?:[A-Za-z0-9_+.-]+)?\\n(.*?)```")
                .matcher(html)
                .replaceAll("<tt>$1</tt>");
        html = html.replaceAll("(?m)^###\\s+(.+)$", "<b>$1</b>");
        html = html.replaceAll("(?m)^##\\s+(.+)$", "<b>$1</b>");
        html = html.replaceAll("(?m)^#\\s+(.+)$", "<b>$1</b>");
        html = html.replaceAll("\\*\\*(.+?)\\*\\*", "<b>$1</b>");
        html = html.replaceAll("`([^`\\n]+)`", "<tt>$1</tt>");
        html = html.replaceAll("(?m)^\\s*[-*]\\s+", "• ");
        html = html.replace("\n", "<br>");

        if (android.os.Build.VERSION.SDK_INT >= 24) {
            return Html.fromHtml(html, Html.FROM_HTML_MODE_LEGACY);
        }
        //noinspection deprecation
        return Html.fromHtml(html);
    }

    private void installCopyAction(TextView view, String raw) {
        view.setOnLongClickListener(v -> {
            ClipboardManager clipboard =
                    (ClipboardManager) getContext().getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(
                    ClipData.newPlainText("FAP message", raw == null ? "" : raw));
            Toast.makeText(getContext(), "コピーしました", Toast.LENGTH_SHORT).show();
            return true;
        });
    }

    private String actorName(ChatLogStore.Entry entry) {
        String c = entry.channel == null ? "" : entry.channel;
        if (c.startsWith("git")) return "Git";
        if (c.startsWith("browser") || c.startsWith("web")) return "Web";
        if (c.startsWith("voice")) return "Voice";
        if (c.startsWith("agent")) return "Agent";
        return "System";
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

    private GradientDrawable roundRect(
            int fill,
            int radiusDp,
            int strokeColor,
            int strokeDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radiusDp));
        if (strokeDp > 0) drawable.setStroke(dp(strokeDp), strokeColor);
        return drawable;
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
