import { useState, useEffect } from 'react';
import { useInfiniteQuery, UseInfiniteQueryResult } from '@tanstack/react-query';

interface Product {
  id: number;
  name: string;
  price: number;
}

async function fetchProducts({ pageParam = 1 }: { pageParam?: number }) {
  const res = await fetch(`https://api.example.com/products?page=${pageParam}&limit=20`);
  return (await res.json()) as { products: Product[]; nextCursor: number | null };
}

function InfiniteProductList(): JSX.Element {
  const [queryKey] = useState(['products']);
  const result: UseInfiniteQueryResult<ReturnType<typeof fetchProducts>> =
    useInfiniteQuery({
      queryKey,
      queryFn: ({ pageParam }) => fetchProducts({ pageParam }),
      getNextPageParam: (last) => last.nextCursor ?? undefined,
    });

  if (result.isLoading) return <p>로딩 중...</p>;
  if (result.isError) return <p>오류가 발생했습니다.</p>;

  return (
    <>
      <ul>
        {result.data.pages.flatMap((p) => p.products).map((product) => (
          <li key={product.id}>{product.name} - ${product.price}</li>
        ))}
      </ul>
      {!result.hasNextPage ? null : (
        <button onClick={() => result.fetchNextPage()}>더 불러오기</button>
      )}
    </>
  );
}

export default InfiniteProductList;