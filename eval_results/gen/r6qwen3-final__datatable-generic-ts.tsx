import React from 'react';

interface DataTableProps<T> {
  rows: T[];
  columns: { key: keyof T; header: string; render?: (v: T[keyof T], r: T) => React.ReactNode }[];
}

function DataTable<T>({ rows, columns }: DataTableProps<T>) {
  return (
    <table>
      <thead>
        <tr>{columns.map((c) => <th key={String(c.key)}>{c.header}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {columns.map((col) => (
              <td key={String(col.key)}>
                {col.render ? col.render(row[col.key] as any, row) : String(row[col.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default DataTable;