import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode;
  size?: "normal" | "small";
  variant?: ButtonVariant;
}

const variantClass: Record<ButtonVariant, string> = {
  primary: "primary-button",
  secondary: "secondary-button",
  danger: "danger-button",
  ghost: "ghost-button",
  icon: "icon-button",
};

export function Button({
  children,
  className,
  icon,
  size = "normal",
  variant = "secondary",
  ...props
}: ButtonProps) {
  const classes = [
    variantClass[variant],
    size === "small" ? "button-small" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={classes} type="button" {...props}>
      {icon}
      {children}
    </button>
  );
}
