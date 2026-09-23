export interface ToastItem { id: number; text: string; kind: 'info' | 'error' }

export const toasts: ToastItem[] = $state([]);
let nextId = 1;

export function toast(text: string, kind: 'info' | 'error' = 'info'): void {
  const id = nextId++;
  toasts.push({ id, text, kind });
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id);
    if (i >= 0) toasts.splice(i, 1);
  }, kind === 'error' ? 5000 : 2500);
}

export function toastError(error: unknown): void {
  toast(error instanceof Error ? error.message : String(error), 'error');
}
