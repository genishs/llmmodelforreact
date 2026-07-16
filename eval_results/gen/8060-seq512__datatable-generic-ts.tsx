import React from 'react';

interface DataTableProps<T> {
  rows: T[];
  columns: Array<{
    key: keyof T;
    header: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
}

const DataTable = <T extends {}>({ rows, columns }: DataTableProps<T>): JSX.Element => (
  <table>
    <thead>
      <tr>{columns.map(({ header }) => <th key={header}>{header}</th>)}</tr>
    </thead>
    <tbody>
      {rows.map((row, index) => (
        <tr key={index}>
          {columns.map(({ key, render }) => (
            <td key={`${key}-${index}`}>
              {render ? render(row[key], row) : (row[key] as unknown as string)}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);

export default DataTable;