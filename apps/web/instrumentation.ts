// サーバー起動時に1回呼ばれる(Next.js の instrumentation)。
// APPLICATIONINSIGHTS_CONNECTION_STRING があるときだけ Azure Monitor の計測を始める。ないとき(ローカル・テスト)は何もしない。
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { telemetryEnabled } = await import("./lib/telemetry");
  if (!telemetryEnabled()) return;
  const { useAzureMonitor: startAzureMonitor } = await import(
    "@azure/monitor-opentelemetry"
  );
  startAzureMonitor({
    azureMonitorExporterOptions: {
      connectionString: process.env.APPLICATIONINSIGHTS_CONNECTION_STRING,
    },
  });
}
