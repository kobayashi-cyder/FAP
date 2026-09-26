package jp.fap.runtime;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;

public final class ScreenShareCaptureService extends Service {
    private static final String CHANNEL_ID = "fap_screen_teach";
    private static final int NOTIFICATION_ID = 1701;
    private static final long FRAME_INTERVAL_MS = 700L;
    private static final int FRAME_RING = 96;
    private static final int MAX_STORED_WIDTH = 720;

    private MediaProjection projection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private HandlerThread captureThread;
    private Handler captureHandler;
    private long lastFrameAt = 0L;
    private int captureWidth;
    private int captureHeight;
    private int densityDpi;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        captureThread = new HandlerThread("fap-screen-teach-capture");
        captureThread.start();
        captureHandler = new Handler(captureThread.getLooper());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? "" : intent.getAction();
        if (ScreenTeachController.ACTION_STOP.equals(action)) {
            stopCapture();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!ScreenTeachController.ACTION_START.equals(action)) {
            return START_NOT_STICKY;
        }

        Notification notification = buildNotification();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }

        int resultCode = intent.getIntExtra(
                ScreenTeachController.EXTRA_RESULT_CODE,
                android.app.Activity.RESULT_CANCELED);
        Intent resultData;
        if (Build.VERSION.SDK_INT >= 33) {
            resultData = intent.getParcelableExtra(
                    ScreenTeachController.EXTRA_RESULT_DATA,
                    Intent.class);
        } else {
            //noinspection deprecation
            resultData = intent.getParcelableExtra(ScreenTeachController.EXTRA_RESULT_DATA);
        }
        if (resultCode != android.app.Activity.RESULT_OK || resultData == null) {
            ScreenTeachController.markSharing(this, false);
            stopSelf();
            return START_NOT_STICKY;
        }

        startProjection(resultCode, resultData);
        return START_NOT_STICKY;
    }

    private void startProjection(int resultCode, Intent resultData) {
        stopCapture();

        MediaProjectionManager manager =
                (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            ScreenTeachController.markSharing(this, false);
            stopSelf();
            return;
        }

        projection = manager.getMediaProjection(resultCode, resultData);
        if (projection == null) {
            ScreenTeachController.markSharing(this, false);
            stopSelf();
            return;
        }

        resolveDisplaySize();
        imageReader = ImageReader.newInstance(
                captureWidth,
                captureHeight,
                PixelFormat.RGBA_8888,
                2);
        imageReader.setOnImageAvailableListener(this::onImageAvailable, captureHandler);

        projection.registerCallback(new MediaProjection.Callback() {
            @Override public void onStop() {
                ScreenTeachController.markSharing(
                        ScreenShareCaptureService.this,
                        false);
                cleanupProjectionOnly();
                stopSelf();
            }
        }, captureHandler);

        virtualDisplay = projection.createVirtualDisplay(
                "FAP Screen Teach",
                captureWidth,
                captureHeight,
                densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader.getSurface(),
                null,
                captureHandler);

        ScreenTeachController.markSharing(this, true);
    }

    private void resolveDisplaySize() {
        WindowManager wm = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
        DisplayMetrics metrics = getResources().getDisplayMetrics();
        densityDpi = Math.max(1, metrics.densityDpi);

        int width = Math.max(1, metrics.widthPixels);
        int height = Math.max(1, metrics.heightPixels);
        if (wm != null && Build.VERSION.SDK_INT >= 30) {
            try {
                Rect bounds = wm.getMaximumWindowMetrics().getBounds();
                width = Math.max(1, bounds.width());
                height = Math.max(1, bounds.height());
            } catch (Throwable ignored) {
            }
        }
        captureWidth = width;
        captureHeight = height;
    }

    private void onImageAvailable(ImageReader reader) {
        Image image = null;
        try {
            image = reader.acquireLatestImage();
            if (image == null) return;

            long now = System.currentTimeMillis();
            if (now - lastFrameAt < FRAME_INTERVAL_MS) return;
            lastFrameAt = now;

            Image.Plane[] planes = image.getPlanes();
            if (planes == null || planes.length == 0) return;
            Image.Plane plane = planes[0];
            ByteBuffer buffer = plane.getBuffer();
            int pixelStride = plane.getPixelStride();
            int rowStride = plane.getRowStride();
            int rowPadding = Math.max(0, rowStride - pixelStride * captureWidth);
            int bitmapWidth = captureWidth + rowPadding / Math.max(1, pixelStride);

            Bitmap padded = Bitmap.createBitmap(
                    bitmapWidth,
                    captureHeight,
                    Bitmap.Config.ARGB_8888);
            padded.copyPixelsFromBuffer(buffer);
            Bitmap cropped = Bitmap.createBitmap(
                    padded,
                    0,
                    0,
                    captureWidth,
                    captureHeight);

            int storedWidth = captureWidth;
            int storedHeight = captureHeight;
            Bitmap stored = cropped;
            if (captureWidth > MAX_STORED_WIDTH) {
                storedWidth = MAX_STORED_WIDTH;
                storedHeight = Math.max(
                        1,
                        Math.round(captureHeight * (MAX_STORED_WIDTH / (float) captureWidth)));
                stored = Bitmap.createScaledBitmap(
                        cropped,
                        storedWidth,
                        storedHeight,
                        true);
            }

            long seq = ScreenTeachController.nextFrameSequence(this);
            int slot = (int) (seq % FRAME_RING);
            File target = new File(
                    ScreenTeachController.frameDirectory(this),
                    String.format(java.util.Locale.ROOT, "frame_%03d.jpg", slot));
            File temp = new File(target.getParentFile(), target.getName() + ".tmp");
            try (FileOutputStream out = new FileOutputStream(temp, false)) {
                stored.compress(Bitmap.CompressFormat.JPEG, 66, out);
                out.flush();
            }
            if (target.exists()) target.delete();
            if (!temp.renameTo(target)) {
                try (FileOutputStream out = new FileOutputStream(target, false)) {
                    stored.compress(Bitmap.CompressFormat.JPEG, 66, out);
                }
                temp.delete();
            }

            ScreenTeachController.recordFrame(
                    this,
                    target,
                    captureWidth,
                    captureHeight,
                    storedWidth,
                    storedHeight);

            if (stored != cropped) stored.recycle();
            cropped.recycle();
            padded.recycle();
        } catch (Throwable ignored) {
        } finally {
            if (image != null) {
                try {
                    image.close();
                } catch (Throwable ignored) {
                }
            }
        }
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
                this,
                1702,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("FAP 画面共有")
                .setContentText("学習用に画面フレームを取得中")
                .setContentIntent(pending)
                .setOngoing(true)
                .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "FAP 画面共有",
                NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("FAPの画面共有・学習用キャプチャ");
        nm.createNotificationChannel(channel);
    }

    private void stopCapture() {
        ScreenTeachController.markSharing(this, false);
        cleanupProjectionOnly();
        try {
            stopForeground(STOP_FOREGROUND_REMOVE);
        } catch (Throwable ignored) {
        }
    }

    private void cleanupProjectionOnly() {
        if (virtualDisplay != null) {
            try {
                virtualDisplay.release();
            } catch (Throwable ignored) {
            }
            virtualDisplay = null;
        }
        if (imageReader != null) {
            try {
                imageReader.close();
            } catch (Throwable ignored) {
            }
            imageReader = null;
        }
        if (projection != null) {
            MediaProjection value = projection;
            projection = null;
            try {
                value.stop();
            } catch (Throwable ignored) {
            }
        }
    }

    @Override
    public void onDestroy() {
        stopCapture();
        if (captureThread != null) {
            try {
                captureThread.quitSafely();
            } catch (Throwable ignored) {
            }
            captureThread = null;
            captureHandler = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
