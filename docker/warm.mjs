// Build-time only: import the server once so the compile cache is written, then leave.
// The server binds a port and starts its Firestore warm-up on import; neither matters
// here, and the timeout is what lets lazily-required modules finish loading first.
await import('./index.js');
setTimeout(() => process.exit(0), 700);
