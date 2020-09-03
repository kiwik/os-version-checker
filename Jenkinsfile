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
      slaveConnectTimeout: 1200,
      idleMinutes: 20,
      yaml: manifest['MANIFEST']
    ){
      node(POD_LABEL){
        stage('Generate output file'){
          container('os-version-checker'){
            sh "cd /tmp; echo '${manifest['MANIFEST']}' > manifest.yaml; python3 VersionStatus.py -r stein,train,ussuri -f ${IMAGE_FILTERS} -m ${MAPPINGS}"
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
