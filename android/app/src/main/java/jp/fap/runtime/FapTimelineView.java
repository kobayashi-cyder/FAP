package jp.fap.runtime;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.MediaController;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.VideoView;

import org.json.JSONObject;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

public final class FapTimelineView extends ScrollView {
    private final LinearLayout feed;
    private final ArrayList<Bitmap> previewBitmaps = new ArrayList<>();

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

    public void render(List<ChatLogStore.Entry> entries) {
        releasePreviewBitmaps();
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

        if (entry.channel != null && entry.channel.startsWith("media:")) {
            body.addView(mediaCard(entry), new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    LayoutParams.WRAP_CONTENT));
        } else {
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
        }

        TextView channel = new TextView(getContext());
        channel.setText(channelLabel(entry));
        channel.setTextSize(11f);
        channel.setTextColor(Color.rgb(83, 100, 113));
        channel.setSingleLine(true);
        body.addView(channel);

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

    private View mediaCard(ChatLogStore.Entry entry) {
        LinearLayout card = new LinearLayout(getContext());
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(10), dp(10), dp(10));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.rgb(250, 251, 252));
        bg.setCornerRadius(dp(16));
        bg.setStroke(dp(1), Color.rgb(224, 230, 234));
        card.setBackground(bg);

        try {
            JSONObject media = new JSONObject(entry.text);
            String type = media.optString("type", "");
            boolean video = "video".equals(type);
            String path = media.optString("path", "").trim();
            String cover = media.optString("cover", "").trim();

            TextView title = new TextView(getContext());
            title.setText(video ? "動画生成" : "画像生成");
            title.setTextSize(15f);
            title.setTypeface(Typeface.DEFAULT_BOLD);
            title.setTextColor(Color.rgb(15, 20, 25));
            title.setPadding(0, 0, 0, dp(8));
            card.addView(title);

            String previewPath = video && !cover.isEmpty() ? cover : path;
            Bitmap bitmap = null;
            if (!previewPath.isEmpty() && new File(previewPath).isFile()) {
                bitmap = decodePreview(previewPath, 960, 640);
            }
            if (bitmap != null) {
                previewBitmaps.add(bitmap);
                ImageView preview = new ImageView(getContext());
                preview.setImageBitmap(bitmap);
                preview.setAdjustViewBounds(true);
                preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
                preview.setBackgroundColor(Color.rgb(242, 244, 246));
                card.addView(preview, new LinearLayout.LayoutParams(
                        LayoutParams.MATCH_PARENT,
                        dp(video ? 210 : 260)));
            }

            TextView info = new TextView(getContext());
            info.setTextColor(Color.rgb(83, 100, 113));
            info.setTextSize(12f);
            if (video) {
                info.setText(
                        media.optInt("width", 512) + "×" + media.optInt("height", 512)
                                + " · " + media.optInt("fps", 12) + "fps"
                                + " · " + media.optInt("duration_seconds", 0) + "秒");
            } else {
                info.setText("生成画像");
            }
            info.setPadding(0, dp(8), 0, video ? dp(6) : 0);
            card.addView(info);

            if (video && !path.isEmpty() && new File(path).isFile()) {
                Button play = new Button(getContext());
                play.setText("▶ 再生");
                play.setAllCaps(false);
                play.setTextSize(13f);
                play.setOnClickListener(v -> openVideo(path));
                card.addView(play, new LinearLayout.LayoutParams(
                        LayoutParams.WRAP_CONTENT,
                        dp(44)));
            }
        } catch (Throwable t) {
            TextView error = new TextView(getContext());
            error.setText("生成物を表示できません · " + t.getClass().getSimpleName());
            error.setTextSize(13f);
            error.setTextColor(Color.rgb(180, 50, 50));
            card.addView(error);
        }
        return card;
    }

    private void releasePreviewBitmaps() {
        for (Bitmap bitmap : previewBitmaps) {
            if (bitmap == null) continue;
            try {
                if (!bitmap.isRecycled()) bitmap.recycle();
            } catch (Throwable ignored) {
            }
        }
        previewBitmaps.clear();
    }

    @Override
    protected void onDetachedFromWindow() {
        releasePreviewBitmaps();
        super.onDetachedFromWindow();
    }

    private Bitmap decodePreview(String path, int maxWidth, int maxHeight) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(path, bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null;

        int sample = 1;
        while (bounds.outWidth / (sample * 2) >= maxWidth
                && bounds.outHeight / (sample * 2) >= maxHeight) {
            sample *= 2;
        }
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = Math.max(1, sample);
        options.inPreferredConfig = Bitmap.Config.RGB_565;
        return BitmapFactory.decodeFile(path, options);
    }

    private void openVideo(String path) {
        if (path == null || path.trim().isEmpty()) return;
        File file = new File(path);
        if (!file.isFile()) return;

        VideoView video = new VideoView(getContext());
        MediaController controls = new MediaController(getContext());
        controls.setAnchorView(video);
        video.setMediaController(controls);
        video.setVideoPath(file.getAbsolutePath());

        AlertDialog dialog = new AlertDialog.Builder(getContext())
                .setTitle("動画プレビュー")
                .setView(video)
                .setNegativeButton("閉じる", (d, which) -> {
                    try {
                        video.stopPlayback();
                    } catch (Throwable ignored) {
                    }
                })
                .create();
        dialog.setOnShowListener(d -> {
            try {
                video.start();
            } catch (Throwable ignored) {
            }
        });
        dialog.show();
    }

    private String actorName(ChatLogStore.Entry entry) {
        String c = entry.channel == null ? "" : entry.channel;
        if ("user".equals(entry.role)) return "あなた";
        if ("assistant".equals(entry.role)) return "FAP";
        if (c.startsWith("media:")) return "FAP";
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
        if (c.startsWith("media:")) {
            return "世界観 · " + c.substring("media:".length()) + " · #" + entry.id;
        }
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
