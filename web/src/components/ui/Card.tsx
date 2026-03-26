// - Универсальная карточка с опциональным заголовком и градиентом
import type { ReactNode } from 'react';

interface CardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  gradient?: boolean;
}

export function Card({ title, children, className = '', gradient = true }: CardProps) {
  return (
    <div className={`rounded-lg border border-border p-4 ${
      gradient
        ? 'bg-gradient-to-br from-bg-card to-bg-card-hover'
        : 'bg-bg-card'
    } ${className}`}>
      {title && (
        <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">
          {title}
        </div>
      )}
      {children}
    </div>
  );
}
