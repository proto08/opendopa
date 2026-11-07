import { afterEach, describe, expect, it, vi } from "vitest";

const azure = vi.hoisted(() => ({ useAzureMonitor: vi.fn() }));
vi.mock("@azure/monitor-opentelemetry", () => azure);

import { register } from "./instrumentation";

afterEach(() => {
  vi.unstubAllEnvs();
  azure.useAzureMonitor.mockClear();
});

describe("register", () => {
  it("接続文字列がなければ何も始めない", async () => {
    vi.stubEnv("NEXT_RUNTIME", "nodejs");
    vi.stubEnv("APPLICATIONINSIGHTS_CONNECTION_STRING", "");
    await register();
    expect(azure.useAzureMonitor).not.toHaveBeenCalled();
  });

  it("接続文字列があれば Azure Monitor を始める", async () => {
    vi.stubEnv("NEXT_RUNTIME", "nodejs");
    vi.stubEnv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=x");
    await register();
    expect(azure.useAzureMonitor).toHaveBeenCalledOnce();
  });
});
