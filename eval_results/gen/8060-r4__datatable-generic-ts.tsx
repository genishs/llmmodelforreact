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
      {rows.map((row) => (
        <tr key={JSON.stringify(row)}>
          {columns.map(({ key, render }) => (
            <td key={`${key}-${JSON.stringify(row)}`}>
              {render ? render(row[key], row) : row[key]}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);

export default DataTable;