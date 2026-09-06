// Point V8's compile cache at a directory baked into the image and populated during the
// build, so a cold instance loads the server from bytecode instead of parsing 7 MB of
// JavaScript. Loaded with `node --import`, so it runs before the server does.
//
// Resolved against this file rather than hardcoded, so warming and serving agree wherever
// the image puts them — V8 keys cache entries by absolute path, and a cache warmed at a
// different path is silently ignored rather than reported.
import { enableCompileCache } from 'node:module';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

enableCompileCache(dirname(fileURLToPath(import.meta.url)) + '/.compile-cache');
