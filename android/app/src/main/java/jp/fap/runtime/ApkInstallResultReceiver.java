package jp.fap.runtime;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.widget.Toast;

public final class ApkInstallResultReceiver extends BroadcastReceiver {
    public static final String ACTION_INSTALL_STATUS =
            "jp.fap.runtime.ACTION_INSTALL_STATUS";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_INSTALL_STATUS.equals(intent.getAction())) return;

        int status = intent.getIntExtra(
                PackageInstaller.EXTRA_STATUS,
                PackageInstaller.STATUS_FAILURE);
        String message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);

        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm != null) {
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(confirm);
            }
            return;
        }

        String text;
        if (status == PackageInstaller.STATUS_SUCCESS) {
            text = "FAP APK更新が完了しました";
        } else {
            text = "FAP APK更新に失敗: "
                    + status
                    + (message == null ? "" : " · " + message);
        }

        try {
            new ChatLogStore(context).appendBack(
                    "system",
                    "git-apk",
                    text);
        } catch (Throwable ignored) {
        }

        Toast.makeText(context, text, Toast.LENGTH_LONG).show();
    }
}
