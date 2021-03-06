#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
import io
import datetime
import commentjson as json
import argparse
import re
import ConfigParser

from StringIO import StringIO

from fabric.api import local, run, sudo, settings, abort, env, get, hide
from fabric.contrib.console import confirm
from fabric.operations import prompt, put, get
from fabric.contrib.files import exists, upload_template, sed, append
from fabric.colors import green, red, blue
from fabric.context_managers import cd, shell_env

import random
import binascii
import dotenv


DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_VERSION = "0.1.5"
env.NODE_VERSION = "0.10.44"


"""
  ____ ___  _   _ _____ ___ ____
 / ___/ _ \| \ | |  ___|_ _/ ___|
| |  | | | |  \| | |_   | | |  _
| |__| |_| | |\  |  _|  | | |_| |
 \____\___/|_| \_|_|   |___\____|

"""

def dotenv_set(filepath, key, value):
    sudo(dotenv.get_cli_string(filepath, 'set', key, value), quiet=True)

def dotenv_get(filepath, key=None):
    out =  sudo(dotenv.get_cli_string(filepath, 'get', key), quiet=True)
    print out
    if "UserWarning" in out:
        return False
    else:
        return out[out.index('=')+1:].strip("\"'")

def read(remote_path):
    with hide('commands'):
        fd = StringIO()
        get(remote_path, fd)
        return fd.getvalue()


def read_env_file(filepath):
    env_file_content = read(filepath)
    config = parse_dotenv(io.BytesIO(env_file_content))
    return config

def parse_dotenv(f):
    config = {}
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        v = v.strip("'").strip('"')
        config[k] = v
    return config


def config_get_domain():
    # DOMAIN for vhosts
    if env.get('domains'):
        return False

    if target.get('domains'):
        env.domains = target.get('domains')
    else:
        env.domains = prompt('Set a list of domain names (comma separated) :')
        env.domains = env.domains.split(',')
    for i in env.domains:
        i = i.strip().lower()
    env.domain = env.domains[0]



def config_get_email():
    if env.get('email'):
        return False
    # EMAIL for sslcerts
    if args.email:
        env.email = args.email
    elif target.get('email'):
        env.email = target.get('email')
    else:
        env.email = prompt('SSL cert authority email :')
    env.email = env.email.lower()



"""
 _   _ _____ ___ _     ____
| | | |_   _|_ _| |   / ___|
| | | | | |  | || |   \___ \
| |_| | | |  | || |___ ___) |
 \___/  |_| |___|_____|____/

"""

def template(from_path, remote_path, ctxt=None):
    if not ctxt: ctxt = env
    upload_template(template_dir=DIR + '/templates/', filename=from_path, destination=remote_path, context=ctxt, use_sudo=True, use_jinja=True)


def which(program):
    path = sudo('/usr/bin/which %s' % program, quiet=True)
    if not len(path):
        return False
    else:
        return path




"""
 ____  _____ _____ _   _ ____
/ ___|| ____|_   _| | | |  _ \
\___ \|  _|   | | | | | | |_) |
 ___) | |___  | | | |_| |  __/
|____/|_____| |_|  \___/|_|

"""

def setup_struct(**kwargs):
    if exists("/opt/%(domain)s" % env):
        return False
    sudo('mkdir -p /var/log/%(domain)s' % env)
    sudo('mkdir -p /opt/%(domain)s/{backups,conf,data,logs,releases,var,etc}' % env)
    sudo('touch /opt/%(domain)s/.env' % env)


def setup_tools(**kwargs):

    # check if all tools are already setup
    with hide('commands'):
        sudo('mkdir -p /root/.starbase/')
        if exists("/root/.starbase/version") and sudo("cat /root/.starbase/version") == RELEASE_VERSION:
            return

    print(blue('Setup some boring unix tools...'))


    sudo('echo "" >> /etc/hosts')
    sudo('echo "127.0.1.1 `hostname`" >> /etc/hosts')


    with cd('/root'):

        # base build tools
        sudo('apt-get -qqy update')
        sudo('apt-get -qqy upgrade')
        sudo('apt-get -qqy install software-properties-common')
        sudo('apt-add-repository -y ppa:rwky/redis')
        sudo('apt-get -qqy update')

        # Base Packages
        sudo("apt-get -qqy install" + " ".join([
            ' curl fail2ban unzip whois zsh moreutils host',
            ' build-essential gcc git libmcrypt4 libpcre3-dev g++ make', # make tools
            ' make python-pip supervisor ufw unattended-upgrades',
        ]))

        hostname = sudo('hostname')
        sudo('debconf-set-selections <<< "postfix postfix/mailname string %s"' % hostname)
        sudo('debconf-set-selections <<< "postfix postfix/main_mailer_type string \'Internet Site\'"')
        sudo('apt-get -qqy postfix')

        setup_locale()

        # HTTPie
        sudo('pip install httpie')
        sudo('pip install python-dotenv')

    sudo('echo "%s" > /root/.starbase/version' % RELEASE_VERSION)



