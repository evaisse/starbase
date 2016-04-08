#!/bin/bash

# Remove the lock
set +e
sudo rm /var/lib/dpkg/lock > /dev/null
sudo rm /var/cache/apt/archives/lock > /dev/null
sudo dpkg --configure -a
set -e


# Install Node.js - either nodeVersion or which works with latest Meteor release
NODE_VERSION={{ NODE_VERSION }}


ARCH=$(python -c 'import platform; print platform.architecture()[0]')
if [[ ${ARCH} == '64bit' ]]; then
  NODE_ARCH=x64
else
  NODE_ARCH=x86
fi

sudo apt-get -y install build-essential libssl-dev git curl

NODE_DIST=node-v${NODE_VERSION}-linux-${NODE_ARCH}

cd /tmp
wget http://nodejs.org/dist/v${NODE_VERSION}/${NODE_DIST}.tar.gz
tar xvzf ${NODE_DIST}.tar.gz
sudo mkdir -p /usr/local/nodejs
sudo rm -rf /usr/local/nodejs
sudo mv ${NODE_DIST} /usr/local/nodejs

sudo ln -sf /usr/local/nodejs/bin/node /usr/bin/node
sudo ln -sf /usr/local/nodejs/bin/npm /usr/bin/npm
