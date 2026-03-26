// - Универсальная таблица с типизированными колонками
import type { ReactNode } from 'react';
import { t } from '../../lib/i18n';

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField: string;
}

export function Table<T extends object>({ columns, data, keyField }: TableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-text-secondary text-center py-8">
        {t.table.noData}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th key={col.key} className="text-left py-3 px-4 text-xs uppercase tracking-wider text-text-secondary">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={String((row as Record<string, unknown>)[keyField])}
              className="border-b border-border/30 hover:bg-bg-card-hover transition-colors"
            >
              {columns.map((col) => (
                <td key={col.key} className="py-3 px-4">
                  {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
