#
# REQUIRES:
#       - server (the forge server instance)
#       - site_name (the name of the site folder)
#       - sudo_password (random password for sudo)
#       - db_password (random password for database user)
#       - event_id (the provisioning event name)
#       - callback (the callback URL)
#

# Upgrade The Base Packages

apt-get update
apt-get upgrade -y

# Add A Few PPAs To Stay Current

apt-get install -y software-properties-common

apt-add-repository ppa:nginx/stable -y
apt-add-repository ppa:rwky/redis -y
apt-add-repository ppa:chris-lea/node.js -y
apt-add-repository ppa:ondrej/php5 -y

apt-get update
# Base Packages

apt-get install -y build-essential curl fail2ban gcc git libmcrypt4 libpcre3-dev \
make python-pip supervisor ufw unattended-upgrades unzip whois zsh

# Install Python Httpie

pip install httpie

# Disable Password Authentication Over SSH

echo "PasswordAuthentication no" | sudo tee -a /etc/ssh/sshd_config

service ssh restart

# Set The Hostname If Necessary


echo "linode-aiur" > /etc/hostname
sed -i 's/127\.0\.0\.1.*localhost/127.0.0.1 localhost linode-aiur/' /etc/hosts
hostname linode-aiur

# Set The Timezone

ln -sf /usr/share/zoneinfo/Asia/Dubai /etc/localtime

# Setup Forge User

useradd forge
mkdir -p /home/forge/.ssh
mkdir -p /home/forge/.forge
adduser forge sudo

# Setup Bash For Forge User

chsh -s /bin/bash forge
cp /root/.profile /home/forge/.profile
cp /root/.bashrc /home/forge/.bashrc

# Set The Sudo Password For Forge

PASSWORD=$(mkpasswd jMYIjsqe0xvneGL6WkYR)
usermod --password $PASSWORD forge

# Create The Server SSH Key

ssh-keygen -f /home/forge/.ssh/id_rsa -t rsa -N ''

# Copy Github And Bitbucket Public Keys Into Known Hosts File

ssh-keyscan -H github.com >> /home/forge/.ssh/known_hosts
ssh-keyscan -H bitbucket.org >> /home/forge/.ssh/known_hosts

# Add The Reconnect Script Into Forge Directory

cat > /home/forge/.forge/reconnect << EOF
#!/usr/bin/env bash

echo "# Laravel Forge" | tee -a /home/forge/.ssh/authorized_keys > /dev/null
echo \$1 | tee -a /home/forge/.ssh/authorized_keys > /dev/null

echo "# Laravel Forge" | tee -a /root/.ssh/authorized_keys > /dev/null
echo \$1 | tee -a /root/.ssh/authorized_keys > /dev/null

echo "Keys Added!"
EOF

# Add The Environment Variables Scripts Into Forge Directory

cat > /home/forge/.forge/add-variable.php << EOF
<?php

// Get the script input...
\$input = array_values(array_slice(\$_SERVER['argv'], 1));

// Get the path to the environment file...
\$path = getcwd().'/'.\$input[2];

// Write a stub file if one doesn't exist...
if ( ! file_exists(\$path)) {
    file_put_contents(\$path, '<?php return '.var_export([], true).';');
}

// Set the new environment variable...
\$env = require \$path;
\$env[\$input[0]] = \$input[1];

// Write the environment file to disk...
file_put_contents(\$path, '<?php return '.var_export(\$env, true).';');

EOF

cat > /home/forge/.forge/remove-variable.php << EOF
<?php

// Get the script input...
\$input = array_values(array_slice(\$_SERVER['argv'], 1));

// Get the path to the environment file...
\$path = getcwd().'/'.\$input[1];

// Write a stub file if one doesn't exist...
if ( ! file_exists(\$path)) {
    file_put_contents(\$path, '<?php return '.var_export([], true).';');
}

// Remove the environment variable...
\$env = require \$path;
unset(\$env[\$input[0]]);

// Write the environment file to disk...
file_put_contents(\$path, '<?php return '.var_export(\$env, true).';');

EOF

# Setup Site Directory Permissions

