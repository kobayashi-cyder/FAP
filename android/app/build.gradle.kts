plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val legacyFapVersion = providers.environmentVariable("FAP_VERSION").orElse("59").get().toIntOrNull() ?: 59
val fapVersionCode = providers.environmentVariable("FAP_VERSION_CODE")
    .orElse(legacyFapVersion.toString()).get().toIntOrNull() ?: legacyFapVersion
val fapVersionName = providers.environmentVariable("FAP_VERSION_NAME")
    .orElse("${legacyFapVersion}.0-android").get()

val fapSigningStoreFile = providers.environmentVariable("FAP_SIGNING_STORE_FILE").orNull
val fapSigningStorePassword = providers.environmentVariable("FAP_SIGNING_STORE_PASSWORD").orNull
val fapSigningKeyAlias = providers.environmentVariable("FAP_SIGNING_KEY_ALIAS").orNull
val fapSigningKeyPassword = providers.environmentVariable("FAP_SIGNING_KEY_PASSWORD").orNull

android {
    namespace = "jp.fap.runtime"
    compileSdk = 37

    defaultConfig {
        applicationId = "jp.fap.runtime"
        minSdk = 26
        targetSdk = 37
        versionCode = fapVersionCode
        versionName = fapVersionName
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        if (
            fapSigningStoreFile != null
            && fapSigningStorePassword != null
            && fapSigningKeyAlias != null
            && fapSigningKeyPassword != null
        ) {
            create("fapRelease") {
                storeFile = file(fapSigningStoreFile)
                storePassword = fapSigningStorePassword
                keyAlias = fapSigningKeyAlias
                keyPassword = fapSigningKeyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("fapRelease")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        buildPython("python3.13")
    }
}
