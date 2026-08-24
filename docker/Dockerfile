FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    GROK_BOT_HOME=/opt/Grok_Bot \
    GROK_BOT_NO_SANDBOX=1 \
    ELECTRON_OZONE_PLATFORM_HINT=auto

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        xdg-utils \
        fonts-liberation \
        libgtk-3-0 \
        libnss3 \
        libnotify4 \
        libxss1 \
        libxtst6 \
        libgbm1 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libasound2 \
        libcups2 \
        libatspi2.0-0 \
        libsecret-1-0 \
        libva2 \
        libegl1 \
        libgl1 \
        libvulkan1 \
        i965-va-driver \
        intel-media-va-driver \
        libayatana-appindicator3-1 \
        mesa-va-drivers \
        procps \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash grok \
    && mkdir -p /opt/Grok_Bot /home/grok/.grokbot "/home/grok/.config/Grok Bot" \
    && chown -R grok:grok /home/grok

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/detect-vaapi.sh /usr/local/bin/detect-vaapi.sh
COPY launch.sh /usr/local/bin/grok-bot-launch
COPY app /tmp/app-src
RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/detect-vaapi.sh /usr/local/bin/grok-bot-launch \
    && if [ -x /tmp/app-src/grok-bot ]; then \
         rm -rf /opt/Grok_Bot && mv /tmp/app-src /opt/Grok_Bot && chmod 755 /opt/Grok_Bot/chrome-sandbox; \
       else \
         rm -rf /tmp/app-src; \
       fi \
    && chown -R grok:grok /opt/Grok_Bot || true

USER grok
WORKDIR /home/grok
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
