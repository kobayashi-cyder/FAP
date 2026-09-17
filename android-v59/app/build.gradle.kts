plugins {
    id("com.android.application")
}

android {
    namespace = "jp.fap.v59"
    compileSdk = 37

    defaultConfig {
        applicationId = "jp.fap.v59"
        minSdk = 26
        targetSdk = 37
        versionCode = 59
        versionName = "59.0-android"
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
