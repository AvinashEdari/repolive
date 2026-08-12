import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

describe("production routing", () => {
  it("routes the obsolete landing flow to the authoritative analysis workspace", async () => {
    expect(await nextConfig.redirects?.()).toContainEqual({
      source: "/",
      destination: "/analyze",
      permanent: false,
    });
  });
});
