pipeline {
  agent {
    kubernetes {
      label 'Jenkins'
      defaultContainer "${OS_VERSION_CHECKER}"
      yaml """
apiVersion: v1
kind: Pod
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
            sh 'cd /opt/app; python3 VersionStatus.py -t html -r train,stein,ussuri -f versions.html'
        }
      }
    }
    stage('Configure proxy') {
      steps {
        container("proxy") {
            withCredentials([certificate(aliasVariable: '', credentialsId: 'e256026f-b227-4f8e-92b0-220d3ccb7079', keystoreVariable: 'KEYSTORE', passwordVariable: 'KEYSTORE_PASS')]) {
                sh "start_proxy.sh $KEYSTORE $KEYSTORE_PASS"
          }
        }
      }
    }
    stage('Upload index artifact') {
      steps {
        container("${OS_VERSION_CHECKER}") {
            withCredentials([usernameColonPassword(credentialsId: '59c660c7-216d-4eaf-9294-0b11abba096d', variable: 'NEXUS_USER')]) {
              sh 'cd /opt/app; curl -X POST "http://localhost:8080/nexus/service/rest/v1/components?repository=public-repo" -H "accept: application/json" -H "Content-Type: multipart/form-data" -F "raw.directory=/" -u "${NEXUS_USER}" -F "raw.asset1=@versions.html;type=text/html" -F "raw.asset1.filename=versions.html"'
            }
        }
      }
    }
  }
}
