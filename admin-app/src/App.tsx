import { HashRouter, Routes, Route } from "react-router-dom";
import { useMe } from "@/auth/useMe";
import { roleOf } from "@/lib/types";
import { ApiError, goToLogin } from "@/lib/api";
import Shell from "@/components/Shell";
import Overview from "@/pages/Overview";
import Members from "@/pages/Members";
import Applications from "@/pages/Applications";
import Dd214 from "@/pages/Dd214";
import Staff from "@/pages/Staff";
import Courses from "@/pages/Courses";
import Knowledge from "@/pages/Knowledge";
import Announcements from "@/pages/Announcements";
import Contacts from "@/pages/Contacts";
import Messages from "@/pages/Messages";
import Audit from "@/pages/Audit";
import Pipeline from "@/pages/Pipeline";
import Reports from "@/pages/Reports";
import Placeholder from "@/pages/Placeholder";
import { ALL_ITEMS } from "@/nav";

// Every section now has a real page.
const BUILT: Record<string, JSX.Element> = {
  "/pipeline": <Pipeline />,
  "/reports": <Reports />,
  "/members": <Members />,
  "/applications": <Applications />,
  "/dd214": <Dd214 />,
  "/staff": <Staff />,
  "/courses": <Courses />,
  "/knowledge": <Knowledge />,
  "/announcements": <Announcements />,
  "/contacts": <Contacts />,
  "/messages": <Messages />,
  "/audit": <Audit />,
};

function Gate({ children }: { children: string }) {
  return (
    <div className="gate">
      <div className="box">
        <h1>Silent Honor</h1>
        <p>{children}</p>
        <button className="btn primary" onClick={goToLogin} style={{ margin: "0 auto" }}>
          Go to sign in
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const { data: me, isLoading, isError, error } = useMe();

  if (isLoading) {
    return (
      <div className="gate">
        <div className="spinner" style={{ borderTopColor: "var(--gold)" }} />
      </div>
    );
  }

  // Not signed in → bounce to the static login page.
  if (isError && error instanceof ApiError && error.status === 401) {
    goToLogin();
    return <Gate>Redirecting to sign in…</Gate>;
  }
  if (isError || !me) {
    return <Gate>We couldn’t verify your session. Please sign in again.</Gate>;
  }
  if (!roleOf(me).includes("admin")) {
    return <Gate>This area is for administrators only.</Gate>;
  }

  // Sections not yet built render the placeholder (Overview is live).
  const rest = ALL_ITEMS.filter((i) => i.path !== "/");

  return (
    <HashRouter>
      <Routes>
        <Route element={<Shell me={me} />}>
          <Route index element={<Overview />} />
          {rest.map((i) => (
            <Route key={i.path} path={i.path.slice(1)} element={BUILT[i.path] ?? <Placeholder title={i.label} />} />
          ))}
          <Route path="*" element={<Placeholder title="Not Found" />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
