import { describe, expect, it } from "vitest";
import { groupKey, groupLabel, groupPath, isoWeek } from "./format";

// Local-time timestamps (no zone suffix) so the results do not depend on the test machine's zone.
describe("date grouping", () => {
  it("numbers ISO weeks across year boundaries", () => {
    expect(isoWeek(new Date("2020-07-14T12:00:00"))).toMatchObject({ year: 2020, week: 29 });
    // 1 Jan 2021 is a Friday: still in 2020's week 53.
    expect(isoWeek(new Date("2021-01-01T12:00:00"))).toMatchObject({ year: 2020, week: 53 });
    expect(isoWeek(new Date("2021-01-04T00:30:00"))).toMatchObject({ year: 2021, week: 1 });
    // Monday 29 Dec 2025 already belongs to 2026's week 1.
    expect(isoWeek(new Date("2025-12-29T08:00:00"))).toMatchObject({ year: 2026, week: 1 });
    // Sunday is the last day of the week.
    expect(isoWeek(new Date("2020-07-19T23:59:00"))).toMatchObject({ week: 29 });
    expect(isoWeek(new Date("2020-07-20T00:00:00"))).toMatchObject({ week: 30 });
  });

  it("builds sortable keys per grouping", () => {
    const at = "2020-07-14T16:30:00";
    expect(groupKey(at, "month")).toBe("2020-07");
    expect(groupKey(at, "week")).toBe("2020-W29");
    expect(groupKey(at, "day")).toBe("2020-07-14");
    expect(groupKey("not a date", "day")).toBe("unknown");
  });

  it("nests sections as year › month › week or day", () => {
    const keys = (by: "month" | "week" | "day") =>
      groupPath("2020-07-27T10:00:00", by).map((level) => level.key);
    expect(keys("month")).toEqual(["2020", "2020-07"]);
    expect(keys("week")).toEqual(["2020", "2020-07", "2020-07/2020-W31"]);
    expect(keys("day")).toEqual(["2020", "2020-07", "2020-07/2020-07-27"]);
    // A week spanning months is split under each month.
    expect(groupPath("2020-08-02T10:00:00", "week")[2]?.key).toBe("2020-08/2020-W31");
    expect(groupPath("bad", "day")).toEqual([{ key: "unknown", label: "Unknown date" }]);
  });

  it("labels weeks with their number and date range", () => {
    const label = groupLabel("2020-07-14T16:30:00", "week");
    expect(label.startsWith("CW 29 · ")).toBe(true);
    expect(label).toContain("2020");
    expect(groupLabel("2020-07-14T16:30:00", "day")).toContain("2020");
  });
});
