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
} from "@/components/icons";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  /** Key into a counts map for the sidebar badge. */
  badge?: "pending_dd214" | "open_applications" | "unread_messages";
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
      { path: "/pipeline", label: "Pipeline", icon: IconPipeline },
      { path: "/reports", label: "Reports", icon: IconReports },
    ],
  },
  {
    label: "People",
    items: [
      { path: "/members", label: "Members", icon: IconMembers },
      { path: "/applications", label: "Applications", icon: IconApplications, badge: "open_applications" },
      { path: "/dd214", label: "DD-214 Review", icon: IconDd214, badge: "pending_dd214" },
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