chown -R forge:forge /home/forge
chmod -R 755 /home/forge
chmod 700 /home/forge/.ssh/id_rsa

# Setup Unattended Security Upgrades

cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "Ubuntu trusty-security";
};
Unattended-Upgrade::Package-Blacklist {
    //
};
EOF

cat > /etc/apt/apt.conf.d/10periodic << EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Setup UFW Firewall

ufw allow 22
ufw allow 80
ufw allow 443
ufw --force enable

# Install Base PHP Packages

apt-get install -y php5-cli php5-dev php-pear \
php5-mysql php5-pgsql php5-sqlite \
php5-apcu php5-json php5-curl php5-dev php5-gd \
php5-gmp php5-imap php5-mcrypt php5-xdebug php5-memcached

# Make The MCrypt Extension Available

ln -s /etc/php5/conf.d/mcrypt.ini /etc/php5/mods-available
sudo php5enmod mcrypt
sudo service nginx restart

# Install Composer Package Manager

curl -sS https://getcomposer.org/installer | php
mv composer.phar /usr/local/bin/composer

# Misc. PHP CLI Configuration

sudo sed -i "s/error_reporting = .*/error_reporting = E_ALL/" /etc/php5/cli/php.ini
sudo sed -i "s/display_errors = .*/display_errors = On/" /etc/php5/cli/php.ini
sudo sed -i "s/memory_limit = .*/memory_limit = 512M/" /etc/php5/cli/php.ini
sudo sed -i "s/;date.timezone.*/date.timezone = UTC/" /etc/php5/cli/php.ini


#
# REQUIRES:
#       - server (the forge server instance)
#       - site_name (the name of the site folder)
#

# Install Nginx & PHP-FPM

apt-get install -y nginx php5-fpm

# Disable The Default Nginx Site

rm /etc/nginx/sites-enabled/default
rm /etc/nginx/sites-available/default
service nginx restart

# Tweak Some PHP-FPM Settings

sed -i "s/error_reporting = .*/error_reporting = E_ALL/" /etc/php5/fpm/php.ini
sed -i "s/display_errors = .*/display_errors = On/" /etc/php5/fpm/php.ini
sed -i "s/;cgi.fix_pathinfo=1/cgi.fix_pathinfo=0/" /etc/php5/fpm/php.ini
sed -i "s/memory_limit = .*/memory_limit = 512M/" /etc/php5/fpm/php.ini
sed -i "s/;date.timezone.*/date.timezone = UTC/" /etc/php5/fpm/php.ini

# Configure Nginx & PHP-FPM To Run As Forge

sed -i "s/user www-data;/user forge;/" /etc/nginx/nginx.conf
sed -i "s/# server_names_hash_bucket_size.*/server_names_hash_bucket_size 64;/" /etc/nginx/nginx.conf

sed -i "s/^user = www-data/user = forge/" /etc/php5/fpm/pool.d/www.conf
sed -i "s/^group = www-data/group = forge/" /etc/php5/fpm/pool.d/www.conf

sed -i "s/;listen\.owner.*/listen.owner = forge/" /etc/php5/fpm/pool.d/www.conf
sed -i "s/;listen\.group.*/listen.group = forge/" /etc/php5/fpm/pool.d/www.conf
sed -i "s/;listen\.mode.*/listen.mode = 0666/" /etc/php5/fpm/pool.d/www.conf

# Configure A Few More Server Things

sed -i "s/;request_terminate_timeout.*/request_terminate_timeout = 60/" /etc/php5/fpm/pool.d/www.conf
sed -i "s/worker_processes.*/worker_processes auto;/" /etc/nginx/nginx.conf
sed -i "s/# multi_accept.*/multi_accept on;/" /etc/nginx/nginx.conf

# Install A Catch All Server

cat > /etc/nginx/sites-available/catch-all << EOF
server {
    return 404;
}
EOF

ln -s /etc/nginx/sites-available/catch-all /etc/nginx/sites-enabled/catch-all

# Restart Nginx & PHP-FPM Services

# Restart Nginx & PHP-FPM Services

service php5-fpm restart
service nginx restart

# Add Forge User To www-data Group

usermod -a -G www-data forge
id forge
groups forge

