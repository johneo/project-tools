# Fabric configuration file for automated deployment
# Mostly from: http://lethain.com/entry/2008/nov/04/deploying-django-with-fabric/
#
import subprocess
import os
import aws
import time
import sys

from fabric.api import run, sudo, put, env, require, local, settings
from fabric.contrib.files import comment, uncomment, contains, exists, append, sed


# The git origin is where we the repo is.
# Use the user@host syntax
GIT_ORIGIN = '' # git@github.com

# Github api token
GIT_API_TOKEN = '' # get from github

# Github account
GIT_ACCOUNT = '' # johnnydobbins

# Github project
GIT_PROJECT = '' # DjangoProjectExample

# The git repo is the repo we should clone
GIT_REPO = GIT_ACCOUNT + "/" + GIT_PROJECT + ".git"

# The AWS Key Pair
AWS_KEY = '' # /Users/johnnydobbins/Documents/code/aws/inspired.pem

# The deploy id_rsa and id_rsa.pub location
RSA_LOCATION = '' # /Users/johnnydobbins/.ssh/aws-deploy/

# import creds from non version controlled file
try:
    from creds import *
except ImportError:
    pass

# These are the packages we need to install using APT
INSTALL_PACKAGES = [
            "ntp",
            "vim",
            "unzip",
            "python2.6",
            "python2.6-dev",
            "libxml2-dev",
            "libxslt1-dev",
            "python-libxml2",
            "python-setuptools",
            "git-core",
            "build-essential",
            "libpcre3-dev",
            "libpcrecpp0",
            "libssl-dev",
            "zlib1g-dev",
            "libgeoip-dev",
            "memcached",
            "libmemcached-dev",
            #"python-coverage",
            #"python-imaging",
            "python-memcache",
            "postgresql-8.4",
            "postgresql-8.4-postgis",
            "postgresql-client-8.4",
            "postgresql-client-common",
            "postgresql-common",
            "libgeos-3.1.0",
            "libgeos-dev",
            "libproj-dev",
            "proj",
            "proj-bin",
            "proj-data",
            "libgdal1-1.6.0",
            "libgdal1-dev",
            "python-gdal", 
            "gdal-bin",
           ]

#### Environments

def production():
    "Setup production settings"
    env.node = aws.provision_with_boto('production-appserver')
    env.hosts = [env.node.hostname]

    env.repo = ("env.example.com", "origin", "release")
    env.virtualenv, env.parent, env.branch = env.repo
    env.base = "/server"
    env.user = "ubuntu"
    env.git_origin = GIT_ORIGIN
    env.git_repo = GIT_REPO
    env.dev_mode = False
    env.key_filename = AWS_KEY

def staging():
    "Setup staging settings"
    env.node = aws.provision_with_boto('staging-appserver')
    env.hosts = [env.node.hostname]
    
    env.repo = ("env.example.com", "origin", "stage")
    env.base = "/server"
    env.virtualenv, env.parent, env.branch = env.repo
    env.user = "ubuntu"
    env.git_origin = GIT_ORIGIN
    env.git_repo = GIT_REPO
    env.dev_mode = False
    env.key_filename = AWS_KEY

def vagrant():
    "Setup local vagrant instance"
    raw_ssh_config = subprocess.Popen(["vagrant", "ssh-config"], stdout=subprocess.PIPE).communicate()[0]
    ssh_config = dict([l.strip().split() for l in raw_ssh_config.split("\n") if l])
    env.repo = ("env.example.com", "origin", "master")
    env.virtualenv, env.parent, env.branch = env.repo
    env.base = "/server"
    env.user = ssh_config["User"]
    env.hosts = ["127.0.0.1:%s" % (ssh_config["Port"])]
    env.key_filename = ssh_config["IdentityFile"]
    env.git_origin = GIT_ORIGIN
    env.git_repo = GIT_REPO
    env.dev_mode = True

#### End Environments

#### Vagrant

