export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export const onRequestError = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN
  ? (async (...args: Parameters<typeof import("@sentry/nextjs").captureRequestError>) => {
      const Sentry = await import("@sentry/nextjs");
      Sentry.captureRequestError(...args);
    })
  : undefined;
