/**
 * 错误边界 — 捕获 React 渲染错误，防止白屏
 */

import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-background p-6">
          <div className="max-w-md text-center">
            <div className="mb-4 flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10">
                <AlertTriangle size={28} className="text-destructive" />
              </div>
            </div>
            <h2 className="mb-2 text-lg font-semibold text-foreground">页面出现错误</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              {this.state.error?.message || '未知错误'}
            </p>
            {/insertBefore|removeChild|not a child/i.test(this.state.error?.message || '') && (
              <p className="mb-4 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-foreground">
                💡 此类报错通常由<strong>网页翻译插件</strong>（沉浸式翻译 / Chrome「翻译此页」）注入 DOM 引起。
                请关闭本站翻译后刷新。
              </p>
            )}
            <div className="flex justify-center gap-2">
              <button
                onClick={this.handleReset}
                className="flex items-center gap-2 rounded-lg border border-border bg-secondary px-4 py-2 text-sm text-foreground transition-colors hover:bg-accent"
              >
                <RefreshCw size={14} />
                重试
              </button>
              <button
                onClick={() => window.location.reload()}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground transition-colors hover:bg-primary/90"
              >
                刷新页面
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