def setup_vagrant():
    "Bootstraps the Vagrant environment"
    require('hosts', provided_by=[vagrant])
    sub_setup_ssh()
    sub_stop_processes()   # Stop everything
    sub_install_packages() # Get the installed packages
    sub_build_packages()   # Build some stuff
    sub_get_virtualenv()   # Download virtualenv
    sub_make_virtualenv()  # Build the virtualenv
    sub_simple_git_clone()
    sub_get_requirements() # Get the requirements (pip install)
    copy_wsgi_config()
    sub_get_admin_media()  # Copy Django admin media over
    sudo("usermod -aG vagrant www-data") # Add www-data to the vagrant group
    sub_copy_memcached_config() # Copies the memcache config
    config_postgres()   # reinit postgres with UTF-8 and setup users
    config_postgis_template()   # setup postgis template
    config_postgis() # create test postgis database
    sub_start_processes()  # Start everything
    configure_gis_example_project()

#### End Vagrant

#### Host Bootstrapping

def bootstrap():
    "Bootstraps the dreamhost environment"
    require('hosts', provided_by=[staging, production])
    sub_stop_processes() # Stop everything
    sub_install_packages() # Get the installed packages
    sub_build_packages()   # Build some stuff
    sub_get_virtualenv()   # Download virtualenv
    sub_make_virtualenv()  # Build the virtualenv
    sub_setup_ssh()        # Copy the SSH keys over
    sub_simple_git_clone() #
    sub_get_requirements() # Get the requirements (pip install)
    sub_get_admin_media()  # Copy Django admin media over
    copy_wsgi_config()
    sub_copy_memcached_config() # Copies the memcache config
    config_postgres()   # reinit postgres with UTF-8 and setup users
    config_postgis_template()   # setup postgis template
    config_postgis() # create test postgis database
    sub_start_processes()  # Start everything
    configure_gis_example_project()

def sub_install_packages():
    "Installs necessary packages on host"
    sudo("apt-get update")
    package_str = " ".join(INSTALL_PACKAGES)
    sudo("apt-get -y install "+package_str)
    sudo("easy_install pip")

def sub_build_packages():
    "Build some of the packages we need"
    sub_build_uwsgi()
    sub_build_nginx()

def sub_build_uwsgi():
    "Builds uWSGI"
    sudo("mkdir -p /usr/src/uwsgi")
    sudo("""cd /usr/src/uwsgi; if [ ! -e uwsgi-0.9.8.1.tar.gz ]; then \
       wget 'http://projects.unbit.it/downloads/uwsgi-0.9.8.1.tar.gz'; \
       tar xfz uwsgi-0.9.8.1.tar.gz; \
       cd uwsgi-0.9.8.1; \
       make; \
       cp uwsgi /usr/local/sbin;
       fi""")
    put("config/uwsgi.conf","/etc/init/uwsgi.conf",use_sudo=True)

def sub_build_nginx():
    "Builds NginX"
    sudo("mkdir -p /usr/src/nginx")
    sudo("""cd /usr/src/nginx; if [ ! -e nginx-1.0.4.tar.gz ]; then
       wget 'http://nginx.org/download/nginx-1.0.4.tar.gz' ; \
       tar xfz nginx-1.0.4.tar.gz; \
       cd nginx-1.0.4/; \
       ./configure --pid-path=/var/run/nginx.pid \
       --conf-path=/etc/nginx/nginx.conf \
       --sbin-path=/usr/local/sbin \
       --user=www-data \
       --group=www-data \
       --http-log-path=/var/log/nginx/access.log \
       --error-log-path=/var/log/nginx/error.log \
       --with-http_stub_status_module \
       --with-http_ssl_module \
       --with-http_realip_module \
       --with-sha1-asm \
       --with-sha1=/usr/lib \
       --http-fastcgi-temp-path=/var/tmp/nginx/fcgi/ \
       --http-proxy-temp-path=/var/tmp/nginx/proxy/ \
       --http-client-body-temp-path=/var/tmp/nginx/client/ \
       --with-http_geoip_module \
       --with-http_gzip_static_module \
       --with-http_sub_module \
       --with-http_addition_module \
       --with-file-aio \
       --without-mail_smtp_module; make ; make install;
       fi
       """)
    sudo("mkdir -p /var/tmp/nginx; chown www-data /var/tmp/nginx")
    put("config/nginx.conf","/etc/init/nginx.conf",use_sudo=True)
    sudo("cd /etc/nginx; mkdir -p sites-available sites-disabled sites-enabled")
    copy_nginx_config()

