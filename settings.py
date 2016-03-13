# Set hosts and user to make the ssh connection
HOSTS = ['devops']
USER = 'ubuntu'

# By default use the ssh configuration at ~/.ssh/config
SSH_CONFIG = True

# The environment directories to install graphite and sentry
GRAPHITE_DIR = "/home/ubuntu/graphite"
SENTRY_DIR = "/home/ubuntu/sentry"
JENKINS_DIR = "home/ubuntu/jenkins"

# Grafana version
GRAFANA_DEB = "grafana_2.6.0_amd64.deb"
GET_GRAFANA = "https://grafanarel.s3.amazonaws.com/builds/"+GRAFANA_DEB

# Server name (www.example.com)
DOMAIN = ""

# By default use locations (example.com/grafana, example.com/sentry)
# Set this to True to use subdomains (grafana.example.com, sentry.example.com)
USE_SUBDOMAINS = False
SUBDOMAINS = {
    'grafana': "", # grafana.example.com
    'sentry': "",
    'jenkins': "",
}
USE_SSL = False

# If USE_SSL is True, the SSL certificate will be generated using Let's Encrypt
# Set this to False and specify the paths to use your own SSL certificate
USE_LETSENCRYPT = True
SSL_CERTIFICATE_PATH = ""
SSL_CERTIFICATE_KEY_PATH = ""
EMAIL = ""
