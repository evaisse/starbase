#!/usr/bin/env python

from __future__ import with_statement

import os
import commentjson as json
import argparse

from fabric.api import local, run, sudo, settings, abort, env
from fabric.contrib.console import confirm
from fabric.operations import prompt
from fabric.contrib.files import exists, upload_template, sed
import random

DIR = os.path.dirname(os.path.abspath(__file__))


parser = argparse.ArgumentParser(description='Deploy or some integers.')

parser.add_argument('target', type=str, 
                    help='Target to execute command')
parser.add_argument('command', type=str, 
                    help='Command to execute')
parser.add_argument('-H', '--host', dest='hostname', 
                    help='Host to connect to')
parser.add_argument('-a', '--app', dest='appdir', 
                    default=os.getcwd(),
                    help='Meteor app directory')
parser.add_argument('-i', '--identity', dest='sshkey', 
                    default=False,
                    help='SSH key path')
parser.add_argument('-p', '--port', dest='sshport', 
                    default=False,
                    help='SSH key path')
parser.add_argument('--domain', dest='domain', 
                    default=False,
                    help='Vhost domain')
parser.add_argument('--email', dest='email', 
                    default=False,
                    help='SSL certs email & administrative contact')





args = parser.parse_args()

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
if not args.target in targets:
    abort('Invalid target name, should be in %s' % targets)
else:
    target = settings['servers'][args.target]

print args


APPDIR = os.path.abspath(args.appdir)

# DOMAIN for vhosts
if args.domain:
    DOMAIN = args.domain
else:
    DOMAIN = prompt('Set domain name :')
DOMAIN = DOMAIN.lower()


# EMAIL for sslcerts 
if args.email:
    EMAIL = args.email
else:
    EMAIL = prompt('SSL cert authority email :')
EMAIL = EMAIL.lower()



CTXT = {
    'DOMAIN': DOMAIN,
    'EMAIL': EMAIL,
    'HTTP_LOCAL_PORT': 8000 + random.randint(100, 1000),
    'SETTINGS': settings,
}

env.host_string = target['host']
env.user = target['username']
env.warn_only = True


"""
 _   _ _____ ___ _     ____  
| | | |_   _|_ _| |   / ___| 
| | | | | |  | || |   \___ \ 
| |_| | | |  | || |___ ___) |
 \___/  |_| |___|_____|____/ 

"""

def template(from_path, remote_path):
    upload_template(template_dir=DIR + '/templates/', filename=from_path, destination=remote_path, context=CTXT, use_sudo=True, use_jinja=True)


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
    sudo('service mongod stop')

    template('cron/mongodb', '/etc/cron.d/mongodb-backup')



def setup_nodejs():
    sudo('add-apt-repository -y ppa:chris-lea/node.js')
    sudo('apt-get -y update')
    sudo('apt-get -y install nodejs')


def setup_nginx():
    sudo('apt-add-repository -y ppa:nginx/development') # on des oufs
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
    
    if not exists('/etc/nginx/dhparams.2048.pem'):
        sudo('openssl dhparam -out /etc/nginx/dhparams.2048.pem 2048')


def setup_ssl_certs():
    if not exists('/root/letsencrypt'):
        sudo('git clone https://github.com/letsencrypt/letsencrypt')
    sudo('service nginx stop')
    sudo('/root/letsencrypt/letsencrypt-auto certonly --standalone --agree-tos --domain %s --email %s' % (DOMAIN, EMAIL))
    sudo('service nginx start')
    template('cron/certs-renewal', '/etc/cron.d/certs-renewal.%s' % DOMAIN)


def setup_vhost():
    template('nginx.vhost.conf', '/etc/nginx/sites-available/%s.conf' % DOMAIN)
    template('upstart.conf', '/etc/init/%s.conf' % DOMAIN)
    sudo('ln -fs /etc/nginx/sites-available/%s.conf /etc/nginx/sites-enabled/' % DOMAIN)
    sudo('service nginx reload')
    sudo('mkdir -p /var/log/%s' % DOMAIN)
    sudo('mkdir -p /opt/%s/bundle' % DOMAIN)
    if not exists('/opt/%s/bundle/main.js' % DOMAIN):
        template('defaultapp.js', '/opt/%s/bundle/main.js' % DOMAIN)
    sudo('service %s restart' % DOMAIN)



"""
Setup server for receiving meteor apps
"""
def setup():

    sudo('cd /root') # go to /root


    # base build tools
    if not which('curl'):
        sudo('apt-get -y update')
        sudo('apt-get -y upgrade')
        sudo('apt-get -y install software-properties-common')
        
        sudo('apt-add-repository -y ppa:rwky/redis')
        sudo('apt-add-repository -y ppa:chris-lea/node.js')
        sudo('apt-get -y update')
        sudo('# Base Packages')
        sudo('apt-get -y install build-essential curl fail2ban gcc git libmcrypt4 libpcre3-dev ' 
            + ' make python-pip supervisor ufw unattended-upgrades unzip whois zsh')


    # HTTPie
    if not which('http'):
        sudo('pip install httpie')


    # Nodejs
    if not which('node'):
        setup_nodejs()


    if not which('mongo'):
        setup_mongodb()


    # SSL certs builder
    if not exists('/etc/letsencrypt/live/%s/fullchain.pem' % DOMAIN):
        setup_ssl_certs()


    # HTTP frontend
    if not exists('/etc/nginx'):
        setup_nginx()


    setup_vhost()





"""
 ____  _____ ____  _     _____   __
|  _ \| ____|  _ \| |   / _ \ \ / /
| | | |  _| | |_) | |  | | | \ V / 
| |_| | |___|  __/| |__| |_| || |  
|____/|_____|_|   |_____\___/ |_|  
                                   
"""

def deploy():
    local('cd ' + APPDIR)
    local('meteor build .')
    pass


def rollback():
    pass









AVAILABLE_COMMANDS = [
    setup,
    deploy,
    rollback
]


if __name__ == "__main__":
    if args.command not in [fn.__name__ for fn in AVAILABLE_COMMANDS]:
        abort('invalid command %s, should be one of : %s' % (args.command, AVAILABLE_COMMANDS))
    else:
        cmds = [fn.__name__ for fn in AVAILABLE_COMMANDS]
        AVAILABLE_COMMANDS[cmds.index(args.command)]()




"""

su root

cd ~


apt-get update
apt-get upgrade


apt-get install -y software-properties-common

apt-add-repository ppa:nginx/stable -y
apt-add-repository ppa:rwky/redis -y
apt-add-repository ppa:chris-lea/node.js -y

apt-get update
# Base Packages

apt-get install -y build-essential curl fail2ban gcc git libmcrypt4 libpcre3-dev \
make python-pip supervisor ufw unattended-upgrades unzip whois zsh

# Install Python Httpie

pip install httpie

# nodejs builds
add-apt-repository ppa:chris-lea/node.js -y
apt-get update
apt-get install -y nodejs

# ssl creation
git clone https://github.com/letsencrypt/letsencrypt
./letsencrypt-auto certonly --standalone --verbose --email -d 


# server build
apt-get install nginx
mkdir /etc/nginx/ssl
chmod 0700 /etc/nginx/ssl

# mongodb
apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo "deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.0.list
apt-get update

apt-get install -y mongodb-org
service mongod stop
"""