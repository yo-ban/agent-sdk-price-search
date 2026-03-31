# Pre-provisioned Patchright-backed playwright-cli runtime image.
FROM mcr.microsoft.com/playwright:v1.58.2-noble

ARG PLAYWRIGHT_CLI_VERSION=0.1.1
ARG PATCHRIGHT_VERSION=1.58.2
ARG RUNTIME_PREFIX=/opt/playwright-cli-runtime

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_CLI_RUNTIME_PREFIX=${RUNTIME_PREFIX}

COPY infra/docker/playwright/patch_playwright_cli_runtime.py /opt/price-search/playwright/patch_playwright_cli_runtime.py
COPY workspace_assets/playwright/cli.config.json /opt/price-search/playwright/cli.config.json
COPY infra/docker/playwright/entrypoint.sh /usr/local/bin/price-search-playwright-entrypoint

RUN mkdir -p "${RUNTIME_PREFIX}" /opt/price-search/playwright && \
    npm install --prefix "${RUNTIME_PREFIX}" "@playwright/cli@${PLAYWRIGHT_CLI_VERSION}" "patchright-core@${PATCHRIGHT_VERSION}" >/dev/null && \
    rm -rf "${RUNTIME_PREFIX}/node_modules/playwright-core" && \
    ln -s "${RUNTIME_PREFIX}/node_modules/patchright-core" "${RUNTIME_PREFIX}/node_modules/playwright-core" && \
    python3 /opt/price-search/playwright/patch_playwright_cli_runtime.py "${RUNTIME_PREFIX}" && \
    bundled_chrome="$(find /ms-playwright -path '*/chrome-linux*/chrome' -type f | sort | head -n 1)" && \
    test -n "${bundled_chrome}" && \
    mkdir -p /opt/google/chrome && \
    ln -sf "${bundled_chrome}" /opt/google/chrome/chrome && \
    chmod +x /usr/local/bin/price-search-playwright-entrypoint

WORKDIR /
ENTRYPOINT ["/usr/local/bin/price-search-playwright-entrypoint"]
