FROM node:22.17.0-alpine AS base

ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_CACHE_DIR=/tmp/otsoc-vite-cache

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY --chown=node:node frontend .
RUN chown -R node:node /app

FROM base AS test

COPY --chown=node:node contracts /contracts

USER node

FROM base AS runtime

USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM mcr.microsoft.com/playwright:v1.62.1-noble AS e2e

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend .

CMD ["npm", "run", "e2e"]
