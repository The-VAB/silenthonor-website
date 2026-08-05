import { useEffect, type ReactNode } from "react";

export function Drawer({
  avatar,
  title,
  meta,
  tabs,
  active,
  onTab,
  onClose,
  footer,
  children,
}: {
  avatar?: string;
  title: ReactNode;
  meta?: ReactNode;
  tabs?: { key: string; label: string }[];
  active?: string;
  onTab?: (key: string) => void;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true">
        <div className="drawer-head">
          {avatar !== undefined && <div className="avatar-lg">{avatar}</div>}
          <div style={{ minWidth: 0 }}>
            <h2>{title}</h2>
            {meta && <div className="meta">{meta}</div>}
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {tabs && tabs.length > 0 && (
          <div className="tabs">
            {tabs.map((t) => (
              <button
                key={t.key}
                className={"tab" + (active === t.key ? " active" : "")}
                onClick={() => onTab?.(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-foot">{footer}</div>}
      </aside>
    </>
  );
}
