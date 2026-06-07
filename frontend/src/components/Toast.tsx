/**
 * Toast 通知组件 — 轻量级全局通知，支持成功/错误/警告类型
 */

import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, X } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // 没有 Provider 时返回空操作，避免报错
    return { showToast: (_type: ToastType, _message: string) => {} };
  }
  return ctx;
}

const ICONS: Record<ToastType, React.ElementType> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
};

const COLORS: Record<ToastType, { bg: string; border: string; icon: string; text: string }> = {
  success: { bg: 'bg-emerald-50', border: 'border-emerald-200', icon: 'text-emerald-500', text: 'text-emerald-700' },
  error: { bg: 'bg-red-50', border: 'border-red-200', icon: 'text-red-500', text: 'text-red-700' },
  warning: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-500', text: 'text-amber-700' },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, type, message }]);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast 容器 — 固定在右下角 */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col-reverse gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onRemove }: { toast: ToastItem; onRemove: (id: number) => void }) {
  const Icon = ICONS[toast.type];
  const colors = COLORS[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => onRemove(toast.id), 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  return (
    <div
      className={`pointer-events-auto flex items-center gap-3 rounded-xl border ${colors.border} ${colors.bg} px-4 py-3 shadow-lg animate-in slide-in-from-right`}
      style={{ minWidth: 280, maxWidth: 420 }}
    >
      <Icon size={18} className={`shrink-0 ${colors.icon}`} />
      <p className={`text-sm ${colors.text} flex-1`}>{toast.message}</p>
      <button
        onClick={() => onRemove(toast.id)}
        className="shrink-0 text-gray-400 hover:text-gray-600"
      >
        <X size={14} />
      </button>
    </div>
  );
}