def setup_mongodb():

    print(blue('INSTALL MONGODB 3.2'))

    sudo('apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927')
    sudo('echo "deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.2.list')
    sudo('apt-get -qqy update')
    sudo('apt-get -qqy install mongodb-org')

    template('cron/mongodb', '/etc/cron.d/mongodb-backup')
    template('mongod.conf', '/etc/mongod.conf')

    mongo_setup_admin_user()

    sudo('service mongod start')


def mongo_setup_admin_user(**kwargs):

    env.dbname = "admin"
    env.dbuser = "starbaseAdmin"
    env.dbpassword = generate_password(16)
    sudo('mkdir /root/.starbase/mongo')
    dotenv_set('/root/.starbase/mongo/env', "MONGO_ADMIN_USER", "starbaseAdmin")
    dotenv_set('/root/.starbase/mongo/env', "MONGO_ADMIN_PWD", env.dbpassword)
    print(green('Setup MONGODB Admin user : %(dbuser)s / %(dbpassword)s' % env))
    script = "%(dbname)s.%(dbuser)s.js" % env
    template('mongodbcreateuser.js', "/root/.starbase/mongo/" + script)
    sudo('mongo /root/.starbase/mongo/' + script)


def mongo_create_db(dbname, dbuser = None, **kwargs):

    print(blue('Create MongoDB DB : %s' % dbname))

    # env.args
    if not exists('/root/.starbase/mongo'):
        mongo_setup_admin_user()
    else:
        mongousr = dotenv_get('/root/.starbase/mongo/env', "MONGO_ADMIN_USER")
        mongopwd = dotenv_get('/root/.starbase/mongo/env', "MONGO_ADMIN_PWD")

    env.dbname = dbname

    if dbuser: env.dbuser = dbuser
    else: env.dbuser = dbname

    script = "%(dbname)s.%(dbuser)s.js" % env

    if exists('/root/.starbase/mongo/%s' % script):
        abort(red('DB %(dbname)s with user %(dbuser)s already exists' % env))

    env.dbpassword = generate_password(16)

    template('mongodbcreateuser.js', "/root/.starbase/mongo/" + script)

    sudo('mongo admin -u %s -p %s /root/.starbase/mongo/%s' % (mongousr, mongopwd, script), quiet=True)

    print(green('Create MongoDB DB %(dbname)s with associated user :' % env))
    print(green('   =>  MONGO_URL="mongodb://%(dbuser)s:%(dbpassword)s@localhost/%(dbname)s"' % env))
    print(green('   => (remote) MONGO_URL="mongodb://%(dbuser)s:%(dbpassword)s@%(host_string)s/%(dbname)s"' % env))

    return (env.dbuser, env.dbpassword)


def mongo_delete_db(dbname, **kwargs):

    params = {
        "adminusr": dotenv_get('/root/.starbase/mongo/env', "MONGO_ADMIN_USER"),
        "adminpwd": dotenv_get('/root/.starbase/mongo/env', "MONGO_ADMIN_PWD"),
        "dbname": dbname
    }

    if not exists('/root/.starbase/mongo/%(dbname)s.%(dbname)s.js' % params):
        print(red('DB %(dbname)s does not exists' % params))
        return
    if not confirm(blue('Delete DB+user "%s" ?' % dbname), default=False):
        print('Deletion skipped.')
        return

    sudo('''mongo admin -u %(adminusr)s -p %(adminpwd)s --eval "db.getSiblingDB('%(dbname)s').dropUser('%(dbname)s');db.getSiblingDB('%(dbname)s').dropDatabase()"''' % params, quiet=True)
    # print sudo('''mongo admin -u %s -p %s --eval "db.getSiblingDB('%s').dropUser('%s')"''' % (mongousr, mongopwd, dbname, dbname), quiet=True)
    sudo('rm /root/.starbase/mongo/%(dbname)s.%(dbname)s.js' % params)
    print(green('DB & user "%s" successfuly deleted' % dbname))



