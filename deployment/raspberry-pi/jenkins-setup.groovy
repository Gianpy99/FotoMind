// init.groovy.d script (copied by jenkins-setup.sh): creates/rotates the Secret text
// credential "fotomind-database-url" and the "fotomind" pipeline job with SCM polling, so
// the first push of the Jenkinsfile to main is picked up automatically.
// Idempotent and self-deleting (not re-run on later Jenkins restarts).
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.Domain
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl
import hudson.util.Secret
import jenkins.model.Jenkins

def tag = '[fotomind-setup]'
def jobName = 'fotomind'
def secretFile = new File('/var/jenkins_home/fotomind_database_url')

if (secretFile.exists()) {
    try {
        def store = SystemCredentialsProvider.getInstance().getStore()
        def domain = Domain.global()
        store.getCredentials(domain).findAll { it.id == 'fotomind-database-url' }.each {
            store.removeCredentials(domain, it)
        }
        store.addCredentials(domain, new StringCredentialsImpl(
            CredentialsScope.GLOBAL, 'fotomind-database-url', 'FotoMind - PostgreSQL URL (Pi, DB fotomind)',
            Secret.fromString(secretFile.text.trim())))
        println "${tag} credential fotomind-database-url created"
    } catch (e) {
        println "${tag} credential ERROR: ${e}"
    } finally {
        secretFile.delete()
    }
}

def xml = '''<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>FotoMind - API + web UI container (photos.borrellofamily.co.uk, port 8097)</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
      <triggers>
        <hudson.triggers.SCMTrigger>
          <spec>H/3 * * * *</spec>
          <ignorePostCommitHooks>false</ignorePostCommitHooks>
        </hudson.triggers.SCMTrigger>
      </triggers>
    </org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>https://github.com/Gianpy99/FotoMind.git</url>
          <credentialsId>github-gianpy99</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/main</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="empty-list"/>
      <extensions/>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>'''

try {
    def jenkins = Jenkins.instance
    if (jenkins.getItem(jobName) == null) {
        jenkins.createProjectFromXML(jobName, new ByteArrayInputStream(xml.getBytes('UTF-8')))
        println "${tag} job '${jobName}' created (polls main every ~3 min)"
    } else {
        println "${tag} job '${jobName}' already exists"
    }
} catch (e) {
    println "${tag} job ERROR: ${e}"
}

try { new File('/var/jenkins_home/init.groovy.d/fotomind-setup.groovy').delete() } catch (ignored) {}
