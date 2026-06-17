import type { ReactNode } from "react";

export function Panel({
  children,
  className,
  eyebrow,
  icon,
  title,
}: {
  children: ReactNode;
  className?: string;
  eyebrow?: string;
  icon?: ReactNode;
  title?: string;
}) {
  return (
    <section className={["panel", className].filter(Boolean).join(" ")}>
      {(eyebrow || title || icon) && (
        <div className="panel-heading">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {icon}
        </div>
      )}
      {children}
    </section>
  );
}
