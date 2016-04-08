#!/bin/bash

BUNDLE_DIR={{ release_path }}/bundle

# utilities
gyp_rebuild_inside_node_modules () {
  for npmModule in ./*; do
    cd $npmModule

    isBinaryModule="no"
    # recursively rebuild npm modules inside node_modules
    check_for_binary_modules () {
      if [ -f binding.gyp ]; then
        isBinaryModule="yes"
      fi

      if [ $isBinaryModule != "yes" ]; then
        if [ -d ./node_modules ]; then
          cd ./node_modules
          for module in ./*; do
            cd $module
            check_for_binary_modules
            cd ..
          done
          cd ../
        fi
      fi
    }

    check_for_binary_modules

    if [ $isBinaryModule = "yes" ]; then
      echo " > $npmModule: npm install due to binary npm modules"
      rm -rf node_modules
      if [ -f binding.gyp ]; then
        sudo npm install
        sudo node-gyp rebuild || :
      else
        sudo npm install
      fi
    fi

    cd ..
  done
}

rebuild_binary_npm_modules () {
  for package in ./*; do
    if [ -d $package/node_modules ]; then
      cd $package/node_modules
        gyp_rebuild_inside_node_modules
      cd ../../
    elif [ -d $package/main/node_module ]; then
      cd $package/node_modules
        gyp_rebuild_inside_node_modules
      cd ../../../
    fi
  done
}



# logic
set -e


cd $BUNDLE_DIR/programs/server

sudo npm install -g node-gyp

if [ -d ./npm ]; then
  cd npm
  rebuild_binary_npm_modules
  cd ../
fi

if [ -d ./node_modules ]; then
  cd ./node_modules
  gyp_rebuild_inside_node_modules
  cd ../
fi

if [ -f package.json ]; then
  # support for 0.9
  sudo npm install
else
  # support for older versions
  sudo npm install fibers
  sudo npm install bcrypt
fi
