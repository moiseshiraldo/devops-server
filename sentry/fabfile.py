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

system_packages = ("python-virtualenv python-pip python-setuptools python-dev "
                   "libxslt1-dev libxml2-dev libz-dev libffi-dev libssl-dev "
                   "libpq-dev libyaml-dev bc postgresql-contrib supervisor "
                   "redis-server nginx uwsgi uwsgi-plugin-python git")

env.hosts = HOSTS
env.user = USER
env.dir = SENTRY_DIR
env.activate = "source "+env.dir+"/bin/activate"
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
    install_sentry()
    config_sentry()
    create_db_user()
    create_db()
    config_db()
    sync_db()
    config_supervisor()
    config_webserver()
    restart_redis()
    restart_webserver()


def install_system_packages():
    print("Installing system packages. This could take a few minutes...",
          end="\t")
    try:
        sudo("apt-add-repository -y ppa:chris-lea/redis-server")
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


def install_sentry():
    print("Installing sentry. This could take a few minutes...", end="\t")
    try:
        with virtualenv():
            run("pip install -U sentry")
            run("mkdir %s/conf" % env.dir)
            run("sentry init %s/conf" % env.dir)
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_sentry():
    print("Configuring sentry...", end="\t")
    try:
        put("../conf/sentry/sentry.conf.py", "%s/conf/" % env.dir)
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
    print("Creating database...", end="\t")
    try:
        if not db_exists("sentry"):
            sudo("psql -c 'CREATE DATABASE sentry;'", user="postgres")
        sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE sentry TO dashboard;'",
             user="postgres")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def config_db():
    print("Configuring PostgreSQL...", end="\t")
    try:
        put("../conf/postgresql/pg_hba.conf", "/etc/postgresql/9.3/main/",
            use_sudo=True)
        sudo("service postgresql restart")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def sync_db():
    print("Synchronizing database...", end="\t")
    try:
        with virtualenv():
            output['stdout'] = True
            run("SENTRY_CONF=%s/conf sentry upgrade" % env.dir)
            output['stdout'] = False
        print_succeed()
    except AbortException as e:
        print_fail(e)


def create_user():
    with virtualenv():
        run("SENTRY_CONF=%s/conf sentry createuser" % env.dir)


def config_supervisor():
    print("Configuring supervisor for sentry-worker...", end="\t")
    try:
        files.upload_template(
            "../conf/supervisor/sentry.conf",
            "/etc/supervisor/conf.d/",
            context={'dir': env.dir, 'user': env.user},
            use_sudo=True,
        )
        sudo("service supervisor restart")
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
                    "../conf/nginx/ssl-subdomain-sentry",
                    "/etc/nginx/sites-available/",
                    context={
                        'server_name': SUBDOMAINS['sentry'],
                        'certificate_path': env.ssl_cert_path,
                        'key_path': env.ssl_key_path,
                    },
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/ssl-subdomain-sentry "
                     "/etc/nginx/sites-enabled/")
            else:
                files.upload_template(
                    "../conf/nginx/subdomain-sentry",
                    "/etc/nginx/sites-available/",
                    context={'server_name': SUBDOMAINS['sentry']},
                    use_sudo=True,
                )
                sudo("ln -nsf /etc/nginx/sites-available/subdomain-sentry "
                     "/etc/nginx/sites-enabled/")
        else:
            put("../conf/nginx/location-sentry", "/etc/nginx/sites-available/",
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
        sudo("rm -f /etc/nginx/sites-enabled/default")
        files.upload_template(
            "../conf/uwsgi/sentry.ini",
            "/etc/uwsgi/apps-available/",
            context={'dir': env.dir},
            use_sudo=True,
        )
        if not files.exists("/etc/uwsgi/apps-enabled/sentry.ini"):
            sudo("ln -s /etc/uwsgi/apps-available/sentry.ini "
                 "/etc/uwsgi/apps-enabled/")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def generate_ssl_certificate():
    print("Generating ssl certificate...", end="\t")
    if USE_SUBDOMAINS:
        domain = SUBDOMAINS['sentry']
        file_prefix = "sentry"
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
                'renew_conf': file_prefix+"-renew.ini",
                'domain': domain,
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


def restart_redis():
    print("Restarting redis server...", end="\t")
    try:
        sudo("service redis-server restart")
        print_succeed()
    except AbortException as e:
        print_fail(e)


def restart_webserver():
    print("Restarting webserver...", end="\t")
    try:
        sudo("service uwsgi restart")
        sudo("service nginx restart")
    except AbortException as e:
        print_fail(e)
