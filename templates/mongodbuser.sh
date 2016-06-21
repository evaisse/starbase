password=$(</dev/urandom tr -dc '12345$qwertQWERTasdfgASDFGzxcvbZXCVB' | head -c15; echo "")

cat > /root/mongodb-admin-user.$1.js << EOF
db.getSiblingDB("admin").createUser(
  {
    user: "$1",
    pwd: "$password",
    roles: [ { role: "userAdminAnyDatabase", db: "admin" } ]
  }
)
EOF

mongo /root/mongodb-admin-user.$1.js

sed -i "s/127.0.0.1/0.0.0.0/g" /etc/mongod.conf

cat >> /etc/mongod.conf <<EOF
security:
    authorization: enabled
EOF

service mongod restart
