import java.text.SimpleDateFormat

def get_current_time(){
  def date = new Date()
  def sdf = new SimpleDateFormat("yyyy-MM-dd'-'HH:mm:ss")
  println sdf.format(date)
  return sdf.format(date)
}

def get_manifest(){
  stage('Get manifest'){
    generate_manifest = build job: 'DEPLOY-INFRA-os-version-checker-helper',
      parameters: [string(name: 'IMAGE_FILTERS', value: params.IMAGE_FILTERS)],
      wait: true,
      propagate: true
    if(generate_manifest.currentResult == "SUCCESS"){
      return [MANIFEST: generate_manifest.buildVariables.MANIFEST];
    }else{
      currentBuild.result = 'FAILURE';
      return [];
    }
  }
}

def apply_manifest(manifest){
  stage('Apply manifest'){
    podTemplate(
      slaveConnectTimeout: 1800,
      idleMinutes: 30,
      yaml: manifest['MANIFEST']
    ){
      node(POD_LABEL){
        stage('Generate output file'){
          container('os-version-checker'){
            sh "cd /tmp; echo '${manifest['MANIFEST']}' > manifest.yaml; python3 VersionStatus.py -r ${RELEASES} -f ${IMAGE_FILTERS} -y manifest.yaml"
          }
        }
        stage('Configure proxy'){
          container("proxy"){
            withCredentials([certificate(aliasVariable: '', credentialsId: 'e256026f-b227-4f8e-92b0-220d3ccb7079', keystoreVariable: 'KEYSTORE', passwordVariable: 'KEYSTORE_PASS')]){
              sh "start_proxy.sh $KEYSTORE $KEYSTORE_PASS"
            }
          }
        }
        stage('Upload openstack version checker artifact'){
          container('os-version-checker'){
            date = get_current_time()
            withCredentials([usernameColonPassword(credentialsId: '59c660c7-216d-4eaf-9294-0b11abba096d', variable: 'NEXUS_USER')]) {
              sh "cd /tmp; curl -X POST 'http://localhost:8080/nexus/service/rest/v1/components?repository=public-repo' -H 'accept: application/json' -H 'Content-Type: multipart/form-data' -F 'raw.directory=/' -u ${NEXUS_USER} -F 'raw.asset1=@os_index.html;type=text/html' -F 'raw.asset1.filename=os-check-${MAPPINGS}-${date}.html'"
            }
          }
        }
        stage('Upload image version checker artifact'){
          container('os-version-checker'){
            date = get_current_time()
            withCredentials([usernameColonPassword(credentialsId: '59c660c7-216d-4eaf-9294-0b11abba096d', variable: 'NEXUS_USER')]) {
              sh "cd /tmp; curl -X POST 'http://localhost:8080/nexus/service/rest/v1/components?repository=public-repo' -H 'accept: application/json' -H 'Content-Type: multipart/form-data' -F 'raw.directory=/' -u ${NEXUS_USER} -F 'raw.asset1=@img_index.html;type=text/html' -F 'raw.asset1.filename=img-check-${MAPPINGS}-${date}.html'"
            }
          }
        }
      }
    }
  }
}

node{
  manifest = get_manifest()
  apply_manifest(manifest)
}