#
# REQUIRES:
#       - server (the forge server instance)
#

# Only Install PHP Extensions When Not On HHVM


# Install The Phalcon Framework

# cd /root
# git clone --depth=1 https://github.com/phalcon/cphalcon.git
# cd /root/cphalcon/build
# ./install
# cd /root
# rm -rf /root/cphalcon
# echo "extension=phalcon.so" > /etc/php5/mods-available/phalcon.ini
# ln -s /etc/php5/mods-available/phalcon.ini /etc/php5/fpm/conf.d/20-phalcon.ini
# ln -s /etc/php5/mods-available/phalcon.ini /etc/php5/cli/conf.d/20-phalcon.ini

# Install The Mongo Extension

printf "no\n" | pecl install mongo
echo "extension=mongo.so" > /etc/php5/mods-available/mongo.ini
ln -s /etc/php5/mods-available/mongo.ini /etc/php5/fpm/conf.d/20-mongo.ini
ln -s /etc/php5/mods-available/mongo.ini /etc/php5/cli/conf.d/20-mongo.ini


# Install Node

apt-get install -y nodejs

# Install Grunt CLI & Gulp

npm install -g pm2
npm install -g grunt-cli
npm install -g gulp

#
# REQUIRES:
#       - server (the forge server instance)
#       - db_password (random password for mysql user)
#

# Set The Automated Root Password

debconf-set-selections <<< "mysql-server mysql-server/root_password password T2Jm5jDCsL2MHIiiFPI5"
debconf-set-selections <<< "mysql-server mysql-server/root_password_again password T2Jm5jDCsL2MHIiiFPI5"

# Install MySQL

apt-get install -y mysql-server

# Configure Access Permissions For Root & Forge Users

sed -i '/^bind-address/s/bind-address.*=.*/bind-address = */' /etc/mysql/my.cnf
mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "GRANT ALL ON *.* TO root@'109.74.200.135' IDENTIFIED BY 'T2Jm5jDCsL2MHIiiFPI5';"
mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "GRANT ALL ON *.* TO root@'%' IDENTIFIED BY 'T2Jm5jDCsL2MHIiiFPI5';"
service mysql restart

mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "CREATE USER 'forge'@'109.74.200.135' IDENTIFIED BY 'T2Jm5jDCsL2MHIiiFPI5';"
mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "GRANT ALL ON *.* TO 'forge'@'109.74.200.135' IDENTIFIED BY 'T2Jm5jDCsL2MHIiiFPI5';"
mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "GRANT ALL ON *.* TO 'forge'@'%' IDENTIFIED BY 'T2Jm5jDCsL2MHIiiFPI5';"
mysql --user="root" --password="T2Jm5jDCsL2MHIiiFPI5" -e "FLUSH PRIVILEGES;"

# Create The Initial Database If Specified


#
# REQUIRES:
#       - server (the forge server instance)
#       - db_password (random password for database user)
#

# Install Postgres

apt-get install -y postgresql

# Configure Postgres For Remote Access

sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/9.3/main/postgresql.conf
echo "host    all             all             0.0.0.0/0               md5" | tee -a /etc/postgresql/9.3/main/pg_hba.conf
sudo -u postgres psql -c "CREATE ROLE forge LOGIN UNENCRYPTED PASSWORD 'T2Jm5jDCsL2MHIiiFPI5' SUPERUSER INHERIT NOCREATEDB NOCREATEROLE NOREPLICATION;"
service postgresql restart

# Create The Initial Database If Specified


# Install & Configure Redis Server

apt-get install -y redis-server
sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
service redis-server restart
# Install & Configure Memcached

apt-get install -y memcached
sed -i 's/-l 127.0.0.1/-l 0.0.0.0/' /etc/memcached.conf
service memcached restart
# Install & Configure Beanstalk

apt-get install -y beanstalkd
sed -i "s/BEANSTALKD_LISTEN_ADDR.*/BEANSTALKD_LISTEN_ADDR=0.0.0.0/" /etc/default/beanstalkd
sed -i "s/#START=yes/START=yes/" /etc/default/beanstalkd
/etc/init.d/beanstalkd start