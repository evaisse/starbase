Starbase
=====

A platform management tools for meteorjs


Features
---

 - Setup MongoDB with full text search
 - Setup NGINX as proxy with free let's encrypt SSL
 - Setup Node + phantomjs (for spiderable module)

 - Deploy application
 - Rollback
 - Tail remote logs

 - Backup / Restore Mongodb instance

 - Easy ENV configuration for private values (AWS keys, secrets, ...)
 - Run local meteor app with settings.json

 - easy to extends via your own fabfiles command



settings.json sample
----

You can setup your targets in settings.json. Watch out to not put some sensitive information here.
Prefer use of `starbase prod env FOO "bar"` for settings target only environment vars.


    {
        "servers": {
            "prod": {
                // domain name against which will be generated your SSL certs
                "domain": "example.com",
                // accessory emails admin
                "email": "foo@gmail.com",
                // hostname to ssh to
                "host": "example.com",
                // credentials
                "username": "root",
                // "password": "password"
                // or pem file (ssh based authentication)
                "pem": "~/.ssh/id_nce_meteor",
                "env": {
                    "ROOT_URL": "https://meselus.com",
                    "METEOR_ENV": "prod",
                }
            },
            "local": {
                "host": "localhost",
                "email": "foo@gmail.com",
                "env": {
                    "ROOT_URL": "http://localhost:3000",
                    "METEOR_ENV": "dev",
                    "MONGO_URL": "mongodb://localhost/nceMeteor"
                }
            }
        },

        // refer to meteor documentation here
        "public": {

        },

        // global environment vars
        "env": {
            "MY_ENV_VAR": "value here... This will available on every envs, but overrided by .env files & servers environments values"
        }
    }




Notes
---

 - https://help.ubuntu.com/community/EnvironmentVariables
 - OPLOG: A TAIL OF WONDER AND WOE  - http://adammonsen.com/post/1314
 - http://joshowens.me/building-your-own-meteor-galaxy-hosting-setup/
 - https://www.digitalocean.com/community/tutorials/how-to-choose-an-effective-backup-strategy-for-your-vps
