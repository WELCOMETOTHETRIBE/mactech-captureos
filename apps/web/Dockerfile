# syntax=docker/dockerfile:1.7
# mactech-web Railway service: Next.js 14 server build.
# Build context is the REPO ROOT so we can lift apps/web from the monorepo
# alongside the package-lock managed at root via pnpm workspaces.

FROM node:20-bookworm-slim AS deps
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /repo
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter ./apps/web... --frozen-lockfile=false

FROM node:20-bookworm-slim AS build
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-workspace.yaml ./
COPY apps/web ./apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter ./apps/web build

FROM node:20-bookworm-slim AS runtime
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /repo
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /repo/node_modules ./node_modules
COPY --from=build /repo/apps/web ./apps/web
COPY package.json pnpm-workspace.yaml ./
WORKDIR /repo/apps/web
EXPOSE 3000
CMD ["pnpm", "start"]
