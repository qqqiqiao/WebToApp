# WebToApp
# Default image includes a JDK, the Android SDK and apktool, so generated
# Android packages are real APKs. Build with --build-arg WITH_ANDROID=0 for
# a smaller image; Android then falls back to an installable PWA zip.
FROM python:3.12-slim-bookworm

ARG WITH_ANDROID=1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    PATH="/opt/android-sdk/build-tools/36.0.0:/opt/android-sdk/platform-tools:/usr/local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl util-linux \
    && if [ "$WITH_ANDROID" = "1" ]; then \
         apt-get install -y --no-install-recommends bash openjdk-17-jdk-headless unzip; \
       fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY . .

RUN if [ "$WITH_ANDROID" = "1" ]; then bash server/scripts/install_android_sdk.sh; fi \
    && useradd --create-home --uid 1000 --shell /bin/sh webtoapp \
    && mkdir -p /app/generated /app/certs/app-keys /app/server/engine/_android_template \
    && chown -R webtoapp:webtoapp /app/generated /app/certs /app/server/engine/_android_template \
    && chmod 755 /app/docker/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
