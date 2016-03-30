#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
import commentjson as json
import argparse

from fabric.api import local, run, sudo, settings, abort, env
from fabric.contrib.console import confirm
from fabric.operations import prompt, put, get
from fabric.contrib.files import exists, upload_template, sed
from fabric.colors import green, red
from fabric.context_managers import cd, shell_env

import random
import binascii

DIR = os.path.dirname(os.path.abspath(__file__))

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

parser_deploy = subparsers.add_parser('deploy', help='Deploy to remote target')
add_base_args(parser_deploy)

parser_restore = subparsers.add_parser('restore', help='Restore MongoDB dump to target')
parser_restore.add_argument('mongodumpzip', type=str, help='Target to execute command')
add_base_args(parser_restore)

parser_restore = subparsers.add_parser('develop', help='Run local env regarding settings.json ENV')
# parser_restore.add_argument('mongodumpzip', type=str, help='Target to execute command')
add_base_args(parser_restore)


args = parser.parse_args()

print args

if not os.path.exists(args.appdir + '/.meteor'):
    abort('''
    Invalid meteor project, you must specify a valid meteor project path (look for .meteor) using -a --app or run commands in meteor application
    ''')

if not os.path.exists(args.appdir + '/settings.json'):
    abort('''
    Invalid meteor settings file, you must create a valid settings.json file in your meteor project
    ''')

settings = json.load(open(args.appdir + '/settings.json', 'r'))

targets = settings.get('servers').keys();

#
if args.target == None:
    args.target = targets[0]

if not args.target in targets:
    abort('Invalid target name, should be in %s' % targets)
else:
    target = settings['servers'][args.target]



"""

  ____ ___  _   _ _____ ___ ____ 
 / ___/ _ \| \ | |  ___|_ _/ ___|
| |  | | | |  \| | |_   | | |  _ 
| |__| |_| | |\  |  _|  | | |_| |
 \____\___/|_| \_|_|   |___\____|




"""
def config_get_domain():
    # DOMAIN for vhosts
    if env.get('domain'):
        return False

    if args.domain:
        env.domain = args.domain
    elif target.get('domain'):
        env.domain = target.get('domain')
    else:
        env.domain = prompt('Set domain name :')
    env.domain = env.domain.lower()

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



config_get_domain()
config_get_email()


env.host_string = target['host']
env.user = target['username']
if target.get('pem', False):
    env.key_filename = target['pem']

env.warn_only = True
env.settings = settings
env.app_node_port = 8000 + (binascii.crc32(env.domain) * -1)%1000
env.app_local_root = os.path.abspath(args.appdir)
env.disable_known_hosts = True


for k, v in settings.get('env', {}).items():
    env[k] = v

for k, v in target.get('env', {}).items():
    env[k] = v


"""
 _   _ _____ ___ _     ____  
| | | |_   _|_ _| |   / ___| 
| | | | | |  | || |   \___ \ 
| |_| | | |  | || |___ ___) |
 \___/  |_| |___|_____|____/ 

"""

def template(from_path, remote_path):
    upload_template(template_dir=DIR + '/templates/', filename=from_path, destination=remote_path, context=env, use_sudo=True, use_jinja=True)


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

def setup_mongodb():
    sudo('apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10')
    sudo('echo "deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.0.list')
    sudo('apt-get -y update')
    sudo('apt-get -y install mongodb-org')
    sudo('service mongod start')

    template('cron/mongodb', '/etc/cron.d/mongodb-backup')

def setup_nodejs():
    sudo('add-apt-repository -y ppa:chris-lea/node.js')
    sudo('apt-get -y update')
    sudo('apt-get -y install nodejs')
    sudo('npm -g install npm@latest')


def setup_nginx():
    sudo('apt-add-repository -y ppa:nginx/development') # on est des oufs
    sudo('apt-get -y update')
    sudo('apt-get -y install nginx')
    sudo('service nginx stop')
    # send default nginx config
    template('nginx.global.conf', '/etc/nginx/nginx.conf')
    template('index.html', '/var/www/html/index.html')
    
    # # default site if none found
    if not exists('nginx.default.conf'):
        template('nginx.default.conf', '/etc/nginx/sites-available/default.conf')
        sudo('ln -fs /etc/nginx/sites-available/default.conf /etc/nginx/sites-enabled/')

    sudo('service nginx start')
    
    # build better cypher for SSL A+ grade ssl labs
    if not exists('/etc/nginx/dhparams.2048.pem'):
        sudo('openssl dhparam -out /etc/nginx/dhparams.2048.pem 2048')


def setup_ssl_certs():
    if not exists('/opt/letsencrypt'):
        sudo('git clone https://github.com/letsencrypt/letsencrypt /usr/local/lib/letsencrypt')
        sudo('mkdir -p /var/www/letsencrypt/%(domain)s' % env)
    sudo('/usr/local/lib/letsencrypt/letsencrypt-auto certonly --webroot -w /var/www/letsencrypt/ --agree-tos --domain %(domain)s --email %(email)s' % env)
    template('cron/certs-renewal', '/etc/cron.d/certs-renewal.%(domain)s' % env)
    template('nginx.letsencrypt.conf', '/etc/nginx/conf.d/letsencrypt.conf')
    sudo('service nginx reload')


