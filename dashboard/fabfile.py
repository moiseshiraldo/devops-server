from __future__ import print_function

from fabric.api import run, sudo, env, cd, prefix, put
from fabric.contrib import files
from contextlib import contextmanager as customcontextmanager
from fabric.state import output
from fabric.colors import green, red

import sys
import os

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.path.append('../')

from settings import *

system_packages = ("git python-pip nginx libcairo2-dev python-cairo libffi-dev "
                   "libssl-dev libboost-python-dev fontconfig bc postgresql "
                   "postgresql-contrib libpq-dev adduser libfontconfig "
                   "nodejs npm devscripts debhelper python-virtualenv uwsgi "
                   "uwsgi-plugin-python python-psycopg2")

env.hosts = HOSTS
env.user = USER
env.dir = GRAPHITE_DIR
env.activate = "source " + env.dir + "/bin/activate"
env.use_ssh_config = SSH_CONFIG
env.ssl_cert_path = SSL_CERTIFICATE_PATH
env.ssl_key_path = SSL_CERTIFICATE_KEY_PATH

output['everything'] = False
output['aborts'] = False


@customcontextmanager
def virtualenv():
    with cd(env.dir):
        with prefix(env.activate):
            yield


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
    create_virtualenv()
    install_pip_packages()
    install_graphite()
    install_grafana()
    install_statsd()
    create_db_user()
    create_db()
    config_graphite()
    config_grafana()
    config_statsd()
    config_webserver()
    sync_db()
    restart_carbon()
    restart_statsd()
    restart_grafana()
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


def create_virtualenv():
    print("Creating virtual environment...", end="\t")
    try:
        run("virtualenv "+env.dir)
        print_succeed()
    except AbortException as e:
        print_fail(e)


def install_pip_packages():
    print("Installing pip packages...", end="\t")
    try:
        with virtualenv():
            put("requirements.txt", "~/")
            run("pip install -r ~/requirements.txt")
            run("rm -f ~/requirements.txt")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def install_graphite():
    print("Installing Graphite. This could take a few minutes...", end="\t")
    try:
        with virtualenv():
            run("pip install "
                "https://github.com/graphite-project/ceres/tarball/master")
            run("pip install whisper")
            run("pip install carbon --install-option='--prefix=%(dir)s' "
                "--install-option='--install-lib=%(dir)s/lib'" % {
                    'dir': env.dir
                })
            run("pip install graphite-web --install-option='--prefix=%(dir)s' "
                "--install-option='--install-lib=%(dir)s/webapp'" % {
                    'dir': env.dir
                })
        print_succeed()
    except AbortException as e:
        print_fail(e)


def install_grafana():
    print("Installing Grafana...", end="\t")
    try:
        run("wget "+GET_GRAFANA)
        sudo("dpkg -i "+GRAFANA_DEB)
        sudo("rm -f "+GRAFANA_DEB)
        print_succeed()
    except AbortException as e:
        print_fail(e)


def install_statsd():
    print("Installing Statsd...", end="\t")
    try:
        run("git clone https://github.com/etsy/statsd.git")
        run("cd statsd && dpkg-buildpackage")
        sudo("dpkg -i statsd*.deb")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def create_db_user():
    print("Creating database user...", end="\t")
    query = "SELECT 1 FROM pg_roles WHERE rolname='dashboard';"
    try:
        if not sudo("psql -tAc \""+query+"\"", user="postgres"):
            sudo("psql -c \"CREATE USER dashboard WITH PASSWORD 'dashboard';\"",
                 user="postgres")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def db_exists(name):
    query = "SELECT 1 FROM pg_database WHERE datname = '%s';" % name
    return sudo("psql -tAc \""+query+"\"", user="postgres")