def copy_nginx_config():
    "Copies the NginX config over"
    put("config/nginx/backends.conf","/etc/nginx/backends.conf",use_sudo=True)
    put("config/nginx/nginx.conf","/etc/nginx/nginx.conf",use_sudo=True)
    put("config/nginx/example.com","/etc/nginx/sites-available/",use_sudo=True)
    sudo("ln -f -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/example.com")
    if env.dev_mode:
        put("config/nginx/dev.example.com","/etc/nginx/sites-available/",use_sudo=True)
        sudo("ln -f -s /etc/nginx/sites-available/dev.example.com /etc/nginx/sites-enabled/dev.example.com")

def copy_wsgi_config():
    put("config/uwsgi/wsgi.py","%(base)s/%(virtualenv)s/wsgi.py" % env)


def sub_get_virtualenv():
    "Fetches the virtualenv package"
    run("if [ ! -e virtualenv-1.6.1.tar.gz ]; then wget http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.6.1.tar.gz; fi")
    run("if [ ! -d virtualenv-1.6.1 ]; then tar xzf virtualenv-1.6.1.tar.gz; fi")
    run("rm -f virtualenv")
    run("ln -s virtualenv-1.6.1 virtualenv")

def sub_make_virtualenv():
    "Makes the virtualenv"
    sudo("if [ ! -d %(base)s ]; then mkdir -p %(base)s; chmod 777 %(base)s; fi" % env)
    run("if [ ! -d %(base)s/%(virtualenv)s ]; then python ~/virtualenv/virtualenv.py --no-site-packages %(base)s/%(virtualenv)s; fi" % env)
    sudo("chmod 777 %(base)s/%(virtualenv)s" % env)

def sub_setup_ssh():
    """
    Create host ssh id_rsa and id_rsa.pub keys if they do not exist and add to github as a deploy key
    """
    # check for and create if necessary the RSA_lOCATION
    if not os.path.exists(RSA_LOCATION):
        os.makedirs(RSA_LOCATION)

    # check to see if the ssh keys are created
    if not os.path.exists(RSA_LOCATION + "id_rsa"):
        bashcommand = "cd %s; ssh-keygen -f id_rsa -t rsa -N ''" % RSA_LOCATION
        os.system(bashcommand)

        # add the id_rsa.pub to github for deploy keys
        pub = open(RSA_LOCATION + "id_rsa.pub").readlines()[0].replace("\n", "")
        deploy_key = """curl -X POST -F "login=%s" -F "token=%s" https://github.com/api/v2/json/repos/key/%s/%s/add -F "title=Deploy" -F "key=%s" """ % (GIT_ACCOUNT, GIT_API_TOKEN, GIT_ACCOUNT, GIT_PROJECT, pub)
        os.system(deploy_key)

    # create the deploy host .ssh folder
    run("mkdir -p ~/.ssh/")

    # put the ssh keys on the deploy host
    put(RSA_LOCATION + "id_rsa", "/home/%(user)s/.ssh/id_rsa" % env, mode=0600)
    put(RSA_LOCATION + "id_rsa.pub", "/home/%(user)s/.ssh/id_rsa.pub" % env, mode=0600)

    # put a preset known_hosts file on the deploy host to make it aware of github for deploys
    put("config/known_hosts", "/home/%(user)s/.ssh/known_hosts" % env, mode=0600)

    if env.dev_mode:
        sudo('cp -f /etc/sudoers /tmp/sudoers.tmp')
        append('/tmp/sudoers.tmp', "vagrant ALL=(ALL) ALL", use_sudo=True)
        sudo('visudo -c -f /tmp/sudoers.tmp')
        sudo('cp -f /tmp/sudoers.tmp /etc/sudoers')
        sudo('rm -rf /tmp/sudoers.tmp')

def sub_simple_git_clone():
    "Clones a repository into the virtualenv at /project"
    run("cd %(base)s/%(virtualenv)s; git clone %(git_origin)s:%(git_repo)s project;" % env)

def sub_get_requirements():
    "Gets the requirements for the project"
    sudo("cd %(base)s/%(virtualenv)s; source bin/activate; pip install -r project/requirements.txt" % env)

