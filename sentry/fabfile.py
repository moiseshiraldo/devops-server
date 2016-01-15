from fabric.api import run, sudo, env, cd, prefix, put
from fabric.contrib import files
from contextlib import contextmanager as customcontextmanager

import sys
sys.path.append('../')
from settings import HOSTS, USER, SSH_CONFIG, SENTRY_DIR

system_packages = ("python-virtualenv python-pip python-setuptools python-dev "
                   "libxslt1-dev libxml2-dev libz-dev libffi-dev libssl-dev "
                   "libpq-dev libyaml-dev postgresql-contrib supervisor "
                   "redis-server nginx uwsgi uwsgi-plugin-python git")

env.hosts = HOSTS
env.user = USER
env.dir = SENTRY_DIR
env.activate = "source "+env.dir+"/bin/activate"
env.use_ssh_config = SSH_CONFIG


@customcontextmanager
def virtualenv():
    with cd(env.dir):
        with prefix(env.activate):
            yield


def install_system_packages():
    sudo("apt-add-repository -y ppa:chris-lea/redis-server")
    sudo("apt-get update")
    sudo("apt-get -y install %s" % system_packages)


def create_virtualenv():
    run("virtualenv "+env.dir)


def install_sentry():
    if not files.exists(env.dir):
        create_virtualenv()
    with virtualenv():
        run("pip install -U sentry")
        run("mkdir %s/conf" % env.dir)
        run("sentry init %s/conf" % env.dir)


def config_sentry():
    put("../conf/sentry/sentry.conf.py", "%s/conf/" % env.dir)


def create_db_user():
    query = "SELECT 1 FROM pg_roles WHERE rolname='dashboard';"
    if not sudo("psql -tAc \""+query+"\"", user="postgres"):
        sudo("psql -c \"CREATE USER dashboard WITH PASSWORD 'dashboard';\"",
             user="postgres")


def db_exists(name):
    query = "SELECT 1 FROM pg_database WHERE datname = '%s';" % name
    return sudo("psql -tAc \""+query+"\"", user="postgres")


def create_db():
    create_db_user()
    if not db_exists("sentry"):
        sudo("psql -c 'CREATE DATABASE sentry;'", user="postgres")
    sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE sentry TO dashboard;'",
         user="postgres")

def config_db():
    put("../conf/postgresql/pg_hba.conf", "/etc/postgresql/9.3/main/",
        use_sudo=True)
    sudo("service postgresql restart")


def sync_db():
    with virtualenv():
        run("SENTRY_CONF=%s/conf sentry upgrade" % env.dir)


def create_user():
    with virtualenv():
        run("SENTRY_CONF=%s/conf sentry createuser" % env.dir)


def config_supervisor():
    files.upload_template(
        "../conf/supervisor/sentry.conf",
        "/etc/supervisor/conf.d/",
        context={'dir': env.dir, 'user': env.user},
        use_sudo=True,
    )
    sudo("service supervisor restart")


def config_webserver():
    put("../conf/nginx/location-sentry", "/etc/nginx/sites-available/",
        use_sudo=True)
    put("../conf/nginx/server", "/etc/nginx/sites-available/", use_sudo=True)
    if not files.exists("/etc/nginx/sites-enabled/server"):
        sudo("ln -s /etc/nginx/sites-available/server "
             "/etc/nginx/sites-enabled/")
    sudo("rm -f /etc/nginx/sites-enabled/default")
    put("../conf/uwsgi/sentry.ini", "/etc/uwsgi/apps-available/",
        use_sudo=True)
    files.upload_template(
        "../conf/uwsgi/sentry.ini",
        "/etc/uwsgi/apps-available/",
        context={'dir': env.dir},
        use_sudo=True,
    )
    if not files.exists("/etc/uwsgi/apps-enabled/sentry.ini"):
        sudo("ln -s /etc/uwsgi/apps-available/sentry.ini "
             "/etc/uwsgi/apps-enabled/")
    restart_webserver()


def restart_redis():
    sudo("service redis-server restart")


def restart_webserver():
    sudo("service uwsgi restart")
    sudo("service nginx restart")
