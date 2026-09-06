# Two stages so the runtime image carries no toolchain and no source: what ships is the
# compiled server, its production dependencies, and nothing else. Cold start is the
# budget this service is written against, and a smaller image is a faster first pull.
FROM node:24-slim AS build
WORKDIR /app

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable

# Dependencies first, so a source-only change reuses the install layer.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build && pnpm prune --prod

FROM node:24-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

# Cloud Run says which port to listen on; adapter-node reads PORT. Binding to every
# interface is required — the container's loopback is not where requests arrive.
ENV HOST=0.0.0.0

COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

# Never root, and never a shell we do not need. The base image ships a `node` user.
USER node

CMD ["node", "build"]
