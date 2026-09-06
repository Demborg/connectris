# Three stages, because cold start is the budget this service is written against and two
# of the three things a cold Node process does can be moved into the image.
#
# Measured on Cloud Run (docs are outside this repo): a plain `node build` cold start is
# ~1764 ms, of which ~690 ms is finding, reading and parsing the server's module graph.
# Bundling to one file removes the finding and reading; a compile cache warmed at build
# time removes the parsing. Together they take the cold start to ~1116 ms.
#
# Image size is deliberately not a goal. Alpine is 26% smaller than this base and 68%
# slower to start, and the fastest image measured was larger than the alpine one. Cloud Run
# streams layers lazily, so bytes that are never read cost nothing.

FROM node:24-slim AS build
WORKDIR /app

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable

# Dependencies first, so a source-only change reuses the install layer.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# One file instead of a node_modules tree: no resolution, no thousands of opens against a
# lazily-streamed filesystem, no install in the runtime image.
#
# google-gax reads `__dirname` at module scope, so the CJS shims have to be handed back to
# an ESM bundle or the Firestore client throws on load.
RUN pnpm exec esbuild build/index.js --bundle --platform=node --format=esm \
      --target=node24 --outfile=/out/index.js \
      --banner:js='import{createRequire as __cr}from "node:module";import{dirname as __dn}from "node:path";import{fileURLToPath as __fu}from "node:url";const require=__cr(import.meta.url);const __filename=__fu(import.meta.url);const __dirname=__dn(__filename);' \
 && cp -r build/client /out/client
COPY docker/cache.mjs docker/warm.mjs /out/

# adapter-node resolves its asset directory from `import.meta.url`, so the bundle has to sit
# one level above `client/` exactly as `build/index.js` did.
FROM node:24-slim AS warm
WORKDIR /app
COPY --from=build /out /app

# Populate the compile cache at the path it will be read from — V8 keys entries by absolute
# path, so warming anywhere else produces a cache the runtime silently ignores.
RUN node --import ./cache.mjs warm.mjs > /dev/null 2>&1 || true; \
    rm warm.mjs; \
    test -s "$(find /app/.compile-cache -type f -size +100k | head -1)" \
      || { echo "compile cache was not written; startup would silently regress"; exit 1; }

FROM node:24-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

# Cloud Run says which port to listen on; adapter-node reads PORT. Binding to every
# interface is required — the container's loopback is not where requests arrive.
ENV HOST=0.0.0.0

COPY --from=warm /app /app

# Never root, and never a shell we do not need. The base image ships a `node` user. The
# cache is read-only to it, which is all Node needs.
USER node

CMD ["node", "--import", "./cache.mjs", "index.js"]