def setup_vhost():
    template('nginx.vhost.conf', '/etc/nginx/sites-available/%(domain)s.conf' % env)
    template('upstart.conf', '/etc/init/%(domain)s.conf' % env)
    sudo('ln -fs /etc/nginx/sites-available/%(domain)s.conf /etc/nginx/sites-enabled/' % env)
    sudo('service nginx reload')
    sudo('mkdir -p /var/log/%(domain)s' % env)
    sudo('mkdir -p /opt/%(domain)s/{bundle,conf,data,logs}' % env)
    if not exists('/opt/%(domain)s/bundle/main.js' % env):
        template('defaultapp.js', '/opt/%(domain)s/bundle/main.js' % env)
    sudo('service %(domain)s restart' % env)


def setup_elasticsearch():
    if exists('/opt/%(domain)s/config/elasticsearch.yml' % env):
        return
    sudo('add-apt-repository -y ppa:webupd8team/java')
    sudo('apt-get -y update')
    sudo('apt-get -y install oracle-java8-installer')
    sudo('wget -qO - https://packages.elastic.co/GPG-KEY-elasticsearch | apt-key add -')
    sudo('echo "deb http://packages.elastic.co/elasticsearch/2.x/debian stable main" | tee -a /etc/apt/sources.list.d/elasticsearch-2.x.list')
    sudo('apt-get -y update')
    sudo('apt-get -y install elasticsearch')


def setup_locale():
    sudo('locale-gen "en_US.UTF-8"')
    sudo('export LANG=en_US.UTF-8')
    sudo('export LANGUAGE=en_US')
    sudo('export LC_ALL=en_US.UTF-8')
    sudo('dpkg-reconfigure locales')


"""
Setup server for receiving meteor apps
"""
def setup():

    sudo('cd /root') # go to /root

    config_get_email()
    config_get_domain()

    # base build tools
    if not which('curl'):
        sudo('apt-get -y update')
        sudo('apt-get -y upgrade')
        sudo('apt-get -y install software-properties-common')
        
        sudo('apt-add-repository -y ppa:rwky/redis')
        sudo('apt-add-repository -y ppa:chris-lea/node.js')
        sudo('apt-get -y update')
        # Base Packages
        sudo('apt-get -y install build-essential curl fail2ban gcc git libmcrypt4 libpcre3-dev g++ make' 
            + ' make python-pip supervisor ufw unattended-upgrades unzip whois zsh moreutils')
        setup_locale()




    # HTTPie
    if not which('http'):
        sudo('pip install httpie')


    # Nodejs
    if not which('npm'):
        setup_nodejs()


    if not which('mongo'):
        setup_mongodb()


    # SSL certs builder
    if not exists('/etc/letsencrypt/live/%(domain)s/fullchain.pem' % env):
        setup_ssl_certs()


    # HTTP frontend
    if not exists('/etc/nginx'):
        setup_nginx()


    setup_vhost()





"""
 ___ __  __ ____   ___  ____ _____      __  _______  ______   ___  ____ _____ 
|_ _|  \/  |  _ \ / _ \|  _ \_   _|    / / | ____\ \/ /  _ \ / _ \|  _ \_   _|
 | || |\/| | |_) | | | | |_) || |     / /  |  _|  \  /| |_) | | | | |_) || |  
 | || |  | |  __/| |_| |  _ < | |    / /   | |___ /  \|  __/| |_| |  _ < | |  
|___|_|  |_|_|    \___/|_| \_\|_|   /_/    |_____/_/\_\_|    \___/|_| \_\|_|  
                                                                              
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
    if settings.get('servers') and settings['servers'].get('local'):
        env_vars.update(settings['servers']['local'].get('env', {}))
    with shell_env(**env_vars):
        local('meteor')



"""
 ____  _____ ____  _     _____   __
|  _ \| ____|  _ \| |   / _ \ \ / /
| | | |  _| | |_) | |  | | | \ V / 
| |_| | |___|  __/| |__| |_| || |  
|____/|_____|_|   |_____\___/ |_|  
                                   
"""

def deploy():

    config_get_email()
    config_get_domain()
    setup_vhost()

    print("Start build on " + env.app_local_root)
    local('cd ' + env.app_local_root)
    local('meteor build .')
    print(green("build complete, lets teleport this !"))
    filename = os.path.basename(env.app_local_root) + '.tar.gz'
    put(env.app_local_root + '/' + filename, '/opt/%(domain)s' % env)
    with cd("/opt/%s/" % (env.domain)):
        sudo("tar -zxf %s" % (filename))
    with cd("/opt/%(domain)s/bundle/programs/server" % env):
        sudo("npm install")
        sudo("rm -rf npm/npm-bcrypt/node_modules/bcrypt/")
        sudo("npm install bcrypt")

    
    sudo("service %(domain)s restart" % env)
    sudo("service nginx reload" % env)





def rollback():
    pass



AVAILABLE_COMMANDS = [
    develop,
    # setup_mongo, # setup mongo only with remote acess @todo
    setup,
    deploy,
    rollback,
    mongo_backup,
    mongo_restore,
]


def main():
    if args.command not in [fn.__name__ for fn in AVAILABLE_COMMANDS]:
        abort('invalid command %s, should be one of : %s' % (args.command, ", ".join([cmd.__name__ for cmd in AVAILABLE_COMMANDS])))
    else:
        cmds = [fn.__name__ for fn in AVAILABLE_COMMANDS]
        AVAILABLE_COMMANDS[cmds.index(args.command)]()



if __name__ == "__main__":
    main()