def setup_nodejs(**kwargs):
    template('install_nodejs.sh', '/root/.starbase/')
    sudo('chmod u+x /root/.starbase/*.sh')
    sudo('/root/.starbase/install_nodejs.sh')



def setup_nginx(**kwargs):

    sudo('mkdir -p /etc/nginx/')

    sudo('apt-add-repository -y ppa:nginx/development') # on est des oufs
    sudo('apt-get -qqy update')
    sudo('apt-get -qqy install nginx')
    sudo('service nginx stop')
    # send default nginx config
    template('nginx.global.conf', '/etc/nginx/nginx.conf')
    template('index.html', '/var/www/html/index.html')

    # cleanup potential default file from ubuntu
    if exists('/etc/nginx/sites-available/default'):
        sudo('rm /etc/nginx/sites-available/default') # potential default file from ubuntu
        sudo('rm /etc/nginx/sites-enabled/default')

    # # default site if none found
    if not exists('/etc/nginx/sites-available/default.conf'):
        template('nginx.default.conf', '/etc/nginx/sites-available/default.conf')
        sudo('ln -fs /etc/nginx/sites-available/default.conf /etc/nginx/sites-enabled/')

    sudo('service nginx start')

    # build better cypher for SSL A+ grade ssl labs
    if not exists('/etc/nginx/dhparams.2048.pem'):
        sudo('openssl dhparam -out /etc/nginx/dhparams.2048.pem 2048')


def setup_ssl_certs(**kwargs):

    # @todos, check host is correctly hiting the server before launching letsencrypt

    print(blue('setup SSL cert generation'))

    if not exists('/usr/local/lib/letsencrypt'):
        print(green('fetch lets encrypt client'))
        sudo('git clone https://github.com/letsencrypt/letsencrypt /usr/local/lib/letsencrypt')
        sudo('service nginx reload')


    print(blue('create SSL certs'))

    env.ssl_dir = "/etc/letsencrypt/live/%(domain)s" % env

    # setup web root for let's encrypt
    sudo('mkdir -p /var/www/letsencrypt/' % env)

    sudo('/usr/local/lib/letsencrypt/letsencrypt-auto certonly --webroot -w /var/www/letsencrypt/ --agree-tos --domain %(domain)s --email %(email)s' % env)
    template('cron/certs-renewal', '/etc/cron.d/certs-renewal.%(domain)s' % env)
    env.enable_ssl = exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env)
    template('nginx.vhost.conf', '/etc/nginx/sites-available/%(domain)s.conf' % env)
    sudo('service nginx reload')


def setup_vhost(**kwargs):
    print(green('setup/reload vhosts'))
    setup_struct()

    env.app_pwd = '/opt/%(domain)s/releases/default/bundle' % env
    env.enable_ssl = exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env)

    # Setup envs
    env.env_vars = {
        "PATH": "/opt/local/bin:/opt/local/sbin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "NODE_PATH": "/usr/lib/nodejs:/usr/lib/node_modules:/usr/share/javascript",
        # set to home directory of the user Meteor will be running as
        "PWD": "%(app_pwd)s" % env,
        "HOME": "%(app_pwd)s" % env,
        "ROOT_URL": "https://%(domain)s" % env,
        # default bind email
        "MAIL_URL": "smtp://localhost",
        # leave as 127.0.0.1 for security
        "BIND_IP": "127.0.0.1",
        # the port nginx is proxying requests to
        "PORT": "%(app_node_port)s" % env,
        # this allows Meteor to figure out correct IP address of visitors
        "HTTP_FORWARDED_COUNT": "1",
        # meteor basic settings
        "METEOR_SETTINGS": "{}", # "$(cat /opt/%(domain)s/releases/latest/bundle/settings.json)" % env,
    }

    config = read_env_file("/opt/%(domain)s/.env" % env)
    env.env_vars.update(env.settings['env'])
    env.env_vars.update(config)

    template('nginx.vhost.conf', '/etc/nginx/sites-available/%(domain)s.conf' % env)
    template('upstart.conf', '/etc/init/%(domain)s.conf' % env)
    template('supervisord-program.conf', '/etc/supervisor/conf.d/%(domain)s.conf' % env)
    template('logrotate.conf', '/etc/logrotate.d/%(domain)s.conf' % env)

    sudo('ln -fs /etc/nginx/sites-available/%(domain)s.conf /etc/nginx/sites-enabled/' % env)
    sudo('service nginx reload')

    if not exists('/opt/%(domain)s/releases/default' % env):
        # create default DB & setup environment var for this one
        dbuser = re.sub('[^\w]', '', env.domain)
        dbuser, dbpassword = mongo_create_db(dbuser)
        dotenv_set("MONGO_URL", "mongodb://%s:%s@localhost/%s" % (dbuser, dbpassword, dbuser))

        sudo('mkdir -p /opt/%(domain)s/releases/default/bundle' % env)
        template('defaultapp.js', '/opt/%(domain)s/releases/default/bundle/main.js' % env)
        sudo('ln -fs /opt/%(domain)s/releases/default/bundle /opt/%(domain)s/releases/latest' % env)
    sudo('service %(domain)s restart' % env)


