# Set hosts and user to make the ssh connection
HOSTS = ['dashboard']
USER = 'ubuntu'

# By default use the ssh configuration at ~/.ssh/config
SSH_CONFIG = True

# The environment directories to install graphite and sentry
GRAPHITE_DIR = "/home/ubuntu/graphite"
SENTRY_DIR = "/home/ubuntu/sentry"

# Grafana version
GRAFANA_DEB = "grafana_2.6.0_amd64.deb"
GET_GRAFANA = "https://grafanarel.s3.amazonaws.com/builds/"+GRAFANA_DEB

