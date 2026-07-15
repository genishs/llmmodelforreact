import React from 'react';

interface Column<T> {
  key: keyof T;
  header: string;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

function DataTable<T>(props: { rows: T[]; columns: Column<T>[] }) {
  const { rows, columns } = props;
  return (
    <table>
      <thead>
        <tr>{columns.map((c) => <th key={String(c.key)}>{c.header}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row[(columns[0]?.key as keyof T)]))}>
            {columns.map((c) => {
              const value = row[c.key];
              return (
                <td key={String(c.key)}>
                  {c.render ? c.render(value, row) : String(value)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default DataTable;