def setup_elasticsearch():
    if exists('/opt/%(domain)s/config/elasticsearch.yml' % env):
        return
    sudo('add-apt-repository -y ppa:webupd8team/java')
    sudo('apt-get -qqy update')
    sudo('apt-get -qqy install oracle-java8-installer')
    sudo('wget -qO - https://packages.elastic.co/GPG-KEY-elasticsearch | apt-key add -')
    sudo('echo "deb http://packages.elastic.co/elasticsearch/2.x/debian stable main" | tee -a /etc/apt/sources.list.d/elasticsearch-2.x.list')
    sudo('apt-get -qqy update')
    sudo('apt-get -qqy install elasticsearch')


def setup_locale(locale = "en_US", encoding="UTF-8", **kwargs):
    print(blue('Setup locale %s' % locale))

    sudo('apt-get install -qqy language-pack-%s-base' % locale[0:2])
    sudo('locale-gen "%s.%s"' % (locale, encoding))
    sudo('dpkg-reconfigure locales')
    dotenv_set('/etc/environment', 'LC_ALL', "%s.%s" % (locale, encoding))
    dotenv_set('/etc/environment', 'set', 'LANG', "%s.%s" % (locale, encoding))
    dotenv_set('/etc/environment', 'set', 'LANG', "%s.%s" % (locale, encoding))
    sudo('export $(cat /etc/environment | xargs)')


"""
Setup server for receiving meteor apps
"""
def setup_meteor(**kwargs):

    setup_tools(**kwargs)

    # Nodejs
    if not which('npm'):
        setup_nodejs(**kwargs)

    if not which('mongo'):
        setup_mongodb(**kwargs)

    # HTTP frontend
    if not exists('/etc/nginx'):
        setup_nginx(**kwargs)

    setup_vhost(**kwargs)

    # SSL certs builder
    if not exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env):
        setup_ssl_certs(**kwargs)



# http://stackoverflow.com/questions/3854692/generate-password-in-python
def generate_password(length = 32):
    if not isinstance(length, int) or length < 8:
        raise ValueError("temp password must have positive length")
    chars = "*234679ADEFGHJKLMNPRTUWabdefghijkmnpqrstuwy"
    from os import urandom
    return "".join([chars[ord(c) % len(chars)] for c in urandom(length)])



"""
 _____ __  __ _____   ____  _____ _______       __  ________   _______   ____  _____ _______
|_   _|  \/  |  __ \ / __ \|  __ \__   __|     / / |  ____\ \ / /  __ \ / __ \|  __ \__   __|
  | | | \  / | |__) | |  | | |__) | | |       / /  | |__   \ V /| |__) | |  | | |__) | | |
  | | | |\/| |  ___/| |  | |  _  /  | |      / /   |  __|   > < |  ___/| |  | |  _  /  | |
 _| |_| |  | | |    | |__| | | \ \  | |     / /    | |____ / . \| |    | |__| | | \ \  | |
|_____|_|  |_|_|     \____/|_|  \_\ |_|    /_/     |______/_/ \_\_|     \____/|_|  \_\ |_|

"""


