import { useInfiniteQuery, InfiniteData } from '@tanstack/react-query';
import axios from 'axios';

interface Product { id: number; name: string; price: number; }

async function fetchProducts(pageParam = 1): Promise<{ products: Product[] }> {
  const res = await axios.get(`/api/products?page=${pageParam}`);
  return res.data;
}

function ProductList() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useInfiniteQuery<InfiniteData<{ products: Product[] }>>(
      'products',
      fetchProducts,
      { getNextPageParam: (last) => last.products.length > 0 ? last.products.at(-1)?.id : undefined }
    );

  if (isLoading) return <p>로딩 중...</p>;
  if (isError) return <p>오류 발생</p>;

  return (
    <div>
      <ul>{data?.pages.flatMap((pg) => pg.products).map((p) => <li key={p.id}>{p.name}</li>)}</ul>
      <button onClick={() => fetchNextPage()} disabled={!hasNextPage || isFetchingNextPage}>
        {isFetchingNextPage ? '로딩...' : hasNextPage ? '더보기' : '마지막'}
      </button>
    </div>
  );
}

export default ProductList;