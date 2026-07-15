import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Product { id: number; name: string; price: number; }
type Page = { products: Product[]; nextPage?: number };

async function fetchProducts(pageParam = 1): Promise<Page> {
  const res = await axios.get<{ products: Product[], nextPage?: number }>('/api/products', { params: { page: pageParam } });
  return res.data;
}

function ProductList() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } = useInfiniteQuery(
    'products',
    fetchProducts,
    { getNextPageParam: (last) => last.nextPage }
  );

  if (isLoading) return <p>Loading...</p>;
  if (isError) return <p>Error fetching products</p>;

  return (
    <div>
      <ul>
        {data?.pages.flatMap((page) => page.products).map((p) => (
          <li key={p.id}>{p.name} - ${p.price}</li>
        ))}
      </ul>
      {hasNextPage && !isFetchingNextPage ? (
        <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>Load More</button>
      ) : (
        <p>No more products</p>
      )}
    </div>
  );
}

export default ProductList;