def create_db():
    print("Creating databases...", end="\t")
    try:
        if not db_exists("graphite"):
            sudo("psql -c 'CREATE DATABASE graphite;'", user="postgres")
        if not db_exists("grafana"):
            sudo("psql -c 'CREATE DATABASE grafana;'", user="postgres")
        sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE graphite TO "
             "dashboard;'", user="postgres")
        sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE grafana TO dashboard;'",
             user="postgres")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_graphite():
    print("Configuring Graphite...", end="\t")
    try:
        run("echo GRAPHITE_ROOT=%s >> .profile" % env.dir)
        with cd(env.dir):
            run("cp -f conf/carbon.conf.example conf/carbon.conf")
            run("cp -f conf/graphite.wsgi.example conf/graphite.wsgi")
        put("../conf/graphite/*.conf", "%s/conf/" % env.dir)
        files.upload_template(
            "../conf/graphite/local_settings.py",
            "%s/webapp/graphite/" % env.dir,
            context={'dir': env.dir},
        )
        sudo("chown -R www-data:www-data graphite/storage/")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_grafana():
    print("Configuring Grafana...", end="\t")
    root_url = "http://"
    if USE_SSL:
        root_url = "https://"
    if USE_SUBDOMAINS:
        root_url += SUBDOMAINS['grafana']
    else:
        root_url += DOMAIN + "/grafana"
    try:
        files.upload_template(
            "../conf/grafana/grafana.ini",
            "/etc/grafana/",
            context={'root_url': root_url},
            use_sudo=True,
        )
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_statsd():
    print("Configuring Statsd...", end="\t")
    try:
        put("../conf/statsd/localConfig.js", "/etc/statsd/", use_sudo=True)
        print_succeed()
    except AbortException as e:
        print_fail(e)


def sync_db():
    print("Synchronizing Graphite database...", end="\t")
    try:
        with virtualenv():
            run("python webapp/graphite/manage.py migrate auth")
            output['stdout'] = True
            run("python webapp/graphite/manage.py syncdb")
            output['stdout'] = False
        print_succeed()
    except AbortException as e:
        print_fail(e)


def restart_carbon():
    print("Restarting carbon daemon...", end="\t")
    try:
        with virtualenv():
            sudo("bin/carbon-cache.py stop")
            sudo("bin/carbon-cache.py start")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def restart_statsd():
    print("Restarting Statsd service...", end="\t")
    try:
        sudo("service statsd restart")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def restart_grafana():
    print("Restarting Grafana...", end="\t")
    try:
        sudo("service grafana-server restart")
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
                    "../conf/nginx/ssl-subdomain-grafana",
                    "/etc/nginx/sites-available/",
                    context={
                        'server_name': SUBDOMAINS['grafana'],
                        'certificate_path': env.ssl_cert_path,
                        'key_path': env.ssl_key_path,
                    },
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/ssl-subdomain-grafana "
                     "/etc/nginx/sites-enabled/")
            else:
                files.upload_template(
                    "../conf/nginx/subdomain-grafana",
                    "/etc/nginx/sites-available/",
                    context={'server_name': SUBDOMAINS['grafana']},
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/subdomain-grafana "
                     "/etc/nginx/sites-enabled/")
        else:
            put("../conf/nginx/location-grafana", "/etc/nginx/sites-available/",
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
        files.upload_template(
            "../conf/uwsgi/graphite.ini",
            "/etc/uwsgi/apps-available/",
            context={'dir': env.dir},
            use_sudo=True,
        )
        sudo("ln -nsf /etc/uwsgi/apps-available/graphite.ini "
             "/etc/uwsgi/apps-enabled/")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def generate_ssl_certificate():
    print("Generating ssl certificate...", end="\t")
    if USE_SUBDOMAINS:
        domain = SUBDOMAINS['grafana']
        file_prefix = "grafana"
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
            output['stdout'] = True
            run("/opt/letsencrypt/letsencrypt-auto certonly --standalone "
                "--email %(email)s -d %(domain)s" % {
                    'email': EMAIL, 'domain': domain
                })
            output['stdout'] = False
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


def restart_webserver():
    print("Restarting webserver...", end="\t")
    try:
        sudo("service uwsgi restart")
        sudo("service nginx restart")
        print_succeed()
    except AbortException as e:
        print_fail(e)
