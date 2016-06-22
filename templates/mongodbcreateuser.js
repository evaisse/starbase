{% if dbuser == "starbaseAdmin" %}
    {#
        ADMIN USER
    #}
    db.getSiblingDB("{{dbname}}").createUser({
        user: "{{ dbuser }}",
        pwd: "{{ dbpassword }}",
        roles: [
            "userAdminAnyDatabase",
            "dbAdminAnyDatabase",
            "readWriteAnyDatabase"
        ]
    })
{% else %}
    {#
        STANDARD USER
    #}
    db.getSiblingDB("{{dbname}}").createUser({
        user: "{{ dbuser }}",
        pwd: "{{ dbpassword }}",
        roles: [ { role: "dbAdmin", db: "{{dbname}}" } ]
    })
{% endif %}


db.getSiblingDB("admin").createUser({
    user: "admin",
    pwd: "t6Qvr58b!FfRsha4g",
    roles: [
        "userAdminAnyDatabase",
        "dbAdminAnyDatabase",
        "readWriteAnyDatabase",
        "root"
    ]
})
