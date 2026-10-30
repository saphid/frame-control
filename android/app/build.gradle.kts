import java.security.MessageDigest
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.saphid.framecontrol"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.saphid.framecontrol"
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        debug {
            // Installs beside a release build, with its own key and pairing.
            applicationIdSuffix = ".debug"
            resValue("string", "app_name", "Frame Control (debug)")
        }
        release {
            // Unsigned: the release key is applied after review, outside this build.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            resValue("string", "app_name", "Frame Control")
        }
    }

    buildFeatures {
        resValues = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // No Google-encrypted dependency block in the APK; Play gets it from the bundle.
    dependenciesInfo {
        includeInApk = false
    }

    packaging {
        resources {
            excludes += setOf("META-INF/versions/9/OSGI-INF/MANIFEST.MF", "META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*")
        }
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
        warningsAsErrors = false
        // The target is Play's current requirement (API 36); 37 needs the local-network
        // permission flow first (docs/android.md).
        disable += setOf("OldTargetApi")
    }

    testOptions {
        unitTests.all { test ->
            test.systemProperty("frame.bundle.dir", layout.buildDirectory.dir("generated/frameBundle").get().asFile.path)
            test.maxHeapSize = "1g"
        }
    }
}

dependencies {
    implementation(libs.jsch)
    implementation(libs.bouncycastle)
    implementation(libs.coroutines.android)
    implementation(libs.activity)
    implementation(libs.lifecycle.runtime)
    implementation(libs.lifecycle.viewmodel)
    implementation(libs.webkit)

    testImplementation(libs.junit)
    testImplementation(libs.coroutines.core)
    testImplementation(libs.sshd.core)
    testImplementation(libs.sshd.sftp)
    testImplementation(libs.slf4j.nop)
}

/** The headset server as an asset: made from a clean commit, or a prebuilt copy, and checked against the pinned hash. */
abstract class FrameBundleTask : DefaultTask() {
    @get:Input abstract val expectedSha256: Property<String>
    @get:Input @get:Optional abstract val rev: Property<String>
    @get:InputFile @get:Optional abstract val prebuilt: RegularFileProperty
    @get:InputFile abstract val script: RegularFileProperty
    @get:Internal abstract val repoDir: DirectoryProperty
    @get:OutputDirectory abstract val outputDir: DirectoryProperty
    @get:Inject abstract val exec: ExecOperations

    @TaskAction
    fun pack() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        out.mkdirs()
        // Not ".tar.gz": asset packaging unzips .gz files and drops the extension.
        val archive = File(out, "frame-bundle.bin")
        if (prebuilt.isPresent) {
            prebuilt.get().asFile.copyTo(archive, overwrite = true)
        } else {
            exec.exec {
                commandLine("python3", "-I", script.get().asFile.path, "--repo", repoDir.get().asFile.path,
                            "--rev", rev.get(), "--out", archive.path, "--expect-sha256", expectedSha256.get())
            }
        }
        val digest = MessageDigest.getInstance("SHA-256").digest(archive.readBytes()).joinToString("") { "%02x".format(it) }
        check(digest == expectedSha256.get().lowercase()) {
            "the frame bundle is $digest, but gradle.properties pins ${expectedSha256.get()}"
        }
        File(out, "frame-bundle.version").writeText(digest.take(16))
    }
}

val frameBundle = tasks.register<FrameBundleTask>("frameBundle") {
    expectedSha256.set(providers.gradleProperty("frameControl.bundleSha256"))
    rev.set(providers.gradleProperty("frameControl.bundleRev"))
    providers.gradleProperty("frameBundleArchive").orNull?.let { prebuilt.set(file(it)) }
    script.set(rootProject.layout.projectDirectory.file("scripts/frame_bundle.py"))
    repoDir.set(rootProject.layout.projectDirectory.dir(".."))
    outputDir.set(layout.buildDirectory.dir("generated/frameBundle"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(frameBundle, FrameBundleTask::outputDir)
    }
}

tasks.withType<Test>().configureEach {
    dependsOn(frameBundle)
}
