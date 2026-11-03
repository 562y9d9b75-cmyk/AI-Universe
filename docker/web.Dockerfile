# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1 AIU_API_ORIGIN=http://api:8000
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM node:24-bookworm-slim
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 AIU_API_ORIGIN=http://api:8000
WORKDIR /app/frontend
COPY --from=build --chown=node:node /app/frontend ./
USER node
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
