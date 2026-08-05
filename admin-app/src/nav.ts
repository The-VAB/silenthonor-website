import type { ComponentType, SVGProps } from "react";
import {
  IconOverview,
  IconMembers,
  IconApplications,
  IconDd214,
  IconStaff,
  IconCourses,
  IconKnowledge,
  IconAnnounce,
  IconContacts,
  IconMessages,
  IconAudit,
  IconPipeline,
  IconReports,
  IconAssistant,
} from "@/components/icons";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  /** Key into the /api/admin/stats response for the sidebar count badge. */
  badge?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "At a glance",
    items: [
      { path: "/", label: "Overview", icon: IconOverview },
      { path: "/assistant", label: "Assistant", icon: IconAssistant },
      { path: "/pipeline", label: "Pipeline", icon: IconPipeline },
      { path: "/reports", label: "Reports", icon: IconReports },
    ],
  },
  {
    label: "People",
    items: [
      { path: "/members", label: "Members", icon: IconMembers },
      { path: "/applications", label: "Applications", icon: IconApplications },
      { path: "/dd214", label: "DD-214 Review", icon: IconDd214, badge: "pending_verification" },
      { path: "/staff", label: "Staff & Counselors", icon: IconStaff },
    ],
  },
  {
    label: "Content",
    items: [
      { path: "/courses", label: "Courses", icon: IconCourses },
      { path: "/knowledge", label: "Knowledge Base", icon: IconKnowledge },
      { path: "/announcements", label: "Announcements", icon: IconAnnounce },
    ],
  },
  {
    label: "Inbox",
    items: [
      { path: "/contacts", label: "Contacts", icon: IconContacts },
      { path: "/messages", label: "Messages", icon: IconMessages, badge: "unread_messages" },
      { path: "/audit", label: "Audit Log", icon: IconAudit },
    ],
  },
];

export const ALL_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

export function titleFor(pathname: string): string {
  const hit = ALL_ITEMS.find((i) => i.path === pathname);
  return hit?.label ?? "Admin";
}
