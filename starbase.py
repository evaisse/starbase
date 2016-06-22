#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
import datetime
import commentjson as json
import argparse
import re
import ConfigParser

from StringIO import StringIO

from fabric.api import local, run, sudo, settings, abort, env, get
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

def read(remote_path):
    fd = StringIO()
    get(remote_path, fd)
    return fd.getvalue()


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

def setup_struct():
    if exists("/opt/%(domain)s" % env):
        return False
    sudo('mkdir -p /var/log/%(domain)s' % env)
    sudo('mkdir -p /opt/%(domain)s/{backups,conf,data,logs,releases,var,etc}' % env)
    sudo('touch /opt/%(domain)s/.env' % env)


def setup_tools():

    print(blue('Setup some boring unix tools...'))

    sudo('mkdir -p /root/.starbase/')

    if exists("/root/.starbase/version") and sudo("cat /root/.starbase/version") == RELEASE_VERSION:
        return

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
    template('mongo.conf', '/etc/mongo.conf')

    mongo_setup_admin_user()

    sudo('service mongod start')



def mongo_command():
    pass


def mongo_setup_admin_user():

    env.dbname = "admin"
    env.dbuser = "starbaseAdmin"
    env.dbpassword = generate_password(16)
    sudo('mkdir /root/.starbase/mongo')
    append('/root/.starbase/mongo/env', "MONGO_ADMIN_USER=starbaseAdmin")
    append('/root/.starbase/mongo/env', "MONGO_ADMIN_PWD=%(dbpassword)s" % env)
    print(blue('Setup MONGODB Admin user : %(dbuser)s / %(dbpassword)s' % env))
    script = "%(dbname)s.%(dbuser)s.js" % env
    template('mongodbcreateuser.js', "/root/.starbase/mongo/" + script)
    sudo('mongo /root/.starbase/mongo/' + script)


def mongo_create_db(dbname, dbuser = None, **kwargs):
    setup_locale()
    print(blue('Create MongoDB DB : %s' % dbname))

    # env.args
    if not exists('/root/.starbase/mongo'):
        mongo_setup_admin_user()
    else:
        env_file_content = read('/root/.starbase/mongo/env')
        config = ConfigParser.RawConfigParser()
        config.readfp(io.BytesIO(env_file_content))

    env.dbpassword = generate_password(16)
    env.dbname = dbname

    if dbuser: env.dbuser = dbuser
    else: env.dbuser = dbname



    script = "%(dbname)s.%(dbuser)s.js" % env
    template('mongodbcreateuser.js', "/root/.starbase/mongo/" + script)

    sudo('mongo /root/.starbase/mongo/' + script)

    print(blue('Create MongoDB DB %(dbname)s with auth : %(dbuser)s / %(dbpassword)s' % env))
    return (env.dbuser, env.dbpassword)



def setup_nodejs():
    template('install_nodejs.sh', '/root/.starbase/')
    sudo('chmod u+x /root/.starbase/*.sh')
    sudo('/root/.starbase/install_nodejs.sh')



def setup_nginx():

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


def setup_ssl_certs():

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


def setup_vhost():
    print(green('setup/reload vhosts'))
    setup_struct()
    dbuser = re.sub('[^\w]', '', env.domain)
    dbuser, dbpassword = mongo_create_db(dbuser)
    environment_set_var("MONGO_URL", "mongodb://%s:%s@localhost/%s" % (dbuser, dbpassword, dbuser))
    env.enable_ssl = exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env)
    template('nginx.vhost.conf', '/etc/nginx/sites-available/%(domain)s.conf' % env)
    template('upstart.conf', '/etc/init/%(domain)s.conf' % env)
    template('logrotate.conf', '/etc/logrotate.d/%(domain)s.conf' % env)
    sudo('ln -fs /etc/nginx/sites-available/%(domain)s.conf /etc/nginx/sites-enabled/' % env)
    sudo('service nginx reload')
    if not exists('/opt/%(domain)s/releases/default' % env):
        sudo('mkdir -p /opt/%(domain)s/releases/default/bundle' % env)
        template('defaultapp.js', '/opt/%(domain)s/releases/default/bundle/main.js' % env)
        sudo('ln -fs /opt/%(domain)s/releases/default/bundle /opt/%(domain)s/bundle' % env)
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
    sudo(dotenv.get_cli_string('/etc/environment', 'set', 'LC_ALL', "%s.%s" % (locale, encoding)))
    sudo(dotenv.get_cli_string('/etc/environment', 'set', 'LANG', "%s.%s" % (locale, encoding)))
    sudo(dotenv.get_cli_string('/etc/environment', 'set', 'LANG', "%s.%s" % (locale, encoding)))
    sudo('export $(cat /etc/environment | xargs)')
    

"""
Setup server for receiving meteor apps
"""
def setup_meteor():

    setup_tools()

    # Nodejs
    if not which('npm'):
        setup_nodejs()

    if not which('mongo'):
        setup_mongodb()

    # HTTP frontend
    if not exists('/etc/nginx'):
        setup_nginx()

    setup_vhost()

    # SSL certs builder
    if not exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env):
        setup_ssl_certs()



# http://stackoverflow.com/questions/3854692/generate-password-in-python
def generate_password(length = 32):
    if not isinstance(length, int) or length < 8:
        raise ValueError("temp password must have positive length")
    chars = "!$234679ADEFGHJKLMNPRTUWabdefghijkmnpqrstuwy"
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


def environment_var():
    setup_tools()
    setup_struct()
    if not args.key:
        return environment_get_all_vars()
    if not args.value:
        return environment_get_var(env.args)
    else:
        return environment_set_var(env.args)

def environment_get_all_vars():
    print read('cat /opt/%s/.env' % env.domain)

def environment_get_var(key, **kwargs):
    print sudo(dotenv.get_cli_string('/opt/%s/.env' % env.domain, 'get', key))

def environment_set_var(key, value, **kwargs):
    sudo(dotenv.get_cli_string('/opt/%s/.env' % env.domain, 'set', key, value))



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
    local('meteor build . --architecture os.linux.x86_64')

    print(blue("build complete, lets teleport this !"))
    filename = os.path.basename(env.app_local_root) + '.tar.gz'
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

    subparser = subparsers.add_parser('restore', help='Restore MongoDB dump to target')
    subparser.add_argument('mongodumpzip', type=str, help='Target to execute command')
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

    subparser = subparsers.add_parser('create_db', help='Create MongoDB collection and associated user')
    subparser.add_argument('dbname', type=str, help='database name')
    subparser.add_argument('dbuser', type=str, help='database user, same as db if not provided', default=None, nargs="?")
    add_base_args(subparser)

    args = parser.parse_args()

    COMMANDS = {
        "develop": develop,
        "setup": setup_meteor,
        "deploy": deploy,
        "rollback": rollback,
        "env": environment_var,
        "mongo_backup": mongo_backup,
        "mongo_restore": mongo_restore,
        "create_db": mongo_create_db,
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
