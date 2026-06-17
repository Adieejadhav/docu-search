import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

export function ConfirmDialog({
  cancelLabel = "Cancel",
  children,
  confirmDisabled,
  confirmLabel,
  isOpen,
  onCancel,
  onConfirm,
  title,
}: {
  cancelLabel?: string;
  children: ReactNode;
  confirmDisabled?: boolean;
  confirmLabel: string;
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
}) {
  if (!isOpen) return null;

  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        aria-modal="true"
        className="confirm-dialog"
        role="dialog"
        aria-labelledby="confirm-dialog-title"
      >
        <header>
          <h2 id="confirm-dialog-title">{title}</h2>
          <Button aria-label="Close dialog" onClick={onCancel} variant="icon">
            <X size={17} />
          </Button>
        </header>
        <div className="dialog-body">{children}</div>
        <footer>
          <Button onClick={onCancel}>{cancelLabel}</Button>
          <Button
            disabled={confirmDisabled}
            onClick={onConfirm}
            variant="danger"
          >
            {confirmLabel}
          </Button>
        </footer>
      </section>
    </div>
  );
}
