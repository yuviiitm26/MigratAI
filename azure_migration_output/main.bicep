param containerAppName string
param containerImage string

resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2021-10-01' = {
  name: containerAppName
  location: 'eastus'
  properties: {
    containers: [
      {
        name: containerAppName
        properties: {
          image: containerImage
          resources: {
            requests: {
              cpu: 1
              memory: json('1.5')
            }
          }
          ports: [
            {
              port: 5000
              protocol: 'TCP'
            }
          ]
        }
      }
    ]
    osType: 'Linux'
    ipAddress: {
      type: 'Public'
      dnsNameLabel: 'migratai-demo-${containerAppName}'
      ports: [
        {
          port: 5000
          protocol: 'TCP'
        }
      ]
    }
  }
}