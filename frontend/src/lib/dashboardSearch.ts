// The dashboard keeps its filters in the URL (?date_from=...&airline=...). A plain link to "/"
// drops them, so the last filters are remembered for the browser tab and every link back to
// the dashboard uses them. Storage can be missing or blocked; the dashboard still works.

const KEY = "console.dashboardSearch";

export function rememberDashboardSearch(search: string): void {
  try {
    sessionStorage.setItem(KEY, search);
  } catch {
    // Not remembered; links go to the default view.
  }
}

/** The dashboard path with the filters the user last had, or the default view. */
export function dashboardPath(): string {
  try {
    const search = sessionStorage.getItem(KEY) ?? "";
    return search.startsWith("?") ? `/${search}` : "/";
  } catch {
    return "/";
  }
}
