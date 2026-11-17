/**
 * Per-student storage isolation.
 *
 * Regression: roadmap progress and generated roadmaps used one global
 * localStorage key, so signing in as a new account on the same browser showed
 * the previous account's pathway on the dashboard.
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { clearTokens, storeTokens } from "@/lib/api/client";
import { ProgressProvider, useProgress } from "@/lib/roadmap/ProgressStore";
import { activeStudentScope } from "@/lib/roadmap/scope";
import { progressStorageKey } from "@/lib/roadmap/storage";
import { fakeAccessToken } from "./fixtures";

function Probe() {
  const { state, ensure } = useProgress();
  return (
    <div>
      <span data-testid="tracked">{Object.keys(state).join(",") || "(none)"}</span>
      <button type="button" onClick={() => ensure("data-scientist")}>
        track
      </button>
    </div>
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("activeStudentScope", () => {
  it("namespaces by the access token's sub claim", () => {
    expect(activeStudentScope()).toBe("anonymous");

    window.localStorage.setItem("cm_access_token", fakeAccessToken("abc123"));
    expect(activeStudentScope()).toBe("student:abc123");
  });

  it("falls back to anonymous for malformed or claim-less tokens", () => {
    window.localStorage.setItem("cm_access_token", "not-a-jwt");
    expect(activeStudentScope()).toBe("anonymous");

    window.localStorage.setItem("cm_access_token", "a.%%%.c");
    expect(activeStudentScope()).toBe("anonymous");

    window.localStorage.setItem("cm_access_token", `a.${btoa("{}")}.c`);
    expect(activeStudentScope()).toBe("anonymous");
  });
});

describe("ProgressProvider across accounts", () => {
  it("shows only the signed-in student's pathways", async () => {
    const user = userEvent.setup();

    act(() => storeTokens(fakeAccessToken("student-a"), "refresh-a"));
    const view = render(
      <ProgressProvider>
        <Probe />
      </ProgressProvider>
    );

    await user.click(screen.getByRole("button", { name: "track" }));
    expect(screen.getByTestId("tracked")).toHaveTextContent("data-scientist");

    // Signing out must not leave the pathway visible to the next visitor.
    act(() => clearTokens());
    expect(screen.getByTestId("tracked")).toHaveTextContent("(none)");

    // A brand-new account on the same browser starts with an empty dashboard...
    act(() => storeTokens(fakeAccessToken("student-b"), "refresh-b"));
    expect(screen.getByTestId("tracked")).toHaveTextContent("(none)");

    // ...while the pending write from the first student landed on their own
    // entry, so signing back in restores it.
    expect(window.localStorage.getItem(progressStorageKey("student:student-a"))).toContain(
      "data-scientist"
    );
    expect(
      window.localStorage.getItem(progressStorageKey("student:student-b")) ?? ""
    ).not.toContain("data-scientist");

    act(() => storeTokens(fakeAccessToken("student-a"), "refresh-a"));
    expect(screen.getByTestId("tracked")).toHaveTextContent("data-scientist");

    view.unmount();
  });
});
