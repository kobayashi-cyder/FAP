plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "jp.fap.v1"
    compileSdk = 37

    defaultConfig {
        applicationId = "jp.fap.v1"
        minSdk = 26
        targetSdk = 37
        versionCode = 10001
        versionName = "1.0.01-android"
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
