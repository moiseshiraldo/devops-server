from __future__ import print_function

from fabric.api import run, sudo, env, cd, prefix, put
from fabric.contrib import files
from fabric.state import output
from fabric.colors import green, red

import sys
import os

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.path.append('../')

from settings import *

system_packages = ("openjdk-7-jre openjdk-7-jdk")

env.hosts = HOSTS
env.user = USER
env.dir = JENKINS_DIR
env.use_ssh_config = SSH_CONFIG
env.ssl_cert_path = SSL_CERTIFICATE_PATH
env.ssl_key_path = SSL_CERTIFICATE_KEY_PATH

output['everything'] = False
output['aborts'] = False

def print_succeed():
    print("[", end="")
    print(green("OK"), end="")
    print("]")


def print_fail(exception):
    print("[", end="")
    print(red("Fail"), end="")
    print("]\n")
    print(exception)


class AbortException(Exception):
    pass

env.abort_exception = AbortException


def full_installation():
    install_system_packages()
    install_jenkins()
    config_webserver()
    restart_webserver()


def install_system_packages():
    print("Installing system packages. This could take a few minutes...",
          end="\t")
    try:
        sudo("apt-get update")
        sudo("apt-get -y install %s" % system_packages)
        print_succeed()
    except AbortException as e:
        print_fail(e)


def install_jenkins():
    print("Installing Jenkins...", end='\t')
    configure_jenkins()
    try:
        sudo("wget -q -O - https://jenkins-ci.org/debian/jenkins-ci.org.key | "
             "sudo apt-key add -")
        sudo("sudo sh -c 'echo deb http://pkg.jenkins-ci.org/debian binary/ > "
             "/etc/apt/sources.list.d/jenkins.list'")
        sudo("apt-get update")
        sudo("apt-get install jenkins")
        print_succeed()
    except AbortException as e:
        print_fail(e)

def configure_jenkins():
    print("Configuring Jenkins...", end="\t")
    try:
        files.upload_template(
            "../conf/jenkins/jenkins",
            "/etc/default/",
            context={'jenkins_dir': env.dir},
            use_sudo=True,
        )
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_webserver():
    if USE_SSL and USE_LETSENCRYPT:
        generate_ssl_certificate()
    print("Configuring webserver...", end="\t")
    try:
        if USE_SUBDOMAINS:
            if USE_SSL:
                files.upload_template(
                    "../conf/nginx/ssl-subdomain-jenkins",
                    "/etc/nginx/sites-available/",
                    context={
                        'server_name': SUBDOMAINS['jenkins'],
                        'certificate_path': env.ssl_cert_path,
                        'key_path': env.ssl_key_path,
                    },
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/ssl-subdomain-jenkins "
                     "/etc/nginx/sites-enabled/")
            else:
                files.upload_template(
                    "../conf/nginx/subdomain-jenkins",
                    "/etc/nginx/sites-available/",
                    context={'server_name': SUBDOMAINS['jenkins']},
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/subdomain-jenkins "
                     "/etc/nginx/sites-enabled/")
        else:
            put("../conf/nginx/location-jenkins", "/etc/nginx/sites-available/",
                use_sudo=True)
            if USE_SSL:
                files.upload_template(
                    "../conf/nginx/ssl-server",
                    "/etc/nginx/sites-available/",
                    context={
                        'server_name': DOMAIN,
                        'certificate_path': env.ssl_cert_path,
                        'key_path': env.ssl_key_path,
                    },
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/ssl-server "
                      "/etc/nginx/sites-enabled/")
            else:
                files.upload_template(
                    "../conf/nginx/server",
                    "/etc/nginx/sites-available/",
                    context={'server_name': DOMAIN},
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/server "
                      "/etc/nginx/sites-enabled/")
        put("../conf/nginx/graphite", "/etc/nginx/sites-available/",
                use_sudo=True)
        sudo("ln -nsf /etc/nginx/sites-available/graphite "
              "/etc/nginx/sites-enabled/")
        sudo("rm -f /etc/nginx/sites-enabled/default")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def generate_ssl_certificate():
    print("Generating ssl certificate...", end="\t")
    if USE_SUBDOMAINS:
        domain = SUBDOMAINS['jenkins']
        file_prefix = "jenkins"
    else:
        domain = DOMAIN
        file_prefix = "cert"
    try:
        key_path = "/etc/letsencrypt/live/%s/fullchain.pem" % domain
        if not files.exists(key_path, use_sudo=True):
            if not files.exists("/opt/letsencrypt/"):
                sudo("git clone https://github.com/letsencrypt/letsencrypt "
                     "/opt/letsencrypt")
            sudo("service nginx stop")
            if OPEN_SG:
                change_security_groups(OPEN_SG)
            output['stdout'] = True
            run("/opt/letsencrypt/letsencrypt-auto certonly --standalone "
                "--email %(email)s -d %(domain)s" % {
                    'email': EMAIL, 'domain': domain
                })
            output['stdout'] = False
            if RESTRICTED_SG:
                change_security_groups(RESTRICTED_SG)
        files.upload_template(
            "../conf/letsencrypt/cert-renew.ini",
            "/opt/letsencrypt/"+file_prefix+"-renew.ini",
            context={'email': EMAIL, 'domain': domain},
            use_sudo=True,
        )
        files.upload_template(
            "../conf/letsencrypt/cert-renew.sh",
            "/opt/letsencrypt/"+file_prefix+"-renew.sh",
            context={
                'domain': domain,
                'renew_conf': file_prefix+"-renew.ini",
                'instance_id': INSTANCE_ID,
                'open_sg': OPEN_SG,
                'restricted_sg': RESTRICTED_SG,
            },
            use_sudo=True,
        )
        files.upload_template(
            "../conf/letsencrypt/crontab",
            "/opt/letsencrypt/"+file_prefix+"-crontab",
            context={'renew_script': file_prefix+"-renew.sh"},
            use_sudo=True,
        )
        run("crontab /opt/letsencrypt/"+file_prefix+"-crontab")
        env.ssl_cert_path = "/etc/letsencrypt/live/%s/fullchain.pem" % domain
        env.ssl_key_path = "/etc/letsencrypt/live/%s/privkey.pem" % domain
        print_succeed()
    except AbortException as e:
        print_fail(e)


def change_security_groups(security_groups):
    run("aws ec2 modify-instance-attribute --instance-id %(instance_id)s "
        "--groups %(sg)s" % {'instance_id': INSTANCE_ID, 'sg': security_groups})


def restart_webserver():
    print("Restarting webserver...", end="\t")
    try:
        sudo("service jenkins restart")
        sudo("service nginx restart")
        print_succeed()
    except AbortException as e:
        print_fail(e)
