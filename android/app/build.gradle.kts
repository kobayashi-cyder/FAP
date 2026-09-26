plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val fapVersionCode = providers.environmentVariable("FAP_VERSION_CODE").orElse("10001").get().toIntOrNull() ?: 10001
val fapVersionName = providers.environmentVariable("FAP_VERSION_NAME").orElse("1.0.01-pixel").get()

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
