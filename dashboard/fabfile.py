from fabric.api import run, sudo, env, cd, prefix, put, upload_template
from fabric.contrib import files
from contextlib import contextmanager as customcontextmanager

system_packages = ("git python-pip nginx libcairo2-dev python-cairo libffi-dev "
                   "libssl-dev libboost-python-dev fontconfig postgresql "
                   "postgresql-contrib libpq-dev adduser libfontconfig "
                   "nodejs npm devscripts debhelper python-virtualenv uwsgi "
                   "uwsgi-plugin-python python-psycopg2")

env.hosts = ['dashboard']
env.dir = "/home/ubuntu/graphite"
env.activate = "source "+env.dir+"/bin/activate"
env.use_ssh_config = True


@customcontextmanager
def virtualenv():
    with cd(env.dir):
        with prefix(env.activate):
            yield


def install_system_packages():
    sudo("apt-get update")
    sudo("apt-get -y install %s" % system_packages)


def create_virtualenv():
    run("virtualenv "+env.dir)


def install_pip_packages():
    if not files.exists(env.dir):
        create_virtualenv()
    with virtualenv():
        put("requirements.txt", "~/")
        run("pip install -r ~/requirements.txt")
        run("rm -f ~/requirements.txt")


def install_graphite():
    if not files.exists(env.dir):
        create_virtualenv()
    with virtualenv():
        run("pip install "
            "https://github.com/graphite-project/ceres/tarball/master")
        run("pip install whisper")
        run("pip install carbon --install-option='--prefix=%(dir)s' "
            "--install-option='--install-lib=%(dir)s/lib'" % {'dir': env.dir})
        run("pip install graphite-web --install-option='--prefix=%(dir)s' "
            "--install-option='--install-lib=%(dir)s/webapp'" %
            {'dir': env.dir})


def install_grafana():
    run("wget "
        "https://grafanarel.s3.amazonaws.com/builds/grafana_2.6.0_amd64.deb")
    sudo("dpkg -i grafana_2.6.0_amd64.deb")
    sudo("rm -f grafana_2.6.0_amd64.deb")


def install_statsd():
    run("git clone https://github.com/etsy/statsd.git")
    run("cd statsd && dpkg-buildpackage")
    sudo("dpkg -i statsd*.deb")


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
    if not db_exists("graphite"):
        sudo("psql -c 'CREATE DATABASE graphite;'", user="postgres")
    if not db_exists("grafana"):
        sudo("psql -c 'CREATE DATABASE grafana;'", user="postgres")
    sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE graphite TO dashboard;'",
         user="postgres")
    sudo("psql -c 'GRANT ALL PRIVILEGES ON DATABASE grafana TO dashboard;'",
         user="postgres")


def config_graphite():
    run("echo GRAPHITE_ROOT=%s >> .profile" % env.dir)
    with cd(env.dir):
        run("cp -f conf/carbon.conf.example conf/carbon.conf")
        run("cp -f conf/graphite.wsgi.example conf/graphite.wsgi")
    put("../conf/graphite/*.conf", "%s/conf/" % env.dir)
    upload_template(
        "../conf/graphite/local_settings.py",
        "%s/webapp/graphite/" % env.dir,
        context={'dir': env.dir},
    )
    sudo("chown -R www-data:www-data graphite/storage/")


def config_grafana():
    put("../conf/grafana/grafana.ini", "/etc/grafana/", use_sudo=True)


def config_statsd():
    put("../conf/statsd/localConfig.js", "/etc/statsd/", use_sudo=True)


def sync_db():
    with virtualenv():
        run("python webapp/graphite/manage.py migrate auth")
        run("python webapp/graphite/manage.py syncdb")


def restart_carbon():
    with virtualenv():
        sudo("bin/carbon-cache.py stop")
        sudo("bin/carbon-cache.py start")


def restart_statsd():
    sudo("service statsd restart")


def restart_grafana():
    sudo("service grafana-server restart")


def config_webserver():
    put("../conf/nginx/graphite", "/etc/nginx/sites-available/", use_sudo=True)
    put("../conf/nginx/grafana", "/etc/nginx/sites-available/", use_sudo=True)
    if not files.exists("/etc/nginx/sites-enabled/graphite"):
        sudo("ln -s /etc/nginx/sites-available/graphite "
             "/etc/nginx/sites-enabled/")
    if not files.exists("/etc/nginx/sites-enabled/grafana"):
        sudo("ln -s /etc/nginx/sites-available/grafana "
             "/etc/nginx/sites-enabled/")
    sudo("rm -f /etc/nginx/sites-enabled/default")
    upload_template(
        "../conf/uwsgi/graphite.ini",
        "/etc/uwsgi/apps-available/",
        context={'dir': env.dir},
        use_sudo=True,
    )
    if not files.exists("/etc/uwsgi/apps-enabled/graphite.ini"):
        sudo("ln -s /etc/uwsgi/apps-available/graphite.ini "
             "/etc/uwsgi/apps-enabled/")
    restart_webserver()


def restart_webserver():
    sudo("service uwsgi restart")
    sudo("service nginx restart")