def mongo_backup():
    pass

def mongo_restore():
    from urlparse import urlsplit
    mongoinfo = urlsplit(env.MONGO_URL)._asdict()
    env.fpath = fpath = args.mongodumpzip
    env.fname = os.path.basename(fpath)
    env.dbname = mongoinfo.get('path').strip('/')
    env.dbhost = mongoinfo.get('netloc').strip('/')
    put(env.fpath, "/tmp/%s" % env.fname)
    sudo("unzip /tmp/%s" % env.fname)
    sudo("mongorestore dump/%(dbname)s --host %(dbhost)s --db %(dbname)s --drop" % env)
    sudo("rm /tmp/%s" % env.fname)
    pass



def develop():
    env_vars = settings.get('env', {})
    if settings.get('targets') and settings['targets'].get('local'):
        env_vars.update(settings['targets']['local'].get('env', {}))
    with shell_env(**env_vars):
        local('meteor')

"""
  _____ ____  _   _ ______ _____ _____
 / ____/ __ \| \ | |  ____|_   _/ ____|
| |   | |  | |  \| | |__    | || |  __
| |   | |  | | . ` |  __|   | || | |_ |
| |___| |__| | |\  | |     _| || |__| |
 \_____\____/|_| \_|_|    |_____\_____|

"""


def environment_var(key=None, value=None,**kwargs):
    setup_tools(**kwargs)
    setup_struct(**kwargs)
    setup_vhost(**kwargs)
    f = '/opt/%s/.env' % env.domain
    if not key:
        print read(f)
        return None
    if not value:
        print dotenv_get(f, key)
        return dotenv_get(f, key)
    else:
        s = dotenv_set(f, key, value)
        sudo("service %s restart" % env.domain)
        return s



"""
 _____  ______ _____  _      ______     __
|  __ \|  ____|  __ \| |    / __ \ \   / /
| |  | | |__  | |__) | |   | |  | \ \_/ /
| |  | |  __| |  ___/| |   | |  | |\   /
| |__| | |____| |    | |___| |__| | | |
|_____/|______|_|    |______\____/  |_|

"""

def deploy(**kwargs):

    print(blue('Start Deployment: %(user)s@%(host_string)s' % env))

    setup_meteor()

    print(blue("Start build on " + env.app_local_root))
    local('cd ' + env.app_local_root)
    local('meteor build .. --architecture os.linux.x86_64')

    print(blue("build complete, lets teleport this !"))
    filename = '../' + os.path.basename(env.app_local_root) + '.tar.gz'
    release_path = '/opt/%(domain)s/releases/%(deployment_id)s' % env
    sudo('mkdir -p %s' % release_path)
    put(env.app_local_root + '/' + filename, release_path + "/" + filename)

    env.release_path = release_path

    template('build_app.sh', '%(release_path)s/build.sh' % env)
    sudo('chmod +x %(release_path)s/build.sh' % env)

    with cd(release_path):
        sudo("tar -zxf %s" % (filename))
        sudo("rm %s" % (filename))

    # build process
    put(env.app_local_root + '/settings.json', "%(release_path)s/bundle/" % env)
    sudo('%(release_path)s/build.sh' % env)

    # deploy this release
    sudo("rm -f /opt/%(domain)s/releases/latest && ln -fs %(release_path)s /opt/%(domain)s/releases/latest" % env)

    # reload services
    sudo("service %(domain)s restart" % env)
    sudo("service nginx reload" % env)


def rollback():
    pass



