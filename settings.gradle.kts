plugins {
    id("com.gradle.develocity") version "4.3"
}

rootProject.name = "firefox-ios-test-import"

develocity {
    server = "https://ge.solutions-team.gradle.com/"
    allowUntrustedServer = true
    edgeDiscovery = true
    buildScan {
        publishing.onlyIf { it.isAuthenticated }
        uploadInBackground = System.getenv("CI") == null
    }
}
