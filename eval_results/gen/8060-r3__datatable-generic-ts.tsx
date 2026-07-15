import React from 'react';

interface DataTableProps<T> {
  rows: T[];
  columns: Array<{
    key: keyof T;
    header: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
}

const DataTable = <T extends {}>({ rows, columns }: DataTableProps<T>) => (
  <table>
    <thead>
      <tr>{columns.map((column) => <th key={column.key}>{column.header}</th>)}</tr>
    </thead>
    <tbody>
      {rows.map((row) => (
        <tr key={JSON.stringify(row)}>
          {columns.map((column) => (
            <td key={`${column.key}-${JSON.stringify(row)}`}>
              {column.render ? column.render(row[column.key] as T[keyof T], row) : row[column.key]}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);

export default DataTable;