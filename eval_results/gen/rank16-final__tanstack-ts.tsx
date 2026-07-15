import { useState } from 'react';
import { useInfiniteQuery, InfiniteData } from '@tanstack/react-query';

interface Product {
  id: number;
  name: string;
  price: number;
}

async function fetchProducts(pageParam = 1): Promise<{ products: Product[]; nextPage: number }> {
  const res = await fetch(`/api/products?page=${pageParam}`);
  if (!res.ok) throw new Error('Failed to fetch products');
  return res.json();
}

function Products() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error, hasNextPage, fetchNextPage } = useInfiniteQuery(
    ['products'],
    ({ pageParam = 1 }) => fetchProducts(pageParam),
    {
      getNextPageParam: (lastPage) => lastPage.nextPage,
      keepPreviousData: true,
    }
  );

  if (isLoading) return <div>Loading...</div>;
  if (isError) return <div>Error: {(error as Error).message}</div>;

  return (
    <>
      <ul>
        {data?.pages.flatMap((p) => p.products).map((p) => (
          <li key={p.id}>{p.name} - ${p.price}</li>
        ))}
      </ul>
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={!hasNextPage}>
          Load More
        </button>
      )}
    </>
  );
}

export default Products;