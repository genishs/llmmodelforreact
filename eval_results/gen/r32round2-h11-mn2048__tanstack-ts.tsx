import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Product {
  id: number;
  name: string;
  price: number;
}

async function fetchProducts(pageParam = 1) {
  const res = await axios.get<{ products: Product[]; nextPage: number }>(
    `/api/products?page=${pageParam}`
  );
  return res.data;
}

function ProductList() {
  const { data, isLoading, isError, hasNextPage, fetchNextPage } =
    useInfiniteQuery(['products'], fetchProducts, {
      getNextPageParam: (lastPage) => lastPage.nextPage,
    });

  if (isLoading) return <div>로딩 중...</div>;
  if (isError) return <div>오류 발생</div>;

  return (
    <ul>
      {data?.pages.flatMap((p) => p.products).map((p) => (
        <li key={p.id}>{p.name} (${p.price})</li>
      ))}
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={!hasNextPage}>
          더보기
        </button>
      )}
    </ul>
  );
}

export default ProductList;