def sub_get_admin_media():
    "Copies over the required admin media files"
    run("mkdir -p %(base)s/%(virtualenv)s/public/media; cd %(base)s/%(virtualenv)s/public/media; if [ ! -d admin-media ]; then cp -R %(base)s/%(virtualenv)s/lib/python2.6/site-packages/django/contrib/admin/media admin-media; fi" % env)

def sub_copy_memcached_config():
    "Copies the memcached config files over"
    put("config/memcached.conf","/etc/memcached.conf",use_sudo=True)

def sub_start_processes():
    "Starts NginX and uWSGI"
    sudo("start nginx")
    sudo("start uwsgi")
    sudo("nohup /etc/init.d/postgresql-8.4 restart")
    sudo("nohup /etc/init.d/memcached restart")

def sub_stop_processes():
    "Stops Nginx and uWSGI"
    with settings(warn_only=True):
        sudo("stop nginx")
        sudo("stop uwsgi")
        sudo("/etc/init.d/postgresql-8.4 stop")
        sudo("/etc/init.d/memcached stop")

#### End Host Bootstrapping

#### Boto AWS EC2 Cleanup

def cleanup(node_name = None):
    config = aws.read_config()
    if node_name:
        if config.has_section(node_name):
            aws.terminate_instance(node_name)
    else:
        for section in config.sections():
            aws.terminate_instance(section)

def destroy():
    aws.terminate_all_instances()

#### End Boto AWS EC2 Cleanup

#### Configure Postgres

def config_postgres():
    """
    For wierd reasons, we need to drop the cluster and recreate it to use UTF8
    for psql8.4 and ubuntu 10.04 only I think.
    
    --consider pulling the apt-get postgres parts into this section
    """
    sudo("/etc/init.d/postgresql-8.4 stop")
    sudo("pg_dropcluster --stop 8.4 main")
    sudo("pg_createcluster --start -e UTF-8 --locale=C 8.4 main")
    put("config/postgresql/pg_hba.conf","/etc/postgresql/8.4/main/pg_hba.conf",use_sudo=True)
    sudo("/etc/init.d/postgresql-8.4 restart")
    run("sudo -u postgres createuser --superuser inspired")
    run("createdb -U inspired inspired_media")

def config_postgis_template():
    """
    setup the default postgis template
    
    --consider pulling the apt-get postgis parts into this section
    """
    run("export POSTGIS_SQL_PATH=/usr/share/postgresql-8.4-postgis/")
    run("createdb -U postgres -E UTF8 template_postgis")
    run("createlang -U postgres plpgsql template_postgis")
    run("""psql -U postgres -d postgres -c "UPDATE pg_database SET datistemplate='true' WHERE datname='template_postgis';" """)
    run("psql -U postgres -d template_postgis -f /usr/share/postgresql/8.4/contrib/postgis.sql")

def config_postgis():
    """
    create a postgis enabled database
    """
    run("createdb -U inspired inspired_media_gis -T template_postgis")
    # don't need these since part of the template
    #run("createlang plpgsql inspired_media_gis -U inspired")
    #run("psql -U inspired -d inspired_media_gis < /usr/share/postgresql/8.4/contrib/postgis.sql")
    run("psql -U inspired -d inspired_media_gis < /usr/share/postgresql/8.4/contrib/postgis_comments.sql")
    run("psql -U inspired -d inspired_media_gis < /usr/share/postgresql/8.4/contrib/spatial_ref_sys.sql")

#### End Configure Postgres

#### Setup Example GIS GeoDjango Project

def configure_gis_example_project():
    """
    expects default_project to have ran first
    modifies settings and urls

    copy settings
    copy urls
    run syncdb
    
    """
    put("config/django/auth_users.json", "%(base)s/%(virtualenv)s/project/auth_users.json" % env)
    run("cd %(base)s/%(virtualenv)s; source bin/activate; cd project; python manage.py schemamigration world --initial" % env)
    run("cd %(base)s/%(virtualenv)s; source bin/activate; cd project; python manage.py syncdb --noinput; python manage.py migrate --noinput; python manage.py loaddata auth_users.json" % env)
    sudo("rm -rf %(base)s/%(virtualenv)s/project/auth_users.json" % env)
    load_gis_example_world_borders_data()
    
def load_gis_example_world_borders_data():
    """
    """
    run("cd %(base)s/%(virtualenv)s; source bin/activate; cd project; python manage.py loadgis" % env)
    