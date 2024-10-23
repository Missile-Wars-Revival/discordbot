# Install:
```
pip install discord httpx pillow firebase_admin
```

Place firebase credentials into the cogs directory under the name `creds` <br />
Expected layout -> `cpgs/creds.json` <br />
The file should look like: <br />
```
{
    "type": "service_account",
    "project_id": "",
    "private_key_id": "",
    "private_key": "",
    "client_email": "",
    "client_id": "",
    "auth_uri": "",
    "token_uri": "",
    "auth_provider_x509_cert_url": "",
    "client_x509_cert_url": "",
    "universe_domain": ""
  }
```
Add file `config.py` into root directory. <br />
This should contain: <br />
```
TOKEN = '' #bot token
BACKEND_URL = ''
GUILD_ID = 1237511122106585181
CHANNEL_ID = 1237513649611083858
NOTIFICATIONS_CHANNEL_ID = 1244534188816732171
FIREBASE_CREDENTIALS_PATH = './cogs/creds.json'
```

# Run with pm2:
```
pm2 start start_bot.sh --name discord-bot
```

Made by @longtimeno-c
