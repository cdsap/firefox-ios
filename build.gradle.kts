import com.gradle.develocity.agent.gradle.test.ImportJUnitXmlReports
import com.gradle.develocity.agent.gradle.test.JUnitXmlDialect

plugins {
    base
}

// Collect all JUnit XML files from the test-reports directory
val reportsDir = layout.projectDirectory.dir("test-reports")

tasks.register("import") {
    doLast { println("Import task executed") }
}

afterEvaluate {
    ImportJUnitXmlReports.register(
        tasks,
        tasks.named("import"),
        JUnitXmlDialect.GENERIC,
    ).configure {
        reports.from(reportsDir.asFileTree.matching { include("*.xml") })
    }
}
