pipeline {
  agent {
    kubernetes {
      label 'Jenkins'
      defaultContainer "${OS_VERSION_CHECKER}"
      yaml """
apiVersion: v1
kind: Pod
metadata:
  labels:
    some-label: some-label-value
spec:
  containers:
  - name: ${OS_VERSION_CHECKER}
    image: dockerhub.ultimum.io/ultimum-internal/${OS_VERSION_CHECKER}:latest
    alwaysPullImage: true
    command:
    - cat
    tty: true
  - name: proxy
    image: dockerhub.ultimum.io/ultimum-internal/internal-proxy:latest
    alwaysPullImage: true
    command:
    - cat
    tty: true
"""
    }
  }
  stages {
    stage('Generate artifact') {
      steps {
        container("${OS_VERSION_CHECKER}") {
            sh "cd /opt/app"
            sh "ls -la"
            sh "pwd"
            sh "cd /home/jenkins/agent"
            sh "ls -la"
        }
      }
    }
    stage('Configure proxy') {
      steps {
        container("proxy") {
          withCredentials([certificate(aliasVariable: '', credentialsId: 'e256026f-b227-4f8e-92b0-220d3ccb7079', keystoreVariable: 'KEYSTORE', passwordVariable: 'KEYSTORE_PASS')]) {
            sh "start_proxy.sh $KEYSTORE $KEYSTORE_PASS"
            sh "ls -la"
            sh "pwd"
          }
        }
      }
    }
    stage('Upload index artifact') {
      steps {
        container("${OS_VERSION_CHECKER}") {
              sh 'cd /opt/app; curl -i -X POST "http://localhost" -F "data=@/opt/app/index.html"'
        }
      }
    }
  }
}