"""
@see http://docs.fabfile.org/en/latest/api/core/context_managers.html#fabric.context_managers.settings
Use context manager to set fabric to use hard error reporting
"""
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Deploy or some integers.')
    parser.add_argument('-e', '--env',
                        type=str,
                        help='Target environment to execute command, (by default first env)',
                        dest="target",
                        default=None)


    def add_base_args(parser):
        parser.add_argument('-a', '--app',
                            dest='appdir',
                            default=os.getcwd(),
                            help='Meteor app directory, default cwd (%s)' % os.getcwd())
        parser.add_argument('-H', '--host',
                            dest='hostname',
                            help='Host to connect to')
        parser.add_argument('-i', '--identity',
                            dest='sshkey',
                            default=False,
                            help='SSH key path')
        parser.add_argument('-p', '--port',
                            dest='sshport',
                            default=False,
                            help='SSH port')
        parser.add_argument('--domain',
                            dest='domain',
                            default=False,
                            help='Vhost domain')
        parser.add_argument('--email',
                            dest='email',
                            default=False,
                            help='SSL certs email & administrative contact')

    subparsers = parser.add_subparsers(title='sub-command', description='Command to launch', dest="command")

    subparser = subparsers.add_parser('deploy', help='Deploy to remote target')
    subparser.add_argument('target', type=str, help='Target where you want to deploy')
    add_base_args(subparser)

    subparser = subparsers.add_parser('set_locale', help='Run local env regarding settings.json ENV')
    subparser.add_argument('locale', type=str, default="en_GB", help="Locale in format 'en_GB'", nargs="?")
    subparser.add_argument('encoding', type=str, default="UTF-8", help="Encoding in format 'UTF-8'", nargs="?")
    add_base_args(subparser)

    subparser = subparsers.add_parser('develop', help='Run local env regarding settings.json ENV')
    # parser_restore.add_argument('mongodumpzip', type=str, help='Target to execute command')
    add_base_args(subparser)

    subparser = subparsers.add_parser('env', help='Store & retrieve remote env vars')
    subparser.add_argument('key', type=str, help='Environment key', default=None, nargs='?')
    subparser.add_argument('value', type=str, help='Environment key value', default=None, nargs='?')
    add_base_args(subparser)

    subparser = subparsers.add_parser('db_create', help='Create MongoDB db and associated user as db owner')
    subparser.add_argument('dbname', type=str, help='database name')
    subparser.add_argument('dbuser', type=str, help='database user, same as db if not provided', default=None, nargs="?")
    add_base_args(subparser)

    subparser = subparsers.add_parser('db_delete', help='Delete MongoDB database and associated user')
    subparser.add_argument('dbname', type=str, help='database name')
    add_base_args(subparser)

    subparser = subparsers.add_parser('db_dump', help='Restore MongoDB dump to target')
    subparser.add_argument('mongodumpzip', type=str, help='Target to execute command')
    add_base_args(subparser)

    subparser = subparsers.add_parser('db_restore', help='Restore MongoDB dump to target')
    subparser.add_argument('mongodumpzip', type=str, help='Target to execute command')
    add_base_args(subparser)


    args = parser.parse_args()

    COMMANDS = {
        "develop": develop,
        "setup": setup_meteor,
        "deploy": deploy,
        "rollback": rollback,
        "env": environment_var,
        "db_dump": mongo_backup,
        "db_restore": mongo_restore,
        "db_create": mongo_create_db,
        "db_delete": mongo_delete_db,
        "set_locale": setup_locale,
    }

    if not os.path.exists(args.appdir + '/.meteor'):
        abort(red('''
        Invalid meteor project, you must specify a valid meteor project path (look for .meteor) using -a --app or run commands in meteor application
        '''))

    if not os.path.exists(args.appdir + '/settings.json'):
        abort(red('''
        Invalid meteor settings file, you must create a valid settings.json file in your meteor project
        '''))

    settings = json.load(open(args.appdir + '/settings.json', 'r'))

    targets = settings.get('targets').keys();

    if args.target == None:
        args.target = targets[0]

    if not args.target in targets:
        abort(red('Invalid target name, should be in %s' % targets))
    else:
        target = settings['targets'][args.target]


    config_get_domain()
    config_get_email()

    env.deployment_id = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    env.host_string = target['host']

    if not target.has_key('user'): env.user = "root"
    else: env.user = target['user']

    if target.get('pem', False):
        env.key_filename = target['pem']

    env.warn_only = True

    if not settings.has_key('env'):
        settings['env'] = {}

    if target.has_key('env'):
        settings['env'].update(target['env'])

    env.settings = settings
    env.app_node_port = 8000 + (binascii.crc32(env.domain) * -1)%1000
    env.app_local_root = os.path.abspath(args.appdir)
    env.disable_known_hosts = True


    for k, v in settings.get('env', {}).items():
        env[k] = v

    for k, v in target.get('env', {}).items():
        env[k] = v

    env.args = args

    COMMANDS[args.command](**vars(args))
