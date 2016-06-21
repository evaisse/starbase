#!/bin/bash

BUNDLE_DIR={{ release_path }}/bundle

cd $BUNDLE_DIR/programs/server
rm -rf node_modules
sudo npm install --production
