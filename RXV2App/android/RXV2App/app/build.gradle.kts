plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.messiter.rxv2"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.messiter.rxv2"
        minSdk = 26
        targetSdk = 35
        // Bump BOTH for every release published to messiter.com — the in-app
        // update check compares versionCode against rxv2app/release/manifest.json
        // (publish with ../publish_app.sh, which reads these values).
        versionCode = 492
        versionName = "5.92"
    }
    buildTypes {
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
