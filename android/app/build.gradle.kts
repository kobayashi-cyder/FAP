plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val fapVersion = providers.environmentVariable("FAP_VERSION").orElse("59").get().toIntOrNull() ?: 59

android {
    namespace = "jp.fap.runtime"
    compileSdk = 37

    defaultConfig {
        applicationId = "jp.fap.runtime"
        minSdk = 26
        targetSdk = 37
        versionCode = fapVersion
        versionName = "${fapVersion}.0-android"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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
