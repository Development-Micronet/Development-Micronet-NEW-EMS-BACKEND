# Production websocket setup

The notifications socket endpoint is served by Django ASGI at `/api/ws/notifications/`.

If the browser shows `Unexpected server response: 200`, the websocket request is not reaching `horilla.asgi:application`. A normal HTTP endpoint or SPA fallback is answering the request instead.

## What must be running

- Start the app with the ASGI entrypoint, not plain WSGI.
- This repository already does that in `.docker/entrypoint.sh`:

```sh
gunicorn horilla.asgi:application -k uvicorn.workers.UvicornWorker
```

- In production, set `CHANNELS_REDIS_URL` to a Redis instance so websocket events work across workers.

## Nginx reverse proxy

Your proxy must forward websocket upgrade headers for `/api/ws/`.

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    server_name ems.acetechnologys.com;

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Frontend connection rules

- Use `wss://ems.acetechnologys.com/api/ws/notifications/` when the site is behind HTTPS.
- Use `ws://ems.acetechnologys.com/api/ws/notifications/` only for plain HTTP environments.
- If the client is a browser, the most reliable auth option is `?token=<access_token>` because native browser websockets do not support arbitrary custom headers consistently.

## Quick verification

1. Open browser devtools and connect to `wss://ems.acetechnologys.com/api/ws/notifications/?token=<jwt>`.
2. The handshake must return `101 Switching Protocols`.
3. The first messages should include `notification_snapshot` and `connection_established`.
4. If you still see `200 OK`, nginx or another proxy layer is still routing `/api/ws/` as normal HTTP.
