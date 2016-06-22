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
        roles: [
            { role: "dbAdmin", db: "{{dbname}}" },
            { role: "readWrite", db: "{{dbname}}" },
            { role: "root", db: "{{dbname}}" }
        ]
    })
{% endif %}
